"""Test status update functionality."""
import sqlite3

def test_status_update():
    """Test updating teacher status."""
    conn = sqlite3.connect('data/local_timetable.db')
    cursor = conn.cursor()
    
    # Get first teacher
    cursor.execute("SELECT id, teacher_code, is_active FROM teachers LIMIT 1")
    teacher = cursor.fetchone()
    
    if teacher:
        teacher_id, code, current_status = teacher
        print(f"Teacher {code}: current status = {current_status}")
        
        # Toggle status
        new_status = 0 if current_status == 1 else 1
        print(f"Toggling to: {new_status}")
        
        # Update
        cursor.execute(
            "UPDATE teachers SET is_active = ? WHERE id = ?",
            (new_status, teacher_id)
        )
        conn.commit()
        
        # Verify
        cursor.execute("SELECT is_active FROM teachers WHERE id = ?", (teacher_id,))
        updated_status = cursor.fetchone()[0]
        print(f"Updated status = {updated_status}")
        
        if updated_status == new_status:
            print("✅ Status update successful!")
        else:
            print("❌ Status update failed!")
    
    conn.close()

if __name__ == "__main__":
    test_status_update()