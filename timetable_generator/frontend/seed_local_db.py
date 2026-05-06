"""Seed the local SQLite database with sample data."""
import sqlite3
import uuid
from datetime import datetime

# Connect to database
conn = sqlite3.connect('data/local_timetable.db')
cursor = conn.cursor()

print("Seeding local database...")

# Clear existing data (optional - comment out if you want to keep existing data)
tables = ['teacher_subjects', 'teacher_unavailability', 'class_subjects', 
          'timetable_slots', 'teachers', 'subjects', 'classes', 'rooms']
for table in tables:
    cursor.execute(f"DELETE FROM {table}")
    print(f"Cleared {table}")

# Insert sample teachers
teachers = [
    ('TCH001', 'Dr. John Smith', 'john.smith@school.edu', 6, 1),
    ('TCH002', 'Mrs. Sarah Johnson', 'sarah.j@school.edu', 6, 1),
    ('TCH003', 'Mr. Michael Brown', 'michael.b@school.edu', 5, 1),
    ('TCH004', 'Ms. Emily Davis', 'emily.d@school.edu', 5, 1),
    ('TCH005', 'Dr. Robert Wilson', 'robert.w@school.edu', 6, 1),
]

teacher_ids = []
for code, name, email, max_periods, active in teachers:
    teacher_id = str(uuid.uuid4())
    teacher_ids.append(teacher_id)
    cursor.execute("""
        INSERT INTO teachers (id, teacher_code, full_name, email, max_daily_periods, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (teacher_id, code, name, email, max_periods, active, datetime.now().isoformat(), datetime.now().isoformat()))
print(f"Added {len(teachers)} teachers")

# Insert sample subjects
subjects = [
    ('MATH', 'Mathematics', 'Core', 5, 40, 0),
    ('ENG', 'English', 'Core', 5, 40, 0),
    ('PHY', 'Physics', 'Core', 4, 40, 1),
    ('CHEM', 'Chemistry', 'Core', 4, 40, 1),
    ('BIO', 'Biology', 'Core', 4, 40, 1),
    ('HIST', 'History', 'Core', 3, 40, 0),
    ('COMP', 'Computer Studies', 'Practical', 3, 40, 1),
]

subject_ids = []
for code, name, category, periods, duration, lab in subjects:
    subject_id = str(uuid.uuid4())
    subject_ids.append(subject_id)
    cursor.execute("""
        INSERT INTO subjects (id, code, name, category, periods_per_week, duration_minutes, requires_lab, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (subject_id, code, name, category, periods, duration, lab, datetime.now().isoformat(), datetime.now().isoformat()))
print(f"Added {len(subjects)} subjects")

# Insert sample rooms
rooms = [
    ('CR101', 'Classroom 101', 40, 'Regular', 1),
    ('CR102', 'Classroom 102', 35, 'Regular', 1),
    ('LAB1', 'Physics Lab', 30, 'Lab', 1),
    ('LAB2', 'Chemistry Lab', 30, 'Lab', 1),
    ('WS1', 'Workshop', 25, 'Workshop', 1),
]

room_ids = []
for code, name, capacity, room_type, available in rooms:
    room_id = str(uuid.uuid4())
    room_ids.append(room_id)
    cursor.execute("""
        INSERT INTO rooms (id, room_code, room_name, capacity, room_type, is_available, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (room_id, code, name, capacity, room_type, available, datetime.now().isoformat(), datetime.now().isoformat()))
print(f"Added {len(rooms)} rooms")

# Insert sample classes
classes = [
    ('JSS1A', 'JSS1', 45),
    ('JSS1B', 'JSS1', 42),
    ('JSS2A', 'JSS2', 40),
    ('SS1A', 'SS1', 38),
    ('SS2A', 'SS2', 35),
]

class_ids = []
for name, level, students in classes:
    class_id = str(uuid.uuid4())
    class_ids.append(class_id)
    cursor.execute("""
        INSERT INTO classes (id, class_name, level, student_count, default_room_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (class_id, name, level, students, room_ids[0], datetime.now().isoformat(), datetime.now().isoformat()))
print(f"Added {len(classes)} classes")

# Link teachers to subjects
for i, teacher_id in enumerate(teacher_ids[:3]):
    for j, subject_id in enumerate(subject_ids[:2]):
        cursor.execute("""
            INSERT INTO teacher_subjects (id, teacher_id, subject_id, created_at)
            VALUES (?, ?, ?, ?)
        """, (str(uuid.uuid4()), teacher_id, subject_id, datetime.now().isoformat()))

# Link classes to subjects with teachers
for i, class_id in enumerate(class_ids):
    for j, subject_id in enumerate(subject_ids[:4]):
        teacher_id = teacher_ids[j % len(teacher_ids)]
        cursor.execute("""
            INSERT INTO class_subjects (id, class_id, subject_id, teacher_id, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), class_id, subject_id, teacher_id, datetime.now().isoformat()))

# Commit changes
conn.commit()

# Verify the data
print("\n=== VERIFICATION ===")
tables = ['teachers', 'subjects', 'rooms', 'classes', 'teacher_subjects', 'class_subjects']
for table in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"{table}: {count} rows")

conn.close()
print("\n✅ Local database seeded successfully!")