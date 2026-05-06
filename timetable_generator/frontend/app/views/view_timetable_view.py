"""Read-only timetable viewer — supports both Class Timetable and Exam Timetable views."""
import flet as ft
import traceback
from datetime import datetime, timedelta


# ─── Exam slot time definitions ───────────────────────────────────────────────
EXAM_SLOT_TIMES = {
    1: ("8:30 AM",  "10:30 AM"),
    2: ("11:00 AM", "1:00 PM"),
    3: ("1:30 PM",  "3:30 PM"),
}
EXAM_SLOT_LABELS = {
    1: "Slot 1  •  8:30 – 10:30",
    2: "Slot 2  •  11:00 – 1:00",
    3: "Slot 3  •  1:30 – 3:30",
}
# 30-minute breaks between exam slots
EXAM_BREAK_AFTER = {
    1: ("10:30 AM", "11:00 AM"),   # break after Slot 1
    2: ("1:00 PM",  "1:30 PM"),    # break after Slot 2
}


class ViewTimetableView:
    def __init__(self, app):
        self.app  = app
        self.page = app.page
        self.current_slots        = []
        self.current_timetable_id = None
        self.days    = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        self.periods = list(range(1, 11))

        # ── Timetable type state: 'class' or 'exam' ───────────────────────
        self.timetable_type = 'class'

        # ── Dropdowns for CLASS timetable ─────────────────────────────────
        self.class_dropdown = ft.Dropdown(
            label='Select Class', width=300,
            on_change=self._load_class)
        self.teacher_dropdown = ft.Dropdown(
            label='Select Teacher', width=300,
            on_change=self._load_teacher)
        self.room_dropdown = ft.Dropdown(
            label='Select Room', width=350,
            on_change=self._load_room)

        # ── Dropdowns for EXAM timetable ──────────────────────────────────
        self.exam_class_dropdown = ft.Dropdown(
            label='Select Class', width=300,
            on_change=self._load_exam_class)

        # ── Grid container ────────────────────────────────────────────────
        self.grid_container = ft.Column(
            spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        # ── Tabs – will be swapped based on timetable type ────────────────
        self.class_tabs = ft.Tabs(
            selected_index=0,
            tabs=[
                ft.Tab(text='All Classes'),
                ft.Tab(text='By Class'),
                ft.Tab(text='By Teacher'),
                ft.Tab(text='By Room'),
            ],
            on_change=self._on_class_tab_change,
        )
        self.exam_tabs = ft.Tabs(
            selected_index=0,
            tabs=[
                ft.Tab(text='All Exams'),
                ft.Tab(text='By Class'),
            ],
            on_change=self._on_exam_tab_change,
        )

        self.selector_row = ft.Row(spacing=10)
        self.selector_container = None  # built in build()
        self.tabs_container = None      # built in build()

        # Type-selector card refs (to highlight active)
        self._class_type_card = None
        self._exam_type_card  = None

        self._building = False

        self._load_dropdowns()

    # ══════════════════════════════════════════════════════════════════════
    # Type-Selector UI  (shown at the top before anything else)
    # ══════════════════════════════════════════════════════════════════════

    def _build_type_selector(self):
        """Return the 'Choose what to view' card row."""

        def _card(icon, title, subtitle, type_key, active_color, inactive_color):
            is_active = (self.timetable_type == type_key)
            return ft.Container(
                content=ft.Column([
                    ft.Icon(icon, size=32,
                            color=ft.colors.WHITE if is_active else active_color),
                    ft.Text(title, size=15, weight=ft.FontWeight.BOLD,
                            color=ft.colors.WHITE if is_active else '#1E293B',
                            text_align=ft.TextAlign.CENTER),
                    ft.Text(subtitle, size=10, italic=True,
                            color=ft.colors.WHITE70 if is_active else '#64748B',
                            text_align=ft.TextAlign.CENTER, max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                   alignment=ft.MainAxisAlignment.CENTER, spacing=6),
                width=190, height=110,
                bgcolor=active_color if is_active else ft.colors.WHITE,
                border_radius=14,
                padding=ft.padding.all(16),
                border=ft.border.all(2, active_color if is_active else '#E2E8F0'),
                shadow=ft.BoxShadow(
                    spread_radius=0, blur_radius=14 if is_active else 6,
                    color=ft.colors.with_opacity(0.18 if is_active else 0.07, ft.colors.BLACK),
                    offset=ft.Offset(0, 4)),
                on_click=lambda e, t=type_key: self._select_type(t),
                ink=True,
            )

        class_card = _card(
            ft.icons.SCHOOL_OUTLINED,
            "Class Timetable",
            "Weekly lesson schedule by class, teacher or room",
            'class', '#1565C0', ft.colors.WHITE,
        )
        exam_card = _card(
            ft.icons.ASSIGNMENT_OUTLINED,
            "Exam Timetable",
            "Date-based exam schedule with invigilators",
            'exam', '#1565C0', ft.colors.WHITE,
        )
        self._class_type_card = class_card
        self._exam_type_card  = exam_card

        return ft.Container(
            content=ft.Column([
                ft.Text("What would you like to view?",
                        size=13, color='#64748B', italic=True),
                ft.Row([class_card, exam_card], spacing=14,
                       alignment=ft.MainAxisAlignment.CENTER),
            ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.symmetric(vertical=16, horizontal=20),
            bgcolor=ft.colors.WHITE,
            border_radius=14,
            margin=ft.margin.only(bottom=10),
            shadow=ft.BoxShadow(
                spread_radius=0, blur_radius=10,
                color=ft.colors.with_opacity(0.07, ft.colors.BLACK),
                offset=ft.Offset(0, 3)),
        )

    def _select_type(self, type_key: str):
        """Switch between 'class' and 'exam' timetable views."""
        self.timetable_type = type_key
        self.grid_container.controls.clear()

        # Rebuild type selector to reflect new active state
        self.type_selector_ref.content = self._build_type_selector()

        # Swap tabs
        if type_key == 'class':
            self.class_tabs.selected_index = 0
            self.tabs_container.content = self.class_tabs
            self._on_class_tab_change(None)
        else:
            self.exam_tabs.selected_index = 0
            self.tabs_container.content = self.exam_tabs
            self._on_exam_tab_change(None)

        if not self._building:
            if not self._building:
                self.grid_container.update()

    # ══════════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════════

    def _period_time(self, p):
        start = datetime(2000, 1, 1, 8, 0) + timedelta(minutes=(p - 1) * 40)
        end   = start + timedelta(minutes=40)
        return (start.strftime('%I:%M %p').lstrip('0'),
                end.strftime('%I:%M %p').lstrip('0'))

    def _get_break_periods(self):
        """Read break_periods from the latest published Class Timetable record.
        Falls back to {4} if the column doesn't exist or has no value."""
        try:
            rows = self.app.local_db.execute(
                "SELECT break_periods FROM timetables "
                "WHERE status='Published' AND type='Class Timetable' "
                "ORDER BY rowid DESC LIMIT 1"
            )
            if rows and rows[0].get('break_periods'):
                raw = rows[0]['break_periods']
                result = set()
                for part in str(raw).split(','):
                    part = part.strip()
                    if part.isdigit():
                        result.add(int(part))
                if result:
                    return result
        except Exception:
            pass
        return {4}

    SUBJECT_PALETTE = {
        'MATH': ('#DBEAFE','#3B82F6','#1E40AF'),
        'ENG':  ('#D1FAE5','#10B981','#065F46'),
        'PHY':  ('#EDE9FE','#8B5CF6','#1565C0'),
        'CHEM': ('#FEF3C7','#F59E0B','#78350F'),
        'BIO':  ('#CCFBF1','#14B8A6','#134E4A'),
        'COMP': ('#F3E8FF','#A855F7','#581C87'),
        'AGRI': ('#ECFCCB','#84CC16','#365314'),
        'CIVI': ('#E0F2FE','#0EA5E9','#0C4A6E'),
        'FMAT': ('#DBEAFE','#2563EB','#1E3A8A'),
        'BSCI': ('#CCFBF1','#2DD4BF','#134E4A'),
        'BTEC': ('#FEE2E2','#F87171','#7F1D1D'),
        'FART': ('#FCE7F3','#EC4899','#831843'),
        'SOS':  ('#FFEDD5','#FB923C','#431407'),
        'CRS':  ('#FEF9C3','#EAB308','#713F12'),
        'PHE':  ('#DCFCE7','#22C55E','#14532D'),
        'FRE':  ('#F0FDF4','#16A34A','#14532D'),
        'HMGT': ('#FDF4FF','#C084FC','#581C87'),
        'TD':   ('#FFF7ED','#FB923C','#7C2D12'),
        'GOVT': ('#E0F2FE','#38BDF8','#0C4A6E'),
        'ECO':  ('#F0FDF4','#86EFAC','#14532D'),
        'LIT':  ('#FDF2F8','#F472B6','#831843'),
        'HIST': ('#EEF2FF','#818CF8','#312E81'),
        'GEO':  ('#FEF2F2','#FCA5A5','#7F1D1D'),
    }

    def _palette(self, code):
        key = (code or '').upper().strip()
        for prefix, cols in self.SUBJECT_PALETTE.items():
            if key.startswith(prefix):
                return cols
        fallbacks = [
            ('#F1F5F9','#94A3B8','#334155'),('#FDF6B2','#E3A008','#723B13'),
            ('#DEF7EC','#0E9F6E','#014737'),('#FDE8E8','#F05252','#771D1D'),
            ('#E5EDFF','#6875F5','#1E429F'),('#FDF2F8','#E74694','#751A3D'),
        ]
        return fallbacks[abs(hash(code)) % len(fallbacks)]

    # ══════════════════════════════════════════════════════════════════════
    # Data loading
    # ══════════════════════════════════════════════════════════════════════

    def _load_dropdowns(self):
        try:
            db = self.app.local_db
            classes  = db.execute('SELECT id, class_name FROM classes ORDER BY class_name') or []
            teachers = db.execute('SELECT id, full_name, teacher_code FROM teachers WHERE is_active=1 ORDER BY full_name') or []
            rooms    = db.execute('SELECT id, room_code, room_name FROM rooms WHERE is_available=1 ORDER BY room_code') or []

            self.class_dropdown.options   = [ft.dropdown.Option(key=c['id'], text=c['class_name']) for c in classes]
            self.teacher_dropdown.options = [
                ft.dropdown.Option(
                    key=t['id'],
                    text=f"{t['full_name'][:30]}{'…' if len(t['full_name']) > 30 else ''} ({t['teacher_code']})"
                ) for t in teachers]
            self.room_dropdown.options    = [
                ft.dropdown.Option(
                    key=r['id'],
                    text=f"{r['room_code']} - {r['room_name'][:28]}{'…' if len(r['room_name']) > 28 else ''}"
                ) for r in rooms]

            # Exam class dropdown: group by class level (JS1, JS2, SS1…) not sections
            seen_levels = []
            for c in classes:
                lvl = self._class_level(c['class_name'])
                if lvl not in seen_levels:
                    seen_levels.append(lvl)
            self.exam_class_dropdown.options = [
                ft.dropdown.Option(key=lvl, text=lvl) for lvl in seen_levels
            ]

            if classes:
                self.class_dropdown.value      = classes[0]['id']
            if seen_levels:
                self.exam_class_dropdown.value = seen_levels[0]
            if teachers: self.teacher_dropdown.value = teachers[0]['id']
            if rooms:    self.room_dropdown.value     = rooms[0]['id']
        except Exception as e:
            print(f'dropdown error: {e}')

    def _get_timetable_id(self, ttype=None):
        """Get the latest published timetable, optionally filtered by type."""
        db = self.app.local_db
        if ttype:
            tt = db.execute(
                "SELECT id FROM timetables WHERE status='Published' AND type=? ORDER BY rowid DESC LIMIT 1",
                (ttype,))
        else:
            tt = db.execute(
                "SELECT id FROM timetables WHERE status='Published' ORDER BY rowid DESC LIMIT 1")
        if tt: return tt[0]['id']
        tt = db.execute('SELECT id FROM timetables ORDER BY rowid DESC LIMIT 1')
        return tt[0]['id'] if tt else None

    def _get_term_label(self, ttype: str) -> str:
        """Return 'Term · Academic Year' for the latest published timetable of given type."""
        try:
            rows = self.app.local_db.execute(
                "SELECT term, academic_year FROM timetables "
                "WHERE status='Published' AND type=? ORDER BY rowid DESC LIMIT 1",
                (ttype,)
            ) or []
            if rows:
                term = rows[0].get('term') or ''
                year = rows[0].get('academic_year') or ''
                if term or year:
                    return f"{term}  ·  {year}".strip(' ·')
        except Exception:
            pass
        return ''

    def _timetable_filename(self, ttype: str, suffix: str) -> str:
        """Build an export filename that includes term and academic year."""
        try:
            rows = self.app.local_db.execute(
                "SELECT term, academic_year FROM timetables "
                "WHERE status='Published' AND type=? ORDER BY rowid DESC LIMIT 1",
                (ttype,)
            ) or []
            if rows:
                term = (rows[0].get('term') or '').replace(' ', '_')
                year = (rows[0].get('academic_year') or '').replace('/', '-').replace(' ', '')
                label = ttype.replace(' ', '_')
                return f"{label}_{term}_{year}_{suffix}.xlsx"
        except Exception:
            pass
        return f"{ttype.replace(' ', '_')}_{suffix}.xlsx"

    def _term_chip(self, ttype: str) -> ft.Container:
        """Small pill showing the term next to the export button."""
        label = self._get_term_label(ttype)
        if not label:
            return ft.Container()
        return ft.Container(
            content=ft.Text(label, size=11, color=ft.colors.WHITE,
                            weight=ft.FontWeight.W_600),
            bgcolor="#2563EB",
            border_radius=20,
            padding=ft.padding.symmetric(horizontal=12, vertical=5),
        )

    # ──────────────────────────────────────────────────────────────────────
    # CLASS timetable loaders
    # ──────────────────────────────────────────────────────────────────────

    def _load_all_classes(self, e=None):
        tid = self._get_timetable_id('Class Timetable')
        if not tid:
            self._show_no_timetable(); return
        self.current_timetable_id = tid
        try:
            slots = self.app.local_db.execute("""
                SELECT ts.*, s.code as subject_code, s.name as subject_name,
                       t.full_name as teacher_name, c.class_name,
                       COALESCE(r.room_code,
                           (SELECT rd.room_code FROM rooms rd
                            WHERE rd.is_available = 1
                              AND (
                                UPPER(TRIM(rd.subject_code)) = UPPER(TRIM(s.code))
                                OR UPPER(rd.subject_code) LIKE UPPER(TRIM(s.code)) || ',%'
                                OR UPPER(rd.subject_code) LIKE '%,' || UPPER(TRIM(s.code))
                                OR UPPER(rd.subject_code) LIKE '%,' || UPPER(TRIM(s.code)) || ',%'
                              )
                            LIMIT 1)
                       ) as room_code
                FROM timetable_slots ts
                JOIN subjects s  ON ts.subject_id = s.id
                JOIN teachers t  ON ts.teacher_id = t.id
                JOIN classes  c  ON ts.class_id   = c.id
                LEFT JOIN rooms r ON ts.room_id   = r.id
                WHERE ts.timetable_id = ?
                ORDER BY c.class_name, ts.day_of_week, ts.period_number
            """, (tid,)) or []
            if not slots:
                self._show_empty(); return
            self._draw_all_classes(slots)
        except Exception as ex:
            print(f'load_all error: {ex}'); traceback.print_exc()
            self._show_empty()

    def _load_class(self, e=None):
        if not self.class_dropdown.value:
            self._show_empty(); return
        tid = self._get_timetable_id('Class Timetable')
        if not tid:
            self._show_no_timetable(); return
        self.current_timetable_id = tid
        try:
            slots = self.app.local_db.execute("""
                SELECT ts.*, s.code as subject_code, s.name as subject_name,
                       t.full_name as teacher_name,
                       COALESCE(r.room_code,
                           (SELECT rd.room_code FROM rooms rd
                            WHERE rd.is_available = 1
                              AND (
                                UPPER(TRIM(rd.subject_code)) = UPPER(TRIM(s.code))
                                OR UPPER(rd.subject_code) LIKE UPPER(TRIM(s.code)) || ',%'
                                OR UPPER(rd.subject_code) LIKE '%,' || UPPER(TRIM(s.code))
                                OR UPPER(rd.subject_code) LIKE '%,' || UPPER(TRIM(s.code)) || ',%'
                              )
                            LIMIT 1)
                       ) as room_code
                FROM timetable_slots ts
                JOIN subjects s  ON ts.subject_id = s.id
                JOIN teachers t  ON ts.teacher_id = t.id
                LEFT JOIN rooms r ON ts.room_id   = r.id
                WHERE ts.timetable_id = ? AND ts.class_id = ?
                ORDER BY ts.day_of_week, ts.period_number
            """, (tid, self.class_dropdown.value)) or []
            self.current_slots = slots
            if not slots: self._show_empty(); return
            self._draw_grid('class')
        except Exception as ex:
            print(ex); traceback.print_exc(); self._show_empty()

    def _load_teacher(self, e=None):
        if not self.teacher_dropdown.value:
            self._show_empty(); return
        tid = self._get_timetable_id('Class Timetable')
        if not tid:
            self._show_no_timetable(); return
        self.current_timetable_id = tid
        try:
            slots = self.app.local_db.execute("""
                SELECT ts.*, s.code as subject_code, s.name as subject_name,
                       t.full_name as teacher_name, c.class_name,
                       COALESCE(r.room_code,
                           (SELECT rd.room_code FROM rooms rd
                            WHERE rd.is_available = 1
                              AND (
                                UPPER(TRIM(rd.subject_code)) = UPPER(TRIM(s.code))
                                OR UPPER(rd.subject_code) LIKE UPPER(TRIM(s.code)) || ',%'
                                OR UPPER(rd.subject_code) LIKE '%,' || UPPER(TRIM(s.code))
                                OR UPPER(rd.subject_code) LIKE '%,' || UPPER(TRIM(s.code)) || ',%'
                              )
                            LIMIT 1)
                       ) as room_code
                FROM timetable_slots ts
                JOIN subjects s  ON ts.subject_id = s.id
                JOIN teachers t  ON ts.teacher_id = t.id
                JOIN classes  c  ON ts.class_id   = c.id
                LEFT JOIN rooms r ON ts.room_id   = r.id
                WHERE ts.timetable_id = ? AND ts.teacher_id = ?
                ORDER BY ts.day_of_week, ts.period_number
            """, (tid, self.teacher_dropdown.value)) or []
            self.current_slots = slots
            self._draw_grid('teacher')
        except Exception as ex:
            print(ex); self._show_empty()

    def _load_room(self, e=None):
        if not self.room_dropdown.value:
            self._show_empty(); return
        tid = self._get_timetable_id('Class Timetable')
        if not tid:
            self._show_no_timetable(); return
        self.current_timetable_id = tid
        try:
            slots = self.app.local_db.execute("""
                SELECT ts.*, s.code as subject_code, s.name as subject_name,
                       c.class_name, t.full_name as teacher_name, r.room_code
                FROM timetable_slots ts
                JOIN subjects s  ON ts.subject_id = s.id
                JOIN classes  c  ON ts.class_id   = c.id
                JOIN teachers t  ON ts.teacher_id = t.id
                LEFT JOIN rooms r ON ts.room_id   = r.id
                WHERE ts.timetable_id = ? AND ts.room_id = ?
                ORDER BY ts.day_of_week, ts.period_number
            """, (tid, self.room_dropdown.value)) or []
            self.current_slots = slots
            self._draw_grid('room')
        except Exception as ex:
            print(ex); self._show_empty()

    # ──────────────────────────────────────────────────────────────────────
    # EXAM timetable loaders
    # ──────────────────────────────────────────────────────────────────────

    # ── helpers for safe column reading ─────────────────────────────────

    @staticmethod
    def _slot_get(slot, col, default=''):
        """Read a column from a slot dict; return default if missing/None."""
        v = slot.get(col)
        return v if v is not None else default

    CORE_PREFIXES = ('MATH','ENG','BSCI','IS','CIVI','SOS','AGRI',
                     'BTEC','PHE','IRS','CRS')

    def _is_core_code(self, code: str) -> bool:
        c = (code or '').upper().strip()
        return any(c.startswith(p) for p in self.CORE_PREFIXES)

    @staticmethod
    def _class_level(class_name: str) -> str:
        """Strip trailing section letter(s) to get class level.
        e.g. 'JS1A' → 'JS1',  'JSS2B' → 'JSS2',  'SS1K' → 'SS1'.
        Names that already have no trailing letter are returned unchanged."""
        import re
        result = re.sub(r'[A-Za-z]+$', '', (class_name or '').strip())
        return result if result else (class_name or '')

    @staticmethod
    def _is_junior(class_level: str) -> bool:
        """Return True if the class level belongs to Junior Secondary."""
        cl = (class_level or '').upper().strip()
        return cl.startswith('JS')

    def _enrich_exam_slots(self, slots: list) -> list:
        """
        Attach exam_date, exam_slot, invigilator details to each slot dict.
        Uses a separate query for the ALTER TABLE columns so a missing column
        can never kill the whole load.  Falls back gracefully to empty strings.
        """
        db = self.app.local_db
        ids = tuple(s['id'] for s in slots if s.get('id'))
        exam_extra: dict = {}
        if ids:
            try:
                rows = db.execute(
                    "SELECT id, exam_date, exam_slot, invigilator_id "
                    "FROM timetable_slots WHERE id IN ({})".format(
                        ','.join('?' * len(ids))),
                    ids) or []
                exam_extra = {r['id']: r for r in rows}
            except Exception as ex:
                print(f"exam_extra query failed (ALTER TABLE columns absent?): {ex}")

        # Invigilator names — fetched once
        invig_map: dict = {}
        invig_ids = {r.get('invigilator_id') for r in exam_extra.values()
                     if r.get('invigilator_id')}
        if invig_ids:
            try:
                rows = db.execute(
                    "SELECT id, full_name, teacher_code FROM teachers "
                    "WHERE id IN ({})".format(','.join('?' * len(invig_ids))),
                    tuple(invig_ids)) or []
                invig_map = {r['id']: r for r in rows}
            except Exception:
                pass

        enriched = []
        for s in slots:
            d = dict(s)
            extra = exam_extra.get(d.get('id'), {})
            d['exam_date']        = extra.get('exam_date') or ''
            d['exam_slot']        = extra.get('exam_slot') or 0
            inv_id                = extra.get('invigilator_id') or ''
            inv                   = invig_map.get(inv_id, {})
            d['invigilator_name'] = inv.get('full_name', '')
            d['invigilator_code'] = inv.get('teacher_code', '')
            # is_core: prefer DB value, fall back to code-prefix heuristic
            d['is_core'] = bool(d.get('is_core', 0)) or self._is_core_code(d.get('subject_code',''))
            enriched.append(d)
        return enriched

    def _load_exam_all(self, e=None):
        """Load and display the master exam timetable (all classes)."""
        tid = self._get_timetable_id('Exam Timetable')
        print(f"[exam_all] timetable_id={tid}")
        if not tid:
            self._show_no_exam_timetable(); return
        self.current_timetable_id = tid
        try:
            # Try full query including ALTER TABLE columns directly
            slots = None
            try:
                slots = self.app.local_db.execute("""
                    SELECT ts.id, ts.class_id, ts.subject_id, ts.room_id,
                           ts.exam_date, ts.exam_slot, ts.invigilator_id,
                           s.code  as subject_code, s.name as subject_name,
                           c.class_name, r.room_code,
                           inv.full_name as invigilator_name,
                           inv.teacher_code as invigilator_code
                    FROM timetable_slots ts
                    JOIN subjects  s   ON ts.subject_id      = s.id
                    JOIN classes   c   ON ts.class_id         = c.id
                    LEFT JOIN rooms r   ON ts.room_id          = r.id
                    LEFT JOIN teachers inv ON ts.invigilator_id = inv.id
                    WHERE ts.timetable_id = ?
                    ORDER BY ts.exam_date, ts.exam_slot, c.class_name
                """, (tid,)) or []
            except Exception as qex:
                print(f"[exam_all] full query failed ({qex}), falling back")

            if slots is None:
                # Fallback: columns may not exist yet, use _enrich_exam_slots
                base = self.app.local_db.execute("""
                    SELECT ts.id, ts.class_id, ts.subject_id, ts.room_id,
                           s.code as subject_code, s.name as subject_name,
                           c.class_name, r.room_code
                    FROM timetable_slots ts
                    JOIN subjects s  ON ts.subject_id = s.id
                    JOIN classes  c  ON ts.class_id   = c.id
                    LEFT JOIN rooms r ON ts.room_id   = r.id
                    WHERE ts.timetable_id = ?
                    ORDER BY c.class_name
                """, (tid,)) or []
                slots = self._enrich_exam_slots(base)

            # Normalise: ensure exam_slot is int, add is_core
            slots = [dict(s) for s in slots]
            for s in slots:
                s['exam_slot'] = int(s.get('exam_slot') or 0)
                s['is_core'] = bool(s.get('is_core', 0)) or self._is_core_code(s.get('subject_code',''))

            slots = [s for s in slots if s.get('exam_date')]
            print(f"[exam_all] final slot count: {len(slots)}")
            if not slots:
                self._show_no_exam_timetable(); return
            self._draw_exam_all(slots)
        except Exception as ex:
            print(f'load_exam_all error: {ex}'); traceback.print_exc()
            self._show_empty()

    def _load_exam_class(self, e=None):
        """Load exam schedule for a specific class level (all sections combined)."""
        if not self.exam_class_dropdown.value:
            self._show_empty(); return
        tid = self._get_timetable_id('Exam Timetable')
        print(f"[exam_class] timetable_id={tid}")
        if not tid:
            self._show_no_exam_timetable(); return
        self.current_timetable_id = tid
        try:
            level = self.exam_class_dropdown.value  # e.g. 'JS1', 'SS2'
            slots = None
            try:
                slots = self.app.local_db.execute("""
                    SELECT ts.id, ts.class_id, ts.subject_id, ts.room_id,
                           ts.exam_date, ts.exam_slot, ts.invigilator_id,
                           s.code  as subject_code, s.name as subject_name,
                           c.class_name, r.room_code,
                           inv.full_name as invigilator_name,
                           inv.teacher_code as invigilator_code
                    FROM timetable_slots ts
                    JOIN subjects  s   ON ts.subject_id      = s.id
                    JOIN classes   c   ON ts.class_id         = c.id
                    LEFT JOIN rooms r   ON ts.room_id          = r.id
                    LEFT JOIN teachers inv ON ts.invigilator_id = inv.id
                    WHERE ts.timetable_id = ? AND c.class_name LIKE ?
                    ORDER BY ts.exam_date, ts.exam_slot
                """, (tid, level + '%')) or []
            except Exception as qex:
                print(f"[exam_class] full query failed ({qex}), falling back")

            if slots is None:
                base = self.app.local_db.execute("""
                    SELECT ts.id, ts.class_id, ts.subject_id, ts.room_id,
                           s.code as subject_code, s.name as subject_name,
                           c.class_name, r.room_code
                    FROM timetable_slots ts
                    JOIN subjects s  ON ts.subject_id = s.id
                    JOIN classes  c  ON ts.class_id   = c.id
                    LEFT JOIN rooms r ON ts.room_id   = r.id
                    WHERE ts.timetable_id = ? AND c.class_name LIKE ?
                """, (tid, level + '%')) or []
                slots = self._enrich_exam_slots(base)

            slots = [dict(s) for s in slots]
            for s in slots:
                s['exam_slot'] = int(s.get('exam_slot') or 0)
                s['is_core'] = bool(s.get('is_core', 0)) or self._is_core_code(s.get('subject_code',''))

            slots = sorted(
                [s for s in slots if s.get('exam_date')],
                key=lambda x: (x['exam_date'], x['exam_slot'])
            )
            print(f"[exam_class] final slot count: {len(slots)}")
            if not slots:
                self._show_no_exam_timetable(); return
            self._draw_exam_by_class(slots, class_level=level)
        except Exception as ex:
            print(ex); traceback.print_exc(); self._show_empty()

    # ──────────────────────────────────────────────────────────────────────
    # Tab switching — CLASS
    # ──────────────────────────────────────────────────────────────────────

    def _export_btn(self, handler):
        return ft.ElevatedButton(
            'Export Excel', icon=ft.icons.DOWNLOAD, on_click=handler,
            style=ft.ButtonStyle(
                bgcolor=ft.colors.GREEN_600, color=ft.colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8)),
        )

    def _on_class_tab_change(self, e=None):
        idx = self.class_tabs.selected_index
        self.selector_container.visible = True
        if idx == 0:
            self.selector_row.controls = [
                self._term_chip('Class Timetable'),
                self._export_btn(self.export_all),
            ]
            self._load_all_classes()
        elif idx == 1:
            self.selector_row.controls = [
                self._term_chip('Class Timetable'),
                self.class_dropdown,
                ft.ElevatedButton('Refresh', icon=ft.icons.REFRESH, on_click=self._load_class),
                self._export_btn(self.export_class),
            ]
            self._load_class()
        elif idx == 2:
            self.selector_row.controls = [
                self._term_chip('Class Timetable'),
                self.teacher_dropdown,
                ft.ElevatedButton('Refresh', icon=ft.icons.REFRESH, on_click=self._load_teacher),
                self._export_btn(self.export_teacher),
            ]
            self._load_teacher()
        else:
            self.selector_row.controls = [
                self._term_chip('Class Timetable'),
                self.room_dropdown,
                ft.ElevatedButton('Refresh', icon=ft.icons.REFRESH, on_click=self._load_room),
                self._export_btn(self.export_room),
            ]
            self._load_room()
        if not self._building:
            self.page.update()

    # ──────────────────────────────────────────────────────────────────────
    # Tab switching — EXAM
    # ──────────────────────────────────────────────────────────────────────

    def _on_exam_tab_change(self, e=None):
        idx = self.exam_tabs.selected_index
        self.selector_container.visible = True
        if idx == 0:
            self.selector_row.controls = [
                self._term_chip('Exam Timetable'),
                self._export_btn(self.export_exam_all),
            ]
            self._load_exam_all()
        else:
            self.selector_row.controls = [
                self._term_chip('Exam Timetable'),
                self.exam_class_dropdown,
                ft.ElevatedButton('Refresh', icon=ft.icons.REFRESH,
                                  on_click=self._load_exam_class),
                self._export_btn(self.export_exam_class),
            ]
            self._load_exam_class()
        if not self._building:
            self.page.update()

    # ══════════════════════════════════════════════════════════════════════
    # CLASS TIMETABLE GRID DRAWING
    # ══════════════════════════════════════════════════════════════════════

    def _build_grid_rows(self, slots, view_type, periods_to_show):
        CELL_W = 140
        DAY_W  = 80
        HDR_H  = 50
        ROW_H  = 86
        RADIUS = 10
        DAY_BGS = ['#EBF3FB','#F5F5F5','#EBF3FB','#F5F5F5','#EBF3FB']

        rows = []
        header_cells = [
            ft.Container(
                ft.Text('Day', weight=ft.FontWeight.BOLD, color=ft.colors.WHITE, size=12),
                width=DAY_W, height=HDR_H, bgcolor='#1565C0',
                border_radius=ft.border_radius.only(top_left=RADIUS, bottom_left=RADIUS),
                alignment=ft.alignment.center,
            )
        ]
        BREAK_P = self._get_break_periods()
        for i, period in enumerate(periods_to_show):
            is_last = (i == len(periods_to_show) - 1)
            t_s, t_e = self._period_time(period)
            if period in BREAK_P:
                header_cells.append(ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.FREE_BREAKFAST, color='#D97706', size=13),
                        ft.Text('BREAK', weight=ft.FontWeight.BOLD, color='#92400E', size=9),
                        ft.Text(t_s + ' - ' + t_e, size=8, color='#92400E'),
                    ], alignment=ft.MainAxisAlignment.CENTER,
                       horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                    width=CELL_W, height=HDR_H, bgcolor='#FEF3C7',
                    border_radius=ft.border_radius.only(
                        top_right=RADIUS if is_last else 0,
                        bottom_right=RADIUS if is_last else 0),
                    alignment=ft.alignment.center,
                ))
            else:
                header_cells.append(ft.Container(
                    content=ft.Column([
                        ft.Text(t_s, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE, size=10),
                        ft.Text(t_e, color='#90CAF9', size=9),
                    ], alignment=ft.MainAxisAlignment.CENTER,
                       horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
                    width=CELL_W, height=HDR_H, bgcolor='#1976D2',
                    border_radius=ft.border_radius.only(
                        top_right=RADIUS if is_last else 0,
                        bottom_right=RADIUS if is_last else 0),
                    alignment=ft.alignment.center,
                ))
        rows.append(ft.Row(header_cells, spacing=0, alignment=ft.MainAxisAlignment.CENTER))
        rows.append(ft.Container(height=3, bgcolor='#1565C0', border_radius=2,
                                 margin=ft.margin.only(bottom=4)))

        for di, day in enumerate(self.days):
            day_bg = DAY_BGS[di]
            row_cells = [
                ft.Container(
                    ft.Text(day, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE, size=11),
                    width=DAY_W, height=ROW_H, bgcolor='#2E75B6',
                    alignment=ft.alignment.center,
                )
            ]
            for period in periods_to_show:
                if period in BREAK_P:
                    row_cells.append(ft.Container(
                        content=ft.Row([ft.Icon(ft.icons.FREE_BREAKFAST, color='#D97706', size=14)],
                                       alignment=ft.MainAxisAlignment.CENTER),
                        width=CELL_W, height=ROW_H, bgcolor='#FFFBEB',
                        border=ft.border.all(1, '#FDE68A'), alignment=ft.alignment.center,
                    ))
                    continue
                slot = next(
                    (s for s in slots
                     if int(s.get('period_number') or 0) == period and s.get('day_of_week') == day), None)
                if slot:
                    bg, bc, tc = self._palette(slot.get('subject_code', ''))
                    if view_type == 'class':
                        l1 = slot.get('subject_code', '')
                        l3 = slot.get('teacher_name', '')
                        l4 = slot.get('room_code', '') or ''
                    elif view_type == 'teacher':
                        l1 = slot.get('subject_code', '')
                        l3 = slot.get('class_name', '')
                        l4 = slot.get('room_code', '') or ''
                    else:
                        l1 = slot.get('subject_code', '')
                        l3 = slot.get('class_name', '')
                        l4 = slot.get('teacher_name', '') or ''
                    cell_content = [
                        ft.Text(l1, weight=ft.FontWeight.BOLD, color=tc, size=15,
                                text_align=ft.TextAlign.CENTER),
                        ft.Container(height=1, bgcolor=bc, opacity=0.3,
                                     margin=ft.margin.symmetric(vertical=2)),
                        ft.Text(l3, size=9, color=tc, text_align=ft.TextAlign.CENTER,
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ]
                    if l4:
                        cell_content.append(ft.Container(
                            content=ft.Text(l4, size=8, color=tc, weight=ft.FontWeight.BOLD,
                                            text_align=ft.TextAlign.CENTER),
                            bgcolor='#00000015', border=ft.border.all(1, bc), border_radius=4,
                            padding=ft.padding.symmetric(horizontal=4, vertical=1),
                            margin=ft.margin.only(top=1),
                        ))
                    cell = ft.Container(
                        content=ft.Column(cell_content, alignment=ft.MainAxisAlignment.CENTER,
                                          horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                        width=CELL_W, height=ROW_H, bgcolor=bg,
                        border=ft.border.all(1.5, bc), border_radius=RADIUS,
                        padding=ft.padding.symmetric(horizontal=6, vertical=4),
                        margin=ft.margin.all(2),
                        shadow=ft.BoxShadow(spread_radius=0, blur_radius=5,
                                            color=ft.colors.with_opacity(0.09, ft.colors.BLACK),
                                            offset=ft.Offset(0, 2)),
                    )
                else:
                    cell = ft.Container(
                        ft.Text('—', color='#CBD5E1', size=18),
                        width=CELL_W, height=ROW_H, bgcolor=day_bg,
                        border=ft.border.all(1, '#E2E8F0'), border_radius=RADIUS,
                        alignment=ft.alignment.center, margin=ft.margin.all(2),
                    )
                row_cells.append(cell)
            rows.append(ft.Row(row_cells, spacing=0, alignment=ft.MainAxisAlignment.CENTER))
        return rows

    def _active_periods(self, slots):
        """
        Return the full list of periods to display as columns.
        Always shows ALL configured periods (1-9) so periods 8 and 9
        are visible even when nothing was placed there.
        """
        # Always return all periods — never hide empty late periods
        return sorted(self.periods)

    def _draw_grid(self, view_type='class'):
        self.grid_container.controls.clear()
        periods_to_show = self._active_periods(self.current_slots)
        if not periods_to_show:
            self._show_empty(); return
        grid_rows = self._build_grid_rows(self.current_slots, view_type, periods_to_show)
        self.grid_container.controls.append(
            ft.Container(
                content=ft.Row(
                    [ft.Column(grid_rows, spacing=4,
                               horizontal_alignment=ft.CrossAxisAlignment.CENTER)],
                    scroll=ft.ScrollMode.ALWAYS,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                margin=ft.margin.only(top=4),
            )
        )
        if not self._building:
            if not self._building:
                self.grid_container.update()

    def _draw_all_classes(self, all_slots):
        self.grid_container.controls.clear()
        class_order = []
        class_slots = {}
        for s in all_slots:
            cls = s.get('class_name', '')
            if cls not in class_slots:
                class_slots[cls] = []
                class_order.append(cls)
            class_slots[cls].append(s)

        if not class_order:
            self._show_empty(); return

        for cls in class_order:
            slots = class_slots[cls]
            periods_to_show = self._active_periods(slots)
            if not periods_to_show:
                continue

            grid_rows = self._build_grid_rows(slots, 'class', periods_to_show)
            grid_card = ft.Container(
                content=ft.Row(
                    [ft.Column(grid_rows, spacing=4,
                               horizontal_alignment=ft.CrossAxisAlignment.CENTER)],
                    scroll=ft.ScrollMode.ALWAYS,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                bgcolor=ft.colors.WHITE, border_radius=14,
                padding=ft.padding.only(left=16, right=16, top=28, bottom=16),
                shadow=ft.BoxShadow(spread_radius=0, blur_radius=16,
                                    color=ft.colors.with_opacity(0.09, ft.colors.BLACK),
                                    offset=ft.Offset(0, 4)),
                margin=ft.margin.only(top=24, bottom=0),
            )

            CELL_W_B = 140; DAY_W_B = 80
            BREAK_P = self._get_break_periods()
            break_col_idx = next(
                (i for i, p in enumerate(periods_to_show) if p in BREAK_P),
                len(periods_to_show) // 2
            )
            left_offset = DAY_W_B + break_col_idx * CELL_W_B

            badge = ft.Container(
                content=ft.Text(cls, size=12, weight=ft.FontWeight.BOLD,
                                color=ft.colors.WHITE, text_align=ft.TextAlign.CENTER,
                                overflow=ft.TextOverflow.ELLIPSIS, max_lines=1),
                bgcolor='#1565C0',
                border_radius=ft.border_radius.only(top_left=8, top_right=8),
                padding=ft.padding.symmetric(horizontal=8, vertical=7),
                width=CELL_W_B + 4,
                shadow=ft.BoxShadow(spread_radius=0, blur_radius=8,
                                    color=ft.colors.with_opacity(0.22, ft.colors.BLACK),
                                    offset=ft.Offset(0, -2)),
                alignment=ft.alignment.center,
            )
            badge_row = ft.Row([
                ft.Container(width=left_offset),
                badge,
                ft.Container(expand=True),
            ], spacing=0)

            block = ft.Stack([grid_card, ft.Container(content=badge_row, margin=ft.margin.only(top=0))])
            self.grid_container.controls.append(
                ft.Container(block, margin=ft.margin.only(top=20, bottom=4)))

        if not self._building:
            if not self._building:
                self.grid_container.update()

    # ══════════════════════════════════════════════════════════════════════
    # EXAM TIMETABLE GRID DRAWING
    # ══════════════════════════════════════════════════════════════════════

    def _fmt_exam_date(self, date_str: str) -> str:
        """Format 'YYYY-MM-DD' → 'Mon\n02 May'"""
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d')
            return d.strftime('%a\n%d %b')
        except Exception:
            return date_str

    def _exam_cell(self, subject_code, subject_name, extra_lines, is_core=False):
        """Build a coloured exam cell with subject + extra info lines."""
        bg, bc, tc = self._palette(subject_code)
        # Core subjects get a small badge
        badge = None
        if is_core:
            badge = ft.Container(
                content=ft.Text('CORE', size=7, weight=ft.FontWeight.BOLD, color='#FFFFFF'),
                bgcolor='#1E40AF', border_radius=4,
                padding=ft.padding.symmetric(horizontal=4, vertical=1),
                margin=ft.margin.only(bottom=2),
            )
        children = []
        if badge:
            children.append(badge)
        children += [
            ft.Text(subject_code or '', weight=ft.FontWeight.BOLD, color=tc, size=12,
                    text_align=ft.TextAlign.CENTER),
            ft.Text(subject_name or '', size=8, color=tc, opacity=0.8,
                    text_align=ft.TextAlign.CENTER, max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS),
            ft.Container(height=1, bgcolor=bc, opacity=0.2,
                         margin=ft.margin.symmetric(vertical=2)),
        ]
        for line in extra_lines:
            if line:
                children.append(
                    ft.Text(str(line), size=8, color=tc, text_align=ft.TextAlign.CENTER,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
                )
        return ft.Container(
            content=ft.Column(children, alignment=ft.MainAxisAlignment.CENTER,
                              horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
            width=160, height=106,
            bgcolor=bg, border=ft.border.all(1.5, bc), border_radius=10,
            padding=ft.padding.symmetric(horizontal=6, vertical=5),
            margin=ft.margin.all(2),
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=6,
                                color=ft.colors.with_opacity(0.10, ft.colors.BLACK),
                                offset=ft.Offset(0, 2)),
        )

    def _draw_exam_all(self, slots):
        """
        Master exam view split into two sections:
          ① JUNIOR SECONDARY  (JS*)
          ② SENIOR SECONDARY  (SS*)
        Rows = dates, Columns = Slot 1 / 2 / 3.
        Each cell shows subjects being examined, with class *levels* (JS1, JS2…)
        rather than individual sections (JS1A, JS1B…).
        """
        self.grid_container.controls.clear()

        # Attach class_level to every slot
        for s in slots:
            s['class_level'] = self._class_level(s.get('class_name', ''))

        # All unique dates, sorted
        all_dates = sorted(set(s.get('exam_date','') for s in slots if s.get('exam_date')))
        if not all_dates:
            self._show_empty(); return

        COL_ORDER  = [1, 'break1', 2, 'break2', 3]

        # ── Dynamic widths — fill the available screen width ──────────────
        # Total columns: 1 date + 3 slots + 2 breaks
        # We measure the usable content width from page.width minus all
        # Container/View padding (≈ 80px) and allocate proportionally.
        _page_w = max(int(self.page.width or 1366), 900)
        _avail  = _page_w - 120                       # larger buffer for margins + scrollbar
        DATE_W  = max(75,  int(_avail * 0.07))        # ~7 % for date column
        BREAK_W = max(70,  int(_avail * 0.05))        # wide enough for break time text
        SLOT_W  = max(160, int((_avail - DATE_W - 2 * BREAK_W) / 3))

        HDR_H      = 50
        MULTI_H    = 110
        RADIUS     = 10
        DATE_BGS   = ['#EBF3FB', '#F5F5F5', '#EBF3FB', '#F5F5F5', '#EBF3FB',
                      '#EBF3FB', '#F5F5F5']

        def _build_section_grid(section_slots, section_label, label_color, hdr_bg, date_bg_col):
            """Build header + data rows for one section (JS or SS)."""
            rows = []

            # ── Section label banner ──────────────────────────────────────
            rows.append(ft.Container(
                content=ft.Text(section_label, size=13, weight=ft.FontWeight.BOLD,
                                color=ft.colors.WHITE),
                bgcolor=label_color, border_radius=8,
                padding=ft.padding.symmetric(horizontal=14, vertical=7),
                margin=ft.margin.only(top=10, bottom=2),
            ))

            # ── Header row ────────────────────────────────────────────────
            hdr_cells = [
                ft.Container(
                    ft.Text('Date', weight=ft.FontWeight.BOLD, color=ft.colors.WHITE, size=14),
                    width=DATE_W, height=HDR_H, bgcolor=hdr_bg,
                    border_radius=ft.border_radius.only(top_left=RADIUS, bottom_left=RADIUS),
                    alignment=ft.alignment.center,
                )
            ]
            for i, col in enumerate(COL_ORDER):
                is_last = (i == len(COL_ORDER) - 1)
                if isinstance(col, str):
                    slot_no = int(col[-1])
                    b_s, b_e = EXAM_BREAK_AFTER[slot_no]
                    # Shorten e.g. "10:30 AM" → "10:30" so it fits
                    def _short(t): return t.replace(' AM','').replace(' PM','')
                    hdr_cells.append(ft.Container(
                        content=ft.Column([
                            ft.Icon(ft.icons.FREE_BREAKFAST, color='#D97706', size=18),
                            ft.Text('BREAK', weight=ft.FontWeight.BOLD, color='#92400E', size=11),
                            ft.Text(f'{_short(b_s)}–{_short(b_e)}', size=10, color='#92400E'),
                        ], alignment=ft.MainAxisAlignment.CENTER,
                           horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                        width=BREAK_W, height=HDR_H, bgcolor='#FEF3C7',
                        border_radius=ft.border_radius.only(
                            top_left=0, bottom_left=0,
                            top_right=RADIUS if is_last else 0,
                            bottom_right=RADIUS if is_last else 0),
                        alignment=ft.alignment.center,
                    ))
                else:
                    t_s, t_e = EXAM_SLOT_TIMES[col]
                    hdr_cells.append(ft.Container(
                        content=ft.Column([
                            ft.Text(f'Slot {col}', weight=ft.FontWeight.BOLD,
                                    color=ft.colors.WHITE, size=14),
                            ft.Text(f'{t_s} – {t_e}', color='#90CAF9', size=12),
                        ], alignment=ft.MainAxisAlignment.CENTER,
                           horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                        width=SLOT_W, height=HDR_H, bgcolor='#1976D2',
                        border_radius=ft.border_radius.only(
                            top_left=0, bottom_left=0,
                            top_right=RADIUS if is_last else 0,
                            bottom_right=RADIUS if is_last else 0),
                        alignment=ft.alignment.center,
                    ))
            rows.append(ft.Row(hdr_cells, spacing=0, alignment=ft.MainAxisAlignment.CENTER))
            rows.append(ft.Container(height=3, bgcolor=hdr_bg, border_radius=2,
                                     margin=ft.margin.only(bottom=4)))

            # Group slots by (date, slot_no)
            date_slot_map: dict = {}
            for s in section_slots:
                key = (s.get('exam_date',''), s.get('exam_slot', 0))
                date_slot_map.setdefault(key, []).append(s)

            # ── Data rows ─────────────────────────────────────────────────
            for di, date_str in enumerate(all_dates):
                # Skip dates with no data for this section
                has_data = any(
                    date_slot_map.get((date_str, sn))
                    for sn in [1, 2, 3]
                )
                if not has_data:
                    continue

                try:
                    d = datetime.strptime(date_str, '%Y-%m-%d')
                    date_label = d.strftime('%a\n%d %b')
                except Exception:
                    date_label = date_str

                day_bg = DATE_BGS[di % len(DATE_BGS)]
                row_cells = [
                    ft.Container(
                        ft.Text(date_label, weight=ft.FontWeight.BOLD,
                                color=ft.colors.WHITE, size=13,
                                text_align=ft.TextAlign.CENTER),
                        width=DATE_W, height=MULTI_H, bgcolor=date_bg_col,
                        alignment=ft.alignment.center,
                    )
                ]
                for col in COL_ORDER:
                    if isinstance(col, str):
                        row_cells.append(ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.icons.FREE_BREAKFAST, color='#D97706', size=18)],
                                alignment=ft.MainAxisAlignment.CENTER),
                            width=BREAK_W, height=MULTI_H, bgcolor='#FFFBEB',
                            border=ft.border.all(1, '#FDE68A'),
                            alignment=ft.alignment.center,
                        ))
                        continue

                    entries = date_slot_map.get((date_str, col), [])
                    if entries:
                        mini_tiles = []
                        seen_subj = set()
                        for ent in entries:
                            sid = ent.get('subject_id','')
                            if sid in seen_subj:
                                continue
                            seen_subj.add(sid)
                            code    = ent.get('subject_code','')
                            name    = ent.get('subject_name','')
                            is_core = bool(ent.get('is_core', 0))
                            bg, bc, tc = self._palette(code)
                            levels_here = sorted(set(
                                self._class_level(e.get('class_name',''))
                                for e in entries if e.get('subject_id') == sid
                            ))
                            cls_str = ', '.join(levels_here[:4])
                            if len(levels_here) > 4:
                                cls_str += f' +{len(levels_here)-4}'
                            mini_tiles.append(ft.Container(
                                content=ft.Column([
                                    ft.Row([
                                        ft.Text(code, weight=ft.FontWeight.BOLD, color=tc, size=14),
                                        ft.Container(
                                            ft.Text('CORE', size=9, color='#FFF'),
                                            bgcolor='#1E40AF', border_radius=3,
                                            padding=ft.padding.symmetric(horizontal=4, vertical=2),
                                            visible=is_core,
                                        ),
                                    ], spacing=4),
                                    ft.Text(name, size=11, color=tc, opacity=0.8, max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS),
                                    ft.Text(cls_str, size=11, color=tc, max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS),
                                ], spacing=3),
                                bgcolor=bg, border=ft.border.all(1.5, bc), border_radius=RADIUS,
                                padding=ft.padding.symmetric(horizontal=10, vertical=8),
                                margin=ft.margin.only(bottom=4),
                                shadow=ft.BoxShadow(spread_radius=0, blur_radius=6,
                                                    color=ft.colors.with_opacity(0.10, ft.colors.BLACK),
                                                    offset=ft.Offset(0, 2)),
                            ))
                        cell = ft.Container(
                            content=ft.Column(mini_tiles, spacing=0,
                                              scroll=ft.ScrollMode.AUTO),
                            width=SLOT_W, height=MULTI_H, bgcolor=day_bg,
                            border=ft.border.all(1, '#E2E8F0'), border_radius=RADIUS,
                            padding=ft.padding.all(8), margin=ft.margin.all(2),
                            clip_behavior=ft.ClipBehavior.HARD_EDGE,
                        )
                    else:
                        cell = ft.Container(
                            ft.Text('—', color='#CBD5E1', size=18),
                            width=SLOT_W, height=MULTI_H, bgcolor=day_bg,
                            border=ft.border.all(1, '#E2E8F0'), border_radius=RADIUS,
                            alignment=ft.alignment.center, margin=ft.margin.all(2),
                        )
                    row_cells.append(cell)

                rows.append(ft.Row(row_cells, spacing=0, alignment=ft.MainAxisAlignment.CENTER))

            return rows

        # ── Split slots into JS and SS ─────────────────────────────────────
        js_slots = [s for s in slots if self._is_junior(s.get('class_level',''))]
        ss_slots = [s for s in slots if not self._is_junior(s.get('class_level',''))]

        all_rows = []
        if js_slots:
            all_rows += _build_section_grid(
                js_slots,
                '📚  JUNIOR SECONDARY',
                '#1565C0', '#1E40AF', '#2E75B6',
            )
        if ss_slots:
            all_rows += _build_section_grid(
                ss_slots,
                '🎓  SENIOR SECONDARY',
                '#01579B', '#0277BD', '#0288D1',
            )

        # scroll=AUTO: scrolls only when content exceeds screen width
        # (small screens), centres naturally on large screens.
        self.grid_container.controls.append(
            ft.Container(
                content=ft.Row(
                    [ft.Column(all_rows, spacing=4,
                               horizontal_alignment=ft.CrossAxisAlignment.CENTER)],
                    scroll=ft.ScrollMode.AUTO,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                margin=ft.margin.only(top=4),
            )
        )
        if not self._building:
            if not self._building:
                self.grid_container.update()

    def _draw_exam_by_class(self, slots, class_level=None):
        """
        Per-class-level exam view (all sections of a class combined):
          Rows = exam dates
          Columns = Slot 1 / Slot 2 / Slot 3
          Each cell = Subject | Invigilator | Room
        """
        self.grid_container.controls.clear()

        all_dates = sorted(set(s.get('exam_date','') for s in slots if s.get('exam_date')))
        if not all_dates:
            self._show_empty(); return

        COL_ORDER  = [1, 'break1', 2, 'break2', 3]

        # ── Dynamic widths — same formula as _draw_exam_all ───────────────
        _page_w = max(int(self.page.width or 1366), 900)
        _avail  = _page_w - 120
        DATE_W  = max(75,  int(_avail * 0.07))
        BREAK_W = max(70,  int(_avail * 0.05))
        SLOT_W  = max(160, int((_avail - DATE_W - 2 * BREAK_W) / 3))

        HDR_H      = 50
        ROW_H      = 110
        RADIUS     = 10
        DATE_BGS   = ['#EBF3FB', '#F5F5F5', '#EBF3FB', '#F5F5F5', '#EBF3FB',
                      '#EBF3FB', '#F5F5F5']

        rows = []

        # ── Class level banner ──────────────────────────────────────────
        display_level = class_level or (
            self._class_level(slots[0].get('class_name','')) if slots else 'Class'
        )
        is_js = self._is_junior(display_level)
        banner_color = '#1565C0' if is_js else '#01579B'
        section_label = 'JUNIOR SECONDARY' if is_js else 'SENIOR SECONDARY'
        rows.append(ft.Container(
            content=ft.Row([
                ft.Text(f'{display_level}', size=15, weight=ft.FontWeight.BOLD,
                        color=ft.colors.WHITE),
                ft.Container(width=10),
                ft.Text(f'— {section_label}', size=11, color='#90CAF9' if not is_js else '#90CAF9'),
            ], spacing=0),
            bgcolor=banner_color, border_radius=8,
            padding=ft.padding.symmetric(horizontal=14, vertical=8),
            margin=ft.margin.only(bottom=6),
        ))

        # ── Header ─────────────────────────────────────────────────────
        hdr_cells = [
            ft.Container(
                ft.Text('Date', weight=ft.FontWeight.BOLD, color=ft.colors.WHITE, size=14),
                width=DATE_W, height=HDR_H, bgcolor='#1565C0',
                border_radius=ft.border_radius.only(top_left=RADIUS, bottom_left=RADIUS),
                alignment=ft.alignment.center,
            )
        ]
        for i, col in enumerate(COL_ORDER):
            is_last = (i == len(COL_ORDER) - 1)
            if isinstance(col, str):
                slot_no = int(col[-1])
                b_s, b_e = EXAM_BREAK_AFTER[slot_no]
                def _short(t): return t.replace(' AM','').replace(' PM','')
                hdr_cells.append(ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.FREE_BREAKFAST, color='#D97706', size=18),
                        ft.Text('BREAK', weight=ft.FontWeight.BOLD, color='#92400E', size=11),
                        ft.Text(f'{_short(b_s)}–{_short(b_e)}', size=10, color='#92400E'),
                    ], alignment=ft.MainAxisAlignment.CENTER,
                       horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                    width=BREAK_W, height=HDR_H, bgcolor='#FEF3C7',
                    border_radius=ft.border_radius.only(
                        top_left=0, bottom_left=0,
                        top_right=RADIUS if is_last else 0,
                        bottom_right=RADIUS if is_last else 0),
                    alignment=ft.alignment.center,
                ))
            else:
                t_s, t_e = EXAM_SLOT_TIMES[col]
                hdr_cells.append(ft.Container(
                    content=ft.Column([
                        ft.Text(f'Slot {col}', weight=ft.FontWeight.BOLD,
                                color=ft.colors.WHITE, size=14),
                        ft.Text(f'{t_s} – {t_e}', color='#90CAF9', size=12),
                    ], alignment=ft.MainAxisAlignment.CENTER,
                       horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                    width=SLOT_W, height=HDR_H, bgcolor='#1976D2',
                    border_radius=ft.border_radius.only(
                        top_left=0, bottom_left=0,
                        top_right=RADIUS if is_last else 0,
                        bottom_right=RADIUS if is_last else 0),
                    alignment=ft.alignment.center,
                ))
        rows.append(ft.Row(hdr_cells, spacing=0, alignment=ft.MainAxisAlignment.CENTER))
        rows.append(ft.Container(height=3, bgcolor='#1565C0', border_radius=2,
                                 margin=ft.margin.only(bottom=4)))

        # Index slots: (date, slot_no) -> list of unique-subject entries
        slot_map: dict = {}
        for s in slots:
            key = (s.get('exam_date',''), s.get('exam_slot', 0))
            slot_map.setdefault(key, {})[s.get('subject_id','')] = s

        # ── Date rows ──────────────────────────────────────────────────
        for di, date_str in enumerate(all_dates):
            try:
                d = datetime.strptime(date_str, '%Y-%m-%d')
                date_label = d.strftime('%a\n%d %b %Y')
            except Exception:
                date_label = date_str

            day_bg = DATE_BGS[di % len(DATE_BGS)]
            row_cells = [
                ft.Container(
                    ft.Text(date_label, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE,
                            size=13, text_align=ft.TextAlign.CENTER),
                    width=DATE_W, height=ROW_H, bgcolor='#2E75B6',
                    alignment=ft.alignment.center,
                )
            ]
            for col in COL_ORDER:
                if isinstance(col, str):
                    row_cells.append(ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.icons.FREE_BREAKFAST, color='#D97706', size=18)],
                            alignment=ft.MainAxisAlignment.CENTER),
                        width=BREAK_W, height=ROW_H, bgcolor='#FFFBEB',
                        border=ft.border.all(1, '#FDE68A'),
                        alignment=ft.alignment.center,
                    ))
                    continue
                sn = col
                subj_map = slot_map.get((date_str, sn), {})
                if subj_map:
                    mini_tiles = []
                    for entry in subj_map.values():
                        code    = entry.get('subject_code','')
                        name    = entry.get('subject_name','')
                        invig   = entry.get('invigilator_name','') or '—'
                        inv_code = entry.get('invigilator_code','')
                        is_core = bool(entry.get('is_core', 0))
                        bg, bc, tc = self._palette(code)
                        children = [
                            ft.Row([
                                ft.Text(code, weight=ft.FontWeight.BOLD, color=tc, size=15),
                                ft.Container(
                                    ft.Text('CORE', size=9, color='#FFF'),
                                    bgcolor='#1E40AF', border_radius=3,
                                    padding=ft.padding.symmetric(horizontal=4, vertical=2),
                                    visible=is_core,
                                ),
                            ], spacing=4, alignment=ft.MainAxisAlignment.CENTER),
                            ft.Text(name, size=11, color=tc, opacity=0.8,
                                    text_align=ft.TextAlign.CENTER,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Container(height=1, bgcolor=bc, opacity=0.2,
                                         margin=ft.margin.symmetric(vertical=2)),
                            ft.Row([
                                ft.Icon(ft.icons.PERSON_OUTLINE, size=12, color=tc),
                                ft.Text(f'{invig} ({inv_code})', size=11, color=tc,
                                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ], spacing=2),
                        ]
                        mini_tiles.append(ft.Container(
                            content=ft.Column(children, alignment=ft.MainAxisAlignment.CENTER,
                                              horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                              spacing=3),
                            bgcolor=bg, border=ft.border.all(1.5, bc), border_radius=RADIUS,
                            padding=ft.padding.symmetric(horizontal=10, vertical=8),
                            margin=ft.margin.only(bottom=4),
                            shadow=ft.BoxShadow(spread_radius=0, blur_radius=6,
                                                color=ft.colors.with_opacity(0.10, ft.colors.BLACK),
                                                offset=ft.Offset(0, 2)),
                        ))
                    cell = ft.Container(
                        content=ft.Column(mini_tiles, spacing=0,
                                          scroll=ft.ScrollMode.AUTO),
                        width=SLOT_W, height=ROW_H, bgcolor=day_bg,
                        border=ft.border.all(1, '#E2E8F0'), border_radius=RADIUS,
                        padding=ft.padding.all(8), margin=ft.margin.all(2),
                        clip_behavior=ft.ClipBehavior.HARD_EDGE,
                    )
                else:
                    cell = ft.Container(
                        ft.Text('—', color='#CBD5E1', size=18),
                        width=SLOT_W, height=ROW_H, bgcolor=day_bg,
                        border=ft.border.all(1, '#E2E8F0'), border_radius=RADIUS,
                        alignment=ft.alignment.center, margin=ft.margin.all(2),
                    )
                row_cells.append(cell)

            rows.append(ft.Row(row_cells, spacing=0, alignment=ft.MainAxisAlignment.CENTER))

        self.grid_container.controls.append(
            ft.Container(
                content=ft.Row(
                    [ft.Column(rows, spacing=4,
                               horizontal_alignment=ft.CrossAxisAlignment.CENTER)],
                    scroll=ft.ScrollMode.AUTO,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                margin=ft.margin.only(top=4),
            )
        )
        if not self._building:
            if not self._building:
                self.grid_container.update()

    # ══════════════════════════════════════════════════════════════════════
    # Empty / Error states
    # ══════════════════════════════════════════════════════════════════════

    def _show_empty(self):
        self.grid_container.controls.clear()
        self.grid_container.controls.append(ft.Container(
            content=ft.Column([
                ft.Icon(ft.icons.CALENDAR_TODAY, size=52, color='#CBD5E1'),
                ft.Text('Nothing to display.', size=16, color='#94A3B8'),
                ft.Text('Select a class or teacher above.', size=12, color='#CBD5E1'),
            ], alignment=ft.MainAxisAlignment.CENTER,
               horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
            alignment=ft.alignment.center, height=260,
        ))
        if not self._building:
            if not self._building:
                self.grid_container.update()

    def _show_no_timetable(self):
        self.grid_container.controls.clear()
        self.grid_container.controls.append(ft.Container(
            content=ft.Column([
                ft.Icon(ft.icons.WARNING_AMBER_ROUNDED, size=52, color='#F59E0B'),
                ft.Text('No class timetable has been generated yet.',
                        size=16, color='#92400E', weight=ft.FontWeight.BOLD),
                ft.Text('Go to Timetable Management to generate one.',
                        size=12, color='#92400E'),
                ft.ElevatedButton('Go to Generator', icon=ft.icons.SETTINGS_SUGGEST,
                                  on_click=lambda e: self.page.go('/timetable'),
                                  style=ft.ButtonStyle(bgcolor=ft.colors.ORANGE,
                                                       color=ft.colors.WHITE)),
            ], alignment=ft.MainAxisAlignment.CENTER,
               horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=14),
            alignment=ft.alignment.center, height=280,
        ))
        if not self._building:
            if not self._building:
                self.grid_container.update()

    def _show_no_exam_timetable(self):
        self.grid_container.controls.clear()
        self.grid_container.controls.append(ft.Container(
            content=ft.Column([
                ft.Icon(ft.icons.ASSIGNMENT_LATE_OUTLINED, size=52, color='#1976D2'),
                ft.Text('No exam timetable has been generated yet.',
                        size=16, color='#1565C0', weight=ft.FontWeight.BOLD),
                ft.Text('Go to Timetable Management → select "Exam Timetable" and generate one.',
                        size=12, color='#1976D2', text_align=ft.TextAlign.CENTER),
                ft.ElevatedButton('Go to Generator', icon=ft.icons.SETTINGS_SUGGEST,
                                  on_click=lambda e: self.page.go('/timetable'),
                                  style=ft.ButtonStyle(bgcolor='#1565C0',
                                                       color=ft.colors.WHITE)),
            ], alignment=ft.MainAxisAlignment.CENTER,
               horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=14),
            alignment=ft.alignment.center, height=280,
        ))
        if not self._building:
            if not self._building:
                self.grid_container.update()

    # ══════════════════════════════════════════════════════════════════════
    # Export helpers
    # ══════════════════════════════════════════════════════════════════════

    def _snack(self, msg, color=None):
        self.page.show_snack_bar(ft.SnackBar(content=ft.Text(msg),
                                              bgcolor=color or ft.colors.GREEN))

    def _write_excel(self, slots, entity_col_label, entity_col_key,
                     view_type, filename):
        import os
        from datetime import datetime as dt2, timedelta as td2
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        if not slots:
            self._snack('No data to export.', ft.colors.RED); return

        DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        used_periods = sorted(set(int(s['period_number']) for s in slots))
        BREAK_P = self._get_break_periods()
        max_p = max(used_periods)
        full_periods = set(range(1, max_p + 1))
        if BREAK_P:
            full_periods |= BREAK_P
        used_periods = sorted(full_periods)

        def pt(p):
            s = dt2(2000, 1, 1, 8, 0) + td2(minutes=(p - 1) * 40)
            e2 = s + td2(minutes=40)
            return (s.strftime('%I:%M %p').lstrip('0'), e2.strftime('%I:%M %p').lstrip('0'))

        entities = []
        entity_slots = {}
        for s in slots:
            ent = s.get(entity_col_key, 'Unknown')
            if ent not in entity_slots:
                entity_slots[ent] = []
                entities.append(ent)
            entity_slots[ent].append(s)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = entity_col_label
        ws.sheet_view.showGridLines = True

        thin = Side(style='thin', color='AAAAAA')

        def _b(): return Border(left=thin, right=thin, top=thin, bottom=thin)

        def _c(row, col, value='', bg=None, bold=False, size=10,
               wrap=False, align='center', color='000000'):
            c = ws.cell(row=row, column=col, value=value)
            c.font = Font(name='Calibri', size=size, bold=bold, color=color)
            c.alignment = Alignment(horizontal=align, vertical='center', wrap_text=wrap)
            if bg: c.fill = PatternFill('solid', fgColor=bg)
            c.border = _b()
            return c

        DAY_BGS = ['EBF3FB', 'F5F5F5', 'EBF3FB', 'F5F5F5', 'EBF3FB']

        # ── Term/year banner row ──────────────────────────────────────────
        term_label = self._get_term_label('Class Timetable')
        total_cols = len(used_periods) + 1
        if term_label:
            ws.merge_cells(start_row=1, start_column=1,
                           end_row=1, end_column=total_cols)
            banner = ws.cell(row=1, column=1, value=term_label)
            banner.font = Font(name='Calibri', size=13, bold=True, color='FFFFFF')
            banner.fill = PatternFill('solid', fgColor='1F3864')
            banner.alignment = Alignment(horizontal='center', vertical='center')
            ws.row_dimensions[1].height = 24
            cur_row = 2
        else:
            cur_row = 1

        for ent in entities:
            ent_slots = entity_slots[ent]
            slot_map = {(s['day_of_week'], int(s['period_number'])): s for s in ent_slots}
            _c(cur_row, 1, ent, bg='1F3864', bold=True, size=11, align='left', color='FFFFFF')
            for pi, p in enumerate(used_periods):
                if p in BREAK_P:
                    t_s, t_e = pt(p)
                    _c(cur_row, pi + 2, 'BREAK\n' + t_s + ' - ' + t_e,
                       bg='FEF3C7', bold=True, size=9, wrap=True, color='92400E')
                else:
                    t_s, t_e = pt(p)
                    _c(cur_row, pi + 2, t_s + '\n' + t_e, bg='BDD7EE', bold=True, size=9, wrap=True)
            ws.row_dimensions[cur_row].height = 36
            cur_row += 1

            for di, day in enumerate(DAYS):
                _c(cur_row, 1, day, bg='2E75B6', bold=True, size=10, color='FFFFFF')
                for pi, p in enumerate(used_periods):
                    if p in BREAK_P:
                        _c(cur_row, pi + 2, '', bg='FFFBEB', size=9)
                        continue
                    s = slot_map.get((day, p))
                    if s:
                        if view_type == 'class':
                            l1 = s.get('subject_code', '')
                            l2 = s.get('teacher_name', '')
                            l3 = s.get('room_code', '') or ''
                        elif view_type == 'teacher':
                            l1 = s.get('subject_code', '')
                            l2 = s.get('class_name', '')
                            l3 = s.get('room_code', '') or ''
                        else:
                            l1 = s.get('subject_code', '')
                            l2 = s.get('class_name', '')
                            l3 = s.get('teacher_name', '') or ''
                        lines = [l1, l2]
                        if l3: lines.append(l3)
                        _c(cur_row, pi + 2, '\n'.join(lines), bg=DAY_BGS[di], size=9, wrap=True)
                    else:
                        _c(cur_row, pi + 2, '', bg=DAY_BGS[di], size=9)
                ws.row_dimensions[cur_row].height = 46
                cur_row += 1

            for col in range(1, len(used_periods) + 2):
                ws.cell(row=cur_row, column=col).border = Border()
            ws.row_dimensions[cur_row].height = 10
            cur_row += 1

        ws.column_dimensions['A'].width = 14
        for pi in range(len(used_periods)):
            ws.column_dimensions[get_column_letter(pi + 2)].width = 22

        desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
        path = os.path.join(desktop, filename)
        if os.path.exists(path):
            self._snack(f'Already exported: {filename} — delete it from Desktop first to re-export.', ft.colors.RED)
            return
        wb.save(path)
        self._snack(f'Saved to Desktop/{filename}')

    def _no_timetable_check(self):
        if not self.current_timetable_id:
            self._snack('No timetable loaded.', ft.colors.RED)
            return True
        return False

    def export_all(self, e=None):
        try:
            tid = self._get_timetable_id('Class Timetable')
            if not tid:
                self._snack('No class timetable found.', ft.colors.ORANGE); return
            slots = self.app.local_db.execute("""
                SELECT c.class_name, ts.day_of_week, ts.period_number,
                       s.code as subject_code, s.name as subject_name,
                       t.full_name as teacher_name, r.room_code
                FROM timetable_slots ts
                JOIN subjects s  ON s.id = ts.subject_id
                JOIN teachers t  ON t.id = ts.teacher_id
                JOIN classes  c  ON c.id = ts.class_id
                LEFT JOIN rooms r ON r.id = ts.room_id
                WHERE ts.timetable_id = ? AND ts.period_number IS NOT NULL
                ORDER BY c.class_name, ts.day_of_week, ts.period_number
            """, (tid,)) or []
            self._write_excel(slots, 'Class', 'class_name', 'class', self._timetable_filename('Class Timetable', 'all_classes'))
        except Exception as ex:
            traceback.print_exc()
            self._snack(f'Export error: {ex}', ft.colors.RED)

    def export_class(self, e=None):
        if self._no_timetable_check(): return
        if not self.class_dropdown.value:
            self._snack('Please select a class first.', ft.colors.ORANGE); return
        try:
            slots = self.app.local_db.execute("""
                SELECT ts.day_of_week, ts.period_number,
                       s.code as subject_code, s.name as subject_name,
                       t.full_name as teacher_name, r.room_code, c.class_name
                FROM timetable_slots ts
                JOIN subjects s  ON ts.subject_id = s.id
                JOIN teachers t  ON ts.teacher_id = t.id
                JOIN classes  c  ON ts.class_id   = c.id
                LEFT JOIN rooms r ON ts.room_id   = r.id
                WHERE ts.timetable_id = ? AND ts.class_id = ?
                ORDER BY ts.day_of_week, ts.period_number
            """, (self.current_timetable_id, self.class_dropdown.value)) or []
            cls_name = slots[0]['class_name'] if slots else 'class'
            self._write_excel(slots, 'Class', 'class_name', 'class',
                              self._timetable_filename('Class Timetable', cls_name.replace(' ','_')))
        except Exception as ex:
            traceback.print_exc()
            self._snack(f'Export error: {ex}', ft.colors.RED)

    def export_teacher(self, e=None):
        if self._no_timetable_check(): return
        if not self.teacher_dropdown.value:
            self._snack('Please select a teacher first.', ft.colors.ORANGE); return
        try:
            slots = self.app.local_db.execute("""
                SELECT ts.day_of_week, ts.period_number,
                       s.code as subject_code, s.name as subject_name,
                       c.class_name, r.room_code, t.full_name as teacher_name
                FROM timetable_slots ts
                JOIN subjects s  ON ts.subject_id = s.id
                JOIN classes  c  ON ts.class_id   = c.id
                JOIN teachers t  ON ts.teacher_id = t.id
                LEFT JOIN rooms r ON ts.room_id   = r.id
                WHERE ts.timetable_id = ? AND ts.teacher_id = ?
                ORDER BY ts.day_of_week, ts.period_number
            """, (self.current_timetable_id, self.teacher_dropdown.value)) or []
            teacher_name = slots[0]['teacher_name'] if slots else 'teacher'
            self._write_excel(slots, 'Teacher', 'teacher_name', 'teacher',
                              self._timetable_filename('Class Timetable', teacher_name.replace(' ','_')))
        except Exception as ex:
            traceback.print_exc()
            self._snack(f'Export error: {ex}', ft.colors.RED)

    def export_room(self, e=None):
        if self._no_timetable_check(): return
        if not self.room_dropdown.value:
            self._snack('Please select a room first.', ft.colors.ORANGE); return
        try:
            slots = self.app.local_db.execute("""
                SELECT ts.day_of_week, ts.period_number,
                       s.code as subject_code, s.name as subject_name,
                       c.class_name, t.full_name as teacher_name, r.room_code
                FROM timetable_slots ts
                JOIN subjects s  ON ts.subject_id = s.id
                JOIN classes  c  ON ts.class_id   = c.id
                JOIN teachers t  ON ts.teacher_id = t.id
                JOIN rooms    r  ON ts.room_id    = r.id
                WHERE ts.timetable_id = ? AND ts.room_id = ?
                ORDER BY ts.day_of_week, ts.period_number
            """, (self.current_timetable_id, self.room_dropdown.value)) or []
            room_code = slots[0]['room_code'] if slots else 'room'
            self._write_excel(slots, 'Room', 'room_code', 'room',
                              self._timetable_filename('Class Timetable', room_code.replace(' ','').replace('-','')))
        except Exception as ex:
            traceback.print_exc()
            self._snack(f'Export error: {ex}', ft.colors.RED)


    # ══════════════════════════════════════════════════════════════════════
    # EXAM export methods
    # ══════════════════════════════════════════════════════════════════════

    def _write_exam_excel(self, slots, filename, single_class=False, class_level=None):
        """Write exam timetable slots to an Excel file.
        - All-classes export: two sections (JUNIOR SECONDARY / SENIOR SECONDARY),
          each showing class levels (JS1, JS2…) not individual sections.
        - Single-class-level export: one sheet for the given level.
        """
        import os
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        if not slots:
            self._snack('No exam data to export.', ft.colors.ORANGE); return

        COL_ORDER = [1, 'break1', 2, 'break2', 3]
        SLOT_LABELS = {
            1: 'Slot 1\n8:30 AM – 10:30 AM',
            2: 'Slot 2\n11:00 AM – 1:00 PM',
            3: 'Slot 3\n1:30 PM – 3:30 PM',
        }
        BREAK_LABELS = {
            'break1': 'BREAK\n10:30 – 11:00',
            'break2': 'BREAK\n1:00 – 1:30',
        }

        all_dates = sorted(set(s.get('exam_date','') for s in slots if s.get('exam_date')))

        thin = Side(style='thin', color='CCCCCC')
        def _b(): return Border(left=thin, right=thin, top=thin, bottom=thin)
        def _c(ws, row, col, value='', bg=None, bold=False, size=10,
               wrap=False, align='center', color='000000', italic=False):
            c = ws.cell(row=row, column=col, value=value)
            c.font = Font(name='Calibri', size=size, bold=bold, color=color, italic=italic)
            c.alignment = Alignment(horizontal=align, vertical='center', wrap_text=wrap)
            if bg: c.fill = PatternFill('solid', fgColor=bg)
            c.border = _b()
            return c

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Exam Timetable'
        ws.sheet_view.showGridLines = True
        DATE_BGS = ['EBF3FB', 'F5F5F5', 'EBF3FB', 'F5F5F5', 'EBF3FB',
                    'EBF3FB', 'F5F5F5']

        total_cols = len(COL_ORDER) + 1  # Date col + 5 slot/break cols

        def _merge_header(ws, cur_row, label, bg, text_color='FFFFFF', size=13):
            _c(ws, cur_row, 1, label, bg=bg, bold=True, size=size, color=text_color)
            for ci in range(2, total_cols + 1):
                _c(ws, cur_row, ci, '', bg=bg)
            ws.merge_cells(
                start_row=cur_row, start_column=1,
                end_row=cur_row, end_column=total_cols)
            ws.row_dimensions[cur_row].height = 28
            return cur_row + 1

        def _write_column_header(ws, cur_row):
            _c(ws, cur_row, 1, 'Date', bg='1565C0', bold=True, size=11,
               align='center', color='FFFFFF')
            for ci, col in enumerate(COL_ORDER):
                col_idx = ci + 2
                if isinstance(col, str):
                    _c(ws, cur_row, col_idx, BREAK_LABELS[col],
                       bg='FEF3C7', bold=True, size=9, wrap=True, color='92400E')
                else:
                    _c(ws, cur_row, col_idx, SLOT_LABELS[col],
                       bg='1976D2', bold=True, size=10, wrap=True, color='FFFFFF')
            ws.row_dimensions[cur_row].height = 38
            return cur_row + 1

        def _write_data_rows(ws, cur_row, section_slots, show_class_level=True):
            """Write date-data rows for a set of slots."""
            # Build slot_map: (date, slot_no) → { subject_id → slot_dict }
            slot_map: dict = {}
            for s in section_slots:
                key = (s.get('exam_date',''), s.get('exam_slot', 0))
                slot_map.setdefault(key, {})[s.get('subject_id', s.get('subject_code',''))] = s

            for di, date_str in enumerate(all_dates):
                # Only output rows that have data for this section
                has_data = any(slot_map.get((date_str, sn)) for sn in [1,2,3])
                if not has_data:
                    continue

                try:
                    from datetime import datetime as _dt
                    dl = _dt.strptime(date_str, '%Y-%m-%d').strftime('%a %d %b %Y')
                except Exception:
                    dl = date_str
                day_bg = DATE_BGS[di % len(DATE_BGS)]

                _c(ws, cur_row, 1, dl, bg='2E75B6', bold=True, size=10,
                   align='center', color='FFFFFF', wrap=True)

                max_entries = 1
                for ci, col in enumerate(COL_ORDER):
                    col_idx = ci + 2
                    if isinstance(col, str):
                        _c(ws, cur_row, col_idx, '', bg='FFFBEB', size=9)
                        continue
                    subj_map = slot_map.get((date_str, col), {})
                    if subj_map:
                        lines_out = []
                        for ent in subj_map.values():
                            code  = ent.get('subject_code','')
                            name  = ent.get('subject_name','')
                            invig = ent.get('invigilator_name','')
                            line = f'{code} - {name}'
                            if show_class_level:
                                lvl = self._class_level(ent.get('class_name',''))
                                if lvl: line += f'\n  Class: {lvl}'
                            if invig: line += f'\n  Invigilator: {invig}'
                            lines_out.append(line)
                        max_entries = max(max_entries, len(lines_out))
                        _c(ws, cur_row, col_idx, '\n\n'.join(lines_out),
                           bg=day_bg, size=9, wrap=True, align='left')
                    else:
                        _c(ws, cur_row, col_idx, '', bg=day_bg, size=9)

                ws.row_dimensions[cur_row].height = max(46, 22 * max_entries)
                cur_row += 1
            return cur_row

        cur_row = 1

        # ── Term/year banner ─────────────────────────────────────────────
        term_label_exam = self._get_term_label('Exam Timetable')
        if term_label_exam:
            cur_row = _merge_header(ws, cur_row, term_label_exam, '0D3B6E', size=12)

        if single_class:
            # ── Per-class-level export ────────────────────────────────────
            lvl = class_level or self._class_level(
                next((s.get('class_name','') for s in slots if s.get('class_name')), ''))
            is_js = self._is_junior(lvl)
            section_label = 'JUNIOR SECONDARY' if is_js else 'SENIOR SECONDARY'
            title_bg = '1565C0' if is_js else '1565C0'

            cur_row = _merge_header(ws, cur_row,
                                    f'{lvl}  —  {section_label}',
                                    title_bg, size=13)
            cur_row = _write_column_header(ws, cur_row)
            cur_row = _write_data_rows(ws, cur_row, slots, show_class_level=False)

        else:
            # ── All-classes export: two sections ──────────────────────────
            # Attach class_level to every slot
            for s in slots:
                s['class_level'] = self._class_level(s.get('class_name', ''))

            js_slots = [s for s in slots if self._is_junior(s.get('class_level',''))]
            ss_slots = [s for s in slots if not self._is_junior(s.get('class_level',''))]

            if js_slots:
                cur_row = _merge_header(ws, cur_row,
                                        'JUNIOR SECONDARY', '1565C0', size=13)
                cur_row = _write_column_header(ws, cur_row)
                cur_row = _write_data_rows(ws, cur_row, js_slots, show_class_level=True)
                cur_row += 1  # blank separator row

            if ss_slots:
                cur_row = _merge_header(ws, cur_row,
                                        'SENIOR SECONDARY', '01579B', size=13)
                cur_row = _write_column_header(ws, cur_row)
                cur_row = _write_data_rows(ws, cur_row, ss_slots, show_class_level=True)

        # ── Column widths ──────────────────────────────────────────────────
        ws.column_dimensions['A'].width = 16
        col_widths = {1: 32, 'break1': 14, 2: 32, 'break2': 14, 3: 32}
        for ci, col in enumerate(COL_ORDER):
            ws.column_dimensions[get_column_letter(ci + 2)].width = col_widths[col]

        desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
        path = os.path.join(desktop, filename)
        if os.path.exists(path):
            self._snack(f'Already exported: {filename} — delete it from Desktop first to re-export.', ft.colors.RED)
            return
        wb.save(path)
        self._snack(f'Saved to Desktop/{filename}')

    def export_exam_all(self, e=None):
        """Export the full master exam timetable."""
        if self._no_timetable_check(): return
        try:
            tid = self._get_timetable_id('Exam Timetable')
            if not tid:
                self._snack('No exam timetable found.', ft.colors.ORANGE); return
            base_slots = self.app.local_db.execute("""
                SELECT ts.id, ts.class_id, ts.subject_id, ts.room_id,
                       s.code as subject_code, s.name as subject_name,
                       c.class_name, r.room_code
                FROM timetable_slots ts
                JOIN subjects s  ON ts.subject_id = s.id
                JOIN classes  c  ON ts.class_id   = c.id
                LEFT JOIN rooms r ON ts.room_id   = r.id
                WHERE ts.timetable_id = ?
            """, (tid,)) or []
            slots = self._enrich_exam_slots(base_slots)
            slots = [s for s in slots if s.get('exam_date')]
            self._write_exam_excel(slots, self._timetable_filename('Exam Timetable', 'all_classes'))
        except Exception as ex:
            traceback.print_exc()
            self._snack(f'Export error: {ex}', ft.colors.RED)

    def export_exam_class(self, e=None):
        """Export exam timetable for the selected class level (all sections combined)."""
        if self._no_timetable_check(): return
        if not self.exam_class_dropdown.value:
            self._snack('Please select a class first.', ft.colors.ORANGE); return
        try:
            tid = self._get_timetable_id('Exam Timetable')
            if not tid:
                self._snack('No exam timetable found.', ft.colors.ORANGE); return
            level = self.exam_class_dropdown.value  # e.g. 'JS1', 'SS2'
            slots = None
            try:
                slots = self.app.local_db.execute("""
                    SELECT ts.id, ts.class_id, ts.subject_id, ts.room_id,
                           ts.exam_date, ts.exam_slot, ts.invigilator_id,
                           s.code as subject_code, s.name as subject_name,
                           c.class_name, r.room_code,
                           inv.full_name as invigilator_name,
                           inv.teacher_code as invigilator_code
                    FROM timetable_slots ts
                    JOIN subjects  s   ON ts.subject_id      = s.id
                    JOIN classes   c   ON ts.class_id         = c.id
                    LEFT JOIN rooms r   ON ts.room_id          = r.id
                    LEFT JOIN teachers inv ON ts.invigilator_id = inv.id
                    WHERE ts.timetable_id = ? AND c.class_name LIKE ?
                    ORDER BY ts.exam_date, ts.exam_slot
                """, (tid, level + '%')) or []
            except Exception:
                pass
            if not slots:
                base = self.app.local_db.execute("""
                    SELECT ts.id, ts.class_id, ts.subject_id, ts.room_id,
                           s.code as subject_code, s.name as subject_name,
                           c.class_name, r.room_code
                    FROM timetable_slots ts
                    JOIN subjects s  ON ts.subject_id = s.id
                    JOIN classes  c  ON ts.class_id   = c.id
                    LEFT JOIN rooms r ON ts.room_id   = r.id
                    WHERE ts.timetable_id = ? AND c.class_name LIKE ?
                """, (tid, level + '%')) or []
                slots = self._enrich_exam_slots(base)
            slots = [dict(s) for s in slots]
            for s in slots:
                s['exam_slot'] = int(s.get('exam_slot') or 0)
            slots = sorted([s for s in slots if s.get('exam_date')],
                           key=lambda x: (x['exam_date'], x['exam_slot']))
            if not slots:
                self._snack('No exam data for this class.', ft.colors.ORANGE); return
            safe = level.replace(' ','_')
            self._write_exam_excel(slots, self._timetable_filename('Exam Timetable', safe),
                                   single_class=True, class_level=level)
        except Exception as ex:
            traceback.print_exc()
            self._snack(f'Export error: {ex}', ft.colors.RED)

    def export_excel(self, e=None):
        self.export_all(e)

    # ══════════════════════════════════════════════════════════════════════
    # Build
    # ══════════════════════════════════════════════════════════════════════

    def _make_selector_container(self):
        self.selector_container = ft.Container(
            content=self.selector_row,
            bgcolor=ft.colors.WHITE, border_radius=10,
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            margin=ft.margin.only(bottom=8),
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=8,
                                color=ft.colors.with_opacity(0.08, ft.colors.BLACK),
                                offset=ft.Offset(0, 2)),
            visible=False,
        )
        return self.selector_container

    def _detect_latest_type(self) -> str:
        """Return pending type set by generator, then clear it. Falls back to 'class'."""
        pending = getattr(self.app, 'pending_view_type', None)
        if pending in ('class', 'exam'):
            self.app.pending_view_type = None
            return pending
        return 'class'


    def build(self):
        self._load_dropdowns()

        # Auto-detect which timetable type was most recently generated
        self.timetable_type = self._detect_latest_type()

        # Initial type selector (highlights the correct card)
        type_selector = self._build_type_selector()
        # Wrap in a ref Container so _select_type can swap its .content
        self.type_selector_ref = ft.Container(content=type_selector)

        # Tabs wrapper — pick the right tab set based on detected type
        initial_tabs = self.exam_tabs if self.timetable_type == 'exam' else self.class_tabs
        self.tabs_container = ft.Container(
            content=initial_tabs,
            bgcolor=ft.colors.WHITE, border_radius=10,
            padding=ft.padding.symmetric(horizontal=10, vertical=5),
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=8,
                                color=ft.colors.with_opacity(0.08, ft.colors.BLACK),
                                offset=ft.Offset(0, 2)),
            margin=ft.margin.only(bottom=8),
        )

        # ── IMPORTANT: build selector_container BEFORE triggering any tab
        # handler, because the handlers reference self.selector_container.
        selector_container_widget = self._make_selector_container()

        # Trigger initial load — suppress page.update() until view is mounted
        self._building = True
        if self.timetable_type == 'exam':
            self._on_exam_tab_change(None)
        else:
            self._on_class_tab_change(None)
        self._building = False

        return ft.View(
            '/view_timetable',
            [
                # ── Navy top bar ───────────────────────────────────────
                ft.Container(
                    content=ft.Row([
                        ft.IconButton(
                            icon=ft.icons.ARROW_BACK_ROUNDED,
                            icon_color=ft.colors.WHITE, icon_size=20,
                            tooltip="Back to Dashboard",
                            on_click=lambda e: self.page.go('/dashboard'),
                        ),
                        ft.Container(width=4),
                        ft.Icon(ft.icons.VISIBILITY_ROUNDED,
                                color=ft.colors.WHITE, size=20),
                        ft.Text("View Timetable", size=17,
                                weight=ft.FontWeight.BOLD,
                                color=ft.colors.WHITE),
                        ft.Container(expand=True),
                        ft.PopupMenuButton(
                            content=ft.Icon(ft.icons.DOWNLOAD_ROUNDED,
                                            color=ft.colors.WHITE, size=22),
                            tooltip='Export to Excel',
                            items=[
                                ft.PopupMenuItem(
                                    text='Export Class Timetable',
                                    icon=ft.icons.CALENDAR_VIEW_WEEK,
                                    on_click=self.export_all,
                                ),
                                ft.PopupMenuItem(
                                    text='Export Exam Timetable',
                                    icon=ft.icons.ASSIGNMENT_OUTLINED,
                                    on_click=self.export_exam_all,
                                ),
                            ],
                        ),
                    ], spacing=6,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor="#0F1E3A",
                    padding=ft.padding.symmetric(horizontal=16, vertical=10),
                    height=56,
                ),
                ft.Container(
                    content=ft.Column([
                        # ① Type selector (Class vs Exam)
                        self.type_selector_ref,
                        # ② Tabs
                        self.tabs_container,
                        # ③ Dropdown selector row
                        selector_container_widget,
                        # ④ Grid
                        ft.Container(
                            content=self.grid_container,
                            bgcolor=ft.colors.WHITE, border_radius=16,
                            padding=ft.padding.symmetric(horizontal=20, vertical=20),
                            shadow=ft.BoxShadow(
                                spread_radius=0, blur_radius=20,
                                color=ft.colors.with_opacity(0.09, ft.colors.BLACK),
                                offset=ft.Offset(0, 4)),
                        ),
                    ], spacing=0),
                    padding=20, bgcolor="#F8FAFC",
                ),
            ],
            padding=0, spacing=0, scroll=ft.ScrollMode.ALWAYS,
        )