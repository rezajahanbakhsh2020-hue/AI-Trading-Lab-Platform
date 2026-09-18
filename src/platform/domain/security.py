"""Security domain models and permissions for host access control and security boundary.

Defines roles, extensible permissions, protected resource identifiers, and security events.
"""

from dataclasses import dataclass
from enum import Enum
import time
from typing import Any, Dict, Optional, Set, Tuple


class UserRole(str, Enum):
    """User roles within the platform security boundary."""

    OWNER = "owner"
    ADMIN = "admin"
    CUSTOMER = "customer"
    USER = "user"  # Backward compatibility alias for customer
    GUEST = "guest"


class Permission(str, Enum):
    """Extensible permissions for resource access control."""

    READ_SIGNALS = "read:signals"
    READ_TRADE_SETUPS = "read:trade_setups"
    READ_BEST_STRATEGIES = "read:best_strategies"
    READ_PROPRIETARY_INDICATORS = "read:proprietary_indicators"
    READ_STRATEGY_PARAMETERS = "read:strategy_parameters"
    READ_LAB_RESEARCH = "read:lab_research"
    READ_SECRETS = "read:secrets"
    ADMIN_ALL = "admin:all"
    MANAGE_USERS = "manage:users"
    MANAGE_SYSTEM = "manage:system"


# Default permissions by role
DEFAULT_ROLE_PERMISSIONS: Dict[UserRole, Tuple[Permission, ...]] = {
    UserRole.OWNER: (
        Permission.ADMIN_ALL,
        Permission.MANAGE_USERS,
        Permission.MANAGE_SYSTEM,
        Permission.READ_SIGNALS,
        Permission.READ_TRADE_SETUPS,
        Permission.READ_BEST_STRATEGIES,
        Permission.READ_PROPRIETARY_INDICATORS,
        Permission.READ_STRATEGY_PARAMETERS,
        Permission.READ_LAB_RESEARCH,
        Permission.READ_SECRETS,
    ),
    UserRole.ADMIN: (
        Permission.ADMIN_ALL,
        Permission.MANAGE_USERS,
        Permission.READ_SIGNALS,
        Permission.READ_TRADE_SETUPS,
        Permission.READ_BEST_STRATEGIES,
        Permission.READ_PROPRIETARY_INDICATORS,
        Permission.READ_STRATEGY_PARAMETERS,
        Permission.READ_LAB_RESEARCH,
        Permission.READ_SECRETS,
    ),
    UserRole.CUSTOMER: (
        Permission.READ_SIGNALS,
        Permission.READ_TRADE_SETUPS,
    ),
    UserRole.USER: (
        Permission.READ_SIGNALS,
        Permission.READ_TRADE_SETUPS,
    ),
    UserRole.GUEST: (),
}

ADMIN_ONLY_PERMISSIONS: Set[Permission] = {
    Permission.READ_BEST_STRATEGIES,
    Permission.READ_PROPRIETARY_INDICATORS,
    Permission.READ_STRATEGY_PARAMETERS,
    Permission.READ_LAB_RESEARCH,
    Permission.READ_SECRETS,
    Permission.ADMIN_ALL,
    Permission.MANAGE_USERS,
    Permission.MANAGE_SYSTEM,
}


@dataclass(frozen=True)
class SecurityEvent:
    """Immutable security audit log record."""

    timestamp: float
    user_id: str
    event_type: str
    resource: str
    action: str
    outcome: str
    details: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.timestamp, (int, float)) or self.timestamp < 0:
            raise ValueError("timestamp must be a non-negative real number")
        object.__setattr__(self, "timestamp", float(self.timestamp))

        if not isinstance(self.user_id, str) or not self.user_id.strip():
            raise ValueError("user_id must be a non-empty string")
        object.__setattr__(self, "user_id", self.user_id.strip())

        if not isinstance(self.event_type, str) or not self.event_type.strip():
            raise ValueError("event_type must be a non-empty string")
        object.__setattr__(self, "event_type", self.event_type.strip())

        if not isinstance(self.resource, str) or not self.resource.strip():
            raise ValueError("resource must be a non-empty string")
        object.__setattr__(self, "resource", self.resource.strip())

        if not isinstance(self.action, str) or not self.action.strip():
            raise ValueError("action must be a non-empty string")
        object.__setattr__(self, "action", self.action.strip())

        if self.outcome not in ("ALLOW", "DENY"):
            raise ValueError("outcome must be either 'ALLOW' or 'DENY'")

        if self.details is not None:
            if not isinstance(self.details, str) or not self.details.strip():
                raise ValueError("details must be a non-empty string if provided")
            object.__setattr__(self, "details", self.details.strip())

    def to_dict(self) -> Dict[str, Any]:
        """Return dictionary representation of the security event."""
        return {
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "event_type": self.event_type,
            "resource": self.resource,
            "action": self.action,
            "outcome": self.outcome,
            "details": self.details,
        }
