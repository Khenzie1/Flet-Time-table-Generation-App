"""Teachers management view - Full working version."""
import flet as ft
import uuid

def _norm_role(role: str) -> str:
    """Normalise role string to uppercase regardless of source."""
    return (role or "VIEWER").strip().upper()

def _can_edit(role: str) -> bool:
    """Admin and Coordinator may mutate data; Viewer is read-only."""
    return _norm_role(role) in ("ADMIN", "COORDINATOR")



class TeachersView:
    """Teachers management screen."""
    
    def __init__(self, app):
        self.app = app
        self.page = app.page
        self._role = _norm_role((app.current_user or {}).get("role", "VIEWER"))
        self.search_field = ft.TextField(
            hint_text="Search teachers...",
            prefix_icon=ft.icons.SEARCH,
            expand=True,
            on_change=self.search_teachers
        )
        self.teachers_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("")),
                ft.DataColumn(ft.Text("Code",        size=13, weight=ft.FontWeight.W_600, color="#0F1E3A")),
                ft.DataColumn(ft.Text("Name",        size=13, weight=ft.FontWeight.W_600, color="#0F1E3A")),
                ft.DataColumn(ft.Text("Email",       size=13, weight=ft.FontWeight.W_600, color="#0F1E3A")),
                ft.DataColumn(ft.Text("Phone",       size=13, weight=ft.FontWeight.W_600, color="#0F1E3A")),
                ft.DataColumn(ft.Text("Max Periods", size=13, weight=ft.FontWeight.W_600, color="#0F1E3A")),
                ft.DataColumn(ft.Text("Subjects",    size=13, weight=ft.FontWeight.W_600, color="#0F1E3A")),
                ft.DataColumn(ft.Text("Status",      size=13, weight=ft.FontWeight.W_600, color="#0F1E3A")),
                ft.DataColumn(ft.Text("Actions",     size=13, weight=ft.FontWeight.W_600, color="#0F1E3A")),
            ],
            rows=[],
            heading_row_color="#EFF6FF",
            heading_row_height=52,
            data_row_min_height=52,
            data_row_max_height=52,
            column_spacing=20,
            horizontal_margin=16,
            divider_thickness=1,
            show_checkbox_column=False,
        )
        self.filter_dropdown = ft.Dropdown(
            width=150,
            label="Filter",
            options=[
                ft.dropdown.Option("All"),
                ft.dropdown.Option("Active"),
                ft.dropdown.Option("Inactive"),
            ],
            value="All",
            on_change=self.filter_teachers
        )
        
        # Add/Edit Dialog — save button stored for animation
        self._btn_save_teacher = ft.ElevatedButton(
            "Save",
            icon=ft.icons.SAVE_ROUNDED,
            on_click=self._save_teacher_animated,
            style=ft.ButtonStyle(
                bgcolor={"": "#2563EB", "hovered": "#1E40AF"},
                color=ft.colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8),
                elevation={"": 0, "hovered": 2},
            ),
        )

        # Add/Edit Dialog fields
        self.dialog = ft.AlertDialog(
            title=ft.Text("Add Teacher"),
            content=ft.Container(
                width=500,
                height=600,
                content=ft.Column([
                    ft.TextField(label="Teacher Code", autofocus=True),
                    ft.TextField(label="Full Name"),
                    ft.TextField(label="Email"),
                    ft.TextField(
                        label="Phone Number",
                        hint_text="e.g., 08012345678",
                        keyboard_type=ft.KeyboardType.PHONE,
                    ),
                    ft.TextField(
                        label="Max Daily Periods",
                        value="6",
                        keyboard_type=ft.KeyboardType.NUMBER
                    ),
                    ft.Dropdown(
                        label="Status",
                        options=[
                            ft.dropdown.Option("Active", "1"),
                            ft.dropdown.Option("Inactive", "0"),
                        ],
                        value="1"
                    ),
                    ft.Text("Subjects", size=16, weight=ft.FontWeight.BOLD),
                    ft.ListView(
                        height=200,
                        spacing=5
                    ),
                ], spacing=10, scroll=ft.ScrollMode.AUTO),
                padding=20
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self.close_dialog,
                              style=ft.ButtonStyle(color=ft.colors.GREY_600)),
                self._btn_save_teacher,
            ]
        )
        
        # Unavailability Dialog
        self.unavail_dialog = ft.AlertDialog(
            title=ft.Text("Teacher Unavailability"),
            content=ft.Container(
                width=400,
                height=500,
                content=ft.Column([
                    ft.Dropdown(
                        label="Day",
                        options=[
                            ft.dropdown.Option("Monday"),
                            ft.dropdown.Option("Tuesday"),
                            ft.dropdown.Option("Wednesday"),
                            ft.dropdown.Option("Thursday"),
                            ft.dropdown.Option("Friday"),
                        ],
                    ),
                    ft.TextField(
                        label="Period Number",
                        keyboard_type=ft.KeyboardType.NUMBER
                    ),
                    ft.TextField(label="Reason"),
                    ft.ElevatedButton(
                        "Add Unavailability",
                        icon=ft.icons.ADD,
                        on_click=self.add_unavailability
                    ),
                    ft.Divider(),
                    ft.Text("Current Unavailability", size=16, weight=ft.FontWeight.BOLD),
                    ft.ListView(height=200, spacing=5)
                ]),
                padding=20
            ),
            actions=[
                ft.TextButton("Close", on_click=self.close_unavail_dialog),
            ]
        )
        
        self.current_teacher_id = None
        self.all_teachers = []
        self.selected_ids = set()

        # Refresh button — stored so refresh() can animate it
        self._btn_refresh = ft.IconButton(
            icon=ft.icons.REFRESH_ROUNDED,
            icon_color=ft.colors.WHITE, icon_size=18,
            tooltip="Refresh",
            on_click=self.refresh,
        )

        # ── Bulk-select action bar (hidden until a checkbox is ticked) ─────
        self._sel_count_lbl = ft.Text(
            "0 selected", size=14, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE)
        self._sel_bar = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.CHECK_BOX_OUTLINED, color=ft.colors.WHITE, size=20),
                self._sel_count_lbl,
                ft.Container(expand=True),
                ft.TextButton("Clear selection",
                    style=ft.ButtonStyle(color=ft.colors.WHITE70),
                    on_click=self._clear_selection),
                ft.ElevatedButton(
                    "Delete Selected",
                    icon=ft.icons.DELETE_SWEEP,
                    on_click=self._bulk_delete_confirm,
                    style=ft.ButtonStyle(
                        bgcolor=ft.colors.RED_700,
                        color=ft.colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                ),
            ], spacing=12),
            bgcolor="#0F1E3A",
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=20, vertical=10),
            visible=False,
            margin=ft.margin.only(bottom=10),
        )
        
        # Store references to dialog controls for later access
        self.subject_list = None
        self.unavail_list = None

        # Live count labels — updated by display_teachers() on every data change
        self._lbl_count_top   = ft.Text(
            "0 teachers", size=12,
            color=ft.colors.with_opacity(0.6, ft.colors.WHITE))
        self._lbl_count_table = ft.Text(
            "Total: 0 teachers", size=13,
            color=ft.colors.GREY_500, weight=ft.FontWeight.W_500)
        
    def build(self):
        """Build the teachers view."""
        self.load_teachers()
        
        # Store references to list views for later access
        if hasattr(self.dialog.content.content, 'controls'):
            self.subject_list = self.dialog.content.content.controls[7]
        if hasattr(self.unavail_dialog.content.content, 'controls'):
            self.unavail_list = self.unavail_dialog.content.content.controls[5]
        
        # Add dialogs to page overlay
        if self.dialog not in self.page.overlay:
            self.page.overlay.append(self.dialog)
        if self.unavail_dialog not in self.page.overlay:
            self.page.overlay.append(self.unavail_dialog)
        
        return ft.View(
            "/teachers",
            [
                # ── Navy top bar (matches dashboard) ──────────────────
                ft.Container(
                    content=ft.Row([
                        ft.IconButton(
                            icon=ft.icons.ARROW_BACK_ROUNDED,
                            icon_color=ft.colors.WHITE,
                            icon_size=20,
                            tooltip="Back to Dashboard",
                            on_click=lambda e: self.page.go("/dashboard"),
                        ),
                        ft.Container(width=4),
                        ft.Icon(ft.icons.PEOPLE_ALT_ROUNDED,
                                color=ft.colors.WHITE, size=20),
                        ft.Text("Teachers Management", size=17,
                                weight=ft.FontWeight.BOLD,
                                color=ft.colors.WHITE),
                        ft.Container(expand=True),
                        self._lbl_count_top,
                        ft.Container(width=8),
                        self._btn_refresh,
                    ], spacing=6,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor="#0F1E3A",
                    padding=ft.padding.symmetric(horizontal=16, vertical=10),
                    height=56,
                ),

                ft.Container(
                    content=ft.Column([
                        # ── Toolbar ────────────────────────────────────
                        ft.Container(
                            content=ft.Row([
                                # search_field already has prefix_icon=SEARCH
                                ft.Container(
                                    content=self.search_field,
                                    expand=True,
                                    bgcolor=ft.colors.WHITE,
                                    border_radius=10,
                                    padding=ft.padding.symmetric(horizontal=4, vertical=2),
                                    border=ft.border.all(1, ft.colors.GREY_200),
                                ),
                                ft.Container(width=8),
                                ft.Container(
                                    content=self.filter_dropdown,
                                    bgcolor=ft.colors.WHITE,
                                    border_radius=10,
                                    padding=ft.padding.only(left=4, right=4),
                                ),
                                ft.Container(width=8),
                                ft.ElevatedButton(
                                    "+ Add Teacher",
                                    visible=_can_edit(self._role),
                                    on_click=self.open_add_dialog,
                                    style=ft.ButtonStyle(
                                        bgcolor={"": "#2563EB", "hovered": "#1E40AF"},
                                        color=ft.colors.WHITE,
                                        shape=ft.RoundedRectangleBorder(radius=8),
                                        elevation={"": 0, "hovered": 2},
                                        padding=ft.padding.symmetric(
                                            horizontal=18, vertical=12),
                                    ),
                                ),
                                ft.Container(width=8),
                                ft.OutlinedButton(
                                    "Bulk Import",
                                    icon=ft.icons.UPLOAD_FILE_ROUNDED,
                                    visible=_can_edit(self._role),
                                    on_click=self.bulk_import,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=8),
                                        side=ft.BorderSide(1, "#2563EB"),
                                        color="#2563EB",
                                        padding=ft.padding.symmetric(
                                            horizontal=16, vertical=12),
                                    ),
                                ),
                            ], spacing=0),
                            bgcolor=ft.colors.WHITE,
                            border_radius=12,
                            padding=ft.padding.symmetric(horizontal=16, vertical=10),
                            shadow=ft.BoxShadow(
                                spread_radius=0, blur_radius=8,
                                color=ft.colors.with_opacity(0.06, ft.colors.BLACK),
                                offset=ft.Offset(0, 2)),
                        ),

                        ft.Container(height=14),

                        # ── Bulk-select bar ────────────────────────────
                        self._sel_bar,

                        # ── Table card ────────────────────────────────
                        # NOTE: no expand=True here — expand inside a
                        # scrollable Column collapses the container to zero.
                        ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    self._lbl_count_table,
                                ], alignment=ft.MainAxisAlignment.END),
                                ft.Divider(height=1, color=ft.colors.GREY_100),
                                ft.Row(
                                    [self.teachers_table],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    scroll=ft.ScrollMode.AUTO,
                                ),
                            ]),
                            bgcolor=ft.colors.WHITE,
                            border_radius=12,
                            padding=ft.padding.symmetric(horizontal=20, vertical=14),
                            shadow=ft.BoxShadow(
                                spread_radius=0, blur_radius=10,
                                color=ft.colors.with_opacity(0.07, ft.colors.BLACK),
                                offset=ft.Offset(0, 3)),
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    scroll=ft.ScrollMode.AUTO,
                    spacing=0),
                    padding=20,
                    bgcolor="#F8FAFC",
                    expand=True,
                )
            ],
            padding=0,
            spacing=0,
        )
    
    def load_teachers(self):
        """Load teachers from database."""
        try:
            # Migrate existing DBs — add phone column if missing
            try:
                self.app.local_db.execute("ALTER TABLE teachers ADD COLUMN phone TEXT")
                print("Migrated teachers table: added phone column")
            except Exception:
                pass  # Column already exists
            result = self.app.local_db.execute("""
                SELECT t.*, GROUP_CONCAT(s.code) as subject_codes
                FROM teachers t
                LEFT JOIN teacher_subjects ts ON t.id = ts.teacher_id
                LEFT JOIN subjects s ON ts.subject_id = s.id
                GROUP BY t.id
                ORDER BY t.full_name
            """)
            
            self.all_teachers = result if result else []
            self.display_teachers()
            print(f"Loaded {len(self.all_teachers)} teachers")
        except Exception as e:
            print(f"Error loading teachers: {e}")
            self.all_teachers = []
        self.selected_ids = set()
    
    def _make_rows(self, teachers):
        """Build rows with a Checkbox cell. _toggle does ZERO Flet calls."""
        rows = []
        for teacher in teachers:
            tid = teacher.get('id', '')
            subject_codes = teacher.get('subject_codes', '') or ''
            is_active = teacher.get('is_active', 1)
            if isinstance(is_active, str):
                is_active = int(is_active) if is_active.isdigit() else 1

            def _toggle(e, tid=tid):
                if tid in self.selected_ids:
                    self.selected_ids.discard(tid)
                else:
                    self.selected_ids.add(tid)
                n = len(self.selected_ids)
                self._sel_bar.visible = n > 0
                self._sel_count_lbl.value = f"{n} teacher(s) selected"
                self.page.update()

            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Checkbox(
                    value=tid in self.selected_ids,
                    on_change=_toggle,
                    visible=_can_edit(self._role),
                )),
                ft.DataCell(ft.Text(teacher.get('teacher_code', ''))),
                ft.DataCell(ft.Text(teacher.get('full_name', ''))),
                ft.DataCell(ft.Text(teacher.get('email', ''))),
                ft.DataCell(ft.Text(teacher.get('phone', '') or '-')),
                ft.DataCell(ft.Text(str(teacher.get('max_daily_periods', 6)))),
                ft.DataCell(ft.Text(subject_codes, overflow=ft.TextOverflow.ELLIPSIS, max_lines=1)),
                ft.DataCell(ft.Container(
                    content=ft.Text(
                        "Active" if is_active else "Inactive",
                        size=11, color=ft.colors.WHITE,
                        weight=ft.FontWeight.W_500),
                    padding=ft.padding.symmetric(horizontal=10, vertical=3),
                    border_radius=20,
                    bgcolor="#16A34A" if is_active else "#DC2626")),
                ft.DataCell(ft.Row([
                    ft.IconButton(icon=ft.icons.EDIT, icon_size=20,
                        visible=_can_edit(self._role),
                        on_click=lambda e, t=teacher: self.open_edit_dialog(t)),
                    ft.IconButton(icon=ft.icons.SCHEDULE, icon_size=20,
                        visible=_can_edit(self._role),
                        on_click=lambda e, t=teacher: self.manage_unavailability(t)),
                    ft.IconButton(icon=ft.icons.DELETE, icon_size=20,
                        visible=_can_edit(self._role),
                        icon_color=ft.colors.RED_400,
                        on_click=lambda e, t=teacher: self.delete_teacher(t)),
                    ft.Tooltip(
                        message="View only",
                        content=ft.Icon(ft.icons.VISIBILITY_OUTLINED,
                                        size=18, color=ft.colors.GREY_400,
                                        visible=not _can_edit(self._role))),
                ])),
            ]))
        return rows

    def _clear_selection(self, e=None):
        self.selected_ids.clear()
        self._sel_bar.visible = False
        self._sel_count_lbl.value = "0 selected"
        self.load_teachers()

    def _bulk_delete_confirm(self, e):
        if not _can_edit(self._role): return
        n = len(self.selected_ids)
        if n == 0:
            self.page.show_snack_bar(ft.SnackBar(
                content=ft.Text("No teachers selected. Tick the checkboxes first."),
                bgcolor=ft.colors.ORANGE))
            return
        ids_snap = set(self.selected_ids)

        def _do(e):
            dlg.open = False
            self.page.update()
            deleted = 0
            for tid in ids_snap:
                try:
                    self.app.local_db.execute(
                        "DELETE FROM teacher_subjects WHERE teacher_id=?", (tid,))
                    self.app.local_db.execute(
                        "DELETE FROM teacher_unavailability WHERE teacher_id=?", (tid,))
                    self.app.local_db.delete("teachers", tid)
                    deleted += 1
                except Exception as ex:
                    print(f"Bulk delete {tid}: {ex}")
            self.selected_ids.clear()
            self._sel_bar.visible = False
            self._sel_count_lbl.value = "0 selected"
            self.load_teachers()
            self.page.show_snack_bar(ft.SnackBar(
                content=ft.Text(f"Deleted {deleted} teacher(s) successfully."),
                bgcolor=ft.colors.GREEN))

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Delete Selected Teachers", color=ft.colors.RED_700),
            content=ft.Text(
                f"Delete {n} teacher(s) and all their assignments? This cannot be undone."),
            actions=[
                ft.TextButton("Cancel",
                    on_click=lambda e: [setattr(dlg, 'open', False), self.page.update()]),
                ft.ElevatedButton("Delete All",
                    icon=ft.icons.DELETE_FOREVER,
                    on_click=_do,
                    style=ft.ButtonStyle(
                        bgcolor=ft.colors.RED_700, color=ft.colors.WHITE)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def display_teachers(self):
        """Display teachers in table and update all live count labels."""
        n = len(self.all_teachers)
        self._lbl_count_top.value   = f"{n} teacher{'s' if n != 1 else ''}"
        self._lbl_count_table.value = f"Total: {n} teacher{'s' if n != 1 else ''}"
        self.teachers_table.rows = self._make_rows(self.all_teachers)
        self.page.update()
    
    def search_teachers(self, e):
        """Filter teachers by search term."""
        search = self.search_field.value.lower() if self.search_field.value else ""
        if not search:
            self.display_teachers()
            return
        
        filtered = [
            t for t in self.all_teachers
            if search in t.get('full_name', '').lower()
            or search in t.get('teacher_code', '').lower()
            or search in t.get('email', '').lower()
            or search in (t.get('phone', '') or '').lower()
        ]
        self.display_filtered(filtered)
    
    def filter_teachers(self, e):
        """Filter teachers by status."""
        filter_value = self.filter_dropdown.value
        
        if filter_value == "All":
            self.display_teachers()
            return
        
        is_active = 1 if filter_value == "Active" else 0
        filtered = []
        for t in self.all_teachers:
            teacher_active = t.get('is_active', 1)
            if isinstance(teacher_active, str):
                teacher_active = int(teacher_active) if teacher_active.isdigit() else 1
            if teacher_active == is_active:
                filtered.append(t)
        
        self.display_filtered(filtered)
    
    def display_filtered(self, filtered):
        """Display filtered teachers."""
        self.teachers_table.rows = self._make_rows(filtered)
        self.page.update()
    
    def open_add_dialog(self, e):
        """Open dialog to add new teacher."""
        if not _can_edit(self._role): return
        self.dialog.title = ft.Text("Add Teacher")
        self.current_teacher_id = None
        
        # Clear fields
        content = self.dialog.content.content
        content.controls[0].value = ""
        content.controls[1].value = ""
        content.controls[2].value = ""
        content.controls[3].value = ""
        content.controls[4].value = "6"
        content.controls[5].value = "1"
        
        # Ensure subject_list is initialized
        if not hasattr(self, 'subject_list') or self.subject_list is None:
            self.subject_list = content.controls[7]
        
        # Load subjects for selection
        self.load_subjects_for_selection()
        
        self.dialog.open = True
        self.page.update()
    
    def open_edit_dialog(self, teacher):
        """Open dialog to edit teacher."""
        if not _can_edit(self._role): return
        self.dialog.title = ft.Text("Edit Teacher")
        self.current_teacher_id = teacher['id']
        
        content = self.dialog.content.content
        content.controls[0].value = teacher.get('teacher_code', '')
        content.controls[1].value = teacher.get('full_name', '')
        content.controls[2].value = teacher.get('email', '')
        content.controls[3].value = teacher.get('phone', '') or ''
        content.controls[4].value = str(teacher.get('max_daily_periods', 6))
        
        # Handle status conversion
        is_active = teacher.get('is_active', 1)
        if isinstance(is_active, str):
            is_active = int(is_active) if is_active.isdigit() else 1
        content.controls[5].value = "1" if is_active else "0"
        
        # Ensure subject_list is initialized
        if not hasattr(self, 'subject_list') or self.subject_list is None:
            self.subject_list = content.controls[7]
        
        # Load subjects and mark selected
        self.load_subjects_for_selection(teacher['id'])
        
        self.dialog.open = True
        self.page.update()
    
    def load_subjects_for_selection(self, teacher_id=None):
        """Load subjects with checkboxes for selection."""
        try:
            # Get all subjects
            subjects = self.app.local_db.execute(
                "SELECT * FROM subjects ORDER BY name"
            ) or []
            
            print(f"Loaded {len(subjects)} subjects for selection")
            
            # Get teacher's subjects if editing
            teacher_subjects = []
            if teacher_id:
                ts = self.app.local_db.execute(
                    "SELECT subject_id FROM teacher_subjects WHERE teacher_id = ?",
                    (teacher_id,)
                ) or []
                teacher_subjects = [s['subject_id'] for s in ts]
                print(f"Teacher has {len(teacher_subjects)} subjects")
            
            # Create checkboxes
            if hasattr(self, 'subject_list') and self.subject_list is not None:
                self.subject_list.controls = []
                
                for subject in subjects:
                    checkbox = ft.Checkbox(
                        label=f"{subject.get('code', '')} - {subject.get('name', '')}",
                        value=subject.get('id') in teacher_subjects,
                        data=subject.get('id')
                    )
                    self.subject_list.controls.append(checkbox)
                
                self.page.update()
            else:
                print("Warning: subject_list not initialized")
                
        except Exception as e:
            print(f"Error loading subjects for selection: {e}")
            import traceback
            traceback.print_exc()
    
    # ══════════════════════════════════════════════════════════════════════
    # BUTTON ANIMATION HELPERS
    # ══════════════════════════════════════════════════════════════════════
    async def _animate_elevated_btn(self, btn, save_fn, e):
        """Spinner → save logic → success flash → reset."""
        import asyncio
        orig_text  = btn.text
        orig_icon  = btn.icon
        # Saving state
        btn.text     = "Saving..."
        btn.icon     = ft.icons.HOURGLASS_TOP_ROUNDED
        btn.disabled = True
        btn.style.bgcolor = {"": "#64748B", "hovered": "#475569"}
        self.page.update()
        await asyncio.sleep(0.15)
        # Run logic
        save_fn(e)
        # Success state
        btn.text     = "Saved ✓"
        btn.icon     = ft.icons.CHECK_CIRCLE_ROUNDED
        btn.disabled = False
        btn.style.bgcolor = {"": "#16A34A", "hovered": "#15803D"}
        self.page.update()
        await asyncio.sleep(1.4)
        # Reset
        btn.text     = orig_text
        btn.icon     = orig_icon
        btn.style.bgcolor = {"": "#2563EB", "hovered": "#1E40AF"}
        self.page.update()

    async def _save_teacher_animated(self, e):
        await self._animate_elevated_btn(self._btn_save_teacher, self.save_teacher, e)

    def save_teacher(self, e):
        """Save teacher to database."""
        if not _can_edit(self._role): return
        content = self.dialog.content.content
        
        # Get the status value properly
        status_value = content.controls[5].value
        print(f"Status dropdown value: '{status_value}' (type: {type(status_value)})")
        
        # Convert to integer (1 for Active, 0 for Inactive)
        if status_value == "1" or status_value == 1 or status_value == "Active":
            is_active = 1
            status_text = "Active"
        else:
            is_active = 0
            status_text = "Inactive"
        
        teacher_data = {
            'teacher_code': content.controls[0].value,
            'full_name': content.controls[1].value,
            'email': content.controls[2].value,
            'phone': content.controls[3].value or None,
            'max_daily_periods': int(content.controls[4].value) if content.controls[4].value else 6,
            'is_active': is_active,
        }
        
        print(f"Teacher data to save: {teacher_data}")
        print(f"Current teacher ID: {self.current_teacher_id}")
        
        try:
            if self.current_teacher_id:
                # ── EDIT: update teacher record, then unconditionally
                # replace subject assignments.
                # Note: local_db.update() returns None on most SQLite helpers,
                # so we never gate on its return value — we always proceed.
                self.app.local_db.update(
                    "teachers", self.current_teacher_id, teacher_data
                )

                self.app.local_db.execute(
                    "DELETE FROM teacher_subjects WHERE teacher_id = ?",
                    (self.current_teacher_id,)
                )

                subject_count = 0
                if hasattr(self, 'subject_list') and self.subject_list:
                    for checkbox in self.subject_list.controls:
                        if hasattr(checkbox, 'value') and checkbox.value:
                            self.app.local_db.insert("teacher_subjects", {
                                'id':         str(uuid.uuid4()),
                                'teacher_id': self.current_teacher_id,
                                'subject_id': checkbox.data,
                            })
                            subject_count += 1
                print(f"Updated teacher, saved {subject_count} subject(s)")

            else:
                # ── ADD: insert teacher, then read back the actual stored ID.
                # We pass our own UUID but some DB helpers ignore it and
                # generate their own — querying by teacher_code afterwards
                # guarantees we use whatever ID was actually written to the DB.
                proposed_id = str(uuid.uuid4())
                teacher_data['id'] = proposed_id
                self.app.local_db.insert("teachers", teacher_data)

                # Get the real stored ID (may differ from proposed_id)
                row = self.app.local_db.execute(
                    "SELECT id FROM teachers WHERE teacher_code = ?",
                    (teacher_data['teacher_code'],)
                )
                actual_id = row[0]['id'] if row else proposed_id
                print(f"New teacher stored with ID: {actual_id}")

                subject_count = 0
                if hasattr(self, 'subject_list') and self.subject_list:
                    for checkbox in self.subject_list.controls:
                        if hasattr(checkbox, 'value') and checkbox.value:
                            self.app.local_db.insert("teacher_subjects", {
                                'id':         str(uuid.uuid4()),
                                'teacher_id': actual_id,   # real DB id
                                'subject_id': checkbox.data,
                            })
                            subject_count += 1
                print(f"Added {subject_count} subject(s) for new teacher")
            
            self.close_dialog(None)
            self.load_teachers()
            
            # Show success message with status
            self.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(f"Teacher saved as {status_text}!"), bgcolor=ft.colors.GREEN)
            )
            
        except Exception as e:
            print(f"❌ Error saving teacher: {e}")
            import traceback
            traceback.print_exc()
            self.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(f"Error: {str(e)}"), bgcolor=ft.colors.RED)
            )
    
    def manage_unavailability(self, teacher):
        """Manage teacher unavailability."""
        if not _can_edit(self._role): return
        self.current_teacher_id = teacher['id']
        self.unavail_dialog.title = ft.Text(f"Unavailability - {teacher.get('full_name')}")
        
        # Load existing unavailability
        self.load_unavailability()
        
        self.unavail_dialog.open = True
        self.page.update()
    
    def load_unavailability(self):
        """Load teacher unavailability."""
        try:
            unavail = self.app.local_db.execute(
                "SELECT * FROM teacher_unavailability WHERE teacher_id = ? ORDER BY day_of_week, period_number",
                (self.current_teacher_id,)
            ) or []
            
            if hasattr(self, 'unavail_list') and self.unavail_list:
                self.unavail_list.controls = []
                
                for u in unavail:
                    row = ft.ListTile(
                        title=ft.Text(f"{u['day_of_week']} - Period {u['period_number']}"),
                        subtitle=ft.Text(u.get('reason', '')),
                        trailing=ft.IconButton(
                            icon=ft.icons.DELETE,
                            on_click=lambda e, id=u['id']: self.delete_unavailability(id)
                        )
                    )
                    self.unavail_list.controls.append(row)
                
                self.page.update()
        except Exception as e:
            print(f"Error loading unavailability: {e}")
    
    def add_unavailability(self, e):
        """Add teacher unavailability."""
        content = self.unavail_dialog.content.content
        
        if not content.controls[0].value or not content.controls[1].value:
            self.page.show_snack_bar(
                ft.SnackBar(content=ft.Text("Please select day and period"), bgcolor=ft.colors.RED)
            )
            return
        
        unavail_data = {
            'teacher_id': self.current_teacher_id,
            'day_of_week': content.controls[0].value,
            'period_number': int(content.controls[1].value),
            'reason': content.controls[2].value or ""
        }
        
        try:
            self.app.local_db.insert("teacher_unavailability", unavail_data)
            
            # Clear fields
            content.controls[0].value = None
            content.controls[1].value = ""
            content.controls[2].value = ""
            
            self.load_unavailability()
            self.page.show_snack_bar(
                ft.SnackBar(content=ft.Text("Unavailability added!"), bgcolor=ft.colors.GREEN)
            )
        except Exception as e:
            print(f"Error adding unavailability: {e}")
    
    def delete_unavailability(self, unavail_id):
        """Delete teacher unavailability."""
        try:
            self.app.local_db.execute(
                "DELETE FROM teacher_unavailability WHERE id = ?",
                (unavail_id,)
            )
            self.load_unavailability()
            self.page.show_snack_bar(
                ft.SnackBar(content=ft.Text("Unavailability removed!"), bgcolor=ft.colors.GREEN)
            )
        except Exception as e:
            print(f"Error deleting unavailability: {e}")
    
    def delete_teacher(self, teacher):
        """Delete teacher with confirmation."""
        if not _can_edit(self._role): return
        def confirm_delete(e):
            try:
                # Delete subject assignments first
                self.app.local_db.execute(
                    "DELETE FROM teacher_subjects WHERE teacher_id = ?",
                    (teacher['id'],)
                )
                # Delete unavailability
                self.app.local_db.execute(
                    "DELETE FROM teacher_unavailability WHERE teacher_id = ?",
                    (teacher['id'],)
                )
                # Delete teacher
                self.app.local_db.delete("teachers", teacher['id'])
                
                dialog.open = False
                self.load_teachers()
                self.page.show_snack_bar(
                    ft.SnackBar(content=ft.Text("Teacher deleted successfully!"), bgcolor=ft.colors.GREEN)
                )
                self.page.update()
            except Exception as ex:
                print(f"Error deleting teacher: {ex}")
        
        dialog = ft.AlertDialog(
            title=ft.Text("Confirm Delete"),
            content=ft.Text(f"Are you sure you want to delete {teacher.get('full_name')}?"),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: [setattr(dialog, 'open', False), self.page.update()]),
                ft.ElevatedButton("Delete", on_click=confirm_delete, color=ft.colors.RED),
            ]
        )
        
        if dialog not in self.page.overlay:
            self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def close_dialog(self, e):
        """Close the add/edit dialog."""
        self.dialog.open = False
        self.page.update()
    
    def close_unavail_dialog(self, e):
        """Close unavailability dialog."""
        self.unavail_dialog.open = False
        self.page.update()
    
    def bulk_import(self, e):
        """Open file picker — accepts CSV and XLSX."""
        if not _can_edit(self._role): return
        def on_file_picked(result: ft.FilePickerResultEvent):
            if result.files:
                self.process_bulk_import(result.files[0].path)

        picker = ft.FilePicker(on_result=on_file_picked)
        self.page.overlay.append(picker)
        self.page.update()
        picker.pick_files(
            dialog_title="Select Teachers file (CSV or Excel)",
            allow_multiple=False,
            allowed_extensions=["csv", "xlsx", "xls"],
        )

    def _read_import_rows(self, file_path):
        """Return list of dicts from CSV or XLSX. All keys lowercased & stripped."""
        import csv, os
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ('.xlsx', '.xls'):
            import openpyxl
            wb = openpyxl.load_workbook(file_path, data_only=True)
            ws = wb.active
            raw_headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
            # normalise: lowercase + strip, blank columns get positional name
            headers = [
                str(h).lower().strip() if h else f'col_{i}'
                for i, h in enumerate(raw_headers)
            ]
            rows = []
            for row in ws.iter_rows(min_row=2, values_only=True):
                if all(v is None for v in row):
                    continue  # skip fully empty rows
                rows.append({
                    headers[i]: (str(v).strip() if v is not None else '')
                    for i, v in enumerate(row)
                })
            return rows
        else:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                # normalise CSV headers too
                rows = []
                for raw_row in reader:
                    rows.append({k.lower().strip(): (v.strip() if v else '') for k, v in raw_row.items()})
                return rows

    def _col(self, row, *aliases):
        """Get first matching alias from a row dict (case already lowered)."""
        for a in aliases:
            v = row.get(a.lower().strip(), '')
            if v:
                return v
        return ''

    def process_bulk_import(self, file_path):
        """Process bulk import from CSV or XLSX.

        Uses UPSERT logic — if a teacher_code already exists the record is
        updated and subjects re-linked, so re-importing never fails with
        duplicate-key errors.

        Accepted column names (case-insensitive, any order):
          Teacher Code : teacher_code, code, teacher code
          Full Name    : full_name, name, full name, teacher_name
          Email        : email, e-mail, email address
          Phone        : phone, phone_number, phone number, mobile
          Max Periods  : max_daily_periods, max_periods, max periods
          Status       : is_active, status, active
          Subjects     : subjects, subject, subject_code, subject_codes
                         (comma-separated codes e.g. "ENG,MATH,BIO")
        """
        try:
            rows = self._read_import_rows(file_path)

            if not rows:
                self.page.show_snack_bar(ft.SnackBar(
                    content=ft.Text("File is empty or could not be read."),
                    bgcolor=ft.colors.ORANGE))
                return

            detected = list(rows[0].keys())
            print(f"[Teachers Import] Detected headers: {detected}")

            # ── Pre-load all subjects into a code→id lookup ────────────
            all_subjects = self.app.local_db.execute(
                "SELECT id, code FROM subjects") or []
            # Normalise keys to uppercase for case-insensitive matching
            subject_lookup = {
                str(s['code']).upper().strip(): s['id']
                for s in all_subjects
            }
            print(f"[Teachers Import] {len(subject_lookup)} subjects available "
                  f"for linking: {list(subject_lookup.keys())}")

            inserted = 0
            updated  = 0
            skipped  = 0
            subjects_linked = 0
            skip_reasons = []

            for i, row in enumerate(rows, start=2):
                # ── Resolve teacher_code and full_name ─────────────────
                code = (row.get('teacher_code') or row.get('code') or
                        row.get('teacher code') or '').strip()
                name = (row.get('full_name') or row.get('name') or
                        row.get('full name') or row.get('teacher_name') or
                        row.get('teacher name') or '').strip()

                if not code and not name:
                    skipped += 1
                    continue
                if not code:
                    skip_reasons.append(f"Row {i}: missing teacher_code")
                    skipped += 1
                    continue
                if not name:
                    skip_reasons.append(f"Row {i}: missing full_name")
                    skipped += 1
                    continue

                # ── Max periods ────────────────────────────────────────
                max_p_raw = (row.get('max_daily_periods') or
                             row.get('max_periods') or
                             row.get('max periods') or
                             row.get('maxperiods') or
                             row.get('max daily periods') or '6')
                try:
                    max_p = int(str(max_p_raw).strip().split('.')[0] or '6')
                except (ValueError, AttributeError):
                    max_p = 6

                # ── Status ─────────────────────────────────────────────
                status_raw = (row.get('is_active') or row.get('status') or
                              row.get('active') or 'active').lower().strip()
                is_active = 1 if status_raw in (
                    'true', '1', 'yes', 'active') else 0

                teacher_data = {
                    'teacher_code':      code,
                    'full_name':         name,
                    'email':             (row.get('email') or row.get('e-mail') or
                                          row.get('email address') or '').strip(),
                    'phone':             (row.get('phone') or
                                          row.get('phone_number') or
                                          row.get('mobile') or '').strip(),
                    'max_daily_periods': max_p,
                    'is_active':         is_active,
                }

                try:
                    # ── UPSERT ─────────────────────────────────────────
                    existing = self.app.local_db.execute(
                        "SELECT id FROM teachers WHERE teacher_code = ?",
                        (code,)
                    )

                    if existing:
                        # Teacher already in DB — update, don't duplicate
                        actual_id = existing[0]['id']
                        self.app.local_db.update(
                            "teachers", actual_id, teacher_data)
                        updated += 1
                        print(f"[Teachers Import] Updated: {code} ({name})")
                    else:
                        # New teacher — insert
                        proposed_id = str(uuid.uuid4())
                        teacher_data['id'] = proposed_id
                        self.app.local_db.insert("teachers", teacher_data)
                        # Read back the actual stored ID
                        row_back = self.app.local_db.execute(
                            "SELECT id FROM teachers WHERE teacher_code = ?",
                            (code,)
                        )
                        actual_id = (row_back[0]['id']
                                     if row_back else proposed_id)
                        inserted += 1
                        print(f"[Teachers Import] Inserted: {code} ({name}), "
                              f"id={actual_id}")

                    # ── Link subjects (always replace for clean re-import) ──
                    self.app.local_db.execute(
                        "DELETE FROM teacher_subjects WHERE teacher_id = ?",
                        (actual_id,)
                    )

                    raw_subj = (row.get('subjects') or
                                row.get('subject') or
                                row.get('subject_code') or
                                row.get('subject_codes') or
                                row.get('subject code') or '').strip()

                    if raw_subj:
                        # ── Split on comma or semicolon ONLY ──────────────
                        # Do NOT split on '/' — many subject codes contain
                        # it (e.g. F/N = Food & Nutrition, F.ARTS/CCA).
                        codes = [
                            c.strip().upper()
                            for c in raw_subj.replace(';', ',').split(',')
                            if c.strip()
                        ]
                        print(f"[Teachers Import]   {code} subjects: {codes}")

                        def _resolve_subject(query_code):
                            """
                            Find a subject id for query_code using a
                            4-level match strategy:

                            Level 1 — Exact match (normalised uppercase).
                            Level 2 — Prefix: stored starts with query or
                                      query starts with stored.
                            Level 3 — Substring (query len >= 3).
                            Level 4 — Normalised: strip dots, spaces, slashes
                                      then repeat levels 1-3.  Catches:
                                        P.AGR   → PRAC. AGR  (AGR in PRACAGR)
                                        PRAC.AGR → PRAC. AGR
                                        F.ARTS/CCA → F.ARTS / CCA
                            """
                            def _norm(s):
                                return s.replace('.', '').replace('/', '') \
                                        .replace(' ', '').upper()

                            # Level 1: exact
                            if query_code in subject_lookup:
                                return subject_lookup[query_code]

                            # Level 2: prefix
                            for stored_code, sid in subject_lookup.items():
                                if (stored_code.startswith(query_code) or
                                        query_code.startswith(stored_code)):
                                    print(f"[Teachers Import]   prefix match: "
                                          f"'{query_code}' → '{stored_code}'")
                                    return sid

                            # Level 3: substring (only for codes >= 3 chars)
                            if len(query_code) >= 3:
                                for stored_code, sid in subject_lookup.items():
                                    if (query_code in stored_code or
                                            stored_code in query_code):
                                        print(f"[Teachers Import]   substr match: "
                                              f"'{query_code}' → '{stored_code}'")
                                        return sid

                            # Level 4: normalised (dots/slashes/spaces removed)
                            nq = _norm(query_code)
                            if len(nq) >= 3:
                                for stored_code, sid in subject_lookup.items():
                                    ns = _norm(stored_code)
                                    if nq == ns:
                                        print(f"[Teachers Import]   norm-exact: "
                                              f"'{query_code}' → '{stored_code}'")
                                        return sid
                                for stored_code, sid in subject_lookup.items():
                                    ns = _norm(stored_code)
                                    if ns.startswith(nq) or nq.startswith(ns):
                                        print(f"[Teachers Import]   norm-prefix: "
                                              f"'{query_code}' → '{stored_code}'")
                                        return sid
                                for stored_code, sid in subject_lookup.items():
                                    ns = _norm(stored_code)
                                    if nq in ns or ns in nq:
                                        print(f"[Teachers Import]   norm-substr: "
                                              f"'{query_code}' → '{stored_code}'")
                                        return sid

                            return None

                        for subj_code in codes:
                            subj_id = _resolve_subject(subj_code)
                            if subj_id:
                                self.app.local_db.insert(
                                    "teacher_subjects", {
                                        'id':         str(uuid.uuid4()),
                                        'teacher_id': actual_id,
                                        'subject_id': subj_id,
                                    }
                                )
                                subjects_linked += 1
                            else:
                                print(f"[Teachers Import]   ⚠ '{subj_code}' "
                                      f"no match found — available codes: "
                                      f"{list(subject_lookup.keys())}")
                    else:
                        print(f"[Teachers Import]   {code}: no subjects column "
                              f"in this row")

                except Exception as row_ex:
                    import traceback; traceback.print_exc()
                    skip_reasons.append(
                        f"Row {i} ({code}): {row_ex}")
                    skipped += 1

            for r in skip_reasons:
                print(f"[Teachers Import] Skipped: {r}")

            self.load_teachers()

            # ── Summary ────────────────────────────────────────────────
            parts = []
            if inserted:
                parts.append(f"{inserted} new teacher(s) added")
            if updated:
                parts.append(f"{updated} existing teacher(s) updated")
            if subjects_linked:
                parts.append(f"{subjects_linked} subject link(s) created")
            if skipped:
                parts.append(f"{skipped} row(s) skipped")

            total = inserted + updated
            if total > 0:
                msg   = "✅ " + ", ".join(parts) + "."
                color = ft.colors.GREEN
            else:
                msg   = "⚠ Nothing imported. " + ", ".join(parts) + "."
                color = ft.colors.ORANGE

            self.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(msg), bgcolor=color))

            # ── Error dialog — only when truly nothing worked ──────────
            if total == 0 and skipped > 0:
                reason_text = "\n".join(skip_reasons[:8])
                if len(skip_reasons) > 8:
                    reason_text += f"\n… and {len(skip_reasons)-8} more"
                hint = ft.AlertDialog(
                    title=ft.Text("Import Failed — Check Details",
                                  color=ft.colors.ORANGE_700),
                    content=ft.Container(
                        width=500,
                        content=ft.Column([
                            ft.Text("Detected headers in your file:",
                                    size=12, color=ft.colors.GREY_700),
                            ft.Container(
                                content=ft.Text(
                                    ", ".join(detected) or "(none found)",
                                    size=12, color=ft.colors.BLUE_700,
                                    selectable=True),
                                bgcolor=ft.colors.BLUE_50,
                                border_radius=8, padding=10,
                            ),
                            ft.Text("Required headers:",
                                    size=12, weight=ft.FontWeight.BOLD,
                                    color=ft.colors.GREY_700),
                            ft.Text(
                                "teacher_code  •  full_name  •  email  •  phone\n"
                                "max_daily_periods  •  is_active\n"
                                "subjects  (comma-separated codes e.g. ENG,MATH)",
                                size=12, color=ft.colors.GREY_800),
                            ft.Divider(height=4),
                            ft.Text("Errors:", size=12,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.colors.RED_700),
                            ft.Text(reason_text or "(no details)",
                                    size=11, color=ft.colors.RED_900,
                                    selectable=True),
                        ], spacing=8, tight=True),
                    ),
                    actions=[ft.TextButton(
                        "OK", on_click=lambda e: [
                            setattr(hint, 'open', False),
                            self.page.update()])],
                )
                self.page.overlay.append(hint)
                hint.open = True
                self.page.update()

        except Exception as ex:
            import traceback; traceback.print_exc()
            self.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(f"Import error: {ex}"),
                            bgcolor=ft.colors.RED))
    
    async def refresh(self, e):
        """Refresh teachers list with spinner animation."""
        import asyncio
        btn = self._btn_refresh
        btn.icon       = ft.icons.HOURGLASS_TOP_ROUNDED
        btn.icon_color = ft.colors.YELLOW_200
        btn.disabled   = True
        self.page.update()
        await asyncio.sleep(0.15)
        self.load_teachers()
        btn.icon       = ft.icons.CHECK_ROUNDED
        btn.icon_color = "#4ADE80"
        btn.disabled   = False
        self.page.update()
        await asyncio.sleep(1.2)
        btn.icon       = ft.icons.REFRESH_ROUNDED
        btn.icon_color = ft.colors.WHITE
        self.page.update()
        self.page.show_snack_bar(
            ft.SnackBar(content=ft.Text("Teachers refreshed!"), bgcolor=ft.colors.GREEN)
        )