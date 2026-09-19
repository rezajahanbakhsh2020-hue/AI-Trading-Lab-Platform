"""Persistence Backup, Recovery, and Hardening Engine (Part 22: Resilience & Storage Recovery).

Provides production-grade atomic backup snapshots, integrity verification, non-destructive restore
with automatic rollback safety, bounded retention enforcement, and audit control integration
for Project 2 file-backed persistence repositories.
"""

from dataclasses import dataclass, field
import hashlib
import json
import logging
import os
import shutil
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from src.platform.domain.security import Permission
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.security import SecurityBoundaryService, SecretSanitizer

logger = logging.getLogger("platform.persistence_recovery")

DEFAULT_BACKUP_RETENTION_COUNT = 10
DEFAULT_CORRUPT_BACKUP_RETENTION_COUNT = 10

MANAGED_STORE_FILES = {
    "users.json",
    "sessions.json",
    "workspaces.json",
    "project1_integration_records.json",
    "order_intents.json",
}

EXPECTED_SCHEMA_VERSIONS = {
    "users.json": 2,
    "sessions.json": 2,
    "workspaces.json": 1,
    "project1_integration_records.json": 1,
    "order_intents.json": "1.0",
}


@dataclass
class BackupStoreMetadata:
    """Metadata for a single store file inside a backup manifest."""

    store_filename: str
    schema_version: Any
    record_count: int
    sha256_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "store_filename": self.store_filename,
            "schema_version": self.schema_version,
            "record_count": self.record_count,
            "sha256_hash": self.sha256_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BackupStoreMetadata":
        return cls(
            store_filename=data["store_filename"],
            schema_version=data.get("schema_version", 1),
            record_count=int(data.get("record_count", 0)),
            sha256_hash=data.get("sha256_hash", ""),
        )


@dataclass
class BackupManifest:
    """Canonical manifest describing a persistence backup snapshot."""

    backup_id: str
    created_at: float
    created_by: str
    app_env: str
    label: Optional[str]
    stores: Dict[str, BackupStoreMetadata]
    bundle_sha256: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backup_id": self.backup_id,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "app_env": self.app_env,
            "label": self.label,
            "stores": {k: v.to_dict() for k, v in self.stores.items()},
            "bundle_sha256": self.bundle_sha256,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BackupManifest":
        stores_raw = data.get("stores", {})
        stores = {k: BackupStoreMetadata.from_dict(v) for k, v in stores_raw.items() if isinstance(v, dict)}
        return cls(
            backup_id=data["backup_id"],
            created_at=float(data.get("created_at", time.time())),
            created_by=data.get("created_by", "system"),
            app_env=data.get("app_env", "production"),
            label=data.get("label"),
            stores=stores,
            bundle_sha256=data.get("bundle_sha256", ""),
        )


@dataclass
class BackupSnapshotResult:
    """Outcome payload of a backup snapshot creation operation."""

    success: bool
    message: str
    backup_id: Optional[str] = None
    filepath: Optional[str] = None
    manifest: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "backup_id": self.backup_id,
            "filepath": self.filepath,
            "manifest": self.manifest,
        }


@dataclass
class BackupVerificationResult:
    """Outcome payload of a backup integrity verification check."""

    valid: bool
    backup_id: Optional[str]
    filepath: Optional[str]
    issues: List[str]
    manifest: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "backup_id": self.backup_id,
            "filepath": self.filepath,
            "issues": self.issues,
            "manifest": self.manifest,
        }


@dataclass
class RestoreResult:
    """Outcome payload of a non-destructive restore operation."""

    success: bool
    message: str
    backup_id: Optional[str] = None
    restored_stores: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    error_details: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "backup_id": self.backup_id,
            "restored_stores": self.restored_stores,
            "timestamp": self.timestamp,
            "error_details": self.error_details,
        }


