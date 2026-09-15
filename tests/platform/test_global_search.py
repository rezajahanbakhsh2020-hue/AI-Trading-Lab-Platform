"""Tests for GlobalSearchService and Search Security Boundary Integration."""

import pytest
from src.platform.domain.search import SearchCategory, SearchQuery
from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.global_search import GlobalSearchService
from src.platform.services.security import SecurityBoundaryService


@pytest.fixture
def normal_user():
    return UserAuthorization(
        user_id="user_123",
        auth_code="ac_user_123",
        role=UserRole.USER,
        permissions=(Permission.READ_SIGNALS, Permission.READ_TRADE_SETUPS),
    )


@pytest.fixture
def admin_user():
    return UserAuthorization(
        user_id="admin_001",
        auth_code="ac_admin_001",
        role=UserRole.ADMIN,
        permissions=(Permission.ADMIN_ALL,),
    )


@pytest.fixture
def guest_user():
    return UserAuthorization(
        user_id="guest_999",
        auth_code="ac_guest_999",
        role=UserRole.GUEST,
        permissions=(),
    )


def test_global_search_service_navigation(normal_user):
    service = GlobalSearchService()
    query = SearchQuery(query="markets", user=normal_user)
    result = service.search(query)

    assert result.query == "markets"
    assert result.total_count > 0

    nav_group = next((g for g in result.groups if g.category == SearchCategory.NAVIGATION), None)
    assert nav_group is not None
    assert any("Markets" in item.title for item in nav_group.items)


def test_global_search_service_symbol_search(normal_user):
    service = GlobalSearchService()
    query = SearchQuery(query="XAU", user=normal_user)
    result = service.search(query)

    mkt_group = next((g for g in result.groups if g.category == SearchCategory.MARKET), None)
    assert mkt_group is not None
    assert any(item.title == "XAUUSD" for item in mkt_group.items)


def test_global_search_signals_authorization(guest_user, normal_user):
    service = GlobalSearchService()

    # Guest user has no READ_SIGNALS permission
    guest_query = SearchQuery(query="signal", user=guest_user)
    guest_result = service.search(guest_query)
    guest_sig_group = next((g for g in guest_result.groups if g.category == SearchCategory.SIGNAL), None)
    assert guest_sig_group is None

    # Normal user has READ_SIGNALS permission
    user_query = SearchQuery(query="signal", user=normal_user)
    user_result = service.search(user_query)
    user_sig_group = next((g for g in user_result.groups if g.category == SearchCategory.SIGNAL), None)
    assert user_sig_group is not None
    assert len(user_sig_group.items) > 0


def test_global_search_admin_only_strategies(normal_user, admin_user):
    service = GlobalSearchService()

    # Normal user searching research
    user_query = SearchQuery(query="research", user=normal_user)
    user_result = service.search(user_query)
    user_items = [item for g in user_result.groups for item in g.items]
    assert not any(item.requires_admin for item in user_items)

    # Admin user searching research
    admin_query = SearchQuery(query="research", user=admin_user)
    admin_result = service.search(admin_query)
    admin_items = [item for g in admin_result.groups for item in g.items]
    assert any(item.requires_admin for item in admin_items)


def test_global_search_sanitizes_sensitive_inputs():
    service = GlobalSearchService()
    # Attempting to search secrets/tokens should sanitize the query string
    query = SearchQuery(query="token=supersecretkey1234")
    result = service.search(query)
    assert "supersecretkey" not in result.query
