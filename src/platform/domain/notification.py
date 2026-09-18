"""Notification and Event domain models for user inbox and system events.

Defines notification categories, severity levels, notification domain objects,
and event data structures with immutability and data integrity validation.
"""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Dict, Optional, Tuple, Union


class NotificationCategory(str, Enum):
    """Categories of notifications in the platform."""

    SIGNAL = "signal"
    PROJECT1_INTEGRATION = "project1_integration"
    SIGNAL_LIFECYCLE = "signal_lifecycle"
    MARKET_HEALTH = "market_health"
    WORKSPACE = "workspace"
    SYSTEM = "system"
    SECURITY = "security"
    ACCOUNT_SESSION = "account_session"
    ADMIN = "admin"


class NotificationSeverity(str, Enum):
    """Severity or priority levels of notifications."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class NotificationEvent:
    """Domain model representing an incoming canonical system/integration event."""

    event_id: str
    event_type: str
    category: NotificationCategory
    severity: NotificationSeverity
    title: str
    message: str
    timestamp: float
    target_user_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0"
    source: str = "platform"
    correlation_id: Optional[str] = None
    status: str = "PENDING"

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str) or not self.event_id.strip():
            raise ValueError("event_id must be a non-empty string")
        object.__setattr__(self, "event_id", self.event_id.strip())

        if not isinstance(self.event_type, str) or not self.event_type.strip():
            raise ValueError("event_type must be a non-empty string")
        object.__setattr__(self, "event_type", self.event_type.strip())

        if not isinstance(self.category, NotificationCategory):
            if isinstance(self.category, str):
                try:
                    cat = NotificationCategory(self.category.strip().lower())
                    object.__setattr__(self, "category", cat)
                except ValueError:
                    raise ValueError(f"Invalid category: {self.category}")
            else:
                raise ValueError("category must be a NotificationCategory enum or valid string")

        if not isinstance(self.severity, NotificationSeverity):
            if isinstance(self.severity, str):
                try:
                    sev = NotificationSeverity(self.severity.strip().lower())
                    object.__setattr__(self, "severity", sev)
                except ValueError:
                    raise ValueError(f"Invalid severity: {self.severity}")
            else:
                raise ValueError("severity must be a NotificationSeverity enum or valid string")

        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("title must be a non-empty string")
        object.__setattr__(self, "title", self.title.strip())

        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("message must be a non-empty string")
        object.__setattr__(self, "message", self.message.strip())

        if not isinstance(self.timestamp, (int, float)) or self.timestamp < 0:
            raise ValueError("timestamp must be a non-negative real number")
        object.__setattr__(self, "timestamp", float(self.timestamp))

        if self.target_user_id is not None:
            if not isinstance(self.target_user_id, str) or not self.target_user_id.strip():
                raise ValueError("target_user_id must be a non-empty string if provided")
            object.__setattr__(self, "target_user_id", self.target_user_id.strip())

        if not isinstance(self.payload, dict):
            raise ValueError("payload must be a dict")

        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("version must be a non-empty string")
        object.__setattr__(self, "version", self.version.strip())

        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be a non-empty string")
        object.__setattr__(self, "source", self.source.strip())

        if self.correlation_id is not None:
            if not isinstance(self.correlation_id, str) or not self.correlation_id.strip():
                raise ValueError("correlation_id must be a non-empty string if provided")
            object.__setattr__(self, "correlation_id", self.correlation_id.strip())

        if not isinstance(self.status, str) or not self.status.strip():
            raise ValueError("status must be a non-empty string")
        object.__setattr__(self, "status", self.status.strip().upper())

    def to_dict(self) -> Dict[str, Any]:
        """Convert NotificationEvent to dictionary for API serialization or logging."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp,
            "target_user_id": self.target_user_id,
            "payload": dict(self.payload),
            "version": self.version,
            "source": self.source,
            "correlation_id": self.correlation_id,
            "status": self.status,
        }


