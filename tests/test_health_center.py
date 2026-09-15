"""Tests for Connection & Data Health Center extensions."""

import pytest
from src.platform.providers.biquote import BiQuoteProvider
from src.platform.providers.biquote_quote import BiQuoteQuoteProvider
from src.platform.services.provider_access import ProviderAccess
from src.platform.services.provider_inspection import ProviderInspectionService
from src.platform.services.provider_monitoring import ProviderMonitor
from src.platform.services.provider_operations import ProviderOperations
from src.platform.services.provider_readiness import (
    PROVIDER_STATUS_READY,
    ProviderReadinessService,
)
from src.platform.services.provider_registry import (
    CATEGORY_MARKET_DATA,
    CATEGORY_QUOTE,
    ProviderRegistry,
)


def test_health_center_backend_readiness_assessment():
    registry = ProviderRegistry()
    biquote = BiQuoteProvider()
    biquote_quote = BiQuoteQuoteProvider()

    registry.register(
        category=CATEGORY_MARKET_DATA,
        provider_id="biquote",
        provider=biquote,
        metadata={"name": "BiQuote Market Data"},
    )
    registry.register(
        category=CATEGORY_QUOTE,
        provider_id="biquote_quote",
        provider=biquote_quote,
        metadata={"name": "BiQuote Real-Time Quotes"},
    )

    access = ProviderAccess(registry)
    inspection_svc = ProviderInspectionService(access)
    operations = ProviderOperations(access)
    monitor = ProviderMonitor(operations)
    readiness_svc = ProviderReadinessService(access=access, monitor=monitor)

    inspections = inspection_svc.inspect_all()
    assert len(inspections) == 2

    md_readiness = readiness_svc.assess(
        category=CATEGORY_MARKET_DATA,
        provider_id="biquote",
        symbol="XAUUSD",
        timeframe="1h",
        reference=1700000000,
    )
    assert md_readiness.category == CATEGORY_MARKET_DATA
    assert md_readiness.provider_id == "biquote"
    assert md_readiness.status == PROVIDER_STATUS_READY

    all_readiness = readiness_svc.assess_all(
        symbol="XAUUSD",
        timeframe="1h",
        reference=1700000000,
        market_data_provider_id="biquote",
    )
    assert len(all_readiness) == 2
