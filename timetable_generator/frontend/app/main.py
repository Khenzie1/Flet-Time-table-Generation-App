"""Flet application entry point."""
import flet as ft
from pathlib import Path
import sys
import threading

sys.path.append(str(Path(__file__).parent.parent))

from app.config import APP_NAME, THEME_COLOR
from app.api_client import ApiClient
from app.local_db import LocalDB


class TimetableApp:
    def __init__(self):
        self.api_client  = ApiClient()
        self.local_db    = LocalDB()
        self.current_user = None
        self.page         = None

    def initialize_db(self):
        try:
            self.local_db.init_database()
            print("✅ Local database initialised")
        except Exception as e:
            print(f"❌ DB init error: {e}")

    def _probe_server(self):
        online = self.api_client.probe()
        print(f"Server status: {'online' if online else 'offline'}")
        if self.page:
            try:
                self.page.pubsub.send_all_on_topic(
                    "server_status", "online" if online else "offline")
            except Exception:
                pass

    def probe_server_async(self):
        threading.Thread(target=self._probe_server, daemon=True).start()

    def do_login(self, username: str, password: str) -> dict:
        # ── Check local users table (seeded admin lives here too) ─────────
        try:
            rows = self.local_db.execute(
                "SELECT * FROM users WHERE username=? AND is_active=1", (username,))
            if rows:
                user = dict(rows[0])
                ph = user.get("password_hash") or user.get("password") or ""
                ok = False
                if ph.startswith("$2"):
                    try:
                        from passlib.context import CryptContext
                        ok = CryptContext(schemes=["bcrypt"], deprecated="auto").verify(password, ph)
                    except Exception:
                        ok = False
                else:
                    ok = (ph == password)
                if ok:
                    self.current_user = user
                    self._try_server_login_async(username, password)
                    return {"ok": True, "user": user}
        except Exception as ex:
            print(f"[login] local DB error: {ex}")

        # ── Emergency fallback: if the DB is completely empty/broken,
        #    allow the original hardcoded credentials so the admin can
        #    always get in and recreate users. ────────────────────────────
        if username == "admin" and password == "admin123":
            try:
                cnt = self.local_db.execute("SELECT COUNT(*) as n FROM users")
                db_empty = (not cnt) or (cnt[0]["n"] == 0)
            except Exception:
                db_empty = True
            if db_empty:
                self.current_user = {
                    "id":       "admin-default",
                    "username": "admin",
                    "role":     "ADMIN",
                    "email":    "admin@school.edu",
                }
                self._try_server_login_async(username, password)
                return {"ok": True, "user": self.current_user}

        # ── Try backend server directly ───────────────────────────────────
        if not self.api_client.offline_mode:
            result = self.api_client.login(username, password)
            if not result.get("error"):
                self.current_user = result["user"]
                return {"ok": True, "user": result["user"]}
            return {"ok": False, "message": result.get("message", "Invalid credentials")}

        return {"ok": False, "message": "Invalid credentials"}

    def _try_server_login_async(self, username: str, password: str):
        """Background: grab a server JWT so sync/API calls work."""
        def _login():
            if self.api_client.offline_mode:
                return
            result = self.api_client.login(username, password)
            if not result.get("error"):
                print(f"[server] token acquired for {username}")
            else:
                print(f"[server] token not acquired: {result.get('message')}")
        threading.Thread(target=_login, daemon=True).start()


    def route_change(self, e: ft.RouteChangeEvent):
        print(f"Route → {self.page.route}")
        self.page.views.clear()
        try:
            route = self.page.route
            if route == "/splash":
                from app.views.splash_view import SplashView
                self.page.views.append(SplashView(self).build())
            elif route in ("/login", "/") or not self.current_user:
                from app.views.login_view import LoginView
                self.page.views.append(LoginView(self).build())
            elif route == "/dashboard":
                from app.views.dashboard_view import DashboardView
                self.page.views.append(DashboardView(self).build())
            elif route == "/teachers":
                from app.views.teachers_view import TeachersView
                self.page.views.append(TeachersView(self).build())
            elif route == "/subjects":
                from app.views.subjects_view import SubjectsView
                self.page.views.append(SubjectsView(self).build())
            elif route == "/classes":
                from app.views.classes_view import ClassesView
                self.page.views.append(ClassesView(self).build())
            elif route == "/rooms":
                from app.views.rooms_view import RoomsView
                self.page.views.append(RoomsView(self).build())
            elif route == "/calendar":
                from app.views.calendar_view import CalendarView
                self.page.views.append(CalendarView(self).build())
            elif route == "/timetable":
                from app.views.timetable_view import TimetableView
                self.page.views.append(TimetableView(self).build())
            elif route == "/view_timetable":
                from app.views.view_timetable_view import ViewTimetableView
                self.page.views.append(ViewTimetableView(self).build())
            elif route == "/reports":
                from app.views.reports_view import ReportsView
                self.page.views.append(ReportsView(self).build())
            elif route == "/settings":
                from app.views.settings_view import SettingsView
                self.page.views.append(SettingsView(self).build())
            else:
                self.page.go("/dashboard")
                return
            self.page.update()
        except Exception as ex:
            import traceback
            print(f"ERROR loading {self.page.route}: {ex}")
            traceback.print_exc()

    def main(self, page: ft.Page):
        self.page = page
        page.title      = APP_NAME
        page.theme_mode = ft.ThemeMode.LIGHT
        page.theme      = ft.Theme(color_scheme_seed=THEME_COLOR)
        page.padding    = 0
        page.spacing    = 0
        page.window_width      = 1200
        page.window_height     = 800
        page.window_min_width  = 800
        page.window_min_height = 600
        self.initialize_db()
        self.probe_server_async()
        page.on_route_change = self.route_change

        # ── Listen for force-logout broadcasts (user deleted by an admin) ─
        def on_force_logout(topic, deleted_uid):
            """Called on every active session when a user is deleted."""
            if self.current_user and self.current_user.get("id") == deleted_uid:
                self.current_user = None
                try:
                    page.show_snack_bar(ft.SnackBar(
                        content=ft.Text("Your account has been deleted by an administrator."),
                        bgcolor=ft.colors.RED_700,
                    ))
                    page.update()
                except Exception:
                    pass
                page.go("/login")

        try:
            page.pubsub.subscribe_topic("force_logout", on_force_logout)
        except Exception:
            pass  # pubsub not available in this runtime — silent skip

        page.go("/splash")
        page.update()


def main():
    app = TimetableApp()
    ft.app(target=app.main, assets_dir="assets")

if __name__ == "__main__":
    main()