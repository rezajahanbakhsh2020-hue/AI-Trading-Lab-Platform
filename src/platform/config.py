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
    persistence_dir: str = ".data"
    session_max_age_seconds: int = 86400
    enable_https_redirect: bool = False
    initial_admin_password: Optional[str] = None

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
            "recovery_email": self.recovery_email,
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
        p_dir = os.getenv("PERSISTENCE_DIR", ".data")
        max_age_str = os.getenv("SESSION_MAX_AGE_SECONDS", "86400")
        try:
            max_age = int(max_age_str)
        except ValueError:
            max_age = 86400

        https_redirect = os.getenv("ENABLE_HTTPS_REDIRECT", "false").lower() in ("true", "1", "yes")
        admin_pwd = os.getenv("INITIAL_ADMIN_PASSWORD", None)

        return cls(
            app_env=env_name,
            allowed_origins=origins,
            session_secret=secret,
            recovery_email=email,
            persistence_dir=p_dir,
            session_max_age_seconds=max_age,
            enable_https_redirect=https_redirect,
            initial_admin_password=admin_pwd,
        )
