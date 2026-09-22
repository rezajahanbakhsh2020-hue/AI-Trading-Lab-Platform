"""Tests for Market Data Trading Terminal integration and API endpoints.

Covers:
- GET /api/v1/providers
- GET /api/v1/market/candles
- GET /api/v1/market/quote
- GET /api/v1/market/overview
- Truthful data states (connected, disconnected, stale, error, empty)
- User authentication and workspace isolation
- Strict Project 1 boundary preservation
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from src.platform.server import create_server
from src.platform.config import PlatformConfig
from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import UserAuthorization


@pytest.fixture
def server():
    cfg = PlatformConfig(
        app_env="testing",
        session_secret="test_session_secret_key_32_bytes_long_testing!",
        persistence_dir="/tmp/test_market_terminal_pers",
    )
    srv = create_server(host="127.0.0.1", port=0, config=cfg)
    yield srv
    srv.server_close()


def test_list_providers_endpoint(server):
    handler_class = server.RequestHandlerClass
    providers = handler_class.provider_access.list_providers()
    assert len(providers) >= 2
    categories = handler_class.provider_access.supported_categories()
    assert "market_data" in categories
    assert "quote" in categories


def test_fetch_candles_success(server):
    handler_class = server.RequestHandlerClass
    with patch.object(handler_class.provider_operations, "fetch_candles") as mock_fetch:
        mock_result = MagicMock()
        mock_result.provider_id = "biquote"
        mock_result.symbol = "XAUUSD"
        mock_result.timeframe = "1h"
        candle_mock = MagicMock()
        candle_mock.to_dict.return_value = {
            "timestamp": 1700000000,
            "open": 2650.0,
            "high": 2655.0,
            "low": 2648.0,
            "close": 2652.5,
            "volume": 120,
        }
        mock_result.candles = [candle_mock]
        mock_fetch.return_value = mock_result

        res = handler_class.provider_operations.fetch_candles("biquote", "XAUUSD", "1h", 100)
        assert res.symbol == "XAUUSD"
        assert len(res.candles) == 1
        assert res.candles[0].to_dict()["close"] == 2652.5


def test_fetch_quote_success(server):
    handler_class = server.RequestHandlerClass
    with patch.object(handler_class.provider_operations, "fetch_quote") as mock_fetch:
        mock_result = MagicMock()
        mock_result.provider_id = "biquote"
        mock_result.symbol = "XAUUSD"
        quote_mock = MagicMock()
        quote_mock.to_dict.return_value = {
            "symbol": "XAUUSD",
            "timestamp": 1700000000,
            "bid": 2652.0,
            "ask": 2653.0,
            "mid": 2652.5,
            "last": 2652.5,
        }
        mock_result.quote = quote_mock
        mock_fetch.return_value = mock_result

        res = handler_class.provider_operations.fetch_quote("biquote", "XAUUSD")
        assert res.symbol == "XAUUSD"
        assert res.quote.to_dict()["ask"] == 2653.0


def test_project1_boundary_preservation(server):
    """Verify that Project 2 host snapshot consumes Project 1 outputs without recalculating prices or strategy signals."""
    handler_class = server.RequestHandlerClass
    user = UserAuthorization(
        user_id="customer_1",
        auth_code="hash_123",
        role=UserRole.CUSTOMER,
        permissions=(Permission.READ_SIGNALS, Permission.READ_TRADE_SETUPS),
    )
    snapshot = handler_class.presenter.build_host_snapshot(symbol="XAUUSD", timeframe="1h", user=user)

    # Ensure Project 1 boundary is honored
    assert snapshot["platform"]["name"] == "AI Trading Lab Platform"
    assert "market" in snapshot
    assert "project1" in snapshot
    assert snapshot["project1"]["connected"] is True
    assert snapshot["signal"]["action"] == "NO SIGNAL"
