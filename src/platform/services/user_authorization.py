"""User authorization application service (Part 19: Host Application & Access Control).

Manages user authorization identity registrations, credential code lookups,
and signal delivery policy evaluation.
"""

from typing import Dict, Optional, Tuple

from src.platform.domain.user_authorization import UserAuthorization


class UserAuthorizationService:
    """Application service for managing user authorization and signal delivery permissions."""

    def __init__(self) -> None:
        self._users_by_id: Dict[str, UserAuthorization] = {}
        self._users_by_code: Dict[str, UserAuthorization] = {}

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
