"""Splash / launch screen — shown for 3 seconds before login."""
import flet as ft
import threading
import time


class SplashView:
    def __init__(self, app):
        self.app  = app
        self.page = app.page

        # ── Logo (fades in) ────────────────────────────────────────────
        self._logo = ft.Image(
            src="MMSSlogo.jpg",
            width=200,
            height=200,
            fit=ft.ImageFit.CONTAIN,
            animate_opacity=ft.Animation(800, ft.AnimationCurve.EASE_IN),
            opacity=0,
        )

        # ── School name ────────────────────────────────────────────────
        self._title = ft.Text(
            "Model Migrant Secondary School",
            size=26,
            weight=ft.FontWeight.BOLD,
            color=ft.colors.WHITE,
            text_align=ft.TextAlign.CENTER,
            animate_opacity=ft.Animation(800, ft.AnimationCurve.EASE_IN),
            opacity=0,
        )

        self._location = ft.Text(
            "Mkpatak, Essien Udim",
            size=15,
            color=ft.colors.BLUE_100,
            text_align=ft.TextAlign.CENTER,
            animate_opacity=ft.Animation(800, ft.AnimationCurve.EASE_IN),
            opacity=0,
        )

        self._tagline = ft.Text(
            "Education For Development",
            size=13,
            italic=True,
            color=ft.colors.BLUE_200,
            text_align=ft.TextAlign.CENTER,
            animate_opacity=ft.Animation(800, ft.AnimationCurve.EASE_IN),
            opacity=0,
        )

        # ── Thin loading bar at the bottom ────────────────────────────
        self._bar = ft.ProgressBar(
            width=260,
            color="#2563EB",
            bgcolor=ft.colors.with_opacity(0.2, ft.colors.WHITE),
            value=0,
            animate_opacity=ft.Animation(600, ft.AnimationCurve.EASE_IN),
            opacity=0,
        )

    # ──────────────────────────────────────────────────────────────────
    def build(self):
        view = ft.View(
            "/",
            [
                ft.Container(
                    expand=True,
                    bgcolor="#0F1E3A",
                    content=ft.Column(
                        [
                            ft.Container(expand=True),   # top spacer

                            # Logo with subtle drop shadow ring
                            ft.Container(
                                content=self._logo,
                                border_radius=120,
                                shadow=ft.BoxShadow(
                                    blur_radius=40,
                                    spread_radius=2,
                                    color=ft.colors.with_opacity(0.35, ft.colors.BLACK),
                                    offset=ft.Offset(0, 8),
                                ),
                                alignment=ft.alignment.center,
                            ),

                            ft.Container(height=28),

                            self._title,
                            ft.Container(height=6),
                            self._location,
                            ft.Container(height=4),
                            self._tagline,

                            ft.Container(expand=True),   # middle spacer

                            # Progress bar pinned near the bottom
                            ft.Column(
                                [self._bar],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Container(height=40),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=0,
                        expand=True,
                    ),
                    padding=ft.padding.symmetric(horizontal=40, vertical=0),
                )
            ],
            padding=0,
            spacing=0,
        )

        # Kick off the animation + timer in a background thread
        threading.Thread(target=self._run, daemon=True).start()
        return view

    # ──────────────────────────────────────────────────────────────────
    def _run(self):
        """Fade everything in, animate the bar, then navigate."""
        try:
            # Short pause so the view has time to render before animating
            time.sleep(0.15)

            # Fade in logo + text
            self._logo.opacity     = 1
            self._title.opacity    = 1
            self._location.opacity = 1
            self._tagline.opacity  = 1
            self._bar.opacity      = 1
            self.page.update()

            # Animate the progress bar across ~2.8 s in small steps
            steps     = 28
            step_time = 2.8 / steps
            for i in range(1, steps + 1):
                if not getattr(self.app, '_splash_running', True):
                    break
                self._bar.value = i / steps
                self.page.update()
                time.sleep(step_time)

            # Navigate based on whether a session exists
            self.app._splash_running = False
            if self.app.current_user:
                self.page.go("/dashboard")
            else:
                self.page.go("/login")

        except Exception as ex:
            print(f"Splash error: {ex}")
            if self.app.current_user:
                self.page.go("/dashboard")
            else:
                self.page.go("/login")
