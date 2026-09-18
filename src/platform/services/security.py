"""Security foundation services for access control, safe secret handling, and audit logging.

Implements real authorization enforcement at the application boundary, secret sanitization,
and security event audit logging.
"""

import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from src.platform.domain.security import (
    ADMIN_ONLY_PERMISSIONS,
    Permission,
    SecurityEvent,
    UserRole,
)
from src.platform.domain.user_authorization import UserAuthorization


class SecretSanitizer:
    """Sanitizes sensitive values, secrets, tokens, and parameters from logs/dicts/strings."""

    SENSITIVE_KEYS: Set[str] = {
        "secret",
        "secrets",
        "password",
        "token",
        "access_token",
        "api_key",
        "apikey",
        "credential",
        "credentials",
        "private_key",
        "auth_code",
        "indicator_logic",
        "strategy_params",
        "sensitive_parameters",
        "lab_secrets",
    }

    SECRET_PATTERN = re.compile(
        r"(bearer\s+[a-zA-Z0-9_\-\.]{8,}|api_key=[a-zA-Z0-9_\-]+|password=[^\s&]+|token=[a-zA-Z0-9_\-]+|secret=[a-zA-Z0-9_\-]+)",
        re.IGNORECASE,
    )

    @classmethod
    def sanitize_string(cls, text: str) -> str:
        """Replace sensitive patterns in text strings with '[REDACTED]'."""
        if not isinstance(text, str):
            return text
        return cls.SECRET_PATTERN.sub("[REDACTED]", text)

    @classmethod
    def sanitize_data(cls, data: Any) -> Any:
        """Recursively sanitize dicts, lists, and strings for safe exposure."""
        if isinstance(data, dict):
            sanitized = {}
            for k, v in data.items():
                key_str = str(k).lower()
                if any(s_key in key_str for s_key in cls.SENSITIVE_KEYS):
                    sanitized[k] = "[REDACTED]"
                else:
                    sanitized[k] = cls.sanitize_data(v)
            return sanitized
        elif isinstance(data, list):
            return [cls.sanitize_data(item) for item in data]
        elif isinstance(data, tuple):
            return tuple(cls.sanitize_data(item) for item in data)
        elif isinstance(data, str):
            return cls.sanitize_string(data)
        return data


