"""Tests for Workspace and Watchlist domain models, repository, security boundary, and application service.
"""

import pytest
from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.domain.workspace import Watchlist, Workspace
from src.platform.services.security import SecurityBoundaryService
from src.platform.services.workspace import (
    InMemoryWorkspaceRepository,
    WorkspaceService,
)


def test_watchlist_domain_operations() -> None:
    wl = Watchlist(
        watchlist_id="wl_1",
        name="Crypto List",
        symbols=("btcusd", "ethusd"),
        is_default=False,
    )
    assert wl.symbols == ("BTCUSD", "ETHUSD")

    # Duplicate symbol addition is ignored
    wl2 = wl.add_symbol("BTCUSD")
    assert wl2.symbols == ("BTCUSD", "ETHUSD")

    # Add new symbol
    wl3 = wl2.add_symbol("SOLUSD")
    assert wl3.symbols == ("BTCUSD", "ETHUSD", "SOLUSD")

    # Remove symbol
    wl4 = wl3.remove_symbol("ETHUSD")
    assert wl4.symbols == ("BTCUSD", "SOLUSD")

    # Rename watchlist
    wl_renamed = wl4.rename("Crypto Favorites")
    assert wl_renamed.name == "Crypto Favorites"

    # Serialization
    d = wl_renamed.to_dict()
    recreated = Watchlist.from_dict(d)
    assert recreated.watchlist_id == wl_renamed.watchlist_id
    assert recreated.name == wl_renamed.name
    assert recreated.symbols == wl_renamed.symbols


def test_workspace_domain_operations() -> None:
    ws = Workspace.create_default(user_id="user_123")
    assert ws.user_id == "user_123"
    assert ws.active_watchlist_id == "default"
    assert ws.active_symbol == "XAUUSD"
    assert "default" in ws.watchlists

    # Change active symbol
    ws2 = ws.with_active_symbol("eurusd")
    assert ws2.active_symbol == "EURUSD"

    # Update preferences
    ws3 = ws2.with_chart_preferences({"timeframe": "4h"}).with_layout_preferences({"compact": True})
    assert ws3.chart_preferences["timeframe"] == "4h"
    assert ws3.layout_preferences["compact"] is True


def test_workspace_service_creation_and_user_isolation() -> None:
    user_a = UserAuthorization(user_id="user_a", auth_code="code_a", role=UserRole.USER)
    user_b = UserAuthorization(user_id="user_b", auth_code="code_b", role=UserRole.USER)
    admin_user = UserAuthorization(user_id="admin_user", auth_code="admin_code", role=UserRole.ADMIN)

    repo = InMemoryWorkspaceRepository()
    sec = SecurityBoundaryService()
    service = WorkspaceService(repository=repo, security_service=sec)

    # User A gets own workspace
    ws_a = service.get_or_create_workspace(user_a, "user_a")
    assert ws_a.user_id == "user_a"

    # User A cannot access User B's workspace (PermissionError / User isolation)
    with pytest.raises(PermissionError, match="not authorized to access workspace"):
        service.get_or_create_workspace(user_a, "user_b")

    # Anonymous access is denied
    with pytest.raises(PermissionError, match="unauthenticated access"):
        service.get_or_create_workspace(None, "user_a")

    # Admin user CAN access User B's workspace for management
    ws_b = service.get_or_create_workspace(admin_user, "user_b")
    assert ws_b.user_id == "user_b"


def test_workspace_service_watchlist_crud() -> None:
    user = UserAuthorization(user_id="trader_1", auth_code="code_1", role=UserRole.USER)
    service = WorkspaceService()

    # Create new watchlist
    ws, new_wl = service.create_watchlist(
        user, "trader_1", name="Forex Majors", symbols=["EURUSD", "GBPUSD"]
    )
    assert new_wl.name == "Forex Majors"
    assert ws.active_watchlist_id == new_wl.watchlist_id
    assert "EURUSD" in ws.watchlists[new_wl.watchlist_id].symbols

    # Add symbol to new watchlist
    ws = service.add_symbol_to_watchlist(user, "trader_1", new_wl.watchlist_id, "USDJPY")
    assert "USDJPY" in ws.watchlists[new_wl.watchlist_id].symbols

    # Remove symbol from watchlist
    ws = service.remove_symbol_from_watchlist(user, "trader_1", new_wl.watchlist_id, "EURUSD")
    assert "EURUSD" not in ws.watchlists[new_wl.watchlist_id].symbols
    assert "USDJPY" in ws.watchlists[new_wl.watchlist_id].symbols

    # Rename watchlist
    ws = service.rename_watchlist(user, "trader_1", new_wl.watchlist_id, "Primary Forex")
    assert ws.watchlists[new_wl.watchlist_id].name == "Primary Forex"

    # Delete watchlist
    ws = service.delete_watchlist(user, "trader_1", new_wl.watchlist_id)
    assert new_wl.watchlist_id not in ws.watchlists
    assert ws.active_watchlist_id == "default"


def test_cannot_delete_last_watchlist() -> None:
    user = UserAuthorization(user_id="trader_2", auth_code="code_2", role=UserRole.USER)
    service = WorkspaceService()

    ws = service.get_or_create_workspace(user, "trader_2")
    assert len(ws.watchlists) == 1

    with pytest.raises(ValueError, match="Cannot remove the last remaining watchlist"):
        service.delete_watchlist(user, "trader_2", "default")
