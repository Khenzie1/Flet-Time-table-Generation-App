"""Local SQLite database manager for offline storage."""
import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import threading
from contextlib import contextmanager

from app.config import DB_PATH


class LocalDB:
    """SQLite database manager for offline storage."""
    
    def __init__(self):
        self.db_path = DB_PATH
        self._local = threading.local()
    
    @contextmanager
    def get_connection(self):
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection'):
            # Disable timestamp converter to avoid Python 3.12 issues
            sqlite3.register_converter("timestamp", lambda b: b.decode('utf-8') if b else None)
            self._local.connection = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES,
                check_same_thread=False
            )
            self._local.connection.row_factory = sqlite3.Row
        
        try:
            yield self._local.connection
        except Exception as e:
            self._local.connection.rollback()
            raise e
        finally:
            self._local.connection.commit()
    
    def init_database(self):
        """Initialize database schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
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
            
            # Schools table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS schools (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    address TEXT,
                    logo_url TEXT,
                    config_json TEXT,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            ''')
            
            # Teachers table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS teachers (
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
            
            # Teacher subjects (many-to-many) - NO updated_at column
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS teacher_subjects (
                    id TEXT PRIMARY KEY,
                    teacher_id TEXT,
                    subject_id TEXT,
                    created_at TIMESTAMP
                )
            ''')
            
            # Teacher unavailability
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS teacher_unavailability (
                    id TEXT PRIMARY KEY,
                    teacher_id TEXT,
                    day_of_week TEXT,
                    period_number INTEGER,
                    reason TEXT,
                    created_at TIMESTAMP
                )
            ''')
            
            # Subjects table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS subjects (
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
            
            # Classes table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS classes (
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
            
            # Class subjects (with teacher assignment) - NO updated_at
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS class_subjects (
                    id TEXT PRIMARY KEY,
                    class_id TEXT,
                    subject_id TEXT,
                    teacher_id TEXT,
                    created_at TIMESTAMP
                )
            ''')
            
            # Rooms table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rooms (
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
            
            # Room unavailability - NO updated_at
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rooms_unavailability (
                    id TEXT PRIMARY KEY,
                    room_id TEXT,
                    day_of_week TEXT,
                    period_number INTEGER,
                    created_at TIMESTAMP
                )
            ''')
            
            # Periods table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS periods (
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
            
            # Timetables table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS timetables (
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
            
            # Timetable slots - NO updated_at
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS timetable_slots (
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
            
            # Sync metadata
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sync_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    last_sync_at TIMESTAMP,
                    server_url TEXT
                )
            ''')
            
            # Pending changes for offline sync
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pending_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation TEXT,
                    table_name TEXT,
                    record_id TEXT,
                    data_json TEXT,
                    created_at TIMESTAMP,
                    synced INTEGER DEFAULT 0
                )
            ''')
            
            # Audit logs
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    action TEXT,
                    table_name TEXT,
                    record_id TEXT,
                    changes_json TEXT,
                    timestamp TIMESTAMP
                )
            ''')
            
            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_pending_changes_synced ON pending_changes(synced)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_timetable_slots_timetable ON timetable_slots(timetable_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_teacher_unavailability_teacher ON teacher_unavailability(teacher_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_class_subjects_class ON class_subjects(class_id)')
            
            # Insert default sync metadata if not exists
            cursor.execute('SELECT COUNT(*) FROM sync_metadata')
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    'INSERT INTO sync_metadata (last_sync_at, server_url) VALUES (?, ?)',
                    (datetime.now().isoformat(), '')
                )
    
    def execute(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute a query and return results."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(query, params)
                
                if query.strip().upper().startswith('SELECT'):
                    rows = cursor.fetchall()
                    # Convert rows to list of dicts safely
                    result = []
                    for row in rows:
                        row_dict = {}
                        for key in row.keys():
                            value = row[key]
                            # Handle None values
                            if value is None:
                                row_dict[key] = None
                            else:
                                row_dict[key] = value
                        result.append(row_dict)
                    return result
                else:
                    conn.commit()
                    return []
            except Exception as e:
                print(f"Database error in execute: {e}")
                conn.rollback()
                return []
    
    def insert(self, table: str, data: Dict) -> str:
        """Insert a record and track for sync."""
        record_id = str(uuid.uuid4())
        data['id'] = record_id
        
        # Tables that should have both created_at and updated_at
        tables_with_timestamps = ['teachers', 'subjects', 'classes', 'rooms', 'timetables', 'users', 'schools', 'periods']
        
        # Junction tables (only created_at, no updated_at)
        junction_tables = ['teacher_subjects', 'class_subjects', 'teacher_unavailability', 
                          'rooms_unavailability', 'timetable_slots', 'sync_queue', 'audit_logs']
        
        now = datetime.now().isoformat()
        
        if table in tables_with_timestamps:
            data['created_at'] = now
            data['updated_at'] = now
        elif table in junction_tables:
            data['created_at'] = now
            # Remove updated_at if it was accidentally added
            if 'updated_at' in data:
                del data['updated_at']
        else:
            # For any other table, just add created_at
            data['created_at'] = now
            if 'updated_at' in data:
                del data['updated_at']
        
        # Filter out None values
        clean_data = {}
        for k, v in data.items():
            if v is not None:
                clean_data[k] = v
        
        if not clean_data:
            raise ValueError(f"No valid data to insert into {table}")
        
        columns = ', '.join(clean_data.keys())
        placeholders = ', '.join(['?' for _ in clean_data])
        values = list(clean_data.values())
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    f'INSERT INTO {table} ({columns}) VALUES ({placeholders})',
                    values
                )
                
                # Track for sync
                cursor.execute(
                    '''INSERT INTO pending_changes 
                       (operation, table_name, record_id, data_json, created_at, synced) 
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    ('INSERT', table, record_id, json.dumps(clean_data), now, 0)
                )
                conn.commit()
                print(f"✅ Inserted into {table}: {record_id}")
            except Exception as e:
                print(f"❌ Error inserting into {table}: {e}")
                conn.rollback()
                raise e
        
        return record_id
    
    def update(self, table: str, record_id: str, data: Dict) -> bool:
        """Update a record and track for sync."""
        # Tables that should have updated_at
        tables_with_timestamps = ['teachers', 'subjects', 'classes', 'rooms', 'timetables', 'users', 'schools', 'periods']
        
        now = datetime.now().isoformat()
        
        if table in tables_with_timestamps:
            data['updated_at'] = now
        else:
            # Remove updated_at for junction tables
            if 'updated_at' in data:
                del data['updated_at']
        
        # Filter out None values
        clean_data = {}
        for k, v in data.items():
            if v is not None:
                clean_data[k] = v
        
        if not clean_data:
            return False
        
        set_clause = ', '.join([f"{k} = ?" for k in clean_data.keys()])
        values = list(clean_data.values()) + [record_id]
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    f'UPDATE {table} SET {set_clause} WHERE id = ?',
                    values
                )
                
                if cursor.rowcount > 0:
                    # Track for sync
                    cursor.execute(
                        '''INSERT INTO pending_changes 
                           (operation, table_name, record_id, data_json, created_at, synced) 
                           VALUES (?, ?, ?, ?, ?, ?)''',
                        ('UPDATE', table, record_id, json.dumps(clean_data), now, 0)
                    )
                    conn.commit()
                    print(f"✅ Updated {table}: {record_id}")
                    return True
            except Exception as e:
                print(f"❌ Error updating {table}: {e}")
                conn.rollback()
        
        return False
    
    def delete(self, table: str, record_id: str) -> bool:
        """Delete a record and track for sync."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get data before deletion for sync
            cursor.execute(f'SELECT * FROM {table} WHERE id = ?', (record_id,))
            row = cursor.fetchone()
            
            if row:
                # Convert row to dict
                data = {}
                for key in row.keys():
                    data[key] = row[key]
                
                cursor.execute(f'DELETE FROM {table} WHERE id = ?', (record_id,))
                
                if cursor.rowcount > 0:
                    # Track for sync
                    cursor.execute(
                        '''INSERT INTO pending_changes 
                           (operation, table_name, record_id, data_json, created_at, synced) 
                           VALUES (?, ?, ?, ?, ?, ?)''',
                        ('DELETE', table, record_id, json.dumps(data), datetime.now().isoformat(), 0)
                    )
                    conn.commit()
                    print(f"✅ Deleted from {table}: {record_id}")
                    return True
        
        return False
    
    def get_pending_changes(self) -> List[Dict]:
        """Get all pending changes that need sync."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM pending_changes WHERE synced = 0 ORDER BY created_at'
            )
            rows = cursor.fetchall()
            result = []
            for row in rows:
                row_dict = {}
                for key in row.keys():
                    row_dict[key] = row[key]
                result.append(row_dict)
            return result
    
    def mark_changes_synced(self, change_ids: List[int]):
        """Mark changes as synced."""
        if not change_ids:
            return
        
        placeholders = ', '.join(['?' for _ in change_ids])
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f'UPDATE pending_changes SET synced = 1 WHERE id IN ({placeholders})',
                change_ids
            )
            conn.commit()
            print(f"✅ Marked {len(change_ids)} changes as synced")
    
    def get_last_sync_time(self) -> Optional[str]:
        """Get last sync timestamp."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT last_sync_at FROM sync_metadata LIMIT 1')
            row = cursor.fetchone()
            return row[0] if row else None
    
    def update_sync_time(self, timestamp: str = None):
        """Update last sync timestamp."""
        if not timestamp:
            timestamp = datetime.now().isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE sync_metadata SET last_sync_at = ?',
                (timestamp,)
            )
            conn.commit()
            print(f"✅ Updated sync time to {timestamp}")