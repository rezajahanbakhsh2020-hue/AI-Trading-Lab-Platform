"""User authorization service implementation (Part 19: Host Application & Access Control).

Provides user authorization lookup, password authentication, session token management,
customer lifecycle management (create, renew, toggle active status, password reset),
and administrative access management with audit logging.
"""

import secrets
import time
from typing import Dict, List, Optional, Tuple

from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import UserAuthorization, hash_password
from src.platform.services.security import AuditLogger


class UserAuthorizationService:
    """Service managing user authorization records, authentication, sessions, and customer lifecycle."""

    def __init__(self, audit_logger: Optional[AuditLogger] = None) -> None:
        self._users_by_id: Dict[str, UserAuthorization] = {}
        self._users_by_code: Dict[str, UserAuthorization] = {}
        self._sessions: Dict[str, Tuple[str, float]] = {}  # session_token -> (user_id, creation_ts)
        self._audit_logger = audit_logger or AuditLogger()
        self._initialize_default_users()

    def _initialize_default_users(self) -> None:
        """Initialize permanent owner/admin and default demo accounts with hashed passwords."""
        admin_hash, admin_salt = hash_password("AdminSecureKey2026!")
        admin_user = UserAuthorization(
            user_id="admin_owner",
            auth_code="AUTH_ADMIN_2026",
            role=UserRole.ADMIN,
            password_hash=admin_hash,
            salt=admin_salt,
            is_permanent_admin=True,
            detail="Permanent protected Owner/Admin account",
        )
        self.register_user(admin_user)

        user_hash, user_salt = hash_password("CustomerPass2026!")
        now_ts = time.time()
        default_customer = UserAuthorization(
            user_id="demo_user",
            auth_code="AUTH_USER_2026",
            role=UserRole.USER,
            allowed_symbols=("XAUUSD", "EURUSD"),
            password_hash=user_hash,
            salt=user_salt,
            is_active=True,
            activation_timestamp=now_ts - 3600,
            expiration_timestamp=now_ts + (30 * 86400),
            detail="Default active customer account",
        )
        self.register_user(default_customer)

    def register_user(self, user: UserAuthorization) -> None:
        """Register or update a user authorization entry."""
        if not isinstance(user, UserAuthorization):
            raise ValueError("user must be a UserAuthorization instance")
        self._users_by_id[user.user_id] = user
        self._users_by_code[user.auth_code] = user

    def authenticate_by_code(self, auth_code: str) -> Optional[UserAuthorization]:
        """Look up user authorization by authorization code."""
        if not isinstance(auth_code, str) or not auth_code.strip():
            return None
        return self._users_by_code.get(auth_code.strip())

    def get_authorized_user(self, user_id: str) -> Optional[UserAuthorization]:
        """Look up user authorization by user_id."""
        if not isinstance(user_id, str) or not user_id.strip():
            return None
        return self._users_by_id.get(user_id.strip())

    def get_user_authorization(self, user_id: str) -> Optional[UserAuthorization]:
        """Look up user authorization by user ID."""
        return self.get_authorized_user(user_id)

    def authenticate_with_password(
        self, user_id: str, plaintext_password: str
    ) -> Tuple[bool, Optional[UserAuthorization], str]:
        """Authenticate user credentials server-side against password hash and account validity.

        Returns:
            Tuple[success, user_authorization, message]
        """
        user = self.get_user_authorization(user_id)
        if not user:
            return False, None, "Invalid credentials"

        if not user.verify_password(plaintext_password):
            self._audit_logger.log(
                user_id=user.user_id,
                event_type="AUTH_FAILED",
                resource="auth.login",
                action="login",
                outcome="DENY",
                details="Password mismatch",
            )
            return False, None, "Invalid credentials"

        now_ts = time.time()
        if not user.is_permanent_admin and not user.role == UserRole.ADMIN:
            if not user.is_active:
                self._audit_logger.log(
                    user_id=user.user_id,
                    event_type="AUTH_FAILED",
                    resource="auth.login",
                    action="login",
                    outcome="DENY",
                    details="Account deactivated",
                )
                return False, None, "Account deactivated"

            if user.activation_timestamp is not None and now_ts < user.activation_timestamp:
                self._audit_logger.log(
                    user_id=user.user_id,
                    event_type="AUTH_FAILED",
                    resource="auth.login",
                    action="login",
                    outcome="DENY",
                    details="Account not yet active",
                )
                return False, None, "Account not yet active"

            if user.is_expired(now_ts):
                self._audit_logger.log(
                    user_id=user.user_id,
                    event_type="AUTH_FAILED",
                    resource="auth.login",
                    action="login",
                    outcome="DENY",
                    details="Account expired",
                )
                return False, None, "Account expired"

        self._audit_logger.log(
            user_id=user.user_id,
            event_type="AUTH_SUCCESS",
            resource="auth.login",
            action="login",
            outcome="ALLOW",
            details="Successful authentication",
        )
        return True, user, "Authentication successful"

    def create_session_token(self, user_id: str) -> Optional[str]:
        """Generate a secure session token for an authenticated valid account."""
        user = self.get_user_authorization(user_id)
        if not user or not user.is_account_valid():
            return None
        token = f"sess_{secrets.token_urlsafe(32)}"
        self._sessions[token] = (user.user_id, time.time())
        return token

    def validate_session_token(self, token: str) -> Tuple[bool, Optional[UserAuthorization]]:
        """Validate session token and re-verify server-side account status in real-time."""
        if not token or token not in self._sessions:
            return False, None
        user_id, created_ts = self._sessions[token]
        user = self.get_user_authorization(user_id)
        if not user or not user.is_account_valid():
            if token in self._sessions:
                del self._sessions[token]
            return False, None
        return True, user

    def revoke_session_token(self, token: str) -> bool:
        """Revoke active session token."""
        if token in self._sessions:
            del self._sessions[token]
            return True
        return False

    def evaluate_delivery_permission(
        self, user_id: str, symbol: str, strategy_name: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Evaluate whether a user is authorized to receive a signal for a symbol/strategy."""
        user = self.get_authorized_user(user_id)
        if user is None:
            return False, "user is not registered or authorized"

        if not user.delivery_enabled:
            return False, "signal delivery is disabled for user"

        if not user.telegram_chat_id:
            return False, "no Telegram chat destination configured for user"

        if not user.can_receive_signal(symbol=symbol, strategy_name=strategy_name):
            return False, f"user policy does not permit signals for symbol '{symbol}' or strategy '{strategy_name}'"

        return True, "delivery authorized"

    # Admin Customer Lifecycle Management Methods

    def create_customer_account(
        self,
        actor_user: UserAuthorization,
        target_user_id: str,
        plaintext_password: str,
        activation_timestamp: float,
        expiration_timestamp: float,
        allowed_symbols: Tuple[str, ...] = ("XAUUSD", "EURUSD"),
        detail: Optional[str] = None,
    ) -> UserAuthorization:
        """Create new customer account with activation and expiration timestamps."""
        if not actor_user.is_admin:
            raise PermissionError("Only Admin can create customer accounts")

        target_user_id = target_user_id.strip()
        if target_user_id in self._users_by_id:
            raise ValueError(f"User ID '{target_user_id}' already exists")

        if expiration_timestamp <= activation_timestamp:
            raise ValueError("Expiration timestamp must be strictly greater than activation timestamp")

        p_hash, salt = hash_password(plaintext_password)
        auth_code = f"AUTH_{secrets.token_hex(8).upper()}"

        new_user = UserAuthorization(
            user_id=target_user_id,
            auth_code=auth_code,
            role=UserRole.USER,
            allowed_symbols=allowed_symbols,
            password_hash=p_hash,
            salt=salt,
            is_active=True,
            activation_timestamp=activation_timestamp,
            expiration_timestamp=expiration_timestamp,
            is_permanent_admin=False,
            detail=detail or "Customer account created by admin",
        )
        self.register_user(new_user)

        self._audit_logger.log(
            user_id=actor_user.user_id,
            event_type="ADMIN_ACTION",
            resource=f"admin.create_user.{target_user_id}",
            action="create_user",
            outcome="ALLOW",
            details=f"Created customer account active from {activation_timestamp} to {expiration_timestamp}",
        )
        return new_user

    def renew_customer_account(
        self,
        actor_user: UserAuthorization,
        target_user_id: str,
        new_expiration_timestamp: float,
    ) -> UserAuthorization:
        """Renew/extend expiration timestamp for a customer account."""
        if not actor_user.is_admin:
            raise PermissionError("Only Admin can renew customer accounts")

        target = self.get_user_authorization(target_user_id)
        if not target:
            raise ValueError(f"User '{target_user_id}' not found")

        if target.is_permanent_admin or target.role == UserRole.ADMIN:
            raise ValueError("Cannot modify expiration for protected Admin/Owner account")

        updated_user = UserAuthorization(
            user_id=target.user_id,
            auth_code=target.auth_code,
            telegram_chat_id=target.telegram_chat_id,
            delivery_enabled=target.delivery_enabled,
            allowed_symbols=target.allowed_symbols,
            allowed_strategies=target.allowed_strategies,
            role=target.role,
            permissions=target.permissions,
            detail=f"Renewed by admin at {time.time()}",
            password_hash=target.password_hash,
            salt=target.salt,
            is_active=True,
            activation_timestamp=target.activation_timestamp,
            expiration_timestamp=new_expiration_timestamp,
            is_permanent_admin=False,
        )
        self.register_user(updated_user)

        self._audit_logger.log(
            user_id=actor_user.user_id,
            event_type="ADMIN_ACTION",
            resource=f"admin.renew_user.{target_user_id}",
            action="renew_user",
            outcome="ALLOW",
            details=f"Extended expiration to {new_expiration_timestamp}",
        )
        return updated_user

    def set_account_active_status(
        self,
        actor_user: UserAuthorization,
        target_user_id: str,
        is_active: bool,
    ) -> UserAuthorization:
        """Toggle active status for a customer account."""
        if not actor_user.is_admin:
            raise PermissionError("Only Admin can modify user active status")

        target = self.get_user_authorization(target_user_id)
        if not target:
            raise ValueError(f"User '{target_user_id}' not found")

        if target.is_permanent_admin or target.role == UserRole.ADMIN:
            raise ValueError("Cannot modify active status for protected Admin/Owner account")

        updated_user = UserAuthorization(
            user_id=target.user_id,
            auth_code=target.auth_code,
            telegram_chat_id=target.telegram_chat_id,
            delivery_enabled=target.delivery_enabled,
            allowed_symbols=target.allowed_symbols,
            allowed_strategies=target.allowed_strategies,
            role=target.role,
            permissions=target.permissions,
            detail=f"Status set to active={is_active} by admin",
            password_hash=target.password_hash,
            salt=target.salt,
            is_active=is_active,
            activation_timestamp=target.activation_timestamp,
            expiration_timestamp=target.expiration_timestamp,
            is_permanent_admin=False,
        )
        self.register_user(updated_user)

        self._audit_logger.log(
            user_id=actor_user.user_id,
            event_type="ADMIN_ACTION",
            resource=f"admin.set_active.{target_user_id}",
            action="set_active",
            outcome="ALLOW",
            details=f"Set is_active={is_active}",
        )
        return updated_user

    def list_user_accounts(self, actor_user: UserAuthorization) -> List[UserAuthorization]:
        """List all managed user accounts (Admin only)."""
        if not actor_user.is_admin:
            raise PermissionError("Only Admin can list user accounts")
        return list(self._users_by_id.values())
