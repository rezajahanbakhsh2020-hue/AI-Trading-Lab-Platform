"""Project 1 Integration Repository Port & File-Backed Adapter.

Hexagonal storage port and persistence adapter for Project 1 contract records.
Provides schema-versioned, user-isolated, replay-protected, atomic JSON storage.
"""

from abc import ABC, abstractmethod
import json
import os
import shutil
import time
from typing import Any, Dict, List, Optional

CURRENT_SCHEMA_VERSION = 1
DEFAULT_STORAGE_PATH = "data/project1_integration_records.json"


class Project1IntegrationRepositoryPort(ABC):
    """Abstract outbound port for persisting Project 1 integration records."""

    @abstractmethod
    def save_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Save or update an integration record."""
        raise NotImplementedError

    @abstractmethod
    def get_record_by_id(
        self, integration_id: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieve record by integration_id, enforcing user isolation if user_id is provided."""
        raise NotImplementedError

    @abstractmethod
    def list_records_for_user(
        self,
        user_id: Optional[str] = None,
        symbol: Optional[str] = None,
        lifecycle_state: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List integration records filtered by user_id, symbol, and lifecycle_state."""
        raise NotImplementedError

    @abstractmethod
    def is_duplicate_request(
        self, signal_id: str, user_id: Optional[str] = None, timestamp: Optional[float] = None
    ) -> bool:
        """Check if request with given signal_id and user_id has already been processed."""
        raise NotImplementedError

    @abstractmethod
    def update_lifecycle_state(
        self,
        signal_id: str,
        lifecycle_state: str,
        reason: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        """Update lifecycle state of an existing signal record."""
        raise NotImplementedError


class FileBackedProject1IntegrationRepository(Project1IntegrationRepositoryPort):
    """Hexagonal file-backed persistence adapter for Project 1 integration records."""

    def __init__(
        self,
        storage_filepath: str = DEFAULT_STORAGE_PATH,
        audit_control: Optional[Any] = None,
    ) -> None:
        self._storage_filepath = storage_filepath
        self._audit_control = audit_control
        self._records: List[Dict[str, Any]] = []
        self._load_from_storage()

    def _load_from_storage(self) -> None:
        if not os.path.exists(self._storage_filepath):
            self._records = []
            return

        try:
            with open(self._storage_filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "records" in data:
                    self._records = data.get("records", [])
                elif isinstance(data, list):
                    self._records = data
                else:
                    self._records = []
        except Exception as exc:
            # Corrupt file handling: backup corrupt file and start fresh
            backup_path = f"{self._storage_filepath}.corrupt.{int(time.time())}"
            try:
                shutil.copy2(self._storage_filepath, backup_path)
            except Exception:
                pass
            self._records = []
            if self._audit_control is not None and hasattr(self._audit_control, "record_failure"):
                self._audit_control.record_failure(
                    component="Project1IntegrationRepository",
                    error_type="CORRUPT_STORAGE_DETECTED",
                    message=f"Corrupt Project 1 repository file backed up to {backup_path}: {str(exc)}",
                    diagnostic_details=f"Filepath: {self._storage_filepath}",
                )

    def _flush_to_storage(self) -> None:
        dir_name = os.path.dirname(self._storage_filepath)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)

        payload = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "updated_at": time.time(),
            "records": self._records,
        }

        tmp_path = f"{self._storage_filepath}.tmp.{int(time.time()*1000)}"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)

            os.replace(tmp_path, self._storage_filepath)
        except Exception as exc:
            if self._audit_control is not None and hasattr(self._audit_control, "record_failure"):
                self._audit_control.record_failure(
                    component="Project1IntegrationRepository",
                    error_type="STORAGE_WRITE_FAILURE",
                    message=f"Failed flushing Project 1 integration records: {str(exc)}",
                    diagnostic_details=f"Filepath: {self._storage_filepath}",
                )
            raise

    def save_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(record, dict):
            raise ValueError("record must be a dictionary")

        int_id = record.get("integration_id")
        if not int_id:
            raise ValueError("record must contain integration_id")

        rec_copy = dict(record)
        rec_copy["updated_at"] = time.time()
        if "created_at" not in rec_copy:
            rec_copy["created_at"] = time.time()

        # Update if exists, else append
        existing_idx = None
        for i, existing in enumerate(self._records):
            if existing.get("integration_id") == int_id:
                existing_idx = i
                break

        if existing_idx is not None:
            self._records[existing_idx] = rec_copy
        else:
            self._records.append(rec_copy)

        self._flush_to_storage()
        return rec_copy

    def get_record_by_id(
        self, integration_id: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        for rec in self._records:
            if rec.get("integration_id") == integration_id:
                if user_id is not None and rec.get("user_id") not in (user_id, None, "system"):
                    return None
                return dict(rec)
        return None

    def list_records_for_user(
        self,
        user_id: Optional[str] = None,
        symbol: Optional[str] = None,
        lifecycle_state: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        filtered = []
        for rec in reversed(self._records):
            if user_id is not None and rec.get("user_id") not in (user_id, None, "system"):
                continue
            if symbol is not None and rec.get("symbol") != symbol.strip().upper():
                continue
            if lifecycle_state is not None and rec.get("lifecycle_state") != lifecycle_state.strip().upper():
                continue
            filtered.append(dict(rec))
            if len(filtered) >= limit:
                break
        return filtered

    def is_duplicate_request(
        self, signal_id: str, user_id: Optional[str] = None, timestamp: Optional[float] = None
    ) -> bool:
        for rec in self._records:
            if rec.get("signal_id") == signal_id:
                if user_id is not None and rec.get("user_id") not in (user_id, None, "system"):
                    continue
                return True
        return False

    def update_lifecycle_state(
        self,
        signal_id: str,
        lifecycle_state: str,
        reason: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        updated = False
        ls_upper = lifecycle_state.strip().upper()
        for i, rec in enumerate(self._records):
            if rec.get("signal_id") == signal_id:
                if user_id is not None and rec.get("user_id") not in (user_id, None, "system"):
                    continue
                updated_rec = dict(rec)
                updated_rec["lifecycle_state"] = ls_upper
                if reason is not None:
                    updated_rec["lifecycle_reason"] = reason
                updated_rec["updated_at"] = time.time()
                self._records[i] = updated_rec
                updated = True

        if updated:
            self._flush_to_storage()
        return updated
