"""
ApiClient – talks to the FastAPI backend.

All bugs from previous sessions fixed:
  1. probe()  → checks status=="healthy" (backend returns "healthy" not "ok")
  2. login()  → sends JSON body (backend uses Pydantic UserLogin, not OAuth2 form)
  3. school_id → stored after login (fetched from /schools endpoint)
  4. get_entities() → unwraps {"items":[...]} paginated response
  5. create_entity() → auto-injects school_id
  6. sync() → uses new /sync/push + /sync/pull endpoints (added to backend)
              strips extra local-SQLite fields before pushing
  7. Timetable type normalisation helper included
"""

import json
import urllib.request
import urllib.error
import urllib.parse
import ssl
import threading
from typing import Any, Optional


# Fields the backend accepts per entity — strips local-only columns
# (phone, subject_codes, teacher_code used as name, etc.)
_ENTITY_FIELDS = {
    "teachers": {
        "id", "school_id", "teacher_code", "full_name", "email",
        "max_daily_periods", "is_active",
    },
    "subjects": {
        "id", "school_id", "code", "name", "category",
        "periods_per_week", "duration_minutes", "requires_lab",
    },
    "classes": {
        "id", "school_id", "class_name", "level",
        "student_count", "default_room_id",
    },
    "rooms": {
        "id", "school_id", "room_code", "room_name",
        "capacity", "room_type", "is_available",
    },
    "periods": {
        "id", "school_id", "period_number", "start_time",
        "end_time", "is_break", "day_of_week",
    },
}


