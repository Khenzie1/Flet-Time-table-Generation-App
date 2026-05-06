"""Fix database schema issues."""
import sqlite3
import os

def fix_schema():
    """Fix database schema issues."""
    db_path = 'data/local_timetable.db'
    
    # Backup existing database
    if os.path.exists(db_path):
        os.rename(db_path, db_path + '.backup')
        print(f"✅ Created backup: {db_path}.backup")
    
    # Create new database with correct schema
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create teachers table
    cursor.execute('''
        CREATE TABLE teachers (
            id TEXT PRIMARY KEY,
            school_id TEXT,
            teacher_code TEXT UNIQUE,
            full_name TEXT,
            email TEXT,
            max_daily_periods INTEGER,
            is_active INTEGER,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    ''')
    
    # Create teacher_subjects table (NO updated_at column)
    cursor.execute('''
        CREATE TABLE teacher_subjects (
            id TEXT PRIMARY KEY,
            teacher_id TEXT,
            subject_id TEXT,
            created_at TIMESTAMP
        )
    ''')
    
    # Create subjects table
    cursor.execute('''
        CREATE TABLE subjects (
            id TEXT PRIMARY KEY,
            school_id TEXT,
            code TEXT UNIQUE,
            name TEXT,
            category TEXT,
            periods_per_week INTEGER,
            duration_minutes INTEGER,
            requires_lab INTEGER,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    ''')
    
    # Create classes table
    cursor.execute('''
        CREATE TABLE classes (
            id TEXT PRIMARY KEY,
            school_id TEXT,
            class_name TEXT UNIQUE,
            level TEXT,
            student_count INTEGER,
            default_room_id TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    ''')
    
    # Create class_subjects table
    cursor.execute('''
        CREATE TABLE class_subjects (
            id TEXT PRIMARY KEY,
            class_id TEXT,
            subject_id TEXT,
            teacher_id TEXT,
            created_at TIMESTAMP
        )
    ''')
    
    # Create rooms table
    cursor.execute('''
        CREATE TABLE rooms (
            id TEXT PRIMARY KEY,
            school_id TEXT,
            room_code TEXT,
            room_name TEXT,
            capacity INTEGER,
            room_type TEXT,
            is_available INTEGER,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    ''')
    
    # Create teacher_unavailability table
    cursor.execute('''
        CREATE TABLE teacher_unavailability (
            id TEXT PRIMARY KEY,
            teacher_id TEXT,
            day_of_week TEXT,
            period_number INTEGER,
            reason TEXT,
            created_at TIMESTAMP
        )
    ''')
    
    # Create rooms_unavailability table
    cursor.execute('''
        CREATE TABLE rooms_unavailability (
            id TEXT PRIMARY KEY,
            room_id TEXT,
            day_of_week TEXT,
            period_number INTEGER,
            created_at TIMESTAMP
        )
    ''')
    
    # Create periods table
    cursor.execute('''
        CREATE TABLE periods (
            id TEXT PRIMARY KEY,
            school_id TEXT,
            period_number INTEGER,
            start_time TEXT,
            end_time TEXT,
            is_break INTEGER,
            day_of_week TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    ''')
    
    # Create timetables table
    cursor.execute('''
        CREATE TABLE timetables (
            id TEXT PRIMARY KEY,
            school_id TEXT,
            name TEXT,
            type TEXT,
            term TEXT,
            academic_year TEXT,
            status TEXT,
            version INTEGER,
            created_by TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    ''')
    
    # Create timetable_slots table
    cursor.execute('''
        CREATE TABLE timetable_slots (
            id TEXT PRIMARY KEY,
            timetable_id TEXT,
            day_of_week TEXT,
            period_number INTEGER,
            class_id TEXT,
            subject_id TEXT,
            teacher_id TEXT,
            room_id TEXT,
            start_time TEXT,
            end_time TEXT
        )
    ''')
    
    # Create sync_metadata table
    cursor.execute('''
        CREATE TABLE sync_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            last_sync_at TIMESTAMP,
            server_url TEXT
        )
    ''')
    
    # Create pending_changes table
    cursor.execute('''
        CREATE TABLE pending_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation TEXT,
            table_name TEXT,
            record_id TEXT,
            data_json TEXT,
            created_at TIMESTAMP,
            synced INTEGER DEFAULT 0
        )
    ''')
    
    # Create audit_logs table
    cursor.execute('''
        CREATE TABLE audit_logs (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            action TEXT,
            table_name TEXT,
            record_id TEXT,
            changes_json TEXT,
            timestamp TIMESTAMP
        )
    ''')
    
    # Create users table
    cursor.execute('''
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE,
            email TEXT,
            password_hash TEXT,
            role TEXT,
            school_id TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ New database created with correct schema!")

if __name__ == "__main__":
    fix_schema()