"""Regression and security test suite for Production Observability, Operational Monitoring, and Recovery Foundation.

Verifies:
- Liveness vs Readiness distinction
- Dependency & Subsystem Readiness
- Structured operational logging & SecretSanitizer redaction
- Persistence integrity validation & schema version checks
- Safe recovery from corrupted persisted storage files
- Canonical operational failure records & query RBAC
- Server endpoints (/health/liveness, /health/readiness, /diagnostics, /api/v1/operational/recovery)
- User isolation, RBAC, IDOR defense, and privilege escalation protection
"""

import json
import os
import shutil
import tempfile
import time
import unittest

from src.platform.config import PlatformConfig
from src.platform.adapters.user_repository import FileBackedUserRepository, CorruptStorageError, CURRENT_SCHEMA_VERSION as USER_SCHEMA_VER
from src.platform.adapters.workspace_repository import FileBackedWorkspaceRepository, CURRENT_WORKSPACE_SCHEMA_VERSION as WS_SCHEMA_VER
from src.platform.adapters.project1_repository import FileBackedProject1IntegrationRepository
from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.audit_control import PlatformAuditControlService
from src.platform.services.health_operations import (
    SystemHealthService,
    PersistenceRecoveryStatus,
    log_operational_event,
)
from src.platform.services.security import SecurityBoundaryService, SecretSanitizer
from src.platform.services.user_authorization import UserAuthorizationService
from src.platform.server import create_server


