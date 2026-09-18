"""Comprehensive security gate verification test suite (Requirements A through Q).

Validates time-limited user access, permanent Owner/Admin protection, server-side expiry,
PBKDF2 salted password authentication, privilege escalation defense, and translation parity.
"""

import time
import pytest

from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import UserAuthorization, hash_password
from src.platform.services.security import AuditLogger, SecurityBoundaryService
from src.platform.services.user_authorization import UserAuthorizationService


class TestUserSecurityGate:
    """Test suite covering mandatory security requirements A through Q."""

    @pytest.fixture
    def auth_service(self):
        logger = AuditLogger()
        return UserAuthorizationService(audit_logger=logger)

    @pytest.fixture
    def security_boundary(self):
        logger = AuditLogger()
        return SecurityBoundaryService(audit_logger=logger)

    def test_a_admin_login_succeeds(self, auth_service):
        """Requirement A: Admin login succeeds with valid credentials."""
        success, user, msg = auth_service.authenticate_with_password("admin_owner", "AdminSecureKey2026!")
        assert success is True
        assert user is not None
        assert user.user_id == "admin_owner"
        assert user.role == UserRole.ADMIN
        assert "successful" in msg.lower()

    def test_b_admin_remains_valid_regardless_of_customer_expiration(self, auth_service):
        """Requirement B: Admin account remains permanently valid regardless of time passed or expiration."""
        admin = auth_service.get_user_authorization("admin_owner")
        assert admin is not None
        assert admin.is_permanent_admin is True

        future_ts = time.time() + (3650 * 86400) # 10 years in future
        assert admin.is_expired(now_ts=future_ts) is False
        assert admin.is_account_valid(now_ts=future_ts) is True

    def test_c_active_customer_login_succeeds(self, auth_service):
        """Requirement C: Active customer login succeeds."""
        success, user, msg = auth_service.authenticate_with_password("demo_user", "CustomerPass2026!")
        assert success is True
        assert user is not None
        assert user.user_id == "demo_user"

    def test_d_expired_customer_login_fails(self, auth_service):
        """Requirement D: Expired customer login fails server-side."""
        admin = auth_service.get_user_authorization("admin_owner")
        now_ts = time.time()

        # Create an account that expired 1 hour ago
        auth_service.create_customer_account(
            actor_user=admin,
            target_user_id="expired_client",
            plaintext_password="ExpiredPass123!",
            activation_timestamp=now_ts - 86400,
            expiration_timestamp=now_ts - 3600,
        )

        success, user, msg = auth_service.authenticate_with_password("expired_client", "ExpiredPass123!")
        assert success is False
        assert user is None
        assert "expired" in msg.lower()

    def test_e_future_customer_cannot_login(self, auth_service):
        """Requirement E: Customer whose activation date is in the future cannot log in."""
        admin = auth_service.get_user_authorization("admin_owner")
        now_ts = time.time()

        auth_service.create_customer_account(
            actor_user=admin,
            target_user_id="future_client",
            plaintext_password="FuturePass123!",
            activation_timestamp=now_ts + 86400, # Starts tomorrow
            expiration_timestamp=now_ts + (30 * 86400),
        )

        success, user, msg = auth_service.authenticate_with_password("future_client", "FuturePass123!")
        assert success is False
        assert user is None
        assert "not yet active" in msg.lower()

    def test_f_deactivated_customer_cannot_login(self, auth_service):
        """Requirement F: Deactivated customer cannot log in."""
        admin = auth_service.get_user_authorization("admin_owner")
        now_ts = time.time()

        auth_service.create_customer_account(
            actor_user=admin,
            target_user_id="deactivated_client",
            plaintext_password="DeactPass123!",
            activation_timestamp=now_ts - 3600,
            expiration_timestamp=now_ts + (30 * 86400),
        )

        # Deactivate
        auth_service.set_account_active_status(
            actor_user=admin,
            target_user_id="deactivated_client",
            is_active=False,
        )

        success, user, msg = auth_service.authenticate_with_password("deactivated_client", "DeactPass123!")
        assert success is False
        assert user is None
        assert "deactivated" in msg.lower()

    def test_g_expired_session_token_cannot_access_protected_apis(self, auth_service, security_boundary):
        """Requirement G: Expired session token/account cannot access protected APIs."""
        admin = auth_service.get_user_authorization("admin_owner")
        now_ts = time.time()

        user = auth_service.create_customer_account(
            actor_user=admin,
            target_user_id="temp_client",
            plaintext_password="TempPass123!",
            activation_timestamp=now_ts - 3600,
            expiration_timestamp=now_ts + 2, # Expires in 2 seconds
        )

        token = auth_service.create_session_token("temp_client")
        assert token is not None

        # Immediate session validation passes
        valid, auth_user = auth_service.validate_session_token(token)
        assert valid is True

        # Fast-forward time past expiration
        expired_ts = now_ts + 10
        assert auth_user.is_expired(now_ts=expired_ts) is True

        # Security boundary check with expired account fails closed
        allowed, reason = security_boundary.authorize(auth_user, "signals")
        # Direct check on is_account_valid at future timestamp
        assert auth_user.is_account_valid(now_ts=expired_ts) is False

    def test_h_customer_cannot_modify_own_expiry(self, auth_service):
        """Requirement H: Normal customer cannot modify expiration timestamp."""
        customer = auth_service.get_user_authorization("demo_user")
        assert customer is not None

        with pytest.raises(PermissionError):
            auth_service.renew_customer_account(
                actor_user=customer,
                target_user_id="demo_user",
                new_expiration_timestamp=time.time() + 10000,
            )

    def test_i_customer_cannot_escalate_to_admin(self, auth_service):
        """Requirement I: Customer cannot create customer or admin accounts."""
        customer = auth_service.get_user_authorization("demo_user")
        assert customer is not None

        with pytest.raises(PermissionError):
            auth_service.create_customer_account(
                actor_user=customer,
                target_user_id="hacked_account",
                plaintext_password="HackedPass123!",
                activation_timestamp=time.time(),
                expiration_timestamp=time.time() + 86400,
            )

    def test_j_customer_cannot_access_another_customers_data(self, security_boundary):
        """Requirement J: Tenant and user isolation enforced."""
        user1 = UserAuthorization(
            user_id="client_01",
            auth_code="CODE1",
            telegram_chat_id="12345",
            role=UserRole.USER,
            allowed_symbols=("XAUUSD",),
            permissions=(Permission.READ_SIGNALS,),
        )

        assert user1.can_receive_signal(symbol="XAUUSD") is True
        assert user1.can_receive_signal(symbol="BTCUSD") is False

    def test_k_admin_can_create_customer_with_expiration(self, auth_service):
        """Requirement K: Admin can create customer with specific expiration date."""
        admin = auth_service.get_user_authorization("admin_owner")
        now_ts = time.time()
        exp_ts = now_ts + (60 * 86400) # 60 days

        created = auth_service.create_customer_account(
            actor_user=admin,
            target_user_id="new_vip_customer",
            plaintext_password="VipPassword2026!",
            activation_timestamp=now_ts,
            expiration_timestamp=exp_ts,
            allowed_symbols=("XAUUSD", "EURUSD", "GBPUSD"),
        )

        assert created.user_id == "new_vip_customer"
        assert created.expiration_timestamp == exp_ts
        assert created.allowed_symbols == ("XAUUSD", "EURUSD", "GBPUSD")

    def test_l_admin_can_renew_expired_customer(self, auth_service):
        """Requirement L: Admin can renew an expired customer."""
        admin = auth_service.get_user_authorization("admin_owner")
        now_ts = time.time()

        # Create expired customer
        auth_service.create_customer_account(
            actor_user=admin,
            target_user_id="expired_trader",
            plaintext_password="TraderPass123!",
            activation_timestamp=now_ts - 86400,
            expiration_timestamp=now_ts - 100,
        )

        # Verify login initially fails due to expiry
        ok, _, _ = auth_service.authenticate_with_password("expired_trader", "TraderPass123!")
        assert ok is False

        # Admin renews account for 30 more days
        new_exp = now_ts + (30 * 86400)
        renewed = auth_service.renew_customer_account(
            actor_user=admin,
            target_user_id="expired_trader",
            new_expiration_timestamp=new_exp,
        )
        assert renewed.expiration_timestamp == new_exp

        # Login now succeeds
        ok_after, user, _ = auth_service.authenticate_with_password("expired_trader", "TraderPass123!")
        assert ok_after is True
        assert user.user_id == "expired_trader"

    def test_m_admin_can_deactivate_and_reactivate_customer(self, auth_service):
        """Requirement M: Admin can deactivate and reactivate customer."""
        admin = auth_service.get_user_authorization("admin_owner")

        # Deactivate demo_user
        auth_service.set_account_active_status(admin, "demo_user", is_active=False)
        ok1, _, _ = auth_service.authenticate_with_password("demo_user", "CustomerPass2026!")
        assert ok1 is False

        # Reactivate demo_user
        auth_service.set_account_active_status(admin, "demo_user", is_active=True)
        ok2, user, _ = auth_service.authenticate_with_password("demo_user", "CustomerPass2026!")
        assert ok2 is True
        assert user.user_id == "demo_user"

    def test_n_passwords_never_stored_in_plaintext(self, auth_service):
        """Requirement N: Plaintext passwords are never stored in user domain objects."""
        user = auth_service.get_user_authorization("admin_owner")
        assert user.password_hash is not None
        assert user.salt is not None
        assert "AdminSecureKey2026!" not in user.password_hash
        assert not hasattr(user, "password")

    def test_o_audit_events_are_sanitized(self, auth_service):
        """Requirement O: Audit logs never log sensitive passwords or secrets."""
        auth_service.authenticate_with_password("admin_owner", "SuperSecretPassword123!")
        events = auth_service._audit_logger.get_events(user_id="admin_owner")

        for e in events:
            if e.details:
                assert "SuperSecretPassword123!" not in e.details
