"""Quick test to verify all screens load."""
import flet as ft
from app.views.dashboard_view import DashboardView
from app.views.teachers_view import TeachersView
from app.views.subjects_view import SubjectsView
from app.views.classes_view import ClassesView
from app.views.rooms_view import RoomsView
from app.views.calendar_view import CalendarView
from app.views.timetable_view import TimetableView
from app.views.reports_view import ReportsView
from app.views.settings_view import SettingsView
from app.local_db import LocalDB

class TestApp:
    def __init__(self, page):
        self.page = page
        self.current_user = {"username": "admin", "role": "ADMIN"}
        self.local_db = LocalDB()
        self.api_client = None
    
    def test_view(self, view_class, view_name):
        """Test loading a view."""
        try:
            print(f"\n🔍 Testing {view_name}...")
            view = view_class(self)
            self.page.views.clear()
            self.page.views.append(view.build())
            self.page.update()
            print(f"✅ {view_name} loaded successfully")
            return True
        except Exception as e:
            print(f"❌ {view_name} failed to load: {e}")
            import traceback
            traceback.print_exc()
            return False

def main(page: ft.Page):
    page.title = "Quick Screen Test"
    page.window_width = 800
    page.window_height = 600
    
    app = TestApp(page)
    
    # Test each view
    views_to_test = [
        (DashboardView, "Dashboard"),
        (TeachersView, "Teachers"),
        (SubjectsView, "Subjects"),
        (ClassesView, "Classes"),
        (RoomsView, "Rooms"),
        (CalendarView, "Calendar"),
        (TimetableView, "Timetable"),
        (ReportsView, "Reports"),
        (SettingsView, "Settings"),
    ]
    
    results = []
    for view_class, view_name in views_to_test:
        success = app.test_view(view_class, view_name)
        results.append((view_name, success))
    
    # Show results
    page.views.clear()
    page.views.append(
        ft.View(
            "/",
            [
                ft.AppBar(title=ft.Text("Test Results")),
                ft.Container(
                    content=ft.Column([
                        ft.Text("Screen Load Test Results", size=20, weight=ft.FontWeight.BOLD),
                        ft.Divider(),
                        *[
                            ft.Row([
                                ft.Icon(
                                    ft.icons.CHECK_CIRCLE if success else ft.icons.ERROR,
                                    color=ft.colors.GREEN if success else ft.colors.RED
                                ),
                                ft.Text(f"{name}: {'✅ Passed' if success else '❌ Failed'}"),
                            ])
                            for name, success in results
                        ]
                    ]),
                    padding=20
                )
            ]
        )
    )
    page.update()

ft.app(target=main)