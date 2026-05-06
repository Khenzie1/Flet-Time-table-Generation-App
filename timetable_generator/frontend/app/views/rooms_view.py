"""Rooms management view - Complete working version (fixed GridView)."""
import flet as ft
import uuid
import traceback

def _norm_role(role: str) -> str:
    """Normalise role string to uppercase regardless of source."""
    return (role or "VIEWER").strip().upper()

def _can_edit(role: str) -> bool:
    """Admin and Coordinator may mutate data; Viewer is read-only."""
    return _norm_role(role) in ("ADMIN", "COORDINATOR")



class RoomsView:
    """Rooms management screen."""
    
    def __init__(self, app):
        self.app = app
        self.page = app.page
        self._role = _norm_role((app.current_user or {}).get("role", "VIEWER"))
        self.search_field = ft.TextField(
            hint_text="Search rooms...",
            prefix_icon=ft.icons.SEARCH,
            expand=True,
            on_change=self.search_rooms
        )
        self.type_tabs = ft.Tabs(
            selected_index=0,
            tabs=[
                ft.Tab(text="All"),
                ft.Tab(text="Regular"),
                ft.Tab(text="Lab"),
                ft.Tab(text="Workshop"),
                ft.Tab(text="Hall"),
            ],
            on_change=self.filter_by_type
        )
        
        # Rooms grid – FIXED: removed max_axis_extent
        self.rooms_grid = ft.GridView(
            runs_count=3,
            spacing=20,
            padding=20,
            child_aspect_ratio=1.0  # optional, helps with sizing
        )
        
        # Add/Edit Dialog — save button stored for animation
        self._btn_save_room = ft.ElevatedButton(
            "Save",
            icon=ft.icons.SAVE_ROUNDED,
            on_click=self._save_room_animated,
            style=ft.ButtonStyle(
                bgcolor={"": "#2563EB", "hovered": "#1E40AF"},
                color=ft.colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8),
                elevation={"": 0, "hovered": 2},
            ),
        )

        # Add/Edit Dialog
        self.dialog = ft.AlertDialog(
            title=ft.Text("Add Room"),
            content=ft.Container(
                width=400,
                height=500,
                content=ft.Column([
                    ft.TextField(label="Room Code", autofocus=True,
                               hint_text="e.g., BIO-LAB"),
                    ft.TextField(label="Room Name",
                               hint_text="e.g., Biology Laboratory"),
                    ft.TextField(
                        label="Capacity",
                        value="40",
                        keyboard_type=ft.KeyboardType.NUMBER
                    ),
                    ft.Dropdown(
                        label="Room Type",
                        options=[
                            ft.dropdown.Option("Regular"),
                            ft.dropdown.Option("Lab"),
                            ft.dropdown.Option("Workshop"),
                            ft.dropdown.Option("Hall"),
                        ],
                        value="Regular"
                    ),
                    ft.Switch(label="Available", value=True),
                    ft.TextField(
                        label="Dedicated Subject Code(s) (optional)",
                        hint_text="e.g., BIO  or  BIO,IBIBS  for multiple subjects",
                    ),
                ], spacing=10),
                padding=20
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self.close_dialog,
                              style=ft.ButtonStyle(color=ft.colors.GREY_600)),
                self._btn_save_room,
            ]
        )
        
        # Unavailability Dialog
        self.unavail_dialog = ft.AlertDialog(
            title=ft.Text("Room Unavailability"),
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
        
        self.current_room_id = None
        self.all_rooms = []
        self.selected_ids = set()
        self.unavail_list = None

        # Refresh button — stored so refresh() can animate it
        self._btn_refresh = ft.IconButton(
            icon=ft.icons.REFRESH_ROUNDED,
            icon_color=ft.colors.WHITE, icon_size=18,
            tooltip="Refresh",
            on_click=self.refresh,
        )

        # Live count label — updated by display_rooms() on every data change
        self._lbl_count_top = ft.Text(
            "0 rooms", size=12,
            color=ft.colors.with_opacity(0.6, ft.colors.WHITE))

        # Add dialogs to overlay
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

        # Add dialogs to overlay
        if self.dialog not in self.page.overlay:
            self.page.overlay.append(self.dialog)
        if self.unavail_dialog not in self.page.overlay:
            self.page.overlay.append(self.unavail_dialog)
    
    def build(self):
        """Build the rooms view."""
        self.load_rooms()
        self.unavail_list = self.unavail_dialog.content.content.controls[5]
        
        return ft.View(
            "/rooms",
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
                        ft.Icon(ft.icons.MEETING_ROOM_ROUNDED,
                                color=ft.colors.WHITE, size=20),
                        ft.Text("Rooms Management", size=17,
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
                                    "+ Add Room",
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

                        # ── Type tabs ──────────────────────────────────
                        ft.Container(
                            content=self.type_tabs,
                            bgcolor=ft.colors.WHITE,
                            border_radius=12,
                            padding=ft.padding.symmetric(horizontal=12, vertical=4),
                            shadow=ft.BoxShadow(
                                spread_radius=0, blur_radius=8,
                                color=ft.colors.with_opacity(0.06, ft.colors.BLACK),
                                offset=ft.Offset(0, 2)),
                        ),

                        ft.Container(height=10),

                        # ── Bulk-select bar ────────────────────────────
                        self._sel_bar,

                        # ── Rooms grid ─────────────────────────────────
                        ft.Container(
                            content=self.rooms_grid,
                            expand=True,
                            bgcolor=ft.colors.WHITE,
                            border_radius=12,
                            padding=10,
                            shadow=ft.BoxShadow(
                                spread_radius=0, blur_radius=8,
                                color=ft.colors.with_opacity(0.06, ft.colors.BLACK),
                                offset=ft.Offset(0, 2)),
                        ),
                    ], expand=True),
                    padding=20,
                    expand=True,
                    bgcolor="#F8FAFC",
                )
            ],
            padding=0,
            spacing=0,
        )
    
    # --------------------------------------------------------------------------
    # All existing data methods (keep as originally provided)
    # --------------------------------------------------------------------------
    def load_rooms(self):
        try:
            # Migrate existing DBs — add subject_code if not present
            try:
                self.app.local_db.execute("ALTER TABLE rooms ADD COLUMN subject_code TEXT")
                print("Migrated rooms table: added subject_code column")
            except Exception:
                pass  # Column already exists

            rooms = self.app.local_db.execute(
                "SELECT * FROM rooms ORDER BY room_type, room_code"
            )
            self.all_rooms = rooms if rooms else []
            self.display_rooms()
            print(f"Loaded {len(self.all_rooms)} rooms")
        except Exception as e:
            print(f"Error loading rooms: {e}")
            traceback.print_exc()
            self.all_rooms = []
    
    # ── bulk-select helpers ──────────────────────────────────────────────────
    def _update_sel_bar(self):
        n = len(self.selected_ids)
        self._sel_bar.visible = n > 0
        self._sel_count_lbl.value = f"{n} room(s) selected"
        self.page.update()

    def _clear_selection(self, e=None):
        self.selected_ids.clear()
        self._update_sel_bar()
        self.display_rooms()

    def _bulk_delete_confirm(self, e):
        if not _can_edit(self._role): return
        n = len(self.selected_ids)
        if n == 0:
            return
        ids_snap = set(self.selected_ids)

        def _do(e):
            dlg.open = False
            self.page.update()
            deleted = 0
            for rid in ids_snap:
                try:
                    self.app.local_db.execute(
                        "DELETE FROM rooms_unavailability WHERE room_id=?", (rid,))
                    self.app.local_db.delete("rooms", rid)
                    deleted += 1
                except Exception as ex:
                    print(f"Bulk delete {rid}: {ex}")
            self.selected_ids.clear()
            self.load_rooms()
            self._update_sel_bar()
            self.page.show_snack_bar(ft.SnackBar(
                content=ft.Text(f"Deleted {deleted} room(s) successfully."),
                bgcolor=ft.colors.GREEN))

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Delete Selected Rooms", color=ft.colors.RED_700),
            content=ft.Text(f"Delete {n} room(s) and all unavailability records? This cannot be undone."),
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

    def display_rooms(self, rooms=None):
        if rooms is None:
            rooms = self.all_rooms
        self.rooms_grid.controls = []
        for room in rooms:
            try:
                unavail = self.app.local_db.execute(
                    "SELECT COUNT(*) as count FROM rooms_unavailability WHERE room_id = ?",
                    (room['id'],)
                )
                unavail_count = unavail[0]['count'] if unavail else 0
            except:
                unavail_count = 0
            is_available = room.get('is_available', 1)
            if isinstance(is_available, str):
                is_available = int(is_available) if is_available.isdigit() else 1
            rid = room.get('id', '')
            is_selected = rid in self.selected_ids

            def _toggle(e, rid=rid):
                if rid in self.selected_ids:
                    self.selected_ids.discard(rid)
                else:
                    self.selected_ids.add(rid)
                self._update_sel_bar()
                self.display_rooms()

            card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Checkbox(
                            value=is_selected,
                            on_change=_toggle,
                            visible=_can_edit(self._role),
                        ),
                        ft.Icon(self._get_room_icon(room['room_type']), size=28,
                                color=self._get_type_color(room['room_type'])),
                        ft.Column([
                            ft.Text(room['room_code'], weight=ft.FontWeight.BOLD, size=14),
                            ft.Text(room['room_name'], size=12, color=ft.colors.GREY_700),
                        ], spacing=0, expand=True),
                    ], spacing=8),
                    ft.Divider(height=1),
                    ft.Row([
                        ft.Container(
                            content=ft.Text(room['room_type'], size=11, color=ft.colors.WHITE),
                            padding=ft.padding.symmetric(horizontal=7, vertical=2),
                            border_radius=8,
                            bgcolor=self._get_type_color(room['room_type'])),
                        ft.Text(f"Cap: {room['capacity']}", size=12, color=ft.colors.GREY_700),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(
                        f"For: {room['subject_code'].replace(',', ', ')}" if room.get('subject_code') else "Shared / General",
                        size=11,
                        color=ft.colors.BLUE_600 if room.get('subject_code') else ft.colors.GREY_400,
                        italic=not room.get('subject_code')),
                    ft.Row([
                        ft.Icon(
                            ft.icons.CHECK_CIRCLE if is_available else ft.icons.CANCEL,
                            size=14,
                            color=ft.colors.GREEN if is_available else ft.colors.RED),
                        ft.Text("Available" if is_available else "Unavailable", size=11),
                        ft.Container(expand=True),
                        ft.Text(f"Unavail: {unavail_count}", size=11, color=ft.colors.GREY_600),
                    ]),
                    ft.Divider(height=1),
                    ft.Row([
                        ft.IconButton(icon=ft.icons.EDIT, icon_size=18,
                            visible=_can_edit(self._role),
                            on_click=lambda e, r=room: self.open_edit_dialog(r)),
                        ft.IconButton(icon=ft.icons.SCHEDULE, icon_size=18,
                            visible=_can_edit(self._role),
                            on_click=lambda e, r=room: self.manage_unavailability(r)),
                        ft.IconButton(icon=ft.icons.DELETE, icon_size=18,
                            visible=_can_edit(self._role),
                            icon_color=ft.colors.RED_400,
                            on_click=lambda e, r=room: self.delete_room(r)),
                        ft.Tooltip(
                            message="View only",
                            content=ft.Icon(ft.icons.VISIBILITY_OUTLINED,
                                            size=16, color=ft.colors.GREY_400,
                                            visible=not _can_edit(self._role))),
                    ], alignment=ft.MainAxisAlignment.END, spacing=0)
                ], spacing=6),
                padding=14,
                bgcolor="#EFF6FF" if is_selected else ft.colors.WHITE,
                border_radius=10,
                border=ft.border.all(2, "#2563EB") if is_selected else ft.border.all(1, "#E2E8F0"),
                shadow=ft.BoxShadow(spread_radius=0, blur_radius=6,
                                    color=ft.colors.with_opacity(0.08, ft.colors.BLACK))
            )
            self.rooms_grid.controls.append(card)
        n = len(self.all_rooms)
        self._lbl_count_top.value = f"{n} room{'s' if n != 1 else ''}"
        self.page.update()
    
    def _get_room_icon(self, room_type):
        icons = {
            'Regular': ft.icons.MEETING_ROOM,
            'Lab': ft.icons.SCIENCE,
            'Workshop': ft.icons.CONSTRUCTION,
            'Hall': ft.icons.MEETING_ROOM
        }
        return icons.get(room_type, ft.icons.ROOM)
    
    def _get_type_color(self, room_type):
        colors = {
            'Regular':  "#2563EB",
            'Lab':      "#16A34A",
            'Workshop': "#D97706",
            'Hall':     "#7C3AED",
        }
        return colors.get(room_type, "#64748B")
    
    def search_rooms(self, e):
        search = self.search_field.value.lower() if self.search_field.value else ""
        if not search:
            self.display_rooms()
            return
        filtered = [
            r for r in self.all_rooms
            if search in r.get('room_code', '').lower()
            or search in r.get('room_name', '').lower()
        ]
        self.display_rooms(filtered)
    
    def filter_by_type(self, e):
        tab_index = self.type_tabs.selected_index
        types = ["All", "Regular", "Lab", "Workshop", "Hall"]
        selected = types[tab_index]
        if selected == "All":
            self.display_rooms()
        else:
            filtered = [r for r in self.all_rooms if r.get('room_type') == selected]
            self.display_rooms(filtered)
    
    def open_add_dialog(self, e):
        if not _can_edit(self._role): return
        self.dialog.title = ft.Text("Add Room")
        self.current_room_id = None
        content = self.dialog.content.content
        content.controls[0].value = ""
        content.controls[1].value = ""
        content.controls[2].value = "40"
        content.controls[3].value = "Regular"
        content.controls[4].value = True
        content.controls[5].value = ""
        self.dialog.open = True
        self.page.update()
    
    def open_edit_dialog(self, room):
        if not _can_edit(self._role): return
        self.dialog.title = ft.Text("Edit Room")
        self.current_room_id = room['id']
        content = self.dialog.content.content
        content.controls[0].value = room.get('room_code', '')
        content.controls[1].value = room.get('room_name', '')
        content.controls[2].value = str(room.get('capacity', 40))
        content.controls[3].value = room.get('room_type', 'Regular')
        is_available = room.get('is_available', 1)
        if isinstance(is_available, str):
            is_available = int(is_available) if is_available.isdigit() else 1
        content.controls[4].value = bool(is_available)
        content.controls[5].value = room.get('subject_code') or ''
        self.dialog.open = True
        self.page.update()
    
    # ══════════════════════════════════════════════════════════════════════
    # BUTTON ANIMATION HELPERS
    # ══════════════════════════════════════════════════════════════════════
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

    async def _save_room_animated(self, e):
        await self._animate_elevated_btn(self._btn_save_room, self.save_room, e)

    def save_room(self, e):
        if not _can_edit(self._role): return
        content = self.dialog.content.content
        room_data = {
            'room_code': content.controls[0].value.upper(),
            'room_name': content.controls[1].value,
            'capacity': int(content.controls[2].value) if content.controls[2].value else 0,
            'room_type': content.controls[3].value,
            'is_available': 1 if content.controls[4].value else 0,
            'subject_code': (
                ",".join(
                    t.strip().upper()
                    for t in content.controls[5].value.split(",")
                    if t.strip()
                ) or None
            ) if content.controls[5].value else None,
        }
        if not room_data['room_code'] or not room_data['room_name']:
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Room code and name are required!"), bgcolor=ft.colors.RED))
            return
        try:
            if self.current_room_id:
                self.app.local_db.update("rooms", self.current_room_id, room_data)
            else:
                room_data['id'] = str(uuid.uuid4())
                self.app.local_db.insert("rooms", room_data)
            self.close_dialog(None)
            self.load_rooms()
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Room saved successfully!"), bgcolor=ft.colors.GREEN))
        except Exception as e:
            print(f"Error saving room: {e}")
            traceback.print_exc()
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text(f"Error: {str(e)}"), bgcolor=ft.colors.RED))
    
    def manage_unavailability(self, room):
        if not _can_edit(self._role): return
        self.current_room_id = room['id']
        self.unavail_dialog.title = ft.Text(f"Unavailability - {room.get('room_code')}")
        self.load_unavailability()
        self.unavail_dialog.open = True
        self.page.update()
    
    def load_unavailability(self):
        try:
            unavail = self.app.local_db.execute(
                "SELECT * FROM rooms_unavailability WHERE room_id = ? ORDER BY day_of_week, period_number",
                (self.current_room_id,)
            ) or []
            if self.unavail_list:
                self.unavail_list.controls = []
                for u in unavail:
                    row = ft.ListTile(
                        title=ft.Text(f"{u['day_of_week']} - Period {u['period_number']}"),
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
        content = self.unavail_dialog.content.content
        if not content.controls[0].value or not content.controls[1].value:
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Please select day and period"), bgcolor=ft.colors.RED))
            return
        try:
            unavail_data = {
                'room_id': self.current_room_id,
                'day_of_week': content.controls[0].value,
                'period_number': int(content.controls[1].value)
            }
            self.app.local_db.insert("rooms_unavailability", unavail_data)
            content.controls[0].value = None
            content.controls[1].value = ""
            self.load_unavailability()
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Unavailability added!"), bgcolor=ft.colors.GREEN))
        except Exception as e:
            print(f"Error adding unavailability: {e}")
    
    def delete_unavailability(self, unavail_id):
        try:
            self.app.local_db.execute("DELETE FROM rooms_unavailability WHERE id = ?", (unavail_id,))
            self.load_unavailability()
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Unavailability removed!"), bgcolor=ft.colors.GREEN))
        except Exception as e:
            print(f"Error deleting unavailability: {e}")
    
    def delete_room(self, room):
        if not _can_edit(self._role): return
        def confirm_delete(e):
            try:
                in_use = self.app.local_db.execute(
                    "SELECT COUNT(*) as count FROM timetable_slots WHERE room_id = ?",
                    (room['id'],)
                )
                if in_use and in_use[0]['count'] > 0:
                    self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Cannot delete room - it is used in timetables!"), bgcolor=ft.colors.RED))
                    dialog.open = False
                    self.page.update()
                    return
                self.app.local_db.execute("DELETE FROM rooms_unavailability WHERE room_id = ?", (room['id'],))
                self.app.local_db.delete("rooms", room['id'])
                dialog.open = False
                self.load_rooms()
                self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Room deleted successfully!"), bgcolor=ft.colors.GREEN))
                self.page.update()
            except Exception as ex:
                print(f"Error deleting room: {ex}")
        dialog = ft.AlertDialog(
            title=ft.Text("Confirm Delete"),
            content=ft.Text(f"Are you sure you want to delete {room.get('room_code')}?"),
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
            dialog_title="Select Rooms file (CSV or Excel)",
            allow_multiple=False,
            allowed_extensions=["csv", "xlsx", "xls"],
        )

    def _read_import_rows(self, file_path):
        """Return list of dicts from CSV or XLSX. All keys lowercased and stripped."""
        import csv, os
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ('.xlsx', '.xls'):
            import openpyxl
            wb = openpyxl.load_workbook(file_path, data_only=True)
            ws = wb.active
            raw_headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
            headers = [
                str(h).lower().strip() if h else f'col_{i}'
                for i, h in enumerate(raw_headers)
            ]
            rows = []
            for row in ws.iter_rows(min_row=2, values_only=True):
                if all(v is None for v in row):
                    continue
                rows.append({
                    headers[i]: (str(v).strip() if v is not None else '')
                    for i, v in enumerate(row)
                })
            return rows
        else:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                return [{k.lower().strip(): (v.strip() if v else '') for k, v in r.items()}
                        for r in reader]

    def process_bulk_import(self, file_path):
        """Process bulk import from CSV or XLSX.

        Accepted column names (case-insensitive):
          room_code     (or: code, room code)
          room_name     (or: name, room name)
          capacity
          room_type     (or: type) — Regular, Lab, Workshop, Hall
          is_available  (or: available) — true/false, 1/0, yes/no
          subject_code  (or: subject) — optional
        """
        try:
            db   = self.app.local_db
            rows = self._read_import_rows(file_path)

            if not rows:
                self.page.show_snack_bar(ft.SnackBar(
                    content=ft.Text("File is empty or could not be read."),
                    bgcolor=ft.colors.ORANGE))
                return

            detected = list(rows[0].keys())
            print(f"[Rooms Import] Detected headers: {detected}")

            created = 0
            updated = 0
            skipped = 0
            skip_reasons = []

            for i, row in enumerate(rows, start=2):
                code = (row.get('room_code') or row.get('code') or
                        row.get('room code') or '').strip().upper()
                name = (row.get('room_name') or row.get('name') or
                        row.get('room name') or '').strip()

                if not code and not name:
                    skipped += 1; continue
                if not code:
                    skip_reasons.append(f"Row {i}: missing room_code"); skipped += 1; continue
                if not name:
                    skip_reasons.append(f"Row {i}: missing room_name"); skipped += 1; continue

                try:
                    capacity = int(str(row.get('capacity') or '40').split('.')[0] or '40')
                except (ValueError, AttributeError):
                    capacity = 40

                room_type = (row.get('room_type') or row.get('type') or 'Regular').strip()
                valid_types = {'Regular', 'Lab', 'Workshop', 'Hall'}
                if room_type not in valid_types:
                    # Try title-case match
                    room_type = room_type.title()
                    if room_type not in valid_types:
                        room_type = 'Regular'

                avail_raw = (row.get('is_available') or row.get('available') or 'true').lower().strip()
                is_available = 1 if avail_raw in ('true', '1', 'yes', 'available') else 0

                subj_raw = (row.get('subject_code') or row.get('subject') or '').strip().upper()
                subject_code = subj_raw or None

                room_data = {
                    'room_code':    code,
                    'room_name':    name,
                    'capacity':     capacity,
                    'room_type':    room_type,
                    'is_available': is_available,
                    'subject_code': subject_code,
                }

                existing = db.execute("SELECT id FROM rooms WHERE room_code = ?", (code,))
                if existing:
                    db.update("rooms", existing[0]['id'], room_data)
                    updated += 1
                else:
                    room_data['id'] = str(__import__('uuid').uuid4())
                    db.insert("rooms", room_data)
                    created += 1

            for r in skip_reasons:
                print(f"[Rooms Import] Skipped: {r}")

            self.load_rooms()
            msg = f"Imported {created} new room(s), updated {updated}."
            if skipped:
                msg += f" ({skipped} row(s) skipped)"
            color = ft.colors.GREEN if (created + updated) > 0 else ft.colors.ORANGE
            self.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(msg), bgcolor=color))

            if (created + updated) == 0 and skipped > 0:
                hint = ft.AlertDialog(
                    title=ft.Text("Import Failed - Column Mismatch",
                                  color=ft.colors.ORANGE_700),
                    content=ft.Container(
                        width=460,
                        content=ft.Column([
                            ft.Text("No rooms were imported. Detected headers:", size=13),
                            ft.Container(
                                content=ft.Text(", ".join(detected) or "(none)",
                                                size=12, color=ft.colors.BLUE_700,
                                                selectable=True),
                                bgcolor=ft.colors.BLUE_50, border_radius=8, padding=10),
                            ft.Text("Expected headers:", size=13,
                                    weight=ft.FontWeight.BOLD, color=ft.colors.GREY_700),
                            ft.Text(
                                "- room_code (or: code)\n- room_name (or: name)\n- capacity\n- room_type (or: type)\n- is_available (or: available)\n- subject_code (optional)",
                                size=12, color=ft.colors.GREY_800),
                        ], spacing=10, tight=True),
                    ),
                    actions=[ft.TextButton(
                        "OK", on_click=lambda e: [setattr(hint, 'open', False),
                                                   self.page.update()])],
                )
                self.page.overlay.append(hint)
                hint.open = True
                self.page.update()

        except Exception as ex:
            print(f"Rooms import error: {ex}")
            import traceback; traceback.print_exc()
            self.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(f"Import error: {str(ex)}"),
                            bgcolor=ft.colors.RED))

    def close_dialog(self, e):
        self.dialog.open = False
        self.page.update()
    
    def close_unavail_dialog(self, e):
        self.unavail_dialog.open = False
        self.page.update()
    
    async def refresh(self, e):
        """Refresh rooms list with spinner animation."""
        import asyncio
        btn = self._btn_refresh
        btn.icon       = ft.icons.HOURGLASS_TOP_ROUNDED
        btn.icon_color = ft.colors.YELLOW_200
        btn.disabled   = True
        self.page.update()
        await asyncio.sleep(0.15)
        self.load_rooms()
        btn.icon       = ft.icons.CHECK_ROUNDED
        btn.icon_color = "#4ADE80"
        btn.disabled   = False
        self.page.update()
        await asyncio.sleep(1.2)
        btn.icon       = ft.icons.REFRESH_ROUNDED
        btn.icon_color = ft.colors.WHITE
        self.page.update()
        self.page.show_snack_bar(
            ft.SnackBar(content=ft.Text("Rooms refreshed!"), bgcolor=ft.colors.GREEN)
        )