"""Academic calendar and periods configuration view - Complete working version."""
import flet as ft
import uuid
import traceback


class CalendarView:
    """Academic calendar configuration screen."""
    
    def __init__(self, app):
        self.app = app
        self.page = app.page
        
        # --- Term Configuration ---
        self.term_dropdown = ft.Dropdown(
            label="Current Term",
            options=[
                ft.dropdown.Option("First Term"),
                ft.dropdown.Option("Second Term"),
                ft.dropdown.Option("Third Term"),
            ],
            value="First Term",
            width=200
        )
        self.academic_year = ft.TextField(
            label="Academic Year",
            value="2025/2026",
            width=200
        )
        self.term_start = ft.TextField(
            label="Term Start Date",
            hint_text="YYYY-MM-DD",
            value="2025-09-15",
            width=150
        )
        self.term_end = ft.TextField(
            label="Term End Date",
            hint_text="YYYY-MM-DD",
            value="2025-12-15",
            width=150
        )
        
        # --- School Days ---
        self.days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        self.selected_days = {
            day: ft.Checkbox(label=day, value=True)
            for day in self.days
        }
        
        # --- Periods Table ---
        self.periods_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Period")),
                ft.DataColumn(ft.Text("Start Time")),
                ft.DataColumn(ft.Text("End Time")),
                ft.DataColumn(ft.Text("Type")),
                ft.DataColumn(ft.Text("Actions")),
            ],
            rows=[]
        )
        
        # Save buttons stored as instance vars for animation
        self._btn_save_period = ft.ElevatedButton(
            "Save",
            icon=ft.icons.SAVE_ROUNDED,
            on_click=self._save_period_animated,
            style=ft.ButtonStyle(
                bgcolor={"": "#2563EB", "hovered": "#1E40AF"},
                color=ft.colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8),
                elevation={"": 0, "hovered": 2},
            ),
        )

        # Add period dialog
        self.period_dialog = ft.AlertDialog(
            title=ft.Text("Add Period"),
            content=ft.Container(
                width=400,
                height=400,
                content=ft.Column([
                    ft.TextField(
                        label="Period Number",
                        value="1",
                        keyboard_type=ft.KeyboardType.NUMBER
                    ),
                    ft.TextField(
                        label="Start Time (HH:MM)",
                        value="08:00",
                        hint_text="e.g., 08:00"
                    ),
                    ft.TextField(
                        label="End Time (HH:MM)",
                        value="08:40",
                        hint_text="e.g., 08:40"
                    ),
                    ft.Switch(label="Is Break Period", value=False),
                    ft.Dropdown(
                        label="Day",
                        options=[
                            ft.dropdown.Option("Monday"),
                            ft.dropdown.Option("Tuesday"),
                            ft.dropdown.Option("Wednesday"),
                            ft.dropdown.Option("Thursday"),
                            ft.dropdown.Option("Friday"),
                        ],
                        value="Monday"
                    ),
                ], spacing=10),
                padding=20
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self.close_period_dialog,
                              style=ft.ButtonStyle(color=ft.colors.GREY_600)),
                self._btn_save_period,
            ]
        )
        
        # --- Special Days ---
        self.special_days_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Date")),
                ft.DataColumn(ft.Text("Event")),
                ft.DataColumn(ft.Text("Type")),
                ft.DataColumn(ft.Text("Actions")),
            ],
            rows=[]
        )
        
        # Add special day dialog
        self._btn_save_special = ft.ElevatedButton(
            "Save",
            icon=ft.icons.SAVE_ROUNDED,
            on_click=self._save_special_animated,
            style=ft.ButtonStyle(
                bgcolor={"": "#2563EB", "hovered": "#1E40AF"},
                color=ft.colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8),
                elevation={"": 0, "hovered": 2},
            ),
        )
        self.special_dialog = ft.AlertDialog(
            title=ft.Text("Add Special Day"),
            content=ft.Container(
                width=400,
                height=300,
                content=ft.Column([
                    ft.TextField(
                        label="Date (YYYY-MM-DD)",
                        hint_text="e.g., 2025-12-25"
                    ),
                    ft.TextField(
                        label="Event Name",
                        hint_text="e.g., Christmas Day"
                    ),
                    ft.Dropdown(
                        label="Type",
                        options=[
                            ft.dropdown.Option("Holiday"),
                            ft.dropdown.Option("Event"),
                            ft.dropdown.Option("Exam"),
                            ft.dropdown.Option("Sports Day"),
                        ],
                        value="Holiday"
                    ),
                ], spacing=10),
                padding=20
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self.close_special_dialog,
                              style=ft.ButtonStyle(color=ft.colors.GREY_600)),
                self._btn_save_special,
            ]
        )
        
        self.all_periods = []
        self.all_special_days = []
        self.current_period = None
        self.current_special = None

        # Top-bar save icon button (animated)
        self._btn_save_all = ft.IconButton(
            icon=ft.icons.SAVE_ROUNDED,
            icon_color=ft.colors.WHITE, icon_size=18,
            tooltip="Save All",
            on_click=self._save_all_animated,
        )

        # "Set Term Dates" button (animated)
        self._btn_set_term = ft.ElevatedButton(
            "Set Term Dates",
            icon=ft.icons.CALENDAR_TODAY_ROUNDED,
            on_click=self._set_term_animated,
            style=ft.ButtonStyle(
                bgcolor={"": "#2563EB", "hovered": "#1E40AF"},
                color=ft.colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8),
                elevation={"": 0, "hovered": 2},
            ),
        )
        
        # Add dialogs to overlay
        if self.period_dialog not in self.page.overlay:
            self.page.overlay.append(self.period_dialog)
        if self.special_dialog not in self.page.overlay:
            self.page.overlay.append(self.special_dialog)
        
        self._ensure_tables()
        self._load_saved_settings()
        self.load_periods()
        self.load_special_days()
    
    def _build_card(self, title, icon, controls):
        """Helper to build a card with title and icon."""
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(icon, size=20, color="#2563EB"),
                    ft.Text(title, size=16, weight=ft.FontWeight.W_600,
                            color="#0F1E3A"),
                ], spacing=8),
                ft.Divider(height=8, color=ft.colors.GREY_200),
                *controls,
            ], spacing=14),
            padding=20,
            bgcolor=ft.colors.WHITE,
            border_radius=12,
            border=ft.border.all(1, ft.colors.GREY_200),
            shadow=ft.BoxShadow(
                spread_radius=0, blur_radius=8,
                color=ft.colors.with_opacity(0.06, ft.colors.BLACK),
                offset=ft.Offset(0, 2)),
            margin=ft.margin.only(bottom=16),
        )
    

    # ══════════════════════════════════════════════════════════════════════
    # DB HELPERS
    # ══════════════════════════════════════════════════════════════════════
    def _db(self, sql, params=()):
        return self.app.local_db.execute(sql, params)

    def _get(self, key, default=''):
        try:
            rows = self._db("SELECT value FROM app_settings WHERE key=?", (key,))
            return rows[0]['value'] if rows else default
        except Exception:
            return default

    def _set(self, key, value):
        try:
            self._db(
                "INSERT INTO app_settings (key,value) VALUES (?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)))
        except Exception as ex:
            print(f"[calendar] _set error: {ex}")

    def _ensure_tables(self):
        """Make sure periods and special_days tables exist."""
        try:
            self._db("""
                CREATE TABLE IF NOT EXISTS periods (
                    id          TEXT PRIMARY KEY,
                    school_id   TEXT DEFAULT 'default',
                    day_of_week TEXT,
                    period_number INTEGER,
                    start_time  TEXT,
                    end_time    TEXT,
                    is_break    INTEGER DEFAULT 0
                )
            """)
            self._db("""
                CREATE TABLE IF NOT EXISTS special_days (
                    id         TEXT PRIMARY KEY,
                    date       TEXT,
                    event      TEXT,
                    type       TEXT DEFAULT 'Holiday',
                    created_at TEXT
                )
            """)
            # Migration: add created_at to existing special_days tables that
            # were created before this column existed — safe to call every time.
            try:
                self._db("ALTER TABLE special_days ADD COLUMN created_at TEXT")
            except Exception:
                pass  # Column already exists — that's fine
            self._db("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY, value TEXT
                )
            """)
        except Exception as ex:
            print(f"[calendar] _ensure_tables: {ex}")

    def _load_saved_settings(self):
        """Restore term config and school days from app_settings.
        calendar_* keys take priority; fall back to shared term/academic_year
        keys written by settings_view so both screens stay in sync."""
        try:
            # Use calendar-specific keys first, fall back to shared settings keys
            term  = self._get('calendar_term', None) or self._get('term', 'First Term')
            year  = self._get('calendar_year', None) or self._get('academic_year', '2025/2026')
            start = self._get('calendar_term_start', '2025-09-15')
            end   = self._get('calendar_term_end',   '2025-12-15')
            self.term_dropdown.value  = term
            self.academic_year.value  = year
            self.term_start.value     = start
            self.term_end.value       = end
        except Exception as ex:
            print(f"[calendar] _load_saved_settings term: {ex}")

        try:
            saved_days = self._get('calendar_school_days', '')
            if saved_days:
                active = [d.strip() for d in saved_days.split(',') if d.strip()]
                for day, cb in self.selected_days.items():
                    cb.value = (day in active)
        except Exception as ex:
            print(f"[calendar] _load_saved_settings days: {ex}")

    def build(self):
        """Build the calendar view."""
        return ft.View(
            "/calendar",
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
                        ft.Text("Academic Calendar", size=17,
                                weight=ft.FontWeight.BOLD,
                                color=ft.colors.WHITE),
                        ft.Container(expand=True),
                        self._btn_save_all,
                    ], spacing=6,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor="#0F1E3A",
                    padding=ft.padding.symmetric(horizontal=16, vertical=10),
                    height=56,
                ),
                ft.Container(
                    content=ft.ListView(
                        controls=[
                            # Term Configuration Card
                            self._build_card("Term Configuration", ft.icons.CALENDAR_MONTH, [
                                ft.Row([self.term_dropdown, self.academic_year], spacing=10),
                                ft.Row([self.term_start, self.term_end,
                                        self._btn_set_term], spacing=10),
                            ]),
                            # School Days Card
                            self._build_card("School Days", ft.icons.TODAY, [
                                ft.Row([self.selected_days[day] for day in self.days], wrap=True),
                            ]),
                            # Periods Card
                            self._build_card("Daily Periods", ft.icons.ACCESS_TIME, [
                                ft.Row([
                                    ft.Text(f"Total: {len(self.all_periods)}",
                                            size=14, color=ft.colors.GREY_600),
                                    ft.ElevatedButton(
                                        "+ Add Period",
                                        on_click=self.open_add_period_dialog,
                                        style=ft.ButtonStyle(
                                            bgcolor={"": "#2563EB", "hovered": "#1E40AF"},
                                            color=ft.colors.WHITE,
                                            shape=ft.RoundedRectangleBorder(radius=8),
                                            elevation={"": 0, "hovered": 2},
                                        ),
                                    ),
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Container(
                                    content=ft.Column([self.periods_table],
                                                      scroll=ft.ScrollMode.AUTO),
                                    height=300,
                                    border=ft.border.all(1, ft.colors.GREY_200),
                                    border_radius=8, padding=10,
                                ),
                            ]),
                            # Special Days Card
                            self._build_card("Special Days & Holidays", ft.icons.STAR, [
                                ft.Row([
                                    ft.ElevatedButton(
                                        "+ Add Event",
                                        on_click=self.open_add_special_dialog,
                                        style=ft.ButtonStyle(
                                            bgcolor={"": "#2563EB", "hovered": "#1E40AF"},
                                            color=ft.colors.WHITE,
                                            shape=ft.RoundedRectangleBorder(radius=8),
                                            elevation={"": 0, "hovered": 2},
                                        ),
                                    ),
                                ], alignment=ft.MainAxisAlignment.END),
                                ft.Container(
                                    content=ft.Column([self.special_days_table],
                                                      scroll=ft.ScrollMode.AUTO),
                                    height=200,
                                    border=ft.border.all(1, ft.colors.GREY_200),
                                    border_radius=8, padding=10,
                                ),
                            ]),
                        ],
                        padding=20,
                        expand=True,
                    ),
                    expand=True,
                    bgcolor="#F8FAFC",
                )
            ],
            padding=0,
            spacing=0,
        )
    
    # --------------------------------------------------------------------------
    # All existing data methods (keep as originally provided)
    # --------------------------------------------------------------------------
    def load_periods(self):
        try:
            periods = self.app.local_db.execute(
                "SELECT * FROM periods ORDER BY day_of_week, period_number"
            )
            if not periods:
                # Seed defaults into DB so they survive restarts
                self._seed_default_periods()
                periods = self.app.local_db.execute(
                    "SELECT * FROM periods ORDER BY day_of_week, period_number"
                ) or []
            self.all_periods = periods
            self.display_periods()
            print(f"Loaded {len(self.all_periods)} periods")
        except Exception as e:
            print(f"Error loading periods: {e}")
            traceback.print_exc()
            self.all_periods = self._get_default_periods()
    
    def _get_default_periods(self):
        default_periods = []
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        periods = [
            (1, "08:00", "08:40", False),
            (2, "08:40", "09:20", False),
            (3, "09:20", "10:00", False),
            (4, "10:00", "10:20", True),
            (5, "10:20", "11:00", False),
            (6, "11:00", "11:40", False),
            (7, "11:40", "12:20", True),
            (8, "12:20", "13:00", False),
            (9, "13:00", "13:40", False),
            (10, "13:40", "14:20", False),
        ]
        for day in days:
            for num, start, end, is_break in periods:
                default_periods.append({
                    'period_number': num,
                    'start_time': start,
                    'end_time': end,
                    'is_break': 1 if is_break else 0,
                    'day_of_week': day
                })
        return default_periods
    

    def _seed_default_periods(self):
        """Insert default periods into the DB (only called when table is empty)."""
        import uuid as _uuid
        defaults = self._get_default_periods()
        for p in defaults:
            p['id'] = str(_uuid.uuid4())
            p['school_id'] = 'default'
            try:
                self.app.local_db.insert("periods", p)
            except Exception as ex:
                print(f"[calendar] seed period error: {ex}")

    def display_periods(self):
        rows = []
        for day in self.days:
            day_periods = [p for p in self.all_periods if p.get('day_of_week') == day]
            day_periods.sort(key=lambda x: x.get('period_number', 0))
            for period in day_periods:
                is_break = period.get('is_break', 0)
                if isinstance(is_break, str):
                    is_break = int(is_break) if is_break.isdigit() else 0
                rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(f"Period {period.get('period_number', '')}")),
                            ft.DataCell(ft.Text(period.get('start_time', ''))),
                            ft.DataCell(ft.Text(period.get('end_time', ''))),
                            ft.DataCell(
                                ft.Container(
                                    content=ft.Text(
                                        "Break" if is_break else "Teaching",
                                        size=12,
                                        color=ft.colors.WHITE
                                    ),
                                    padding=ft.padding.symmetric(horizontal=5, vertical=2),
                                    border_radius=10,
                                    bgcolor="#D97706" if is_break else "#16A34A"
                                )
                            ),
                            ft.DataCell(
                                ft.Row([
                                    ft.IconButton(
                                        icon=ft.icons.EDIT,
                                        icon_size=20,
                                        on_click=lambda e, p=period: self.open_edit_period_dialog(p)
                                    ),
                                    ft.IconButton(
                                        icon=ft.icons.DELETE,
                                        icon_size=20,
                                        on_click=lambda e, p=period: self.delete_period(p)
                                    ),
                                ])
                            ),
                        ]
                    )
                )
            if day_periods:
                rows.append(ft.DataRow(cells=[ft.DataCell(ft.Container(height=5))] * 5))
        self.periods_table.rows = rows
        try:
            self.page.update()
        except Exception: pass
    
    def load_special_days(self):
        try:
            self._ensure_tables()
            special = self.app.local_db.execute(
                "SELECT * FROM special_days ORDER BY date") or []

            # Only seed defaults when the table has NEVER had any rows AND
            # no user has manually cleared it.  We track this with a settings key.
            if not special and not self._get('special_days_seeded', ''):
                self._seed_default_special_days()
                self._set('special_days_seeded', '1')
                special = self.app.local_db.execute(
                    "SELECT * FROM special_days ORDER BY date") or []

            self.all_special_days = list(special)
            self.display_special_days()
        except Exception as ex:
            print(f"Error loading special days: {ex}")
            traceback.print_exc()
            self.all_special_days = []
            self.display_special_days()
    
    def _get_default_special_days(self):
        return [
            {"date": "2025-10-01", "event": "Independence Day", "type": "Holiday"},
            {"date": "2025-12-25", "event": "Christmas Day", "type": "Holiday"},
            {"date": "2025-12-26", "event": "Boxing Day", "type": "Holiday"},
            {"date": "2026-01-01", "event": "New Year's Day", "type": "Holiday"},
            {"date": "2026-03-17", "event": "Sports Day", "type": "Event"},
        ]
    

    def _seed_default_special_days(self):
        """Insert default special days into the DB (only called when table is empty)."""
        import uuid as _uuid
        for s in self._get_default_special_days():
            s['id'] = str(_uuid.uuid4())
            try:
                self.app.local_db.insert("special_days", s)
            except Exception as ex:
                print(f"[calendar] seed special_day error: {ex}")

    def display_special_days(self):
        rows = []
        for day in self.all_special_days:
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(day.get('date', ''))),
                        ft.DataCell(ft.Text(day.get('event', ''))),
                        ft.DataCell(
                            ft.Container(
                                content=ft.Text(
                                    day.get('type', ''),
                                    size=12,
                                    color=ft.colors.WHITE
                                ),
                                padding=ft.padding.symmetric(horizontal=5, vertical=2),
                                border_radius=10,
                                bgcolor="#7C3AED" if day.get('type') == "Holiday" else "#2563EB"
                            )
                        ),
                        ft.DataCell(
                            ft.Row([
                                ft.IconButton(
                                    icon=ft.icons.EDIT,
                                    icon_size=20,
                                    on_click=lambda e, d=day: self.open_edit_special_dialog(d)
                                ),
                                ft.IconButton(
                                    icon=ft.icons.DELETE,
                                    icon_size=20,
                                    on_click=lambda e, d=day: self.delete_special_day(d)
                                ),
                            ])
                        ),
                    ]
                )
            )
        self.special_days_table.rows = rows
        try:
            self.page.update()
        except Exception: pass
    
    def open_add_period_dialog(self, e):
        self.period_dialog.title = ft.Text("Add Period")
        self.current_period = None
        content = self.period_dialog.content.content
        content.controls[0].value = "1"
        content.controls[1].value = "08:00"
        content.controls[2].value = "08:40"
        content.controls[3].value = False
        content.controls[4].value = "Monday"
        self.period_dialog.open = True
        self.page.update()
    
    def open_edit_period_dialog(self, period):
        self.period_dialog.title = ft.Text("Edit Period")
        self.current_period = period
        content = self.period_dialog.content.content
        content.controls[0].value = str(period.get('period_number', 1))
        content.controls[1].value = period.get('start_time', '08:00')
        content.controls[2].value = period.get('end_time', '08:40')
        is_break = period.get('is_break', 0)
        if isinstance(is_break, str):
            is_break = int(is_break) if is_break.isdigit() else 0
        content.controls[3].value = bool(is_break)
        content.controls[4].value = period.get('day_of_week', 'Monday')
        self.period_dialog.open = True
        self.page.update()
    
    # ══════════════════════════════════════════════════════════════════════
    # BUTTON ANIMATION HELPERS
    # ══════════════════════════════════════════════════════════════════════
    async def _animate_elevated_btn(self, btn, save_fn, e):
        """Animate an ElevatedButton: spinner → save logic → success → reset."""
        import asyncio
        orig_text  = btn.text
        orig_icon  = btn.icon
        # ── Saving state ──────────────────────────────────────────────
        btn.text     = "Saving..."
        btn.icon     = ft.icons.HOURGLASS_TOP_ROUNDED
        btn.disabled = True
        btn.style.bgcolor = {"": "#64748B", "hovered": "#475569"}
        self.page.update()
        await asyncio.sleep(0.15)
        # ── Run actual logic ──────────────────────────────────────────
        save_fn(e)
        # ── Success state ─────────────────────────────────────────────
        btn.text     = "Saved ✓"
        btn.icon     = ft.icons.CHECK_CIRCLE_ROUNDED
        btn.disabled = False
        btn.style.bgcolor = {"": "#16A34A", "hovered": "#15803D"}
        self.page.update()
        await asyncio.sleep(1.4)
        # ── Reset ─────────────────────────────────────────────────────
        btn.text     = orig_text
        btn.icon     = orig_icon
        btn.style.bgcolor = {"": "#2563EB", "hovered": "#1E40AF"}
        self.page.update()

    async def _animate_icon_btn(self, btn, save_fn, e):
        """Animate an IconButton in the top bar."""
        import asyncio
        btn.icon       = ft.icons.HOURGLASS_TOP_ROUNDED
        btn.icon_color = ft.colors.YELLOW_200
        btn.disabled   = True
        self.page.update()
        await asyncio.sleep(0.15)
        save_fn(e)
        btn.icon       = ft.icons.CHECK_CIRCLE_ROUNDED
        btn.icon_color = "#4ADE80"
        btn.disabled   = False
        self.page.update()
        await asyncio.sleep(1.4)
        btn.icon       = ft.icons.SAVE_ROUNDED
        btn.icon_color = ft.colors.WHITE
        self.page.update()

    async def _save_period_animated(self, e):
        await self._animate_elevated_btn(self._btn_save_period, self.save_period, e)

    async def _save_special_animated(self, e):
        await self._animate_elevated_btn(self._btn_save_special, self.save_special_day, e)

    async def _set_term_animated(self, e):
        await self._animate_elevated_btn(self._btn_set_term, self.set_term_dates, e)

    async def _save_all_animated(self, e):
        await self._animate_icon_btn(self._btn_save_all, self.save_all, e)

    def save_period(self, e):
        content = self.period_dialog.content.content
        period_data = {
            'period_number': int(content.controls[0].value) if content.controls[0].value else 1,
            'start_time': content.controls[1].value,
            'end_time': content.controls[2].value,
            'is_break': 1 if content.controls[3].value else 0,
            'day_of_week': content.controls[4].value
        }
        try:
            if ':' not in period_data['start_time'] or ':' not in period_data['end_time']:
                raise ValueError("Invalid time format")
        except:
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Invalid time format! Use HH:MM"), bgcolor=ft.colors.RED))
            return
        try:
            if self.current_period and self.current_period.get('id'):
                self.app.local_db.update("periods", self.current_period['id'], period_data)
            else:
                period_data['id'] = str(uuid.uuid4())
                period_data['school_id'] = "default"
                self.app.local_db.insert("periods", period_data)
                self.all_periods.append(period_data)
            self.close_period_dialog(None)
            self.load_periods()
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Period saved successfully!")))
        except Exception as e:
            print(f"Error saving period: {e}")
            traceback.print_exc()
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text(f"Error: {str(e)}"), bgcolor=ft.colors.RED))
    
    def delete_period(self, period):
        def confirm_delete(e):
            try:
                if period.get('id'):
                    self.app.local_db.delete("periods", period['id'])
                if period in self.all_periods:
                    self.all_periods.remove(period)
                dialog.open = False
                self.load_periods()
                self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Period deleted!")))
                self.page.update()
            except Exception as ex:
                print(f"Error deleting period: {ex}")
        dialog = ft.AlertDialog(
            title=ft.Text("Confirm Delete"),
            content=ft.Text(f"Delete Period {period.get('period_number')} on {period.get('day_of_week')}?"),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: setattr(dialog, 'open', False)),
                ft.ElevatedButton("Delete", on_click=confirm_delete, color=ft.colors.RED),
            ]
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()
    
    def open_add_special_dialog(self, e):
        self.special_dialog.title = ft.Text("Add Special Day")
        self.current_special = None
        content = self.special_dialog.content.content
        content.controls[0].value = ""
        content.controls[1].value = ""
        content.controls[2].value = "Holiday"
        self.special_dialog.open = True
        self.page.update()
    
    def open_edit_special_dialog(self, special):
        self.special_dialog.title = ft.Text("Edit Special Day")
        self.current_special = special
        content = self.special_dialog.content.content
        content.controls[0].value = special.get('date', '')
        content.controls[1].value = special.get('event', '')
        content.controls[2].value = special.get('type', 'Holiday')
        self.special_dialog.open = True
        self.page.update()
    
    def save_special_day(self, e):
        content = self.special_dialog.content.content
        special_data = {
            'date':  content.controls[0].value.strip(),
            'event': content.controls[1].value.strip(),
            'type':  content.controls[2].value or 'Holiday',
        }
        if not special_data['date'] or not special_data['event']:
            self.page.show_snack_bar(ft.SnackBar(
                content=ft.Text("Date and event name are required!"),
                bgcolor=ft.colors.RED))
            return

        # Basic date format guard
        import re
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', special_data['date']):
            self.page.show_snack_bar(ft.SnackBar(
                content=ft.Text("Date must be in YYYY-MM-DD format."),
                bgcolor=ft.colors.RED))
            return

        try:
            # Ensure the table exists (safe to call repeatedly)
            self._ensure_tables()

            if self.current_special and self.current_special.get('id'):
                # UPDATE existing row
                self.app.local_db.update(
                    "special_days", self.current_special['id'], special_data)
            else:
                # INSERT new row — always generate a fresh id
                special_data['id'] = str(uuid.uuid4())
                self.app.local_db.insert("special_days", special_data)

            self.close_special_dialog(None)
            # Reload directly from the DB so the table always reflects reality
            self.load_special_days()
            self.page.show_snack_bar(ft.SnackBar(
                content=ft.Text("Event saved successfully! ✓"),
                bgcolor=ft.colors.GREEN))
        except Exception as ex:
            print(f"Error saving special day: {ex}")
            traceback.print_exc()
            self.page.show_snack_bar(ft.SnackBar(
                content=ft.Text(f"Save failed: {ex}"),
                bgcolor=ft.colors.RED))
    
    def delete_special_day(self, special):
        def confirm_delete(e):
            dlg.open = False
            self.page.update()
            try:
                if special.get('id'):
                    self.app.local_db.delete("special_days", special['id'])
                self.load_special_days()
                self.page.show_snack_bar(ft.SnackBar(
                    content=ft.Text("Event deleted."),
                    bgcolor=ft.colors.GREEN))
            except Exception as ex:
                print(f"Error deleting special day: {ex}")
                traceback.print_exc()
                self.page.show_snack_bar(ft.SnackBar(
                    content=ft.Text(f"Delete failed: {ex}"),
                    bgcolor=ft.colors.RED))

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Delete Event", color=ft.colors.RED_700),
            content=ft.Text(
                f"Delete \"{special.get('event', '')}\" on {special.get('date', '')}?"),
            actions=[
                ft.TextButton("Cancel",
                    on_click=lambda e: [setattr(dlg, 'open', False), self.page.update()]),
                ft.ElevatedButton("Delete", on_click=confirm_delete,
                    style=ft.ButtonStyle(
                        bgcolor=ft.colors.RED_700, color=ft.colors.WHITE)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        if dlg not in self.page.overlay:
            self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()
    
    def set_term_dates(self, e):
        start = self.term_start.value.strip()
        end   = self.term_end.value.strip()
        term  = self.term_dropdown.value or "First Term"
        year  = self.academic_year.value.strip()
        # Basic date format validation
        import re
        date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        if not date_re.match(start) or not date_re.match(end):
            self.page.show_snack_bar(ft.SnackBar(
                content=ft.Text("Use YYYY-MM-DD format for dates."),
                bgcolor=ft.colors.RED))
            return
        self._set("calendar_term",       term)
        self._set("calendar_year",       year)
        self._set("calendar_term_start", start)
        self._set("calendar_term_end",   end)
        # Mirror into shared keys used by timetable generator AND settings screen
        self._set("term",          term)
        self._set("academic_year", year)
        self.page.show_snack_bar(ft.SnackBar(
            content=ft.Text(f"Term dates saved — {term}  ·  {year}"),
            bgcolor=ft.colors.GREEN))
    
    def save_all(self, e):
        term = self.term_dropdown.value or "First Term"
        year = self.academic_year.value.strip()
        # Save calendar-specific keys
        self._set("calendar_term",       term)
        self._set("calendar_year",       year)
        self._set("calendar_term_start", self.term_start.value.strip())
        self._set("calendar_term_end",   self.term_end.value.strip())
        # Mirror into shared keys so settings screen and timetable generator stay in sync
        self._set("term",          term)
        self._set("academic_year", year)
        # Save school days as comma-separated list
        active_days = [day for day, cb in self.selected_days.items() if cb.value]
        self._set("calendar_school_days", ",".join(active_days))
        self.page.show_snack_bar(ft.SnackBar(
            content=ft.Text("All calendar settings saved ✓"),
            bgcolor=ft.colors.GREEN))
    
    def close_period_dialog(self, e):
        self.period_dialog.open = False
        self.page.update()
    
    def close_special_dialog(self, e):
        self.special_dialog.open = False
        self.page.update()