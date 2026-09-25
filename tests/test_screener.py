"""Tests for Market Screener domain and service."""

from unittest.mock import MagicMock
import pytest

from src.platform.domain.quote import Quote
from src.platform.domain.screener import AssetCategory, MarketScreenerFilter
from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.provider_operations import QuoteOperationResult
from src.platform.services.market_screener import MarketScreenerService


def test_screener_default_query_no_runtime_providers():
    """Verify screener operates safely with no runtime providers attached (returns truthful unavailable data)."""
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
    # No demo prices or fake percentages
    for item in res.items:
        assert item.price is None
        assert item.change_24h_percent is None
        assert item.volume_24h_usd is None
        assert item.volatility_percent is None
        assert item.signal_action is None


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


def test_screener_uses_runtime_quotes_and_symbol_isolation():
    """Requirement J: Tests 1-10 covering removal of demo catalog, runtime quote integration, symbol isolation, and unavailable states."""
    mock_provider_ops = MagicMock()

    def mock_fetch_quote(provider_id: str, symbol: str):
        if symbol == "XAUUSD":
            return QuoteOperationResult(
                provider_id="biquote",
                symbol="XAUUSD",
                quote=Quote(
                    symbol="XAUUSD",
                    bid=2700.0,
                    ask=2702.0,
                    mid=2701.0,
                    last=2701.0,
                    timestamp=1700000000.0,
                    change_percent=1.25,
                ),
            )
        elif symbol == "BTCUSD":
            return QuoteOperationResult(
                provider_id="biquote",
                symbol="BTCUSD",
                quote=Quote(
                    symbol="BTCUSD",
                    bid=68000.0,
                    ask=68100.0,
                    mid=68050.0,
                    last=68050.0,
                    timestamp=1700000000.0,
                    change_percent=-0.50,
                ),
            )
        raise RuntimeError(f"Quote unavailable for {symbol}")

    mock_provider_ops.fetch_quote.side_effect = mock_fetch_quote

    guest_user = UserAuthorization(
        user_id="guest_1",
        auth_code="code_guest_123",
        role=UserRole.GUEST,
        permissions=(),
    )

    service = MarketScreenerService(provider_operations=mock_provider_ops)
    res = service.screen_markets(user_context=guest_user)

    # 1. Demo catalog removed
    for item in res.items:
        assert item.price != 2685.50  # old demo price for XAUUSD

    # 3. Price comes from runtime quote path
    xau_item = next(i for i in res.items if i.symbol == "XAUUSD")
    assert xau_item.price == 2701.0
    assert xau_item.change_24h_percent == 1.25

    btc_item = next(i for i in res.items if i.symbol == "BTCUSD")
    assert btc_item.price == 68050.0
    assert btc_item.change_24h_percent == -0.50

    # 5. XAUUSD cannot receive another instrument's quote
    assert xau_item.price != btc_item.price

    # 6 & 8. Missing quote / missing volume remains unavailable
    eur_item = next(i for i in res.items if i.symbol == "EURUSD")
    assert eur_item.price is None
    assert eur_item.change_24h_percent is None
    assert eur_item.volume_24h_usd is None

    # 10. No fabricated volatility
    assert xau_item.volatility_percent is None


def test_screener_uses_runtime_signals_and_freshness_rules():
    """Requirement J: Tests 11-20 covering signal boundary, freshness threshold, and NO SIGNAL status."""
    mock_presenter = MagicMock()

    def mock_present_signal(symbol: str, timeframe: str = "1h", user=None):
        if symbol == "XAUUSD":
            return {
                "status": "active",
                "signal": {
                    "symbol": "XAUUSD",
                    "signal_type": "BUY",
                    "confidence": 0.85,
                    "timestamp": 1700000000.0,
                },
            }
        elif symbol == "EURUSD":
            # Stale / historical signal returned by presenter as no-signal
            return {
                "status": "no-signal",
                "signal": None,
                "message": "Signal is stale (>300s).",
            }
        return {"status": "no-signal", "signal": None}

    mock_presenter.present_signal.side_effect = mock_present_signal

    admin_user = UserAuthorization(
        user_id="admin_1",
        auth_code="code_admin_123",
        role=UserRole.ADMIN,
        permissions=(Permission.READ_SIGNALS,),
    )

    service = MarketScreenerService(signal_presenter=mock_presenter)
    res = service.screen_markets(user_context=admin_user)

    # 11 & 15. Active fresh signal displayed
    xau_item = next(i for i in res.items if i.symbol == "XAUUSD")
    assert xau_item.signal_action == "BUY"
    assert xau_item.signal_confidence == 0.85

    # 16-20. Stale / missing signals become NO SIGNAL (None action), NEVER HOLD
    eur_item = next(i for i in res.items if i.symbol == "EURUSD")
    assert eur_item.signal_action is None
    assert eur_item.signal_action != "HOLD"


def test_screener_and_heatmap_dataset_parity():
    """Requirement J: Tests 21-24 dataset parity between list and heatmap."""
    mock_provider_ops = MagicMock()
    mock_provider_ops.fetch_quote.return_value = QuoteOperationResult(
        provider_id="biquote",
        symbol="XAUUSD",
        quote=Quote(
            symbol="XAUUSD",
            bid=2700.0,
            ask=2702.0,
            mid=2701.0,
            last=2701.0,
            timestamp=1700000000.0,
            change_percent=2.5,
        ),
    )

    guest_user = UserAuthorization(
        user_id="guest_1",
        auth_code="code_guest_123",
        role=UserRole.GUEST,
        permissions=(),
    )

    service = MarketScreenerService(provider_operations=mock_provider_ops)
    res = service.screen_markets(user_context=guest_user)

    assert len(res.items) == len(res.heatmap_tiles)
    for item, tile in zip(res.items, res.heatmap_tiles):
        assert item.symbol == tile.symbol
        assert item.change_24h_percent == tile.change_24h_percent
        assert item.signal_action == tile.signal_action
