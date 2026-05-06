"""Sync engine for offline-to-online synchronization."""
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Optional
import time

from app.api_client import ApiClient
from app.local_db import LocalDB
from app.config import SYNC_RETRY_INTERVALS


class SyncEngine:
    """Handles synchronization between local SQLite and server."""
    
    def __init__(self, api_client: ApiClient, local_db: LocalDB):
        self.api_client = api_client
        self.local_db = local_db
        self.is_syncing = False
        self.last_sync_status = None
        self.conflicts = []
    
    async def sync(self) -> Dict:
        """Perform full sync (push then pull)."""
        if self.is_syncing:
            return {"status": "already_syncing"}
        
        self.is_syncing = True
        self.conflicts = []
        
        try:
            # Step 1: Push pending changes
            push_result = await self._push_changes()
            
            if push_result.get("error"):
                self.last_sync_status = "push_failed"
                return {"status": "failed", "error": push_result.get("message")}
            
            # Step 2: Pull changes since last sync
            pull_result = await self._pull_changes()
            
            if pull_result.get("error"):
                self.last_sync_status = "pull_failed"
                return {"status": "failed", "error": pull_result.get("message")}
            
            # Step 3: Update sync time
            self.local_db.update_sync_time()
            
            self.last_sync_status = "success"
            return {
                "status": "success",
                "pushed": push_result.get("count", 0),
                "pulled": pull_result.get("count", 0),
                "conflicts": len(self.conflicts)
            }
            
        except Exception as e:
            self.last_sync_status = "error"
            return {"status": "error", "message": str(e)}
            
        finally:
            self.is_syncing = False
    
    async def _push_changes(self) -> Dict:
        """Push pending changes to server."""
        pending = self.local_db.get_pending_changes()
        
        if not pending:
            return {"count": 0}
        
        # Group changes by operation
        changes = []
        change_ids = []
        
        for change in pending:
            changes.append({
                "operation": change["operation"],
                "table": change["table_name"],
                "record_id": change["record_id"],
                "data": json.loads(change["data_json"])
            })
            change_ids.append(change["id"])
        
        # Try to push with retry logic
        for attempt, delay in enumerate(SYNC_RETRY_INTERVALS):
            try:
                result = self.api_client._request(
                    "POST",
                    "/sync/push",
                    json={"changes": changes}
                )
                
                if not result.get("error"):
                    # Mark changes as synced
                    self.local_db.mark_changes_synced(change_ids)
                    
                    # Handle any conflicts reported
                    if result.get("conflicts"):
                        self.conflicts.extend(result["conflicts"])
                    
                    return {
                        "count": len(changes),
                        "conflicts": result.get("conflicts", [])
                    }
                
                if attempt < len(SYNC_RETRY_INTERVALS) - 1:
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                if attempt < len(SYNC_RETRY_INTERVALS) - 1:
                    await asyncio.sleep(delay)
                else:
                    return {"error": True, "message": str(e)}
        
        return {"error": True, "message": "Max retries exceeded"}
    
    async def _pull_changes(self) -> Dict:
        """Pull changes from server since last sync."""
        last_sync = self.local_db.get_last_sync_time()
        
        if not last_sync:
            last_sync = "1970-01-01T00:00:00"
        
        # Try to pull with retry logic
        for attempt, delay in enumerate(SYNC_RETRY_INTERVALS):
            try:
                result = self.api_client._request(
                    "GET",
                    f"/sync/pull?since={last_sync}"
                )
                
                if not result.get("error"):
                    # Apply changes to local DB
                    await self._apply_pulled_changes(result.get("changes", []))
                    
                    return {
                        "count": len(result.get("changes", [])),
                        "timestamp": result.get("timestamp")
                    }
                
                if attempt < len(SYNC_RETRY_INTERVALS) - 1:
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                if attempt < len(SYNC_RETRY_INTERVALS) - 1:
                    await asyncio.sleep(delay)
                else:
                    return {"error": True, "message": str(e)}
        
        return {"error": True, "message": "Max retries exceeded"}
    
    async def _apply_pulled_changes(self, changes: List[Dict]):
        """Apply pulled changes to local database."""
        for change in changes:
            table = change["table"]
            operation = change["operation"]
            record_id = change["record_id"]
            data = change["data"]
            
            if operation == "INSERT" or operation == "UPDATE":
                # Check if record exists
                existing = self.local_db.execute(
                    f"SELECT id FROM {table} WHERE id = ?",
                    (record_id,)
                )
                
                if existing:
                    # Update
                    set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
                    values = list(data.values()) + [record_id]
                    
                    self.local_db.execute(
                        f"UPDATE {table} SET {set_clause} WHERE id = ?",
                        values
                    )
                else:
                    # Insert
                    columns = ', '.join(data.keys())
                    placeholders = ', '.join(['?' for _ in data])
                    values = list(data.values())
                    
                    self.local_db.execute(
                        f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
                        values
                    )
                    
            elif operation == "DELETE":
                self.local_db.execute(
                    f"DELETE FROM {table} WHERE id = ?",
                    (record_id,)
                )
    
    def get_sync_status(self) -> Dict:
        """Get current sync status."""
        pending_count = len(self.local_db.get_pending_changes())
        last_sync = self.local_db.get_last_sync_time()
        
        return {
            "is_syncing": self.is_syncing,
            "pending_changes": pending_count,
            "last_sync": last_sync,
            "last_status": self.last_sync_status,
            "conflicts": len(self.conflicts)
        }