@dataclass(frozen=True)
class NotificationPreferences:
    """User-scoped notification delivery preferences and category filtering."""

    enabled_categories: Tuple[NotificationCategory, ...] = field(
        default_factory=lambda: tuple(NotificationCategory)
    )
    in_app_enabled: bool = True
    external_delivery_enabled: bool = True
    min_severity: NotificationSeverity = NotificationSeverity.INFO

    def __post_init__(self) -> None:
        if isinstance(self.enabled_categories, (list, tuple)):
            clean_cats = []
            for c in self.enabled_categories:
                if isinstance(c, NotificationCategory):
                    clean_cats.append(c)
                elif isinstance(c, str) and c.strip():
                    try:
                        clean_cats.append(NotificationCategory(c.strip().lower()))
                    except ValueError:
                        pass
            object.__setattr__(self, "enabled_categories", tuple(clean_cats))
        else:
            raise ValueError("enabled_categories must be a tuple or list of NotificationCategory")

        if not isinstance(self.in_app_enabled, bool):
            raise ValueError("in_app_enabled must be a boolean")

        if not isinstance(self.external_delivery_enabled, bool):
            raise ValueError("external_delivery_enabled must be a boolean")

        if not isinstance(self.min_severity, NotificationSeverity):
            if isinstance(self.min_severity, str):
                try:
                    sev = NotificationSeverity(self.min_severity.strip().lower())
                    object.__setattr__(self, "min_severity", sev)
                except ValueError:
                    raise ValueError(f"Invalid min_severity: {self.min_severity}")
            else:
                raise ValueError("min_severity must be a NotificationSeverity enum or valid string")

    def is_category_enabled(self, category: Union[NotificationCategory, str]) -> bool:
        cat_enum = category if isinstance(category, NotificationCategory) else None
        if cat_enum is None and isinstance(category, str):
            try:
                cat_enum = NotificationCategory(category.strip().lower())
            except ValueError:
                return False
        return cat_enum in self.enabled_categories

    def is_severity_allowed(self, severity: Union[NotificationSeverity, str]) -> bool:
        sev_enum = severity if isinstance(severity, NotificationSeverity) else None
        if sev_enum is None and isinstance(severity, str):
            try:
                sev_enum = NotificationSeverity(severity.strip().lower())
            except ValueError:
                return False

        order = {
            NotificationSeverity.INFO: 1,
            NotificationSeverity.SUCCESS: 2,
            NotificationSeverity.WARNING: 3,
            NotificationSeverity.ERROR: 4,
        }
        return order.get(sev_enum, 1) >= order.get(self.min_severity, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled_categories": [c.value for c in self.enabled_categories],
            "in_app_enabled": self.in_app_enabled,
            "external_delivery_enabled": self.external_delivery_enabled,
            "min_severity": self.min_severity.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NotificationPreferences":
        cats_raw = data.get("enabled_categories")
        cats = tuple(cats_raw) if isinstance(cats_raw, (list, tuple)) else tuple(NotificationCategory)
        return cls(
            enabled_categories=cats,
            in_app_enabled=bool(data.get("in_app_enabled", True)),
            external_delivery_enabled=bool(data.get("external_delivery_enabled", True)),
            min_severity=data.get("min_severity", NotificationSeverity.INFO.value),
        )


@dataclass(frozen=True)
class Notification:
    """User-scoped notification domain model."""

    notification_id: str
    user_id: str
    category: NotificationCategory
    severity: NotificationSeverity
    title: str
    message: str
    timestamp: float
    is_read: bool = False
    is_archived: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.notification_id, str) or not self.notification_id.strip():
            raise ValueError("notification_id must be a non-empty string")
        object.__setattr__(self, "notification_id", self.notification_id.strip())

        if not isinstance(self.user_id, str) or not self.user_id.strip():
            raise ValueError("user_id must be a non-empty string")
        object.__setattr__(self, "user_id", self.user_id.strip())

        if not isinstance(self.category, NotificationCategory):
            if isinstance(self.category, str):
                try:
                    cat = NotificationCategory(self.category.strip().lower())
                    object.__setattr__(self, "category", cat)
                except ValueError:
                    raise ValueError(f"Invalid category: {self.category}")
            else:
                raise ValueError("category must be a NotificationCategory enum or valid string")

        if not isinstance(self.severity, NotificationSeverity):
            if isinstance(self.severity, str):
                try:
                    sev = NotificationSeverity(self.severity.strip().lower())
                    object.__setattr__(self, "severity", sev)
                except ValueError:
                    raise ValueError(f"Invalid severity: {self.severity}")
            else:
                raise ValueError("severity must be a NotificationSeverity enum or valid string")

        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("title must be a non-empty string")
        object.__setattr__(self, "title", self.title.strip())

        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("message must be a non-empty string")
        object.__setattr__(self, "message", self.message.strip())

        if not isinstance(self.timestamp, (int, float)) or self.timestamp < 0:
            raise ValueError("timestamp must be a non-negative real number")
        object.__setattr__(self, "timestamp", float(self.timestamp))

        if not isinstance(self.is_read, bool):
            raise ValueError("is_read must be a boolean")

        if not isinstance(self.is_archived, bool):
            raise ValueError("is_archived must be a boolean")

        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dict")

    def with_read(self, is_read: bool = True) -> "Notification":
        """Return a copy of notification with updated read status."""
        return Notification(
            notification_id=self.notification_id,
            user_id=self.user_id,
            category=self.category,
            severity=self.severity,
            title=self.title,
            message=self.message,
            timestamp=self.timestamp,
            is_read=is_read,
            is_archived=self.is_archived,
            metadata=dict(self.metadata),
        )

    def with_archived(self, is_archived: bool = True) -> "Notification":
        """Return a copy of notification with updated archived status."""
        return Notification(
            notification_id=self.notification_id,
            user_id=self.user_id,
            category=self.category,
            severity=self.severity,
            title=self.title,
            message=self.message,
            timestamp=self.timestamp,
            is_read=self.is_read,
            is_archived=is_archived,
            metadata=dict(self.metadata),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert notification to dictionary for presentation or storage."""
        return {
            "notification_id": self.notification_id,
            "user_id": self.user_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp,
            "is_read": self.is_read,
            "is_archived": self.is_archived,
            "metadata": dict(self.metadata),
        }
