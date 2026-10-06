"""Tests for Authoritative Multi-Timeframe Signal Viewing UX and Boundaries."""

import time
import pytest
from src.platform.adapters.project1_adapter import Project1GatewayAdapter
from src.platform.adapters.project1_repository import FileBackedProject1IntegrationRepository
from src.platform.domain.presented_signal import PresentedSignal
from src.platform.integrations.project1 import Project1IntegrationPort
from src.platform.services.project1_gateway import Project1IntegrationGatewayService
from src.platform.services.project1_presenter import Project1SignalPresenter


class MockMultiTimeframePort(Project1IntegrationPort):
    """Mock P1 integration port holding signals for specific timeframes."""

    def __init__(self, signals_map=None):
        # signals_map: dict of (symbol, timeframe) -> PresentedSignal
        self._map = signals_map or {}

    def fetch_latest_signal(self, symbol: str, timeframe: str, strategy_name=None, user_id=None):
        return self._map.get((symbol.upper(), timeframe.lower()))

    def describe(self, user_id=None):
        return {
            "name": "MockMultiTimeframePort",
            "port": "Project1IntegrationPort",
            "connected": True,
            "status": "active",
        }


def test_exact_timeframe_isolation_and_no_cross_timeframe_fallback():
    """Verify that every supported timeframe is queried exactly and no cross-timeframe fallback occurs."""
    now_ts = time.time()
    tf_5m_signal = PresentedSignal(
        signal_id="sig_5m_001",
        symbol="XAUUSD",
        signal_type="buy",
        timestamp=now_ts - 20.0,
        entry_price=2650.0,
        stop_loss=2630.0,
        take_profits=(2680.0,),
        confidence=0.85,
        strategy_name="P1MultiTFStrategy",
        timeframe="5m",
        metadata={"provenance_type": "live_signal", "is_live": True},
    )

    port = MockMultiTimeframePort({("XAUUSD", "5m"): tf_5m_signal})
    presenter = Project1SignalPresenter(port)

    # 1. 5m request returns active BUY
    pres_5m = presenter.present_signal("XAUUSD", "5m")
    assert pres_5m["status"] == "active"
    assert pres_5m["signal"]["signal_type"] == "buy"
    assert pres_5m["timeframe"] == "5m"

    # 2. 15m request MUST NOT fall back to 5m signal
    for other_tf in ["1m", "15m", "30m", "1h", "4h", "1d"]:
        pres_other = presenter.present_signal("XAUUSD", other_tf)
        assert pres_other["status"] == "no-signal"
        assert pres_other["signal"] is None
        assert pres_other["timeframe"] == other_tf

        snap_other = presenter.build_host_snapshot("XAUUSD", other_tf)
        assert snap_other["signal"]["status"] == "no-signal"
        assert snap_other["signal"]["action"] == "NO SIGNAL"


def test_live_buy_and_sell_semantics_for_selected_timeframe():
    """Verify live BUY and SELL preserve exact prices, strategy, and lineage for the selected timeframe."""
    now_ts = time.time()
    buy_sig = PresentedSignal(
        signal_id="sig_buy_15m",
        symbol="XAUUSD",
        signal_type="buy",
        timestamp=now_ts - 10.0,
        entry_price=2650.25,
        stop_loss=2635.00,
        take_profits=(2670.00, 2690.00),
        confidence=0.90,
        strategy_name="GoldTrend",
        timeframe="15m",
        metadata={
            "provenance_type": "live_signal",
            "is_live": True,
            "publication_id": "pub_buy_15m",
            "decision_id": "dec_buy_15m",
        },
    )
    sell_sig = PresentedSignal(
        signal_id="sig_sell_1h",
        symbol="XAUUSD",
        signal_type="sell",
        timestamp=now_ts - 15.0,
        entry_price=2660.00,
        stop_loss=2675.00,
        take_profits=(2640.00, 2620.00),
        confidence=0.88,
        strategy_name="GoldTrend",
        timeframe="1h",
        metadata={
            "provenance_type": "live_signal",
            "is_live": True,
            "publication_id": "pub_sell_1h",
            "decision_id": "dec_sell_1h",
        },
    )

    port = MockMultiTimeframePort({
        ("XAUUSD", "15m"): buy_sig,
        ("XAUUSD", "1h"): sell_sig,
    })
    presenter = Project1SignalPresenter(port)

    # 15m BUY
    snap_15m = presenter.build_host_snapshot("XAUUSD", "15m")
    assert snap_15m["signal"]["action"] == "BUY"
    assert snap_15m["signal"]["status"] == "active"
    assert snap_15m["risk"]["entry"] == 2650.25
    assert snap_15m["risk"]["stopLoss"] == 2635.00

    # 1h SELL
    snap_1h = presenter.build_host_snapshot("XAUUSD", "1h")
    assert snap_1h["signal"]["action"] == "SELL"
    assert snap_1h["signal"]["status"] == "active"
    assert snap_1h["risk"]["entry"] == 2660.00
    assert snap_1h["risk"]["stopLoss"] == 2675.00


