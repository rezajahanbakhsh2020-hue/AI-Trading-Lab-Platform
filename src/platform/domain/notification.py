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
    MARKET_HEALTH = "market_health"
    WORKSPACE = "workspace"
    SYSTEM = "system"


class NotificationSeverity(str, Enum):
    """Severity or priority levels of notifications."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class NotificationEvent:
    """Domain model representing an incoming real system event."""

    event_id: str
    event_type: str
    category: NotificationCategory
    severity: NotificationSeverity
    title: str
    message: str
    timestamp: float
    target_user_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

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
