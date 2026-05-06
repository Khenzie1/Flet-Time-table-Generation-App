"""Reports view - Real data from DB, polished UI consistent with app theme."""
import flet as ft
import traceback
import threading


class ReportsView:
    """Reports screen with modern card layout."""

    def __init__(self, app):
        self.app = app
        self.page = app.page

        self.report_type = ft.Dropdown(
            label="Report Type",
            options=[
                ft.dropdown.Option("Teacher Workload"),
                ft.dropdown.Option("Room Utilization"),
                ft.dropdown.Option("Subject Distribution"),
                ft.dropdown.Option("Class Coverage"),
            ],
            value="Teacher Workload",
            width=300,
            border_radius=8,
            dense=True,
        )

        self.generate_btn = ft.ElevatedButton(
            "Generate Report",
            icon=ft.icons.ANALYTICS_ROUNDED,
            on_click=self.generate_report,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                bgcolor={"": "#2563EB", "hovered": "#1E40AF"},
                color=ft.colors.WHITE,
                elevation={"": 0, "hovered": 2},
            ),
        )

        self.report_area = ft.Column([], spacing=16)

    # ------------------------------------------------------------------ #
    #  BUILD                                                               #
    # ------------------------------------------------------------------ #
    def build(self):
        return ft.View(
            "/reports",
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
                        ft.Icon(ft.icons.ANALYTICS_ROUNDED,
                                color=ft.colors.WHITE, size=20),
                        ft.Text("Reports & Analytics", size=17,
                                weight=ft.FontWeight.BOLD,
                                color=ft.colors.WHITE),
                        ft.Container(expand=True),
                    ], spacing=6,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor="#0F1E3A",
                    padding=ft.padding.symmetric(horizontal=16, vertical=10),
                    height=56,
                ),
                ft.Container(
                    content=ft.Column([
                        # ── Controls card ──────────────────────────────
                        ft.Container(
                            content=ft.Column([
                                ft.Text(
                                    "Analytics Dashboard",
                                    size=20,
                                    weight=ft.FontWeight.BOLD,
                                    color="#0F1E3A",
                                ),
                                ft.Text(
                                    "Select a report type and click Generate.",
                                    size=13,
                                    color=ft.colors.GREY_500,
                                ),
                                ft.Row([
                                    self.report_type,
                                    self.generate_btn,
                                ], spacing=12),
                            ], spacing=8),
                            padding=20,
                            bgcolor=ft.colors.WHITE,
                            border_radius=12,
                            shadow=ft.BoxShadow(
                                spread_radius=0, blur_radius=6,
                                color=ft.colors.with_opacity(0.08, ft.colors.BLACK),
                            ),
                        ),
                        # ── Report output ──────────────────────────────
                        self.report_area,
                    ], spacing=16),
                    padding=20,
                    bgcolor="#F8FAFC",
                ),
            ],
            padding=0,
            spacing=0,
            scroll=ft.ScrollMode.ALWAYS,
        )

    # ------------------------------------------------------------------ #
    #  DATA HELPERS                                                        #
    # ------------------------------------------------------------------ #
    def _fetch(self, sql, params=()):
        try:
            result = self.app.local_db.execute(sql, params)
            return result if result else []
        except Exception as ex:
            print(f"[ReportsView] DB error: {ex}")
            traceback.print_exc()
            return []

    def _latest_timetable_id(self):
        """Return the id of the most recently published Class Timetable."""
        rows = self._fetch(
            "SELECT id FROM timetables "
            "WHERE status='Published' AND type='Class Timetable' "
            "ORDER BY rowid DESC LIMIT 1"
        )
        if rows:
            return rows[0]['id']
        # Fall back to any timetable if no published one exists
        rows = self._fetch(
            "SELECT id FROM timetables "
            "WHERE type='Class Timetable' "
            "ORDER BY rowid DESC LIMIT 1"
        )
        return rows[0]['id'] if rows else None

    def _load_teacher_data(self):
        """
        Count actual periods each teacher has in the generated timetable,
        not just what was assigned in class_subjects.
        """
        tid = self._latest_timetable_id()
        if not tid:
            return []
        return self._fetch("""
            SELECT
                t.teacher_code          AS code,
                t.full_name             AS name,
                t.max_daily_periods     AS max_periods,
                COUNT(DISTINCT ts.id)                   AS periods_placed,
                COUNT(DISTINCT ts.class_id)             AS classes_count,
                COUNT(DISTINCT ts.subject_id)           AS subjects_count
            FROM teachers t
            LEFT JOIN timetable_slots ts
                   ON ts.teacher_id   = t.id
                  AND ts.timetable_id = ?
            WHERE t.is_active = 1
            GROUP BY t.id
            ORDER BY periods_placed DESC
        """, (tid,))

    def _load_room_data(self):
        """
        Count slots actually used per room in the generated timetable.
        """
        tid = self._latest_timetable_id()
        if not tid:
            return self._fetch("""
                SELECT r.room_code AS code, r.room_name AS name,
                       r.room_type AS type, r.capacity,
                       0 AS slots_used
                FROM rooms r
            """)
        return self._fetch("""
            SELECT
                r.room_code  AS code,
                r.room_name  AS name,
                r.room_type  AS type,
                r.capacity   AS capacity,
                COUNT(ts.id) AS slots_used
            FROM rooms r
            LEFT JOIN timetable_slots ts
                   ON ts.room_id      = r.id
                  AND ts.timetable_id = ?
            GROUP BY r.id
            ORDER BY slots_used DESC
        """, (tid,))

    def _load_subject_data(self):
        """
        Count how many times each subject was actually placed in the
        timetable, and how many distinct classes it appears in.
        """
        tid = self._latest_timetable_id()
        if not tid:
            return []
        return self._fetch("""
            SELECT
                s.code,
                s.name,
                CASE
                    WHEN LOWER(TRIM(s.category)) = 'core'      THEN 'Core'
                    WHEN LOWER(TRIM(s.category)) = 'elective'  THEN 'Elective'
                    WHEN LOWER(TRIM(s.category)) = 'practical' THEN 'Practical'
                    ELSE 'Other'
                END AS category,
                s.periods_per_week,
                COUNT(DISTINCT ts.class_id) AS classes_count,
                COUNT(ts.id)               AS total_periods_placed
            FROM subjects s
            LEFT JOIN timetable_slots ts
                   ON ts.subject_id   = s.id
                  AND ts.timetable_id = ?
            GROUP BY s.id
            ORDER BY classes_count DESC
        """, (tid,))

    def _load_class_data(self):
        """
        Count how many distinct subjects were actually placed per class
        in the timetable, and total periods placed.
        """
        tid = self._latest_timetable_id()
        if not tid:
            return []
        return self._fetch("""
            SELECT
                c.class_name    AS name,
                c.level,
                c.student_count AS students,
                COUNT(DISTINCT ts.subject_id) AS subjects_placed,
                COUNT(ts.id)                  AS periods_placed
            FROM classes c
            LEFT JOIN timetable_slots ts
                   ON ts.class_id     = c.id
                  AND ts.timetable_id = ?
            GROUP BY c.id
            ORDER BY c.level, c.class_name
        """, (tid,))

    # ------------------------------------------------------------------ #
    #  GENERATE                                                            #
    # ------------------------------------------------------------------ #
    def generate_report(self, e):
        """Animate the button for 1.5 s then render the report."""
        # ── Loading state ─────────────────────────────────────────────
        self.generate_btn.disabled = True
        self.generate_btn.icon     = ft.icons.HOURGLASS_TOP_ROUNDED
        self.generate_btn.text     = "Generating…"
        self.report_area.controls.clear()
        # Show a progress bar while loading
        self._loading_bar = ft.ProgressBar(width=400, color="#2563EB", bgcolor="#E2E8F0")
        self.report_area.controls.append(
            ft.Container(
                content=ft.Column([
                    ft.Text("Generating report…", size=13, color=ft.colors.GREY_500),
                    self._loading_bar,
                ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                alignment=ft.alignment.center,
                padding=40,
            )
        )
        self.page.update()

        def _do():
            import time
            time.sleep(1.5)   # let the animation breathe
            # ── Build the report ──────────────────────────────────────
            try:
                report_type = self.report_type.value
                if report_type == "Teacher Workload":
                    widgets = self._build_teacher_report()
                elif report_type == "Room Utilization":
                    widgets = self._build_room_report()
                elif report_type == "Subject Distribution":
                    widgets = self._build_subject_report()
                else:
                    widgets = self._build_class_report()
            except Exception as ex:
                traceback.print_exc()
                widgets = [
                    self._card(ft.Text(f"Error generating report: {ex}",
                                       color=ft.colors.RED))
                ]
            # ── Restore button & show results ─────────────────────────
            self.generate_btn.disabled = False
            self.generate_btn.icon     = ft.icons.ANALYTICS_ROUNDED
            self.generate_btn.text     = "Generate Report"
            self.report_area.controls.clear()
            self.report_area.controls.extend(widgets)
            self.page.update()

        threading.Thread(target=_do, daemon=True).start()

    # ------------------------------------------------------------------ #
    #  UI HELPERS                                                          #
    # ------------------------------------------------------------------ #
    def _card(self, content, padding=20):
        return ft.Container(
            content=content,
            padding=padding,
            bgcolor=ft.colors.WHITE,
            border_radius=12,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=6,
                color=ft.colors.with_opacity(0.08, ft.colors.BLACK),
            ),
        )

    def _stat_chip(self, label, value, icon, color):
        """Fixed-width stat chip. No expand=True — avoids collapse in scrollable views."""
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(icon, color=ft.colors.WHITE, size=18),
                    width=36, height=36,
                    bgcolor=color,
                    border_radius=8,
                    alignment=ft.alignment.center,
                ),
                ft.Column([
                    ft.Text(str(value), size=20, weight=ft.FontWeight.BOLD, color=color),
                    ft.Text(label, size=11, color=ft.colors.GREY_600),
                ], spacing=0, tight=True),
            ], spacing=10),
            padding=ft.padding.symmetric(horizontal=14, vertical=10),
            bgcolor=ft.colors.WHITE,
            border_radius=10,
            border=ft.border.all(1, ft.colors.with_opacity(0.2, color)),
            width=210,
        )

    def _section_title(self, title, subtitle=""):
        return ft.Column([
            ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color="#0F1E3A"),
            ft.Text(subtitle, size=12, color=ft.colors.GREY_500) if subtitle else ft.Container(height=0),
        ], spacing=2)

    def _category_badge(self, text, color):
        return ft.Container(
            content=ft.Text(text, size=11, color=ft.colors.WHITE, weight=ft.FontWeight.BOLD),
            padding=ft.padding.symmetric(horizontal=8, vertical=3),
            border_radius=20,
            bgcolor=color,
        )

    def _no_data(self, msg="No data found in database."):
        return [self._card(ft.Row([
            ft.Icon(ft.icons.INFO_OUTLINE, color=ft.colors.GREY_400),
            ft.Text(msg, size=14, color=ft.colors.GREY_500),
        ], spacing=10))]

    # ------------------------------------------------------------------ #
    #  TEACHER WORKLOAD                                                    #
    # ------------------------------------------------------------------ #
    def _build_teacher_report(self):
        tid = self._latest_timetable_id()
        if not tid:
            return self._no_data(
                "No timetable generated yet. Generate a class timetable "
                "first, then re-run this report.")

        data = self._load_teacher_data()
        if not data:
            return self._no_data("No active teachers found in database.")

        # Only count teachers who actually appear in the timetable
        active = [r for r in data if r.get('periods_placed', 0) > 0]
        total  = len(data)
        avg_periods = round(
            sum(r.get('periods_placed', 0) for r in active) / len(active), 1
        ) if active else 0
        overloaded = sum(
            1 for r in active
            if r.get('max_periods') and
            r.get('periods_placed', 0) > r['max_periods'] * 5
        )

        summary_row = ft.Row([
            self._stat_chip("Total Teachers", total,
                            ft.icons.PEOPLE, "#2563EB"),
            self._stat_chip("Teaching in Timetable", len(active),
                            ft.icons.ASSIGNMENT_IND, "#16A34A"),
            self._stat_chip("Avg Periods/Week", avg_periods,
                            ft.icons.AUTO_GRAPH, "#D97706"),
            self._stat_chip("Over Capacity", overloaded,
                            ft.icons.WARNING_ROUNDED, "#DC2626"),
        ], spacing=12, wrap=True)

        max_placed = max(
            (r.get('periods_placed', 0) for r in data), default=1) or 1

        rows = []
        for t in data:
            placed   = t.get('periods_placed', 0)
            classes  = t.get('classes_count', 0)
            subjects = t.get('subjects_count', 0)
            max_p    = t.get('max_periods') or 6
            max_weekly = max_p * 5
            pct = (placed / max_weekly * 100) if max_weekly else 0

            color = ("#64748B" if placed == 0 else
                     "#16A34A" if pct < 70 else
                     "#D97706" if pct < 100 else "#DC2626")

            rows.append(ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(t.get('name', ''), size=13,
                                weight=ft.FontWeight.W_500),
                        ft.Row([
                            ft.Text(t.get('code', ''), size=11,
                                    color=ft.colors.GREY_500),
                            self._category_badge(
                                "No slots" if placed == 0 else f"{pct:.0f}%",
                                color),
                        ], spacing=6),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.ProgressBar(
                        value=min(placed / max_placed, 1.0),
                        color=color,
                        bgcolor=ft.colors.GREY_100,
                        height=10,
                    ),
                    ft.Row([
                        ft.Text(
                            f"{placed} periods placed  ·  "
                            f"{classes} class(es)  ·  {subjects} subject(s)",
                            size=11, color=ft.colors.GREY_500),
                        ft.Text(
                            f"Capacity: {max_p}/day × 5 = {max_weekly}/week",
                            size=11, color=ft.colors.GREY_400),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ], spacing=5),
                padding=ft.padding.symmetric(vertical=10, horizontal=4),
                border=ft.border.only(
                    bottom=ft.BorderSide(1, ft.colors.GREY_100)),
            ))

        legend = ft.Row([
            ft.Row([ft.Container(width=12, height=12,
                                 bgcolor="#16A34A", border_radius=2),
                    ft.Text("< 70%  Normal", size=11,
                            color=ft.colors.GREY_600)], spacing=4),
            ft.Row([ft.Container(width=12, height=12,
                                 bgcolor="#D97706", border_radius=2),
                    ft.Text("70–99%  High", size=11,
                            color=ft.colors.GREY_600)], spacing=4),
            ft.Row([ft.Container(width=12, height=12,
                                 bgcolor="#DC2626", border_radius=2),
                    ft.Text("≥ 100%  Over Capacity", size=11,
                            color=ft.colors.GREY_600)], spacing=4),
            ft.Row([ft.Container(width=12, height=12,
                                 bgcolor="#64748B", border_radius=2),
                    ft.Text("No slots — not in timetable", size=11,
                            color=ft.colors.GREY_600)], spacing=4),
        ], spacing=20, wrap=True)

        return [
            self._card(summary_row, padding=16),
            self._card(ft.Column([
                self._section_title(
                    "Teacher Workload Breakdown",
                    "Periods actually placed in the generated timetable "
                    "vs weekly capacity (max_daily_periods × 5 days)"),
                ft.Divider(height=12),
                ft.Column(rows, spacing=0),
                ft.Divider(height=12),
                legend,
            ], spacing=8)),
        ]

    # ------------------------------------------------------------------ #
    #  ROOM UTILIZATION                                                    #
    # ------------------------------------------------------------------ #
    def _build_room_report(self):
        data = self._load_room_data()
        if not data:
            return self._no_data("No rooms found in database.")

        total_rooms = len(data)
        total_slots = sum(r.get('slots_used', 0) for r in data)
        max_slots   = max((r.get('slots_used', 0) for r in data), default=1) or 1

        # If nothing has been generated yet warn the user clearly
        if total_slots == 0:
            return [
                self._card(ft.Row([
                    ft.Icon(ft.icons.INFO_OUTLINE, color="#2563EB"),
                    ft.Column([
                        ft.Text("No timetable generated yet",
                                size=14, weight=ft.FontWeight.W_600,
                                color="#0F1E3A"),
                        ft.Text(
                            f"{total_rooms} room(s) are configured but no "
                            "timetable slots have been assigned. Generate a "
                            "class timetable first, then re-run this report.",
                            size=12, color=ft.colors.GREY_600),
                    ], spacing=4, tight=True),
                ], spacing=12)),
            ]

        summary_row = ft.Row([
            self._stat_chip("Total Rooms", total_rooms,
                            ft.icons.MEETING_ROOM, "#2563EB"),
            self._stat_chip("Slots Used", total_slots,
                            ft.icons.GRID_ON, "#16A34A"),
            self._stat_chip("Busiest Room", max_slots,
                            ft.icons.TRENDING_UP, "#D97706"),
        ], spacing=12, wrap=True)

        type_colors = {
            "Regular":  "#2563EB",
            "Lab":      "#16A34A",
            "Workshop": "#D97706",
            "Hall":     "#7C3AED",
        }

        rows = []
        for r in data:
            slots = r.get('slots_used', 0)
            color = type_colors.get(r.get('type', ''), "#64748B")
            rows.append(ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(r.get('name', r.get('code', '')), size=13,
                                weight=ft.FontWeight.W_500),
                        ft.Row([
                            self._category_badge(r.get('type', 'Room'), color),
                            ft.Text(f"{slots} slots", size=12,
                                    weight=ft.FontWeight.BOLD, color=color),
                        ], spacing=6),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.ProgressBar(
                        value=slots / max_slots,
                        color=color,
                        bgcolor=ft.colors.GREY_100,
                        height=10,
                    ),
                    ft.Row([
                        ft.Text(r.get('code', ''), size=11,
                                color=ft.colors.GREY_500),
                        ft.Text(f"Capacity: {r.get('capacity', 'N/A')}",
                                size=11, color=ft.colors.GREY_400),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ], spacing=5),
                padding=ft.padding.symmetric(vertical=10, horizontal=4),
                border=ft.border.only(
                    bottom=ft.BorderSide(1, ft.colors.GREY_100)),
            ))

        return [
            self._card(summary_row, padding=16),
            self._card(ft.Column([
                self._section_title(
                    "Room Utilization Breakdown",
                    "Timetable slots assigned per room"),
                ft.Divider(height=12),
                ft.Column(rows, spacing=0),
            ], spacing=8)),
        ]

    # ------------------------------------------------------------------ #
    #  SUBJECT DISTRIBUTION                                                #
    # ------------------------------------------------------------------ #
    def _build_subject_report(self):
        tid = self._latest_timetable_id()
        if not tid:
            return self._no_data(
                "No timetable generated yet. Generate a class timetable "
                "first, then re-run this report.")

        data = self._load_subject_data()
        if not data:
            return self._no_data("No subjects found in database.")

        total      = len(data)
        in_tt      = sum(1 for s in data if s.get('classes_count', 0) > 0)
        not_placed = total - in_tt
        categories = {}
        for s in data:
            cat = s.get('category', 'Other')
            categories[cat] = categories.get(cat, 0) + 1

        cat_colors = {
            "Core":      "#2563EB",
            "Elective":  "#16A34A",
            "Practical": "#D97706",
            "Other":     "#64748B",
        }

        chips = [
            self._stat_chip("Total Subjects", total,
                            ft.icons.BOOK, "#2563EB"),
            self._stat_chip("In Timetable", in_tt,
                            ft.icons.CHECK_CIRCLE, "#16A34A"),
        ]
        if not_placed:
            chips.append(self._stat_chip(
                "Not Placed", not_placed, ft.icons.WARNING, "#DC2626"))
        for cat, count in categories.items():
            chips.append(self._stat_chip(
                cat, count, ft.icons.CATEGORY,
                cat_colors.get(cat, "#64748B")))
        summary_row = ft.Row(chips, spacing=12, wrap=True)

        max_classes = max(
            (s.get('classes_count', 0) for s in data), default=1) or 1

        rows = []
        for s in data:
            color     = cat_colors.get(s.get('category', ''), "#64748B")
            cls_count = s.get('classes_count', 0)
            total_p   = s.get('total_periods_placed', 0)
            rows.append(ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(s.get('name', ''), size=13,
                                weight=ft.FontWeight.W_500),
                        ft.Row([
                            ft.Text(s.get('code', ''), size=11,
                                    color=ft.colors.GREY_500),
                            self._category_badge(s.get('category', ''), color),
                        ], spacing=6),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.ProgressBar(
                        value=cls_count / max_classes,
                        color=color if cls_count > 0 else "#E2E8F0",
                        bgcolor=ft.colors.GREY_100,
                        height=10,
                    ),
                    ft.Row([
                        ft.Text(
                            f"{cls_count} class(es)  ·  "
                            f"{total_p} periods placed in timetable",
                            size=11, color=ft.colors.GREY_500),
                        ft.Text(
                            f"Target: {s.get('periods_per_week', 0)} p/week",
                            size=11, color=ft.colors.GREY_400),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ], spacing=5),
                padding=ft.padding.symmetric(vertical=10, horizontal=4),
                border=ft.border.only(
                    bottom=ft.BorderSide(1, ft.colors.GREY_100)),
            ))

        return [
            self._card(summary_row, padding=16),
            self._card(ft.Column([
                self._section_title(
                    "Subject Distribution Breakdown",
                    "Periods actually placed per subject in the generated timetable"),
                ft.Divider(height=12),
                ft.Column(rows, spacing=0),
            ], spacing=8)),
        ]

    # ------------------------------------------------------------------ #
    #  CLASS COVERAGE                                                      #
    # ------------------------------------------------------------------ #
    def _build_class_report(self):
        tid = self._latest_timetable_id()
        if not tid:
            return self._no_data(
                "No timetable generated yet. Generate a class timetable "
                "first, then re-run this report.")

        data = self._load_class_data()
        if not data:
            return self._no_data("No classes found in database.")

        total          = len(data)
        total_students = sum(r.get('students', 0) for r in data)
        avg_subjects   = round(
            sum(r.get('subjects_placed', 0) for r in data) / total, 1
        ) if total else 0
        avg_periods    = round(
            sum(r.get('periods_placed', 0) for r in data) / total, 1
        ) if total else 0

        summary_row = ft.Row([
            self._stat_chip("Total Classes", total,
                            ft.icons.CLASS_, "#2563EB"),
            self._stat_chip("Total Students", total_students,
                            ft.icons.PEOPLE, "#16A34A"),
            self._stat_chip("Avg Subjects/Class", avg_subjects,
                            ft.icons.BOOK, "#D97706"),
            self._stat_chip("Avg Periods/Class", avg_periods,
                            ft.icons.GRID_ON, "#7C3AED"),
        ], spacing=12, wrap=True)

        max_subj = max(
            (r.get('subjects_placed', 0) for r in data), default=1) or 1

        level_colors = {
            "JSS1": "#2563EB",
            "JSS2": "#3B82F6",
            "JSS3": "#60A5FA",
            "SS1":  "#4F46E5",
            "SS2":  "#6366F1",
            "SS3":  "#818CF8",
        }

        rows = []
        for c in data:
            level   = c.get('level', '')
            color   = level_colors.get(level, "#64748B")
            subj    = c.get('subjects_placed', 0)
            periods = c.get('periods_placed', 0)
            rows.append(ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(c.get('name', ''), size=13,
                                weight=ft.FontWeight.W_500),
                        ft.Row([
                            self._category_badge(level, color),
                            ft.Text(f"{subj} subjects · {periods} periods",
                                    size=12, weight=ft.FontWeight.BOLD,
                                    color=color),
                        ], spacing=8),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.ProgressBar(
                        value=subj / max_subj,
                        color=color,
                        bgcolor=ft.colors.GREY_100,
                        height=10,
                    ),
                    ft.Text(
                        f"{c.get('students', 0)} students enrolled",
                        size=11, color=ft.colors.GREY_500),
                ], spacing=5),
                padding=ft.padding.symmetric(vertical=10, horizontal=4),
                border=ft.border.only(
                    bottom=ft.BorderSide(1, ft.colors.GREY_100)),
            ))

        return [
            self._card(summary_row, padding=16),
            self._card(ft.Column([
                self._section_title(
                    "Class Coverage Breakdown",
                    "Subjects and periods actually placed per class "
                    "in the generated timetable"),
                ft.Divider(height=12),
                ft.Column(rows, spacing=0),
            ], spacing=8)),
        ]