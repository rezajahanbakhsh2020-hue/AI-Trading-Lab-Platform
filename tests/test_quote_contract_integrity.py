"""Tests for Quote canonical contract integrity and presenter timeframe propagation."""

import pytest
from src.platform.domain.quote import Quote
from src.platform.services.project1_presenter import Project1SignalPresenter
from src.platform.adapters.project1_adapter import Project1GatewayAdapter
from src.platform.services.project1_gateway import Project1IntegrationGatewayService
from src.platform.services.provider_operations import ProviderOperations
from src.platform.services.provider_access import ProviderAccess
from src.platform.services.provider_registry import ProviderRegistry
from src.platform.services.market_overview import MarketOverviewService
from src.platform.providers.biquote import BiQuoteProvider
from src.platform.providers.biquote_quote import BiQuoteQuoteProvider


def test_quote_domain_derives_mid_from_bid_and_ask():
    quote = Quote(
        symbol="XAUUSD",
        timestamp=1700000000,
        bid=2650.0,
        ask=2660.0,
        change_percent=1.5,
        high=2670.0,
        low=2640.0,
    )
    assert quote.bid == 2650.0
    assert quote.ask == 2660.0
    assert quote.mid == 2655.0  # (2650 + 2660) / 2
    assert quote.last is None

    d = quote.to_dict()
    assert d["bid"] == 2650.0
    assert d["ask"] == 2660.0
    assert d["mid"] == 2655.0
    assert d["change_percent"] == 1.5
    assert d["changePercent"] == 1.5
    assert d["high"] == 2670.0
    assert d["high24h"] == 2670.0
    assert d["low"] == 2640.0
    assert d["low24h"] == 2640.0


def test_presenter_build_host_snapshot_preserves_requested_timeframe():
    registry = ProviderRegistry()
    md_provider = BiQuoteProvider()
    md_provider.connect()
    qt_provider = BiQuoteQuoteProvider()
    qt_provider.connect()

    registry.register("biquote", "market_data", md_provider)
    registry.register("biquote", "quote", qt_provider)

    access = ProviderAccess(registry)
    ops = ProviderOperations(access)
    overview_service = MarketOverviewService(ops)

    gateway_service = Project1IntegrationGatewayService()
    port_adapter = Project1GatewayAdapter(gateway_service=gateway_service)

    presenter = Project1SignalPresenter(
        port=port_adapter,
        gateway_service=gateway_service,
        provider_operations=ops,
        market_overview_service=overview_service,
    )

    snapshot = presenter.build_host_snapshot(
        symbol="XAUUSD",
        timeframe="15m",
    )

    assert snapshot["market"]["symbol"] == "XAUUSD"
    assert snapshot["market"]["timeframe"] == "15m"
