"""System health, readiness, and operational diagnostics service (Part 21: Operational Resilience & Health Control).

Provides explicit distinction between liveness (process alive) and readiness (dependencies ready & configured),
application health status, safe operational diagnostics, correlation request tracking, and sanitized logging.
"""

from dataclasses import dataclass, field
import json
import logging
import os
import secrets
import time
from typing import Any, Dict, List, Optional, Tuple

from src.platform.config import PlatformConfig
from src.platform.services.security import SecretSanitizer

logger = logging.getLogger("platform.health")


@dataclass
class PersistenceRecoveryStatus:
    """Status report for persistence integrity, schema validation, and storage recovery."""

    status: str  # "CLEAN", "RECOVERED_FROM_CORRUPTION", "DEGRADED", "UNAVAILABLE"
    storage_dir: str
    stores_checked: Dict[str, Any]
    corrupt_backups_found: List[str]
    is_healthy: bool
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "storage_dir": self.storage_dir,
            "stores_checked": self.stores_checked,
            "corrupt_backups_found": self.corrupt_backups_found,
            "is_healthy": self.is_healthy,
            "message": self.message,
        }


@dataclass(frozen=True)
class OperationalDiagnostics:
    """Sanitized operational diagnostics report."""

    timestamp: float
    liveness: bool
    readiness: bool
    app_env: str
    active_sessions_count: int
    system_status: str
    persistence_recovery: Dict[str, Any]
    diagnostics_summary: Dict[str, Any]


def log_operational_event(
    level: int,
    message: str,
    component: str,
    correlation_id: Optional[str] = None,
    extra_data: Optional[Dict[str, Any]] = None,
) -> None:
    """Safely format and log a structured, secret-sanitized operational log event."""
    sanitized_msg = SecretSanitizer.sanitize_string(message)
    sanitized_extra = SecretSanitizer.sanitize_data(extra_data or {})
    corr_part = f" [corr_id={correlation_id}]" if correlation_id else ""
    extra_part = f" | details={json.dumps(sanitized_extra)}" if extra_data else ""

    formatted = f"[{component}]{corr_part} {sanitized_msg}{extra_part}"
    logger.log(level, formatted)


