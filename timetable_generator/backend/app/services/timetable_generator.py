"""CSP-based timetable generation algorithm."""
import asyncio
from typing import Dict, List, Tuple, Optional, Set, Any
from datetime import time
import uuid
from collections import defaultdict
import random

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from app.models.timetable import Timetable, TimetableSlot, TimetableStatus, TimetableType
from app.models.teacher import Teacher, TeacherUnavailability
from app.models.subject import Subject
from app.models.class_ import Class, ClassSubject
from app.models.room import Room, RoomUnavailability, RoomType
from app.models.period import Period
from app.models.user import User


class TimetableGenerator:
    """CSP solver for timetable generation."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.school_id = None
        self.term = None
        self.academic_year = None
        self.parameters = {}
        
        # Data containers
        self.classes: Dict[uuid.UUID, Class] = {}
        self.teachers: Dict[uuid.UUID, Teacher] = {}
        self.subjects: Dict[uuid.UUID, Subject] = {}
        self.rooms: Dict[uuid.UUID, Room] = {}
        self.periods: List[Period] = []
        
        # Constraints
        self.teacher_unavailability: Dict[uuid.UUID, List[Tuple[str, int]]] = defaultdict(list)
        self.room_unavailability: Dict[uuid.UUID, List[Tuple[str, int]]] = defaultdict(list)
        self.class_subjects: Dict[uuid.UUID, List[Tuple[uuid.UUID, uuid.UUID]]] = defaultdict(list)
        self.teacher_subjects: Dict[uuid.UUID, Set[uuid.UUID]] = defaultdict(set)
        
        # Variables
        self.variables: List[Dict] = []  # Each variable is a (class_id, day, period) slot
        self.domains: Dict[Tuple, List[Dict]] = {}  # Domain for each variable
        self.assignment: Dict[Tuple, Dict] = {}  # Current assignment
        self.timetable_id = None
        
        # Progress tracking
        self.progress_callback = None
        self.current_progress = 0
        self.total_variables = 0
        
    async def generate(
        self,
        school_id: uuid.UUID,
        term: str,
        academic_year: str,
        parameters: Dict,
        progress_callback=None
    ) -> uuid.UUID:
        """Generate a new timetable."""
        self.school_id = school_id
        self.term = term
        self.academic_year = academic_year
        self.parameters = parameters
        self.progress_callback = progress_callback
        
        # Step 1: Load all data
        await self._load_data()
        self._update_progress(10, "Data loaded")
        
        # Step 2: Build variables and domains
        self._build_variables()
        self._update_progress(20, "Variables created")
        
        self._build_domains()
        self._update_progress(30, "Domains built")
        
        # Step 3: Order variables by constraint (most constrained first)
        self._order_variables()
        self._update_progress(40, "Variables ordered")
        
        # Step 4: Run CSP solver
        success = await self._solve()
        
        if not success:
            raise Exception("No solution found with given constraints")
        
        self._update_progress(90, "Solution found")
        
        # Step 5: Save to database
        timetable_id = await self._save_timetable()
        self._update_progress(100, "Timetable saved")
        
        return timetable_id
    
    async def _load_data(self):
        """Load all necessary data from database."""
        # Load classes
        result = await self.db.execute(
            select(Class).where(Class.school_id == self.school_id)
        )
        for cls in result.scalars().all():
            self.classes[cls.id] = cls
        
        # Load teachers
        result = await self.db.execute(
            select(Teacher).where(
                and_(
                    Teacher.school_id == self.school_id,
                    Teacher.is_active == True
                )
            )
        )
        for teacher in result.scalars().all():
            self.teachers[teacher.id] = teacher
        
        # Load subjects
        result = await self.db.execute(
            select(Subject).where(Subject.school_id == self.school_id)
        )
        for subject in result.scalars().all():
            self.subjects[subject.id] = subject
        
        # Load rooms
        result = await self.db.execute(
            select(Room).where(
                and_(
                    Room.school_id == self.school_id,
                    Room.is_available == True
                )
            )
        )
        for room in result.scalars().all():
            self.rooms[room.id] = room
        
        # Load periods
        result = await self.db.execute(
            select(Period).where(Period.school_id == self.school_id)
        )
        self.periods = result.scalars().all()
        
        # Load teacher unavailability
        result = await self.db.execute(
            select(TeacherUnavailability).where(
                TeacherUnavailability.teacher_id.in_(self.teachers.keys())
            )
        )
        for unavail in result.scalars().all():
            self.teacher_unavailability[unavail.teacher_id].append(
                (unavail.day_of_week, unavail.period_number)
            )
        
        # Load room unavailability
        result = await self.db.execute(
            select(RoomUnavailability).where(
                RoomUnavailability.room_id.in_(self.rooms.keys())
            )
        )
        for unavail in result.scalars().all():
            self.room_unavailability[unavail.room_id].append(
                (unavail.day_of_week, unavail.period_number)
            )
        
        # Load class-subject-teacher assignments
        result = await self.db.execute(
            select(ClassSubject).where(
                ClassSubject.class_id.in_(self.classes.keys())
            )
        )
        for cs in result.scalars().all():
            self.class_subjects[cs.class_id].append((cs.subject_id, cs.teacher_id))
            self.teacher_subjects[cs.teacher_id].add(cs.subject_id)
    
    def _build_variables(self):
        """Build variables for CSP."""
        self.variables = []
        
        # For each class, create slots for each required subject
        for class_id, cls in self.classes.items():
            # Count periods needed per subject for this class
            subject_counts = defaultdict(int)
            for subject_id, teacher_id in self.class_subjects[class_id]:
                subject = self.subjects[subject_id]
                subject_counts[(subject_id, teacher_id)] = subject.periods_per_week
            
            # Create variables for each required period
            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            periods_per_day = [p for p in self.periods if not p.is_break]
            periods_by_day = defaultdict(list)
            for p in periods_per_day:
                periods_by_day[p.day_of_week].append(p.period_number)
            
            # For each subject, create required number of slots
            for (subject_id, teacher_id), count in subject_counts.items():
                for i in range(count):
                    self.variables.append({
                        "class_id": class_id,
                        "subject_id": subject_id,
                        "teacher_id": teacher_id,
                        "slot_index": i
                    })
        
        self.total_variables = len(self.variables)
    
    def _build_domains(self):
        """Build domains for each variable."""
        self.domains = {}
        
        # Get valid periods (non-break periods)
        valid_periods = [(p.day_of_week, p.period_number) for p in self.periods if not p.is_break]
        
        for var in self.variables:
            class_id = var["class_id"]
            subject_id = var["subject_id"]
            teacher_id = var["teacher_id"]
            
            subject = self.subjects[subject_id]
            domain = []
            
            # Try all possible (day, period, room) combinations
            for day, period in valid_periods:
                # Check if teacher is available
                if (day, period) in self.teacher_unavailability[teacher_id]:
                    continue
                
                # Find available rooms
                available_rooms = []
                for room_id, room in self.rooms.items():
                    # Check room availability
                    if (day, period) in self.room_unavailability[room_id]:
                        continue
                    
                    # Check room type requirement
                    if subject.requires_lab and room.room_type != RoomType.LAB:
                        continue
                    
                    # Check capacity (assuming room capacity >= class size)
                    if room.capacity < self.classes[class_id].student_count:
                        continue
                    
                    available_rooms.append(room_id)
                
                # Add domain values for each available room
                for room_id in available_rooms:
                    domain.append({
                        "day": day,
                        "period": period,
                        "room_id": room_id,
                        "teacher_id": teacher_id,
                        "subject_id": subject_id,
                        "class_id": class_id
                    })
            
            # Sort domain by some heuristic (e.g., room availability)
            domain.sort(key=lambda x: len(self.rooms[x["room_id"]].unavailability))
            self.domains[self._var_key(var)] = domain
    
    def _order_variables(self):
        """Order variables by most constrained first."""
        # Sort by domain size (smallest first)
        self.variables.sort(key=lambda v: len(self.domains[self._var_key(v)]))
    
    def _var_key(self, var):
        """Create unique key for variable."""
        return (var["class_id"], var["subject_id"], var["slot_index"])
    
    async def _solve(self) -> bool:
        """Run CSP solver with backtracking."""
        self.assignment = {}
        return await self._backtrack(0)
    
    async def _backtrack(self, index: int) -> bool:
        """Backtracking search."""
        if index >= len(self.variables):
            return True
        
        var = self.variables[index]
        var_key = self._var_key(var)
        
        # Get current domain after forward checking
        domain = self.domains[var_key]
        
        # Try each value in domain
        for value in domain:
            # Check if value is consistent with current assignment
            if self._is_consistent(value, self.assignment):
                # Assign value
                self.assignment[var_key] = value
                
                # Forward checking - prune domains of future variables
                pruned = await self._forward_check(index, value)
                
                if pruned is not None:  # If no domain became empty
                    # Update progress
                    progress = 40 + int((index / self.total_variables) * 50)
                    self._update_progress(progress, f"Solving... {index}/{self.total_variables}")
                    
                    # Recurse
                    result = await self._backtrack(index + 1)
                    if result:
                        return True
                
                # Restore pruned values
                if pruned:
                    self._restore_pruned(pruned)
                
                # Remove assignment
                del self.assignment[var_key]
        
        return False
    
    def _is_consistent(self, value: Dict, assignment: Dict) -> bool:
        """Check if a value is consistent with current assignment."""
        # Check teacher conflicts
        for assigned_var, assigned_value in assignment.items():
            if assigned_value["day"] == value["day"] and assigned_value["period"] == value["period"]:
                # Same time slot
                if assigned_value["teacher_id"] == value["teacher_id"]:
                    return False  # Teacher double-booked
                if assigned_value["room_id"] == value["room_id"]:
                    return False  # Room double-booked
                if assigned_var[0] == value["class_id"]:  # Same class
                    return False  # Class double-booked
        
        return True
    
    async def _forward_check(self, index: int, value: Dict) -> Optional[List[Tuple]]:
        """Forward checking - prune future domains."""
        pruned = []
        
        for i in range(index + 1, len(self.variables)):
            future_var = self.variables[i]
            future_key = self._var_key(future_var)
            future_domain = self.domains[future_key]
            
            # Remove inconsistent values
            to_remove = []
            for future_value in future_domain:
                if not self._is_consistent_with_future(value, future_value):
                    to_remove.append(future_value)
            
            if to_remove:
                # Store pruned values for later restoration
                pruned.append((future_key, to_remove))
                
                # Remove from domain
                new_domain = [v for v in future_domain if v not in to_remove]
                self.domains[future_key] = new_domain
                
                # If domain becomes empty, forward check fails
                if not new_domain:
                    return None
        
        return pruned
    
    def _is_consistent_with_future(self, current_value: Dict, future_value: Dict) -> bool:
        """Check if current value is consistent with a future value."""
        if future_value["day"] == current_value["day"] and future_value["period"] == current_value["period"]:
            # Same time slot - check for conflicts
            if future_value["teacher_id"] == current_value["teacher_id"]:
                return False
            if future_value["room_id"] == current_value["room_id"]:
                return False
            if future_value["class_id"] == current_value["class_id"]:
                return False
        return True
    
    def _restore_pruned(self, pruned: List[Tuple]):
        """Restore pruned domain values."""
        for future_key, removed_values in pruned:
            current_domain = self.domains[future_key]
            self.domains[future_key] = current_domain + removed_values
            # Sort to maintain heuristic
            self.domains[future_key].sort(key=lambda x: len(self.rooms[x["room_id"]].unavailability))
    
    def _update_progress(self, progress: int, message: str):
        """Update generation progress."""
        self.current_progress = progress
        if self.progress_callback:
            self.progress_callback(progress, message)
    
    async def _save_timetable(self) -> uuid.UUID:
        """Save generated timetable to database."""
        # Create timetable record
        timetable = Timetable(
            school_id=self.school_id,
            name=f"Timetable {self.term} {self.academic_year}",
            type=TimetableType.CLASS,
            term=self.term,
            academic_year=self.academic_year,
            status=TimetableStatus.DRAFT,
            version=1,
            created_by=uuid.UUID("00000000-0000-0000-0000-000000000000")  # System user
        )
        
        self.db.add(timetable)
        await self.db.flush()
        
        # Create slots
        for var_key, value in self.assignment.items():
            class_id, subject_id, _ = var_key
            
            # Get period times
            period_info = None
            for p in self.periods:
                if p.day_of_week == value["day"] and p.period_number == value["period"]:
                    period_info = p
                    break
            
            slot = TimetableSlot(
                timetable_id=timetable.id,
                day_of_week=value["day"],
                period_number=value["period"],
                class_id=class_id,
                subject_id=subject_id,
                teacher_id=value["teacher_id"],
                room_id=value["room_id"],
                start_time=period_info.start_time if period_info else None,
                end_time=period_info.end_time if period_info else None
            )
            
            self.db.add(slot)
        
        await self.db.commit()
        
        return timetable.id
    
    async def validate_timetable(self, timetable_id: uuid.UUID) -> List[Dict]:
        """Validate a timetable for conflicts."""
        # Load timetable with slots
        result = await self.db.execute(
            select(Timetable)
            .where(Timetable.id == timetable_id)
            .options(selectinload(Timetable.slots))
        )
        timetable = result.scalar_one_or_none()
        
        if not timetable:
            return [{"error": "Timetable not found"}]
        
        conflicts = []
        slots_by_time = defaultdict(list)
        
        # Group slots by time
        for slot in timetable.slots:
            key = (slot.day_of_week, slot.period_number)
            slots_by_time[key].append(slot)
        
        # Check for conflicts at each time slot
        for time_key, slots in slots_by_time.items():
            day, period = time_key
            
            # Check teacher conflicts
            teachers_at_time = defaultdict(list)
            rooms_at_time = defaultdict(list)
            classes_at_time = defaultdict(list)
            
            for slot in slots:
                teachers_at_time[slot.teacher_id].append(slot)
                rooms_at_time[slot.room_id].append(slot)
                classes_at_time[slot.class_id].append(slot)
            
            # Report conflicts
            for teacher_id, teacher_slots in teachers_at_time.items():
                if len(teacher_slots) > 1:
                    conflicts.append({
                        "type": "teacher_double_booked",
                        "teacher_id": str(teacher_id),
                        "day": day,
                        "period": period,
                        "slots": [str(s.id) for s in teacher_slots]
                    })
            
            for room_id, room_slots in rooms_at_time.items():
                if len(room_slots) > 1:
                    conflicts.append({
                        "type": "room_double_booked",
                        "room_id": str(room_id),
                        "day": day,
                        "period": period,
                        "slots": [str(s.id) for s in room_slots]
                    })
            
            for class_id, class_slots in classes_at_time.items():
                if len(class_slots) > 1:
                    conflicts.append({
                        "type": "class_double_booked",
                        "class_id": str(class_id),
                        "day": day,
                        "period": period,
                        "slots": [str(s.id) for s in class_slots]
                    })
        
        return conflicts