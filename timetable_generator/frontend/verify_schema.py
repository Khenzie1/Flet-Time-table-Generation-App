"""Verify and fix database schema."""
import sqlite3

def verify_schema():
    """Check teacher_subjects table schema."""
    conn = sqlite3.connect('data/local_timetable.db')
    cursor = conn.cursor()
    
    # Check current schema
    cursor.execute("PRAGMA table_info(teacher_subjects)")
    columns = cursor.fetchall()
    print("Current teacher_subjects schema:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    # Check if updated_at column exists
    has_updated_at = any(col[1] == 'updated_at' for col in columns)
    
    if has_updated_at:
        print("\n⚠️  Found updated_at column - removing it...")
        
        # Create new table without updated_at
        cursor.execute('''
            CREATE TABLE teacher_subjects_new (
                id TEXT PRIMARY KEY,
                teacher_id TEXT,
                subject_id TEXT,
                created_at TIMESTAMP
            )
        ''')
        
        # Copy data
        cursor.execute('''
            INSERT INTO teacher_subjects_new (id, teacher_id, subject_id, created_at)
            SELECT id, teacher_id, subject_id, created_at FROM teacher_subjects
        ''')
        
        # Drop old table
        cursor.execute('DROP TABLE teacher_subjects')
        
        # Rename new table
        cursor.execute('ALTER TABLE teacher_subjects_new RENAME TO teacher_subjects')
        
        print("✅ Removed updated_at column from teacher_subjects")
    else:
        print("\n✅ teacher_subjects schema is correct (no updated_at column)")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    verify_schema()