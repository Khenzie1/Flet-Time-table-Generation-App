"""Dashboard view — Option A dark sidebar with collapse/expand toggle."""
import flet as ft
from datetime import datetime
import threading

SIDEBAR_FULL    = 210
SIDEBAR_MINI    = 56
NAVY            = "#0F1E3A"
BLUE_ACCENT     = "#2563EB"


# ── Stat card ─────────────────────────────────────────────────────────────────
def _stat_card(label, value_ctrl, bar_color):
    return ft.Container(
        content=ft.Column([
            value_ctrl,
            ft.Text(label, size=12, color=ft.colors.GREY_500),
            ft.Container(bgcolor=bar_color, height=3, border_radius=2,
                         margin=ft.margin.only(top=10)),
        ], spacing=2),
        bgcolor=ft.colors.WHITE,
        border_radius=10,
        padding=ft.padding.symmetric(horizontal=16, vertical=14),
        shadow=ft.BoxShadow(blur_radius=8, spread_radius=0,
                            color=ft.colors.with_opacity(0.06, ft.colors.BLACK),
                            offset=ft.Offset(0, 2)),
        expand=True,
    )


# ── Quick action card ─────────────────────────────────────────────────────────
def _action_card(icon, title, subtitle, accent, route, page):
    return ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Icon(icon, size=18, color=accent),
                width=36, height=36,
                bgcolor=ft.colors.with_opacity(0.1, accent),
                border_radius=9, alignment=ft.alignment.center,
            ),
            ft.Text(title, size=13, weight=ft.FontWeight.W_500,
                    color=ft.colors.GREY_900),
            ft.Text(subtitle, size=11, color=ft.colors.GREY_500),
            ft.Container(content=ft.Text("Open →", size=11, color=accent),
                         margin=ft.margin.only(top=4)),
        ], spacing=4),
        bgcolor=ft.colors.WHITE, border_radius=10,
        padding=ft.padding.symmetric(horizontal=14, vertical=14),
        shadow=ft.BoxShadow(blur_radius=8, spread_radius=0,
                            color=ft.colors.with_opacity(0.06, ft.colors.BLACK),
                            offset=ft.Offset(0, 2)),
        on_click=lambda e: page.go(route), ink=True, expand=True,
    )