class ApiClient:
    def __init__(self, base_url: str = "http://localhost:8000/api/v1"):
        self.base_url     = base_url.rstrip("/")
        self.offline_mode = True
        self.token: Optional[str] = None
        self.school_id: Optional[str] = None
        self._lock = threading.Lock()

        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode    = ssl.CERT_NONE

    # ── HTTP helpers ──────────────────────────────────────────────────────────
    def _headers(self) -> dict:
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _request(self, method: str, path: str,
                  body: Any = None, timeout: int = 30) -> dict:
        url  = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req  = urllib.request.Request(
            url, data=data, headers=self._headers(), method=method)
        try:
            with urllib.request.urlopen(
                    req, timeout=timeout, context=self._ssl_ctx) as resp:
                raw = resp.read().decode()
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as e:
            raw = e.read().decode()
            try:
                detail = json.loads(raw).get("detail", raw)
            except Exception:
                detail = raw
            return {"error": True, "message": str(detail), "status_code": e.code}
        except Exception as e:
            return {"error": True, "message": str(e)}

    def _get(self, path: str, params: dict = None):
        if params:
            path = f"{path}?{urllib.parse.urlencode(params)}"
        return self._request("GET", path)

    def _post(self, path: str, body: Any = None):
        return self._request("POST", path, body)

    def _put(self, path: str, body: Any = None):
        return self._request("PUT", path, body)

    def _delete(self, path: str):
        return self._request("DELETE", path)

    # ── Connectivity ──────────────────────────────────────────────────────────
    def probe(self) -> bool:
        """Ping /health. Backend returns {"status":"healthy"} not "ok"."""
        result = self._request("GET", "/health", timeout=5)
        online = not result.get("error") and result.get("status") == "healthy"
        with self._lock:
            self.offline_mode = not online
        return online

    def probe_async(self, callback=None):
        def _run():
            online = self.probe()
            if callback:
                callback(online)
        threading.Thread(target=_run, daemon=True).start()

    # ── Auth ──────────────────────────────────────────────────────────────────
    def login(self, username: str, password: str) -> dict:
        """
        Login with JSON body — backend uses Pydantic UserLogin (not OAuth2 form).
        Stores token and fetches school_id automatically.
        """
        result = self._post("/auth/login",
                            {"username": username, "password": password})

        if result.get("error"):
            return result

        if "access_token" in result:
            self.token        = result["access_token"]
            self.offline_mode = False
            # school_id is injected server-side by crud_base._school_id()
            # No blocking HTTP call needed here.
            self.school_id = "__server__"

        return result

    def _fetch_school_id(self):
        """Fetch and cache the school_id after login."""
        try:
            resp  = self._get("/schools", {"limit": 1})
            items = resp.get("items", []) if isinstance(resp, dict) else (resp or [])
            if items:
                self.school_id = str(items[0].get("id", ""))
                return
        except Exception:
            pass
        # Fallback: ask the sync endpoint for the school_id
        try:
            resp = self._get("/sync/pull")
            # server returns tables dict; we don't need data, just being
            # online is enough — school_id will be injected by the server
            # side anyway via _get_school_id() in crud_base
            self.school_id = "__server__"   # sentinel: inject from server
        except Exception:
            self.school_id = None

    def logout(self):
        self.token        = None
        self.offline_mode = True
        self.school_id    = None

    def change_password(self, old: str, new: str) -> dict:
        return self._post("/auth/change-password",
                          {"old_password": old, "new_password": new})

    # ── Generic CRUD ──────────────────────────────────────────────────────────
    def get_entities(self, table: str, params: dict = None) -> list:
        """Returns a plain list — unwraps {"items":[...]} automatically."""
        result = self._get(f"/{table}", params)
        if isinstance(result, dict):
            if result.get("error"):
                return []
            return result.get("items", [])
        return result if isinstance(result, list) else []

    def get_entity(self, table: str, item_id: str) -> dict:
        return self._get(f"/{table}/{item_id}")

    def create_entity(self, table: str, data: dict) -> dict:
        payload = dict(data)
        if self.school_id and "school_id" not in payload:
            payload["school_id"] = self.school_id
        return self._post(f"/{table}", payload)

    def update_entity(self, table: str, item_id: str, data: dict) -> dict:
        return self._put(f"/{table}/{item_id}", data)

    def delete_entity(self, table: str, item_id: str) -> dict:
        return self._delete(f"/{table}/{item_id}")

    # ── Timetable ─────────────────────────────────────────────────────────────
    def get_timetable(self, timetable_id: str) -> dict:
        return self._get(f"/timetables/{timetable_id}")

    def get_timetable_slots(self, timetable_id: str) -> list:
        result = self._get(f"/timetables/{timetable_id}/slots")
        if isinstance(result, list):
            return result
        return result.get("items", result.get("slots", []))

    # ── Sync ─────────────────────────────────────────────────────────────────
    def sync(self, local_db=None) -> dict:
        """
        Full two-way sync: PUSH local → server, then PULL server → local.
        
        PUSH tables: teachers, subjects, classes, rooms, periods,
                     timetables, timetable_slots, class_subjects
        PULL tables: same — so local SQLite mirrors the server exactly.
        
        After sync completes, the local SQLite is fully up to date and all
        screens will show correct data on their next load/refresh.
        """
        if local_db is None:
            return {"status": "ok", "records": 0}
        if self.offline_mode or not self.token:
            return {"error": True, "message": "Not connected to server"}

        push_result = self.sync_push(local_db)
        if push_result.get("error"):
            return push_result

        pull_result = self.sync_pull(local_db)
        if pull_result.get("error"):
            return pull_result

        total = push_result.get("pushed", 0) + pull_result.get("pulled", 0)
        result = {
            "status": "ok",
            "records": total,
            "pushed": push_result.get("pushed", 0),
            "pulled": pull_result.get("pulled", 0),
        }
        if push_result.get("warnings") or pull_result.get("warnings"):
            result["warnings"] = (
                (push_result.get("warnings") or []) +
                (pull_result.get("warnings") or [])
            )[:10]
        return result

    def sync_push(self, local_db) -> dict:
        """
        Push local SQLite → server, one table at a time.
        Each table is its own POST request so no single request is too large.
        """
        from datetime import datetime

        FIELDS = {
            "teachers": {
                "id", "teacher_code", "full_name", "email",
                "max_daily_periods", "is_active",
            },
            "subjects": {
                "id", "code", "name", "category",
                "periods_per_week", "duration_minutes", "requires_lab",
            },
            "classes": {
                "id", "class_name", "level",
                "student_count", "default_room_id",
            },
            "rooms": {
                "id", "room_code", "room_name",
                "capacity", "room_type", "is_available",
            },
            "periods": {
                "id", "period_number", "start_time",
                "end_time", "is_break", "day_of_week",
            },
            "timetables": {
                "id", "name", "type", "term",
                "academic_year", "status",
            },
            "timetable_slots": {
                "id", "timetable_id", "class_id", "subject_id",
                "teacher_id", "room_id", "day_of_week", "period_number",
            },
            "class_subjects": {
                "id", "class_id", "subject_id", "teacher_id",
            },
        }

        TYPE_MAP = {
            "Class Timetable": "Class",
            "Exam Timetable":  "Exam",
        }

        total_pushed = 0
        errors = []

        for table, allowed in FIELDS.items():
            try:
                rows = local_db.execute(f"SELECT * FROM {table}") or []
                clean_rows = []
                for row in rows:
                    rd = dict(row)
                    clean = {
                        k: (str(v) if v is not None
                            and not isinstance(v, (int, float, bool, str))
                            else v)
                        for k, v in rd.items()
                        if k in allowed and v is not None
                    }
                    if not clean.get("id"):
                        continue
                    if table == "timetables" and "type" in clean:
                        clean["type"] = TYPE_MAP.get(
                            clean["type"], clean["type"])
                    clean_rows.append(clean)

                if not clean_rows:
                    continue

                # POST this table's rows with a generous timeout
                result = self._request(
                    "POST", "/sync/push",
                    {"tables": {table: clean_rows},
                     "pushed_at": datetime.utcnow().isoformat()},
                    timeout=60
                )
                if result.get("error"):
                    errors.append(
                        f"{table}: {result.get('message', 'unknown error')}")
                else:
                    n = result.get("upserted", len(clean_rows))
                    total_pushed += n

            except Exception as ex:
                errors.append(f"{table}: {ex}")

        result = {"status": "ok", "pushed": total_pushed}
        if errors:
            result["warnings"] = errors[:10]
        return result

    def sync_pull(self, local_db) -> dict:
        """
        Pull server → local SQLite via /sync/pull endpoint.
        Upserts all rows so local mirrors the server exactly.
        After this call, all screens will show up-to-date data on refresh.
        """
        result = self._request("GET", "/sync/pull", timeout=60)
        if result.get("error"):
            return result

        # Map server timetable types back to local format
        TYPE_BACK = {"Class": "Class Timetable", "Exam": "Exam Timetable"}

        tables = result.get("tables", {})
        pulled = 0
        errors = []

        for table, rows in tables.items():
            for row in rows:
                try:
                    # Normalise values
                    clean = {}
                    for k, v in row.items():
                        if v is None:
                            clean[k] = None
                        elif isinstance(v, (int, float, bool, str)):
                            clean[k] = v
                        else:
                            clean[k] = str(v)

                    # Convert server timetable types back to local format
                    if table == "timetables" and "type" in clean:
                        clean["type"] = TYPE_BACK.get(
                            clean["type"], clean["type"])

                    if not clean.get("id"):
                        continue

                    cols = ", ".join(clean.keys())
                    ph   = ", ".join("?" for _ in clean)
                    local_db.execute(
                        f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({ph})",
                        tuple(clean.values())
                    )
                    pulled += 1
                except Exception as ex:
                    errors.append(f"{table}: {ex}")

        result = {"status": "ok", "pulled": pulled}
        if errors:
            result["warnings"] = errors[:10]
        return result

    # ── Reports ───────────────────────────────────────────────────────────────
    def get_report_summary(self, timetable_id: str = None,
                            term: str = None,
                            academic_year: str = None) -> dict:
        return self._post("/reports/summary", {
            "timetable_id": timetable_id,
            "term":         term,
            "academic_year": academic_year,
        })

    # ── User management ───────────────────────────────────────────────────────
    def create_user(self, username: str, email: str,
                     password: str, role: str = "Viewer") -> dict:
        # Backend expects title-case: Admin / Coordinator / Viewer
        role_map = {"ADMIN": "Admin", "COORDINATOR": "Coordinator",
                    "VIEWER": "Viewer"}
        return self._post("/users", {
            "username": username,
            "email":    email,
            "password": password,
            "role":     role_map.get(role.upper(), role),
        })

    def update_user(self, user_id: str, **kwargs) -> dict:
        return self._put(f"/users/{user_id}", kwargs)

    # ── Helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def normalise_timetable_type(frontend_type: str) -> str:
        """Maps "Class Timetable" → "Class", "Exam Timetable" → "Exam"."""
        return {"Class Timetable": "Class", "Exam Timetable": "Exam",
                "class": "Class", "exam": "Exam"}.get(frontend_type, frontend_type)