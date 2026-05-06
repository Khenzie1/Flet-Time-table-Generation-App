"""Seed data script for initial database population."""
import asyncio
import uuid
from datetime import datetime, time
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import ssl
import certifi

from app.config import settings
from app.models.user import User, UserRole
from app.models.school import School
from app.models.teacher import Teacher, TeacherSubject
from app.models.subject import Subject, SubjectCategory
from app.models.class_ import Class, ClassLevel, ClassSubject
from app.models.room import Room, RoomType
from app.models.period import Period
from app.utils.password_handler import get_password_hash


async def seed_database():
    """Seed the database with initial data."""
    print("=" * 60)
    print("SEEDING DATABASE")
    print("=" * 60)
    
    # Create SSL context
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    
    # Build database URL
    url = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    
    # Create engine
    engine = create_async_engine(
        url,
        echo=True,
        connect_args={
            "ssl": ssl_context,
            "server_settings": {"application_name": "timetable_seeder"}
        }
    )
    
    # Create session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # Check if already seeded
            result = await session.execute(select(User).where(User.username == "admin"))
            if result.scalar_one_or_none():
                print("Database already seeded. Skipping...")
                return
            
            print("Seeding database...")
            
            # Create school
            school = School(
                id=uuid.uuid4(),
                name="Migrant Model Secondary School",
                address="123 Education Avenue, Lagos, Nigeria",
                config_json={
                    "school_type": "Secondary",
                    "curriculum": "Nigerian",
                    "term_duration_weeks": 13,
                    "periods_per_day": 8
                }
            )
            session.add(school)
            await session.flush()
            
            # Create admin user
            admin = User(
                id=uuid.uuid4(),
                username="admin",
                email="admin@migrantmodel.edu.ng",
                password_hash=get_password_hash("Admin1234!"),
                role=UserRole.ADMIN
            )
            session.add(admin)
            
            # Create subjects (35 subjects)
            subjects_data = [
                # Core subjects
                ("MATH", "Mathematics", SubjectCategory.CORE, 5, 40, False),
                ("ENG", "English Language", SubjectCategory.CORE, 5, 40, False),
                ("PHY", "Physics", SubjectCategory.CORE, 4, 40, True),
                ("CHEM", "Chemistry", SubjectCategory.CORE, 4, 40, True),
                ("BIO", "Biology", SubjectCategory.CORE, 4, 40, True),
                ("GEO", "Geography", SubjectCategory.CORE, 3, 40, False),
                ("HIST", "History", SubjectCategory.CORE, 3, 40, False),
                ("GOVT", "Government", SubjectCategory.CORE, 3, 40, False),
                ("ECO", "Economics", SubjectCategory.CORE, 4, 40, False),
                ("CRS", "Christian Religious Studies", SubjectCategory.CORE, 2, 40, False),
                ("IRS", "Islamic Religious Studies", SubjectCategory.CORE, 2, 40, False),
                
                # Elective subjects
                ("LIT", "Literature in English", SubjectCategory.ELECTIVE, 3, 40, False),
                ("FREN", "French", SubjectCategory.ELECTIVE, 3, 40, False),
                ("YOR", "Yoruba", SubjectCategory.ELECTIVE, 3, 40, False),
                ("HAUS", "Hausa", SubjectCategory.ELECTIVE, 3, 40, False),
                ("IGBO", "Igbo", SubjectCategory.ELECTIVE, 3, 40, False),
                ("ARAB", "Arabic", SubjectCategory.ELECTIVE, 3, 40, False),
                ("FURD", "Furata", SubjectCategory.ELECTIVE, 3, 40, False),
                ("CIVIC", "Civic Education", SubjectCategory.ELECTIVE, 2, 40, False),
                ("SEC", "Security Education", SubjectCategory.ELECTIVE, 2, 40, False),
                
                # Practical subjects
                ("AGRIC", "Agricultural Science", SubjectCategory.PRACTICAL, 3, 40, True),
                ("COMP", "Computer Studies", SubjectCategory.PRACTICAL, 3, 40, True),
                ("TECH", "Basic Technology", SubjectCategory.PRACTICAL, 3, 40, True),
                ("HOMEEC", "Home Economics", SubjectCategory.PRACTICAL, 3, 40, True),
                ("FINEART", "Fine Arts", SubjectCategory.PRACTICAL, 3, 40, True),
                ("MUSIC", "Music", SubjectCategory.PRACTICAL, 2, 40, True),
                ("PE", "Physical Education", SubjectCategory.PRACTICAL, 2, 40, False),
                ("BUS", "Business Studies", SubjectCategory.PRACTICAL, 3, 40, False),
                ("BOOK", "Book Keeping", SubjectCategory.PRACTICAL, 3, 40, False),
                ("SHOP", "Shop Work", SubjectCategory.PRACTICAL, 3, 40, True),
                ("METAL", "Metal Work", SubjectCategory.PRACTICAL, 3, 40, True),
                ("WOOD", "Wood Work", SubjectCategory.PRACTICAL, 3, 40, True),
                ("ELECT", "Electronics", SubjectCategory.PRACTICAL, 3, 40, True),
                ("MECH", "Mechanics", SubjectCategory.PRACTICAL, 3, 40, True),
                ("AUTO", "Auto Mechanics", SubjectCategory.PRACTICAL, 3, 40, True),
            ]
            
            subjects = []
            for code, name, category, periods, duration, requires_lab in subjects_data:
                subject = Subject(
                    id=uuid.uuid4(),
                    school_id=school.id,
                    code=code,
                    name=name,
                    category=category,
                    periods_per_week=periods,
                    duration_minutes=duration,
                    requires_lab=requires_lab
                )
                session.add(subject)
                subjects.append(subject)
            
            await session.flush()
            
            # Create rooms (20 rooms)
            rooms_data = [
                # Regular classrooms (16)
                *[(f"CR-{i:03d}", f"Classroom {i}", 40, RoomType.REGULAR) for i in range(1, 11)],
                *[(f"CR-{i:03d}", f"Classroom {i}", 30, RoomType.REGULAR) for i in range(11, 17)],
                
                # Labs (2)
                ("LAB-PHY", "Physics Laboratory", 30, RoomType.LAB),
                ("LAB-CHEM", "Chemistry Laboratory", 30, RoomType.LAB),
                
                # Workshop (1)
                ("WORKSHOP", "Technical Workshop", 25, RoomType.WORKSHOP),
                
                # Hall (1)
                ("HALL", "School Hall", 500, RoomType.HALL),
            ]
            
            rooms = []
            for code, name, capacity, room_type in rooms_data:
                room = Room(
                    id=uuid.uuid4(),
                    school_id=school.id,
                    room_code=code,
                    room_name=name,
                    capacity=capacity,
                    room_type=room_type,
                    is_available=True
                )
                session.add(room)
                rooms.append(room)
            
            await session.flush()
            
            # Create teachers (45 teachers)
            teachers_data = [
                # Sciences department
                ("SCI001", "Dr. Adebayo Ogunlesi", "adebayo.ogunlesi@school.edu.ng", 6),
                ("SCI002", "Mrs. Funmilayo Johnson", "funmilayo.johnson@school.edu.ng", 6),
                ("SCI003", "Mr. Chinedu Okonkwo", "chinedu.okonkwo@school.edu.ng", 6),
                ("SCI004", "Miss Ngozi Eze", "ngozi.eze@school.edu.ng", 5),
                ("SCI005", "Dr. Emeka Nwosu", "emeka.nwosu@school.edu.ng", 6),
                ("SCI006", "Mrs. Grace Akpan", "grace.akpan@school.edu.ng", 5),
                
                # Arts department
                ("ART001", "Prof. Oluwaseun Adeleke", "oluwaseun.adeleke@school.edu.ng", 5),
                ("ART002", "Mr. Babatunde Ojo", "babatunde.ojo@school.edu.ng", 6),
                ("ART003", "Mrs. Adaeze Obi", "adaeze.obi@school.edu.ng", 5),
                ("ART004", "Miss Chinwe Umeh", "chinwe.umeh@school.edu.ng", 5),
                ("ART005", "Dr. Kunle Salami", "kunle.salami@school.edu.ng", 6),
                ("ART006", "Mr. Tunde Bakare", "tunde.bakare@school.edu.ng", 5),
                
                # Commercial department
                ("COM001", "Mrs. Folashade Williams", "folashade.williams@school.edu.ng", 6),
                ("COM002", "Mr. Ifeanyi Okoro", "ifeanyi.okoro@school.edu.ng", 6),
                ("COM003", "Miss Bose Akinwande", "bose.akinwande@school.edu.ng", 5),
                ("COM004", "Dr. Nnamdi Okafor", "nnamdi.okafor@school.edu.ng", 5),
                ("COM005", "Mr. Segun Adeyemi", "segun.adeyemi@school.edu.ng", 6),
                
                # Technical department
                ("TEC001", "Engr. Femi Adegoke", "femi.adegoke@school.edu.ng", 5),
                ("TEC002", "Mr. Kayode Fasasi", "kayode.fasasi@school.edu.ng", 6),
                ("TEC003", "Mrs. Yemisi Ogunleye", "yemisi.ogunleye@school.edu.ng", 5),
                ("TEC004", "Mr. Gbenga Adebayo", "gbenga.adebayo@school.edu.ng", 6),
                ("TEC005", "Miss Dupe Akinola", "dupe.akinola@school.edu.ng", 5),
                
                # Languages department
                ("LAN001", "Prof. Akintunde Ojo", "akintunde.ojo@school.edu.ng", 5),
                ("LAN002", "Mrs. Modupe Fashola", "modupe.fashola@school.edu.ng", 6),
                ("LAN003", "Mr. Olumide Adebayo", "olumide.adebayo@school.edu.ng", 5),
                ("LAN004", "Miss Kemi Adesina", "kemi.adesina@school.edu.ng", 5),
                ("LAN005", "Dr. Rasheed Bello", "rasheed.bello@school.edu.ng", 5),
                
                # Additional teachers
                ("GEN001", "Mr. Patrick Okeke", "patrick.okeke@school.edu.ng", 6),
                ("GEN002", "Mrs. Nkechi Nwankwo", "nkechi.nwankwo@school.edu.ng", 5),
                ("GEN003", "Mr. Suleiman Danladi", "suleiman.danladi@school.edu.ng", 6),
                ("GEN004", "Miss Hauwa Mohammed", "hauwa.mohammed@school.edu.ng", 5),
                ("GEN005", "Dr. Godwin Etuk", "godwin.etuk@school.edu.ng", 5),
                ("GEN006", "Mrs. Bose Olaniyan", "bose.olaniyan@school.edu.ng", 6),
                ("GEN007", "Mr. Chuka Okafor", "chuka.okafor@school.edu.ng", 5),
                ("GEN008", "Miss Ifeoluwa Adeleke", "ifeoluwa.adeleke@school.edu.ng", 5),
                ("GEN009", "Mr. Jibrin Garba", "jibrin.garba@school.edu.ng", 6),
                ("GEN010", "Mrs. Amara Igwe", "amara.igwe@school.edu.ng", 5),
                ("GEN011", "Mr. Yemi Adetola", "yemi.adetola@school.edu.ng", 5),
                ("GEN012", "Miss Zainab Abubakar", "zainab.abubakar@school.edu.ng", 5),
                ("GEN013", "Dr. Olufemi Aina", "olufemi.aina@school.edu.ng", 6),
                ("GEN014", "Mrs. Bisi Ogundipe", "bisi.ogundipe@school.edu.ng", 5),
                ("GEN015", "Mr. Emeka Okafor", "emeka.okafor@school.edu.ng", 5),
            ]
            
            teachers = []
            for code, name, email, max_periods in teachers_data:
                teacher = Teacher(
                    id=uuid.uuid4(),
                    school_id=school.id,
                    teacher_code=code,
                    full_name=name,
                    email=email,
                    max_daily_periods=max_periods,
                    is_active=True
                )
                session.add(teacher)
                teachers.append(teacher)
            
            await session.flush()
            
            # Create classes (18 classes)
            class_levels = [
                ("JSS1A", ClassLevel.JSS1, 45),
                ("JSS1B", ClassLevel.JSS1, 42),
                ("JSS1C", ClassLevel.JSS1, 38),
                ("JSS2A", ClassLevel.JSS2, 44),
                ("JSS2B", ClassLevel.JSS2, 41),
                ("JSS2C", ClassLevel.JSS2, 39),
                ("JSS3A", ClassLevel.JSS3, 43),
                ("JSS3B", ClassLevel.JSS3, 40),
                ("JSS3C", ClassLevel.JSS3, 37),
                ("SS1A", ClassLevel.SS1, 38),
                ("SS1B", ClassLevel.SS1, 35),
                ("SS1C", ClassLevel.SS1, 32),
                ("SS2A", ClassLevel.SS2, 36),
                ("SS2B", ClassLevel.SS2, 34),
                ("SS2C", ClassLevel.SS2, 30),
                ("SS3A", ClassLevel.SS3, 28),
                ("SS3B", ClassLevel.SS3, 26),
                ("SS3C", ClassLevel.SS3, 24),
            ]
            
            classes = []
            for name, level, count in class_levels:
                class_obj = Class(
                    id=uuid.uuid4(),
                    school_id=school.id,
                    class_name=name,
                    level=level,
                    student_count=count,
                    default_room_id=rooms[0].id
                )
                session.add(class_obj)
                classes.append(class_obj)
            
            await session.flush()
            
            # Create periods
            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            period_times = [
                (1, time(8, 0), time(8, 40), False),
                (2, time(8, 40), time(9, 20), False),
                (3, time(9, 20), time(10, 0), False),
                (4, time(10, 0), time(10, 20), True),
                (5, time(10, 20), time(11, 0), False),
                (6, time(11, 0), time(11, 40), False),
                (7, time(11, 40), time(12, 20), True),
                (8, time(12, 20), time(13, 0), False),
                (9, time(13, 0), time(13, 40), False),
                (10, time(13, 40), time(14, 20), False),
            ]
            
            for day in days:
                for period_num, start, end, is_break in period_times:
                    period = Period(
                        id=uuid.uuid4(),
                        school_id=school.id,
                        period_number=period_num,
                        start_time=start,
                        end_time=end,
                        is_break=is_break,
                        day_of_week=day
                    )
                    session.add(period)
            
            await session.commit()
            print("✅ Database seeded successfully!")
            
        except Exception as e:
            print(f"❌ Error seeding database: {e}")
            import traceback
            traceback.print_exc()
            await session.rollback()
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_database())