"""Classes management view - Complete working version."""
import flet as ft
import uuid
import traceback

def _norm_role(role: str) -> str:
    """Normalise role string to uppercase regardless of source."""
    return (role or "VIEWER").strip().upper()

def _can_edit(role: str) -> bool:
    """Admin and Coordinator may mutate data; Viewer is read-only."""
    return _norm_role(role) in ("ADMIN", "COORDINATOR")



class ClassesView:
    """Classes management screen."""
    
    def __init__(self, app):
        self.app = app
        self.page = app.page
        self._role = _norm_role((app.current_user or {}).get("role", "VIEWER"))
        self.search_field = ft.TextField(
            hint_text="Search classes...",
            prefix_icon=ft.icons.SEARCH,
            expand=True,
            on_change=self.search_classes
        )
        self.level_tabs = ft.Tabs(
            selected_index=0,
            tabs=[
                ft.Tab(text="All"),
                ft.Tab(text="JSS1"),
                ft.Tab(text="JSS2"),
                ft.Tab(text="JSS3"),
                ft.Tab(text="SS1"),
                ft.Tab(text="SS2"),
                ft.Tab(text="SS3"),
            ],
            on_change=self.filter_by_level
        )
        self.classes_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("",             size=13)),
                ft.DataColumn(ft.Text("Class Name",  size=13, weight=ft.FontWeight.W_600, color="#0F1E3A")),
                ft.DataColumn(ft.Text("Level",        size=13, weight=ft.FontWeight.W_600, color="#0F1E3A")),
                ft.DataColumn(ft.Text("Students",     size=13, weight=ft.FontWeight.W_600, color="#0F1E3A")),
                ft.DataColumn(ft.Text("Default Room", size=13, weight=ft.FontWeight.W_600, color="#0F1E3A")),
                ft.DataColumn(ft.Text("Subjects",     size=13, weight=ft.FontWeight.W_600, color="#0F1E3A")),
                ft.DataColumn(ft.Text("Actions",      size=13, weight=ft.FontWeight.W_600, color="#0F1E3A")),
            ],
            rows=[],
            heading_row_color="#EFF6FF",
            heading_row_height=52,
            data_row_min_height=52,
            data_row_max_height=52,
            column_spacing=20,
            horizontal_margin=0,
            divider_thickness=1,
            show_checkbox_column=False,
        )

        self.selected_ids = set()

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
        
        # Add/Edit Dialog — save button stored for animation
        self._btn_save_class = ft.ElevatedButton(
            "Save",
            icon=ft.icons.SAVE_ROUNDED,
            on_click=self._save_class_animated,
            style=ft.ButtonStyle(
                bgcolor={"": "#2563EB", "hovered": "#1E40AF"},
                color=ft.colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8),
                elevation={"": 0, "hovered": 2},
            ),
        )
        self.dialog = ft.AlertDialog(
            title=ft.Text("Add Class"),
            content=ft.Container(
                width=min(self.page.window_width * 0.75, 900) if self.page.window_width else 700,
                height=600,
                content=ft.Column([
                    ft.TextField(label="Class Name", autofocus=True,
                               hint_text="e.g., JSS1A"),
                    ft.Dropdown(
                        label="Level",
                        options=[
                            ft.dropdown.Option("JSS1"),
                            ft.dropdown.Option("JSS2"),
                            ft.dropdown.Option("JSS3"),
                            ft.dropdown.Option("SS1"),
                            ft.dropdown.Option("SS2"),
                            ft.dropdown.Option("SS3"),
                        ],
                        value="JSS1"
                    ),
                    ft.TextField(
                        label="Student Count",
                        value="40",
                        keyboard_type=ft.KeyboardType.NUMBER
                    ),
                    ft.Dropdown(
                        label="Default Room",
                        options=[]
                    ),
                    ft.Text("Subject Assignments", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Text("Subject", weight=ft.FontWeight.BOLD, expand=2),
                                ft.Text("Teacher", weight=ft.FontWeight.BOLD, expand=2),
                                ft.Text("", width=50),
                            ]),
                            ft.ListView(height=200, spacing=5),
                        ]),
                        padding=10,
                        border=ft.border.all(1, ft.colors.GREY_300),
                        border_radius=5
                    ),
                    ft.ElevatedButton(
                        "Add Subject",
                        icon=ft.icons.ADD,
                        on_click=self.add_subject_row
                    )
                ], spacing=10, scroll=ft.ScrollMode.AUTO),
                padding=20
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self.close_dialog,
                              style=ft.ButtonStyle(color=ft.colors.GREY_600)),
                self._btn_save_class,
            ]
        )
        
        self.current_class_id = None
        self.all_classes = []
        self.rooms = []
        self.subjects = []
        self.teachers = []
        self.subject_rows = []
        self.subject_list_view = None

        # Refresh button — stored so refresh() can animate it
        self._btn_refresh = ft.IconButton(
            icon=ft.icons.REFRESH_ROUNDED,
            icon_color=ft.colors.WHITE, icon_size=18,
            tooltip="Refresh",
            on_click=self.refresh,
        )

        # Live count labels — updated by display_classes() on every data change
        self._lbl_count_top   = ft.Text(
            "0 classes", size=12,
            color=ft.colors.with_opacity(0.6, ft.colors.WHITE))
        self._lbl_count_table = ft.Text(
            "Total: 0 classes", size=13,
            color=ft.colors.GREY_500, weight=ft.FontWeight.W_500)

        # Add dialog to overlay
        if self.dialog not in self.page.overlay:
            self.page.overlay.append(self.dialog)
    
    def build(self):
        """Build the classes view."""
        self.load_classes()
        self.load_rooms()
        self.load_subjects()
        self.load_teachers()
        
        # Store reference to subject list view
        self.subject_list_view = self.dialog.content.content.controls[5].content.controls[1]
        
        return ft.View(
            "/classes",
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
                        ft.Icon(ft.icons.GROUPS_ROUNDED,
                                color=ft.colors.WHITE, size=20),
                        ft.Text("Classes Management", size=17,
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
                                ft.Container(
                                    content=self.search_field,
                                    expand=True,
                                    bgcolor=ft.colors.WHITE,
                                    border_radius=10,
                                    padding=ft.padding.symmetric(
                                        horizontal=4, vertical=2),
                                    border=ft.border.all(1, ft.colors.GREY_200),
                                ),
                                ft.Container(width=8),
                                ft.ElevatedButton(
                                    "+ Add Class",
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

                        ft.Container(height=12),

                        # ── Level tabs ─────────────────────────────────
                        ft.Container(
                            content=self.level_tabs,
                            bgcolor=ft.colors.WHITE,
                            border_radius=12,
                            padding=ft.padding.symmetric(horizontal=12, vertical=4),
                            shadow=ft.BoxShadow(
                                spread_radius=0, blur_radius=8,
                                color=ft.colors.with_opacity(0.06, ft.colors.BLACK),
                                offset=ft.Offset(0, 2)),
                        ),

                        ft.Container(height=12),

                        # ── Bulk-select bar ────────────────────────────
                        self._sel_bar,

                        # ── Table card (no expand=True — fixes blank table) ──
                        ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    self._lbl_count_table,
                                ], alignment=ft.MainAxisAlignment.END),
                                ft.Divider(height=1, color=ft.colors.GREY_100),
                                ft.Row(
                                    [self.classes_table],
                                    alignment=ft.MainAxisAlignment.START,
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
    
    def load_classes(self):
        """Load classes from database."""
        try:
            classes = self.app.local_db.execute("""
                SELECT c.*, r.room_name as default_room_name,
                       COUNT(DISTINCT cs.id) as subject_count
                FROM classes c
                LEFT JOIN rooms r ON c.default_room_id = r.id
                LEFT JOIN class_subjects cs ON c.id = cs.class_id
                GROUP BY c.id
                ORDER BY c.level, c.class_name
            """)
            
            self.all_classes = classes if classes else []
            self.selected_ids.clear()
            self.display_classes()
            print(f"Loaded {len(self.all_classes)} classes")
        except Exception as e:
            print(f"Error loading classes: {e}")
            traceback.print_exc()
            self.all_classes = []
    
    def load_rooms(self):
        """Load rooms for dropdown."""
        try:
            rooms = self.app.local_db.execute(
                "SELECT id, room_code, room_name FROM rooms WHERE is_available = 1 ORDER BY room_code"
            )
            self.rooms = rooms if rooms else []
        except Exception as e:
            print(f"Error loading rooms: {e}")
            self.rooms = []
    
    def load_subjects(self):
        """Load subjects for assignment."""
        try:
            subjects = self.app.local_db.execute(
                "SELECT id, code, name FROM subjects ORDER BY code"
            )
            self.subjects = subjects if subjects else []
        except Exception as e:
            print(f"Error loading subjects: {e}")
            self.subjects = []
    
    def load_teachers(self):
        """Load teachers for assignment."""
        try:
            teachers = self.app.local_db.execute(
                "SELECT id, teacher_code, full_name FROM teachers WHERE is_active = 1 ORDER BY full_name"
            )
            self.teachers = teachers if teachers else []
        except Exception as e:
            print(f"Error loading teachers: {e}")
            self.teachers = []
    
    def display_classes(self):
        """Display classes in table."""
        rows = []
        for cls in self.all_classes:
            cid = cls.get('id', '')
            def _toggle(e, cid=cid):
                if cid in self.selected_ids:
                    self.selected_ids.discard(cid)
                else:
                    self.selected_ids.add(cid)
                n = len(self.selected_ids)
                self._sel_bar.visible = n > 0
                self._sel_count_lbl.value = f"{n} class(es) selected"
                self.page.update()
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Checkbox(value=cid in self.selected_ids, on_change=_toggle, visible=_can_edit(self._role))),
                        ft.DataCell(ft.Text(cls.get('class_name', ''), size=14)),
                        ft.DataCell(ft.Text(cls.get('level', ''), size=14)),
                        ft.DataCell(ft.Text(str(cls.get('student_count', 0)), size=14)),
                        ft.DataCell(ft.Text(cls.get('default_room_name', 'None'), size=14)),
                        ft.DataCell(ft.Text(str(cls.get('subject_count', 0)), size=14)),
                        ft.DataCell(
                            ft.Row([
                                ft.IconButton(
                                    icon=ft.icons.EDIT,
                                    icon_size=20,
                                    visible=_can_edit(self._role),
                                    on_click=lambda e, c=cls: self.open_edit_dialog(c)
                                ),
                                ft.IconButton(
                                    icon=ft.icons.ASSIGNMENT,
                                    icon_size=20,
                                    visible=_can_edit(self._role),
                                    on_click=lambda e, c=cls: self.manage_subjects(c)
                                ),
                                ft.IconButton(
                                    icon=ft.icons.DELETE,
                                    icon_size=20,
                                    visible=_can_edit(self._role),
                                    icon_color=ft.colors.RED_400,
                                    on_click=lambda e, c=cls: self.delete_class(c)
                                ),
                                ft.Tooltip(
                                    message="View only",
                                    content=ft.Icon(ft.icons.VISIBILITY_OUTLINED,
                                                    size=18, color=ft.colors.GREY_400,
                                                    visible=not _can_edit(self._role))),
                            ])
                        ),
                    ]
                )
            )
        
        self.classes_table.rows = rows
        n = len(self.all_classes)
        self._lbl_count_top.value   = f"{n} class{'es' if n != 1 else ''}"
        self._lbl_count_table.value = f"Total: {n} class{'es' if n != 1 else ''}"
        self.page.update()
    
    def search_classes(self, e):
        """Filter classes by search term."""
        search = self.search_field.value.lower() if self.search_field.value else ""
        if not search:
            self.display_classes()
            return
        
        filtered = [
            c for c in self.all_classes
            if search in c.get('class_name', '').lower()
        ]
        self.display_filtered(filtered)
    
    def display_filtered(self, classes):
        """Display filtered classes."""
        rows = []
        for cls in classes:
            cid = cls.get('id', '')
            def _toggle(e, cid=cid):
                if cid in self.selected_ids:
                    self.selected_ids.discard(cid)
                else:
                    self.selected_ids.add(cid)
                n = len(self.selected_ids)
                self._sel_bar.visible = n > 0
                self._sel_count_lbl.value = f"{n} class(es) selected"
                self.page.update()
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Checkbox(value=cid in self.selected_ids, on_change=_toggle, visible=_can_edit(self._role))),
                        ft.DataCell(ft.Text(cls.get('class_name', ''), size=14)),
                        ft.DataCell(ft.Text(cls.get('level', ''), size=14)),
                        ft.DataCell(ft.Text(str(cls.get('student_count', 0)), size=14)),
                        ft.DataCell(ft.Text(cls.get('default_room_name', 'None'), size=14)),
                        ft.DataCell(ft.Text(str(cls.get('subject_count', 0)), size=14)),
                        ft.DataCell(
                            ft.Row([
                                ft.IconButton(
                                    icon=ft.icons.EDIT,
                                    icon_size=20,
                                    visible=_can_edit(self._role),
                                    on_click=lambda e, c=cls: self.open_edit_dialog(c)
                                ),
                                ft.IconButton(
                                    icon=ft.icons.ASSIGNMENT,
                                    icon_size=20,
                                    visible=_can_edit(self._role),
                                    on_click=lambda e, c=cls: self.manage_subjects(c)
                                ),
                                ft.IconButton(
                                    icon=ft.icons.DELETE,
                                    icon_size=20,
                                    visible=_can_edit(self._role),
                                    icon_color=ft.colors.RED_400,
                                    on_click=lambda e, c=cls: self.delete_class(c)
                                ),
                                ft.Tooltip(
                                    message="View only",
                                    content=ft.Icon(ft.icons.VISIBILITY_OUTLINED,
                                                    size=18, color=ft.colors.GREY_400,
                                                    visible=not _can_edit(self._role))),
                            ])
                        ),
                    ]
                )
            )
        
        self.classes_table.rows = rows
        n_total    = len(self.all_classes)
        n_filtered = len(classes)
        self._lbl_count_top.value   = f"{n_total} class{'es' if n_total != 1 else ''}"
        self._lbl_count_table.value = (
            f"Showing: {n_filtered} of {n_total} class{'es' if n_total != 1 else ''}"
        )
        self.page.update()
    
    def filter_by_level(self, e):
        """Filter classes by level."""
        tab_index = self.level_tabs.selected_index
        levels = ["All", "JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3"]
        selected = levels[tab_index]
        
        if selected == "All":
            self.display_classes()
        else:
            filtered = [c for c in self.all_classes if c.get('level') == selected]
            self.display_filtered(filtered)
    
    def open_add_dialog(self, e):
        """Open dialog to add new class."""
        if not _can_edit(self._role): return
        self.dialog.title = ft.Text("Add Class")
        self.current_class_id = None
        self.subject_rows = []
        
        content = self.dialog.content.content
        
        # Clear fields
        content.controls[0].value = ""
        content.controls[1].value = "JSS1"
        content.controls[2].value = "40"
        
        # Load rooms dropdown
        room_dropdown = content.controls[3]
        room_dropdown.options = [
            ft.dropdown.Option(key="", text="None")
        ] + [
            ft.dropdown.Option(key=r['id'], text=f"{r['room_code']} - {r['room_name']}")
            for r in self.rooms
        ]
        room_dropdown.value = ""
        
        # Clear subject list
        if self.subject_list_view:
            self.subject_list_view.controls = []
        
        self.dialog.open = True
        self.page.update()
    
    def open_edit_dialog(self, class_obj):
        """Open dialog to edit class."""
        if not _can_edit(self._role): return
        self.dialog.title = ft.Text("Edit Class")
        self.current_class_id = class_obj['id']
        self.subject_rows = []
        
        content = self.dialog.content.content
        
        # Fill fields
        content.controls[0].value = class_obj.get('class_name', '')
        content.controls[1].value = class_obj.get('level', 'JSS1')
        content.controls[2].value = str(class_obj.get('student_count', 40))
        
        # Load rooms dropdown
        room_dropdown = content.controls[3]
        room_dropdown.options = [
            ft.dropdown.Option(key="", text="None")
        ] + [
            ft.dropdown.Option(key=r['id'], text=f"{r['room_code']} - {r['room_name']}")
            for r in self.rooms
        ]
        room_dropdown.value = class_obj.get('default_room_id', '')
        
        # Load subject assignments
        self.load_class_subjects(class_obj['id'])
        
        self.dialog.open = True
        self.page.update()
    
    def load_class_subjects(self, class_id):
        """Load subject assignments for class."""
        try:
            assignments = self.app.local_db.execute("""
                SELECT cs.*, s.code as subject_code, s.name as subject_name,
                       t.teacher_code, t.full_name as teacher_name
                FROM class_subjects cs
                JOIN subjects s ON cs.subject_id = s.id
                JOIN teachers t ON cs.teacher_id = t.id
                WHERE cs.class_id = ?
            """, (class_id,))
            
            if self.subject_list_view:
                self.subject_list_view.controls = []
                
                for assignment in assignments or []:
                    self.add_subject_row_with_data(
                        assignment['subject_id'],
                        assignment['teacher_id']
                    )
        except Exception as e:
            print(f"Error loading class subjects: {e}")
    
    def add_subject_row(self, e=None):
        """Add a new subject assignment row."""
        self.add_subject_row_with_data(None, None)
    
    def add_subject_row_with_data(self, subject_id=None, teacher_id=None):
        """Add subject row with pre-selected values."""
        if not self.subject_list_view:
            return
        
        # Create subject dropdown  (key=id so .value returns the UUID)
        subject_dropdown = ft.Dropdown(
            expand=True,
            hint_text="Select subject",
            options=[
                ft.dropdown.Option(key=s['id'], text=f"{s['code']} - {s['name']}")
                for s in self.subjects
            ],
            value=subject_id
        )
        
        # Create teacher dropdown
        teacher_dropdown = ft.Dropdown(
            expand=True,
            hint_text="Select teacher",
            options=[
                ft.dropdown.Option(key=t['id'], text=f"{t['teacher_code']} - {t['full_name']}")
                for t in self.teachers
            ],
            value=teacher_id
        )
        
        # Create row
        row = ft.Row([
            subject_dropdown,
            teacher_dropdown,
            ft.IconButton(
                icon=ft.icons.DELETE,
                on_click=lambda e: self.remove_subject_row(row)
            )
        ], spacing=10, expand=True)
        
        self.subject_list_view.controls.append(row)
        self.subject_rows.append(row)
        self.page.update()
    
    def remove_subject_row(self, row):
        """Remove a subject assignment row."""
        if self.subject_list_view and row in self.subject_list_view.controls:
            self.subject_list_view.controls.remove(row)
        if row in self.subject_rows:
            self.subject_rows.remove(row)
        self.page.update()
    
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

    async def _save_class_animated(self, e):
        await self._animate_elevated_btn(self._btn_save_class, self.save_class, e)

    def save_class(self, e):
        """Save class to database."""
        if not _can_edit(self._role): return
        content = self.dialog.content.content
        
        class_data = {
            'class_name': content.controls[0].value,
            'level': content.controls[1].value,
            'student_count': int(content.controls[2].value) if content.controls[2].value else 0,
            'default_room_id': None if not content.controls[3].value else content.controls[3].value
        }
        
        # Validate
        if not class_data['class_name']:
            self.page.show_snack_bar(
                ft.SnackBar(content=ft.Text("Class name is required!"), bgcolor=ft.colors.RED)
            )
            return
        
        try:
            if self.current_class_id:
                # Update existing class record
                self.app.local_db.update(
                    "classes", self.current_class_id, class_data
                )
                
                # ── Delete all existing subject assignments with a direct SQL
                # DELETE rather than delete-by-id.  class_subjects rows are
                # inserted without an 'id' field so delete("class_subjects", id)
                # can silently fail to find the row, causing subjects to
                # accumulate on every save (e.g. 6 subjects × 19 saves = 114).
                self.app.local_db.execute(
                    "DELETE FROM class_subjects WHERE class_id = ?",
                    (self.current_class_id,)
                )
                
                # Re-insert current subject assignments
                if self.subject_list_view:
                    for row in self.subject_list_view.controls:
                        subject_dropdown = row.controls[0]
                        teacher_dropdown = row.controls[1]
                        
                        if subject_dropdown.value and teacher_dropdown.value:
                            self.app.local_db.insert("class_subjects", {
                                'id':         str(uuid.uuid4()),
                                'class_id':   self.current_class_id,
                                'subject_id': subject_dropdown.value,
                                'teacher_id': teacher_dropdown.value
                            })
            else:
                # ── Save the UUID in a local variable BEFORE calling insert().
                # Some DB helpers pop 'id' from the dict during insert, which
                # would make class_data['id'] raise KeyError and silently skip
                # all subject assignments even though the class itself was saved.
                new_class_id = str(uuid.uuid4())
                class_data['id'] = new_class_id
                self.app.local_db.insert("classes", class_data)
                
                # Add subject assignments for new class
                if self.subject_list_view:
                    for row in self.subject_list_view.controls:
                        subject_dropdown = row.controls[0]
                        teacher_dropdown = row.controls[1]
                        
                        if subject_dropdown.value and teacher_dropdown.value:
                            self.app.local_db.insert("class_subjects", {
                                'id':         str(uuid.uuid4()),
                                'class_id':   new_class_id,   # safe local var
                                'subject_id': subject_dropdown.value,
                                'teacher_id': teacher_dropdown.value
                            })
            
            self.close_dialog(None)
            self.load_classes()
            
            self.page.show_snack_bar(
                ft.SnackBar(content=ft.Text("Class saved successfully!"), bgcolor=ft.colors.GREEN)
            )
        except Exception as e:
            print(f"Error saving class: {e}")
            traceback.print_exc()
            self.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(f"Error: {str(e)}"), bgcolor=ft.colors.RED)
            )
    
    def manage_subjects(self, class_obj):
        """Open subject management for class."""
        if not _can_edit(self._role): return
        self.open_edit_dialog(class_obj)
    
    def _clear_selection(self, e=None):
        self.selected_ids.clear()
        self._sel_bar.visible = False
        self._sel_count_lbl.value = "0 selected"
        self.load_classes()

    def _bulk_delete_confirm(self, e):
        if not _can_edit(self._role): return
        n = len(self.selected_ids)
        if n == 0:
            self.page.show_snack_bar(ft.SnackBar(
                content=ft.Text("No classes selected. Tick the checkboxes first."),
                bgcolor=ft.colors.ORANGE))
            return
        ids_snap = set(self.selected_ids)

        def _do(e):
            dlg.open = False
            self.page.update()
            deleted = 0
            skipped = 0
            for cid in ids_snap:
                try:
                    in_use = self.app.local_db.execute(
                        "SELECT COUNT(*) as count FROM timetable_slots WHERE class_id=?", (cid,))
                    if in_use and in_use[0]['count'] > 0:
                        skipped += 1
                        continue
                    self.app.local_db.execute(
                        "DELETE FROM class_subjects WHERE class_id=?", (cid,))
                    self.app.local_db.delete("classes", cid)
                    deleted += 1
                except Exception as ex:
                    print(f"Bulk delete {cid}: {ex}")
            self.selected_ids.clear()
            self._sel_bar.visible = False
            self._sel_count_lbl.value = "0 selected"
            self.load_classes()
            msg = f"Deleted {deleted} class(es) successfully."
            if skipped:
                msg += f" {skipped} skipped (in use by timetables)."
            self.page.show_snack_bar(ft.SnackBar(
                content=ft.Text(msg), bgcolor=ft.colors.GREEN))

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Delete Selected Classes", color=ft.colors.RED_700),
            content=ft.Text(
                f"Delete {n} class(es) and all their subject assignments? This cannot be undone."),
            actions=[
                ft.TextButton("Cancel",
                    on_click=lambda e: [setattr(dlg, 'open', False), self.page.update()]),
                ft.ElevatedButton("Delete All",
                    icon=ft.icons.DELETE_FOREVER,
                    on_click=_do,
                    style=ft.ButtonStyle(
                        bgcolor=ft.colors.RED_700,
                        color=ft.colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=8),
                    )),
            ],
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def delete_class(self, class_obj):
        """Delete class with confirmation."""
        if not _can_edit(self._role): return
        def confirm_delete(e):
            try:
                # Check if class is in use in timetables
                in_use = self.app.local_db.execute(
                    "SELECT COUNT(*) as count FROM timetable_slots WHERE class_id = ?",
                    (class_obj['id'],)
                )
                if in_use and in_use[0]['count'] > 0:
                    self.page.show_snack_bar(
                        ft.SnackBar(
                            content=ft.Text("Cannot delete class - it is used in timetables!"),
                            bgcolor=ft.colors.RED
                        )
                    )
                    dialog.open = False
                    self.page.update()
                    return
                
                # Delete assignments first
                self.app.local_db.execute(
                    "DELETE FROM class_subjects WHERE class_id = ?",
                    (class_obj['id'],)
                )
                self.app.local_db.delete("classes", class_obj['id'])
                
                dialog.open = False
                self.load_classes()
                self.page.show_snack_bar(
                    ft.SnackBar(content=ft.Text("Class deleted successfully!"), bgcolor=ft.colors.GREEN)
                )
                self.page.update()
            except Exception as ex:
                print(f"Error deleting class: {ex}")
        
        dialog = ft.AlertDialog(
            title=ft.Text("Confirm Delete"),
            content=ft.Text(f"Are you sure you want to delete {class_obj.get('class_name')}?"),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: [setattr(dialog, 'open', False), self.page.update()]),
                ft.ElevatedButton("Delete", on_click=confirm_delete, color=ft.colors.RED),
            ]
        )
        
        if dialog not in self.page.overlay:
            self.page.overlay.append(dialog)
        dialog.open = True
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
            dialog_title="Select Classes file (CSV or Excel)",
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

        Accepted column names (case-insensitive):
          class_name, level, student_count, default_room_code,
          subject_code  (or: subject code), teacher_code  (or: teacher code)

        Rows with the same class_name are grouped automatically.
        The class is created once; each row adds one subject-teacher pair.
        """
        try:
            db = self.app.local_db

            # ── pre-load lookup tables ─────────────────────────────────
            subjects_raw = db.execute("SELECT id, code, name FROM subjects") or []
            # Match by subject code OR subject name (case-insensitive)
            subject_map = {}
            for s in subjects_raw:
                if s['code']:
                    subject_map[s['code'].upper().strip()] = s['id']
                if s['name']:
                    subject_map[s['name'].upper().strip()] = s['id']

            teachers_raw = db.execute(
                "SELECT id, teacher_code, full_name FROM teachers WHERE is_active = 1"
            ) or []
            # Match by teacher_code OR full_name (case-insensitive) — whichever the CSV uses
            teacher_map = {}
            for t in teachers_raw:
                if t['teacher_code']:
                    teacher_map[t['teacher_code'].upper().strip()] = t['id']
                if t['full_name']:
                    teacher_map[t['full_name'].upper().strip()] = t['id']

            rooms_raw = db.execute("SELECT id, room_code FROM rooms") or []
            room_map  = {r['room_code'].upper(): r['id'] for r in rooms_raw}

            # ── read file (CSV or XLSX) and group rows by class_name ───
            rows = self._read_import_rows(file_path)

            # ── detect headers early for error dialog ─────────────────
            detected = list(rows[0].keys()) if rows else []
            print(f"[Classes Import] Detected headers: {detected}")

            # group: class_name → {meta, assignments:[]}
            class_groups = {}
            for row in rows:
                name = (row.get('class_name') or row.get('class name') or
                        row.get('classname') or '').strip()
                if not name:
                    continue
                if name not in class_groups:
                    level_raw = (row.get('level') or 'JSS1').strip()
                    try:
                        sc = int(str(row.get('student_count') or row.get('student count') or 40).split('.')[0])
                    except: sc = 40
                    class_groups[name] = {
                        'level':             level_raw,
                        'student_count':     sc,
                        'default_room_code': (row.get('default_room_code') or
                                              row.get('default room code') or '').strip().upper(),
                        'assignments': []
                    }
                subj_raw    = (row.get('subject_code') or row.get('subject code') or '').strip()
                teacher_raw = (row.get('teacher_code') or row.get('teacher code') or '').strip()

                # Support comma-separated subjects and teachers in a single cell.
                # Each subject pairs positionally with its teacher (Commerce=T01, English=T02).
                # If fewer teachers than subjects, the last teacher is reused for the rest.
                subj_codes    = [s.strip().upper() for s in subj_raw.split(',')  if s.strip()]
                teacher_codes = [t.strip().upper() for t in teacher_raw.split(',') if t.strip()]

                for i, sc in enumerate(subj_codes):
                    tc = teacher_codes[i] if i < len(teacher_codes) else (teacher_codes[-1] if teacher_codes else '')
                    if sc and tc:
                        class_groups[name]['assignments'].append((sc, tc))

            # ── upsert each class ──────────────────────────────────────
            classes_created  = 0
            classes_updated  = 0
            assignments_done = 0
            warnings         = []

            for class_name, meta in class_groups.items():
                room_id = room_map.get(meta['default_room_code'])

                # check if class already exists
                existing = db.execute(
                    "SELECT id FROM classes WHERE class_name = ?", (class_name,)
                )
                if existing:
                    class_id = existing[0]['id']
                    db.update("classes", class_id, {
                        'level':           meta['level'],
                        'student_count':   meta['student_count'],
                        'default_room_id': room_id,
                    })
                    # wipe old assignments before re-importing
                    db.execute(
                        "DELETE FROM class_subjects WHERE class_id = ?",
                        (class_id,)
                    )
                    classes_updated += 1
                else:
                    class_id = str(uuid.uuid4())
                    db.insert("classes", {
                        'id':              class_id,
                        'class_name':      class_name,
                        'level':           meta['level'],
                        'student_count':   meta['student_count'],
                        'default_room_id': room_id,
                    })
                    classes_created += 1

                # insert subject assignments
                for subj_code, teacher_code in meta['assignments']:
                    subject_id = subject_map.get(subj_code)
                    teacher_id = teacher_map.get(teacher_code)

                    if not subject_id:
                        warnings.append(
                            f"{class_name}: subject '{subj_code}' not found — "
                            f"check the Code in Subjects screen"
                        )
                        continue
                    if not teacher_id:
                        warnings.append(
                            f"{class_name}: teacher '{teacher_code}' not found — "
                            f"check Teacher Code or Full Name in Teachers screen"
                        )
                        continue

                    db.insert("class_subjects", {
                        'id':         str(uuid.uuid4()),
                        'class_id':   class_id,
                        'subject_id': subject_id,
                        'teacher_id': teacher_id,
                    })
                    assignments_done += 1

            self.load_classes()
            self.load_rooms()

            total_classes = classes_created + classes_updated
            msg = (f"✅ {classes_created} new class(es) created, "
                   f"{classes_updated} updated, "
                   f"{assignments_done} subject assignment(s) saved.")
            if warnings:
                msg += f"  ⚠ {len(warnings)} assignment(s) skipped — see details."
            color = ft.colors.GREEN if total_classes > 0 else ft.colors.ORANGE
            self.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(msg), bgcolor=color,
                            duration=6000))

            # ── Always show a results dialog so nothing is hidden ──────
            # Group warnings by type for clarity
            missing_teachers = sorted({
                w.split("teacher '")[1].split("'")[0]
                for w in warnings if "teacher '" in w
            })
            missing_subjects = sorted({
                w.split("subject '")[1].split("'")[0]
                for w in warnings if "subject '" in w
            })

            dialog_rows = []

            if total_classes > 0 and not warnings:
                dialog_rows.append(ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.CHECK_CIRCLE_ROUNDED,
                                color="#16A34A", size=20),
                        ft.Text(
                            f"All {assignments_done} subject-teacher "
                            "assignments imported successfully!",
                            size=13, color="#16A34A"),
                    ], spacing=8),
                    bgcolor="#F0FDF4", border_radius=8,
                    padding=ft.padding.all(10),
                ))

            if missing_teachers:
                mt_text = ", ".join(missing_teachers)
                dialog_rows.append(ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.icons.PERSON_OFF_ROUNDED,
                                    color="#DC2626", size=18),
                            ft.Text(
                                f"{len(missing_teachers)} teacher code(s) "
                                "NOT found in the Teachers table:",
                                size=13, weight=ft.FontWeight.W_600,
                                color="#DC2626"),
                        ], spacing=6),
                        ft.Container(
                            content=ft.Text(mt_text, size=12,
                                            color="#7F1D1D",
                                            selectable=True),
                            bgcolor="#FEF2F2", border_radius=6,
                            padding=ft.padding.all(8),
                        ),
                        ft.Text(
                            "These subject-teacher pairs were SKIPPED. "
                            "Fix: make sure these codes exist exactly in the "
                            "Teachers screen, then re-import this file.",
                            size=11, color=ft.colors.GREY_700, italic=True),
                    ], spacing=6, tight=True),
                    bgcolor="#FFF5F5", border_radius=8,
                    padding=ft.padding.all(12),
                    border=ft.border.all(1, "#FECACA"),
                ))

            if missing_subjects:
                ms_text = ", ".join(missing_subjects)
                dialog_rows.append(ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.icons.BOOK_OUTLINED,
                                    color="#D97706", size=18),
                            ft.Text(
                                f"{len(missing_subjects)} subject code(s) "
                                "NOT found in the Subjects table:",
                                size=13, weight=ft.FontWeight.W_600,
                                color="#D97706"),
                        ], spacing=6),
                        ft.Container(
                            content=ft.Text(ms_text, size=12,
                                            color="#78350F",
                                            selectable=True),
                            bgcolor="#FFFBEB", border_radius=6,
                            padding=ft.padding.all(8),
                        ),
                        ft.Text(
                            "Fix: make sure these codes exist in the "
                            "Subjects screen, then re-import.",
                            size=11, color=ft.colors.GREY_700, italic=True),
                    ], spacing=6, tight=True),
                    bgcolor="#FFFBEB", border_radius=8,
                    padding=ft.padding.all(12),
                    border=ft.border.all(1, "#FDE68A"),
                ))

            if total_classes == 0:
                dialog_rows.append(ft.Container(
                    content=ft.Column([
                        ft.Text("No classes were imported.",
                                size=13, weight=ft.FontWeight.BOLD,
                                color="#DC2626"),
                        ft.Text("Detected headers in your file:",
                                size=12, color=ft.colors.GREY_700),
                        ft.Container(
                            content=ft.Text(
                                ", ".join(detected) or "(none)",
                                size=12, color="#2563EB", selectable=True),
                            bgcolor="#EFF6FF", border_radius=6,
                            padding=ft.padding.all(8),
                        ),
                        ft.Text(
                            "Required: class_name  •  level  •  student_count\n"
                            "subject_code (comma-sep)  •  teacher_code (comma-sep)",
                            size=12, color=ft.colors.GREY_800),
                    ], spacing=8, tight=True),
                    bgcolor="#FEF2F2", border_radius=8,
                    padding=ft.padding.all(12),
                ))

            if dialog_rows:
                result_dlg = ft.AlertDialog(
                    modal=True,
                    title=ft.Row([
                        ft.Icon(
                            ft.icons.CHECK_CIRCLE_ROUNDED
                            if not warnings else ft.icons.WARNING_AMBER_ROUNDED,
                            color="#16A34A" if not warnings else "#D97706",
                            size=22),
                        ft.Text(
                            "Import Complete"
                            if not warnings else "Import Complete — Action Required",
                            size=15, weight=ft.FontWeight.BOLD),
                    ], spacing=8),
                    content=ft.Container(
                        width=540,
                        content=ft.Column(
                            dialog_rows, spacing=10,
                            scroll=ft.ScrollMode.AUTO),
                        height=min(400, 120 * len(dialog_rows)),
                    ),
                    actions=[
                        ft.ElevatedButton(
                            "OK", on_click=lambda e: [
                                setattr(result_dlg, 'open', False),
                                self.page.update()],
                            style=ft.ButtonStyle(
                                bgcolor={"": "#2563EB", "hovered": "#1E40AF"},
                                color=ft.colors.WHITE,
                                shape=ft.RoundedRectangleBorder(radius=8))),
                    ],
                    actions_alignment=ft.MainAxisAlignment.END,
                )
                self.page.overlay.append(result_dlg)
                result_dlg.open = True
                self.page.update()

            # show warnings in a separate dialog if any
            if warnings:
                warn_dialog = ft.AlertDialog(
                    title=ft.Text("Import Warnings", color=ft.colors.ORANGE),
                    content=ft.Container(
                        width=500,
                        height=300,
                        content=ft.Column(
                            [ft.Text(f"- {w}", size=12, color=ft.colors.ORANGE_700)
                             for w in warnings],
                            scroll=ft.ScrollMode.AUTO,
                            spacing=6,
                        ),
                    ),
                    actions=[ft.TextButton(
                        "OK",
                        on_click=lambda e: setattr(warn_dialog, 'open', False)
                    )],
                )
                self.page.overlay.append(warn_dialog)
                warn_dialog.open = True
                self.page.update()

        except Exception as ex:
            print(f"Import error: {ex}")
            traceback.print_exc()
            self.page.show_snack_bar(
                ft.SnackBar(
                    content=ft.Text(f"Import error: {str(ex)}"),
                    bgcolor=ft.colors.RED
                )
            )

    def close_dialog(self, e):
        """Close the dialog."""
        self.dialog.open = False
        self.page.update()
    
    async def refresh(self, e):
        """Refresh classes list with spinner animation."""
        import asyncio
        btn = self._btn_refresh
        # Spin animation
        btn.icon       = ft.icons.HOURGLASS_TOP_ROUNDED
        btn.icon_color = ft.colors.YELLOW_200
        btn.disabled   = True
        self.page.update()
        await asyncio.sleep(0.15)
        # Reload data
        self.load_classes()
        self.load_rooms()
        self.load_subjects()
        self.load_teachers()
        # Success state
        btn.icon       = ft.icons.CHECK_ROUNDED
        btn.icon_color = "#4ADE80"
        btn.disabled   = False
        self.page.update()
        await asyncio.sleep(1.2)
        # Reset
        btn.icon       = ft.icons.REFRESH_ROUNDED
        btn.icon_color = ft.colors.WHITE
        self.page.update()
        self.page.show_snack_bar(
            ft.SnackBar(content=ft.Text("Classes refreshed!"), bgcolor=ft.colors.GREEN)
        )