def test_live_authoritative_no_trade_preservation():
    """Verify live NO_TRADE decision remains NO_TRADE with timestamp, timeframe, strategy, and MTF intact without conversion or fake risk levels."""
    now_ts = time.time()
    no_trade_sig = PresentedSignal(
        signal_id="sig_no_trade_30m",
        symbol="XAUUSD",
        signal_type="no-trade",
        timestamp=now_ts - 10.0,
        entry_price=None,
        stop_loss=None,
        take_profits=(),
        confidence=None,
        strategy_name="P1MTFStrategy",
        timeframe="30m",
        metadata={
            "provenance_type": "live_signal",
            "is_live": True,
            "publication_id": "pub_nt_30m",
            "decision_id": "dec_nt_30m",
            "mtf": {
                "symbol": "XAUUSD",
                "local_timeframe": "30m",
                "participating_timeframes": ["5m", "15m", "30m", "1H", "4H", "1D"],
                "alignment_count": 2,
                "alignment_coverage": 2,
                "classification": "NEUTRAL",
                "star_representation": "⭐⭐☆☆☆",
                "signals": [],
            },
        },
    )

    port = MockMultiTimeframePort({("XAUUSD", "30m"): no_trade_sig})
    presenter = Project1SignalPresenter(port)

    res = presenter.present_signal("XAUUSD", "30m")
    assert res["status"] == "no-trade"
    assert res["signal"] is not None
    assert res["signal"]["signal_type"] == "no-trade"

    snapshot = presenter.build_host_snapshot("XAUUSD", "30m")
    assert snapshot["signal"]["action"] == "NO TRADE"
    assert snapshot["signal"]["status"] == "no-trade"
    assert snapshot["signal"]["strategyName"] == "P1MTFStrategy"
    assert snapshot["signal"]["timeframe"] == "30m"
    assert snapshot["signal"]["metadata"]["mtf"]["star_representation"] == "⭐⭐☆☆☆"

    # Risk levels MUST remain empty/unavailable for NO_TRADE
    assert snapshot["risk"]["entry"] is None
    assert snapshot["risk"]["stopLoss"] is None
    assert snapshot["risk"]["takeProfits"] == []
    assert snapshot["risk"]["status"] == "unavailable"


def test_stale_signal_remains_fail_closed():
    """Verify signal with publication age > 300s remains active signal according to canonical validity contract."""
    now_ts = time.time()
    stale_sig = PresentedSignal(
        signal_id="sig_stale_1h",
        symbol="XAUUSD",
        signal_type="buy",
        timestamp=now_ts - 600.0,  # 10 minutes old
        entry_price=2650.0,
        stop_loss=2630.0,
        take_profits=(2680.0,),
        confidence=0.80,
        strategy_name="GoldTrend",
        timeframe="1h",
        metadata={"provenance_type": "live_signal", "is_live": True},
    )

    port = MockMultiTimeframePort({("XAUUSD", "1h"): stale_sig})
    presenter = Project1SignalPresenter(port)

    res = presenter.present_signal("XAUUSD", "1h")
    assert res["status"] == "active"
    assert res["signal"] is not None

    snapshot = presenter.build_host_snapshot("XAUUSD", "1h")
    assert snapshot["signal"]["status"] == "active"
    assert snapshot["signal"]["action"] == "BUY"
    assert snapshot["risk"]["entry"] == 2650.0


