"""User authorization repository port and file-backed JSON adapter (Part 20: Hexagonal Persistence Boundary).

Provides Hexagonal Architecture port (UserRepositoryPort) and JSON file implementation (FileBackedUserRepository)
for persisting user accounts, authentication hashes, active session tokens, and security audit logs across process restarts.
"""

from abc import ABC, abstractmethod
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import UserAuthorization


class UserRepositoryPort(ABC):
    """Abstract Hexagonal port for user authorization and session persistence."""

    @abstractmethod
    def save_user(self, user: UserAuthorization) -> UserAuthorization:
        """Persist user authorization record."""
        pass

    @abstractmethod
    def get_user_by_id(self, user_id: str) -> Optional[UserAuthorization]:
        """Retrieve user authorization by user ID."""
        pass

    @abstractmethod
    def get_user_by_auth_code(self, auth_code: str) -> Optional[UserAuthorization]:
        """Retrieve user authorization by auth code."""
        pass

    @abstractmethod
    def list_users(self) -> List[UserAuthorization]:
        """List all stored user authorization records."""
        pass

    @abstractmethod
    def save_session(self, token: str, user_id: str, created_ts: float) -> None:
        """Persist active session token."""
        pass

    @abstractmethod
    def get_session(self, token: str) -> Optional[Tuple[str, float]]:
        """Retrieve active session data by token."""
        pass

    @abstractmethod
    def delete_session(self, token: str) -> None:
        """Delete session token."""
        pass

    @abstractmethod
    def list_sessions(self) -> Dict[str, Tuple[str, float]]:
        """List all stored active sessions."""
        pass


class FileBackedUserRepository(UserRepositoryPort):
    """File-backed JSON implementation of UserRepositoryPort."""

    def __init__(self, storage_dir: str = ".data") -> None:
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self.users_file = os.path.join(self.storage_dir, "users.json")
        self.sessions_file = os.path.join(self.storage_dir, "sessions.json")
        self._users: Dict[str, UserAuthorization] = {}
        self._sessions: Dict[str, Tuple[str, float]] = {}
        self._load()

    def _serialize_user(self, user: UserAuthorization) -> Dict[str, Any]:
        return {
            "user_id": user.user_id,
            "auth_code": user.auth_code,
            "telegram_chat_id": user.telegram_chat_id,
            "delivery_enabled": user.delivery_enabled,
            "allowed_symbols": list(user.allowed_symbols),
            "allowed_strategies": list(user.allowed_strategies),
            "role": user.role.value,
            "permissions": [p.value for p in user.permissions],
            "detail": user.detail,
            "password_hash": user.password_hash,
            "salt": user.salt,
            "is_active": user.is_active,
            "activation_timestamp": user.activation_timestamp,
            "expiration_timestamp": user.expiration_timestamp,
            "is_permanent_admin": user.is_permanent_admin,
            "recovery_email": user.recovery_email,
            "recovery_token_hash": user.recovery_token_hash,
            "recovery_token_expiration": user.recovery_token_expiration,
        }

    def _deserialize_user(self, data: Dict[str, Any]) -> UserAuthorization:
        return UserAuthorization(
            user_id=data["user_id"],
            auth_code=data["auth_code"],
            telegram_chat_id=data.get("telegram_chat_id"),
            delivery_enabled=data.get("delivery_enabled", True),
            allowed_symbols=tuple(data.get("allowed_symbols", [])),
            allowed_strategies=tuple(data.get("allowed_strategies", [])),
            role=UserRole(data.get("role", "user")),
            permissions=tuple(Permission(p) for p in data.get("permissions", [])),
            detail=data.get("detail"),
            password_hash=data.get("password_hash"),
            salt=data.get("salt"),
            is_active=data.get("is_active", True),
            activation_timestamp=data.get("activation_timestamp"),
            expiration_timestamp=data.get("expiration_timestamp"),
            is_permanent_admin=data.get("is_permanent_admin", False),
            recovery_email=data.get("recovery_email"),
            recovery_token_hash=data.get("recovery_token_hash"),
            recovery_token_expiration=data.get("recovery_token_expiration"),
        )

    def _load(self) -> None:
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        u = self._deserialize_user(item)
                        self._users[u.user_id] = u
            except Exception:
                pass

        if os.path.exists(self.sessions_file):
            try:
                with open(self.sessions_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for token, sess in data.items():
                        self._sessions[token] = (sess["user_id"], sess["created_ts"])
            except Exception:
                pass

    def _save_users(self) -> None:
        try:
            serialized = [self._serialize_user(u) for u in self._users.values()]
            temp_file = f"{self.users_file}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(serialized, f, indent=2)
            os.replace(temp_file, self.users_file)
        except Exception:
            pass

    def _save_sessions(self) -> None:
        try:
            serialized = {
                token: {"user_id": uid, "created_ts": ts}
                for token, (uid, ts) in self._sessions.items()
            }
            temp_file = f"{self.sessions_file}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(serialized, f, indent=2)
            os.replace(temp_file, self.sessions_file)
        except Exception:
            pass

    def save_user(self, user: UserAuthorization) -> UserAuthorization:
        self._users[user.user_id] = user
        self._save_users()
        return user

    def get_user_by_id(self, user_id: str) -> Optional[UserAuthorization]:
        return self._users.get(user_id)

    def get_user_by_auth_code(self, auth_code: str) -> Optional[UserAuthorization]:
        for u in self._users.values():
            if u.auth_code == auth_code:
                return u
        return None

    def list_users(self) -> List[UserAuthorization]:
        return list(self._users.values())

    def save_session(self, token: str, user_id: str, created_ts: float) -> None:
        self._sessions[token] = (user_id, created_ts)
        self._save_sessions()

    def get_session(self, token: str) -> Optional[Tuple[str, float]]:
        return self._sessions.get(token)

    def delete_session(self, token: str) -> None:
        if token in self._sessions:
            del self._sessions[token]
            self._save_sessions()

    def list_sessions(self) -> Dict[str, Tuple[str, float]]:
        return dict(self._sessions)
