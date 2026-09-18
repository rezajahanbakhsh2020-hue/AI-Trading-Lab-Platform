"""Workspace repository port implementation with file-backed JSON persistence (Part 21: Hexagonal Workspace Persistence).

Provides FileBackedWorkspaceRepository implementing WorkspaceRepositoryPort with schema versioning,
atomic writes, corrupt file backup, and process-restart persistence.
"""

import json
import logging
import os
import shutil
import time
from typing import Dict, Optional

from src.platform.domain.notification import NotificationPreferences
from src.platform.domain.workspace import Watchlist, Workspace
from src.platform.services.workspace import WorkspaceRepositoryPort

logger = logging.getLogger(__name__)

CURRENT_WORKSPACE_SCHEMA_VERSION = 1


class WorkspaceRepositoryError(Exception):
    """Base exception for workspace repository operational failures."""
    pass


class CorruptWorkspaceStorageError(WorkspaceRepositoryError):
    """Raised when persisted workspace storage files are corrupted or unparseable."""
    pass


class FileBackedWorkspaceRepository(WorkspaceRepositoryPort):
    """File-backed JSON implementation of WorkspaceRepositoryPort with atomic writes and corrupt file backup."""

    def __init__(self, storage_dir: str = ".data") -> None:
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self.workspaces_file = os.path.join(self.storage_dir, "workspaces.json")
        self._workspaces: Dict[str, Workspace] = {}
        self._load()

    def _serialize_workspace(self, workspace: Workspace) -> dict:
        data = workspace.to_dict()
        data["_schema_version"] = CURRENT_WORKSPACE_SCHEMA_VERSION
        return data

    def _deserialize_workspace(self, data: dict) -> Workspace:
        user_id = data["user_id"]
        active_wl_id = data.get("active_watchlist_id", "default")
        active_symbol = data.get("active_symbol", "XAUUSD")
        watchlists_raw = data.get("watchlists", {})

        watchlists: Dict[str, Watchlist] = {}
        for wl_id, wl_data in watchlists_raw.items():
            if isinstance(wl_data, dict):
                watchlists[wl_id] = Watchlist.from_dict(wl_data)

        if not watchlists:
            default_wl = Watchlist(
                watchlist_id="default",
                name="Main Watchlist",
                symbols=("XAUUSD", "EURUSD", "GBPUSD", "BTCUSD", "SPX500"),
                is_default=True,
            )
            watchlists["default"] = default_wl
            active_wl_id = "default"

        notif_prefs_raw = data.get("notification_preferences")
        notif_prefs = (
            NotificationPreferences.from_dict(notif_prefs_raw)
            if isinstance(notif_prefs_raw, dict)
            else NotificationPreferences()
        )

        return Workspace(
            user_id=user_id,
            active_watchlist_id=active_wl_id if active_wl_id in watchlists else list(watchlists.keys())[0],
            active_symbol=active_symbol,
            watchlists=watchlists,
            chart_preferences=data.get("chart_preferences", {}),
            layout_preferences=data.get("layout_preferences", {}),
            notification_preferences=notif_prefs,
            updated_at=float(data.get("updated_at", time.time())),
        )

    def _backup_corrupt_file(self, filepath: str) -> str:
        timestamp = int(time.time())
        corrupt_backup = f"{filepath}.corrupt.{timestamp}"
        try:
            if os.path.exists(filepath):
                shutil.copy2(filepath, corrupt_backup)
                logger.warning("Corrupt workspace file backed up to '%s'", corrupt_backup)
        except Exception as exc:
            logger.error("Failed to backup corrupt workspace file '%s': %s", filepath, exc)
        return corrupt_backup

    def _load(self) -> None:
        if os.path.exists(self.workspaces_file):
            try:
                with open(self.workspaces_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not isinstance(data, dict):
                        raise ValueError("Workspace storage root must be a dictionary keyed by user_id")
                    for user_id, ws_data in data.items():
                        if isinstance(ws_data, dict):
                            self._workspaces[user_id] = self._deserialize_workspace(ws_data)
            except Exception as e:
                self._backup_corrupt_file(self.workspaces_file)
                raise CorruptWorkspaceStorageError(f"Failed to load workspace file '{self.workspaces_file}': {e}") from e

    def _save(self) -> None:
        try:
            serialized = {uid: self._serialize_workspace(ws) for uid, ws in self._workspaces.items()}
            temp_file = f"{self.workspaces_file}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(serialized, f, indent=2)
            os.replace(temp_file, self.workspaces_file)
        except Exception as e:
            raise WorkspaceRepositoryError(f"Failed to save workspaces to '{self.workspaces_file}': {e}") from e

    def get_workspace(self, user_id: str) -> Optional[Workspace]:
        if not isinstance(user_id, str) or not user_id.strip():
            return None
        return self._workspaces.get(user_id.strip())

    def save_workspace(self, workspace: Workspace) -> Workspace:
        if not isinstance(workspace, Workspace):
            raise ValueError("workspace must be a Workspace instance")
        self._workspaces[workspace.user_id] = workspace
        self._save()
        return workspace

    def delete_workspace(self, user_id: str) -> bool:
        if not isinstance(user_id, str) or not user_id.strip():
            return False
        clean_uid = user_id.strip()
        if clean_uid in self._workspaces:
            del self._workspaces[clean_uid]
            self._save()
            return True
        return False