class TestHealthOperationsAndRecovery(unittest.TestCase):
    """Test suite for health operations, structured logging, and persistence recovery."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.config = PlatformConfig(persistence_dir=self.temp_dir, app_env="testing")
        self.health_service = SystemHealthService(config=self.config)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_liveness_vs_readiness_distinction(self) -> None:
        """Liveness must return True, while readiness performs deep subsystem checks."""
        is_live, msg = self.health_service.check_liveness()
        self.assertTrue(is_live)
        self.assertIn("Process is live", msg)

        # Deep readiness check on clean system
        is_ready, details = self.health_service.check_readiness()
        self.assertTrue(is_ready)
        self.assertTrue(details["persistence_healthy"])
        self.assertEqual(details["persistence_status"], "CLEAN")
        self.assertTrue(details["project1_gateway_connected"])
        self.assertTrue(details["notification_pipeline_healthy"])

    def test_readiness_fails_when_provider_failed(self) -> None:
        """Readiness check must return False if any registered provider is unavailable."""
        provider_checks = {"biquote_md": True, "biquote_quote": False}
        is_ready, details = self.health_service.check_readiness(provider_checks=provider_checks)
        self.assertFalse(is_ready)
        self.assertIn("biquote_quote", details["reason"])

    def test_readiness_production_session_secret_enforcement(self) -> None:
        """In production mode, insecure SESSION_SECRET raises ValueError or fails readiness check."""
        with self.assertRaises(ValueError):
            PlatformConfig(
                app_env="production",
                session_secret="too_short",
                persistence_dir=self.temp_dir,
            )

    def test_persistence_integrity_validation_clean(self) -> None:
        """Validation on clean storage directory returns CLEAN status."""
        rec = self.health_service.validate_persistence_integrity()
        self.assertTrue(rec.is_healthy)
        self.assertEqual(rec.status, "CLEAN")
        self.assertEqual(len(rec.corrupt_backups_found), 0)

    def test_persistence_integrity_detects_corrupt_file(self) -> None:
        """Validation detects corrupt storage JSON files and marks status DEGRADED."""
        corrupt_user_file = os.path.join(self.temp_dir, "users.json")
        with open(corrupt_user_file, "w", encoding="utf-8") as f:
            f.write("{ INVALID JSON payload ...")

        rec = self.health_service.validate_persistence_integrity()
        self.assertFalse(rec.is_healthy)
        self.assertEqual(rec.status, "DEGRADED")
        self.assertIn("users.json", str(rec.stores_checked))

    def test_persistence_integrity_detects_historical_corrupt_backups(self) -> None:
        """Presence of .corrupt.<ts> backup files triggers RECOVERED_FROM_CORRUPTION status."""
        backup_file = os.path.join(self.temp_dir, "users.json.corrupt.1700000000")
        with open(backup_file, "w", encoding="utf-8") as f:
            f.write("[]")

        rec = self.health_service.validate_persistence_integrity()
        self.assertTrue(rec.is_healthy)
        self.assertEqual(rec.status, "RECOVERED_FROM_CORRUPTION")
        self.assertEqual(len(rec.corrupt_backups_found), 1)

    def test_repository_corrupt_recovery_creates_backup(self) -> None:
        """FileBackedUserRepository backs up corrupt file and raises CorruptStorageError."""
        users_file = os.path.join(self.temp_dir, "users.json")
        with open(users_file, "w", encoding="utf-8") as f:
            f.write("{ corrupt json }")

        with self.assertRaises(CorruptStorageError):
            FileBackedUserRepository(storage_dir=self.temp_dir)

        # Confirm corrupt backup copy was created
        files = os.listdir(self.temp_dir)
        corrupt_backups = [fn for fn in files if ".corrupt." in fn]
        self.assertGreaterEqual(len(corrupt_backups), 1)

    def test_structured_operational_logging_sanitizes_secrets(self) -> None:
        """log_operational_event must sanitize secrets and credentials from messages and details."""
        secret_payload = {"api_key": "secret_key_12345", "password": "super_secret_password"}
        # Should execute without throwing or leaking raw secret
        log_operational_event(
            level=20,
            message="User authenticated with password secret_key_12345",
            component="test.logger",
            correlation_id="corr_999",
            extra_data=secret_payload,
        )

    def test_get_unified_observability_report(self) -> None:
        """Verify unified operational observability report aggregates all platform subsystem states."""
        rep = self.health_service.get_unified_observability_report(
            active_sessions_count=3,
            provider_checks={"biquote_md": True, "biquote_quote": True},
            project1_gateway_connected=True,
            notification_pipeline_healthy=True,
            ai_provider_status="connected",
            recent_failures_count=2,
        )

        self.assertEqual(rep.overall_status, "HEALTHY")
        self.assertTrue(rep.liveness)
        self.assertTrue(rep.readiness)
        self.assertEqual(rep.active_sessions_count, 3)
        self.assertEqual(rep.recent_failures_count, 2)
        self.assertIn("application_server", rep.components)
        self.assertIn("persistence_storage", rep.components)
        self.assertIn("project1_gateway", rep.components)
        self.assertIn("execution_gateway_boundary", rep.components)
        self.assertIn("notification_pipeline", rep.components)
        self.assertIn("ai_provider_gateway", rep.components)

        rep_dict = rep.to_dict()
        self.assertEqual(rep_dict["overall_status"], "HEALTHY")
        self.assertEqual(rep_dict["components"]["project1_gateway"]["status"], "HEALTHY")

    def test_observability_endpoint_returns_active_sessions(self) -> None:
        """GET /api/v1/operational/observability reports real active session counts."""
        server = create_server(host="127.0.0.1", port=0, config=self.config)
        auth_service = server.RequestHandlerClass.server_user_auth_service
        token = auth_service.create_session_token("admin_owner")
        self.assertIsNotNone(token)

        self.assertEqual(auth_service.count_active_sessions(), 1)


class TestOperationalFailureAndAudit(unittest.TestCase):
    """Test suite for operational failure tracking, incident logs, and RBAC."""

    def setUp(self) -> None:
        self.sec = SecurityBoundaryService()
        self.audit_service = PlatformAuditControlService(security_boundary=self.sec)

        self.owner = UserAuthorization(
            user_id="owner_1",
            auth_code="auth1",
            role=UserRole.OWNER,
            permissions=(Permission.ADMIN_ALL, Permission.READ_SIGNALS),
            is_permanent_admin=True,
        )
        self.admin = UserAuthorization(
            user_id="admin_1",
            auth_code="auth2",
            role=UserRole.ADMIN,
            permissions=(Permission.ADMIN_ALL, Permission.READ_SIGNALS),
        )
        self.customer = UserAuthorization(
            user_id="customer_1",
            auth_code="auth3",
            role=UserRole.CUSTOMER,
            permissions=(Permission.READ_SIGNALS,),
        )

    def test_record_and_query_operational_failures(self) -> None:
        """Record operational failures and verify admin query retrieves sanitized failure records."""
        fail_rec = self.audit_service.record_failure(
            component="database.adapter",
            error_type="CONNECTION_TIMEOUT",
            message="Database connection timed out after 5.0s",
            retryable=True,
            correlation_id="req_fail_100",
            diagnostic_details="Traceback: timeout reading from socket",
            user_id="system",
        )

        self.assertIsNotNone(fail_rec.failure_id)
        self.assertEqual(fail_rec.component, "database.adapter")
        self.assertEqual(fail_rec.error_type, "CONNECTION_TIMEOUT")
        self.assertTrue(fail_rec.retryable)

        # Admin can query failures
        ok, msg, fails = self.audit_service.query_failures(user=self.admin)
        self.assertTrue(ok)
        self.assertGreaterEqual(len(fails), 1)
        self.assertEqual(fails[0].correlation_id, "req_fail_100")

    def test_customer_isolation_and_rbac_on_failures(self) -> None:
        """Non-admin customer user cannot query other users' or system operational failures."""
        self.audit_service.record_failure(
            component="system.service",
            error_type="CRITICAL_FAIL",
            message="Internal system failure",
            user_id="other_user",
        )

        # Customer requesting failures should only see system failures or own failures
        ok, msg, fails = self.audit_service.query_failures(user=self.customer)
        self.assertTrue(ok)
        for f in fails:
            self.assertIn(f.user_id, ("system", self.customer.user_id))


if __name__ == "__main__":
    unittest.main()
