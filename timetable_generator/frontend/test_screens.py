"""Test each screen individually."""
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
        self.page = page  # Store the page reference
        self.current_user = {"username": "admin", "role": "ADMIN"}
        self.local_db = LocalDB()
        self.api_client = None  # Mock API client for testing
        
    def test_teachers(self, e):
        print("Testing Teachers View")
        self.page.views.clear()
        view = TeachersView(self)
        self.page.views.append(view.build())
        self.page.update()
        
    def test_subjects(self, e):
        print("Testing Subjects View")
        self.page.views.clear()
        view = SubjectsView(self)
        self.page.views.append(view.build())
        self.page.update()
        
    def test_classes(self, e):
        print("Testing Classes View")
        self.page.views.clear()
        view = ClassesView(self)
        self.page.views.append(view.build())
        self.page.update()
        
    def test_rooms(self, e):
        print("Testing Rooms View")
        self.page.views.clear()
        view = RoomsView(self)
        self.page.views.append(view.build())
        self.page.update()
        
    def test_calendar(self, e):
        print("Testing Calendar View")
        self.page.views.clear()
        view = CalendarView(self)
        self.page.views.append(view.build())
        self.page.update()
        
    def test_timetable(self, e):
        print("Testing Timetable View")
        self.page.views.clear()
        view = TimetableView(self)
        self.page.views.append(view.build())
        self.page.update()
        
    def test_reports(self, e):
        print("Testing Reports View")
        self.page.views.clear()
        view = ReportsView(self)
        self.page.views.append(view.build())
        self.page.update()
        
    def test_settings(self, e):
        print("Testing Settings View")
        self.page.views.clear()
        view = SettingsView(self)
        self.page.views.append(view.build())
        self.page.update()
        
    def back_to_menu(self, e):
        """Return to the main menu."""
        self.show_menu()
    
    def show_menu(self):
        """Show the main menu."""
        self.page.views.clear()
        
        # Create menu buttons
        menu = ft.View(
            "/",
            [
                ft.AppBar(
                    title=ft.Text("Screen Tester"),
                    bgcolor=ft.colors.BLUE,
                    color=ft.colors.WHITE,
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text("Test Each Screen:", size=24, weight=ft.FontWeight.BOLD),
                        ft.Divider(height=20),
                        
                        # Row 1
                        ft.Row([
                            ft.ElevatedButton(
                                "Teachers",
                                icon=ft.icons.PEOPLE,
                                on_click=self.test_teachers,
                                width=150,
                                height=50,
                            ),
                            ft.ElevatedButton(
                                "Subjects",
                                icon=ft.icons.BOOK,
                                on_click=self.test_subjects,
                                width=150,
                                height=50,
                            ),
                            ft.ElevatedButton(
                                "Classes",
                                icon=ft.icons.GROUP,
                                on_click=self.test_classes,
                                width=150,
                                height=50,
                            ),
                        ], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
                        
                        # Row 2
                        ft.Row([
                            ft.ElevatedButton(
                                "Rooms",
                                icon=ft.icons.MEETING_ROOM,
                                on_click=self.test_rooms,
                                width=150,
                                height=50,
                            ),
                            ft.ElevatedButton(
                                "Calendar",
                                icon=ft.icons.CALENDAR_MONTH,
                                on_click=self.test_calendar,
                                width=150,
                                height=50,
                            ),
                            ft.ElevatedButton(
                                "Timetable",
                                icon=ft.icons.SCHEDULE,
                                on_click=self.test_timetable,
                                width=150,
                                height=50,
                            ),
                        ], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
                        
                        # Row 3
                        ft.Row([
                            ft.ElevatedButton(
                                "Reports",
                                icon=ft.icons.ANALYTICS,
                                on_click=self.test_reports,
                                width=150,
                                height=50,
                            ),
                            ft.ElevatedButton(
                                "Settings",
                                icon=ft.icons.SETTINGS,
                                on_click=self.test_settings,
                                width=150,
                                height=50,
                            ),
                            ft.ElevatedButton(
                                "Dashboard",
                                icon=ft.icons.DASHBOARD,
                                on_click=lambda e: self.show_dashboard(),
                                width=150,
                                height=50,
                            ),
                        ], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
                        
                        ft.Divider(height=20),
                        
                        ft.Container(
                            content=ft.Column([
                                ft.Text("Instructions:", weight=ft.FontWeight.BOLD),
                                ft.Text("• Click any button to test that screen"),
                                ft.Text("• Use the back button in each screen to return here"),
                                ft.Text("• Watch the console for error messages"),
                            ]),
                            padding=20,
                            bgcolor=ft.colors.GREY_100,
                            border_radius=10,
                        )
                    ], spacing=20, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    
                    padding=30,
                    alignment=ft.alignment.center,
                    expand=True,
                )
            ],
            padding=0,
            spacing=0
        )
        
        self.page.views.append(menu)
        self.page.update()
    
    def show_dashboard(self, e=None):
        """Show the dashboard view."""
        self.page.views.clear()
        view = DashboardView(self)
        self.page.views.append(view.build())
        self.page.update()


def main(page: ft.Page):
    """Main entry point."""
    page.title = "Screen Tester"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window_width = 1200
    page.window_height = 800
    page.padding = 0
    page.spacing = 0
    
    # Create test app with page reference
    app = TestApp(page)
    
    # Show the menu
    app.show_menu()


if __name__ == "__main__":
    ft.app(target=main)