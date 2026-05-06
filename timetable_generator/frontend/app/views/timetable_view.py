"""Timetable view – complete with all methods, robust grid, and full Exam Timetable generation."""
import flet as ft

def _norm_role(role: str) -> str:
    return (role or "VIEWER").strip().upper()

def _can_edit(role: str) -> bool:
    return _norm_role(role) in ("ADMIN", "COORDINATOR")

import uuid
import traceback
import threading
import time
import random
from datetime import datetime, timedelta, date


# ─────────────────────────────────────────────────────────────────────────────
# Nigerian public holidays (fixed + approximate variable for 2025-2027)
# ─────────────────────────────────────────────────────────────────────────────
NIGERIAN_HOLIDAYS = {
    # Fixed holidays (month, day)
    "fixed": [
        (1, 1),   # New Year's Day
        (5, 1),   # Workers' Day
        (6, 12),  # Democracy Day
        (10, 1),  # Independence Day
        (12, 25), # Christmas Day
        (12, 26), # Boxing Day
    ],
    # Variable holidays keyed by year → list of date strings YYYY-MM-DD
    "variable": {
        2025: ["2025-03-30", "2025-03-31", "2025-04-18", "2025-04-21", "2025-06-06", "2025-06-07"],
        2026: ["2026-03-20", "2026-03-21", "2026-04-03", "2026-04-06", "2026-06-26", "2026-06-27"],
        2027: ["2027-03-10", "2027-03-11", "2027-03-26", "2027-03-29", "2027-06-17", "2027-06-18"],
    }
}

# Classes excluded from school exams in Third Term (external exams only)
THIRD_TERM_EXEMPT_PATTERNS = ['js3', 'jss3', 'j.s.s 3', 'ss2', 'sss2', 'ss 2', 'ss3', 'sss3', 'ss 3']

# Core subject code prefixes for Nigerian schools
# Core subject codes for MMSS — only these get morning-slot priority.
# Matches exactly what is marked Core in the Subjects screen.
CORE_PREFIXES = (
    'MATHS', 'MATH',    # Mathematics
    'PHY',              # Physics
    'ACC',              # Account
    'B.KEEP', 'BKEEP',  # Book Keeping
    'BUS',              # Business Studies
    'MARKNG',           # Marketing
)


def _is_nigerian_holiday(d: date) -> bool:
    """Return True if *d* is a Nigerian public holiday."""
    # Fixed
    for (m, day) in NIGERIAN_HOLIDAYS["fixed"]:
        if d.month == m and d.day == day:
            return True
    # Variable
    yr = d.year
    for ds in NIGERIAN_HOLIDAYS["variable"].get(yr, []):
        if d == datetime.strptime(ds, "%Y-%m-%d").date():
            return True
    return False


def _is_exam_eligible_date(d: date) -> bool:
    """Return True if date is a valid exam day (weekday, not holiday)."""
    return d.weekday() < 5 and not _is_nigerian_holiday(d)