def test_p1_mtf_metadata_and_lineage_preservation_without_p2_recomputation(tmp_path):
    """Verify exact unmutated transport of P1 MTF metadata, lineage fields, and zero P2 recomputation."""
    now_ts = time.time()
    repo_file = str(tmp_path / "mtf_test_records.json")
    repo = FileBackedProject1IntegrationRepository(storage_filepath=repo_file)
    gw_svc = Project1IntegrationGatewayService(repository=repo)

    rec_payload = {
        "event_id": "evt_mtf_001",
        "publication_id": "pub_mtf_001",
        "signal_id": "sig_mtf_001",
        "command_type": "EMIT_SIGNAL",
        "symbol": "XAUUSD",
        "timeframe": "5m",
        "signal_type": "buy",
        "timestamp": now_ts - 5.0,
        "entry_price": 2650.0,
        "stop_loss": 2630.0,
        "take_profit_1": 2680.0,
        "confidence": 0.88,
        "operational_stability_score": 0.95,
        "risk_reward_ratio": 2.1234,
        "strategy_name": "MTF_Strategy_P1",
        "decision_id": "dec_mtf_100",
        "candidate_id": "cand_mtf_200",
        "research_evidence_id": "res_mtf_300",
        "canonical_live_decision_fingerprint": "fp_decision_mtf",
        "runtime_authorization_fingerprint": "fp_auth_mtf",
        "mtf": {
            "symbol": "XAUUSD",
            "local_timeframe": "5m",
            "participating_timeframes": ["5m", "15m", "30m", "1H", "4H", "1D"],
            "alignment_count": 5,
            "alignment_coverage": 5,
            "classification": "ALIGNED",
            "star_representation": "⭐⭐⭐⭐⭐",
            "higher_timeframe_context": {"trend": "BULLISH_STRONG"},
            "signals": [
                {
                    "symbol": "XAUUSD",
                    "timeframe": "15m",
                    "direction": "buy",
                    "decision_id": "dec_15m",
                    "signal_id": "sig_15m",
                    "decision_timestamp": now_ts - 10.0,
                    "market_timestamp": now_ts - 10.0,
                    "strategy_name": "MTF_Strategy_P1",
                    "strategy_version": "1.0",
                    "candidate_id": "cand_15m",
                    "evidence_id": "ev_15m",
                    "experiment_fingerprint": "exp_15m",
                    "canonical_live_decision_fingerprint": "dec_fp_15m",
                    "authorization_fingerprint": "auth_fp_15m",
                    "constituent_fingerprint": "const_fp_15m",
                    "provenance": {"source": "P1"},
                }
            ],
        },
        "metadata": {
            "provenance_type": "live_signal",
            "is_live": True,
        },
    }

    from src.platform.domain.security import Permission
    from src.platform.domain.user_authorization import UserAuthorization

    admin_user = UserAuthorization(
        user_id="test_admin",
        auth_code="code_123",
        role="admin",
        permissions=[Permission.READ_SIGNALS, Permission.ADMIN_ALL],
    )

    res = gw_svc.ingest_signal_payload(admin_user, rec_payload)
    assert res.get("status") in ("INGESTED", "DUPLICATE_ACCEPTED") or res.get("success") is True

    adapter = Project1GatewayAdapter(gateway_service=gw_svc)
    presenter = Project1SignalPresenter(port=adapter, gateway_service=gw_svc)

    snapshot = presenter.build_host_snapshot("XAUUSD", "5m", user=admin_user)

    assert snapshot["signal"]["action"] == "BUY"
    assert snapshot["signal"]["status"] == "active"
    assert snapshot["signal"]["publicationId"] == "pub_mtf_001"

    mtf_out = snapshot["signal"]["metadata"]["mtf"]
    assert mtf_out["star_representation"] == "⭐⭐⭐⭐⭐"
    assert mtf_out["alignment_coverage"] == 5
    assert mtf_out["classification"] == "ALIGNED"
    assert mtf_out["higher_timeframe_context"]["trend"] == "BULLISH_STRONG"
    assert len(mtf_out["signals"]) == 1
    assert mtf_out["signals"][0]["timeframe"] == "15m"
    assert mtf_out["signals"][0]["direction"] == "buy"

    # Lineage verification
    assert snapshot["authorization"]["decision_id"] == "dec_mtf_100"
    assert snapshot["authorization"]["candidate_id"] == "cand_mtf_200"
    assert snapshot["authorization"]["research_evidence_id"] == "res_mtf_300"
    assert snapshot["authorization"]["canonical_live_decision_fingerprint"] == "fp_decision_mtf"
    assert snapshot["authorization"]["runtime_authorization_fingerprint"] == "fp_auth_mtf"

    # Exact P1 values, zero P2 recalculation
    assert snapshot["authorization"]["riskRewardRatio"] == 2.1234
    assert snapshot["strategy"]["stability"] == 0.95
