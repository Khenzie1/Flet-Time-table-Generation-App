"""Login view — split-screen, matches dashboard navy/blue identity."""
import flet as ft
from app.config import APP_NAME, ERROR_COLOR, SUCCESS_COLOR


class LoginView:
    def __init__(self, app):
        self.app  = app
        self.page = app.page

        self.username_field = ft.TextField(
            label="Username",
            prefix_icon=ft.icons.PERSON_OUTLINE_ROUNDED,
            width=340,
            autofocus=True,
            border_radius=10,
            on_submit=self.login,
            filled=True,
            bgcolor=ft.colors.GREY_50,
        )
        self.password_field = ft.TextField(
            label="Password",
            prefix_icon=ft.icons.LOCK_OUTLINE_ROUNDED,
            password=True,
            can_reveal_password=True,
            width=340,
            border_radius=10,
            on_submit=self.login,
            filled=True,
            bgcolor=ft.colors.GREY_50,
        )
        self.message = ft.Text("", size=12)
        self.login_btn = ft.ElevatedButton(
            "Login",
            width=340,
            height=48,
            on_click=self._login_animated,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                bgcolor={"": "#0F1E3A", "hovered": "#1E3A5F"},
                color=ft.colors.WHITE,
                elevation={"": 0, "hovered": 3},
            ),
        )

    def build(self):
        # ── Left panel: school branding ────────────────────────────────
        left_panel = ft.Container(
            content=ft.Column([
                ft.Container(expand=True),

                # Logo
                ft.Container(
                    content=ft.Image(
                        src="MMSSlogo.jpg",
                        width=140,
                        height=140,
                        fit=ft.ImageFit.CONTAIN,
                        border_radius=ft.border_radius.all(12),
                    ),
                    alignment=ft.alignment.center,
                    shadow=ft.BoxShadow(
                        blur_radius=30, spread_radius=0,
                        color=ft.colors.with_opacity(0.3, ft.colors.BLACK),
                        offset=ft.Offset(0, 8),
                    ),
                ),

                ft.Container(height=28),

                # School name
                ft.Text(
                    "Model Migrant Secondary School",
                    size=20,
                    weight=ft.FontWeight.BOLD,
                    color=ft.colors.WHITE,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=6),
                ft.Text(
                    "Mkpatak, Essien Udim",
                    size=13,
                    color=ft.colors.with_opacity(0.6, ft.colors.WHITE),
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=6),
                ft.Container(
                    content=ft.Text(
                        "Education For Development",
                        size=12,
                        italic=True,
                        color=ft.colors.with_opacity(0.5, ft.colors.WHITE),
                        text_align=ft.TextAlign.CENTER,
                    ),
                ),

                ft.Container(expand=True),

                # App label at the bottom
                ft.Container(
                    content=ft.Row([
                        ft.Container(
                            width=28, height=28,
                            bgcolor="#2563EB",
                            border_radius=7,
                            content=ft.Text("TT", size=11,
                                            color=ft.colors.WHITE,
                                            weight=ft.FontWeight.BOLD,
                                            text_align=ft.TextAlign.CENTER),
                            alignment=ft.alignment.center,
                        ),
                        ft.Column([
                            ft.Text("Smart Timetable Generator",
                                    size=12, color=ft.colors.WHITE,
                                    weight=ft.FontWeight.W_500),
                            ft.Text("MMSS TT · v1.0",
                                    size=10,
                                    color=ft.colors.with_opacity(0.4, ft.colors.WHITE)),
                        ], spacing=0),
                    ], spacing=10),
                    margin=ft.margin.only(bottom=20),
                ),

            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
            expand=True,
            bgcolor="#0F1E3A",
            padding=ft.padding.symmetric(horizontal=40, vertical=30),
        )

        # ── Right panel: login form ────────────────────────────────────
        right_panel = ft.Container(
            content=ft.Column([
                ft.Container(expand=True),

                ft.Column([
                    # Heading
                    ft.Text("Welcome back",
                            size=26, weight=ft.FontWeight.BOLD,
                            color=ft.colors.GREY_900),
                    ft.Text("Sign in to your account to continue",
                            size=13, color=ft.colors.GREY_500),

                    ft.Container(height=28),

                    self.username_field,
                    ft.Container(height=10),
                    self.password_field,

                    # Remember me
                    ft.Container(
                        content=ft.Checkbox(
                            label="Remember me",
                            value=True,
                            label_style=ft.TextStyle(size=12, color=ft.colors.GREY_600),
                        ),
                        width=340,
                        alignment=ft.alignment.center_left,
                        margin=ft.margin.only(top=4, bottom=8),
                    ),

                    self.login_btn,
                    self.message,

                    ft.Container(height=10),

                    # Forgot password
                    ft.Container(
                        content=ft.TextButton(
                            "Forgot password?",
                            on_click=self.forgot_password,
                            style=ft.ButtonStyle(
                                color=ft.colors.GREY_500,
                            ),
                        ),
                        width=340,
                        alignment=ft.alignment.center_right,
                    ),

                    ft.Container(height=8),
                    ft.Divider(color=ft.colors.GREY_200, height=1),
                    ft.Container(height=8),

                    ft.Row([
                        ft.Text("Need access?", size=12, color=ft.colors.GREY_500),
                        ft.TextButton(
                            "Contact administrator",
                            on_click=self.register,
                            style=ft.ButtonStyle(
                                color="#2563EB",
                            ),
                        ),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=2),

                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),

                ft.Container(expand=True),

                # Footer
                ft.Text(
                    "© 2025 Model Migrant Secondary School",
                    size=11,
                    color=ft.colors.GREY_400,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=16),

            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
            expand=True,
            bgcolor=ft.colors.WHITE,
            padding=ft.padding.symmetric(horizontal=60, vertical=30),
        )

        return ft.View(
            "/login",
            [
                ft.Row(
                    [left_panel, right_panel],
                    spacing=0,
                    expand=True,
                )
            ],
            padding=0,
            spacing=0,
        )

    # ══════════════════════════════════════════════════════════════════
    # LOGIN BUTTON ANIMATION
    # ══════════════════════════════════════════════════════════════════
    async def _login_animated(self, e):
        """Show 'Signing in…' spinner, run login logic, then reset on failure
        (on success the page navigates away so the button state doesn't matter)."""
        import asyncio
        self.login_btn.text     = "Signing in…"
        self.login_btn.icon     = ft.icons.HOURGLASS_TOP_ROUNDED
        self.login_btn.disabled = True
        self.login_btn.style.bgcolor = {"": "#1E3A5F", "hovered": "#1E3A5F"}
        self.page.update()
        await asyncio.sleep(0.15)

        self.login(e)  # runs credentials check + navigates on success

        # Only reached when login FAILED (success navigates away)
        self.login_btn.text     = "Login"
        self.login_btn.icon     = None
        self.login_btn.disabled = False
        self.login_btn.style.bgcolor = {"": "#0F1E3A", "hovered": "#1E3A5F"}
        self.page.update()

    def login(self, e):
        username = self.username_field.value.strip()
        password = self.password_field.value

        if not username or not password:
            self.message.value = "Please enter your username and password."
            self.message.color = ERROR_COLOR
            self.page.update()
            return

        self.message.value = "Checking credentials…"
        self.message.color = ft.colors.GREY_500
        self.page.update()

        result = self.app.do_login(username, password)

        if result["ok"]:
            self.message.value = ""
            self.page.update()
            self.page.go("/dashboard")
        else:
            self.message.value = result.get("message", "Invalid username or password.")
            self.message.color = ERROR_COLOR
            self.password_field.value = ""
            self.page.update()

    def register(self, e):
        self.message.value = "Please contact your administrator for access."
        self.message.color = ft.colors.GREY_600
        self.page.update()

    def forgot_password(self, e):
        self.message.value = "Please contact your administrator to reset your password."
        self.message.color = ft.colors.GREY_600
        self.page.update()