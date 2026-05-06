"""Settings view – fully functional with real DB persistence."""
import flet as ft
import threading
import shutil
import uuid
import traceback
from pathlib import Path
from datetime import datetime
from app import config


def _norm_role(role: str) -> str:
    return (role or "VIEWER").strip().upper()

def _is_admin_role(role: str) -> bool:
    return _norm_role(role) == "ADMIN"

# Username that is permanently protected — cannot be deleted, cannot be
# impersonated by a new account, and is always shown in the list.
_PROTECTED_USERNAME = "admin"


class SettingsView:
    def __init__(self, app):
        self.app  = app
        self.page = app.page
        self._editing_user_id = None
        self._role = _norm_role((app.current_user or {}).get("role", "VIEWER"))

        self._migrate_users_table()

        # ── School Settings ────────────────────────────────────────────────
        self.school_name    = ft.TextField(label="School Name", width=420, border_radius=8, dense=True)
        self.school_address = ft.TextField(label="Address", width=420, multiline=True,
                                           min_lines=2, max_lines=3, border_radius=8, dense=True)
        self.school_logo    = ft.TextField(label="Logo URL / Path", width=420, border_radius=8, dense=True)

        # ── Academic Calendar ──────────────────────────────────────────────
        self.term_dropdown   = ft.Dropdown(label="Term", width=190, border_radius=8, dense=True,
            options=[ft.dropdown.Option(t) for t in ["First Term","Second Term","Third Term"]])
        self.academic_year   = ft.TextField(label="Academic Year", width=190, border_radius=8, dense=True)
        self.periods_per_day = ft.TextField(label="Periods per Day", width=130,
                                            keyboard_type=ft.KeyboardType.NUMBER,
                                            border_radius=8, dense=True)
        self.break_periods   = ft.TextField(label="Break Periods (comma-separated)",
                                            hint_text="e.g. 4,6", width=210, border_radius=8, dense=True)

        # ── Sync Settings ──────────────────────────────────────────────────
        self.server_url    = ft.TextField(label="Server URL", width=420, border_radius=8, dense=True)
        self.auto_sync     = ft.Switch(label="Auto Sync", value=False)
        self.sync_interval = ft.TextField(label="Interval (minutes)", width=130,
                                          keyboard_type=ft.KeyboardType.NUMBER,
                                          border_radius=8, dense=True)
        self._conn_status  = ft.Text("", size=13)
        self._sync_status  = ft.Text("", size=13)
        self.test_conn_btn = ft.ElevatedButton(
            "Test Connection", icon=ft.icons.WIFI_ROUNDED,
            on_click=self.test_connection,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                bgcolor={"": "#2563EB", "hovered": "#1E40AF"},
                color=ft.colors.WHITE,
                elevation={"": 0, "hovered": 2}))
        self.sync_now_btn = ft.OutlinedButton(
            "Sync Now", icon=ft.icons.SYNC_ROUNDED,
            on_click=self.sync_now,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                side=ft.BorderSide(1, "#2563EB"),
                color="#2563EB"))

        # ── User Management ────────────────────────────────────────────────
        self.users_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Username", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Email",    weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Role",     weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Actions",  weight=ft.FontWeight.BOLD)),
            ],
            rows=[], column_spacing=20, horizontal_margin=10,
        )

        # ── User Dialog fields (reused for add/edit) ───────────────────────
        self._dlg_title    = ft.Text("Add User", size=16, weight=ft.FontWeight.BOLD)
        self._dlg_username = ft.TextField(label="Username",  width=340, border_radius=8)
        self._dlg_email    = ft.TextField(label="Email",     width=340, border_radius=8)
        self._dlg_password = ft.TextField(label="Password",  width=340, border_radius=8,
                                          password=True, can_reveal_password=True)
        _role_opts = (["ADMIN", "COORDINATOR", "VIEWER"]
                      if _is_admin_role(self._role) else ["COORDINATOR", "VIEWER"])
        self._dlg_role     = ft.Dropdown(label="Role", width=200,
            options=[ft.dropdown.Option(r) for r in _role_opts],
            value="VIEWER")
        self._dlg_err      = ft.Text("", color=ft.colors.RED, size=12)

        self._btn_save_user = ft.ElevatedButton(
            "Save",
            icon=ft.icons.SAVE_ROUNDED,
            on_click=self._save_user_animated,
            style=ft.ButtonStyle(
                bgcolor={"": "#2563EB", "hovered": "#1E40AF"},
                color=ft.colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8),
                elevation={"": 0, "hovered": 2}))

        self._user_dlg = ft.AlertDialog(
            modal=True,
            title=self._dlg_title,
            content=ft.Container(width=380, padding=ft.padding.symmetric(vertical=8),
                content=ft.Column([
                    self._dlg_username, self._dlg_email,
                    self._dlg_password, self._dlg_role, self._dlg_err,
                ], spacing=12, tight=True)),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self._close_dlg(),
                              style=ft.ButtonStyle(color=ft.colors.GREY_600)),
                self._btn_save_user,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # ── Backup & Restore ───────────────────────────────────────────────
        self.backup_location = ft.TextField(label="Backup Location", value="./backups",
                                            width=420, border_radius=8, dense=True)
        self._backup_status  = ft.Text("", size=13)
        self._file_picker    = ft.FilePicker(on_result=self._on_restore_picked)
        self.page.overlay.append(self._file_picker)

        # ── Card save buttons (stored for animation) ───────────────────────
        _save_btn_style = ft.ButtonStyle(
            bgcolor={"": "#2563EB", "hovered": "#1E40AF"},
            color=ft.colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=8),
            elevation={"": 0, "hovered": 2})

        self._btn_save_school = ft.ElevatedButton(
            "Save School Settings", icon=ft.icons.SAVE_ROUNDED,
            on_click=self._save_school_animated, style=_save_btn_style)

        self._btn_save_academic = ft.ElevatedButton(
            "Save Calendar Settings", icon=ft.icons.SAVE_ROUNDED,
            on_click=self._save_academic_animated, style=_save_btn_style)

        self._btn_save_sync = ft.ElevatedButton(
            "Save Sync Settings", icon=ft.icons.SAVE_ROUNDED,
            on_click=self._save_sync_animated, style=_save_btn_style)

        self._load_settings()
        self.load_users()

    # ══════════════════════════════════════════════════════════════════
    # DB HELPERS
    # ══════════════════════════════════════════════════════════════════
    def _db(self, sql, params=()):
        return self.app.local_db.execute(sql, params)

    def _migrate_users_table(self):
        """Create users table and ensure all required columns exist."""
        # Create base table (no password column = old schema still works)
        self._db("""
            CREATE TABLE IF NOT EXISTS users (
                id        TEXT PRIMARY KEY,
                username  TEXT NOT NULL UNIQUE,
                email     TEXT NOT NULL,
                role      TEXT NOT NULL DEFAULT 'VIEWER',
                is_active INTEGER NOT NULL DEFAULT 1
            )
        """)
        self._db("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY, value TEXT
            )
        """)

        # Add columns that may be missing in old databases — ignore if already exist
        for col_sql in [
            "ALTER TABLE users ADD COLUMN password  TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE users ADD COLUMN created_at TEXT DEFAULT (datetime('now'))",
        ]:
            try:
                self._db(col_sql)
            except Exception:
                pass  # column already exists

        # Seed default users if empty
        cnt = self._db("SELECT COUNT(*) as n FROM users")
        if cnt and cnt[0]["n"] == 0:
            for u in [
                (str(uuid.uuid4()), "admin",       "admin@school.edu",       "ADMIN",       "admin123"),
                (str(uuid.uuid4()), "coordinator",  "coordinator@school.edu", "COORDINATOR", "coord123"),
            ]:
                self._db("INSERT OR IGNORE INTO users (id,username,email,role,password,is_active) "
                         "VALUES (?,?,?,?,?,1)", u)

        # Fix blank passwords on existing seeded users
        self._db("UPDATE users SET password='admin123' "
                 "WHERE username='admin' AND (password IS NULL OR password='')")
        self._db("UPDATE users SET password='coord123' "
                 "WHERE username='coordinator' AND (password IS NULL OR password='')")
        self._db("UPDATE users SET is_active=1 WHERE is_active IS NULL")

    def _get(self, key, default=""):
        rows = self._db("SELECT value FROM app_settings WHERE key=?", (key,))
        return rows[0]["value"] if rows else default

    def _set(self, key, value):
        self._db("INSERT INTO app_settings (key,value) VALUES (?,?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                 (key, str(value)))

    def _load_settings(self):
        self.school_name.value     = self._get("school_name",    "Migrant Model Secondary School")
        self.school_address.value  = self._get("school_address", "123 Education Avenue, Lagos, Nigeria")
        self.school_logo.value     = self._get("school_logo",    "/assets/school_logo.png")
        self.term_dropdown.value   = self._get("term",           "First Term")
        self.academic_year.value   = self._get("academic_year",  "2025/2026")
        self.periods_per_day.value = self._get("periods_per_day","8")
        self.break_periods.value   = self._get("break_periods",  "4,6")
        self.server_url.value      = self._get("server_url",     getattr(self.app.api_client, "base_url", ""))
        self.auto_sync.value       = self._get("auto_sync",      "false") == "true"
        self.sync_interval.value   = self._get("sync_interval",  "30")
        self.backup_location.value = self._get("backup_location","./backups")

    # ══════════════════════════════════════════════════════════════════
    # USER MANAGEMENT
    # ══════════════════════════════════════════════════════════════════
    def load_users(self):
        try:
            users = self._db("SELECT * FROM users ORDER BY role, username") or []
        except Exception as ex:
            print(f"[settings] load_users: {ex}")
            users = []

        current_id   = (self.app.current_user or {}).get("id", "")
        current_user = self.app.current_user or {}
        viewer_is_admin      = _is_admin_role(self._role)
        viewer_is_coordinator = _norm_role(self._role) == "COORDINATOR"
        viewer_is_viewer      = _norm_role(self._role) == "VIEWER"

        ROLE_COLOR = {"ADMIN": "#DC2626", "COORDINATOR": "#2563EB"}
        rows = []
        for u in users:
            u = dict(u)
            role  = u.get("role", "VIEWER")
            uname = u.get("username", "")
            uid   = u.get("id", "")

            # ── VIEWER: only show their own row, no actions ────────────
            if viewer_is_viewer:
                if uid != current_id:
                    continue   # skip every other user entirely
                rows.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(uname)),
                    ft.DataCell(ft.Text(u.get("email", ""))),
                    ft.DataCell(ft.Container(
                        content=ft.Text(role, color=ft.colors.WHITE, size=11,
                                        weight=ft.FontWeight.W_500),
                        bgcolor=ROLE_COLOR.get(role, "#16A34A"),
                        padding=ft.padding.symmetric(horizontal=8, vertical=3),
                        border_radius=12)),
                    ft.DataCell(ft.Text("—", color=ft.colors.GREY_400, size=12)),
                ]))
                continue   # done — only one row for viewer

            # ── COORDINATOR: cannot see Admin rows ─────────────────────
            if viewer_is_coordinator and _norm_role(role) == "ADMIN":
                continue

            is_protected = (uname.lower() == _PROTECTED_USERNAME)

            # ── Action buttons ─────────────────────────────────────────
            if viewer_is_admin:
                actions = ft.Row([
                    ft.IconButton(ft.icons.EDIT, icon_size=18, tooltip="Edit",
                                  on_click=lambda e, usr=u: self._require_auth(
                                      lambda: self._open_edit_dlg(usr))),
                    ft.IconButton(
                        ft.icons.LOCK_OUTLINED if is_protected else ft.icons.DELETE,
                        icon_size=18,
                        tooltip="Protected — cannot delete" if is_protected else "Delete",
                        icon_color=ft.colors.GREY_400 if is_protected else ft.colors.RED_400,
                        disabled=is_protected,
                        on_click=(None if is_protected else
                                  lambda e, usr=u: self._require_auth(
                                      lambda: self._confirm_delete(usr))),
                    ),
                ])
            else:
                # Coordinator: can edit/delete fellow coordinators and viewers only
                can_act = _norm_role(role) in ("COORDINATOR", "VIEWER") and not is_protected
                actions = ft.Row([
                    ft.IconButton(ft.icons.EDIT, icon_size=18, tooltip="Edit",
                                  disabled=not can_act,
                                  icon_color="#2563EB" if can_act else ft.colors.GREY_300,
                                  on_click=(lambda e, usr=u: self._require_auth(
                                      lambda: self._open_edit_dlg(usr))) if can_act else None),
                    ft.IconButton(ft.icons.DELETE, icon_size=18, tooltip="Delete",
                                  disabled=not can_act,
                                  icon_color=ft.colors.RED_400 if can_act else ft.colors.GREY_300,
                                  on_click=(lambda e, usr=u: self._require_auth(
                                      lambda: self._confirm_delete(usr))) if can_act else None),
                ])

            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(uname)),
                ft.DataCell(ft.Text(u.get("email", ""))),
                ft.DataCell(ft.Container(
                    content=ft.Text(role, color=ft.colors.WHITE, size=11,
                                    weight=ft.FontWeight.W_500),
                    bgcolor=ROLE_COLOR.get(role, ft.colors.GREEN_600),
                    padding=ft.padding.symmetric(horizontal=8, vertical=3),
                    border_radius=12)),
                ft.DataCell(actions),
            ]))
        self.users_table.rows = rows

    # ══════════════════════════════════════════════════════════════════
    # CREDENTIAL GATE  (re-auth before any user management action)
    # ══════════════════════════════════════════════════════════════════
    def _require_auth(self, on_success):
        """Show a re-authentication dialog. Calls on_success() only if credentials match."""
        auth_user  = ft.TextField(
            label="Your Username", width=320, border_radius=8,
            value=(self.app.current_user or {}).get("username", ""),
            read_only=True,
        )
        auth_pass  = ft.TextField(
            label="Your Password", width=320, border_radius=8,
            password=True, can_reveal_password=True,
        )
        auth_err   = ft.Text("", color=ft.colors.RED, size=12)

        def _verify(e):
            entered_pw = auth_pass.value.strip()
            cu = self.app.current_user or {}
            uname = cu.get("username", "")

            # Look up the live password for the currently logged-in user
            rows = self._db(
                "SELECT password FROM users WHERE username=? AND is_active=1", (uname,))
            stored_pw = rows[0]["password"] if rows else None

            # Also accept the hardcoded fallback for the protected admin
            if stored_pw is None and uname.lower() == _PROTECTED_USERNAME:
                stored_pw = "admin123"

            ok = (stored_pw is not None and entered_pw == stored_pw)
            if not ok:
                auth_err.value = "Incorrect password. Please try again."
                auth_pass.value = ""
                self.page.update()
                return

            # Credentials verified — close gate and proceed
            auth_dlg.open = False
            self.page.update()
            on_success()

        def _cancel(e):
            auth_dlg.open = False
            self.page.update()

        auth_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.icons.LOCK_PERSON, color=ft.colors.BLUE_700),
                ft.Text("Confirm Your Identity", size=15, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                width=360,
                padding=ft.padding.symmetric(vertical=8),
                content=ft.Column([
                    ft.Text("Enter your password to continue.", size=13, color=ft.colors.GREY_700),
                    auth_user,
                    auth_pass,
                    auth_err,
                ], spacing=12, tight=True),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=_cancel),
                ft.ElevatedButton(
                    "Verify & Continue",
                    icon=ft.icons.VERIFIED_USER,
                    on_click=_verify,
                    style=ft.ButtonStyle(
                        bgcolor={"": "#2563EB", "hovered": "#1E40AF"},
                        color=ft.colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=8),
                        elevation={"": 0, "hovered": 2}),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = auth_dlg
        auth_dlg.open = True
        self.page.update()

    def _open_add_dlg(self, e=None):
        self._require_auth(self._do_open_add_dlg)

    def _do_open_add_dlg(self):
        self._editing_user_id       = None
        self._dlg_title.value       = "Add User"
        self._dlg_username.value    = ""
        self._dlg_email.value       = ""
        self._dlg_password.value    = ""
        self._dlg_role.value        = "VIEWER"
        self._dlg_err.value         = ""
        self._dlg_username.read_only = False
        self._dlg_password.label    = "Password"
        self._show_dlg()

    def _open_edit_dlg(self, user):
        self._editing_user_id        = user["id"]
        self._dlg_title.value        = "Edit User"
        self._dlg_username.value     = user.get("username", "")
        self._dlg_email.value        = user.get("email", "")
        self._dlg_password.value     = ""
        self._dlg_role.value         = user.get("role", "VIEWER")
        self._dlg_err.value          = ""
        self._dlg_username.read_only = True
        self._dlg_password.label     = "Password (blank = keep current)"
        self._show_dlg()

    def _show_dlg(self):
        self.page.dialog = self._user_dlg
        self._user_dlg.open = True
        self.page.update()

    def _close_dlg(self):
        self._user_dlg.open = False
        self.page.update()

    def _save_user(self, e):
        username = self._dlg_username.value.strip()
        email    = self._dlg_email.value.strip()
        password = self._dlg_password.value.strip()
        role     = self._dlg_role.value or "VIEWER"

        if not username or not email:
            self._dlg_err.value = "Username and email are required."
            self.page.update()
            return
        if not self._editing_user_id and not password:
            self._dlg_err.value = "Password is required for new users."
            self.page.update()
            return

        # Block anyone from creating a new account with the protected username
        if not self._editing_user_id and username.lower() == _PROTECTED_USERNAME:
            self._dlg_err.value = f"Username '{_PROTECTED_USERNAME}' is reserved and cannot be used."
            self.page.update()
            return

        # Coordinators cannot assign or change role to ADMIN
        if not _is_admin_role(self._role) and _norm_role(role) == "ADMIN":
            self._dlg_err.value = "You do not have permission to assign the ADMIN role."
            self.page.update()
            return

        try:
            if self._editing_user_id:
                # Protect the admin record from role/username tampering
                target_row = self._db("SELECT username FROM users WHERE id=?",
                                      (self._editing_user_id,))
                target_uname = (target_row[0]["username"] if target_row else "").lower()
                if target_uname == _PROTECTED_USERNAME and _norm_role(role) != "ADMIN":
                    self._dlg_err.value = "The admin account's role cannot be changed."
                    self.page.update()
                    return

                if password:
                    self._db("UPDATE users SET email=?, role=?, password=? WHERE id=?",
                             (email, role, password, self._editing_user_id))
                else:
                    self._db("UPDATE users SET email=?, role=? WHERE id=?",
                             (email, role, self._editing_user_id))
                self._snack(f"User '{username}' updated.", ft.colors.GREEN)
            else:
                existing = self._db("SELECT id FROM users WHERE username=?", (username,))
                if existing:
                    self._dlg_err.value = "Username already exists."
                    self.page.update()
                    return
                self._db("INSERT INTO users (id,username,email,role,password,is_active) "
                         "VALUES (?,?,?,?,?,1)",
                         (str(uuid.uuid4()), username, email, role, password))
                self._snack(f"User '{username}' added.", ft.colors.GREEN)

            self._close_dlg()
            self.load_users()
            self.page.update()

        except Exception as ex:
            self._dlg_err.value = f"Error: {ex}"
            self.page.update()

    def _confirm_delete(self, user):
        uid      = user["id"]
        username = user.get("username", "")
        role     = user.get("role", "VIEWER")

        # Hard block: the protected admin account can never be deleted
        if username.lower() == _PROTECTED_USERNAME:
            self._snack("The admin account is protected and cannot be deleted.", ft.colors.RED)
            return

        # Coordinator cannot delete an Admin
        if not _is_admin_role(self._role) and _norm_role(role) == "ADMIN":
            self._snack("You do not have permission to delete an Admin account.", ft.colors.RED)
            return

        # Is this the currently logged-in user deleting their own account?
        current_uid = (self.app.current_user or {}).get("id", "")
        is_self = (uid == current_uid)

        warning_text = (
            f"You are deleting YOUR OWN account ('{username}'). "
            "You will be logged out immediately. Continue?"
            if is_self else
            f"Delete '{username}'? This cannot be undone."
        )

        def do_delete(e):
            dlg.open = False
            self.page.update()
            try:
                self._db("DELETE FROM users WHERE id=?", (uid,))

                # ── Broadcast logout to every session logged in as this user ──
                # Any page subscribed to "force_logout" will check and kick itself.
                try:
                    self.page.pubsub.send_all_on_topic("force_logout", uid)
                except Exception:
                    pass  # pubsub unavailable in some desktop modes — fall through

                # ── Also handle this session directly if it IS the deleted user ──
                if uid == (self.app.current_user or {}).get("id", ""):
                    self.app.current_user = None
                    self.page.go("/login")
                    return

                self.load_users()
                self._snack(f"User '{username}' deleted.", ft.colors.GREEN)
                self.page.update()
            except Exception as ex:
                self._snack(f"Error: {ex}", ft.colors.RED)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(
                "Delete Your Own Account" if is_self else "Delete User",
                color=ft.colors.RED_700),
            content=ft.Text(warning_text),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: [setattr(dlg, "open", False), self.page.update()]),
                ft.ElevatedButton("Delete", icon=ft.icons.DELETE, on_click=do_delete,
                    style=ft.ButtonStyle(bgcolor=ft.colors.RED_700, color=ft.colors.WHITE)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()


    # ══════════════════════════════════════════════════════════════════
    # BUTTON ANIMATION HELPERS
    # ══════════════════════════════════════════════════════════════════
    async def _animate_elevated_btn(self, btn, save_fn, e):
        """Spinner → save logic → success flash → reset."""
        import asyncio
        orig_text  = btn.text
        orig_icon  = btn.icon
        btn.text     = "Saving..."
        btn.icon     = ft.icons.HOURGLASS_TOP_ROUNDED
        btn.disabled = True
        btn.style.bgcolor = {"": "#64748B", "hovered": "#475569"}
        self.page.update()
        await asyncio.sleep(0.15)
        save_fn(e)
        btn.text     = "Saved ✓"
        btn.icon     = ft.icons.CHECK_CIRCLE_ROUNDED
        btn.disabled = False
        btn.style.bgcolor = {"": "#16A34A", "hovered": "#15803D"}
        self.page.update()
        await asyncio.sleep(1.4)
        btn.text     = orig_text
        btn.icon     = orig_icon
        btn.style.bgcolor = {"": "#2563EB", "hovered": "#1E40AF"}
        self.page.update()

    async def _save_school_animated(self, e):
        await self._animate_elevated_btn(self._btn_save_school, self.save_school_settings, e)

    async def _save_academic_animated(self, e):
        await self._animate_elevated_btn(self._btn_save_academic, self.save_academic_settings, e)

    async def _save_sync_animated(self, e):
        await self._animate_elevated_btn(self._btn_save_sync, self.save_sync_settings, e)

    async def _save_user_animated(self, e):
        await self._animate_elevated_btn(self._btn_save_user, self._save_user, e)

    # ══════════════════════════════════════════════════════════════════
    # SAVE HANDLERS
    # ══════════════════════════════════════════════════════════════════
    def save_school_settings(self, e):
        self._set("school_name",    self.school_name.value.strip())
        self._set("school_address", self.school_address.value.strip())
        self._set("school_logo",    self.school_logo.value.strip())
        self._snack("School settings saved ✓", ft.colors.GREEN)

    def save_academic_settings(self, e):
        ppd = self.periods_per_day.value.strip()
        if not ppd.isdigit() or int(ppd) < 1:
            self._snack("Periods per day must be a positive number.", ft.colors.RED)
            return
        term = self.term_dropdown.value or ""
        year = self.academic_year.value.strip()
        bp   = self.break_periods.value.strip()
        # Primary keys (used by timetable generator)
        self._set("term",            term)
        self._set("academic_year",   year)
        self._set("periods_per_day", ppd)
        self._set("break_periods",   bp)
        # Mirror keys (kept in sync with Academic Calendar screen)
        self._set("calendar_term",   term)
        self._set("calendar_year",   year)
        self._snack("Academic settings saved ✓", ft.colors.GREEN)

    def save_sync_settings(self, e):
        url = self.server_url.value.strip()
        self._set("server_url",    url)
        self._set("auto_sync",     "true" if self.auto_sync.value else "false")
        self._set("sync_interval", self.sync_interval.value.strip())
        self.app.api_client.base_url = url
        self._snack("Sync settings saved ✓", ft.colors.GREEN)
        # Re-probe immediately so offline_mode reflects the new URL
        if url:
            self._conn_status.value = "Probing server…"
            self._conn_status.color = ft.colors.GREY_600
            self.page.update()
            def _probe():
                online = self.app.api_client.probe()
                self._conn_status.value = ("✓ Server reachable"
                                           if online else
                                           "✗ Server unreachable — working offline")
                self._conn_status.color = (ft.colors.GREEN
                                           if online else ft.colors.ORANGE)
                self.page.update()
            threading.Thread(target=_probe, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════
    # SYNC
    # ══════════════════════════════════════════════════════════════════
    def test_connection(self, e):
        url = self.server_url.value.strip()
        if not url:
            self._conn_status.value = "No server URL configured."
            self._conn_status.color = ft.colors.ORANGE
            self.page.update()
            return
        self._conn_status.value = "Testing…"
        self._conn_status.color = ft.colors.GREY_600
        self.test_conn_btn.disabled = True
        self.page.update()

        def _ping():
            import urllib.request, urllib.error, ssl
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                health_url = url.rstrip("/") + "/health"
                req = urllib.request.Request(health_url,
                                             headers={"User-Agent": "SmartTimetable/1.0"})
                with urllib.request.urlopen(req, timeout=6, context=ctx) as resp:
                    import json as _json
                    data = _json.loads(resp.read().decode())
                if data.get("status") == "healthy":
                    self._conn_status.value = "✓ Server reachable and healthy"
                else:
                    self._conn_status.value = "✓ Server reachable"
                self._conn_status.color = ft.colors.GREEN
            except urllib.error.HTTPError as ex:
                self._conn_status.value = f"✗ Server error (HTTP {ex.code})"
                self._conn_status.color = ft.colors.RED
            except Exception as ex:
                self._conn_status.value = f"✗ Error: {ex}"
                self._conn_status.color = ft.colors.RED
            finally:
                self.test_conn_btn.disabled = False
                self.page.update()

        threading.Thread(target=_ping, daemon=True).start()

    def sync_now(self, e):
        url = self.server_url.value.strip()
        if not url:
            self._sync_status.value = "No server URL — save Sync Settings first."
            self._sync_status.color = ft.colors.ORANGE
            self.page.update()
            return
        self._sync_status.value = "Connecting to server… (may take up to 30s on first connect)"
        self._sync_status.color = ft.colors.GREY_600
        self.sync_now_btn.disabled = True
        self.page.update()

        def _do_sync():
            try:
                self.app.api_client.base_url = url
                # Pre-warm: hit /health to wake Neon before login/sync
                self._sync_status.value = "Waking up server…"
                try: self.page.update()
                except Exception: pass
                # Try up to 3 times to get a healthy response
                for _attempt in range(3):
                    h = self.app.api_client._request(
                        "GET", "/health", timeout=15)
                    if not h.get("error"):
                        break
                    import time; time.sleep(3)
                # Ensure we have a token — read password from DB, not
                # current_user (which may not carry plaintext password)
                if not getattr(self.app.api_client, "token", None):
                    cu    = self.app.current_user or {}
                    uname = cu.get("username", "admin")
                    # Try DB first, fall back to hardcoded default
                    rows  = self._db(
                        "SELECT password FROM users WHERE username=? AND is_active=1",
                        (uname,))
                    pw = (rows[0]["password"] if rows else None) or \
                         ("admin123" if uname == "admin" else "")
                    self._sync_status.value = "Logging in to server…"
                    try: self.page.update()
                    except Exception: pass
                    # Use a generous timeout — Neon cold starts can take 10-15s
                    self.app.api_client._ssl_ctx  # ensure client is initialised
                    old_timeout = 20  # increased from 10
                    login_result = self.app.api_client._request(
                        "POST", "/auth/login",
                        {"username": uname, "password": pw},
                        timeout=30)
                    if "access_token" in login_result:
                        self.app.api_client.token = login_result["access_token"]
                        self.app.api_client.offline_mode = False
                        self.app.api_client.school_id = "__server__"
                    if login_result.get("error"):
                        self._sync_status.value = (
                            "✗ Login failed — check server credentials.")
                        self._sync_status.color = ft.colors.RED
                        return

                self._sync_status.value = (
                    "Syncing data to server… "
                    "(pushing tables one by one — please wait)")
                try: self.page.update()
                except Exception: pass
                result = self.app.api_client.sync(self.app.local_db)
                if result.get("error"):
                    msg = str(result.get("message", ""))
                    if "401" in msg or "Unauthorized" in msg:
                        self._sync_status.value = "✗ Not authorised — check server credentials."
                    else:
                        self._sync_status.value = f"✗ Sync failed: {msg}"
                    self._sync_status.color = ft.colors.RED
                    self.app.api_client.offline_mode = True
                else:
                    pushed  = result.get("pushed", 0)
                    pulled  = result.get("pulled", 0)
                    warns   = result.get("warnings", [])
                    self._sync_status.value = (
                        f"✓ Sync complete — ↑ {pushed} pushed, ↓ {pulled} pulled"
                        + (f"  ({len(warns)} warnings)" if warns else "")
                    )
                    self._sync_status.color = ft.colors.GREEN
                    self.app.api_client.offline_mode = False
                    try:
                        self.page.pubsub.send_all_on_topic("sync_status", "online")
                    except Exception:
                        pass
            except Exception as ex:
                self._sync_status.value = f"✗ Sync error: {ex}"
                self._sync_status.color = ft.colors.RED
                self.app.api_client.offline_mode = True
            finally:
                self.sync_now_btn.disabled = False
                self.page.update()

        threading.Thread(target=_do_sync, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════
    # BACKUP & RESTORE
    # ══════════════════════════════════════════════════════════════════
    def _db_path(self):
        db = self.app.local_db
        for attr in ("db_path", "path", "database", "db_file"):
            p = getattr(db, attr, None)
            if p and Path(str(p)).exists():
                return Path(str(p))
        for pattern in ("*.db", "*.sqlite", "*.sqlite3"):
            found = list(Path(".").rglob(pattern))
            if found:
                return found[0]
        return None

    def backup_db(self, e):
        src = self._db_path()
        if not src:
            self._backup_status.value = "✗ Cannot locate database file."
            self._backup_status.color = ft.colors.RED
            self.page.update()
            return
        dest_dir = Path(self.backup_location.value.strip() or "./backups")
        dest_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest  = dest_dir / f"timetable_backup_{stamp}.db"
        try:
            shutil.copy2(str(src), str(dest))
            ts = datetime.now().strftime("%d %b %Y %H:%M")
            self._set("last_backup",      ts)
            self._set("backup_location",  str(dest_dir))
            self._backup_status.value = f"✓ Backup saved → {dest}"
            self._backup_status.color = ft.colors.GREEN
            self._snack("Database backed up ✓", ft.colors.GREEN)
        except Exception as ex:
            self._backup_status.value = f"✗ Backup failed: {ex}"
            self._backup_status.color = ft.colors.RED
        self.page.update()

    def restore_db(self, e):
        self._file_picker.pick_files(
            dialog_title="Select backup file to restore",
            allowed_extensions=["db", "sqlite", "sqlite3"],
            allow_multiple=False,
        )

    def _on_restore_picked(self, ev: ft.FilePickerResultEvent):
        if not ev.files:
            return
        src    = Path(ev.files[0].path)
        db_dst = self._db_path()
        if not db_dst:
            self._snack("Cannot locate active database.", ft.colors.RED)
            return

        def do_restore(e):
            dlg.open = False
            self.page.update()
            try:
                safety = db_dst.parent / f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                shutil.copy2(str(db_dst), str(safety))
                shutil.copy2(str(src), str(db_dst))
                self._snack("Restore complete — please restart the app.", ft.colors.TEAL)
            except Exception as ex:
                self._snack(f"Restore failed: {ex}", ft.colors.RED)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirm Restore", color=ft.colors.ORANGE_700),
            content=ft.Text(f"Restore from '{src.name}'?\n\n"
                            "Current DB will be backed up automatically.\n"
                            "App must restart after restore."),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: [setattr(dlg, "open", False), self.page.update()]),
                ft.ElevatedButton("Restore", icon=ft.icons.RESTORE, on_click=do_restore,
                    style=ft.ButtonStyle(bgcolor=ft.colors.ORANGE_700, color=ft.colors.WHITE)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    # ══════════════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════════════
    def _snack(self, msg, color=ft.colors.GREEN):
        self.page.show_snack_bar(ft.SnackBar(content=ft.Text(msg), bgcolor=color, duration=3000))

    def _card(self, title, icon, controls):
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
            padding=20, bgcolor=ft.colors.WHITE, border_radius=12,
            border=ft.border.all(1, ft.colors.GREY_200),
            shadow=ft.BoxShadow(
                spread_radius=0, blur_radius=8,
                color=ft.colors.with_opacity(0.06, ft.colors.BLACK),
                offset=ft.Offset(0, 2)),
            margin=ft.margin.only(bottom=16),
        )

    # ══════════════════════════════════════════════════════════════════
    # BUILD
    # ══════════════════════════════════════════════════════════════════
    def build(self):
        return ft.View(
            "/settings",
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
                        ft.Icon(ft.icons.SETTINGS_ROUNDED,
                                color=ft.colors.WHITE, size=20),
                        ft.Text("Settings", size=17,
                                weight=ft.FontWeight.BOLD,
                                color=ft.colors.WHITE),
                        ft.Container(expand=True),
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.icons.INFO_OUTLINE,
                                        color=ft.colors.with_opacity(0.6, ft.colors.WHITE),
                                        size=16),
                                ft.Text(f"v{config.APP_VERSION}",
                                        color=ft.colors.with_opacity(0.6, ft.colors.WHITE),
                                        size=12),
                            ], spacing=4),
                            padding=ft.padding.only(right=8),
                        ),
                    ], spacing=6,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor="#0F1E3A",
                    padding=ft.padding.symmetric(horizontal=16, vertical=10),
                    height=56,
                ),
                ft.Container(
                    content=ft.ListView(controls=[

                        self._card("School Settings", ft.icons.SCHOOL, [
                            self.school_name, self.school_address, self.school_logo,
                            ft.Row([self._btn_save_school],
                                   alignment=ft.MainAxisAlignment.END),
                        ]),

                        self._card("Academic Calendar", ft.icons.CALENDAR_MONTH, [
                            ft.Row([self.term_dropdown, self.academic_year], spacing=10),
                            ft.Row([self.periods_per_day, self.break_periods], spacing=10),
                            ft.Text("Break periods: comma-separated period numbers",
                                    size=12, color=ft.colors.GREY_500, italic=True),
                            ft.Row([self._btn_save_academic],
                                   alignment=ft.MainAxisAlignment.END),
                        ]),

                        self._card("Sync Settings", ft.icons.SYNC, [
                            self.server_url,
                            ft.Row([self.auto_sync, self.sync_interval], spacing=16),
                            ft.Row([self._btn_save_sync],
                                   alignment=ft.MainAxisAlignment.END),
                            ft.Divider(height=6, color=ft.colors.GREY_200),
                            ft.Row([self.test_conn_btn, self.sync_now_btn], spacing=10),
                            self._conn_status, self._sync_status,
                        ]),

                        self._card("User Management", ft.icons.PEOPLE, [
                            ft.Row([
                                ft.Text(
                                    "Manage app users" if _norm_role(self._role) != "VIEWER"
                                    else "Your account details",
                                    size=13, color=ft.colors.GREY_500, expand=True),
                                # Only ADMIN and COORDINATOR can add users
                                ft.ElevatedButton(
                                    "+ Add User", icon=ft.icons.PERSON_ADD_ROUNDED,
                                    on_click=self._open_add_dlg,
                                    visible=_norm_role(self._role) in ("ADMIN", "COORDINATOR"),
                                    style=ft.ButtonStyle(
                                        bgcolor={"": "#2563EB", "hovered": "#1E40AF"},
                                        color=ft.colors.WHITE,
                                        shape=ft.RoundedRectangleBorder(radius=8),
                                        elevation={"": 0, "hovered": 2})),
                            ]),
                            ft.Container(
                                content=ft.Column([self.users_table],
                                                  scroll=ft.ScrollMode.AUTO),
                                border=ft.border.all(1, ft.colors.GREY_200),
                                border_radius=8, padding=4),
                        ]),

                        self._card("Backup & Restore", ft.icons.BACKUP, [
                            self.backup_location,
                            ft.Row([
                                ft.ElevatedButton(
                                    "Backup Database", icon=ft.icons.UPLOAD_FILE_ROUNDED,
                                    on_click=self.backup_db,
                                    style=ft.ButtonStyle(
                                        bgcolor={"": "#2563EB", "hovered": "#1E40AF"},
                                        color=ft.colors.WHITE,
                                        shape=ft.RoundedRectangleBorder(radius=8),
                                        elevation={"": 0, "hovered": 2})),
                                ft.OutlinedButton(
                                    "Restore Database", icon=ft.icons.DOWNLOAD_ROUNDED,
                                    on_click=self.restore_db,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=8),
                                        side=ft.BorderSide(1, "#2563EB"),
                                        color="#2563EB")),
                            ], spacing=10),
                            self._backup_status,
                        ]),

                        self._card("About", ft.icons.INFO_OUTLINE, [
                            ft.Row([
                                ft.Image(
                                    src="MMSSlogo.jpg",
                                    width=44, height=44,
                                    fit=ft.ImageFit.CONTAIN,
                                    border_radius=ft.border_radius.all(6),
                                ),
                                ft.Column([
                                    ft.Text("Smart Timetable Generator", size=15,
                                            weight=ft.FontWeight.W_600, color="#0F1E3A"),
                                    ft.Text(f"Version {config.APP_VERSION}",
                                            size=12, color=ft.colors.GREY_500),
                                ], spacing=2),
                            ], spacing=14),
                            ft.Divider(height=8, color=ft.colors.GREY_200),
                            ft.Text("© 2026 Model Migrant Secondary School",
                                    size=12, color=ft.colors.GREY_600),
                            ft.Text("Developed for Nigerian Secondary Schools",
                                    size=12, italic=True, color=ft.colors.GREY_500),
                            ft.Text(f"Last backup: {self._get('last_backup','Never')}",
                                    size=12, color=ft.colors.GREY_400),
                        ]),

                    ], spacing=0, padding=20, expand=True),
                    expand=True, bgcolor="#F8FAFC",
                ),
            ],
            padding=0, spacing=0,
        )