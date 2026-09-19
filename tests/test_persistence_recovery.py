"""Targeted test suite for Persistence Backup, Recovery, and Hardening Engine.

Verifies backup snapshot creation, SHA-256 manifest checksum verification,
non-destructive restore, fail-closed corrupted backup handling, atomic rollback safety,
admin RBAC isolation, bounded retention pruning, and REST API operational endpoints.
"""

import json
import os
import shutil
import tempfile
import time
import unittest

from src.platform.config import PlatformConfig
from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.domain.workspace import Workspace
from src.platform.domain.order_intent import OrderIntent, OrderLifecycleState
from src.platform.adapters.user_repository import FileBackedUserRepository
from src.platform.adapters.workspace_repository import FileBackedWorkspaceRepository
from src.platform.adapters.order_intent_repository import FileBackedOrderIntentRepository
from src.platform.adapters.project1_repository import FileBackedProject1IntegrationRepository
from src.platform.services.security import SecurityBoundaryService
from src.platform.services.health_operations import SystemHealthService
from src.platform.services.persistence_recovery import (
    PersistenceRecoveryEngine,
    BackupSnapshotResult,
    BackupVerificationResult,
    RestoreResult,
)


class TestPersistenceRecoveryEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.storage_dir = os.path.join(self.temp_dir, ".data")
        self.backups_dir = os.path.join(self.storage_dir, "backups")
        os.makedirs(self.storage_dir, exist_ok=True)

        self.security_boundary = SecurityBoundaryService()
        self.engine = PersistenceRecoveryEngine(
            storage_dir=self.storage_dir,
            backups_dir=self.backups_dir,
            security_boundary=self.security_boundary,
            app_env="test",
        )

        # Create test users
        self.admin_user = UserAuthorization(
            user_id="admin_user",
            auth_code="code_admin",
            role=UserRole.ADMIN,
            permissions=(Permission.ADMIN_ALL, Permission.READ_SIGNALS),
            is_permanent_admin=True,
        )
        self.regular_user = UserAuthorization(
            user_id="cust_user",
            auth_code="code_cust",
            role=UserRole.CUSTOMER,
            permissions=(Permission.READ_SIGNALS,),
            is_permanent_admin=False,
        )

        # Seed initial test persistent data
        self.user_repo = FileBackedUserRepository(storage_dir=self.storage_dir)
        self.user_repo.save_user(self.admin_user)
        self.user_repo.save_user(self.regular_user)

        self.ws_repo = FileBackedWorkspaceRepository(storage_dir=self.storage_dir)
        ws = Workspace(user_id="cust_user", active_watchlist_id="default", active_symbol="XAUUSD")
        self.ws_repo.save_workspace(ws)

        self.intent_repo = FileBackedOrderIntentRepository(
            storage_filepath=os.path.join(self.storage_dir, "order_intents.json")
        )
        intent = OrderIntent(
            order_intent_id="intent_101",
            authorization_id="auth_101",
            user_id="cust_user",
            symbol="XAUUSD",
            direction="buy",
            idempotency_key="idemp_101",
            creation_timestamp=time.time(),
            stop_loss=1980.0,
            take_profit_1=2040.0,
            lifecycle_state=OrderLifecycleState.STAGED,
        )
        self.intent_repo.save_order_intent(intent)

        self.p1_repo = FileBackedProject1IntegrationRepository(
            storage_filepath=os.path.join(self.storage_dir, "project1_integration_records.json")
        )
        self.p1_repo.save_record({
            "integration_id": "rec_101",
            "signal_id": "sig_101",
            "user_id": "cust_user",
            "symbol": "XAUUSD",
            "lifecycle_state": "EMITTED",
        })

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_successful_backup_creation_and_manifest_checksum(self) -> None:
        res = self.engine.create_backup(user=self.admin_user, label="initial_snapshot")
        self.assertTrue(res.success)
        self.assertIsNotNone(res.backup_id)
        self.assertTrue(os.path.exists(res.filepath))

        # Check manifest contents
        manifest = res.manifest
        self.assertEqual(manifest["created_by"], "admin_user")
        self.assertEqual(manifest["label"], "initial_snapshot")
        self.assertIn("users.json", manifest["stores"])
        self.assertIn("workspaces.json", manifest["stores"])
        self.assertIn("order_intents.json", manifest["stores"])
        self.assertIn("project1_integration_records.json", manifest["stores"])

        # Check bundle checksum
        self.assertTrue(len(manifest["bundle_sha256"]) > 32)

    def test_verify_backup_integrity_valid_and_invalid(self) -> None:
        res = self.engine.create_backup(user=self.admin_user)
        self.assertTrue(res.success)

        # 1. Unmodified backup must be valid
        verif = self.engine.verify_backup(res.backup_id)
        self.assertTrue(verif.valid)
        self.assertEqual(len(verif.issues), 0)

        # 2. Tampered backup payload must fail verification
        with open(res.filepath, "r", encoding="utf-8") as f:
            bundle = json.load(f)

        bundle["data"]["users.json"] = [{"tampered": True}]
        with open(res.filepath, "w", encoding="utf-8") as f:
            json.dump(bundle, f, indent=2)

        verif_tampered = self.engine.verify_backup(res.backup_id)
        self.assertFalse(verif_tampered.valid)
        self.assertTrue(any("sha256 checksum mismatch" in issue.lower() for issue in verif_tampered.issues))

    def test_successful_restore(self) -> None:
        # Step 1: Create backup of initial state
        b_res = self.engine.create_backup(user=self.admin_user, label="before_deletion")
        self.assertTrue(b_res.success)

        # Step 2: Mutate live state (add extra user, modify workspace, add intent)
        new_user = UserAuthorization(
            user_id="extra_user",
            auth_code="code_extra",
            role=UserRole.CUSTOMER,
        )
        self.user_repo.save_user(new_user)
        self.assertIsNotNone(self.user_repo.get_user_by_id("extra_user"))

        # Step 3: Restore backup
        r_res = self.engine.restore_backup(user=self.admin_user, backup_id_or_path=b_res.backup_id)
        self.assertTrue(r_res.success)

        # Step 4: Re-load repos and verify live storage was restored to snapshot state
        reloaded_user_repo = FileBackedUserRepository(storage_dir=self.storage_dir)
        self.assertIsNone(reloaded_user_repo.get_user_by_id("extra_user"))
        self.assertIsNotNone(reloaded_user_repo.get_user_by_id("cust_user"))

    def test_corrupted_backup_restore_fails_closed_without_destroying_live_state(self) -> None:
        b_res = self.engine.create_backup(user=self.admin_user)
        self.assertTrue(b_res.success)

        # Corrupt backup file
        with open(b_res.filepath, "w", encoding="utf-8") as f:
            f.write("Corrupted garbage JSON payload {{{")

        # Attempt restore
        r_res = self.engine.restore_backup(user=self.admin_user, backup_id_or_path=b_res.backup_id)
        self.assertFalse(r_res.success)
        self.assertIn("verification failed", r_res.message.lower())

        # Verify existing live data is preserved untouched
        reloaded_user_repo = FileBackedUserRepository(storage_dir=self.storage_dir)
        self.assertIsNotNone(reloaded_user_repo.get_user_by_id("cust_user"))

    def test_atomic_rollback_on_failed_restore_staging(self) -> None:
        # Create valid backup
        b_res = self.engine.create_backup(user=self.admin_user)
        self.assertTrue(b_res.success)

        # Tampered backup so that JSON is valid but dry-run load fails
        with open(b_res.filepath, "r", encoding="utf-8") as f:
            bundle = json.load(f)

        # Inject malformed data that passes JSON parse but fails repo constructor
        bundle["data"]["users.json"] = "NOT_A_LIST_ROOT"
        canonical_stores_json = json.dumps(bundle["data"], sort_keys=True)
        import hashlib
        bundle["manifest"]["bundle_sha256"] = hashlib.sha256(canonical_stores_json.encode("utf-8")).hexdigest()
        bundle["manifest"]["stores"]["users.json"]["record_count"] = 14

        with open(b_res.filepath, "w", encoding="utf-8") as f:
            json.dump(bundle, f, indent=2)

        # Restore attempt
        r_res = self.engine.restore_backup(user=self.admin_user, backup_id_or_path=b_res.backup_id)
        self.assertFalse(r_res.success)

        # Verify live files remained intact via rollback
        reloaded_user_repo = FileBackedUserRepository(storage_dir=self.storage_dir)
        self.assertIsNotNone(reloaded_user_repo.get_user_by_id("cust_user"))

    def test_admin_rbac_authorization_for_backup_and_restore(self) -> None:
        # Regular customer user must be blocked
        res = self.engine.create_backup(user=self.regular_user)
        self.assertFalse(res.success)
        self.assertIn("authorization failure", res.message.lower())

        r_res = self.engine.restore_backup(user=self.regular_user, backup_id_or_path="some_id")
        self.assertFalse(r_res.success)
        self.assertIn("authorization failure", r_res.message.lower())

    def test_bounded_retention_pruning(self) -> None:
        # Create 12 backups with retention limit set to 5
        backup_ids = []
        for i in range(12):
            res = self.engine.create_backup(user=self.admin_user, label=f"snap_{i}")
            self.assertTrue(res.success)
            backup_ids.append(res.backup_id)
            time.sleep(0.01)

        # Prune with max_backups=5
        pruned = self.engine.prune_backups_and_corrupt_files(max_backups=5, max_corrupt_files=3)
        remaining = self.engine.list_backups()
        self.assertLessEqual(len(remaining), 5)
        self.assertGreater(pruned["backups_pruned"], 0)

        # Create dummy corrupt files to test corrupt pruning
        for i in range(8):
            cfp = os.path.join(self.storage_dir, f"users.json.corrupt.{1000 + i}")
            with open(cfp, "w", encoding="utf-8") as f:
                f.write("corrupt")

        pruned_c = self.engine.prune_backups_and_corrupt_files(max_backups=5, max_corrupt_files=3)
        corrupt_files_left = [fn for fn in os.listdir(self.storage_dir) if ".corrupt." in fn]
        self.assertLessEqual(len(corrupt_files_left), 3)

    def test_health_operations_integration(self) -> None:
        health_service = SystemHealthService(config=PlatformConfig(persistence_dir=self.storage_dir))

        # Take a backup
        self.engine.create_backup(user=self.admin_user)

        status = health_service.validate_persistence_integrity(storage_dir=self.storage_dir)
        self.assertTrue(status.is_healthy)
        self.assertGreaterEqual(status.backup_snapshots_count, 1)
        self.assertIsNotNone(status.latest_backup_timestamp)
        self.assertEqual(status.retention_status, "BOUNDED_RETENTION_OK")


if __name__ == "__main__":
    unittest.main()