class DashboardView:
    def __init__(self, app):
        self.app  = app
        self.page = app.page
        self._expanded = True   # sidebar state

        # ── Dynamic counters ───────────────────────────────────────────
        # ── Sync status badge (updated after probe) ──────────────────
        self._sync_badge_icon = ft.Icon(
            ft.icons.SYNC_ROUNDED, size=14, color=ft.colors.GREY_500)
        self._sync_badge_text = ft.Text(
            "Checking…", size=12, color=ft.colors.GREY_500)
        self._sync_badge_row  = ft.Container(
            content=ft.Row([self._sync_badge_icon,
                            self._sync_badge_text], spacing=5),
            padding=ft.padding.symmetric(horizontal=12, vertical=6),
            border_radius=20, bgcolor=ft.colors.GREY_100,
        )
        self.teacher_count = ft.Text("0", size=26, weight=ft.FontWeight.BOLD,
                                     color=ft.colors.GREY_900)
        self.subject_count = ft.Text("0", size=26, weight=ft.FontWeight.BOLD,
                                     color=ft.colors.GREY_900)
        self.class_count   = ft.Text("0", size=26, weight=ft.FontWeight.BOLD,
                                     color=ft.colors.GREY_900)
        self.room_count    = ft.Text("0", size=26, weight=ft.FontWeight.BOLD,
                                     color=ft.colors.GREY_900)
        self.load_counts()
        # Probe server in background and update badge when done
        self.app.api_client.probe_async(callback=self._on_probe_result)
        # Also update badge if settings screen completes a sync
        try:
            self.page.pubsub.subscribe_topic(
                "sync_status",
                lambda topic, msg: self._on_probe_result(msg == "online")
            )
        except Exception:
            pass

    def load_counts(self):
        try:
            def _q(t):
                r = self.app.local_db.execute(f"SELECT COUNT(*) as cnt FROM {t}")
                return str(r[0]['cnt']) if r else "0"
            self.teacher_count.value = _q("teachers")
            self.subject_count.value = _q("subjects")
            self.class_count.value   = _q("classes")
            self.room_count.value    = _q("rooms")
        except Exception as ex:
            print(f"Dashboard count error: {ex}")

    def _on_probe_result(self, online: bool):
        """Called from background thread after server probe completes."""
        if online:
            self._sync_badge_icon.name   = ft.icons.CHECK_CIRCLE_ROUNDED
            self._sync_badge_icon.color  = ft.colors.GREEN_700
            self._sync_badge_text.value  = "Synced"
            self._sync_badge_text.color  = ft.colors.GREEN_700
            self._sync_badge_row.bgcolor = ft.colors.GREEN_50
        else:
            self._sync_badge_icon.name   = ft.icons.CLOUD_OFF_ROUNDED
            self._sync_badge_icon.color  = ft.colors.GREY_500
            self._sync_badge_text.value  = "Offline"
            self._sync_badge_text.color  = ft.colors.GREY_500
            self._sync_badge_row.bgcolor = ft.colors.GREY_100
        try:
            self.page.update()
        except Exception:
            pass

    # ── Toggle ────────────────────────────────────────────────────────
    def _toggle_sidebar(self, e):
        self._expanded = not self._expanded
        w = SIDEBAR_FULL if self._expanded else SIDEBAR_MINI

        # Resize sidebar
        self._sidebar.width = w

        # Show/hide all text labels and section headings
        for ctrl in self._sidebar_labels:
            ctrl.visible = self._expanded

        # Swap toggle icon
        self._toggle_btn.icon = (ft.icons.MENU_OPEN_ROUNDED
                                 if self._expanded
                                 else ft.icons.MENU_ROUNDED)

        # Centre icons in mini mode, left-align in full mode
        for row in self._nav_rows:
            row.alignment = (ft.MainAxisAlignment.CENTER
                             if not self._expanded
                             else ft.MainAxisAlignment.START)

        # Brand row
        self._brand_row.alignment = (ft.MainAxisAlignment.CENTER
                                     if not self._expanded
                                     else ft.MainAxisAlignment.START)

        self.page.update()

    # ── Build ─────────────────────────────────────────────────────────
    def build(self):
        username  = (self.app.current_user or {}).get('username', 'Admin')
        initials  = username[:2].upper()
        now_label = datetime.now().strftime("%A, %d %B %Y")

        # ── Helpers that track label refs ──────────────────────────────
        # Every Text that should hide when collapsed is appended here.
        self._sidebar_labels = []

        def _label(text, **kwargs):
            """Make a Text and register it for show/hide toggling."""
            t = ft.Text(text, **kwargs)
            self._sidebar_labels.append(t)
            return t

        def _nav_row(icon, lbl_text, active=False, route=None):
            """Build one nav row; returns (Container, Row) so we can track Row."""
            lbl = _label(lbl_text, size=13,
                         color=ft.colors.WHITE if active
                         else ft.colors.with_opacity(0.75, ft.colors.WHITE),
                         weight=ft.FontWeight.W_500 if active
                         else ft.FontWeight.NORMAL)
            row = ft.Row([
                ft.Icon(icon, size=18,
                        color=ft.colors.WHITE if active
                        else ft.colors.with_opacity(0.75, ft.colors.WHITE)),
                lbl,
            ], spacing=10)
            self._nav_rows.append(row)

            def _go(e):
                if route:
                    self.page.go(route)

            return ft.Container(
                content=row,
                padding=ft.padding.symmetric(horizontal=10, vertical=9),
                border_radius=8,
                bgcolor=(ft.colors.with_opacity(0.15, ft.colors.WHITE)
                         if active else ft.colors.TRANSPARENT),
                on_click=_go if route else None,
                ink=bool(route),
                tooltip=lbl_text if not self._expanded else None,
            )

        # ── Build sidebar ──────────────────────────────────────────────
        self._nav_rows = []

        # Brand row
        brand_text_col = ft.Column([
            _label("MMSS TT", size=14, weight=ft.FontWeight.BOLD,
                   color=ft.colors.WHITE),
            _label("Timetable Generator", size=10,
                   color=ft.colors.with_opacity(0.5, ft.colors.WHITE)),
        ], spacing=0)
        self._brand_row = ft.Row([
            ft.Image(src="MMSSlogo.jpg", width=34, height=34,
                     fit=ft.ImageFit.CONTAIN,
                     border_radius=ft.border_radius.all(6)),
            brand_text_col,
        ], spacing=10)

        section_main      = _label("MAIN", size=10, weight=ft.FontWeight.BOLD,
                                    color=ft.colors.with_opacity(0.35, ft.colors.WHITE))
        section_timetable = _label("TIMETABLE", size=10, weight=ft.FontWeight.BOLD,
                                    color=ft.colors.with_opacity(0.35, ft.colors.WHITE))

        user_name_text = _label(username, size=12, color=ft.colors.WHITE,
                                weight=ft.FontWeight.W_500)
        user_role_text = _label("Admin", size=10,
                                color=ft.colors.with_opacity(0.5, ft.colors.WHITE))
        self._sidebar_labels.append(brand_text_col)  # hide whole column

        # User strip
        user_strip = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Text(initials, size=12, color=ft.colors.WHITE,
                                    weight=ft.FontWeight.BOLD),
                    width=32, height=32, bgcolor=BLUE_ACCENT,
                    border_radius=16, alignment=ft.alignment.center,
                ),
                ft.Column([user_name_text, user_role_text],
                          spacing=0, expand=True),
                ft.IconButton(icon=ft.icons.LOGOUT_ROUNDED, icon_size=16,
                              icon_color=ft.colors.with_opacity(0.5, ft.colors.WHITE),
                              tooltip="Logout", on_click=self.logout),
            ], spacing=8),
            margin=ft.margin.only(top=10),
        )

        sidebar_col = ft.Column([
            ft.Container(content=self._brand_row,
                         margin=ft.margin.only(bottom=20, top=4)),

            section_main,
            ft.Container(height=4),
            _nav_row(ft.icons.DASHBOARD_ROUNDED,    "Dashboard",  active=True),
            _nav_row(ft.icons.PEOPLE_ALT_ROUNDED,   "Teachers",   route="/teachers"),
            _nav_row(ft.icons.MENU_BOOK_ROUNDED,    "Subjects",   route="/subjects"),
            _nav_row(ft.icons.GROUPS_ROUNDED,       "Classes",    route="/classes"),
            _nav_row(ft.icons.MEETING_ROOM_ROUNDED, "Rooms",      route="/rooms"),

            ft.Container(height=14),
            section_timetable,
            ft.Container(height=4),
            _nav_row(ft.icons.ADD_CIRCLE_OUTLINE,   "Generate",   route="/timetable"),
            _nav_row(ft.icons.VISIBILITY_ROUNDED,   "View",       route="/view_timetable"),
            _nav_row(ft.icons.CALENDAR_MONTH,       "Calendar",   route="/calendar"),
            _nav_row(ft.icons.ANALYTICS_ROUNDED,    "Reports",    route="/reports"),

            ft.Container(expand=True),
            ft.Divider(color=ft.colors.with_opacity(0.1, ft.colors.WHITE), height=1),
            ft.Container(height=6),
            _nav_row(ft.icons.SETTINGS_ROUNDED,     "Settings",   route="/settings"),
            user_strip,
        ], spacing=2, expand=True)

        self._sidebar = ft.Container(
            content=sidebar_col,
            width=SIDEBAR_FULL,
            bgcolor=NAVY,
            padding=ft.padding.symmetric(horizontal=12, vertical=18),
            animate=ft.Animation(220, ft.AnimationCurve.EASE_IN_OUT),
        )

        # ── Toggle button ──────────────────────────────────────────────
        self._toggle_btn = ft.IconButton(
            icon=ft.icons.MENU_OPEN_ROUNDED,
            icon_size=20,
            icon_color=ft.colors.GREY_600,
            tooltip="Toggle sidebar",
            on_click=self._toggle_sidebar,
        )

        # ── Main area ──────────────────────────────────────────────────
        main_area = ft.Container(
            content=ft.Column([

                # Top bar — toggle btn on the left
                ft.Row([
                    self._toggle_btn,
                    ft.Container(width=8),
                    ft.Column([
                        ft.Text(f"Welcome back, {username}!",
                                size=20, weight=ft.FontWeight.BOLD,
                                color=ft.colors.GREY_900),
                        ft.Text(now_label, size=12, color=ft.colors.GREY_500),
                    ], spacing=2),
                    ft.Container(expand=True),
                    self._sync_badge_row,
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),

                ft.Container(height=20),

                # Stat cards
                ft.Row([
                    _stat_card("Teachers", self.teacher_count, BLUE_ACCENT),
                    _stat_card("Subjects",  self.subject_count, "#F59E0B"),
                    _stat_card("Classes",   self.class_count,   "#10B981"),
                    _stat_card("Rooms",     self.room_count,    "#8B5CF6"),
                ], spacing=12),

                ft.Container(height=24),

                ft.Text("Quick Actions", size=14, weight=ft.FontWeight.W_500,
                        color=ft.colors.GREY_600),
                ft.Container(height=10),

                ft.Row([
                    _action_card(ft.icons.ADD_CIRCLE_OUTLINE,
                                 "Generate",     "Create timetable",
                                 BLUE_ACCENT, "/timetable",       self.page),
                    _action_card(ft.icons.VISIBILITY_ROUNDED,
                                 "View Timetable","Browse schedules",
                                 "#10B981",  "/view_timetable",   self.page),
                    _action_card(ft.icons.ANALYTICS_ROUNDED,
                                 "Reports",      "View insights",
                                 "#F59E0B",  "/reports",          self.page),
                ], spacing=12),

                ft.Container(height=16),

                ft.Row([
                    _action_card(ft.icons.PEOPLE_ALT_ROUNDED,
                                 "Teachers",  "Manage staff",
                                 "#6366F1", "/teachers",  self.page),
                    _action_card(ft.icons.GROUPS_ROUNDED,
                                 "Classes",   "Manage classes",
                                 "#EC4899", "/classes",   self.page),
                    _action_card(ft.icons.CALENDAR_MONTH,
                                 "Calendar",  "School schedule",
                                 "#EF4444", "/calendar",  self.page),
                ], spacing=12),

            ], scroll=ft.ScrollMode.AUTO),
            expand=True,
            bgcolor="#F8FAFC",
            padding=ft.padding.symmetric(horizontal=24, vertical=20),
        )

        return ft.View(
            "/dashboard",
            [ft.Row([self._sidebar, main_area], spacing=0, expand=True)],
            padding=0, spacing=0,
        )

    def logout(self, e):
        self.app.current_user = None
        self.page.go("/login")