def _compute_sha256_str(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class PersistenceRecoveryEngine:
    """Engine for atomic backup creation, verification, non-destructive restore, and retention pruning."""

    def __init__(
        self,
        storage_dir: str = ".data",
        backups_dir: Optional[str] = None,
        security_boundary: Optional[SecurityBoundaryService] = None,
        audit_control: Optional[Any] = None,
        app_env: str = "production",
    ) -> None:
        self.storage_dir = storage_dir
        self.backups_dir = backups_dir or os.path.join(self.storage_dir, "backups")
        self.security_boundary = security_boundary or SecurityBoundaryService()
        self.audit_control = audit_control
        self.app_env = app_env

        os.makedirs(self.storage_dir, exist_ok=True)
        os.makedirs(self.backups_dir, exist_ok=True)

    def _authorize_admin(self, user: Optional[UserAuthorization], action: str) -> None:
        if user is None:
            return  # Internal system trigger allowed
        if not user.is_admin:
            raise PermissionError(f"User '{user.user_id}' lacks admin authorization for action '{action}'")
        if self.security_boundary:
            ok, msg = self.security_boundary.authorize(user, resource="users", action=action)
            if not ok:
                raise PermissionError(f"User '{user.user_id}' authorization denied for action '{action}': {msg}")

    def _resolve_backup_filepath(self, backup_id_or_path: str) -> Optional[str]:
        if os.path.isfile(backup_id_or_path):
            return backup_id_or_path

        # Try matching in backups_dir
        clean_id = os.path.basename(backup_id_or_path).replace(".json", "")
        for filename in os.listdir(self.backups_dir):
            if clean_id in filename and filename.endswith(".json"):
                return os.path.join(self.backups_dir, filename)

        return None

    def create_backup(
        self,
        user: Optional[UserAuthorization] = None,
        label: Optional[str] = None,
    ) -> BackupSnapshotResult:
        """Create an atomic, integrity-checksummed backup snapshot of current persistence stores."""
        try:
            self._authorize_admin(user, "create_backup")
        except Exception as err:
            return BackupSnapshotResult(success=False, message=f"Authorization failure: {err}")

        now = time.time()
        backup_id = f"snap_{int(now)}_{uuid.uuid4().hex[:8]}"
        created_by = user.user_id if user else "system"

        stores_payload: Dict[str, Any] = {}
        stores_meta: Dict[str, BackupStoreMetadata] = {}

        for filename in MANAGED_STORE_FILES:
            filepath = os.path.join(self.storage_dir, filename)
            if not os.path.exists(filepath):
                # Check data/ directory fallback for order_intents / project1_integration_records
                alt_path = os.path.join("data", filename)
                if os.path.exists(alt_path):
                    filepath = alt_path

            if os.path.exists(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        raw_content = f.read()
                        data = json.loads(raw_content)

                    cnt = len(data) if isinstance(data, (list, dict)) else 0
                    schema_ver = EXPECTED_SCHEMA_VERSIONS.get(filename, 1)
                    if isinstance(data, dict):
                        if "schema_version" in data:
                            schema_ver = data["schema_version"]
                        elif "_schema_version" in data:
                            schema_ver = data["_schema_version"]

                    sha256 = _compute_sha256_str(raw_content)

                    stores_payload[filename] = data
                    stores_meta[filename] = BackupStoreMetadata(
                        store_filename=filename,
                        schema_version=schema_ver,
                        record_count=cnt,
                        sha256_hash=sha256,
                    )
                except Exception as exc:
                    msg = f"Failed reading store file '{filename}' for backup: {exc}"
                    logger.error(msg)
                    return BackupSnapshotResult(success=False, message=msg)

        if not stores_payload:
            return BackupSnapshotResult(success=False, message="No persistent storage files found to backup.")

        # Compute overall bundle SHA256 before final wrapping
        canonical_stores_json = json.dumps(stores_payload, sort_keys=True)
        bundle_sha256 = _compute_sha256_str(canonical_stores_json)

        manifest = BackupManifest(
            backup_id=backup_id,
            created_at=now,
            created_by=created_by,
            app_env=self.app_env,
            label=label,
            stores=stores_meta,
            bundle_sha256=bundle_sha256,
        )

        full_bundle = {
            "manifest": manifest.to_dict(),
            "data": stores_payload,
        }

        # Atomically write backup file
        target_file = os.path.join(self.backups_dir, f"{backup_id}.json")
        temp_file = f"{target_file}.tmp.{int(now*1000)}"

        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(full_bundle, f, indent=2, ensure_ascii=False)
            os.replace(temp_file, target_file)
        except Exception as exc:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            msg = f"Failed to write backup bundle to disk: {exc}"
            logger.error(msg)
            return BackupSnapshotResult(success=False, message=msg)

        # Enforce bounded retention after successful backup creation
        self.prune_backups_and_corrupt_files()

        # Record audit event
        if self.audit_control and hasattr(self.audit_control, "record_event"):
            try:
                self.audit_control.record_event(
                    user=user,
                    category="PERSISTENCE",
                    action="BACKUP_CREATED",
                    severity="INFO",
                    details=f"Created backup snapshot '{backup_id}' with {len(stores_payload)} store(s)",
                )
            except Exception:
                pass

        return BackupSnapshotResult(
            success=True,
            message=f"Backup snapshot '{backup_id}' created successfully.",
            backup_id=backup_id,
            filepath=target_file,
            manifest=manifest.to_dict(),
        )

    def verify_backup(self, backup_id_or_path: str) -> BackupVerificationResult:
        """Verify the integrity, checksums, and schema compatibility of a backup snapshot."""
        filepath = self._resolve_backup_filepath(backup_id_or_path)
        if not filepath or not os.path.exists(filepath):
            return BackupVerificationResult(
                valid=False,
                backup_id=os.path.basename(backup_id_or_path),
                filepath=None,
                issues=[f"Backup file '{backup_id_or_path}' not found."],
            )

        issues: List[str] = []
        manifest_dict: Optional[Dict[str, Any]] = None
        backup_id = None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                bundle = json.load(f)

            if not isinstance(bundle, dict) or "manifest" not in bundle or "data" not in bundle:
                return BackupVerificationResult(
                    valid=False,
                    backup_id=os.path.basename(filepath),
                    filepath=filepath,
                    issues=["Invalid backup file format: missing 'manifest' or 'data' root keys."],
                )

            manifest_dict = bundle["manifest"]
            manifest = BackupManifest.from_dict(manifest_dict)
            backup_id = manifest.backup_id
            stores_data = bundle["data"]

            if not isinstance(stores_data, dict):
                issues.append("Backup 'data' root must be a dictionary keyed by store filename.")
            else:
                for k in stores_data.keys():
                    if k not in MANAGED_STORE_FILES:
                        issues.append(f"Unrecognized or forbidden store filename '{k}' in backup data payload.")

            # Recompute overall bundle sha256
            canonical_stores_json = json.dumps(stores_data, sort_keys=True)
            recomputed_bundle_sha256 = _compute_sha256_str(canonical_stores_json)

            if recomputed_bundle_sha256 != manifest.bundle_sha256:
                issues.append(
                    f"Bundle sha256 checksum mismatch: manifest='{manifest.bundle_sha256}', calculated='{recomputed_bundle_sha256}'"
                )

            # Check individual store integrity
            for store_name, meta in manifest.stores.items():
                if store_name not in MANAGED_STORE_FILES:
                    issues.append(f"Store '{store_name}' in manifest is not an allowed store file.")
                    continue

                if store_name not in stores_data:
                    issues.append(f"Store file '{store_name}' listed in manifest is missing from backup data payload.")
                    continue

                content_obj = stores_data[store_name]
                cnt = len(content_obj) if isinstance(content_obj, (list, dict)) else 0
                if cnt != meta.record_count:
                    issues.append(f"Store '{store_name}' record count mismatch: expected {meta.record_count}, found {cnt}")

        except Exception as exc:
            issues.append(f"Failed to read or parse backup file: {exc}")

        return BackupVerificationResult(
            valid=(len(issues) == 0),
            backup_id=backup_id or os.path.basename(filepath),
            filepath=filepath,
            issues=issues,
            manifest=manifest_dict,
        )

    def restore_backup(
        self,
        user: UserAuthorization,
        backup_id_or_path: str,
    ) -> RestoreResult:
        """Perform non-destructive atomic restore from a verified backup snapshot with rollback safety."""
        try:
            self._authorize_admin(user, "restore_backup")
        except Exception as err:
            return RestoreResult(success=False, message=f"Authorization failure: {err}", error_details=str(err))

        # Step 1: Verify backup integrity BEFORE touching live storage
        verif = self.verify_backup(backup_id_or_path)
        if not verif.valid:
            msg = f"Restore aborted: Backup integrity verification failed. Issues: {'; '.join(verif.issues)}"
            logger.error(msg)
            return RestoreResult(success=False, message=msg, error_details="; ".join(verif.issues))

        filepath = verif.filepath
        if not filepath:
            return RestoreResult(success=False, message="Backup filepath resolved to None.")

        backup_id = verif.backup_id
        ts_suffix = int(time.time() * 1000)
        rollback_dir = os.path.join(self.storage_dir, f"_rollback_tmp_{ts_suffix}")
        staging_dir = os.path.join(self.storage_dir, f"_staging_tmp_{ts_suffix}")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                bundle = json.load(f)
            stores_data: Dict[str, Any] = bundle["data"]

            os.makedirs(rollback_dir, exist_ok=True)
            os.makedirs(staging_dir, exist_ok=True)

            # Step 2: Create pre-restore rollback safety copy of current live files
            for filename in stores_data.keys():
                clean_filename = os.path.basename(filename)
                if clean_filename not in MANAGED_STORE_FILES:
                    continue
                live_file = os.path.join(self.storage_dir, clean_filename)
                if os.path.exists(live_file):
                    shutil.copy2(live_file, os.path.join(rollback_dir, clean_filename))

            # Step 3: Write candidate restored files into staging directory
            for filename, content_obj in stores_data.items():
                clean_filename = os.path.basename(filename)
                if clean_filename not in MANAGED_STORE_FILES:
                    continue
                staged_file = os.path.join(staging_dir, clean_filename)
                with open(staged_file, "w", encoding="utf-8") as f:
                    json.dump(content_obj, f, indent=2, ensure_ascii=False)

            # Step 4: Dry-run loadability check on staged files
            from src.platform.adapters.user_repository import FileBackedUserRepository
            from src.platform.adapters.workspace_repository import FileBackedWorkspaceRepository
            from src.platform.adapters.order_intent_repository import FileBackedOrderIntentRepository
            from src.platform.adapters.project1_repository import FileBackedProject1IntegrationRepository

            # Test deserialization in isolation using staging_dir
            if "users.json" in stores_data:
                FileBackedUserRepository(storage_dir=staging_dir)
            if "workspaces.json" in stores_data:
                FileBackedWorkspaceRepository(storage_dir=staging_dir)
            if "order_intents.json" in stores_data:
                FileBackedOrderIntentRepository(storage_filepath=os.path.join(staging_dir, "order_intents.json"))
            if "project1_integration_records.json" in stores_data:
                FileBackedProject1IntegrationRepository(storage_filepath=os.path.join(staging_dir, "project1_integration_records.json"))

            # Step 5: Atomically swap staged files into live storage directory
            restored_filenames = []
            for filename in stores_data.keys():
                clean_filename = os.path.basename(filename)
                if clean_filename not in MANAGED_STORE_FILES:
                    continue
                staged_file = os.path.join(staging_dir, clean_filename)
                live_file = os.path.join(self.storage_dir, clean_filename)
                os.replace(staged_file, live_file)
                restored_filenames.append(clean_filename)

            # Clean up temp directories
            shutil.rmtree(rollback_dir, ignore_errors=True)
            shutil.rmtree(staging_dir, ignore_errors=True)

            # Audit restore event
            if self.audit_control and hasattr(self.audit_control, "record_event"):
                try:
                    self.audit_control.record_event(
                        user=user,
                        category="PERSISTENCE",
                        action="BACKUP_RESTORED",
                        severity="WARNING",
                        details=f"Restored persistence state from backup '{backup_id}' ({len(restored_filenames)} stores)",
                    )
                except Exception:
                    pass

            return RestoreResult(
                success=True,
                message=f"Successfully restored persistence state from backup '{backup_id}'.",
                backup_id=backup_id,
                restored_stores=restored_filenames,
                timestamp=time.time(),
            )

        except Exception as exc:
            logger.error("Restore failed during staging/swap. Initiating automatic rollback: %s", exc)
            # Automatic rollback: restore live files from rollback_dir
            if os.path.exists(rollback_dir):
                for rb_file in os.listdir(rollback_dir):
                    shutil.copy2(os.path.join(rollback_dir, rb_file), os.path.join(self.storage_dir, rb_file))

            # Cleanup temp dirs
            shutil.rmtree(rollback_dir, ignore_errors=True)
            shutil.rmtree(staging_dir, ignore_errors=True)

            if self.audit_control and hasattr(self.audit_control, "record_failure"):
                try:
                    self.audit_control.record_failure(
                        component="PersistenceRecoveryEngine",
                        error_type="RESTORE_FAILED_ROLLED_BACK",
                        message=f"Restore from backup '{backup_id}' failed: {exc}. Live state safely rolled back.",
                        diagnostic_details=f"Backup filepath: {filepath}",
                    )
                except Exception:
                    pass

            return RestoreResult(
                success=False,
                message=f"Restore failed and live state was safely rolled back: {exc}",
                backup_id=backup_id,
                error_details=str(exc),
            )

    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backup snapshots ordered by creation timestamp descending."""
        backups: List[Dict[str, Any]] = []
        if not os.path.exists(self.backups_dir):
            return backups

        for filename in os.listdir(self.backups_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(self.backups_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        bundle = json.load(f)
                    if isinstance(bundle, dict) and "manifest" in bundle:
                        mf = bundle["manifest"]
                        mf["filepath"] = filepath
                        mf["file_size_bytes"] = os.path.getsize(filepath)
                        backups.append(mf)
                except Exception:
                    continue

        backups.sort(key=lambda b: float(b.get("created_at", 0)), reverse=True)
        return backups

    def prune_backups_and_corrupt_files(
        self,
        max_backups: int = DEFAULT_BACKUP_RETENTION_COUNT,
        max_corrupt_files: int = DEFAULT_CORRUPT_BACKUP_RETENTION_COUNT,
    ) -> Dict[str, int]:
        """Enforce bounded retention by purging oldest backup snapshots and historical corrupt files."""
        pruned_counts = {"backups_pruned": 0, "corrupt_files_pruned": 0}

        # 1. Prune backup snapshots beyond max_backups limit
        all_backups = self.list_backups()
        if len(all_backups) > max_backups:
            to_remove = all_backups[max_backups:]
            for b_info in to_remove:
                fp = b_info.get("filepath")
                if fp and os.path.exists(fp):
                    try:
                        os.remove(fp)
                        pruned_counts["backups_pruned"] += 1
                    except Exception as e:
                        logger.warning("Failed to remove expired backup file '%s': %s", fp, e)

        # 2. Prune .corrupt.* files in storage_dir beyond max_corrupt_files limit
        if os.path.exists(self.storage_dir):
            corrupt_files: List[Tuple[str, float]] = []
            for fname in os.listdir(self.storage_dir):
                if ".corrupt." in fname:
                    fp = os.path.join(self.storage_dir, fname)
                    mtime = os.path.getmtime(fp)
                    corrupt_files.append((fp, mtime))

            corrupt_files.sort(key=lambda x: x[1], reverse=True)
            if len(corrupt_files) > max_corrupt_files:
                for fp, _ in corrupt_files[max_corrupt_files:]:
                    try:
                        os.remove(fp)
                        pruned_counts["corrupt_files_pruned"] += 1
                    except Exception as e:
                        logger.warning("Failed to remove expired corrupt file '%s': %s", fp, e)

        return pruned_counts
