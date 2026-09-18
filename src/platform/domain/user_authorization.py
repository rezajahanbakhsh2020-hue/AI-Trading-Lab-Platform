"""User authorization domain model (Part 19: Host Application & Access Control).

Immutable domain object representing a user's authorization identity, destination configuration,
role, signal delivery permissions, and time-limited account credentials.
"""

from dataclasses import dataclass, field
import hashlib
import os
import secrets
import time
from typing import Any, Dict, Optional, Set, Tuple, Union

from src.platform.domain.security import (
    DEFAULT_ROLE_PERMISSIONS,
    Permission,
    UserRole,
)


def hash_password(plaintext: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Securely hash a password using PBKDF2-HMAC-SHA256 with a unique salt."""
    if not isinstance(plaintext, str) or not plaintext:
        raise ValueError("Password must be a non-empty string")
    if salt is None:
        salt = secrets.token_hex(16)

    key = hashlib.pbkdf2_hmac(
        "sha256",
        plaintext.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=100_000,
    )
    return key.hex(), salt


@dataclass(frozen=True)
class UserAuthorization:
    """Immutable user authorization identity, role, delivery configuration, and account lifecycle."""

    user_id: str
    auth_code: str
    telegram_chat_id: Optional[str] = None
    delivery_enabled: bool = True
    allowed_symbols: Tuple[str, ...] = field(default_factory=tuple)
    allowed_strategies: Tuple[str, ...] = field(default_factory=tuple)
    role: UserRole = UserRole.USER
    permissions: Tuple[Permission, ...] = field(default_factory=tuple)
    detail: Optional[str] = None

    # Security Gate & Account Lifecycle extensions
    password_hash: Optional[str] = None
    salt: Optional[str] = None
    is_active: bool = True
    activation_timestamp: Optional[float] = None
    expiration_timestamp: Optional[float] = None
    is_permanent_admin: bool = False
    recovery_email: Optional[str] = None
    recovery_token_hash: Optional[str] = None
    recovery_token_expiration: Optional[float] = None

    def __post_init__(self) -> None:
        if not isinstance(self.user_id, str) or not self.user_id.strip():
            raise ValueError("user_id must be a non-empty string")
        object.__setattr__(self, "user_id", self.user_id.strip())

        if not isinstance(self.auth_code, str) or not self.auth_code.strip():
            raise ValueError("auth_code must be a non-empty string")
        object.__setattr__(self, "auth_code", self.auth_code.strip())

        if not isinstance(self.delivery_enabled, bool):
            raise ValueError("delivery_enabled must be a boolean")

        if self.telegram_chat_id is not None:
            if not isinstance(self.telegram_chat_id, str) or not self.telegram_chat_id.strip():
                raise ValueError("telegram_chat_id must be a non-empty string if provided")
            object.__setattr__(self, "telegram_chat_id", self.telegram_chat_id.strip())

        if isinstance(self.allowed_symbols, (list, tuple)):
            clean_syms = tuple(s.strip().upper() for s in self.allowed_symbols if isinstance(s, str) and s.strip())
            object.__setattr__(self, "allowed_symbols", clean_syms)
        else:
            raise ValueError("allowed_symbols must be a tuple or list")

        if isinstance(self.allowed_strategies, (list, tuple)):
            clean_strats = tuple(s.strip() for s in self.allowed_strategies if isinstance(s, str) and s.strip())
            object.__setattr__(self, "allowed_strategies", clean_strats)
        else:
            raise ValueError("allowed_strategies must be a tuple or list")

        # Validate Role
        if isinstance(self.role, str):
            try:
                clean_role = UserRole(self.role.lower().strip())
            except ValueError:
                raise ValueError(f"invalid UserRole: {self.role}")
            object.__setattr__(self, "role", clean_role)
        elif not isinstance(self.role, UserRole):
            raise ValueError("role must be a UserRole or string equivalent")

        # Guarantee permanent admin if role is OWNER or ADMIN
        if self.role in (UserRole.OWNER, UserRole.ADMIN):
            object.__setattr__(self, "is_permanent_admin", True)

        # Set default permissions if not explicitly supplied
        if not self.permissions:
            default_perms = DEFAULT_ROLE_PERMISSIONS.get(self.role, ())
            object.__setattr__(self, "permissions", default_perms)
        else:
            if not isinstance(self.permissions, (list, tuple, set)):
                raise ValueError("permissions must be a sequence of Permission")
            clean_perms = []
            for p in self.permissions:
                if isinstance(p, str):
                    try:
                        clean_perms.append(Permission(p.lower().strip()))
                    except ValueError:
                        raise ValueError(f"invalid Permission: {p}")
                elif isinstance(p, Permission):
                    clean_perms.append(p)
                else:
                    raise ValueError(f"invalid Permission item: {p}")
            object.__setattr__(self, "permissions", tuple(clean_perms))

        if self.detail is not None:
            if not isinstance(self.detail, str) or not self.detail.strip():
                raise ValueError("detail must be a non-empty string if provided")
            object.__setattr__(self, "detail", self.detail.strip())

    @property
    def is_owner(self) -> bool:
        """Return True if user is platform Owner."""
        return self.role == UserRole.OWNER or (self.is_permanent_admin and Permission.MANAGE_SYSTEM in self.permissions)

    @property
    def is_admin(self) -> bool:
        """Return True if user is an admin or owner."""
        return self.role in (UserRole.OWNER, UserRole.ADMIN) or self.is_permanent_admin

    def verify_password(self, plaintext: str) -> bool:
        """Verify candidate plaintext password against stored hash and salt."""
        if not self.password_hash or not self.salt:
            return False
        if not plaintext:
            return False
        candidate_hash, _ = hash_password(plaintext, self.salt)
        return secrets.compare_digest(candidate_hash, self.password_hash)

    def is_expired(self, now_ts: Optional[float] = None) -> bool:
        """Determine if account has expired. Owner/Admin accounts are immune."""
        if self.is_permanent_admin or self.role in (UserRole.OWNER, UserRole.ADMIN):
            return False
        if self.expiration_timestamp is None:
            return False
        if now_ts is None:
            now_ts = time.time()
        return now_ts >= self.expiration_timestamp

    def is_account_valid(self, now_ts: Optional[float] = None) -> bool:
        """Evaluate server-side validity of account for authentication and authorization."""
        if self.is_permanent_admin or self.role in (UserRole.OWNER, UserRole.ADMIN):
            return True
        if not self.is_active:
            return False
        if now_ts is None:
            now_ts = time.time()
        if self.activation_timestamp is not None and now_ts < self.activation_timestamp:
            return False
        if self.is_expired(now_ts):
            return False
        return True

    def has_permission(self, permission: Union[Permission, str]) -> bool:
        """Evaluate if user possesses a specific permission."""
        if not self.is_account_valid():
            return False
        if Permission.ADMIN_ALL in self.permissions or self.is_admin:
            return True
        if isinstance(permission, str):
            try:
                permission = Permission(permission.lower().strip())
            except ValueError:
                return False
        return permission in self.permissions

    def can_receive_signal(self, symbol: str, strategy_name: Optional[str] = None) -> bool:
        """Evaluate if user authorization policy allows receiving a signal."""
        if not self.is_account_valid():
            return False
        if not self.has_permission(Permission.READ_SIGNALS):
            return False
        if not self.delivery_enabled:
            return False
        if not self.telegram_chat_id:
            return False
        if self.allowed_symbols and symbol.strip().upper() not in self.allowed_symbols:
            return False
        if self.allowed_strategies and strategy_name and strategy_name.strip() not in self.allowed_strategies:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Return dictionary representation without exposing sensitive auth_code or password hashes."""
        return {
            "user_id": self.user_id,
            "role": self.role.value,
            "permissions": [p.value for p in self.permissions],
            "delivery_enabled": self.delivery_enabled,
            "telegram_chat_id": self.telegram_chat_id,
            "allowed_symbols": list(self.allowed_symbols),
            "allowed_strategies": list(self.allowed_strategies),
            "detail": self.detail,
            "is_active": self.is_active,
            "activation_timestamp": self.activation_timestamp,
            "expiration_timestamp": self.expiration_timestamp,
            "is_permanent_admin": self.is_permanent_admin,
            "is_expired": self.is_expired(),
            "is_account_valid": self.is_account_valid(),
        }