class TimetableView:
    def __init__(self, app):
        self.app = app
        self.page = app.page
        self._role = _norm_role((app.current_user or {}).get("role", "VIEWER"))

        # ── Tabs ──────────────────────────────────────────────────────────
        _init_role = _norm_role((app.current_user or {}).get("role", "VIEWER"))
        _default_tab = 1 if not _can_edit(_init_role) else 0
        self.view_tabs = ft.Tabs(
            selected_index=_default_tab,
            tabs=[
                ft.Tab(text="Generate"),
                ft.Tab(text="View by Class"),
                ft.Tab(text="View by Teacher"),
                ft.Tab(text="View by Room"),
                ft.Tab(text="Edit"),
            ],
            on_change=self.on_tab_change
        )

        # ── Generation parameters – shared ────────────────────────────────
        self.type_dropdown = ft.Dropdown(
            label="Timetable Type",
            options=[
                ft.dropdown.Option("Class Timetable"),
                ft.dropdown.Option("Exam Timetable"),
            ],
            value="Class Timetable",
            width=300,
            on_change=self._on_type_change,
        )
        self.term_dropdown = ft.Dropdown(
            label="Term",
            options=[
                ft.dropdown.Option("First Term"),
                ft.dropdown.Option("Second Term"),
                ft.dropdown.Option("Third Term"),
            ],
            value="First Term",
            width=200,
        )
        self.academic_year = ft.TextField(
            label="Academic Year",
            value=datetime.now().strftime("%Y") + "/" + str(int(datetime.now().strftime("%Y")) + 1),
            width=200,
        )
        self.parameters = {
            'max_iterations': ft.TextField(label="Max Iterations", value="10000", keyboard_type=ft.KeyboardType.NUMBER, width=150),
            'timeout_seconds': ft.TextField(label="Timeout (s)", value="120", keyboard_type=ft.KeyboardType.NUMBER, width=150),
            'respect_teacher_prefs': ft.Switch(label="Respect Teacher Preferences", value=True),
            'balance_workload': ft.Switch(label="Balance Workload", value=True),
            'core_morning': ft.Switch(label="Core in Morning", value=True),
            'break_periods': ft.TextField(
                label="Break Periods",
                value="4",
                hint_text="e.g. 4  or  4,7  for multiple breaks",
                width=250,
                tooltip="Enter period numbers to mark as breaks (no classes scheduled). Separate multiple with commas.",
            ),
        }

        # ── Exam start date — DatePicker replaces TextField ───────────────
        # A TextField inside a hidden container (visible=False) NEVER syncs
        # typed values back to Python — .value always returns the default.
        # DatePicker is a native OS dialog in page.overlay, completely outside
        # the hidden container, so it always fires reliably.
        from datetime import date as _d, timedelta as _td
        _default_dt   = _d.today() + _td(weeks=2)
        default_exam_date = _default_dt.strftime("%d/%m/%Y")
        self._captured_exam_start_date = default_exam_date   # source of truth

        self._exam_date_display = ft.Text(
            default_exam_date,
            size=14, weight=ft.FontWeight.BOLD, color="#2563EB",
        )

        def _on_date_picked(e):
            if e.control.value:
                self._captured_exam_start_date = \
                    e.control.value.strftime("%d/%m/%Y")
                self._exam_date_display.value = \
                    self._captured_exam_start_date
                # Persist immediately so it survives app restarts
                self._save_setting("exam_start_date",
                                   self._captured_exam_start_date)
                self._exam_date_display.update()

        self._date_picker = ft.DatePicker(
            first_date=datetime(2024, 1, 1),
            last_date=datetime(2030, 12, 31),
            value=datetime(_default_dt.year,
                           _default_dt.month,
                           _default_dt.day),
            on_change=_on_date_picked,
        )

        self.exam_start_date_btn = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(ft.icons.CALENDAR_MONTH, size=16,
                        color=ft.colors.WHITE),
                self._exam_date_display,
            ], spacing=8, tight=True),
            on_click=lambda e: self._date_picker.pick_date(),
            style=ft.ButtonStyle(
                bgcolor={"": "#0F1E3A", "hovered": "#1E40AF"},
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
            ),
        )

        # ── Exam-specific parameters ───────────────────────────────────────
        # Break periods — only relevant for class timetable
        self.break_periods_section = ft.Container(
            visible=True,
            content=ft.Column([
                ft.Divider(),
                ft.Row([
                    ft.Icon(ft.icons.FREE_BREAKFAST, color=ft.colors.ORANGE),
                    ft.Text("Break Periods", weight=ft.FontWeight.BOLD, size=14),
                ], spacing=6),
                ft.Text(
                    "Periods blocked as breaks every day (class timetable only). "
                    "Exam timetable has two 30-minute breaks built in automatically.",
                    size=12, color=ft.colors.GREY_600, italic=True,
                ),
                self.parameters['break_periods'],
            ], spacing=8),
            padding=ft.padding.only(top=4),
        )

        # Container shown only when Exam Timetable is selected
        self.exam_params_section = ft.Container(
            visible=False,
            content=ft.Column([
                ft.Divider(),
                ft.Row([
                    ft.Icon(ft.icons.EVENT, color=ft.colors.PURPLE),
                    ft.Text("Exam Configuration", weight=ft.FontWeight.BOLD, size=15),
                ], spacing=8),
                ft.Row([
                    ft.Icon(ft.icons.CALENDAR_TODAY,
                            color=ft.colors.PURPLE_400, size=18),
                    ft.Text("Exam Start Date:",
                            size=12, weight=ft.FontWeight.W_600),
                    self.exam_start_date_btn,
                ], spacing=8,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Text(
                    "• 3 exams per day  •  Each exam: 2 hours  •  30-min break between exams\n"
                    "• Starts 8:30 AM daily  •  Invigilators assigned randomly (no subject-teacher bias)\n"
                    "• Duration calculated automatically from your subject list\n"
                    "• Weekends & public holidays skipped  •  JS3/SS2/SS3 excluded in Third Term",
                    size=12, color=ft.colors.GREY_700, italic=True,
                ),
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.INFO_OUTLINE, color=ft.colors.BLUE_400, size=16),
                        ft.Text(
                            "Core subjects will be mixed with elective subjects — no two consecutive core exams in the same day.",
                            size=11, color=ft.colors.BLUE_700, italic=True,
                        ),
                    ], spacing=6),
                    bgcolor=ft.colors.BLUE_50,
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                ),
            ], spacing=10),
            padding=ft.padding.symmetric(vertical=4),
        )

        # ── Progress ──────────────────────────────────────────────────────
        self.progress_bar = ft.ProgressBar(width=400, visible=False)
        self.progress_text = ft.Text("", size=14)
        self.generate_btn = ft.ElevatedButton(
            "Generate", icon=ft.icons.PLAY_ARROW_ROUNDED,
            on_click=self.start_generation,
            style=ft.ButtonStyle(
                bgcolor={"": "#2563EB", "hovered": "#1E40AF"},
                color=ft.colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8),
                overlay_color=ft.colors.with_opacity(0.12, ft.colors.WHITE),
                elevation={"": 0, "hovered": 2},
            ),
        )
        self.stop_btn = ft.ElevatedButton(
            "Stop", icon=ft.icons.STOP_ROUNDED,
            on_click=self.stop_generation, visible=False,
            style=ft.ButtonStyle(
                bgcolor={"": "#DC2626", "hovered": "#B91C1C"},
                color=ft.colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8),
                overlay_color=ft.colors.with_opacity(0.12, ft.colors.WHITE),
                elevation={"": 0, "hovered": 2},
            ),
        )

        # ── View dropdowns ────────────────────────────────────────────────
        self.class_dropdown = ft.Dropdown(label="Select Class", options=[], width=300, on_change=self.load_class_timetable)
        self.teacher_dropdown = ft.Dropdown(label="Select Teacher", options=[], width=300, on_change=self.load_teacher_timetable, visible=False)
        self.room_dropdown = ft.Dropdown(label="Select Room", options=[], width=350, on_change=self.load_room_timetable, visible=False)

        # ── Grid container ────────────────────────────────────────────────
        self.grid_container = ft.Column(spacing=4)

        # ── Edit mode ─────────────────────────────────────────────────────
        self.edit_mode = False
        self.undo_stack = []
        self.redo_stack = []

        # Save Changes button — stored for animation
        self._btn_save_changes = ft.ElevatedButton(
            'Save Changes', icon=ft.icons.SAVE_ROUNDED,
            on_click=self._save_changes_animated,
            style=ft.ButtonStyle(
                bgcolor={"": "#16A34A", "hovered": "#15803D"},
                color=ft.colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8),
                overlay_color=ft.colors.with_opacity(0.12, ft.colors.WHITE),
                elevation={"": 0, "hovered": 2},
            ),
        )

        self.edit_toolbar = ft.Container(
            content=ft.Row([
                ft.IconButton(icon=ft.icons.UNDO_ROUNDED,
                              tooltip='Undo last swap', on_click=self.undo),
                ft.IconButton(icon=ft.icons.REDO_ROUNDED,
                              tooltip='Redo', on_click=self.redo),
                self._btn_save_changes,
                ft.ElevatedButton(
                    'Cancel', icon=ft.icons.CANCEL_ROUNDED,
                    on_click=self.cancel_edit,
                    style=ft.ButtonStyle(
                        bgcolor={"": "#DC2626", "hovered": "#B91C1C"},
                        color=ft.colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=8),
                        overlay_color=ft.colors.with_opacity(0.12, ft.colors.WHITE),
                        elevation={"": 0, "hovered": 2},
                    ),
                ),
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.TOUCH_APP_ROUNDED,
                                color=ft.colors.ORANGE_700, size=16),
                        ft.Text('Click a cell, then click another to swap',
                                color=ft.colors.ORANGE_700, size=12, italic=True),
                    ], spacing=4),
                    bgcolor=ft.colors.ORANGE_50, border_radius=8,
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                ),
            ], spacing=8),
            visible=False, padding=10,
            bgcolor="#F1F5F9", border_radius=10,
            border=ft.border.all(1, ft.colors.GREY_200),
        )

        self.conflict_list = ft.ListView(height=150, spacing=5)
        self.conflict_container = ft.Container(
            content=ft.Column([
                ft.Text("Conflicts Detected:", color=ft.colors.RED, weight=ft.FontWeight.BOLD),
                self.conflict_list,
            ]),
            bgcolor=ft.colors.RED_50, padding=10, border_radius=10, visible=False
        )

        self.selected_cell = None
        self.current_timetable_id = None
        self.current_slots = []
        self.generation_task_id = None
        self.generation_running = False
        self.generation_thread = None
        self.days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        self.periods = list(range(1, 10))
        self.locked_cells = set()

        self.wizard_container = None
        self.view_selector_container = None

    # ── Type change handler ───────────────────────────────────────────────
    def _on_type_change(self, e):
        is_exam = self.type_dropdown.value == "Exam Timetable"
        self.exam_params_section.visible = is_exam
        self.break_periods_section.visible = not is_exam
        self.page.update()

    # ── Build ─────────────────────────────────────────────────────────────
    def _get_setting(self, key, default=""):
        """Read a value from app_settings by key."""
        try:
            rows = self.app.local_db.execute(
                "SELECT value FROM app_settings WHERE key=?", (key,))
            return rows[0]["value"] if rows else default
        except Exception:
            return default

    def _save_setting(self, key, value):
        """Persist a value to app_settings (upsert)."""
        try:
            self.app.local_db.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)))
        except Exception as ex:
            print(f"[TimetableView] Could not save setting '{key}': {ex}")

    def build(self):
        self.load_dropdowns()
        # DatePicker must live in page.overlay — not inside any view container
        if self._date_picker not in self.page.overlay:
            self.page.overlay.append(self._date_picker)

        # ── Restore last configured exam start date ────────────────────────
        saved = self._get_setting("exam_start_date", "")
        if saved:
            self._captured_exam_start_date = saved
            self._exam_date_display.value  = saved
            # Also update the DatePicker's internal value so the calendar
            # opens pre-selected on the saved date
            try:
                from datetime import datetime as _dtp
                _dt = _dtp.strptime(saved, "%d/%m/%Y")
                self._date_picker.value = _dt
            except Exception:
                pass

        _viewer_mode = not _can_edit(self._role)
        self.wizard_container = ft.Container(
            content=self.build_generation_wizard(),
            visible=not _viewer_mode, padding=20, bgcolor=ft.colors.WHITE,
            border_radius=12,
            border=ft.border.all(1, ft.colors.GREY_200),
            margin=ft.margin.only(bottom=20),
        )
        self.view_selector_container = ft.Container(
            content=self.build_view_selector(),
            visible=_viewer_mode, padding=20, bgcolor=ft.colors.WHITE,
            border_radius=12,
            border=ft.border.all(1, ft.colors.GREY_200),
            margin=ft.margin.only(bottom=20),
        )
        # For Viewer: auto-load the class timetable on open
        if not _can_edit(self._role):
            self.class_dropdown.visible = True
            self.view_selector_container.content = self.build_view_selector()
            self.load_class_timetable(None)

        return ft.View(
            "/timetable",
            [
                # ── Navy top bar ───────────────────────────────────────
                ft.Container(
                    content=ft.Row([
                        ft.IconButton(
                            icon=ft.icons.ARROW_BACK_ROUNDED,
                            icon_color=ft.colors.WHITE, icon_size=20,
                            tooltip="Back to Dashboard",
                            on_click=lambda e: self.page.go("/dashboard"),
                        ),
                        ft.Container(width=4),
                        ft.Icon(ft.icons.CALENDAR_MONTH_ROUNDED,
                                color=ft.colors.WHITE, size=20),
                        ft.Text("Timetable Management", size=17,
                                weight=ft.FontWeight.BOLD,
                                color=ft.colors.WHITE),
                        ft.Container(expand=True),
                        ft.IconButton(
                            icon=ft.icons.REFRESH_ROUNDED,
                            icon_color=ft.colors.WHITE, icon_size=18,
                            tooltip="Refresh",
                            on_click=self.refresh,
                        ),
                        ft.PopupMenuButton(
                            content=ft.Icon(ft.icons.MORE_VERT,
                                            color=ft.colors.WHITE, size=22),
                            items=[
                                ft.PopupMenuItem(
                                    text="Export Excel (.xlsx)",
                                    on_click=lambda e: self.export_timetable("xlsx")),
                                ft.PopupMenuItem(
                                    text="Print",
                                    on_click=self.print_timetable),
                            ],
                        ),
                    ], spacing=6,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor="#0F1E3A",
                    padding=ft.padding.symmetric(horizontal=16, vertical=10),
                    height=56,
                ),
                ft.Container(
                    content=ft.Column([
                        self.view_tabs,
                        self.wizard_container,
                        self.view_selector_container,
                        self.edit_toolbar,
                        self.conflict_container,
                        ft.Container(
                            content=ft.Row(
                                [self.grid_container],
                                scroll=ft.ScrollMode.ALWAYS,
                                alignment=ft.MainAxisAlignment.CENTER,
                            ),
                            bgcolor=ft.colors.WHITE,
                            border_radius=16,
                            padding=ft.padding.all(28),
                            margin=ft.margin.symmetric(horizontal=16, vertical=8),
                            shadow=ft.BoxShadow(
                                spread_radius=0, blur_radius=24,
                                color=ft.colors.with_opacity(0.09, ft.colors.BLACK),
                                offset=ft.Offset(0, 6),
                            ),
                        ),
                    ], spacing=0),
                    padding=20, bgcolor="#F8FAFC",
                )
            ],
            padding=0, spacing=0, scroll=ft.ScrollMode.ALWAYS,
        )

    def build_generation_wizard(self):
        return ft.Column([
            ft.Text("Generate New Timetable", size=18,
                    weight=ft.FontWeight.BOLD, color="#0F1E3A"),
            ft.Divider(color=ft.colors.GREY_200),
            ft.Container(
                content=ft.Column([
                    ft.Text("Step 1: Basic Information", size=14,
                            weight=ft.FontWeight.W_600, color="#0F1E3A"),
                    ft.Row([self.type_dropdown, self.term_dropdown, self.academic_year],
                           wrap=True, spacing=10),
                    self.exam_params_section,
                ]),
                padding=14, bgcolor=ft.colors.WHITE,
                border=ft.border.all(1, ft.colors.GREY_200),
                border_radius=10, margin=ft.margin.only(bottom=10),
            ),
            ft.Container(
                content=ft.Column([
                    ft.Text("Step 2: Parameters", size=14,
                            weight=ft.FontWeight.W_600, color="#0F1E3A"),
                    ft.Row([self.parameters['max_iterations'],
                            self.parameters['timeout_seconds']],
                           wrap=True, spacing=10),
                    ft.Row([self.parameters['respect_teacher_prefs'],
                            self.parameters['balance_workload'],
                            self.parameters['core_morning']],
                           wrap=True, spacing=20),
                    self.break_periods_section,
                ]),
                padding=14, bgcolor=ft.colors.WHITE,
                border=ft.border.all(1, ft.colors.GREY_200),
                border_radius=10, margin=ft.margin.only(bottom=10),
            ),
            ft.Container(
                content=ft.Column([
                    ft.Text("Step 3: Generate", size=14,
                            weight=ft.FontWeight.W_600, color="#0F1E3A"),
                    ft.Row([self.generate_btn, self.stop_btn]),
                    self.progress_bar,
                    self.progress_text,
                ]),
                padding=14, bgcolor=ft.colors.WHITE,
                border=ft.border.all(1, ft.colors.GREY_200),
                border_radius=10,
            ),
        ])

    def build_view_selector(self):
        idx = self.view_tabs.selected_index
        if idx == 1:
            self.class_dropdown.visible = True
            self.teacher_dropdown.visible = False
            self.room_dropdown.visible = False
            return ft.Row([self.class_dropdown, ft.ElevatedButton("Refresh", icon=ft.icons.REFRESH, on_click=self.refresh_timetable)], spacing=10)
        elif idx == 2:
            self.class_dropdown.visible = False
            self.teacher_dropdown.visible = True
            self.room_dropdown.visible = False
            return ft.Row([self.teacher_dropdown, ft.ElevatedButton("Refresh", icon=ft.icons.REFRESH, on_click=self.refresh_timetable)], spacing=10)
        elif idx == 3:
            self.class_dropdown.visible = False
            self.teacher_dropdown.visible = False
            self.room_dropdown.visible = True
            return ft.Row([self.room_dropdown, ft.ElevatedButton("Refresh", icon=ft.icons.REFRESH, on_click=self.refresh_timetable)], spacing=10)
        elif idx == 4:
            if not _can_edit(self._role):
                return ft.Container()  # Viewer: no edit selector
            self.edit_mode = True
            self.edit_toolbar.visible = True
            self.class_dropdown.visible = True
            self.teacher_dropdown.visible = False
            self.room_dropdown.visible = False
            return ft.Row([self.class_dropdown, ft.Text("Edit Mode: Click cells to swap", color=ft.colors.ORANGE, italic=True)], spacing=10)
        return ft.Container()

    def on_tab_change(self, e):
        idx = self.view_tabs.selected_index
        # Viewer cannot use Generate (0) or Edit (4) tabs
        if not _can_edit(self._role) and idx in (0, 4):
            self.page.show_snack_bar(ft.SnackBar(
                content=ft.Text("Viewers can only use View by Class, Teacher, or Room."),
                bgcolor=ft.colors.ORANGE))
            # redirect to View by Class
            self.view_tabs.selected_index = 1
            self.page.update()
            # now fall through with idx corrected
            idx = 1
        self.class_dropdown.visible = False
        self.teacher_dropdown.visible = False
        self.room_dropdown.visible = False
        self.edit_toolbar.visible = False
        self.edit_mode = False

        show_wizard = (idx == 0)
        if self.wizard_container:
            self.wizard_container.visible = show_wizard
        if self.view_selector_container:
            self.view_selector_container.visible = not show_wizard
            if not show_wizard:
                self.view_selector_container.content = self.build_view_selector()

        if idx == 0:
            self.grid_container.controls[:] = []
            self.page.update()
        elif idx == 1:
            self.class_dropdown.visible = True
            self.load_class_timetable(None)
        elif idx == 2:
            self.teacher_dropdown.visible = True
            self.load_teacher_timetable(None)
        elif idx == 3:
            self.room_dropdown.visible = True
            self.load_room_timetable(None)
        elif idx == 4:
            self.class_dropdown.visible = True
            self.edit_toolbar.visible = True
            self.edit_mode = True
            self.load_class_timetable(None)

    # ── Data Loading ──────────────────────────────────────────────────────
    def load_dropdowns(self):
        print("Loading dropdowns...")
        try:
            classes = self.app.local_db.execute("SELECT id, class_name FROM classes ORDER BY class_name")
            self.class_dropdown.options = [ft.dropdown.Option(key=c['id'], text=c['class_name']) for c in classes or []]

            teachers = self.app.local_db.execute("SELECT id, full_name, teacher_code FROM teachers WHERE is_active = 1 ORDER BY full_name")
            self.teacher_dropdown.options = [ft.dropdown.Option(key=t['id'], text=f"{t['full_name']} ({t['teacher_code']})") for t in teachers or []]

            rooms = self.app.local_db.execute("SELECT id, room_code, room_name FROM rooms WHERE is_available = 1 ORDER BY room_code")
            self.room_dropdown.options = [ft.dropdown.Option(key=r['id'], text=f"{r['room_code']} - {r['room_name']}") for r in rooms or []]

            print(f"Dropdowns loaded: {len(classes or [])} classes, {len(teachers or [])} teachers, {len(rooms or [])} rooms")
        except Exception as e:
            print(f"Error loading dropdowns: {e}")
            traceback.print_exc()

    def get_latest_timetable_id(self, ttype=None):
        """Always use local DB — API calls block the UI.
        If ttype is given, filter by timetables.type."""
        if ttype:
            tt = self.app.local_db.execute(
                "SELECT id FROM timetables WHERE status = 'Published' AND type = ? ORDER BY rowid DESC LIMIT 1", (ttype,)
            )
        else:
            tt = self.app.local_db.execute(
                "SELECT id FROM timetables WHERE status = 'Published' ORDER BY rowid DESC LIMIT 1"
            )
        if tt:
            return tt[0]['id']
        tt = self.app.local_db.execute("SELECT id FROM timetables ORDER BY rowid DESC LIMIT 1")
        return tt[0]['id'] if tt else None

    def load_class_timetable(self, e):
        print("Loading class timetable...")
        if not self.class_dropdown.value:
            self.show_empty_timetable()
            return
        class_id = self.class_dropdown.value
        timetable_id = self.get_latest_timetable_id(ttype='Class Timetable')
        if not timetable_id:
            self.show_empty_timetable()
            return
        self.current_timetable_id = timetable_id
        try:
            slots = self.app.local_db.execute("""
                SELECT ts.*, s.code as subject_code, s.name as subject_name,
                       t.full_name as teacher_name, t.teacher_code,
                       COALESCE(r.room_code,
                           (SELECT rd.room_code FROM rooms rd
                            WHERE rd.is_available = 1
                              AND (
                                UPPER(TRIM(rd.subject_code)) = UPPER(TRIM(s.code))
                                OR UPPER(rd.subject_code) LIKE UPPER(TRIM(s.code)) || ',%'
                                OR UPPER(rd.subject_code) LIKE '%,' || UPPER(TRIM(s.code))
                                OR UPPER(rd.subject_code) LIKE '%,' || UPPER(TRIM(s.code)) || ',%'
                              )
                            LIMIT 1)
                       ) as room_code,
                       COALESCE(r.room_name,
                           (SELECT rd.room_name FROM rooms rd
                            WHERE rd.is_available = 1
                              AND (
                                UPPER(TRIM(rd.subject_code)) = UPPER(TRIM(s.code))
                                OR UPPER(rd.subject_code) LIKE UPPER(TRIM(s.code)) || ',%'
                                OR UPPER(rd.subject_code) LIKE '%,' || UPPER(TRIM(s.code))
                                OR UPPER(rd.subject_code) LIKE '%,' || UPPER(TRIM(s.code)) || ',%'
                              )
                            LIMIT 1)
                       ) as room_name
                FROM timetable_slots ts
                JOIN subjects s ON ts.subject_id = s.id
                JOIN teachers t ON ts.teacher_id = t.id
                LEFT JOIN rooms r ON ts.room_id = r.id
                WHERE ts.timetable_id = ? AND ts.class_id = ?
                ORDER BY ts.day_of_week, ts.period_number
            """, (timetable_id, class_id))
            self.current_slots = slots if slots else []
            print(f"Loaded {len(self.current_slots)} slots")
            if not self.current_slots:
                self.show_empty_timetable()
                self.page.show_snack_bar(ft.SnackBar(
                    content=ft.Text("No timetable slots found for this class. Try regenerating the timetable."),
                    bgcolor=ft.colors.ORANGE))
                return
            self.display_timetable_grid('class')
        except Exception as e:
            print(f"Error loading class timetable: {e}")
            traceback.print_exc()
            self.show_empty_timetable()

    def load_teacher_timetable(self, e):
        print("Loading teacher timetable...")
        if not self.teacher_dropdown.value:
            self.show_empty_timetable()
            return
        teacher_id = self.teacher_dropdown.value
        timetable_id = self.get_latest_timetable_id(ttype='Class Timetable')
        if not timetable_id:
            self.show_empty_timetable()
            return
        try:
            slots = self.app.local_db.execute("""
                SELECT ts.*, s.code as subject_code, s.name as subject_name,
                       c.class_name,
                       COALESCE(r.room_code,
                           (SELECT rd.room_code FROM rooms rd
                            WHERE rd.is_available = 1
                              AND (
                                UPPER(TRIM(rd.subject_code)) = UPPER(TRIM(s.code))
                                OR UPPER(rd.subject_code) LIKE UPPER(TRIM(s.code)) || ',%'
                                OR UPPER(rd.subject_code) LIKE '%,' || UPPER(TRIM(s.code))
                                OR UPPER(rd.subject_code) LIKE '%,' || UPPER(TRIM(s.code)) || ',%'
                              )
                            LIMIT 1)
                       ) as room_code,
                       COALESCE(r.room_name,
                           (SELECT rd.room_name FROM rooms rd
                            WHERE rd.is_available = 1
                              AND (
                                UPPER(TRIM(rd.subject_code)) = UPPER(TRIM(s.code))
                                OR UPPER(rd.subject_code) LIKE UPPER(TRIM(s.code)) || ',%'
                                OR UPPER(rd.subject_code) LIKE '%,' || UPPER(TRIM(s.code))
                                OR UPPER(rd.subject_code) LIKE '%,' || UPPER(TRIM(s.code)) || ',%'
                              )
                            LIMIT 1)
                       ) as room_name
                FROM timetable_slots ts
                JOIN subjects s ON ts.subject_id = s.id
                JOIN classes c ON ts.class_id = c.id
                LEFT JOIN rooms r ON ts.room_id = r.id
                WHERE ts.timetable_id = ? AND ts.teacher_id = ?
                ORDER BY ts.day_of_week, ts.period_number
            """, (timetable_id, teacher_id))
            self.current_slots = slots if slots else []
            self.display_timetable_grid('teacher')
        except Exception as e:
            print(e)
            self.show_empty_timetable()

    def load_room_timetable(self, e):
        print("Loading room timetable...")
        if not self.room_dropdown.value:
            self.show_empty_timetable()
            return
        room_id = self.room_dropdown.value
        timetable_id = self.get_latest_timetable_id(ttype='Class Timetable')
        if not timetable_id:
            self.show_empty_timetable()
            return
        try:
            slots = self.app.local_db.execute("""
                SELECT ts.*, s.code as subject_code, s.name as subject_name,
                       c.class_name,
                       t.full_name as teacher_name, t.teacher_code
                FROM timetable_slots ts
                JOIN subjects s ON ts.subject_id = s.id
                JOIN classes c ON ts.class_id = c.id
                JOIN teachers t ON ts.teacher_id = t.id
                WHERE ts.timetable_id = ? AND ts.room_id = ?
                ORDER BY ts.day_of_week, ts.period_number
            """, (timetable_id, room_id))
            self.current_slots = slots if slots else []
            self.display_timetable_grid('room')
        except Exception as e:
            print(e)
            self.show_empty_timetable()

    def display_timetable_grid(self, view_type='class'):
        """Transposed grid: time slots as columns, days as rows."""
        print(f"Displaying grid, {len(self.current_slots)} slots")
        _rows = []

        CELL_W = 118
        DAY_W = 85
        HDR_H = 52
        ROW_H = 88
        RADIUS = 10

        break_raw = (self.parameters['break_periods'].value or '').strip()
        BREAK_P = set()
        for part in break_raw.split(','):
            part = part.strip()
            if part.isdigit():
                BREAK_P.add(int(part))

        header_cells = [
            ft.Container(
                ft.Text('Day', weight=ft.FontWeight.BOLD, color=ft.colors.WHITE, size=13),
                width=DAY_W, height=HDR_H, bgcolor='#1565C0',
                border_radius=ft.border_radius.only(top_left=RADIUS, bottom_left=RADIUS),
                alignment=ft.alignment.center,
            )
        ]
        for i, period in enumerate(self.periods):
            is_last = (i == len(self.periods) - 1)
            t_s, t_e = self.get_period_time(period)
            if period in BREAK_P:
                header_cells.append(ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.FREE_BREAKFAST, color='#D97706', size=13),
                        ft.Text('BREAK', weight=ft.FontWeight.BOLD, color='#92400E', size=9),
                        ft.Text(t_s + ' - ' + t_e, size=8, color='#92400E'),
                    ], alignment=ft.MainAxisAlignment.CENTER,
                       horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                    width=CELL_W, height=HDR_H, bgcolor='#FEF3C7',
                    border_radius=ft.border_radius.only(
                        top_right=RADIUS if is_last else 0,
                        bottom_right=RADIUS if is_last else 0),
                    alignment=ft.alignment.center,
                ))
            else:
                header_cells.append(ft.Container(
                    content=ft.Column([
                        ft.Text(t_s, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE, size=10),
                        ft.Text(t_e, color='#90CAF9', size=9),
                    ], alignment=ft.MainAxisAlignment.CENTER,
                       horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                    width=CELL_W, height=HDR_H, bgcolor='#1976D2',
                    border_radius=ft.border_radius.only(
                        top_right=RADIUS if is_last else 0,
                        bottom_right=RADIUS if is_last else 0),
                    alignment=ft.alignment.center,
                ))
        _rows.append(
            ft.Row(header_cells, spacing=0, alignment=ft.MainAxisAlignment.CENTER))
        _rows.append(
            ft.Container(height=3, bgcolor='#1565C0', border_radius=2, margin=ft.margin.only(bottom=4)))

        DAY_BGS = ['#EBF3FB', '#F5F5F5', '#EBF3FB', '#F5F5F5', '#EBF3FB']
        for di, day in enumerate(self.days):
            day_bg = DAY_BGS[di]
            row_cells = [
                ft.Container(
                    ft.Text(day, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE, size=12),
                    width=DAY_W, height=ROW_H, bgcolor='#2E75B6',
                    alignment=ft.alignment.center,
                )
            ]
            for period in self.periods:
                if period in BREAK_P:
                    row_cells.append(ft.Container(
                        content=ft.Row([ft.Icon(ft.icons.FREE_BREAKFAST, color='#D97706', size=14)],
                                       alignment=ft.MainAxisAlignment.CENTER),
                        width=CELL_W, height=ROW_H, bgcolor='#FFFBEB',
                        border=ft.border.all(1, '#FDE68A'), alignment=ft.alignment.center,
                    ))
                    continue

                slot = next(
                    (s for s in self.current_slots
                     if int(s.get('period_number') or 0) == period and s.get('day_of_week') == day), None)
                if slot:
                    bg, border_col, text_col = self.get_subject_palette(slot.get('subject_code', ''))
                    locked = (period, day) in self.locked_cells
                    if view_type == 'class':
                        l1 = slot.get('subject_code', '')
                        l2 = slot.get('subject_name', '') or l1
                        l3 = slot.get('teacher_name', '')
                        l4 = slot.get('room_code', '') or ''
                    elif view_type == 'teacher':
                        l1 = slot.get('subject_code', '')
                        l2 = slot.get('subject_name', '') or l1
                        l3 = slot.get('class_name', '')
                        l4 = slot.get('room_code', '') or ''
                    else:
                        l1 = slot.get('subject_code', '')
                        l2 = slot.get('subject_name', '') or l1
                        l3 = slot.get('class_name', '')
                        l4 = slot.get('teacher_name', '') or ''
                    cell_rows = [
                        ft.Text(l1, weight=ft.FontWeight.BOLD, color=text_col, size=13,
                                text_align=ft.TextAlign.CENTER),
                        ft.Text(l2, size=8, color=text_col, opacity=0.7,
                                text_align=ft.TextAlign.CENTER, max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Container(height=1, bgcolor=border_col, opacity=0.25,
                                     margin=ft.margin.symmetric(vertical=1)),
                        ft.Text(l3, size=9, color=text_col, text_align=ft.TextAlign.CENTER,
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ]
                    if l4:
                        cell_rows.append(ft.Container(
                            content=ft.Text(l4, size=8, color=text_col, weight=ft.FontWeight.BOLD,
                                            text_align=ft.TextAlign.CENTER),
                            bgcolor='#00000015', border=ft.border.all(1, border_col),
                            border_radius=4, padding=ft.padding.symmetric(horizontal=4, vertical=1),
                            margin=ft.margin.only(top=1),
                        ))
                    cell = ft.Container(
                        content=ft.Column(cell_rows, alignment=ft.MainAxisAlignment.CENTER,
                                          horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                        width=CELL_W, height=ROW_H, bgcolor=bg,
                        border=ft.border.all(1.5, border_col), border_radius=RADIUS,
                        padding=ft.padding.symmetric(horizontal=6, vertical=5),
                        margin=ft.margin.all(2),
                        data={'period': period, 'day': day, 'slot': slot},
                        on_click=self.cell_click if self.edit_mode else None,
                        opacity=0.5 if locked else 1.0,
                        ink=self.edit_mode,
                        shadow=ft.BoxShadow(spread_radius=0, blur_radius=6,
                                            color=ft.colors.with_opacity(0.10, ft.colors.BLACK),
                                            offset=ft.Offset(0, 2)),
                    )
                else:
                    cell = ft.Container(
                        ft.Text('—', color='#CBD5E1', size=18),
                        width=CELL_W, height=ROW_H, bgcolor=day_bg,
                        border=ft.border.all(1, '#E2E8F0'), border_radius=RADIUS,
                        alignment=ft.alignment.center, margin=ft.margin.all(2),
                    )
                row_cells.append(cell)

            _rows.append(
                ft.Row(row_cells, spacing=0, alignment=ft.MainAxisAlignment.CENTER))

        self.grid_container.controls[:] = _rows
        self.page.update()
        print("Grid updated")

    # ── Time label helper ─────────────────────────────────────────────────
    def get_period_time(self, period, break_periods=None):
        start = datetime(2000, 1, 1, 8, 0)
        DURATION = 40
        slot_start = start + timedelta(minutes=(period - 1) * DURATION)
        slot_end = slot_start + timedelta(minutes=DURATION)
        fmt = '%I:%M %p'
        return (slot_start.strftime(fmt).lstrip('0'), slot_end.strftime(fmt).lstrip('0'))

    SUBJECT_PALETTE = {
        'MATH':  ('#DBEAFE', '#3B82F6', '#1E40AF'),
        'ENG':   ('#D1FAE5', '#10B981', '#065F46'),
        'PHY':   ('#EDE9FE', '#8B5CF6', '#4C1D95'),
        'CHEM':  ('#FEF3C7', '#F59E0B', '#78350F'),
        'BIO':   ('#CCFBF1', '#14B8A6', '#134E4A'),
        'COMP':  ('#F3E8FF', '#A855F7', '#581C87'),
        'AGRI':  ('#ECFCCB', '#84CC16', '#365314'),
        'CIVI':  ('#E0F2FE', '#0EA5E9', '#0C4A6E'),
        'FMAT':  ('#DBEAFE', '#2563EB', '#1E3A8A'),
        'BSCI':  ('#CCFBF1', '#2DD4BF', '#134E4A'),
        'BTEC':  ('#FEE2E2', '#F87171', '#7F1D1D'),
        'FART':  ('#FCE7F3', '#EC4899', '#831843'),
        'SOS':   ('#FFEDD5', '#FB923C', '#431407'),
        'CRS':   ('#FEF9C3', '#EAB308', '#713F12'),
        'PHE':   ('#DCFCE7', '#22C55E', '#14532D'),
        'FRE':   ('#F0FDF4', '#16A34A', '#14532D'),
        'HMGT':  ('#FDF4FF', '#C084FC', '#581C87'),
        'TD':    ('#FFF7ED', '#FB923C', '#7C2D12'),
        'GOVT':  ('#E0F2FE', '#38BDF8', '#0C4A6E'),
        'ECO':   ('#F0FDF4', '#86EFAC', '#14532D'),
        'LIT':   ('#FDF2F8', '#F472B6', '#831843'),
        'HIST':  ('#EEF2FF', '#818CF8', '#312E81'),
        'GEO':   ('#FEF2F2', '#FCA5A5', '#7F1D1D'),
    }

    def get_subject_palette(self, code):
        key = (code or '').upper().strip()
        for prefix, colors in self.SUBJECT_PALETTE.items():
            if key.startswith(prefix):
                return colors
        fallbacks = [
            ('#F1F5F9', '#94A3B8', '#334155'), ('#FDF6B2', '#E3A008', '#723B13'),
            ('#DEF7EC', '#0E9F6E', '#014737'), ('#FDE8E8', '#F05252', '#771D1D'),
            ('#E5EDFF', '#6875F5', '#1E429F'), ('#FDF2F8', '#E74694', '#751A3D'),
            ('#F3FAF7', '#31C48D', '#014737'), ('#FFF8F1', '#FF8A4C', '#771D1D'),
            ('#EBF5FB', '#3F83F8', '#1E429F'), ('#F4F0FF', '#9F7AEA', '#44337A'),
            ('#FEFCE8', '#F6E05E', '#744210'), ('#F0FFF4', '#68D391', '#276749'),
        ]
        return fallbacks[abs(hash(code)) % len(fallbacks)]

    def get_subject_color(self, code):
        return self.get_subject_palette(code)[0]

    def show_empty_timetable(self):
        print("Showing empty timetable (transposed)")
        _rows = []
        CELL_W = 118; DAY_W = 85; HDR_H = 52; ROW_H = 88; RADIUS = 10

        try:
            break_raw = (self.parameters['break_periods'].value or '').strip()
            break_periods = {int(p.strip()) for p in break_raw.split(',') if p.strip().isdigit()}
        except Exception:
            break_periods = {4}

        header_cells = [
            ft.Container(
                ft.Text('Day', weight=ft.FontWeight.BOLD, color=ft.colors.WHITE, size=13),
                width=DAY_W, height=HDR_H, bgcolor='#1565C0',
                border_radius=ft.border_radius.only(top_left=RADIUS, bottom_left=RADIUS),
                alignment=ft.alignment.center,
            )
        ]
        for i, period in enumerate(self.periods):
            is_last = (i == len(self.periods) - 1)
            t_s, t_e = self.get_period_time(period)
            if period in break_periods:
                header_cells.append(ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.FREE_BREAKFAST, color='#D97706', size=13),
                        ft.Text('BREAK', weight=ft.FontWeight.BOLD, color='#92400E', size=9),
                        ft.Text(f'{t_s} - {t_e}', size=8, color='#92400E'),
                    ], alignment=ft.MainAxisAlignment.CENTER,
                       horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                    width=CELL_W, height=HDR_H, bgcolor='#FEF3C7',
                    border_radius=ft.border_radius.only(
                        top_right=RADIUS if is_last else 0,
                        bottom_right=RADIUS if is_last else 0),
                    alignment=ft.alignment.center,
                ))
            else:
                header_cells.append(ft.Container(
                    content=ft.Column([
                        ft.Text(t_s, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE, size=10),
                        ft.Text(t_e, color='#90CAF9', size=9),
                    ], alignment=ft.MainAxisAlignment.CENTER,
                       horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                    width=CELL_W, height=HDR_H, bgcolor='#1976D2',
                    border_radius=ft.border_radius.only(
                        top_right=RADIUS if is_last else 0,
                        bottom_right=RADIUS if is_last else 0),
                    alignment=ft.alignment.center,
                ))

        _rows.append(
            ft.Row(header_cells, spacing=0, alignment=ft.MainAxisAlignment.CENTER))
        _rows.append(
            ft.Container(height=3, bgcolor='#1565C0', border_radius=2, margin=ft.margin.only(bottom=4)))

        DAY_BGS = ['#EBF3FB', '#F5F5F5', '#EBF3FB', '#F5F5F5', '#EBF3FB']
        for di, day in enumerate(self.days):
            day_bg = DAY_BGS[di]
            row_cells = [
                ft.Container(
                    ft.Text(day, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE, size=11),
                    width=DAY_W, height=ROW_H, bgcolor='#2E75B6',
                    alignment=ft.alignment.center,
                )
            ]
            for period in self.periods:
                if period in break_periods:
                    row_cells.append(ft.Container(
                        content=ft.Row([ft.Icon(ft.icons.FREE_BREAKFAST, color='#D97706', size=14)],
                                       alignment=ft.MainAxisAlignment.CENTER),
                        width=CELL_W, height=ROW_H, bgcolor='#FFFBEB',
                        border=ft.border.all(1, '#FDE68A'), alignment=ft.alignment.center,
                    ))
                else:
                    row_cells.append(ft.Container(
                        ft.Text('—', color='#CBD5E1', size=18),
                        width=CELL_W, height=ROW_H, bgcolor=day_bg,
                        border=ft.border.all(1, '#E2E8F0'), border_radius=RADIUS,
                        alignment=ft.alignment.center, margin=ft.margin.all(2),
                    ))
            _rows.append(
                ft.Row(row_cells, spacing=0, alignment=ft.MainAxisAlignment.CENTER))
        self.grid_container.controls[:] = _rows
        self.page.update()

    # ══════════════════════════════════════════════════════════════════════
    # Generation  (fully local — no API server required)
    # ══════════════════════════════════════════════════════════════════════
    def start_generation(self, e):
        if not _can_edit(self._role):
            self.page.show_snack_bar(ft.SnackBar(
                content=ft.Text("Viewers cannot generate timetables."),
                bgcolor=ft.colors.RED))
            return
        # _captured_exam_start_date is already set by the DatePicker
        # on_change handler when the user picks a date — no TextField read.
        print(f"[Generate] exam start date = '{self._captured_exam_start_date}'")

        self.generate_btn.visible = False
        self.stop_btn.visible = True
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.progress_text.value = "Starting generation..."
        self.page.update()

        self.generation_running = True
        self.generation_thread = threading.Thread(target=self._run_local_generation, daemon=True)
        self.generation_thread.start()

    def _update_progress(self, value, message):
        self.progress_bar.value = value
        self.progress_text.value = message
        self.page.update()

    def _run_local_generation(self):
        """Route to class or exam generation based on type dropdown."""
        self._navigate_after_generation = None
        try:
            if self.type_dropdown.value == "Class Timetable":
                if not self._check_data_feasibility():
                    return      # dialog shown — user must fix data first
                self._run_class_generation()
            else:
                self._run_exam_generation()
        except Exception as ex:
            print(f"Generation error: {ex}")
            traceback.print_exc()
            self.page.show_snack_bar(ft.SnackBar(
                content=ft.Text(f"Generation error: {ex}"), bgcolor=ft.colors.RED
            ))
        finally:
            # Reset UI first, THEN navigate — prevents threading race on page.update()
            self.reset_generation_ui()
            target = getattr(self, '_navigate_after_generation', None)
            if target:
                self._navigate_after_generation = None
                self.page.go(target)

    # ──────────────────────────────────────────────────────────────────────
    # PRE-GENERATION DATA FEASIBILITY CHECK
    # ──────────────────────────────────────────────────────────────────────
    def _check_data_feasibility(self) -> bool:
        """
        Verify that all assigned periods can physically fit into the week.
        Returns True if generation should proceed, False to stop with a dialog.

        Check A — Class overload:
          A class has more total periods assigned than usable slots in the week.
          e.g. JSS1A assigned 40 periods, only 35 available (5 days × 7 periods).

        Check B — Teacher overload:
          A teacher is assigned more total teaching periods than slots in the week.
          e.g. one Chemistry teacher assigned to all 27 classes × 3 periods = 81,
          but only 35 slots exist.  No algorithm can solve this.
        """
        try:
            db = self.app.local_db
            self._update_progress(0.03, "Checking data feasibility…")

            break_raw = (self.parameters['break_periods'].value or '4').strip()
            BREAK_PERIODS = set()
            for part in break_raw.split(','):
                part = part.strip()
                if part.isdigit():
                    BREAK_PERIODS.add(int(part))

            usable_per_day = 9 - len(BREAK_PERIODS)   # 9 periods per day now
            MAX_SLOTS      = 5 * usable_per_day        # e.g. 5 × 8 = 40

            rows = db.execute("""
                SELECT cs.class_id,  c.class_name,
                       cs.teacher_id, t.full_name AS teacher_name,
                       s.name        AS subject_name,
                       COALESCE(s.periods_per_week, 3) AS ppw
                FROM class_subjects cs
                JOIN subjects s ON s.id = cs.subject_id
                JOIN classes  c ON c.id = cs.class_id
                JOIN teachers t ON t.id = cs.teacher_id
            """) or []

            if not rows:
                return True     # no assignments — caught later in generation

            # ── A: class totals ────────────────────────────────────────
            class_total = {}
            class_name  = {}
            for r in rows:
                cid = r['class_id']
                class_total[cid]  = class_total.get(cid, 0) + r['ppw']
                class_name[cid]   = r['class_name']

            bad_classes = sorted(
                [(class_name[c], class_total[c], class_total[c] - MAX_SLOTS)
                 for c in class_total if class_total[c] > MAX_SLOTS],
                key=lambda x: -x[2]
            )

            # ── B: teacher totals ──────────────────────────────────────
            teacher_total = {}
            teacher_name  = {}
            for r in rows:
                tid = r['teacher_id']
                teacher_total[tid]  = teacher_total.get(tid, 0) + r['ppw']
                teacher_name[tid]   = r['teacher_name']

            bad_teachers = sorted(
                [(teacher_name[t], teacher_total[t], teacher_total[t] - MAX_SLOTS)
                 for t in teacher_total if teacher_total[t] > MAX_SLOTS],
                key=lambda x: -x[2]
            )

            if not bad_classes and not bad_teachers:
                self._update_progress(0.05, "Data check passed ✅")
                return True

            # ── Build dialog ───────────────────────────────────────────
            content_rows = []

            if bad_classes:
                lines = "\n".join(
                    f"  • {name}:  {total} assigned,  max {MAX_SLOTS}"
                    f"  ({over:+d})"
                    for name, total, over in bad_classes[:10]
                ) + (
                    f"\n  … and {len(bad_classes)-10} more"
                    if len(bad_classes) > 10 else ""
                )
                content_rows.append(ft.Container(
                    content=ft.Column([
                        ft.Text("Classes with too many periods",
                                weight=ft.FontWeight.BOLD,
                                size=13, color=ft.colors.RED_900),
                        ft.Text(lines, size=12, color=ft.colors.RED_900,
                                font_family="monospace"),
                    ], spacing=4),
                    bgcolor=ft.colors.RED_50, border_radius=8,
                    padding=ft.padding.all(10),
                ))

            if bad_teachers:
                lines = "\n".join(
                    f"  • {name}:  {total} periods assigned,  max {MAX_SLOTS}"
                    f"  ({over:+d})"
                    for name, total, over in bad_teachers[:10]
                ) + (
                    f"\n  … and {len(bad_teachers)-10} more"
                    if len(bad_teachers) > 10 else ""
                )
                content_rows.append(ft.Container(
                    content=ft.Column([
                        ft.Text("Teachers with too many periods",
                                weight=ft.FontWeight.BOLD,
                                size=13, color=ft.colors.ORANGE_900),
                        ft.Text(lines, size=12, color=ft.colors.ORANGE_900,
                                font_family="monospace"),
                    ], spacing=4),
                    bgcolor=ft.colors.ORANGE_50, border_radius=8,
                    padding=ft.padding.all(10),
                ))

            tip = (
                f"Max usable slots/week = {MAX_SLOTS}  "
                f"(5 days × {usable_per_day} periods, "
                f"excluding {len(BREAK_PERIODS)} break period(s)).\n\n"
                "The algorithm will place as many periods as slots allow\n"
                "and report any gaps. You can still generate — gaps will\n"
                "be shown so you know what couldn't fit.\n\n"
                "To eliminate gaps:\n"
                "  • Reduce periods_per_week on some subjects (e.g. 3→2)\n"
                "  • Remove subjects that don't need to be in every class"
            )
            content_rows.append(ft.Container(
                content=ft.Text(tip, size=12, color=ft.colors.GREY_800),
                bgcolor=ft.colors.BLUE_50, border_radius=8,
                padding=ft.padding.all(10),
            ))

            # Use an event to communicate the user's choice back to this
            # thread.  We can't block here so we store the result on self
            # and set a threading.Event.
            import threading as _threading
            self._feasibility_proceed = False
            self._feasibility_event   = _threading.Event()

            def _proceed(e):
                self._feasibility_proceed = True
                dialog.open = False
                self.page.update()
                self._feasibility_event.set()

            def _cancel(e):
                self._feasibility_proceed = False
                dialog.open = False
                self.page.update()
                self._feasibility_event.set()

            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Row([
                    ft.Icon(ft.icons.WARNING_AMBER_ROUNDED,
                            color=ft.colors.ORANGE, size=22),
                    ft.Text("Capacity Warning — Some Periods May Not Fit",
                            weight=ft.FontWeight.BOLD, size=14),
                ], spacing=8),
                content=ft.Container(
                    content=ft.Column(content_rows, spacing=10,
                                      scroll=ft.ScrollMode.AUTO),
                    width=560, height=380,
                ),
                actions=[
                    ft.TextButton(
                        "Cancel",
                        on_click=_cancel,
                        style=ft.ButtonStyle(color=ft.colors.GREY_700),
                    ),
                    ft.ElevatedButton(
                        "Generate Anyway →",
                        icon=ft.icons.PLAY_ARROW_ROUNDED,
                        on_click=_proceed,
                        style=ft.ButtonStyle(
                            bgcolor={"": "#2563EB", "hovered": "#1E40AF"},
                            color=ft.colors.WHITE,
                            shape=ft.RoundedRectangleBorder(radius=8),
                        ),
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            self.page.dialog = dialog
            dialog.open = True
            self.page.update()

            # Wait for user to click a button (max 5 min)
            self._feasibility_event.wait(timeout=300)
            return self._feasibility_proceed

        except Exception as ex:
            print(f"Feasibility check error: {ex}")
            traceback.print_exc()
            return True     # don't block generation on a diagnostics crash

    # ──────────────────────────────────────────────────────────────────────
    # CLASS TIMETABLE GENERATION  —  Smart Greedy (scored candidate selection)
    # ──────────────────────────────────────────────────────────────────────
    def _run_class_generation(self):
        """
        Per-Level Slot-Rotation Greedy — designed for MMSS data structure.

        KEY INSIGHT FROM YOUR DATA
        ──────────────────────────
        Teachers are shared WITHIN a level (OBALEX teaches Maths to all
        JSS1A–E) but completely SEPARATE across levels (OBALEX never
        teaches JSS2). So:

          • JSS1 ↔ JSS2: zero teacher conflicts → schedule independently
          • JSS1A ↔ JSS1B: real conflicts → need coordination

        HOW THE ALGORITHM WORKS
        ────────────────────────
        Step 1  Group classes by level (JSS1, JSS2, JSS3, SS1, SS2, SS3).
                Levels with different teacher pools are fully independent.

        Step 2  Within each level, iterate over every (day, period) slot.
                For each slot, cycle through the level's classes in
                round-robin order and ask:
                  "What is the BEST subject I can place for this class
                   right now, given which teachers are still free?"

        Step 3  For each class in the slot, pick the best available
                subject using this priority:
                  1. Core subjects in morning slots (periods 1–3)
                  2. Subject with fewest remaining periods first (MRV)
                  3. Spread across days — penalise days that already
                     have many subjects for this class

        Step 4  Mark the teacher and class as busy for this slot.
                Move to next class in the round-robin.

        Step 5  Repeat until all periods are placed or no progress.

        WHY THIS IS BETTER
        ──────────────────
        • Every class gets one shot per slot before any class gets two
          → guaranteed fairness across parallel classes in a level
        • No wasted candidates — each slot's teacher pool is shared
          fairly via round-robin
        • Core+morning constraint applied at selection time, not as
          a post-hoc penalty
        • SS2/SS3 (separate teacher pools per class) will fill ~90%+
        • JSS1–SS1 (shared pools) will fill optimally given the
          mathematical limit (~60–70% due to teacher capacity)
        """
        try:
            db = self.app.local_db
            DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday"]
            MAX_PERIODS = 9
            MORNING_P   = {1, 2, 3}

            # ── Load data ──────────────────────────────────────────────
            self._update_progress(0.05, "Loading classes and subjects…")
            classes = db.execute(
                "SELECT * FROM classes ORDER BY level, class_name") or []
            if not classes:
                self.page.show_snack_bar(ft.SnackBar(
                    content=ft.Text("No classes found."),
                    bgcolor=ft.colors.RED)); return

            # Ensure subject_code column exists before querying it
            try:
                db.execute("ALTER TABLE rooms ADD COLUMN subject_code TEXT")
            except Exception:
                pass  # already exists

            rooms = db.execute(
                "SELECT * FROM rooms WHERE is_available=1") or []

            self._update_progress(0.10, "Loading assignments…")
            assignments = db.execute("""
                SELECT cs.class_id, cs.subject_id, cs.teacher_id,
                       s.code, s.name, s.periods_per_week, s.requires_lab,
                       c.level,
                       t.full_name as teacher_name, t.teacher_code
                FROM class_subjects cs
                JOIN subjects  s ON s.id = cs.subject_id
                JOIN teachers  t ON t.id = cs.teacher_id
                JOIN classes   c ON c.id = cs.class_id
            """) or []
            if not assignments:
                self.page.show_snack_bar(ft.SnackBar(
                    content=ft.Text("No subject assignments found."),
                    bgcolor=ft.colors.RED)); return

            # ── DB setup ───────────────────────────────────────────────
            self._update_progress(0.15, "Preparing database…")
            try:
                db.execute(
                    "ALTER TABLE timetables ADD COLUMN break_periods TEXT")
            except Exception: pass

            for row in db.execute(
                "SELECT id FROM timetables WHERE type=? AND term=? "
                "AND academic_year=?",
                (self.type_dropdown.value, self.term_dropdown.value,
                 self.academic_year.value)) or []:
                db.execute("DELETE FROM timetable_slots WHERE timetable_id=?",
                           (row["id"],))
                db.execute("DELETE FROM timetables WHERE id=?", (row["id"],))

            break_raw = (self.parameters["break_periods"].value or "4").strip()
            tid_tt    = str(uuid.uuid4())
            db.execute(
                "INSERT INTO timetables "
                "(id,name,type,term,academic_year,status,break_periods) "
                "VALUES (?,?,?,?,?,'Draft',?)",
                (tid_tt,
                 f"{self.term_dropdown.value} {self.academic_year.value}",
                 self.type_dropdown.value,
                 self.term_dropdown.value,
                 self.academic_year.value,
                 break_raw))

            # ── Constraints ────────────────────────────────────────────
            BREAK_PERIODS = set()
            for part in break_raw.split(","):
                part = part.strip()
                if part.isdigit():
                    BREAK_PERIODS.add(int(part))

            prefer_morning = self.parameters["core_morning"].value

            # All usable (day, period) pairs — period-first so P8/P9
            # are visited in the same pass as P1.
            ALL_SLOTS = [
                (day, p)
                for p in range(1, MAX_PERIODS + 1)
                if p not in BREAK_PERIODS
                for day in DAYS
            ]

            # ── Room index ─────────────────────────────────────────────
            SPECIALIST = {"Lab", "Workshop", "Hall"}
            sc_rooms   = {}          # subject_code (UPPER) → [rooms]
            rooms_by_id = {r["id"]: r for r in rooms}
            for r in rooms:
                raw_sc = (r.get("subject_code") or "").upper().strip()
                if raw_sc:
                    # Support comma-separated codes: "BIO,IBIBS" → maps both to this room
                    for sc in [x.strip() for x in raw_sc.split(",") if x.strip()]:
                        sc_rooms.setdefault(sc, []).append(r)
            print(f"[Room index] sc_rooms keys: {sorted(sc_rooms.keys())}")
            # Generic labs: Lab-type rooms with NO dedicated subject_code
            lab_rooms = [r for r in rooms
                         if r.get("room_type") == "Lab"
                         and not (r.get("subject_code") or "").strip()]
            # Regular rooms: anything that is NOT a specialist room type
            reg_rooms = [r for r in rooms
                         if r.get("room_type") not in SPECIALIST]
            # Dedicated rooms: rooms tied to specific subject code(s).
            # These must NEVER appear as generic fallbacks for other subjects.
            # subject_code may be comma-separated, e.g. "BIO,IBIBS"
            dedicated_ids = {
                r["id"] for r in rooms
                if (r.get("subject_code") or "").strip()
            }

            # Map each class to its assigned default room (set in Classes screen)
            class_default_room = {
                c["id"]: c["default_room_id"]
                for c in classes
                if c.get("default_room_id")
            }

            def _has_dedicated_room(code):
                """Return True if any room is dedicated to this exact subject code.
                Uses EXACT match only — sc_rooms is pre-expanded from comma-separated
                subject_code values so 'BIO,IBIBS' already maps both codes here."""
                return bool(sc_rooms.get((code or "").upper().strip()))

            def pick_room(code, needs_lab, day, period, class_id=None,
                          subj_name=""):
                code_up = (code or "").upper().strip()

                # 1. Class's own assigned room — skip if a dedicated room exists
                #    for this exact subject code (so labs always get their room).
                if class_id and class_id in class_default_room:
                    if not _has_dedicated_room(code_up):
                        rid = class_default_room[class_id]
                        if rid in rooms_by_id and (rid, day, period) not in room_busy:
                            return rid

                # 2. Subject-dedicated room — EXACT match via pre-expanded sc_rooms.
                #    Works for both single codes ("BIO") and multi-codes ("BIO,IBIBS").
                for r in sc_rooms.get(code_up, []):
                    if (r["id"], day, period) not in room_busy:
                        return r["id"]

                # 3. Generic lab (for lab subjects with no dedicated room assigned)
                if needs_lab:
                    for r in lab_rooms:
                        if (r["id"], day, period) not in room_busy:
                            return r["id"]

                # 4. Class default room — last resort when no specialist room found
                if class_id and class_id in class_default_room:
                    rid = class_default_room[class_id]
                    if rid in rooms_by_id and (rid, day, period) not in room_busy:
                        return rid

                # 5. Any available regular room as final fallback
                #    (dedicated rooms are never used as generic fallbacks)
                for r in reg_rooms:
                    if r["id"] not in dedicated_ids and (r["id"], day, period) not in room_busy:
                        return r["id"]
                return None

            # ── State ──────────────────────────────────────────────────
            teacher_busy: dict = {}   # teacher_id → set{(day,period)}
            room_busy:    dict = {}   # (room_id,day,period) → True
            class_busy:   dict = {c["id"]: set() for c in classes}
            class_day_n:  dict = {c["id"]: {} for c in classes}
            # remaining[(class_id, subject_id)] = periods left to place
            remaining:    dict = {}
            for a in assignments:
                key = (a["class_id"], a["subject_id"])
                remaining[key] = a.get("periods_per_week") or 3

            total_needed = sum(remaining.values())

            # ── Index assignments by class ─────────────────────────────
            class_map  = {c["id"]: c for c in classes}
            cls_assign = {}
            for a in assignments:
                cls_assign.setdefault(a["class_id"], []).append(a)

            # ── Group classes by level ─────────────────────────────────
            # Classes within the same level share a teacher pool →
            # must be scheduled together to avoid teacher conflicts.
            # Classes in different levels are fully independent.
            level_groups: dict = {}
            for c in classes:
                level_groups.setdefault(c["level"], []).append(c["id"])

            # ── CORE SUBJECT PREFIXES ──────────────────────────────────
            # (inherited from the outer scope constant)

            # ── Consecutive-pair map ────────────────────────────────────
            # For subjects with ppw ≥ 2, we place both periods back-to-back
            # on the same day so students never have the same subject
            # split across a break.
            #
            # Valid adjacent pairs: (p, p+1) where neither p nor p+1 is a
            # break period.  Given break=4 and 9 periods:
            #   Before break : (1,2)  (2,3)
            #   After break  : (5,6)  (6,7)  (7,8)  (8,9)
            # The pair (3,5) is INVALID — split by the break.
            USABLE = [p for p in range(1, MAX_PERIODS + 1)
                      if p not in BREAK_PERIODS]

            CONSEC_PAIRS = [
                (USABLE[i], USABLE[i+1])
                for i in range(len(USABLE) - 1)
                if USABLE[i+1] == USABLE[i] + 1   # truly adjacent, not break-separated
            ]
            # e.g. with break=4, periods 1-9:
            # USABLE = [1,2,3,5,6,7,8,9]
            # CONSEC_PAIRS = [(1,2),(2,3),(5,6),(6,7),(7,8),(8,9)]

            slots_created = 0
            max_ppw = max((a.get("periods_per_week") or 1) for a in assignments)

            # ── PHASE 1: Place multi-period subjects as consecutive pairs ─
            # For each subject with ppw=2 we try to find ONE day where both
            # adjacent slots are free for the class AND teacher, then place
            # the pair together. This avoids the break-split problem.
            # For ppw=3: place one pair + one single (handled in phase 2).

            self._update_progress(0.20, "Phase 1: placing consecutive pairs…")

            for level, cids in level_groups.items():
                if not self.generation_running: break

                # Rotate starting class per level so fairness is maintained
                for start_offset, cid in enumerate(cids):
                    if not self.generation_running: break

                    for a in cls_assign.get(cid, []):
                        if not self.generation_running: break

                        sid = a["subject_id"]
                        tid = a["teacher_id"]
                        key = (cid, sid)
                        ppw = remaining.get(key, 0)

                        if ppw < 2:
                            continue   # single-period — handle in phase 2

                        code      = (a.get("code") or "").upper().strip()
                        is_core   = any(code.startswith(p) for p in CORE_PREFIXES)
                        needs_lab = a.get("requires_lab", 0)
                        cdc       = class_day_n[cid]
                        t_busy    = teacher_busy.get(tid, set())
                        c_busy    = class_busy[cid]

                        # Try to place pairs.  For each 2 periods needed,
                        # find the best consecutive pair on any day.
                        while remaining.get(key, 0) >= 2:
                            if not self.generation_running: break

                            best_pair  = None
                            best_score = None

                            for day in DAYS:
                                for (p1, p2) in CONSEC_PAIRS:
                                    if (day, p1) in c_busy: continue
                                    if (day, p2) in c_busy: continue
                                    if (day, p1) in t_busy: continue
                                    if (day, p2) in t_busy: continue

                                    # Check no same-level teacher conflict
                                    # (another class in this level using same
                                    #  teacher in either slot)
                                    if (day, p1) in teacher_busy.get(tid, set()): continue
                                    if (day, p2) in teacher_busy.get(tid, set()): continue

                                    # Prefer morning pairs for core subjects
                                    is_morning = (p1 in MORNING_P and p2 in MORNING_P)
                                    if is_core and is_morning:
                                        morning_score = 0
                                    elif is_core:
                                        morning_score = 2
                                    else:
                                        morning_score = 1
                                    day_load = cdc.get(day, 0)
                                    score = (morning_score, day_load, day)

                                    if best_score is None or score < best_score:
                                        best_score = score
                                        best_pair  = (day, p1, p2)

                            if best_pair is None:
                                break  # no consecutive pair available — phase 2 handles remainder

                            day, p1, p2 = best_pair
                            _sn = a.get("name", "")
                            room1 = pick_room(code, needs_lab, day, p1,
                                              class_id=cid, subj_name=_sn)
                            room2 = pick_room(code, needs_lab, day, p2,
                                              class_id=cid, subj_name=_sn)

                            for period, room_id in [(p1, room1), (p2, room2)]:
                                db.execute(
                                    "INSERT INTO timetable_slots "
                                    "(id,timetable_id,class_id,subject_id,"
                                    "teacher_id,room_id,day_of_week,period_number) "
                                    "VALUES (?,?,?,?,?,?,?,?)",
                                    (str(uuid.uuid4()), tid_tt, cid, sid,
                                     tid, room_id, day, period))
                                class_busy[cid].add((day, period))
                                cdc[day] = cdc.get(day, 0) + 1
                                teacher_busy.setdefault(tid, set()).add((day, period))
                                if room_id:
                                    room_busy[(room_id, day, period)] = True
                                slots_created += 1

                            remaining[key] -= 2

                            pct = min(0.20 + (slots_created / max(total_needed, 1)) * 0.50, 0.70)
                            self._update_progress(pct, f"Pairs placed: {slots_created}/{total_needed}")

            # ── PHASE 2: Place remaining single periods ─────────────────
            # Handles:  ppw=1 subjects, and any leftover from pairs
            # (e.g. ppw=3 after one pair → 1 remaining)
            # Uses same per-level round-robin greedy as before.

            self._update_progress(0.70, "Phase 2: placing single periods…")

            for pass_num in range(1, max_ppw + 1):
                if not self.generation_running: break
                placed_in_pass = 0

                for slot_idx, (day, period) in enumerate(ALL_SLOTS):
                    if not self.generation_running: break

                    if slot_idx % 8 == 0:
                        pct = min(
                            0.70 + (slots_created / max(total_needed, 1)) * 0.22,
                            0.92)
                        self._update_progress(
                            pct,
                            f"Phase 2 · {day} P{period} · "
                            f"{slots_created}/{total_needed}")

                    is_morning = period in MORNING_P

                    for level, cids in level_groups.items():
                        slot_teachers_used: set = set()
                        n = len(cids)
                        ordered_cids = (cids[slot_idx % n:] + cids[:slot_idx % n])

                        for cid in ordered_cids:
                            if (day, period) in class_busy[cid]:
                                continue

                            best = None
                            best_score = None
                            cdc = class_day_n[cid]

                            for a in cls_assign.get(cid, []):
                                sid = a["subject_id"]
                                tid = a["teacher_id"]
                                key = (cid, sid)

                                if remaining.get(key, 0) <= 0: continue
                                if tid in slot_teachers_used: continue
                                if (day, period) in teacher_busy.get(tid, set()): continue

                                code    = (a.get("code") or "").upper()
                                is_core = any(code.startswith(p) for p in CORE_PREFIXES)

                                if is_core and is_morning:       morning_score = 0
                                elif not is_core and not is_morning: morning_score = 1
                                elif is_core and not is_morning: morning_score = 2
                                else:                            morning_score = 1

                                mrv      = -(remaining.get(key, 0))
                                day_load = cdc.get(day, 0)
                                score    = (morning_score, day_load, mrv)

                                if best_score is None or score < best_score:
                                    best_score = score
                                    best = a

                            if best is None: continue

                            sid     = best["subject_id"]
                            tid     = best["teacher_id"]
                            key     = (cid, sid)
                            code    = (best.get("code") or "").upper().strip()
                            room_id = pick_room(code, best.get("requires_lab", 0), day, period,
                                                class_id=cid, subj_name=(best.get("name") or ""))

                            db.execute(
                                "INSERT INTO timetable_slots "
                                "(id,timetable_id,class_id,subject_id,"
                                "teacher_id,room_id,day_of_week,period_number) "
                                "VALUES (?,?,?,?,?,?,?,?)",
                                (str(uuid.uuid4()), tid_tt, cid, sid,
                                 tid, room_id, day, period))

                            class_busy[cid].add((day, period))
                            cdc[day] = cdc.get(day, 0) + 1
                            teacher_busy.setdefault(tid, set()).add((day, period))
                            if room_id:
                                room_busy[(room_id, day, period)] = True

                            remaining[key]       -= 1
                            slot_teachers_used.add(tid)
                            slots_created  += 1
                            placed_in_pass += 1

                if placed_in_pass == 0:
                    break

            # ── Collect gaps ───────────────────────────────────────────
            gaps = []
            for (cid, sid), rem in remaining.items():
                if rem > 0:
                    cls_name  = class_map.get(cid, {}).get("class_name", "?")
                    subj_name = next(
                        (a.get("name") or a.get("code","?")
                         for a in cls_assign.get(cid,[])
                         if a["subject_id"] == sid), sid)
                    gaps.append(f"{cls_name}·{subj_name}({rem})")

            # ── Room repair pass ───────────────────────────────────────
            # Any slot that ended up with room_id=NULL gets a second chance:
            # look up the dedicated room for that subject and fill it in.
            # This handles cases where all pick_room() fallbacks returned None
            # (e.g. dedicated lab was fully booked at that exact slot-time for
            # another class, but the subject still needs a visible location).
            try:
                self._update_progress(0.93, "Assigning missing room locations…")
                null_slots = db.execute("""
                    SELECT ts.id, ts.day_of_week, ts.period_number, s.code as subject_code
                    FROM timetable_slots ts
                    JOIN subjects s ON ts.subject_id = s.id
                    WHERE ts.timetable_id = ? AND ts.room_id IS NULL
                """, (tid_tt,)) or []

                # Build a fresh subject_code → room_id map from dedicated rooms
                ded_rooms = db.execute(
                    "SELECT id, subject_code FROM rooms "
                    "WHERE subject_code IS NOT NULL AND subject_code != '' "
                    "AND is_available = 1"
                ) or []
                ded_map = {}  # upper(subject_code_token) → room_id
                for dr in ded_rooms:
                    raw = (dr.get("subject_code") or "").upper().strip()
                    # Expand comma-separated codes: "BIO,IBIBS" → both map to this room
                    for token in [x.strip() for x in raw.split(",") if x.strip()]:
                        if token not in ded_map:
                            ded_map[token] = dr["id"]

                repaired = 0
                for ns in null_slots:
                    sc = (ns.get("subject_code") or "").upper().strip()
                    # EXACT match only — prefix/fuzzy caused false matches (e.g. IBIBS→BIO-LAB)
                    rid = ded_map.get(sc)
                    if rid:
                        db.execute(
                            "UPDATE timetable_slots SET room_id=? WHERE id=?",
                            (rid, ns["id"]))
                        repaired += 1

                if repaired:
                    print(f"[Room repair] Backfilled room_id for {repaired} slot(s)")
            except Exception as rep_ex:
                print(f"[Room repair] Warning: {rep_ex}")

            # ── Finalise ───────────────────────────────────────────────
            if self.generation_running:
                self._update_progress(0.95, "Saving…")
                db.execute(
                    "UPDATE timetables SET status='Published' WHERE id=?",
                    (tid_tt,))
                self.current_timetable_id = tid_tt
                self._update_progress(
                    1.0,
                    f"Done! {slots_created}/{total_needed} periods placed.")
                time.sleep(0.4)

                if not gaps:
                    msg   = f"✅ Timetable complete! {slots_created} periods."
                    color = ft.colors.GREEN
                else:
                    top  = ", ".join(gaps[:3])
                    more = f" +{len(gaps)-3} more" if len(gaps) > 3 else ""
                    msg  = (f"⚠ {slots_created}/{total_needed} placed. "
                            f"Gaps: {top}{more}. "
                            f"Reduce periods_per_week to eliminate gaps.")
                    color = ft.colors.ORANGE

                self.page.show_snack_bar(
                    ft.SnackBar(content=ft.Text(msg), bgcolor=color))
                self.load_dropdowns()
                self.app.pending_view_type = "class"
                self._navigate_after_generation = "/view_timetable"
            else:
                db.execute(
                    "DELETE FROM timetable_slots WHERE timetable_id=?",
                    (tid_tt,))
                db.execute("DELETE FROM timetables WHERE id=?", (tid_tt,))
                self.page.show_snack_bar(ft.SnackBar(
                    content=ft.Text("Cancelled."),
                    bgcolor=ft.colors.ORANGE))

        except Exception as ex:
            print(f"Generation error: {ex}")
            traceback.print_exc()
            self.page.show_snack_bar(ft.SnackBar(
                content=ft.Text(f"Error: {ex}"), bgcolor=ft.colors.RED))

    # EXAM TIMETABLE GENERATION
    # ──────────────────────────────────────────────────────────────────────
    def _ensure_exam_schema(self, db):
        """Add exam-specific columns to timetable_slots if they don't exist."""
        for col, defn in [
            ("exam_date", "TEXT"),
            ("exam_slot", "INTEGER"),
            ("invigilator_id", "TEXT"),
        ]:
            try:
                db.execute(f"ALTER TABLE timetable_slots ADD COLUMN {col} {defn}")
            except Exception:
                pass  # column already exists

    @staticmethod
    def _classify_subject(assignment) -> bool:
        """Return True if the subject is a Core subject."""
        # Prefer explicit database field
        if assignment.get('is_core') is not None:
            return bool(assignment['is_core'])
        if assignment.get('subject_type'):
            return assignment['subject_type'].lower() in ('core', 'compulsory')
        # Fallback: code-prefix heuristic for Nigerian school subjects
        code = (assignment.get('code') or '').upper().strip()
        return any(code.startswith(p) for p in CORE_PREFIXES)

    @staticmethod
    def _get_exam_dates(start: date, duration_weeks: int) -> list:
        """Return a list of valid exam dates (weekdays, no holidays)."""
        end = start + timedelta(weeks=duration_weeks)
        result = []
        d = start
        while d < end:
            if _is_exam_eligible_date(d):
                result.append(d)
            d += timedelta(days=1)
        return result

    @staticmethod
    def _is_exempt_class(class_name: str, term: str) -> bool:
        """JS3, SS2, SS3 do NOT sit school exams in Third Term."""
        if term != "Third Term":
            return False
        import re
        name = class_name.lower().replace(' ', '').replace('.', '')
        if re.search(r'js+3', name): return True
        if re.search(r'ss+2', name) and not re.search(r'js+2', name): return True
        if re.search(r'ss+3', name) and not re.search(r'js+3', name): return True
        return False

    def _get_class_exam_venues(self, db) -> dict:
        """
        For every class, find their exam venue = the most-used Classroom-type
        room in their published class timetable slots.
        Labs, Halls, Workshops and any other specialist rooms are excluded.

        Returns: { class_id: room_id }  (room_id may be None if not found)
        """
        SPECIALIST_TYPES = {'Lab', 'Workshop', 'Hall'}

        # Get all rooms and index by id, filtering to Classroom types only
        all_rooms = db.execute("SELECT id, room_type FROM rooms") or []
        classroom_ids = {
            r['id'] for r in all_rooms
            if r.get('room_type') not in SPECIALIST_TYPES
        }

        # Get the latest published Class Timetable id
        tt_rows = db.execute(
            "SELECT id FROM timetables WHERE status='Published' AND type='Class Timetable' "
            "ORDER BY rowid DESC LIMIT 1"
        ) or []
        if not tt_rows:
            return {}
        class_tt_id = tt_rows[0]['id']

        # Count how many slots each (class_id, room_id) pair has, skipping labs/halls
        slot_rows = db.execute(
            "SELECT class_id, room_id, COUNT(*) as cnt "
            "FROM timetable_slots "
            "WHERE timetable_id=? AND room_id IS NOT NULL "
            "GROUP BY class_id, room_id",
            (class_tt_id,)
        ) or []

        # For each class, pick the classroom-type room with the highest count
        from collections import defaultdict
        class_room_counts = defaultdict(dict)
        for row in slot_rows:
            if row['room_id'] in classroom_ids:
                class_room_counts[row['class_id']][row['room_id']] = row['cnt']

        venue_map = {}
        for class_id, room_counts in class_room_counts.items():
            if room_counts:
                # Pick the room used most frequently
                venue_map[class_id] = max(room_counts, key=room_counts.get)

        return venue_map

    def _run_exam_generation(self):
        """
        Generate a date-based exam timetable:
          • 3 exam slots per day  (8:30–10:30 | 11:00–13:00 | 13:30–15:30)
          • Core and elective subjects interleaved — no two consecutive cores per day
          • Invigilators: random teacher, NOT the subject teacher, no double-booking
          • Rooms: conflict-free per (date, slot)
          • Skips weekends, Nigerian public holidays
          • JS3 / SS2 / SS3 excluded in Third Term
        """
        try:
            db = self.app.local_db
            self._ensure_exam_schema(db)

            # ── Parse user-supplied start date ────────────────────────────
            self._update_progress(0.05, "Calculating exam schedule…")
            term = self.term_dropdown.value

            raw_date = (self._captured_exam_start_date or '').strip()
            print(f"[ExamGen] Using start date: '{raw_date}'")
            try:
                start_dt = datetime.strptime(raw_date, "%d/%m/%Y").date()
            except ValueError:
                raise ValueError(
                    f"Invalid exam start date '{raw_date}'. "
                    "Please pick a date using the calendar button."
                )
            while not _is_exam_eligible_date(start_dt):
                start_dt += timedelta(days=1)
            start_str = start_dt.strftime("%d/%m/%Y")

            # We don't know how many dates we need yet — load subjects first,
            # then come back and trim/extend.  Use 8 weeks as a safe ceiling.
            all_possible_dates = self._get_exam_dates(start_dt, duration_weeks=8)

            # ── Load school data ──────────────────────────────────────────
            self._update_progress(0.10, "Loading classes and assignments…")
            all_classes = db.execute("SELECT * FROM classes ORDER BY class_name") or []
            if not all_classes:
                raise ValueError("No classes found. Add classes first.")

            # Filter exempt classes for Third Term
            eligible_classes = [
                c for c in all_classes
                if not self._is_exempt_class(c['class_name'], term)
            ]
            if not eligible_classes:
                raise ValueError("All classes are exempt for this term. No exam timetable can be generated.")

            exempt_count = len(all_classes) - len(eligible_classes)
            if exempt_count:
                self._update_progress(0.12,
                    f"Note: {exempt_count} class(es) excluded (Third Term external exams).")
                time.sleep(0.8)

            eligible_ids = {c['id'] for c in eligible_classes}

            # ── Count subjects to determine how many exam days are needed ──
            # We do a quick count now; the full list is built below.
            # 3 exams per day → days_needed = ceil(unique_subjects / 3)
            subj_count_rows = db.execute(
                "SELECT COUNT(DISTINCT subject_id) as cnt FROM class_subjects "
                "WHERE class_id IN ({})".format(
                    ','.join('?' * len(eligible_ids))), tuple(eligible_ids)
            ) or [{'cnt': 0}]
            subj_count = max(subj_count_rows[0].get('cnt', 0), 1)
            import math
            days_needed = math.ceil(subj_count / 3)
            # Trim possible dates to exactly what is needed
            exam_dates = all_possible_dates[:days_needed]
            if not exam_dates:
                raise ValueError(
                    "No valid exam dates found starting from "
                    f"{start_str}. Check that there are non-holiday weekdays available."
                )
            # 3 slots per day: slot numbers 1 / 2 / 3
            all_slots = [(d, s) for d in exam_dates for s in [1, 2, 3]]
            self._update_progress(0.13,
                f"{subj_count} subjects → {days_needed} exam days "
                f"({start_str} → {exam_dates[-1].strftime('%d/%m/%Y')})")

            teachers = db.execute("SELECT * FROM teachers WHERE is_active=1 ORDER BY full_name") or []
            rooms = db.execute("SELECT * FROM rooms WHERE is_available=1") or []

            # ── Build class → exam venue map (most-used Classroom per class) ─
            self._update_progress(0.12, "Determining exam venues from class timetable…")
            class_venue_map = self._get_class_exam_venues(db)
            # Build a quick id lookup for all rooms
            rooms_by_id = {r['id']: r for r in rooms}

            self._update_progress(0.15, "Loading subject assignments…")

            # Base query: guaranteed columns only — never fails on schemas
            # that lack subject_type / is_core.
            raw_assignments = db.execute("""
                SELECT cs.class_id, cs.subject_id, cs.teacher_id,
                       s.code, s.name
                FROM class_subjects cs
                JOIN subjects s ON s.id = cs.subject_id
                WHERE cs.class_id IN ({})
            """.format(','.join('?' * len(eligible_ids))),
                tuple(eligible_ids)
            ) or []

            if not raw_assignments:
                raise ValueError(
                    "No subject assignments found for eligible classes. "
                    "Please assign subjects to classes first "
                    "(Subjects → Assign to Class)."
                )

            # Enrich with optional subject_type / is_core columns.
            # Falls back silently if columns don't exist in this schema.
            subj_meta: dict = {}
            try:
                rows = db.execute(
                    "SELECT id, COALESCE(subject_type,'') as subject_type, "
                    "COALESCE(is_core, 0) as is_core FROM subjects"
                ) or []
                subj_meta = {r['id']: r for r in rows}
            except Exception:
                pass  # columns absent — _classify_subject() uses code prefix

            for a in raw_assignments:
                meta = subj_meta.get(a['subject_id'], {})
                a['subject_type'] = meta.get('subject_type', '')
                a['is_core']      = meta.get('is_core', 0)


            # ── Build subject registry ─────────────────────────────────────
            # subject_id → { meta + list of {class_id, teacher_id} }
            subject_registry = {}
            for a in raw_assignments:
                sid = a['subject_id']
                if sid not in subject_registry:
                    subject_registry[sid] = {
                        'subject_id': sid,
                        'code': a['code'],
                        'name': a['name'],
                        'is_core': self._classify_subject(a),
                        'entries': [],  # [{class_id, teacher_id}]
                    }
                subject_registry[sid]['entries'].append({
                    'class_id': a['class_id'],
                    'teacher_id': a['teacher_id'],
                })

            # ── Interleave core / elective to avoid core-core consecutive ──
            core_subjects = [s for s in subject_registry.values() if s['is_core']]
            elec_subjects = [s for s in subject_registry.values() if not s['is_core']]

            # Shuffle within each group for variety
            random.shuffle(core_subjects)
            random.shuffle(elec_subjects)

            ordered_subjects = []
            max_len = max(len(core_subjects), len(elec_subjects))
            for i in range(max_len):
                if i < len(core_subjects):
                    ordered_subjects.append(core_subjects[i])
                if i < len(elec_subjects):
                    ordered_subjects.append(elec_subjects[i])

            if len(ordered_subjects) > len(all_slots):
                raise ValueError(
                    f"Not enough exam slots ({len(all_slots)}) for {len(ordered_subjects)} subjects. "
                    f"Increase exam duration or add more weeks."
                )

            # ── Create timetable record ────────────────────────────────────
            self._update_progress(0.20, "Creating exam timetable record…")

            # Ensure break_periods column exists
            try:
                db.execute("ALTER TABLE timetables ADD COLUMN break_periods TEXT")
            except Exception:
                pass

            # Delete existing exam timetable for same term+year so regeneration works
            existing = db.execute(
                "SELECT id FROM timetables WHERE type='Exam Timetable' AND term=? AND academic_year=?",
                (self.term_dropdown.value, self.academic_year.value)
            ) or []
            for row in existing:
                db.execute("DELETE FROM timetable_slots WHERE timetable_id=?", (row['id'],))
                db.execute("DELETE FROM timetables WHERE id=?", (row['id'],))

            timetable_id = str(uuid.uuid4())
            timetable_name = f"Exam — {self.term_dropdown.value} {self.academic_year.value}"
            db.execute(
                "INSERT INTO timetables (id, name, type, term, academic_year, status, break_periods) "
                "VALUES (?, ?, ?, ?, ?, 'Draft', '')",
                (timetable_id, timetable_name, "Exam Timetable",
                 self.term_dropdown.value, self.academic_year.value)
            )

            # ── Assign subjects to (date, slot) pairs ─────────────────────
            # subject_id → (date_str, slot_number)
            subject_schedule = {}
            for i, subj in enumerate(ordered_subjects):
                exam_date_obj, exam_slot = all_slots[i]
                subject_schedule[subj['subject_id']] = (
                    exam_date_obj.strftime('%Y-%m-%d'), exam_slot
                )

            # ── Conflict tracking ─────────────────────────────────────────
            # (date_str, slot) → set of teacher_ids used as invigilators
            invig_busy: dict = {}
            # (date_str, slot) → set of room_ids used
            room_busy: dict = {}
            # (class_id, date_str) → count of exams that day
            class_day_count: dict = {}

            total_subjects = len(subject_registry)
            slots_created = 0

            for si, (subj_id, (date_str, slot_no)) in enumerate(subject_schedule.items()):
                if not self.generation_running:
                    break

                progress = 0.25 + (si / total_subjects) * 0.65
                subj = subject_registry[subj_id]
                label = "CORE" if subj['is_core'] else "ELEC"
                self._update_progress(
                    progress,
                    f"[{label}] Scheduling {subj['code']} — {subj['name'][:30]}… ({si+1}/{total_subjects})"
                )

                slot_key = (date_str, slot_no)
                invig_busy.setdefault(slot_key, set())
                room_busy.setdefault(slot_key, set())

                # All classes that take this subject
                for entry in subj['entries']:
                    class_id = entry['class_id']
                    subject_teacher_id = entry['teacher_id']

                    # Ensure class doesn't have more than 3 exams on this day
                    day_key = (class_id, date_str)
                    if class_day_count.get(day_key, 0) >= 3:
                        continue

                    # ── Pick invigilator ──────────────────────────────────
                    # Random teacher, NOT the subject's own teacher, not already busy
                    available_invigs = [
                        t for t in teachers
                        if t['id'] not in invig_busy[slot_key]
                        and t['id'] != subject_teacher_id
                    ]
                    if not available_invigs:
                        # Relax the "not subject teacher" constraint
                        available_invigs = [
                            t for t in teachers
                            if t['id'] not in invig_busy[slot_key]
                        ]
                    if not available_invigs:
                        # All teachers busy — pick any (log warning)
                        available_invigs = teachers

                    invigilator = random.choice(available_invigs)
                    invig_busy[slot_key].add(invigilator['id'])

                    # ── Pick exam venue ───────────────────────────────────
                    # Use the class's own classroom from the class timetable.
                    # Falls back to any available non-lab room if not found.
                    preferred_room_id = class_venue_map.get(class_id)

                    if preferred_room_id and preferred_room_id in rooms_by_id:
                        # Always use the class's own room — no conflict possible
                        # since exams and classes run on entirely separate dates
                        room_id = preferred_room_id
                    else:
                        # Fallback: pick any available non-specialist room
                        SPECIALIST_TYPES = {'Lab', 'Workshop', 'Hall'}
                        fallback_rooms = [
                            r for r in rooms
                            if r['id'] not in room_busy[slot_key]
                            and r.get('room_type') not in SPECIALIST_TYPES
                        ]
                        if not fallback_rooms:
                            # Last resort: any available room
                            fallback_rooms = [
                                r for r in rooms
                                if r['id'] not in room_busy[slot_key]
                            ]
                        room_id = fallback_rooms[0]['id'] if fallback_rooms else None

                    if room_id:
                        room_busy[slot_key].add(room_id)

                    # ── Insert exam slot ──────────────────────────────────
                    slot_id = str(uuid.uuid4())
                    db.execute(
                        "INSERT INTO timetable_slots "
                        "(id, timetable_id, class_id, subject_id, "
                        " teacher_id, room_id, day_of_week, period_number, "
                        " exam_date, exam_slot, invigilator_id) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            slot_id, timetable_id, class_id, subj_id,
                            subject_teacher_id, room_id,
                            None, None,         # not used for exam timetable
                            date_str, slot_no, invigilator['id']
                        )
                    )
                    class_day_count[day_key] = class_day_count.get(day_key, 0) + 1
                    slots_created += 1

            # ── Finalise ──────────────────────────────────────────────────
            if self.generation_running:
                self._update_progress(0.95, "Finalising exam timetable…")
                db.execute("UPDATE timetables SET status='Published' WHERE id=?", (timetable_id,))
                self.current_timetable_id = timetable_id
                self._update_progress(1.0, f"Done! {slots_created} exam slots scheduled across {len(exam_dates)} days.")
                time.sleep(0.5)
                self.page.show_snack_bar(ft.SnackBar(
                    content=ft.Text(
                        f"✅ Exam timetable generated!  {slots_created} slots  •  "
                        f"{len(exam_dates)} days  •  "
                        f"{start_str} → {exam_dates[-1].strftime('%d/%m/%Y')}"
                    ),
                    bgcolor=ft.colors.GREEN
                ))
                self.load_dropdowns()
                self.app.pending_view_type = 'exam'
                self._navigate_after_generation = '/view_timetable'
            else:
                db.execute("DELETE FROM timetable_slots WHERE timetable_id=?", (timetable_id,))
                db.execute("DELETE FROM timetables WHERE id=?", (timetable_id,))
                self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Exam generation cancelled."), bgcolor=ft.colors.ORANGE))

        except Exception as ex:
            print(f"Exam generation error: {ex}")
            traceback.print_exc()
            self.page.show_snack_bar(ft.SnackBar(
                content=ft.Text(f"Exam generation error: {ex}"), bgcolor=ft.colors.RED
            ))

    def stop_generation(self, e):
        self.generation_running = False
        self.reset_generation_ui()

    def reset_generation_ui(self):
        self.generate_btn.visible = True
        self.stop_btn.visible = False
        self.progress_bar.visible = False
        self.progress_text.value = ""
        self.page.update()

    # ══════════════════════════════════════════════════════════════════════
    # Export & Print
    # ══════════════════════════════════════════════════════════════════════
    def export_timetable(self, fmt):
        import os
        from datetime import datetime, timedelta

        if not self.current_timetable_id:
            self.page.show_snack_bar(ft.SnackBar(
                content=ft.Text("No timetable loaded. Generate or select one first."),
                bgcolor=ft.colors.RED))
            return
        try:
            rows = self.app.local_db.execute("""
                SELECT c.class_name, ts.day_of_week, ts.period_number,
                       s.code as subject_code, s.name as subject_name,
                       t.full_name as teacher_name, r.room_code
                FROM timetable_slots ts
                JOIN subjects s  ON s.id = ts.subject_id
                JOIN teachers t  ON t.id = ts.teacher_id
                JOIN classes c   ON c.id = ts.class_id
                LEFT JOIN rooms r ON r.id = ts.room_id
                WHERE ts.timetable_id = ?
                ORDER BY c.class_name, ts.day_of_week, ts.period_number
            """, (self.current_timetable_id,)) or []

            if not rows:
                self.page.show_snack_bar(ft.SnackBar(
                    content=ft.Text("No slots found for this timetable."),
                    bgcolor=ft.colors.ORANGE))
                return

            DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
            PERIODS = list(range(1, 10))

            break_raw = (self.parameters['break_periods'].value or "").strip()
            BREAK_PERIODS = set()
            for part in break_raw.split(','):
                part = part.strip()
                if part.isdigit():
                    BREAK_PERIODS.add(int(part))

            def period_time(p):
                start = datetime(2000, 1, 1, 8, 0) + timedelta(minutes=(p - 1) * 40)
                end = start + timedelta(minutes=40)
                return (start.strftime('%I:%M %p').lstrip('0'), end.strftime('%I:%M %p').lstrip('0'))

            slot_map = {}
            classes = []
            for r in rows:
                cls = r['class_name']
                if cls not in classes:
                    classes.append(cls)
                slot_map[(cls, r['day_of_week'], int(r['period_number']))] = r

            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            msg = ''

            if fmt == 'xlsx':
                import openpyxl
                from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
                from openpyxl.utils import get_column_letter

                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = 'Timetable'
                ws.sheet_view.showGridLines = True

                thin = Side(style='thin', color='AAAAAA')

                def _border():
                    return Border(left=thin, right=thin, top=thin, bottom=thin)

                def _cell(ws, row, col, value='', bg=None, bold=False,
                          size=10, wrap=False, italic=False, align='center', color='000000'):
                    c = ws.cell(row=row, column=col, value=value)
                    c.font = Font(name='Calibri', size=size, bold=bold, italic=italic, color=color)
                    c.alignment = Alignment(horizontal=align, vertical='center', wrap_text=wrap)
                    if bg:
                        c.fill = PatternFill('solid', fgColor=bg)
                    c.border = _border()
                    return c

                DAY_BGS = ['EBF3FB', 'F5F5F5', 'EBF3FB', 'F5F5F5', 'EBF3FB']
                cur_row = 1

                for cls in classes:
                    _cell(ws, cur_row, 1, cls, bg='1F3864', bold=True, size=11, align='left', color='FFFFFF')
                    for pi, p in enumerate(PERIODS):
                        t_s, t_e = period_time(p)
                        col = pi + 2
                        if p in BREAK_PERIODS:
                            _cell(ws, cur_row, col, 'BREAK\n' + t_s + ' - ' + t_e, bg='FFE699', bold=True, size=9, wrap=True)
                        else:
                            _cell(ws, cur_row, col, t_s + '\n' + t_e, bg='BDD7EE', bold=True, size=9, wrap=True)
                    ws.row_dimensions[cur_row].height = 36
                    cur_row += 1

                    for di, day in enumerate(DAYS):
                        day_bg = DAY_BGS[di]
                        _cell(ws, cur_row, 1, day, bg='2E75B6', bold=True, size=10, color='FFFFFF')
                        for pi, p in enumerate(PERIODS):
                            col = pi + 2
                            if p in BREAK_PERIODS:
                                _cell(ws, cur_row, col, '', bg='FFFBEB', size=9)
                            else:
                                s = slot_map.get((cls, day, p))
                                if s:
                                    room = s.get('room_code', '') or ''
                                    lines = [s['subject_code'] + ' - ' + s['subject_name'], s['teacher_name']]
                                    if room:
                                        lines.append(room)
                                    _cell(ws, cur_row, col, '\n'.join(lines), bg=day_bg, size=9, wrap=True)
                                else:
                                    _cell(ws, cur_row, col, '', bg=day_bg, size=9)
                        ws.row_dimensions[cur_row].height = 46
                        cur_row += 1

                    for col in range(1, len(PERIODS) + 2):
                        ws.cell(row=cur_row, column=col).border = Border()
                    ws.row_dimensions[cur_row].height = 10
                    cur_row += 1

                ws.column_dimensions['A'].width = 14
                for pi in range(len(PERIODS)):
                    ws.column_dimensions[get_column_letter(pi + 2)].width = 22

                filepath = os.path.join(desktop, 'timetable_export.xlsx')
                wb.save(filepath)
                msg = f'Exported {len(classes)} class(es) to Desktop/timetable_export.xlsx'

            self.page.show_snack_bar(ft.SnackBar(content=ft.Text(msg), bgcolor=ft.colors.GREEN))

        except Exception as ex:
            print(f'Export error: {ex}')
            traceback.print_exc()
            self.page.show_snack_bar(ft.SnackBar(
                content=ft.Text(f'Export error: {ex}'), bgcolor=ft.colors.RED))

    def print_timetable(self, e):
        self.page.launch_url("javascript:window.print();")

    # ══════════════════════════════════════════════════════════════════════
    # Edit Mode
    # ══════════════════════════════════════════════════════════════════════
    def cell_click(self, e):
        if not self.edit_mode:
            return
        cell = e.control
        data = cell.data
        if not data or not data['slot']:
            return
        if self.selected_cell is None:
            self.selected_cell = cell
            cell.bgcolor = ft.colors.YELLOW
            self.page.update()
        else:
            self.perform_swap(self.selected_cell, cell)
            self.selected_cell = None
            self.display_timetable_grid('class')

    def perform_swap(self, src, tgt):
        src_data = src.data
        tgt_data = tgt.data
        if not src_data['slot'] or not tgt_data['slot']:
            return
        self.undo_stack.append({
            'type': 'swap',
            'source': src_data['slot'].copy(),
            'target': tgt_data['slot'].copy(),
        })
        self.redo_stack.clear()
        src_slot = src_data['slot']
        tgt_slot = tgt_data['slot']
        src_slot['day_of_week'],  tgt_slot['day_of_week']  = tgt_slot['day_of_week'],  src_slot['day_of_week']
        src_slot['period_number'], tgt_slot['period_number'] = tgt_slot['period_number'], src_slot['period_number']
        self.check_conflicts()
        self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Swapped! Click Save Changes to keep.")))

    def check_conflicts(self):
        conflicts = []
        teacher_periods = {}
        room_periods = {}
        for slot in self.current_slots:
            key = (slot['teacher_id'], slot['day_of_week'], slot['period_number'])
            if key in teacher_periods:
                conflicts.append(f"Teacher conflict: {slot.get('teacher_name', 'Unknown')} at {slot['day_of_week']} Period {slot['period_number']}")
            teacher_periods[key] = True
            if slot.get('room_id'):
                rkey = (slot['room_id'], slot['day_of_week'], slot['period_number'])
                if rkey in room_periods:
                    conflicts.append(f"Room conflict: {slot.get('room_code', 'Unknown')} at {slot['day_of_week']} Period {slot['period_number']}")
                room_periods[rkey] = True
        self.conflict_list.controls = [ft.Text(c, color=ft.colors.RED, size=12) for c in conflicts[:5]]
        self.conflict_container.visible = len(conflicts) > 0
        if len(conflicts) > 5:
            self.conflict_list.controls.append(
                ft.Text(f"... and {len(conflicts) - 5} more", color=ft.colors.RED, size=12, italic=True))
        self.page.update()

    def undo(self, e):
        if not self.undo_stack:
            return
        action = self.undo_stack.pop()
        self.redo_stack.append(action)
        if action['type'] == 'swap':
            source = action['source']
            target = action['target']
            for slot in self.current_slots:
                if slot.get('id') == source['id']:
                    slot['day_of_week']   = source['day_of_week']
                    slot['period_number'] = source['period_number']
                elif slot.get('id') == target['id']:
                    slot['day_of_week']   = target['day_of_week']
                    slot['period_number'] = target['period_number']
        self.check_conflicts()
        self.display_timetable_grid('class')
        self.page.show_snack_bar(ft.SnackBar(content=ft.Text("↩  Undo")))

    def redo(self, e):
        if not self.redo_stack:
            return
        action = self.redo_stack.pop()
        self.undo_stack.append(action)
        if action['type'] == 'swap':
            source = action['source']
            target = action['target']
            for slot in self.current_slots:
                if slot.get('id') == source['id']:
                    slot['day_of_week']   = target['day_of_week']
                    slot['period_number'] = target['period_number']
                elif slot.get('id') == target['id']:
                    slot['day_of_week']   = source['day_of_week']
                    slot['period_number'] = source['period_number']
        self.check_conflicts()
        self.display_timetable_grid('class')
        self.page.show_snack_bar(ft.SnackBar(content=ft.Text("↪  Redo")))

    # ══════════════════════════════════════════════════════════════════════
    # BUTTON ANIMATION HELPERS
    # ══════════════════════════════════════════════════════════════════════
    async def _animate_elevated_btn(self, btn, save_fn, e,
                                    saving_color="#64748B", success_color="#16A34A",
                                    reset_color="#16A34A"):
        """Spinner → save logic → success flash → reset."""
        import asyncio
        orig_text = btn.text
        orig_icon = btn.icon
        btn.text     = "Saving..."
        btn.icon     = ft.icons.HOURGLASS_TOP_ROUNDED
        btn.disabled = True
        btn.style.bgcolor = {"": saving_color, "hovered": "#475569"}
        self.page.update()
        await asyncio.sleep(0.15)
        save_fn(e)
        btn.text     = "Saved ✓"
        btn.icon     = ft.icons.CHECK_CIRCLE_ROUNDED
        btn.disabled = False
        btn.style.bgcolor = {"": success_color, "hovered": "#15803D"}
        self.page.update()
        await asyncio.sleep(1.4)
        btn.text     = orig_text
        btn.icon     = orig_icon
        btn.style.bgcolor = {"": reset_color, "hovered": "#15803D"}
        self.page.update()

    async def _save_changes_animated(self, e):
        await self._animate_elevated_btn(
            self._btn_save_changes, self.save_changes, e,
            saving_color="#4B5563", success_color="#16A34A", reset_color="#16A34A")

    def save_changes(self, e):
        if not _can_edit(self._role):
            return
        try:
            saved = 0
            for slot in self.current_slots:
                if slot.get('id'):
                    self.app.local_db.update(
                        "timetable_slots", slot['id'],
                        {'day_of_week': slot['day_of_week'],
                         'period_number': slot['period_number']})
                    saved += 1
            # Stay in edit mode after save — just clear selection & undo stack
            self.selected_cell = None
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.conflict_container.visible = False
            self.conflict_list.controls[:] = []
            self.load_class_timetable(None)  # reload from DB, stays on Edit tab
            self.page.show_snack_bar(ft.SnackBar(
                content=ft.Text(f"\u2705  {saved} changes saved! Continue editing or press Cancel to exit."),
                bgcolor=ft.colors.GREEN_700,
                duration=3000,
            ))
        except Exception as ex:
            print(ex)
            traceback.print_exc()
            self.page.show_snack_bar(ft.SnackBar(
                content=ft.Text(f"Save error: {ex}"), bgcolor=ft.colors.RED))

    def cancel_edit(self, e):
        self.edit_mode = False
        self.edit_toolbar.visible = False
        self.conflict_container.visible = False
        self.conflict_list.controls[:] = []
        self.selected_cell = None
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.load_class_timetable(None)
        self.page.update()

    def refresh(self, e):
        self.load_dropdowns()
        self.refresh_timetable(e)

    def refresh_timetable(self, e):
        idx = self.view_tabs.selected_index
        if idx == 1:
            self.load_class_timetable(None)
        elif idx == 2:
            self.load_teacher_timetable(None)
        elif idx == 3:
            self.load_room_timetable(None)
        elif idx == 4:
            self.load_class_timetable(None)
        self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Refreshed")))