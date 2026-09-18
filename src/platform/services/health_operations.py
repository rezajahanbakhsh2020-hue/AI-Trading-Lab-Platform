"""System health, readiness, and operational diagnostics service (Part 21: Operational Resilience & Health Control).

Provides explicit distinction between liveness (process alive) and readiness (dependencies ready & configured),
application health status, safe operational diagnostics, correlation request tracking, and sanitized logging.
"""

from dataclasses import dataclass, field
import secrets
import time
from typing import Any, Dict, List, Optional, Tuple

from src.platform.config import PlatformConfig
from src.platform.services.security import SecretSanitizer


@dataclass(frozen=True)
class OperationalDiagnostics:
    """Sanitized operational diagnostics report."""

    timestamp: float
    liveness: bool
    readiness: bool
    app_env: str
    active_sessions_count: int
    system_status: str
    diagnostics_summary: Dict[str, Any]


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

    def check_readiness(
        self,
        active_sessions_count: int = 0,
        provider_checks: Optional[Dict[str, bool]] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Readiness check: evaluates configuration validity and dependency readiness.

        Returns:
            Tuple[is_ready, readiness_details]
        """
        details: Dict[str, Any] = {
            "config_valid": True,
            "app_env": self.config.app_env,
            "is_production": self.config.is_production,
            "active_sessions": active_sessions_count,
            "providers": provider_checks or {},
        }

        # Validate production configuration if in production mode
        if self.config.is_production:
            if not self.config.session_secret or len(self.config.session_secret) < 32:
                details["config_valid"] = False
                details["reason"] = "Insecure SESSION_SECRET in production"
                return False, details

        # Check if any provider failed
        if provider_checks:
            for provider_name, is_ok in provider_checks.items():
                if not is_ok:
                    details["reason"] = f"Provider '{provider_name}' unavailable"
                    return False, details

        return True, details

    def get_operational_diagnostics(
        self,
        active_sessions_count: int = 0,
        provider_checks: Optional[Dict[str, bool]] = None,
    ) -> OperationalDiagnostics:
        """Return comprehensive sanitized operational diagnostics report."""
        is_live, _ = self.check_liveness()
        is_ready, readiness_details = self.check_readiness(
            active_sessions_count=active_sessions_count,
            provider_checks=provider_checks,
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
            diagnostics_summary=sanitized_summary if isinstance(sanitized_summary, dict) else {},
        )
