"""Platform configuration and production security contract.

Provides environment configuration parsing, production secret validation, trusted origin
handling, security header contracts, and safe configuration redaction.
"""

from dataclasses import dataclass, field
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class PlatformConfig:
    """Immutable platform configuration contract for runtime environment settings."""

    app_env: str = "development"
    allowed_origins: Tuple[str, ...] = (
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    )
    session_secret: str = "dev_session_secret_key_change_in_production_2026"
    recovery_email: Optional[str] = None
    owner_user_id: str = "admin_owner"
    owner_email: Optional[str] = None
    persistence_dir: str = ".data"
    session_max_age_seconds: int = 86400
    enable_https_redirect: bool = False
    initial_admin_password: Optional[str] = None

    # Transactional Email Delivery configuration
    email_provider: str = "none"
    email_host: str = "localhost"
    email_port: int = 587
    email_username: Optional[str] = None
    email_password: Optional[str] = None
    email_from: Optional[str] = None
    email_use_tls: bool = True
    public_base_url: str = "http://localhost:3000"

    def __post_init__(self) -> None:
        clean_env = self.app_env.strip().lower()
        if clean_env not in ("development", "testing", "production"):
            raise ValueError(f"Invalid APP_ENV '{self.app_env}'. Must be 'development', 'testing', or 'production'.")
        object.__setattr__(self, "app_env", clean_env)

        if not isinstance(self.allowed_origins, (tuple, list)):
            raise ValueError("allowed_origins must be a tuple or list of strings")
        clean_origins = tuple(o.strip() for o in self.allowed_origins if isinstance(o, str) and o.strip())
        object.__setattr__(self, "allowed_origins", clean_origins)

        if not isinstance(self.session_secret, str) or not self.session_secret.strip():
            raise ValueError("session_secret must be a non-empty string")
        object.__setattr__(self, "session_secret", self.session_secret.strip())

        # Enforce fail-closed security for production
        if clean_env == "production":
            if self.session_secret in (
                "dev_session_secret_key_change_in_production_2026",
                "secret",
                "changeme",
                "password",
            ) or len(self.session_secret) < 32:
                raise ValueError("SESSION_SECRET must be explicitly set to a strong key (at least 32 chars) in production.")

        if self.recovery_email is not None:
            clean_email = self.recovery_email.strip().lower()
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", clean_email):
                raise ValueError(f"Invalid recovery_email format: '{self.recovery_email}'")
            object.__setattr__(self, "recovery_email", clean_email)

        if self.owner_email is not None:
            clean_o_email = self.owner_email.strip().lower()
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", clean_o_email):
                raise ValueError(f"Invalid owner_email format: '{self.owner_email}'")
            object.__setattr__(self, "owner_email", clean_o_email)
        elif self.recovery_email is not None:
            object.__setattr__(self, "owner_email", self.recovery_email)

        if not isinstance(self.owner_user_id, str) or not self.owner_user_id.strip():
            object.__setattr__(self, "owner_user_id", "admin_owner")
        else:
            object.__setattr__(self, "owner_user_id", self.owner_user_id.strip())

        clean_provider = self.email_provider.strip().lower() if isinstance(self.email_provider, str) else "none"
        object.__setattr__(self, "email_provider", clean_provider)

        if self.email_from is not None:
            clean_from = self.email_from.strip().lower()
            if clean_from and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", clean_from):
                raise ValueError(f"Invalid email_from format: '{self.email_from}'")
            object.__setattr__(self, "email_from", clean_from if clean_from else None)

        if not isinstance(self.public_base_url, str) or not self.public_base_url.strip():
            object.__setattr__(self, "public_base_url", "http://localhost:3000")
        else:
            object.__setattr__(self, "public_base_url", self.public_base_url.strip().rstrip("/"))

        if not isinstance(self.persistence_dir, str) or not self.persistence_dir.strip():
            raise ValueError("persistence_dir must be a non-empty string")
        object.__setattr__(self, "persistence_dir", self.persistence_dir.strip())

        if not isinstance(self.session_max_age_seconds, int) or self.session_max_age_seconds <= 0:
            raise ValueError("session_max_age_seconds must be a positive integer")

    @property
    def is_production(self) -> bool:
        """Return True if running in production mode."""
        return self.app_env == "production"

    def get_security_headers(self) -> Dict[str, str]:
        """Return production HTTP security headers contract."""
        headers = {
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "connect-src 'self' http: https:;"
            ),
        }
        if self.is_production or self.enable_https_redirect:
            headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return headers

    def is_origin_allowed(self, origin: str) -> bool:
        """Verify if a given origin is in the trusted origins whitelist."""
        if not origin or not isinstance(origin, str):
            return False
        clean_origin = origin.strip().rstrip("/")
        for allowed in self.allowed_origins:
            if allowed.rstrip("/") == clean_origin:
                return True
        return False

    def to_sanitized_dict(self) -> Dict[str, Any]:
        """Return configuration dictionary with sensitive secrets redacted."""
        return {
            "app_env": self.app_env,
            "allowed_origins": list(self.allowed_origins),
            "session_secret": "[REDACTED]",
            "initial_admin_password": "[REDACTED]" if self.initial_admin_password else None,
            "recovery_email": self.recovery_email,
            "owner_user_id": self.owner_user_id,
            "owner_email": self.owner_email,
            "email_provider": self.email_provider,
            "email_host": self.email_host,
            "email_port": self.email_port,
            "email_username": self.email_username,
            "email_password": "[REDACTED]" if self.email_password else None,
            "email_from": self.email_from,
            "email_use_tls": self.email_use_tls,
            "public_base_url": self.public_base_url,
            "persistence_dir": self.persistence_dir,
            "session_max_age_seconds": self.session_max_age_seconds,
            "enable_https_redirect": self.enable_https_redirect,
            "is_production": self.is_production,
        }

    @classmethod
    def load_from_env(cls) -> "PlatformConfig":
        """Factory method to load PlatformConfig from environment variables."""
        env_name = os.getenv("APP_ENV", "development").strip().lower()

        raw_origins = os.getenv("ALLOWED_ORIGINS", "")
        if raw_origins.strip():
            origins = tuple(o.strip() for o in raw_origins.split(",") if o.strip())
        else:
            origins = (
                "http://localhost:5173",
                "http://localhost:3000",
                "http://127.0.0.1:5173",
                "http://127.0.0.1:3000",
            )

        secret = os.getenv("SESSION_SECRET", "dev_session_secret_key_change_in_production_2026")
        email = os.getenv("RECOVERY_EMAIL", None)
        o_user_id = os.getenv("OWNER_USER_ID", "admin_owner")
        o_email = os.getenv("OWNER_EMAIL", email)
        p_dir = os.getenv("PERSISTENCE_DIR", ".data")
        max_age_str = os.getenv("SESSION_MAX_AGE_SECONDS", "86400")
        try:
            max_age = int(max_age_str)
        except ValueError:
            max_age = 86400

        https_redirect = os.getenv("ENABLE_HTTPS_REDIRECT", "false").lower() in ("true", "1", "yes")
        admin_pwd = os.getenv("INITIAL_ADMIN_PASSWORD", None)

        e_provider = os.getenv("EMAIL_PROVIDER", "none")
        e_host = os.getenv("EMAIL_HOST", "localhost")
        try:
            e_port = int(os.getenv("EMAIL_PORT", "587"))
        except ValueError:
            e_port = 587
        e_username = os.getenv("EMAIL_USERNAME", None)
        e_password = os.getenv("EMAIL_PASSWORD", None)
        e_from = os.getenv("EMAIL_FROM", None)
        e_use_tls = os.getenv("EMAIL_USE_TLS", "true").lower() in ("true", "1", "yes")
        public_url = os.getenv("PUBLIC_BASE_URL", "http://localhost:3000")

        return cls(
            app_env=env_name,
            allowed_origins=origins,
            session_secret=secret,
            recovery_email=email,
            owner_user_id=o_user_id,
            owner_email=o_email,
            persistence_dir=p_dir,
            session_max_age_seconds=max_age,
            enable_https_redirect=https_redirect,
            initial_admin_password=admin_pwd,
            email_provider=e_provider,
            email_host=e_host,
            email_port=e_port,
            email_username=e_username,
            email_password=e_password,
            email_from=e_from,
            email_use_tls=e_use_tls,
            public_base_url=public_url,
        )
