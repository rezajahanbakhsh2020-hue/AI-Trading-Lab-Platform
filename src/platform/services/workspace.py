"""Workspace application service and persistence repository port/adapter.

Implements Hexagonal Architecture port (WorkspaceRepositoryPort), in-memory adapter
(InMemoryWorkspaceRepository), and application service (WorkspaceService) with
security boundary authorization and user isolation.
"""

from abc import ABC, abstractmethod
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

from src.platform.domain.notification import NotificationPreferences
from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.domain.workspace import Watchlist, Workspace
from src.platform.services.security import SecurityBoundaryService


class WorkspaceRepositoryPort(ABC):
    """Port interface for persisting and retrieving user workspaces."""

    @abstractmethod
    def get_workspace(self, user_id: str) -> Optional[Workspace]:
        """Retrieve workspace for a given user_id."""
        pass

    @abstractmethod
    def save_workspace(self, workspace: Workspace) -> Workspace:
        """Save or update workspace for a user."""
        pass

    @abstractmethod
    def delete_workspace(self, user_id: str) -> bool:
        """Delete workspace for a given user_id."""
        pass


class InMemoryWorkspaceRepository(WorkspaceRepositoryPort):
    """In-memory implementation of WorkspaceRepositoryPort."""

    def __init__(self) -> None:
        self._store: Dict[str, Workspace] = {}

    def get_workspace(self, user_id: str) -> Optional[Workspace]:
        if not isinstance(user_id, str) or not user_id.strip():
            return None
        return self._store.get(user_id.strip())

    def save_workspace(self, workspace: Workspace) -> Workspace:
        if not isinstance(workspace, Workspace):
            raise ValueError("workspace must be a Workspace instance")
        self._store[workspace.user_id] = workspace
        return workspace

    def delete_workspace(self, user_id: str) -> bool:
        if not isinstance(user_id, str) or not user_id.strip():
            return False
        clean_uid = user_id.strip()
        if clean_uid in self._store:
            del self._store[clean_uid]
            return True
        return False

    def clear(self) -> None:
        self._store.clear()


