"""User authorization repository port and file-backed JSON adapter (Part 20: Hexagonal Persistence Boundary).

Provides Hexagonal Architecture port (UserRepositoryPort) and JSON file implementation (FileBackedUserRepository)
for persisting user accounts, authentication hashes, active session tokens, and security audit logs across process restarts.
Includes schema versioning, backward-compatible migration, safe corrupted-file handling (backup + alert), and atomic disk writes.
"""

from abc import ABC, abstractmethod
import json
import logging
import os
import shutil
import time
from typing import Any, Dict, List, Optional, Tuple

from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import UserAuthorization

logger = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION = 2


class UserRepositoryError(Exception):
    """Base exception for user repository operational failures."""
    pass


class CorruptStorageError(UserRepositoryError):
    """Raised when persisted storage files are corrupted or unparseable."""
    pass


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
    """File-backed JSON implementation of UserRepositoryPort with schema migration and corruption handling."""

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
            "_schema_version": CURRENT_SCHEMA_VERSION,
        }

    def _deserialize_user(self, data: Dict[str, Any]) -> UserAuthorization:
        # Schema Migration Logic: Handle V1 (or unversioned) payload to V2
        migrated_data = dict(data)
        schema_ver = migrated_data.get("_schema_version", 1)

        if schema_ver < 2:
            # V1 to V2 migration: handle role defaults and permissions
            raw_role = str(migrated_data.get("role", "user")).lower()
            if raw_role == "owner":
                migrated_data["role"] = "owner"
                migrated_data["is_permanent_admin"] = True
            elif raw_role in ("admin", "user", "customer", "guest"):
                migrated_data["role"] = raw_role
            else:
                migrated_data["role"] = "user"

            if "is_active" not in migrated_data:
                migrated_data["is_active"] = True
            if "is_permanent_admin" not in migrated_data:
                migrated_data["is_permanent_admin"] = (migrated_data["role"] in ("admin", "owner"))

            migrated_data["_schema_version"] = CURRENT_SCHEMA_VERSION

        return UserAuthorization(
            user_id=migrated_data["user_id"],
            auth_code=migrated_data["auth_code"],
            telegram_chat_id=migrated_data.get("telegram_chat_id"),
            delivery_enabled=migrated_data.get("delivery_enabled", True),
            allowed_symbols=tuple(migrated_data.get("allowed_symbols", [])),
            allowed_strategies=tuple(migrated_data.get("allowed_strategies", [])),
            role=UserRole(migrated_data.get("role", "user")),
            permissions=tuple(Permission(p) for p in migrated_data.get("permissions", [])),
            detail=migrated_data.get("detail"),
            password_hash=migrated_data.get("password_hash"),
            salt=migrated_data.get("salt"),
            is_active=migrated_data.get("is_active", True),
            activation_timestamp=migrated_data.get("activation_timestamp"),
            expiration_timestamp=migrated_data.get("expiration_timestamp"),
            is_permanent_admin=migrated_data.get("is_permanent_admin", False),
            recovery_email=migrated_data.get("recovery_email"),
            recovery_token_hash=migrated_data.get("recovery_token_hash"),
            recovery_token_expiration=migrated_data.get("recovery_token_expiration"),
        )

    def _backup_corrupt_file(self, filepath: str) -> str:
        """Create a timestamped copy of a corrupt file so operator data is never silently destroyed."""
        timestamp = int(time.time())
        corrupt_backup = f"{filepath}.corrupt.{timestamp}"
        try:
            if os.path.exists(filepath):
                shutil.copy2(filepath, corrupt_backup)
                logger.warning("Corrupt storage file backed up to '%s'", corrupt_backup)
        except Exception as exc:
            logger.error("Failed to backup corrupt storage file '%s': %s", filepath, exc)
        return corrupt_backup

    def _load(self) -> None:
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not isinstance(data, list):
                        raise ValueError("User repository data root must be a list")
                    for item in data:
                        if not isinstance(item, dict):
                            raise ValueError("User repository item must be a JSON object")
                        u = self._deserialize_user(item)
                        self._users[u.user_id] = u
            except Exception as e:
                self._backup_corrupt_file(self.users_file)
                raise CorruptStorageError(f"Failed to load user repository file '{self.users_file}': {e}") from e

        if os.path.exists(self.sessions_file):
            try:
                with open(self.sessions_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not isinstance(data, dict):
                        raise ValueError("Session repository data root must be a dictionary")
                    for token_h, sess in data.items():
                        if isinstance(sess, dict) and "user_id" in sess and "created_ts" in sess:
                            self._sessions[token_h] = (sess["user_id"], float(sess["created_ts"]))
            except Exception as e:
                self._backup_corrupt_file(self.sessions_file)
                raise CorruptStorageError(f"Failed to load session repository file '{self.sessions_file}': {e}") from e

    def _save_users(self) -> None:
        try:
            serialized = [self._serialize_user(u) for u in self._users.values()]
            temp_file = f"{self.users_file}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(serialized, f, indent=2)
            os.replace(temp_file, self.users_file)
        except Exception as e:
            raise UserRepositoryError(f"Failed to save user records to '{self.users_file}': {e}") from e

    def _save_sessions(self) -> None:
        try:
            serialized = {
                token: {"user_id": uid, "created_ts": ts, "_schema_version": CURRENT_SCHEMA_VERSION}
                for token, (uid, ts) in self._sessions.items()
            }
            temp_file = f"{self.sessions_file}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(serialized, f, indent=2)
            os.replace(temp_file, self.sessions_file)
        except Exception as e:
            raise UserRepositoryError(f"Failed to save session records to '{self.sessions_file}': {e}") from e

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
