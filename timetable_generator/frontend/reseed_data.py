"""Reseed database with sample data."""
import sqlite3
import uuid
from datetime import datetime

def reseed():
    """Add sample data to database."""
    conn = sqlite3.connect('data/local_timetable.db')
    cursor = conn.cursor()
    
    print("Adding sample data...")
    
    # Sample teachers
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
    
    # Sample subjects
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
    
    # Link teachers to subjects
    for i, teacher_id in enumerate(teacher_ids[:3]):
        for j, subject_id in enumerate(subject_ids[:2]):
            cursor.execute("""
                INSERT INTO teacher_subjects (id, teacher_id, subject_id, created_at)
                VALUES (?, ?, ?, ?)
            """, (str(uuid.uuid4()), teacher_id, subject_id, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    print("✅ Sample data added successfully!")

if __name__ == "__main__":
    reseed()