class WorkspaceService:
    """Application Service for managing user workspaces and watchlists safely."""

    def __init__(
        self,
        repository: Optional[WorkspaceRepositoryPort] = None,
        security_service: Optional[SecurityBoundaryService] = None,
    ) -> None:
        self._repo = repository or InMemoryWorkspaceRepository()
        self._security = security_service or SecurityBoundaryService()

    def _authorize_user_access(
        self, requester: Optional[UserAuthorization], target_user_id: str, action: str = "read"
    ) -> None:
        """Enforce role & user isolation security rules."""
        if not isinstance(target_user_id, str) or not target_user_id.strip():
            raise ValueError("target_user_id must be a non-empty string")
        clean_target = target_user_id.strip()

        # Authorize against security boundary first
        allowed, reason = self._security.authorize(
            user=requester,
            resource="workspace",
            action=action,
        )
        if not allowed:
            raise PermissionError(reason)

        assert requester is not None  # Guaranteed by authorize

        # User Isolation rule: user can only access their own workspace unless Admin
        if not requester.is_admin and requester.user_id != clean_target:
            self._security.audit_logger.log(
                user_id=requester.user_id,
                event_type="UNAUTHORIZED_CROSS_USER_ACCESS",
                resource=f"workspace:{clean_target}",
                action=action,
                outcome="DENY",
                details=f"User '{requester.user_id}' attempted cross-user access to target user '{clean_target}'",
            )
            raise PermissionError(
                f"Access denied: user '{requester.user_id}' is not authorized to access workspace of user '{clean_target}'"
            )

    def get_or_create_workspace(
        self, requester: Optional[UserAuthorization], target_user_id: str
    ) -> Workspace:
        """Get workspace for user, creating a default one if none exists yet."""
        clean_target = target_user_id.strip() if isinstance(target_user_id, str) else ""
        self._authorize_user_access(requester, clean_target, action="get_workspace")

        ws = self._repo.get_workspace(clean_target)
        if ws is None:
            ws = Workspace.create_default(clean_target)
            self._repo.save_workspace(ws)

        return ws

    def set_active_symbol(
        self, requester: Optional[UserAuthorization], target_user_id: str, symbol: str
    ) -> Workspace:
        """Set active symbol in workspace."""
        ws = self.get_or_create_workspace(requester, target_user_id)
        updated = ws.with_active_symbol(symbol)
        return self._repo.save_workspace(updated)

    def set_active_watchlist(
        self, requester: Optional[UserAuthorization], target_user_id: str, watchlist_id: str
    ) -> Workspace:
        """Set active watchlist ID in workspace."""
        ws = self.get_or_create_workspace(requester, target_user_id)
        updated = ws.with_active_watchlist(watchlist_id)
        return self._repo.save_workspace(updated)

    def create_watchlist(
        self,
        requester: Optional[UserAuthorization],
        target_user_id: str,
        name: str,
        symbols: Optional[List[str]] = None,
    ) -> Tuple[Workspace, Watchlist]:
        """Create a new watchlist in the user's workspace."""
        ws = self.get_or_create_workspace(requester, target_user_id)
        wl_id = f"wl_{uuid.uuid4().hex[:8]}"
        new_wl = Watchlist(
            watchlist_id=wl_id,
            name=name,
            symbols=tuple(symbols or []),
            is_default=False,
        )
        updated = ws.with_updated_watchlist(new_wl).with_active_watchlist(wl_id)
        saved = self._repo.save_workspace(updated)
        return saved, new_wl

    def rename_watchlist(
        self,
        requester: Optional[UserAuthorization],
        target_user_id: str,
        watchlist_id: str,
        new_name: str,
    ) -> Workspace:
        """Rename an existing watchlist."""
        ws = self.get_or_create_workspace(requester, target_user_id)
        wl = ws.watchlists.get(watchlist_id)
        if wl is None:
            raise KeyError(f"Watchlist '{watchlist_id}' not found")

        renamed = wl.rename(new_name)
        updated = ws.with_updated_watchlist(renamed)
        return self._repo.save_workspace(updated)

    def delete_watchlist(
        self, requester: Optional[UserAuthorization], target_user_id: str, watchlist_id: str
    ) -> Workspace:
        """Delete a watchlist."""
        ws = self.get_or_create_workspace(requester, target_user_id)
        updated = ws.without_watchlist(watchlist_id)
        return self._repo.save_workspace(updated)

    def add_symbol_to_watchlist(
        self,
        requester: Optional[UserAuthorization],
        target_user_id: str,
        watchlist_id: str,
        symbol: str,
    ) -> Workspace:
        """Add symbol to watchlist."""
        ws = self.get_or_create_workspace(requester, target_user_id)
        wl = ws.watchlists.get(watchlist_id)
        if wl is None:
            raise KeyError(f"Watchlist '{watchlist_id}' not found")

        updated_wl = wl.add_symbol(symbol)
        updated_ws = ws.with_updated_watchlist(updated_wl)
        return self._repo.save_workspace(updated_ws)

    def remove_symbol_from_watchlist(
        self,
        requester: Optional[UserAuthorization],
        target_user_id: str,
        watchlist_id: str,
        symbol: str,
    ) -> Workspace:
        """Remove symbol from watchlist."""
        ws = self.get_or_create_workspace(requester, target_user_id)
        wl = ws.watchlists.get(watchlist_id)
        if wl is None:
            raise KeyError(f"Watchlist '{watchlist_id}' not found")

        updated_wl = wl.remove_symbol(symbol)
        updated_ws = ws.with_updated_watchlist(updated_wl)
        return self._repo.save_workspace(updated_ws)

    def update_preferences(
        self,
        requester: Optional[UserAuthorization],
        target_user_id: str,
        chart_preferences: Optional[Dict[str, Any]] = None,
        layout_preferences: Optional[Dict[str, Any]] = None,
        notification_preferences: Optional[Union[NotificationPreferences, Dict[str, Any]]] = None,
    ) -> Workspace:
        """Update chart, layout, or notification preferences."""
        ws = self.get_or_create_workspace(requester, target_user_id)
        res = ws
        if chart_preferences:
            res = res.with_chart_preferences(chart_preferences)
        if layout_preferences:
            res = res.with_layout_preferences(layout_preferences)
        if notification_preferences:
            if isinstance(notification_preferences, dict):
                notif_prefs = NotificationPreferences.from_dict(notification_preferences)
            elif isinstance(notification_preferences, NotificationPreferences):
                notif_prefs = notification_preferences
            else:
                raise ValueError("notification_preferences must be a NotificationPreferences or dict")
            res = res.with_notification_preferences(notif_prefs)
        return self._repo.save_workspace(res)
