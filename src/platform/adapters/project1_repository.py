"""Project 1 Integration Repository Port & File-Backed Adapter.

Hexagonal storage port and persistence adapter for Project 1 contract records.
Provides schema-versioned, user-isolated, replay-protected, process-safe, atomic JSON storage.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import json
import os
import shutil
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Set

CURRENT_SCHEMA_VERSION = 1
DEFAULT_STORAGE_PATH = "data/project1_integration_records.json"

AUTHORITATIVE_CONTENT_KEYS = (
    "publication_id",
    "event_id",
    "signal_id",
    "decision_id",
    "canonical_live_decision_fingerprint",
    "candidate_id",
    "research_evidence_id",
    "strategy_name",
    "research_fingerprint",
    "runtime_authorization_fingerprint",
    "strategy_version",
    "symbol",
    "signal_type",
    "timeframe",
    "entry_price",
    "stop_loss",
    "take_profit_1",
    "take_profit_2",
    "take_profit_3",
    "confidence",
    "operational_stability_score",
    "trailing_stop",
    "invalidation_condition",
)


class RepositoryStatus(str, Enum):
    ABSENT = "ABSENT"
    CREATED = "CREATED"
    DUPLICATE_ACCEPTED = "DUPLICATE_ACCEPTED"
    INTEGRITY_CONFLICT = "INTEGRITY_CONFLICT"
    IDENTITY_AMBIGUOUS = "IDENTITY_AMBIGUOUS"
    STORAGE_CORRUPT = "STORAGE_CORRUPT"
    STORAGE_UNAVAILABLE = "STORAGE_UNAVAILABLE"
    PERSISTENCE_FAILURE = "PERSISTENCE_FAILURE"
    IDENTITY_COLLISION = "IDENTITY_COLLISION"


class StorageUnavailableError(RuntimeError):
    """Raised when process locking or file storage access fails."""

    pass


class StorageCorruptError(RuntimeError):
    """Raised when underlying JSON persistence storage is unreadable or malformed."""

    pass


@dataclass
class AuthoritativeLookupResult:
    status: RepositoryStatus
    record: Optional[Dict[str, Any]] = None
    message: str = ""


class _ProcessLock:
    """Inter-process file locking context manager using fcntl.flock where supported."""

    def __init__(self, lock_filepath: str) -> None:
        self.lock_filepath = lock_filepath
        self._fd: Optional[int] = None

    def __enter__(self) -> "_ProcessLock":
        dir_name = os.path.dirname(self.lock_filepath)
        if dir_name and not os.path.exists(dir_name):
            try:
                os.makedirs(dir_name, exist_ok=True)
            except Exception as exc:
                raise StorageUnavailableError(
                    f"Failed creating directory for lock file {self.lock_filepath}: {str(exc)}"
                ) from exc

        try:
            self._fd = os.open(self.lock_filepath, os.O_CREAT | os.O_RDWR)
        except Exception as exc:
            raise StorageUnavailableError(
                f"Failed opening process lock file {self.lock_filepath}: {str(exc)}"
            ) from exc

        try:
            import fcntl

            fcntl.flock(self._fd, fcntl.LOCK_EX)
        except Exception as exc:
            try:
                os.close(self._fd)
            except Exception:
                pass
            self._fd = None
            raise StorageUnavailableError(
                f"Failed acquiring process lock on {self.lock_filepath}: {str(exc)}"
            ) from exc

        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._fd is not None:
            try:
                import fcntl

                fcntl.flock(self._fd, fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                os.close(self._fd)
            except Exception:
                pass
            self._fd = None


class Project1IntegrationRepositoryPort(ABC):
    """Abstract outbound port for persisting Project 1 integration records."""

    @abstractmethod
    def save_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Save or update an integration record."""
        raise NotImplementedError

    @abstractmethod
    def ingest_authoritative_record(
        self, record: Dict[str, Any], user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Atomically lookup, compare content, update indexes, and durably persist record."""
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
    def find_authoritative_record(
        self, record: Dict[str, Any], user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Find existing record matching authoritative publication/event/signal identity."""
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


def _user_matches(rec: Dict[str, Any], user_id: Optional[str]) -> bool:
    if user_id is None:
        return True
    rec_user = rec.get("user_id")
    return rec_user in (user_id, None, "system", "p1_service_ingest")


class FileBackedProject1IntegrationRepository(Project1IntegrationRepositoryPort):
    """Hexagonal process-safe and thread-safe file-backed persistence adapter for Project 1 integration records."""

    def __init__(
        self,
        storage_filepath: str = DEFAULT_STORAGE_PATH,
        audit_control: Optional[Any] = None,
    ) -> None:
        self._storage_filepath = storage_filepath
        self._audit_control = audit_control
        self._lock = threading.RLock()
        self._is_unavailable: bool = False
        self._is_corrupt: bool = False
        self._last_mtime_ns: int = -1
        self._last_size: int = -1
        self._records: List[Dict[str, Any]] = []
        self._publication_map: Dict[str, Dict[str, Any]] = {}
        self._event_map: Dict[str, Dict[str, Any]] = {}
        self._signal_map: Dict[str, Dict[str, Any]] = {}
        self._ambiguous_keys: Set[str] = set()

        try:
            with self._lock, _ProcessLock(f"{self._storage_filepath}.lock"):
                self._load_from_storage_unlocked()
        except StorageUnavailableError:
            self._is_unavailable = True
        except Exception:
            self._is_unavailable = True

    def _all_records_identical_content(self, recs: List[Dict[str, Any]]) -> bool:
        if not recs or len(recs) <= 1:
            return True
        first = recs[0]
        for other in recs[1:]:
            for k in AUTHORITATIVE_CONTENT_KEYS:
                v1 = first.get(k)
                v2 = other.get(k)
                if isinstance(v1, float) and isinstance(v2, float):
                    if abs(v1 - v2) > 1e-9:
                        return False
                elif v1 != v2:
                    return False
        return True

    def _rebuild_indexes_unlocked(self) -> None:
        self._publication_map.clear()
        self._event_map.clear()
        self._signal_map.clear()
        self._ambiguous_keys.clear()

        pub_occ: Dict[str, List[Dict[str, Any]]] = {}
        evt_occ: Dict[str, List[Dict[str, Any]]] = {}
        sig_occ: Dict[str, List[Dict[str, Any]]] = {}

        for rec in self._records:
            pub_id = rec.get("publication_id")
            event_id = rec.get("event_id")
            sig_id = rec.get("signal_id")

            if pub_id:
                pub_occ.setdefault(pub_id, []).append(rec)
            if event_id:
                evt_occ.setdefault(event_id, []).append(rec)
            if sig_id:
                sig_occ.setdefault(sig_id, []).append(rec)

        for k, recs in pub_occ.items():
            if len(recs) == 1:
                self._publication_map[k] = recs[0]
            else:
                if not self._all_records_identical_content(recs):
                    self._ambiguous_keys.add(k)
                else:
                    self._publication_map[k] = recs[0]

        for k, recs in evt_occ.items():
            if len(recs) == 1:
                self._event_map[k] = recs[0]
            else:
                if not self._all_records_identical_content(recs):
                    self._ambiguous_keys.add(k)
                else:
                    self._event_map[k] = recs[0]

        for k, recs in sig_occ.items():
            if len(recs) == 1:
                self._signal_map[k] = recs[0]
            else:
                if not self._all_records_identical_content(recs):
                    self._ambiguous_keys.add(k)
                else:
                    self._signal_map[k] = recs[0]

    def _index_record_unlocked(self, rec: Dict[str, Any]) -> None:
        pub_id = rec.get("publication_id")
        event_id = rec.get("event_id")
        sig_id = rec.get("signal_id")

        if pub_id and pub_id not in self._ambiguous_keys:
            self._publication_map[pub_id] = rec
        if event_id and event_id not in self._ambiguous_keys:
            self._event_map[event_id] = rec
        if sig_id and sig_id not in self._ambiguous_keys:
            self._signal_map[sig_id] = rec

    def _load_from_storage_unlocked(self) -> None:
        if self._is_unavailable or self._is_corrupt:
            return

        if not os.path.exists(self._storage_filepath):
            self._records = []
            self._publication_map.clear()
            self._event_map.clear()
            self._signal_map.clear()
            self._ambiguous_keys.clear()
            self._last_mtime_ns = -1
            self._last_size = -1
            return

        try:
            st = os.stat(self._storage_filepath)
            if self._last_mtime_ns > 0 and st.st_mtime_ns == self._last_mtime_ns and st.st_size == self._last_size and self._records:
                return

            with open(self._storage_filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "records" in data:
                    self._records = data.get("records", [])
                elif isinstance(data, list):
                    self._records = data
                else:
                    raise ValueError("JSON top-level payload must be dict with 'records' key or list")
            self._last_mtime_ns = st.st_mtime_ns
            self._last_size = st.st_size
            self._rebuild_indexes_unlocked()
        except Exception as exc:
            self._is_corrupt = True
            self._records = []
            self._publication_map.clear()
            self._event_map.clear()
            self._signal_map.clear()
            self._ambiguous_keys.clear()
            self._last_mtime_ns = -1
            self._last_size = -1
            backup_path = f"{self._storage_filepath}.corrupt.{int(time.time())}"
            try:
                shutil.copy2(self._storage_filepath, backup_path)
            except Exception:
                pass
            if self._audit_control is not None and hasattr(self._audit_control, "record_failure"):
                self._audit_control.record_failure(
                    component="Project1IntegrationRepository",
                    error_type="CORRUPT_STORAGE_DETECTED",
                    message=f"Corrupt Project 1 repository file backed up to {backup_path}: {str(exc)}",
                    diagnostic_details=f"Filepath: {self._storage_filepath}",
                )

    def _flush_to_storage_unlocked(self) -> None:
        dir_name = os.path.dirname(self._storage_filepath)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)

        payload = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "updated_at": time.time(),
            "records": self._records,
        }

        unique_id = uuid.uuid4().hex
        tmp_path = f"{self._storage_filepath}.tmp.{unique_id}"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_path, self._storage_filepath)
            try:
                st = os.stat(self._storage_filepath)
                self._last_mtime_ns = st.st_mtime_ns
                self._last_size = st.st_size
            except Exception:
                pass

            if dir_name:
                try:
                    dir_fd = os.open(dir_name, os.O_RDONLY)
                    try:
                        os.fsync(dir_fd)
                    finally:
                        os.close(dir_fd)
                except Exception:
                    pass
        except Exception as exc:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
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

        if self._is_unavailable:
            raise StorageUnavailableError("Repository storage or process lock is unavailable.")
        if self._is_corrupt:
            raise StorageCorruptError("Cannot write to corrupted repository storage.")

        try:
            with self._lock, _ProcessLock(f"{self._storage_filepath}.lock"):
                self._load_from_storage_unlocked()
                if self._is_unavailable:
                    raise StorageUnavailableError("Repository storage or process lock is unavailable.")
                if self._is_corrupt:
                    raise StorageCorruptError("Cannot write to corrupted repository storage.")

                # Guard against mutating existing record's authoritative content via save_record
                if record.get("publication_id") or record.get("event_id"):
                    lookup_res = self.find_authoritative_lookup_unlocked(record, user_id=record.get("user_id"))
                    if lookup_res.record is not None:
                        existing = lookup_res.record
                        for k in AUTHORITATIVE_CONTENT_KEYS:
                            rec_val = record.get(k)
                            ext_val = existing.get(k)
                            if isinstance(rec_val, float) and isinstance(ext_val, float):
                                if abs(rec_val - ext_val) > 1e-9:
                                    raise ValueError(f"Mutation bypass rejected: Field {k} mutated.")
                            elif rec_val != ext_val:
                                raise ValueError(f"Mutation bypass rejected: Field {k} mutated.")

                prev_records = [dict(r) for r in self._records]

                rec_copy = dict(record)
                rec_copy["updated_at"] = time.time()
                if "created_at" not in rec_copy:
                    rec_copy["created_at"] = time.time()

                existing_idx = None
                for i, existing in enumerate(self._records):
                    if existing.get("integration_id") == int_id and _user_matches(existing, rec_copy.get("user_id")):
                        existing_idx = i
                        break

                if existing_idx is not None:
                    self._records[existing_idx] = rec_copy
                else:
                    self._records.append(rec_copy)

                self._index_record_unlocked(rec_copy)
                try:
                    self._flush_to_storage_unlocked()
                except Exception:
                    self._records = prev_records
                    self._rebuild_indexes_unlocked()
                    raise
                return dict(rec_copy)
        except StorageUnavailableError:
            self._is_unavailable = True
            raise

    def find_authoritative_lookup_unlocked(
        self, record: Dict[str, Any], user_id: Optional[str] = None
    ) -> AuthoritativeLookupResult:
        if self._is_unavailable:
            return AuthoritativeLookupResult(
                status=RepositoryStatus.STORAGE_UNAVAILABLE,
                message="Storage or process lock is unavailable.",
            )

        if self._is_corrupt:
            return AuthoritativeLookupResult(
                status=RepositoryStatus.STORAGE_CORRUPT,
                message="Underlying JSON persistence storage is corrupted.",
            )

        if not isinstance(record, dict):
            return AuthoritativeLookupResult(
                status=RepositoryStatus.ABSENT,
                message="Invalid payload record.",
            )

        target_pub_id = record.get("publication_id")
        target_event_id = record.get("event_id")
        target_sig_id = record.get("signal_id")

        for key in (target_pub_id, target_event_id, target_sig_id):
            if key and key in self._ambiguous_keys:
                return AuthoritativeLookupResult(
                    status=RepositoryStatus.IDENTITY_AMBIGUOUS,
                    message=f"Key '{key}' matches pre-existing ambiguous storage state.",
                )

        matches: List[Dict[str, Any]] = []

        for rec in self._records:
            if not _user_matches(rec, user_id):
                continue

            rec_pub_id = rec.get("publication_id")
            rec_event_id = rec.get("event_id")
            rec_sig_id = rec.get("signal_id")

            match_by_pub = bool(target_pub_id and rec_pub_id and target_pub_id == rec_pub_id)
            match_by_event = bool(target_event_id and rec_event_id and target_event_id == rec_event_id)
            match_by_sig = bool(target_sig_id and rec_sig_id and target_sig_id == rec_sig_id)

            if match_by_pub or match_by_event or match_by_sig:
                if match_by_pub and target_event_id and rec_event_id and target_event_id != rec_event_id:
                    return AuthoritativeLookupResult(
                        status=RepositoryStatus.IDENTITY_COLLISION,
                        record=dict(rec),
                        message="Identity collision: same publication_id assigned to different event_id.",
                    )
                if match_by_event and target_pub_id and rec_pub_id and target_pub_id != rec_pub_id:
                    return AuthoritativeLookupResult(
                        status=RepositoryStatus.IDENTITY_COLLISION,
                        record=dict(rec),
                        message="Identity collision: same event_id assigned to different publication_id.",
                    )
                if match_by_sig and target_pub_id and rec_pub_id and target_pub_id != rec_pub_id:
                    return AuthoritativeLookupResult(
                        status=RepositoryStatus.IDENTITY_COLLISION,
                        record=dict(rec),
                        message="Identity collision: same signal_id assigned to different publication_id.",
                    )
                matches.append(rec)

        if not matches:
            return AuthoritativeLookupResult(
                status=RepositoryStatus.ABSENT,
                message="No matching record found.",
            )

        if len(matches) == 1:
            return AuthoritativeLookupResult(
                status=RepositoryStatus.CREATED,
                record=dict(matches[0]),
                message="Single matching record resolved.",
            )

        if not self._all_records_identical_content(matches):
            return AuthoritativeLookupResult(
                status=RepositoryStatus.IDENTITY_AMBIGUOUS,
                message="Multiple matching records found with ambiguous / conflicting authoritative content.",
            )

        return AuthoritativeLookupResult(
            status=RepositoryStatus.CREATED,
            record=dict(matches[0]),
            message="Multiple identical duplicate records resolved.",
        )

    def ingest_authoritative_record(
        self, record: Dict[str, Any], user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if not isinstance(record, dict):
            raise ValueError("record must be a dictionary")

        int_id = record.get("integration_id")
        if not int_id:
            raise ValueError("record must contain integration_id")

        if self._is_unavailable:
            return {
                "status": RepositoryStatus.STORAGE_UNAVAILABLE,
                "record": None,
                "message": "Storage or process lock is unavailable.",
            }

        if self._is_corrupt:
            return {
                "status": RepositoryStatus.STORAGE_CORRUPT,
                "record": None,
                "message": "Underlying storage is corrupted.",
            }

        try:
            with self._lock, _ProcessLock(f"{self._storage_filepath}.lock"):
                self._load_from_storage_unlocked()

                if self._is_unavailable:
                    return {
                        "status": RepositoryStatus.STORAGE_UNAVAILABLE,
                        "record": None,
                        "message": "Storage or process lock is unavailable.",
                    }

                if self._is_corrupt:
                    return {
                        "status": RepositoryStatus.STORAGE_CORRUPT,
                        "record": None,
                        "message": "Underlying storage is corrupted.",
                    }

                lookup_res = self.find_authoritative_lookup_unlocked(record, user_id=user_id)

                if lookup_res.status in (
                    RepositoryStatus.IDENTITY_AMBIGUOUS,
                    RepositoryStatus.STORAGE_CORRUPT,
                    RepositoryStatus.STORAGE_UNAVAILABLE,
                    RepositoryStatus.IDENTITY_COLLISION,
                ):
                    return {
                        "status": lookup_res.status,
                        "record": lookup_res.record,
                        "message": lookup_res.message,
                    }

                if lookup_res.record is not None:
                    existing = lookup_res.record
                    is_identical = True
                    for k in AUTHORITATIVE_CONTENT_KEYS:
                        rec_val = record.get(k)
                        ext_val = existing.get(k)
                        if isinstance(rec_val, float) and isinstance(ext_val, float):
                            if abs(rec_val - ext_val) > 1e-9:
                                is_identical = False
                                break
                        elif rec_val != ext_val:
                            is_identical = False
                            break

                    if is_identical:
                        return {
                            "status": RepositoryStatus.DUPLICATE_ACCEPTED,
                            "record": dict(existing),
                            "message": "Idempotent replay accepted.",
                        }
                    else:
                        return {
                            "status": RepositoryStatus.INTEGRITY_CONFLICT,
                            "record": dict(existing),
                            "message": "Same publication identity received with mutated authoritative content.",
                        }

                # ABSENT -> Create new record atomically
                prev_records = [dict(r) for r in self._records]

                rec_copy = dict(record)
                rec_copy["updated_at"] = time.time()
                if "created_at" not in rec_copy:
                    rec_copy["created_at"] = time.time()

                existing_idx = None
                for i, existing in enumerate(self._records):
                    if existing.get("integration_id") == int_id and _user_matches(existing, user_id):
                        existing_idx = i
                        break

                if existing_idx is not None:
                    self._records[existing_idx] = rec_copy
                else:
                    self._records.append(rec_copy)

                self._index_record_unlocked(rec_copy)

                try:
                    self._flush_to_storage_unlocked()
                except Exception as exc:
                    self._records = prev_records
                    self._rebuild_indexes_unlocked()
                    return {
                        "status": RepositoryStatus.PERSISTENCE_FAILURE,
                        "record": None,
                        "message": f"Persistence write failed: {str(exc)}",
                    }

                return {
                    "status": RepositoryStatus.CREATED,
                    "record": dict(rec_copy),
                    "message": "Authoritative record created successfully.",
                }
        except StorageUnavailableError as exc:
            self._is_unavailable = True
            return {
                "status": RepositoryStatus.STORAGE_UNAVAILABLE,
                "record": None,
                "message": f"Process lock or storage unavailable: {str(exc)}",
            }

    def get_record_by_id(
        self, integration_id: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        if self._is_unavailable or self._is_corrupt:
            return None
        try:
            with self._lock, _ProcessLock(f"{self._storage_filepath}.lock"):
                self._load_from_storage_unlocked()
                if self._is_unavailable or self._is_corrupt:
                    return None
                for rec in self._records:
                    if rec.get("integration_id") == integration_id:
                        if _user_matches(rec, user_id):
                            return dict(rec)
                return None
        except StorageUnavailableError:
            self._is_unavailable = True
            return None

    def list_records_for_user(
        self,
        user_id: Optional[str] = None,
        symbol: Optional[str] = None,
        lifecycle_state: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if self._is_unavailable or self._is_corrupt:
            return []
        try:
            with self._lock, _ProcessLock(f"{self._storage_filepath}.lock"):
                self._load_from_storage_unlocked()
                if self._is_unavailable or self._is_corrupt:
                    return []
                filtered = []
                for rec in reversed(self._records):
                    if not _user_matches(rec, user_id):
                        continue
                    if symbol is not None and rec.get("symbol") != symbol.strip().upper():
                        continue
                    if lifecycle_state is not None and rec.get("lifecycle_state") != lifecycle_state.strip().upper():
                        continue
                    filtered.append(dict(rec))
                    if len(filtered) >= limit:
                        break
                return filtered
        except StorageUnavailableError:
            self._is_unavailable = True
            return []

    def find_authoritative_record_unlocked(
        self, record: Dict[str, Any], user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        lookup_res = self.find_authoritative_lookup_unlocked(record, user_id=user_id)
        if lookup_res.status in (
            RepositoryStatus.IDENTITY_AMBIGUOUS,
            RepositoryStatus.STORAGE_CORRUPT,
            RepositoryStatus.STORAGE_UNAVAILABLE,
            RepositoryStatus.IDENTITY_COLLISION,
            RepositoryStatus.ABSENT,
        ):
            return None
        return lookup_res.record

    def find_authoritative_record(
        self, record: Dict[str, Any], user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        if self._is_unavailable or self._is_corrupt:
            return None
        try:
            with self._lock, _ProcessLock(f"{self._storage_filepath}.lock"):
                self._load_from_storage_unlocked()
                return self.find_authoritative_record_unlocked(record, user_id=user_id)
        except StorageUnavailableError:
            self._is_unavailable = True
            return None

    def is_duplicate_request(
        self, signal_id: str, user_id: Optional[str] = None, timestamp: Optional[float] = None
    ) -> bool:
        if self._is_unavailable or self._is_corrupt:
            return False
        try:
            with self._lock, _ProcessLock(f"{self._storage_filepath}.lock"):
                self._load_from_storage_unlocked()
                if self._is_unavailable or self._is_corrupt:
                    return False
                if signal_id in self._signal_map or signal_id in self._publication_map or signal_id in self._event_map:
                    candidate = (
                        self._signal_map.get(signal_id)
                        or self._publication_map.get(signal_id)
                        or self._event_map.get(signal_id)
                    )
                    if candidate and _user_matches(candidate, user_id):
                        return True

                for rec in self._records:
                    if (
                        rec.get("signal_id") == signal_id
                        or rec.get("publication_id") == signal_id
                        or rec.get("event_id") == signal_id
                    ):
                        if _user_matches(rec, user_id):
                            return True
                return False
        except StorageUnavailableError:
            self._is_unavailable = True
            return False

    def update_lifecycle_state(
        self,
        signal_id: str,
        lifecycle_state: str,
        reason: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        if self._is_unavailable or self._is_corrupt:
            return False
        ls_upper = lifecycle_state.strip().upper()
        try:
            with self._lock, _ProcessLock(f"{self._storage_filepath}.lock"):
                self._load_from_storage_unlocked()
                if self._is_unavailable or self._is_corrupt:
                    return False

                prev_records = [dict(r) for r in self._records]

                matching_indices = []

                for i, rec in enumerate(self._records):
                    if not _user_matches(rec, user_id):
                        continue

                    if (
                        rec.get("signal_id") == signal_id
                        or rec.get("publication_id") == signal_id
                        or rec.get("event_id") == signal_id
                    ):
                        matching_indices.append(i)

                if len(matching_indices) > 1:
                    lineages = set()
                    for idx in matching_indices:
                        r = self._records[idx]
                        lineages.add((r.get("publication_id"), r.get("event_id"), r.get("signal_id")))
                    if len(lineages) > 1:
                        return False

                if not matching_indices:
                    return False

                for idx in matching_indices:
                    updated_rec = dict(self._records[idx])
                    updated_rec["lifecycle_state"] = ls_upper
                    if reason is not None:
                        updated_rec["lifecycle_reason"] = reason
                    updated_rec["updated_at"] = time.time()
                    self._records[idx] = updated_rec
                    self._index_record_unlocked(updated_rec)

                try:
                    self._flush_to_storage_unlocked()
                except Exception:
                    self._records = prev_records
                    self._rebuild_indexes_unlocked()
                    return False
                return True
        except StorageUnavailableError:
            self._is_unavailable = True
            return False
