"""User authorization service implementation (Part 19: Host Application & Access Control).

Provides user authorization lookup, password authentication, session token management,
customer lifecycle management (create, renew, toggle active status, password reset),
and administrative access management with audit logging.
"""

import hashlib
import os
import secrets
import time
from typing import Any, Dict, List, Optional, Tuple, Union

def hash_token(token: str) -> str:
    """Hash a session token using SHA-256 for secure non-reversible storage."""
    if not isinstance(token, str) or not token:
        raise ValueError("Token must be a non-empty string")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import UserAuthorization, hash_password
from src.platform.services.security import AuditLogger
from src.platform.adapters.user_repository import UserRepositoryPort


class UserAuthorizationService:
    """Service managing user authorization records, authentication, sessions, and customer lifecycle."""

    def __init__(
        self,
        audit_logger: Optional[AuditLogger] = None,
        repository: Optional[UserRepositoryPort] = None,
        config: Optional[Any] = None,
        email_service: Optional[Any] = None,
    ) -> None:
        self._users_by_id: Dict[str, UserAuthorization] = {}
        self._users_by_code: Dict[str, UserAuthorization] = {}
        self._sessions: Dict[str, Tuple[str, float]] = {}  # token_hash -> (user_id, creation_ts)
        self._audit_logger = audit_logger or AuditLogger()
        self._repository = repository
        self._config = config
        self._email_service = email_service
        self._load_from_repository()
        self._initialize_default_users(config=config)

    def _load_from_repository(self) -> None:
        """Load persisted users and active sessions from repository if present."""
        if not self._repository:
            return
        persisted_users = self._repository.list_users()
        for user in persisted_users:
            self._users_by_id[user.user_id] = user
            self._users_by_code[user.auth_code] = user
        self._sessions = self._repository.list_sessions()

    def _initialize_default_users(self, config: Optional[Any] = None) -> None:
        """Initialize permanent owner/admin without hardcoded production credentials.

        In production mode (`APP_ENV=production`), the initial Owner account MUST be bootstrapped
        via operator-supplied `INITIAL_ADMIN_PASSWORD` or existing persisted store.
        If unprovisioned in production, fails closed to prevent unauthenticated/default access.
        """
        app_env = getattr(config, "app_env", "development") if config else os.getenv("APP_ENV", "development").lower()
        init_pwd = getattr(config, "initial_admin_password", None) or os.getenv("INITIAL_ADMIN_PASSWORD")
        owner_id = getattr(config, "owner_user_id", None) or os.getenv("OWNER_USER_ID", "admin_owner")
        owner_email = getattr(config, "owner_email", None) or os.getenv("OWNER_EMAIL") or os.getenv("RECOVERY_EMAIL")

        if owner_id not in self._users_by_id and "admin_owner" not in self._users_by_id:
            if app_env == "production":
                if not init_pwd:
                    raise RuntimeError("Production startup failed: Owner/Admin account not provisioned and INITIAL_ADMIN_PASSWORD is not set.")
                pwd_to_use = init_pwd
            else:
                pwd_to_use = init_pwd or "DevAdminSecureKey2026!"

            admin_hash, admin_salt = hash_password(pwd_to_use)
            admin_user = UserAuthorization(
                user_id=owner_id,
                auth_code="AUTH_ADMIN_PROVISIONED",
                role=UserRole.OWNER,
                password_hash=admin_hash,
                salt=admin_salt,
                is_permanent_admin=True,
                recovery_email=owner_email,
                detail="Permanent protected Owner account",
            )
            self.register_user(admin_user)
        else:
            # If owner account already exists in repository, update recovery email if configured
            existing_owner_id = owner_id if owner_id in self._users_by_id else "admin_owner"
            existing_owner = self._users_by_id[existing_owner_id]
            if owner_email and existing_owner.recovery_email != owner_email:
                updated_owner = UserAuthorization(
                    user_id=existing_owner.user_id,
                    auth_code=existing_owner.auth_code,
                    telegram_chat_id=existing_owner.telegram_chat_id,
                    delivery_enabled=existing_owner.delivery_enabled,
                    allowed_symbols=existing_owner.allowed_symbols,
                    allowed_strategies=existing_owner.allowed_strategies,
                    role=UserRole.OWNER,
                    permissions=existing_owner.permissions,
                    detail=existing_owner.detail,
                    password_hash=existing_owner.password_hash,
                    salt=existing_owner.salt,
                    is_active=existing_owner.is_active,
                    activation_timestamp=existing_owner.activation_timestamp,
                    expiration_timestamp=existing_owner.expiration_timestamp,
                    is_permanent_admin=True,
                    recovery_email=owner_email,
                    recovery_token_hash=existing_owner.recovery_token_hash,
                    recovery_token_expiration=existing_owner.recovery_token_expiration,
                )
                self.register_user(updated_owner)

        if "demo_user" not in self._users_by_id and app_env != "production":
            user_hash, user_salt = hash_password("DevCustomerPass2026!")
            now_ts = time.time()
            default_customer = UserAuthorization(
                user_id="demo_user",
                auth_code="AUTH_USER_DEV",
                role=UserRole.CUSTOMER,
                allowed_symbols=("XAUUSD", "EURUSD"),
                password_hash=user_hash,
                salt=user_salt,
                is_active=True,
                activation_timestamp=now_ts - 3600,
                expiration_timestamp=now_ts + (30 * 86400),
                detail="Development demo customer account",
            )
            self.register_user(default_customer)

    def register_user(self, user: UserAuthorization) -> None:
        """Register or update a user authorization entry."""
        if not isinstance(user, UserAuthorization):
            raise ValueError("user must be a UserAuthorization instance")
        self._users_by_id[user.user_id] = user
        self._users_by_code[user.auth_code] = user
        if self._repository:
            self._repository.save_user(user)

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
            self._audit_logger.log(
                user_id=user_id or "unknown",
                event_type="AUTH_FAILED",
                resource="auth.login",
                action="login",
                outcome="DENY",
                details="User account not found",
            )
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
        if not user.is_permanent_admin and user.role not in (UserRole.OWNER, UserRole.ADMIN):
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

    def create_session_token(self, user_id: str, max_age_seconds: float = 86400) -> Optional[str]:
        """Generate a secure session token for an authenticated valid account."""
        user = self.get_user_authorization(user_id)
        if not user or not user.is_account_valid():
            return None
        token = f"sess_{secrets.token_urlsafe(32)}"
        token_h = hash_token(token)
        created_ts = time.time()
        self._sessions[token_h] = (user.user_id, created_ts)
        if self._repository:
            self._repository.save_session(token_h, user.user_id, created_ts)
        return token

    def validate_session_token(self, token: str, max_age_seconds: float = 86400) -> Tuple[bool, Optional[UserAuthorization]]:
        """Validate session token using SHA-256 token hash lookup and re-verify server-side account status in real-time."""
        if not token:
            return False, None
        token_h = hash_token(token)
        if token_h not in self._sessions:
            return False, None
        user_id, created_ts = self._sessions[token_h]
        now_ts = time.time()
        if now_ts - created_ts > max_age_seconds:
            del self._sessions[token_h]
            if self._repository:
                self._repository.delete_session(token_h)
            return False, None
        user = self.get_user_authorization(user_id)
        if not user or not user.is_account_valid():
            if token_h in self._sessions:
                del self._sessions[token_h]
                if self._repository:
                    self._repository.delete_session(token_h)
            return False, None
        return True, user

    def request_password_recovery(
        self, user_id: str, recovery_email: str
    ) -> Dict[str, Any]:
        """Initiate password recovery flow. Generates a token contract and dispatches via EmailDeliveryService if configured.

        Exposes honest delivery state ('SENT', 'NOT_CONFIGURED', 'DELIVERY_FAILED') and supports user enumeration defense.

        Returns:
            Dict containing success, message, delivery_status, and recovery_token (omitted/None if email is sent externally).
        """
        user = self.get_user_authorization(user_id)
        generic_msg = "If the user account and recovery email match our records, a recovery token contract has been created."

        if not user or not user.is_account_valid():
            self._audit_logger.log(
                user_id=user_id or "unknown",
                event_type="AUTH_RECOVERY_REQUESTED",
                resource="auth.recovery",
                action="request_recovery",
                outcome="DENY",
                details="Recovery request for non-existent or invalid account",
            )
            return {
                "success": True,
                "message": generic_msg,
                "delivery_status": "NOT_CONFIGURED",
                "delivery_detail": "External email provider is not configured. Token generated for direct operator/modal presentation.",
                "recovery_token": None,
            }

        # Validate recovery_email if account has one configured, otherwise set it
        if user.recovery_email and user.recovery_email.lower() != recovery_email.strip().lower():
            self._audit_logger.log(
                user_id=user.user_id,
                event_type="AUTH_RECOVERY_REQUESTED",
                resource="auth.recovery",
                action="request_recovery",
                outcome="DENY",
                details="Recovery email mismatch",
            )
            return {
                "success": True,
                "message": generic_msg,
                "delivery_status": "NOT_CONFIGURED",
                "delivery_detail": "External email provider is not configured.",
                "recovery_token": None,
            }

        recovery_token = f"rec_{secrets.token_urlsafe(24)}"
        token_hash = hash_token(recovery_token)
        expiration = time.time() + 3600  # 1 hour validity

        updated_user = UserAuthorization(
            user_id=user.user_id,
            auth_code=user.auth_code,
            telegram_chat_id=user.telegram_chat_id,
            delivery_enabled=user.delivery_enabled,
            allowed_symbols=user.allowed_symbols,
            allowed_strategies=user.allowed_strategies,
            role=user.role,
            permissions=user.permissions,
            detail=user.detail,
            password_hash=user.password_hash,
            salt=user.salt,
            is_active=user.is_active,
            activation_timestamp=user.activation_timestamp,
            expiration_timestamp=user.expiration_timestamp,
            is_permanent_admin=user.is_permanent_admin,
            recovery_email=recovery_email.strip().lower(),
            recovery_token_hash=token_hash,
            recovery_token_expiration=expiration,
        )
        self.register_user(updated_user)

        self._audit_logger.log(
            user_id=user.user_id,
            event_type="AUTH_RECOVERY_REQUESTED",
            resource="auth.recovery",
            action="request_recovery",
            outcome="ALLOW",
            details="Password recovery token generated for user",
        )

        delivery_status = "NOT_CONFIGURED"
        delivery_detail = "External email delivery is Not Configured. Recovery token is available for immediate presentation."
        returned_token: Optional[str] = recovery_token

        if self._email_service is not None:
            email_res = self._email_service.send_recovery_email(
                to_email=recovery_email.strip().lower(),
                user_id=user.user_id,
                recovery_token=recovery_token,
            )
            delivery_status = email_res.status_code
            delivery_detail = email_res.reason or email_res.detail or ""
            if email_res.success and email_res.externally_delivered:
                # Omit recovery token from public response when delivered via real external email
                returned_token = None
                delivery_detail = "Recovery instructions dispatched to user email."

        return {
            "success": True,
            "message": generic_msg,
            "delivery_status": delivery_status,
            "delivery_detail": delivery_detail,
            "recovery_token": returned_token,
        }

    def reset_password_with_recovery_token(
        self, user_id: str, recovery_token: str, new_password: str
    ) -> Tuple[bool, str]:
        """Reset user password using a valid, non-expired recovery token and revoke existing active user sessions."""
        user = self.get_user_authorization(user_id)
        if not user or not user.recovery_token_hash or not user.recovery_token_expiration:
            return False, "No active recovery request found"

        now_ts = time.time()
        if now_ts >= user.recovery_token_expiration:
            return False, "Recovery token has expired"

        candidate_hash = hash_token(recovery_token)
        if not secrets.compare_digest(user.recovery_token_hash, candidate_hash):
            self._audit_logger.log(
                user_id=user.user_id,
                event_type="AUTH_RECOVERY_FAILED",
                resource="auth.recovery",
                action="reset_password",
                outcome="DENY",
                details="Invalid recovery token",
            )
            return False, "Invalid recovery token"

        if not new_password or len(new_password) < 6:
            return False, "New password must be at least 6 characters long"

        new_hash, new_salt = hash_password(new_password)
        updated_user = UserAuthorization(
            user_id=user.user_id,
            auth_code=user.auth_code,
            telegram_chat_id=user.telegram_chat_id,
            delivery_enabled=user.delivery_enabled,
            allowed_symbols=user.allowed_symbols,
            allowed_strategies=user.allowed_strategies,
            role=user.role,
            permissions=user.permissions,
            detail="Password reset via recovery token",
            password_hash=new_hash,
            salt=new_salt,
            is_active=user.is_active,
            activation_timestamp=user.activation_timestamp,
            expiration_timestamp=user.expiration_timestamp,
            is_permanent_admin=user.is_permanent_admin,
            recovery_email=user.recovery_email,
            recovery_token_hash=None,
            recovery_token_expiration=None,
        )
        self.register_user(updated_user)

        # Invalidate all active sessions for this user post-password reset
        revoked_sessions = self.revoke_user_sessions(updated_user, updated_user.user_id)

        self._audit_logger.log(
            user_id=user.user_id,
            event_type="AUTH_RECOVERY_SUCCESS",
            resource="auth.recovery",
            action="reset_password",
            outcome="ALLOW",
            details=f"Password reset completed via recovery token. Revoked {revoked_sessions} session(s).",
        )
        return True, "Password reset successful"

    def revoke_session_token(self, token: str) -> bool:
        """Revoke active session token (explicit logout)."""
        if not token:
            return False
        token_h = hash_token(token)
        if token_h in self._sessions:
            uid, _ = self._sessions[token_h]
            del self._sessions[token_h]
            if self._repository:
                self._repository.delete_session(token_h)
            self._audit_logger.log(
                user_id=uid,
                event_type="LOGOUT",
                resource="auth.session",
                action="logout",
                outcome="ALLOW",
                details="Session token revoked and invalidated",
            )
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
        role: UserRole = UserRole.CUSTOMER,
        detail: Optional[str] = None,
    ) -> UserAuthorization:
        """Create new account with activation and expiration timestamps."""
        if not actor_user.is_admin:
            raise PermissionError("Only Admin can create customer accounts")

        target_user_id = target_user_id.strip()
        if target_user_id in self._users_by_id:
            raise ValueError(f"User ID '{target_user_id}' already exists")

        if expiration_timestamp <= activation_timestamp:
            raise ValueError("Expiration timestamp must be strictly greater than activation timestamp")

        p_hash, salt = hash_password(plaintext_password)
        auth_code = f"AUTH_{secrets.token_hex(8).upper()}"

        clean_role = role
        if isinstance(role, str):
            clean_role = UserRole(role.lower().strip())

        new_user = UserAuthorization(
            user_id=target_user_id,
            auth_code=auth_code,
            role=clean_role,
            allowed_symbols=allowed_symbols,
            password_hash=p_hash,
            salt=salt,
            is_active=True,
            activation_timestamp=activation_timestamp,
            expiration_timestamp=expiration_timestamp,
            is_permanent_admin=clean_role in (UserRole.OWNER, UserRole.ADMIN),
            detail=detail or f"Account created by {actor_user.user_id}",
        )
        self.register_user(new_user)

        self._audit_logger.log(
            user_id=actor_user.user_id,
            event_type="ADMIN_ACTION",
            resource=f"admin.create_user.{target_user_id}",
            action="create_user",
            outcome="ALLOW",
            details=f"Created account role={clean_role.value} active from {activation_timestamp} to {expiration_timestamp}",
        )
        return new_user

    def renew_customer_account(
        self,
        actor_user: UserAuthorization,
        target_user_id: str,
        new_expiration_timestamp: float,
    ) -> UserAuthorization:
        """Renew/extend expiration timestamp for an account."""
        if not actor_user.is_admin:
            raise PermissionError("Only Admin can renew customer accounts")

        target = self.get_user_authorization(target_user_id)
        if not target:
            raise ValueError(f"User '{target_user_id}' not found")

        if target.is_permanent_admin or target.role in (UserRole.OWNER, UserRole.ADMIN):
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
        """Toggle active status for an account. Revokes sessions if deactivated."""
        if not actor_user.is_admin:
            raise PermissionError("Only Admin can modify user active status")

        target = self.get_user_authorization(target_user_id)
        if not target:
            raise ValueError(f"User '{target_user_id}' not found")

        if target.is_permanent_admin or target.role in (UserRole.OWNER, UserRole.ADMIN):
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
            recovery_email=target.recovery_email,
        )
        self.register_user(updated_user)

        # If deactivating, immediately revoke active sessions for this target user
        if not is_active:
            self.revoke_user_sessions(actor_user, target.user_id)

        self._audit_logger.log(
            user_id=actor_user.user_id,
            event_type="ADMIN_ACTION",
            resource=f"admin.set_active.{target_user_id}",
            action="deactivate" if not is_active else "reactivate",
            outcome="ALLOW",
            details=f"Set is_active={is_active}",
        )

        # Notify user via email if email service and recovery email exist
        if self._email_service is not None and target.recovery_email:
            action_str = "Reactivated" if is_active else "Deactivated"
            try:
                self._email_service.send_security_notification(
                    to_email=target.recovery_email,
                    title=f"Account {action_str}",
                    message=f"Your account status was changed to active={is_active} by administrator {actor_user.user_id}.",
                    details={"target_user_id": target.user_id, "is_active": is_active, "actor_user_id": actor_user.user_id},
                )
            except Exception:
                pass

        return updated_user

    def deactivate_user_account(
        self, actor_user: UserAuthorization, target_user_id: str
    ) -> UserAuthorization:
        """Explicitly deactivate a user account and revoke all active sessions."""
        return self.set_account_active_status(actor_user, target_user_id, is_active=False)

    def reactivate_user_account(
        self, actor_user: UserAuthorization, target_user_id: str
    ) -> UserAuthorization:
        """Explicitly reactivate a user account."""
        return self.set_account_active_status(actor_user, target_user_id, is_active=True)

    def list_user_accounts(self, actor_user: UserAuthorization) -> List[UserAuthorization]:
        """List all managed user accounts (Owner/Admin only)."""
        if not actor_user.is_admin:
            raise PermissionError("Only Admin can list user accounts")
        return list(self._users_by_id.values())

    def update_user_role(
        self,
        actor_user: UserAuthorization,
        target_user_id: str,
        new_role: Union[UserRole, str],
    ) -> UserAuthorization:
        """Update role of a target user enforcing strict RBAC rules.

        Rules:
        - Owner can assign/revoke any role.
        - Admin cannot promote anyone to Owner or Admin, nor demote/modify Owner or other Admin accounts.
        - Non-admins cannot alter roles.
        """
        if not actor_user.is_admin and not actor_user.is_owner:
            raise PermissionError("Only Admin or Owner can update user roles")

        target = self.get_user_authorization(target_user_id)
        if not target:
            raise ValueError(f"User '{target_user_id}' not found")

        clean_new_role = new_role if isinstance(new_role, UserRole) else UserRole(str(new_role).lower().strip())

        # Admin privilege restrictions
        if not actor_user.is_owner:
            if target.is_owner or target.role == UserRole.OWNER:
                raise PermissionError("Admin cannot modify Owner accounts")
            if target.is_admin or target.role == UserRole.ADMIN:
                raise PermissionError("Admin cannot modify other Admin accounts")
            if clean_new_role in (UserRole.OWNER, UserRole.ADMIN):
                raise PermissionError("Admin cannot promote accounts to Admin or Owner")

        if target.is_permanent_admin and clean_new_role not in (UserRole.OWNER, UserRole.ADMIN):
            if not actor_user.is_owner:
                raise PermissionError("Cannot revoke permanent admin status")

        updated_user = UserAuthorization(
            user_id=target.user_id,
            auth_code=target.auth_code,
            telegram_chat_id=target.telegram_chat_id,
            delivery_enabled=target.delivery_enabled,
            allowed_symbols=target.allowed_symbols,
            allowed_strategies=target.allowed_strategies,
            role=clean_new_role,
            detail=f"Role changed to '{clean_new_role.value}' by {actor_user.user_id}",
            password_hash=target.password_hash,
            salt=target.salt,
            is_active=target.is_active,
            activation_timestamp=target.activation_timestamp,
            expiration_timestamp=target.expiration_timestamp,
            is_permanent_admin=clean_new_role in (UserRole.OWNER, UserRole.ADMIN),
            recovery_email=target.recovery_email,
        )
        self.register_user(updated_user)

        self._audit_logger.log(
            user_id=actor_user.user_id,
            event_type="ADMIN_ACTION",
            resource=f"admin.update_role.{target_user_id}",
            action="update_role",
            outcome="ALLOW",
            details=f"Updated role of {target_user_id} from {target.role.value} to {clean_new_role.value}",
        )

        # Notify user via email if email service and recovery email exist
        if self._email_service is not None and target.recovery_email:
            try:
                self._email_service.send_security_notification(
                    to_email=target.recovery_email,
                    title="Account Role Updated",
                    message=f"Your account role was updated to '{clean_new_role.value}' by administrator {actor_user.user_id}.",
                    details={"target_user_id": target.user_id, "new_role": clean_new_role.value, "actor_user_id": actor_user.user_id},
                )
            except Exception:
                pass

        return updated_user

    def update_user_profile(
        self,
        actor_user: UserAuthorization,
        target_user_id: str,
        allowed_symbols: Optional[Tuple[str, ...]] = None,
        telegram_chat_id: Optional[str] = None,
        delivery_enabled: Optional[bool] = None,
        detail: Optional[str] = None,
    ) -> UserAuthorization:
        """Update permitted profile/settings fields for self or target user (Admin only for cross-user)."""
        clean_target = target_user_id.strip()
        if not actor_user.is_admin and actor_user.user_id != clean_target:
            raise PermissionError("Access denied: cannot modify profile of another user")

        target = self.get_user_authorization(clean_target)
        if not target:
            raise ValueError(f"User '{clean_target}' not found")

        # Non-admin users cannot change their own allowed_symbols if updated
        new_symbols = target.allowed_symbols
        if allowed_symbols is not None:
            if not actor_user.is_admin and actor_user.user_id == clean_target:
                pass  # Keep existing allowed_symbols for customer self-update
            else:
                new_symbols = allowed_symbols

        new_chat_id = telegram_chat_id if telegram_chat_id is not None else target.telegram_chat_id
        new_delivery = delivery_enabled if delivery_enabled is not None else target.delivery_enabled
        new_detail = detail if detail is not None else target.detail

        updated_user = UserAuthorization(
            user_id=target.user_id,
            auth_code=target.auth_code,
            telegram_chat_id=new_chat_id,
            delivery_enabled=new_delivery,
            allowed_symbols=new_symbols,
            allowed_strategies=target.allowed_strategies,
            role=target.role,
            permissions=target.permissions,
            detail=new_detail,
            password_hash=target.password_hash,
            salt=target.salt,
            is_active=target.is_active,
            activation_timestamp=target.activation_timestamp,
            expiration_timestamp=target.expiration_timestamp,
            is_permanent_admin=target.is_permanent_admin,
            recovery_email=target.recovery_email,
        )
        self.register_user(updated_user)

        self._audit_logger.log(
            user_id=actor_user.user_id,
            event_type="PROFILE_UPDATE",
            resource=f"user.profile.{clean_target}",
            action="update_profile",
            outcome="ALLOW",
            details=f"Updated profile fields for user '{clean_target}'",
        )
        return updated_user

    def revoke_user_sessions(
        self,
        actor_user: UserAuthorization,
        target_user_id: str,
    ) -> int:
        """Revoke all active session tokens for target user (Admin or Self)."""
        clean_target = target_user_id.strip()
        if not actor_user.is_admin and actor_user.user_id != clean_target:
            raise PermissionError("Access denied: cannot revoke sessions of another user")

        target = self.get_user_authorization(clean_target)
        if not target:
            raise ValueError(f"User '{clean_target}' not found")

        revoked_count = 0
        tokens_to_delete = [
            token_h for token_h, (uid, _) in self._sessions.items() if uid == clean_target
        ]

        for token_h in tokens_to_delete:
            del self._sessions[token_h]
            if self._repository:
                self._repository.delete_session(token_h)
            revoked_count += 1

        self._audit_logger.log(
            user_id=actor_user.user_id,
            event_type="SESSION_REVOKED",
            resource=f"auth.sessions.{clean_target}",
            action="revoke_sessions",
            outcome="ALLOW",
            details=f"Revoked {revoked_count} active session(s) for user '{clean_target}'",
        )
        return revoked_count