class SystemHealthService:
    """Service evaluating application liveness, readiness, dependency status, and correlation tracking."""

    def __init__(
        self,
        config: Optional[PlatformConfig] = None,
    ) -> None:
        self.config = config or PlatformConfig()
        self._startup_time = time.time()

    def generate_correlation_id(self) -> str:
        """Generate a secure request correlation identifier."""
        return f"req_{secrets.token_hex(12)}"

    def check_liveness(self) -> Tuple[bool, str]:
        """Liveness check: returns True if process is alive and responsive."""
        return True, "Process is live"

    def validate_persistence_integrity(
        self, storage_dir: Optional[str] = None
    ) -> PersistenceRecoveryStatus:
        """Validate integrity and schema versions of all file-backed persistence stores."""
        target_dir = storage_dir or self.config.persistence_dir
        stores_info: Dict[str, Any] = {}
        corrupt_backups: List[str] = []
        is_healthy = True
        recovered_mode = False
        issues: List[str] = []

        if not os.path.exists(target_dir):
            try:
                os.makedirs(target_dir, exist_ok=True)
            except Exception as e:
                return PersistenceRecoveryStatus(
                    status="UNAVAILABLE",
                    storage_dir=target_dir,
                    stores_checked={},
                    corrupt_backups_found=[],
                    is_healthy=False,
                    message=f"Cannot create persistence storage directory '{target_dir}': {e}",
                )

        # Scan for existing corrupt backup files
        try:
            for filename in os.listdir(target_dir):
                if ".corrupt." in filename:
                    corrupt_backups.append(os.path.join(target_dir, filename))
                    recovered_mode = True
        except Exception as e:
            issues.append(f"Failed to scan directory '{target_dir}': {e}")

        files_to_check = {
            "users.json": {"expected_schema": 2, "root_type": list},
            "sessions.json": {"expected_schema": 2, "root_type": dict},
            "workspaces.json": {"expected_schema": 1, "root_type": dict},
            "project1_integration_records.json": {"expected_schema": 1, "root_type": (dict, list)},
        }

        for filename, spec in files_to_check.items():
            filepath = os.path.join(target_dir, filename)
            if not os.path.exists(filepath):
                # Also check data/ fallback for project1_integration_records.json
                if filename == "project1_integration_records.json" and os.path.exists("data/project1_integration_records.json"):
                    filepath = "data/project1_integration_records.json"
                else:
                    stores_info[filename] = {"exists": False, "status": "NOT_CREATED_YET"}
                    continue

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                expected_type = spec["root_type"]
                if not isinstance(data, expected_type):
                    is_healthy = False
                    issues.append(f"Store '{filename}' root is not of expected type {expected_type}")
                    stores_info[filename] = {"exists": True, "status": "INVALID_ROOT_TYPE"}
                else:
                    record_count = len(data) if isinstance(data, (list, dict)) else 0
                    schema_ver = spec["expected_schema"]
                    if isinstance(data, dict) and "schema_version" in data:
                        schema_ver = data["schema_version"]
                    elif isinstance(data, dict) and "_schema_version" in data:
                        schema_ver = data["_schema_version"]

                    stores_info[filename] = {
                        "exists": True,
                        "status": "VALID",
                        "record_count": record_count,
                        "schema_version": schema_ver,
                    }
            except Exception as err:
                is_healthy = False
                issues.append(f"Store '{filename}' corrupted or unparseable: {err}")
                stores_info[filename] = {"exists": True, "status": "CORRUPTED", "error": str(err)}

        if not is_healthy:
            status = "DEGRADED"
            msg = f"Persistence store issues detected: {'; '.join(issues)}"
        elif recovered_mode:
            status = "RECOVERED_FROM_CORRUPTION"
            msg = f"Storage operational ({len(corrupt_backups)} historical corrupt backup file(s) found)."
        else:
            status = "CLEAN"
            msg = "All persistence stores valid and healthy."

        return PersistenceRecoveryStatus(
            status=status,
            storage_dir=target_dir,
            stores_checked=stores_info,
            corrupt_backups_found=corrupt_backups,
            is_healthy=is_healthy,
            message=msg,
        )

    def check_readiness(
        self,
        active_sessions_count: int = 0,
        provider_checks: Optional[Dict[str, bool]] = None,
        persistence_healthy: bool = True,
        project1_gateway_connected: bool = True,
        notification_pipeline_healthy: bool = True,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Deep readiness check: evaluates config validity, storage integrity, providers, and integration gateways.

        Explicitly classifies readiness status states across subsystem components:
        - HEALTHY: Subsystem is fully operational and configured.
        - DEGRADED: Non-critical subsystem issue present, but overall platform remains functional.
        - UNAVAILABLE: Critical subsystem component failure rendering service unusable.
        - NOT_CONFIGURED: Optional integration or credential not provisioned.
        """
        persistence_status = self.validate_persistence_integrity()

        # Classify persistence state
        if not (persistence_healthy and persistence_status.is_healthy):
            persistence_state = "UNAVAILABLE" if persistence_status.status == "UNAVAILABLE" else "DEGRADED"
        else:
            persistence_state = "HEALTHY"

        # Classify provider states
        providers_dict = provider_checks or {}
        if not providers_dict:
            providers_state = "NOT_CONFIGURED"
        elif all(providers_dict.values()):
            providers_state = "HEALTHY"
        elif any(providers_dict.values()):
            providers_state = "DEGRADED"
        else:
            providers_state = "UNAVAILABLE"

        # Classify Project 1 Gateway state
        project1_state = "HEALTHY" if project1_gateway_connected else "NOT_CONFIGURED"

        # Classify Notification Pipeline state
        notification_state = "HEALTHY" if notification_pipeline_healthy else "DEGRADED"

        # Determine overall readiness status
        if persistence_state == "UNAVAILABLE":
            overall_status = "UNAVAILABLE"
        elif persistence_state == "DEGRADED" or providers_state in ("DEGRADED", "UNAVAILABLE") or notification_state == "DEGRADED":
            overall_status = "DEGRADED"
        else:
            overall_status = "HEALTHY"

        details: Dict[str, Any] = {
            "overall_status": overall_status,
            "config_valid": True,
            "app_env": self.config.app_env,
            "is_production": self.config.is_production,
            "active_sessions": active_sessions_count,
            "providers": providers_dict,
            "subsystem_states": {
                "persistence": persistence_state,
                "providers": providers_state,
                "project1_gateway": project1_state,
                "notification_pipeline": notification_state,
            },
            "persistence_healthy": persistence_healthy and persistence_status.is_healthy,
            "persistence_status": persistence_status.status,
            "project1_gateway_connected": project1_gateway_connected,
            "notification_pipeline_healthy": notification_pipeline_healthy,
        }

        if persistence_state == "UNAVAILABLE":
            details["reason"] = f"Persistence storage unavailable: {persistence_status.message}"
            return False, details

        # Validate production configuration if in production mode
        if self.config.is_production:
            if not self.config.session_secret or len(self.config.session_secret) < 32:
                details["config_valid"] = False
                details["overall_status"] = "UNAVAILABLE"
                details["reason"] = "Insecure SESSION_SECRET in production"
                return False, details

        # Check if any provider is failing
        if provider_checks:
            for p_name, is_ok in provider_checks.items():
                if not is_ok:
                    details["reason"] = f"Provider '{p_name}' unavailable"
                    return False, details

        is_ready = overall_status in ("HEALTHY", "DEGRADED")
        return is_ready, details

    def get_operational_diagnostics(
        self,
        active_sessions_count: int = 0,
        provider_checks: Optional[Dict[str, bool]] = None,
        persistence_healthy: bool = True,
        project1_gateway_connected: bool = True,
        notification_pipeline_healthy: bool = True,
    ) -> OperationalDiagnostics:
        """Return comprehensive sanitized operational diagnostics report."""
        is_live, _ = self.check_liveness()
        persistence_recovery = self.validate_persistence_integrity()
        is_ready, readiness_details = self.check_readiness(
            active_sessions_count=active_sessions_count,
            provider_checks=provider_checks,
            persistence_healthy=persistence_healthy,
            project1_gateway_connected=project1_gateway_connected,
            notification_pipeline_healthy=notification_pipeline_healthy,
        )

        uptime_seconds = time.time() - self._startup_time
        summary = {
            "uptime_seconds": round(uptime_seconds, 2),
            "config": self.config.to_sanitized_dict(),
            "readiness": readiness_details,
        }

        sanitized_summary = SecretSanitizer.sanitize_data(summary)

        return OperationalDiagnostics(
            timestamp=time.time(),
            liveness=is_live,
            readiness=is_ready,
            app_env=self.config.app_env,
            active_sessions_count=active_sessions_count,
            system_status="HEALTHY" if is_ready else "DEGRADED",
            persistence_recovery=persistence_recovery.to_dict(),
            diagnostics_summary=sanitized_summary if isinstance(sanitized_summary, dict) else {},
        )
