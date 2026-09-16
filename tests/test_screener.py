"""Tests for Market Screener domain and service."""

import pytest
from src.platform.domain.screener import AssetCategory, MarketScreenerFilter
from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.market_screener import MarketScreenerService


def test_screener_default_query():
    service = MarketScreenerService()
    admin_user = UserAuthorization(
        user_id="admin_1",
        auth_code="code_admin_123",
        role=UserRole.ADMIN,
        permissions=(Permission.READ_SIGNALS,),
    )
    res = service.screen_markets(user_context=admin_user)
    assert res.total_count == 10
    assert len(res.heatmap_tiles) == 10
    # Confirm default sort descending by 24h change
    assert res.items[0].change_24h_percent >= res.items[-1].change_24h_percent


def test_screener_category_filter():
    service = MarketScreenerService()
    admin_user = UserAuthorization(
        user_id="admin_1",
        auth_code="code_admin_123",
        role=UserRole.ADMIN,
        permissions=(Permission.READ_SIGNALS,),
    )
    filter_comm = MarketScreenerFilter(category=AssetCategory.COMMODITIES)
    res = service.screen_markets(filter_criteria=filter_comm, user_context=admin_user)
    assert res.total_count == 2
    assert all(item.category == AssetCategory.COMMODITIES for item in res.items)


def test_screener_search_filter():
    service = MarketScreenerService()
    admin_user = UserAuthorization(
        user_id="admin_1",
        auth_code="code_admin_123",
        role=UserRole.ADMIN,
        permissions=(Permission.READ_SIGNALS,),
    )
    filter_search = MarketScreenerFilter(search_query="gold")
    res = service.screen_markets(filter_criteria=filter_search, user_context=admin_user)
    assert res.total_count == 1
    assert res.items[0].symbol == "XAUUSD"


def test_screener_unauthorized_guest_redacts_signals():
    service = MarketScreenerService()
    guest_user = UserAuthorization(
        user_id="guest_1",
        auth_code="code_guest_123",
        role=UserRole.GUEST,
        permissions=(),
    )
    res = service.screen_markets(user_context=guest_user)
    assert res.total_count == 10
    for item in res.items:
        assert item.signal_action is None
        assert item.signal_confidence is None


def test_screener_signal_filter_authorized():
    service = MarketScreenerService()
    admin_user = UserAuthorization(
        user_id="admin_1",
        auth_code="code_admin_123",
        role=UserRole.ADMIN,
        permissions=(Permission.READ_SIGNALS,),
    )
    filter_buy = MarketScreenerFilter(signal_filter="BUY")
    res = service.screen_markets(filter_criteria=filter_buy, user_context=admin_user)
    assert res.total_count > 0
    assert all(item.signal_action == "BUY" for item in res.items)