class AuditLogger:
    """In-memory security audit event logger."""

    def __init__(self, max_records: int = 1000) -> None:
        if not isinstance(max_records, int) or max_records <= 0:
            raise ValueError("max_records must be a positive integer")
        self._max_records = max_records
        self._events: List[SecurityEvent] = []

    def log(
        self,
        user_id: str,
        event_type: str,
        resource: str,
        action: str,
        outcome: str,
        details: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> SecurityEvent:
        """Record a security audit event."""
        if timestamp is None:
            ts = time.time()
        else:
            ts = float(timestamp)

        event = SecurityEvent(
            timestamp=ts,
            user_id=user_id,
            event_type=event_type,
            resource=resource,
            action=action,
            outcome=outcome,
            details=SecretSanitizer.sanitize_string(details) if details else None,
        )

        self._events.append(event)
        if len(self._events) > self._max_records:
            self._events.pop(0)

        return event

    def get_events(
        self, user_id: Optional[str] = None, outcome: Optional[str] = None
    ) -> List[SecurityEvent]:
        """Retrieve audit log events, optionally filtered by user_id or outcome."""
        filtered = self._events
        if user_id is not None:
            clean_uid = user_id.strip()
            filtered = [e for e in filtered if e.user_id == clean_uid]
        if outcome is not None:
            clean_out = outcome.strip()
            filtered = [e for e in filtered if e.outcome == clean_out]
        return list(filtered)

    def clear(self) -> None:
        """Clear all stored audit events."""
        self._events.clear()


class SecurityBoundaryService:
    """Enforces role-based and permission-based authorization at application boundary."""

    RESOURCE_PERMISSIONS: Dict[str, Permission] = {
        "signals": Permission.READ_SIGNALS,
        "trade_setups": Permission.READ_TRADE_SETUPS,
        "best_strategies": Permission.READ_BEST_STRATEGIES,
        "proprietary_indicators": Permission.READ_PROPRIETARY_INDICATORS,
        "strategy_parameters": Permission.READ_STRATEGY_PARAMETERS,
        "lab_research": Permission.READ_LAB_RESEARCH,
        "secrets": Permission.READ_SECRETS,
        "users": Permission.MANAGE_USERS,
        "system": Permission.MANAGE_SYSTEM,
    }

    def __init__(self, audit_logger: Optional[AuditLogger] = None) -> None:
        self.audit_logger = audit_logger or AuditLogger()

    def authorize(
        self,
        user: Optional[UserAuthorization],
        resource: str,
        action: str = "read",
        required_permission: Optional[Permission] = None,
    ) -> Tuple[bool, str]:
        """Authorize user access to a protected resource server-side."""
        if not isinstance(resource, str) or not resource.strip():
            raise ValueError("resource must be a non-empty string")
        clean_res = resource.strip().lower()

        if user is None:
            self.audit_logger.log(
                user_id="anonymous",
                event_type="ACCESS_DENIED",
                resource=clean_res,
                action=action,
                outcome="DENY",
                details="No user identity provided",
            )
            return False, "Access denied: unauthenticated access"

        if not isinstance(user, UserAuthorization):
            raise ValueError("user must be a UserAuthorization instance")

        # Verify server-side account validity (fails closed if expired or inactive)
        if hasattr(user, "is_account_valid") and callable(getattr(user, "is_account_valid")):
            if not user.is_account_valid():
                reason = "Access denied: account expired or inactive"
                self.audit_logger.log(
                    user_id=user.user_id,
                    event_type="ACCESS_DENIED",
                    resource=clean_res,
                    action=action,
                    outcome="DENY",
                    details=reason,
                )
                return False, reason

        # Determine required permission
        perm = required_permission
        if perm is None:
            perm = self.RESOURCE_PERMISSIONS.get(clean_res)

        # Owner / Admin checks
        if user.is_owner or user.has_permission(Permission.MANAGE_SYSTEM):
            self.audit_logger.log(
                user_id=user.user_id,
                event_type="ACCESS_ALLOWED",
                resource=clean_res,
                action=action,
                outcome="ALLOW",
                details="Owner privilege granted",
            )
            return True, "Access granted"

        if clean_res in ("system", "platform_admin"):
            if not user.is_owner:
                reason = f"Access denied: resource '{clean_res}' requires Owner authority"
                self.audit_logger.log(
                    user_id=user.user_id,
                    event_type="ACCESS_DENIED",
                    resource=clean_res,
                    action=action,
                    outcome="DENY",
                    details=reason,
                )
                return False, reason

        if user.is_admin or user.has_permission(Permission.ADMIN_ALL):
            self.audit_logger.log(
                user_id=user.user_id,
                event_type="ACCESS_ALLOWED",
                resource=clean_res,
                action=action,
                outcome="ALLOW",
                details="Admin privilege granted",
            )
            return True, "Access granted"

        # Check resource specific permission if mapped
        if perm is not None:
            if not user.has_permission(perm):
                reason = f"Access denied: missing permission '{perm.value}' for resource '{clean_res}'"
                self.audit_logger.log(
                    user_id=user.user_id,
                    event_type="ACCESS_DENIED",
                    resource=clean_res,
                    action=action,
                    outcome="DENY",
                    details=reason,
                )
                return False, reason

        # Check for admin-only resources if resource is protected
        if clean_res in ("best_strategies", "proprietary_indicators", "strategy_parameters", "lab_research", "secrets", "users"):
            if not user.is_admin:
                reason = f"Access denied: resource '{clean_res}' is restricted to admin users"
                self.audit_logger.log(
                    user_id=user.user_id,
                    event_type="ACCESS_DENIED",
                    resource=clean_res,
                    action=action,
                    outcome="DENY",
                    details=reason,
                )
                return False, reason

        self.audit_logger.log(
            user_id=user.user_id,
            event_type="ACCESS_ALLOWED",
            resource=clean_res,
            action=action,
            outcome="ALLOW",
            details="Access authorized",
        )
        return True, "Access granted"

    def filter_protected_payload(
        self, user: Optional[UserAuthorization], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Filter out protected fields (best_strategies, sensitive parameters, lab secrets, indicator logic) for normal users."""
        if not isinstance(payload, dict):
            return payload

        sanitized = SecretSanitizer.sanitize_data(payload)
        if not isinstance(sanitized, dict):
            return {}

        is_admin = user is not None and user.is_admin

        if is_admin:
            return sanitized

        # Strip protected sections for normal users
        result = {}
        protected_keys = {
            "best_strategies",
            "indicator_logic",
            "sensitive_parameters",
            "lab_research",
            "secrets",
            "credentials",
        }
        for k, v in sanitized.items():
            if str(k).lower() in protected_keys:
                continue
            result[k] = v

        return result
