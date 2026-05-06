"""Initial migration

Revision ID: 697ccfdf7f0e
Revises: 
Create Date: 2026-02-24 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ENUM

# revision identifiers, used by Alembic.
revision = '697ccfdf7f0e'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ENUM types
    op.execute("CREATE TYPE userrole AS ENUM ('ADMIN', 'COORDINATOR', 'VIEWER')")
    op.execute("CREATE TYPE subjectcategory AS ENUM ('Core', 'Elective', 'Practical')")
    op.execute("CREATE TYPE classlevel AS ENUM ('JSS1', 'JSS2', 'JSS3', 'SS1', 'SS2', 'SS3')")
    op.execute("CREATE TYPE roomtype AS ENUM ('Regular', 'Lab', 'Workshop', 'Hall')")
    op.execute("CREATE TYPE timetablestatus AS ENUM ('Draft', 'Approved', 'Published')")
    op.execute("CREATE TYPE timetabletype AS ENUM ('Class', 'Exam')")
    
    # 1. Create users table FIRST
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('username', sa.String(50), unique=True, nullable=False),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('role', ENUM('ADMIN', 'COORDINATOR', 'VIEWER', name='userrole'), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    
    # 2. Create schools table
    op.create_table(
        'schools',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('address', sa.String(500)),
        sa.Column('logo_url', sa.String(500)),
        sa.Column('config_json', sa.JSON, default={}),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    
    # 3. Create teachers table (references schools)
    op.create_table(
        'teachers',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('school_id', UUID(as_uuid=True), sa.ForeignKey('schools.id'), nullable=False),
        sa.Column('teacher_code', sa.String(20), unique=True, nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255)),
        sa.Column('max_daily_periods', sa.Integer, default=6),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    
    # 4. Create subjects table (references schools)
    op.create_table(
        'subjects',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('school_id', UUID(as_uuid=True), sa.ForeignKey('schools.id'), nullable=False),
        sa.Column('code', sa.String(20), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('category', ENUM('Core', 'Elective', 'Practical', name='subjectcategory'), nullable=False),
        sa.Column('periods_per_week', sa.Integer, nullable=False),
        sa.Column('duration_minutes', sa.Integer, default=40),
        sa.Column('requires_lab', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    
    # 5. Create rooms table (references schools)
    op.create_table(
        'rooms',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('school_id', UUID(as_uuid=True), sa.ForeignKey('schools.id'), nullable=False),
        sa.Column('room_code', sa.String(20), nullable=False),
        sa.Column('room_name', sa.String(255), nullable=False),
        sa.Column('capacity', sa.Integer, nullable=False),
        sa.Column('room_type', ENUM('Regular', 'Lab', 'Workshop', 'Hall', name='roomtype'), nullable=False),
        sa.Column('is_available', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    
    # 6. Create classes table (references schools and rooms)
    op.create_table(
        'classes',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('school_id', UUID(as_uuid=True), sa.ForeignKey('schools.id'), nullable=False),
        sa.Column('class_name', sa.String(50), unique=True, nullable=False),
        sa.Column('level', ENUM('JSS1', 'JSS2', 'JSS3', 'SS1', 'SS2', 'SS3', name='classlevel'), nullable=False),
        sa.Column('student_count', sa.Integer, default=0),
        sa.Column('default_room_id', UUID(as_uuid=True), sa.ForeignKey('rooms.id'), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    
    # 7. Create periods table (references schools)
    op.create_table(
        'periods',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('school_id', UUID(as_uuid=True), sa.ForeignKey('schools.id'), nullable=False),
        sa.Column('period_number', sa.Integer, nullable=False),
        sa.Column('start_time', sa.Time, nullable=False),
        sa.Column('end_time', sa.Time, nullable=False),
        sa.Column('is_break', sa.Boolean, default=False),
        sa.Column('day_of_week', sa.String(10), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    
    # 8. Create timetables table (references schools and users)
    op.create_table(
        'timetables',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('school_id', UUID(as_uuid=True), sa.ForeignKey('schools.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('type', ENUM('Class', 'Exam', name='timetabletype'), nullable=False),
        sa.Column('term', sa.String(50)),
        sa.Column('academic_year', sa.String(20)),
        sa.Column('status', ENUM('Draft', 'Approved', 'Published', name='timetablestatus'), default='Draft'),
        sa.Column('version', sa.Integer, default=1),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    
    # 9. Create teacher_subjects table (junction)
    op.create_table(
        'teacher_subjects',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('teacher_id', UUID(as_uuid=True), sa.ForeignKey('teachers.id'), nullable=False),
        sa.Column('subject_id', UUID(as_uuid=True), sa.ForeignKey('subjects.id'), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
    )
    
    # 10. Create teacher_unavailability table
    op.create_table(
        'teacher_unavailability',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('teacher_id', UUID(as_uuid=True), sa.ForeignKey('teachers.id'), nullable=False),
        sa.Column('day_of_week', sa.String(10), nullable=False),
        sa.Column('period_number', sa.Integer, nullable=False),
        sa.Column('reason', sa.String(255)),
        sa.Column('created_at', sa.DateTime, nullable=False),
    )
    
    # 11. Create rooms_unavailability table
    op.create_table(
        'rooms_unavailability',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('room_id', UUID(as_uuid=True), sa.ForeignKey('rooms.id'), nullable=False),
        sa.Column('day_of_week', sa.String(10), nullable=False),
        sa.Column('period_number', sa.Integer, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
    )
    
    # 12. Create class_subjects table (junction)
    op.create_table(
        'class_subjects',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('class_id', UUID(as_uuid=True), sa.ForeignKey('classes.id'), nullable=False),
        sa.Column('subject_id', UUID(as_uuid=True), sa.ForeignKey('subjects.id'), nullable=False),
        sa.Column('teacher_id', UUID(as_uuid=True), sa.ForeignKey('teachers.id'), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
    )
    
    # 13. Create timetable_slots table
    op.create_table(
        'timetable_slots',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('timetable_id', UUID(as_uuid=True), sa.ForeignKey('timetables.id'), nullable=False),
        sa.Column('day_of_week', sa.String(10), nullable=False),
        sa.Column('period_number', sa.Integer, nullable=False),
        sa.Column('class_id', UUID(as_uuid=True), sa.ForeignKey('classes.id'), nullable=False),
        sa.Column('subject_id', UUID(as_uuid=True), sa.ForeignKey('subjects.id'), nullable=False),
        sa.Column('teacher_id', UUID(as_uuid=True), sa.ForeignKey('teachers.id'), nullable=False),
        sa.Column('room_id', UUID(as_uuid=True), sa.ForeignKey('rooms.id'), nullable=False),
        sa.Column('start_time', sa.Time),
        sa.Column('end_time', sa.Time),
    )
    
    # 14. Create sync_queue table (references users)
    op.create_table(
        'sync_queue',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('operation', sa.String(20), nullable=False),
        sa.Column('table_name', sa.String(50), nullable=False),
        sa.Column('record_id', UUID(as_uuid=True), nullable=False),
        sa.Column('data_json', sa.JSON),
        sa.Column('synced', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
    )
    
    # 15. Create audit_logs table LAST (references users)
    op.create_table(
        'audit_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('table_name', sa.String(50)),
        sa.Column('record_id', UUID(as_uuid=True)),
        sa.Column('changes_json', sa.JSON),
        sa.Column('timestamp', sa.DateTime, nullable=False),
    )
    
    # Create indexes
    op.create_index('idx_teacher_code', 'teachers', ['teacher_code'])
    op.create_index('idx_subject_code', 'subjects', ['code'])
    op.create_index('idx_class_name', 'classes', ['class_name'])
    op.create_index('idx_timetable_slots_timetable', 'timetable_slots', ['timetable_id'])
    op.create_index('idx_sync_queue_synced', 'sync_queue', ['synced'])
    op.create_index('idx_audit_logs_timestamp', 'audit_logs', ['timestamp'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('audit_logs')
    op.drop_table('sync_queue')
    op.drop_table('timetable_slots')
    op.drop_table('class_subjects')
    op.drop_table('rooms_unavailability')
    op.drop_table('teacher_unavailability')
    op.drop_table('teacher_subjects')
    op.drop_table('timetables')
    op.drop_table('periods')
    op.drop_table('classes')
    op.drop_table('rooms')
    op.drop_table('subjects')
    op.drop_table('teachers')
    op.drop_table('schools')
    op.drop_table('users')
    
    # Drop ENUM types
    op.execute('DROP TYPE IF EXISTS userrole')
    op.execute('DROP TYPE IF EXISTS subjectcategory')
    op.execute('DROP TYPE IF EXISTS classlevel')
    op.execute('DROP TYPE IF EXISTS roomtype')
    op.execute('DROP TYPE IF EXISTS timetablestatus')
    op.execute('DROP TYPE IF EXISTS timetabletype')