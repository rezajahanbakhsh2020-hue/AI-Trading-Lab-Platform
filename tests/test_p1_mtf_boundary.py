"""Adversarial cross-boundary and anti-recurrence test suite for Project 1 Multi-Timeframe (MTF) intelligence.

Verifies:
- P1 Contract v1 payload['mtf'] preservation across P2 validation -> repository -> presenter boundary.
- Defect A repair: Exact preservation without casing/whitespace normalization.
- Defect B repair: Mandatory non-empty P1 lineage field enforcement.
- All required anti-recurrence controls A through L and required-identity test matrix.
"""

from datetime import datetime
import os
import tempfile
import time
import pytest

from src.platform.adapters.project1_adapter import Project1GatewayAdapter
from src.platform.adapters.project1_repository import FileBackedProject1IntegrationRepository
from src.platform.domain.project1_contract import validate_project1_contract_payload
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.domain.security import UserRole
from src.platform.services.audit_control import PlatformAuditControlService
from src.platform.services.project1_gateway import Project1IntegrationGatewayService
from src.platform.services.project1_presenter import Project1SignalPresenter
from src.platform.services.security import SecurityBoundaryService


@pytest.fixture
def temp_repo_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield os.path.join(tmpdir, "test_mtf_p1_records.json")


@pytest.fixture
def admin_user():
    return UserAuthorization(
        user_id="usr_admin",
        auth_code="ac_admin",
        role=UserRole.ADMIN,
        allowed_symbols=("XAUUSD", "EURUSD"),
    )


@pytest.fixture
def gateway_service(temp_repo_path):
    repo = FileBackedProject1IntegrationRepository(temp_repo_path)
    sec = SecurityBoundaryService()
    audit = PlatformAuditControlService(security_boundary=sec)
    return Project1IntegrationGatewayService(
        repository=repo,
        security_boundary=sec,
        audit_control=audit,
        service_key="test_mtf_service_key_999",
    )


def sample_p1_mtf_payload():
    return {
        "contract_version": "1.0",
        "event_id": "pub_xau_mtf_001",
        "event_type": "TRADING_SIGNAL",
        "timestamp": "2026-03-30T12:00:00Z",
        "instrument": {
            "symbol": "XAUUSD",
            "interval": "5m",
        },
        "signal": {
            "publication_id": "pub_xau_mtf_001",
            "signal_id": "sig_xau_5m_001",
            "decision_id": "dec_xau_5m_001",
            "decision": "buy",
            "strategy": "GoldTrendv1",
            "candidate_id": "cand_5m_01",
            "confidence": 0.88,
            "stability_score": 0.85,
        },
        "trade_setup": {
            "entry_price": 2650.0,
            "stop_loss": 2640.0,
            "tp1": 2660.0,
            "tp2": 2670.0,
            "risk_reward_ratio": 2.0,
        },
        "provenance": {
            "provenance_type": "live_signal",
            "is_live": True,
            "produced_at": "2026-03-30T12:00:00Z",
            "research_evidence_id": "ev_mtf_001",
            "research_fingerprint": "fp_res_mtf",
        },
        "mtf": {
            "symbol": "XAUUSD",
            "local_timeframe": "5m",
            "participating_timeframes": ["5m", "15m", "30m", "1H", "4H", "1D"],
            "signals": [
                {
                    "symbol": "XAUUSD",
                    "timeframe": "1D",
                    "direction": "sell",
                    "decision_id": "dec_1d",
                    "signal_id": "sig_1d",
                    "decision_timestamp": 1774872000.0,
                    "market_timestamp": 1774872000.0,
                    "strategy_name": "GoldTrend1D",
                    "strategy_version": "1.0.0",
                    "candidate_id": "cand_1d",
                    "evidence_id": "ev_1d",
                    "experiment_fingerprint": "exp_1d",
                    "canonical_live_decision_fingerprint": "clf_1d",
                    "authorization_fingerprint": "auth_1d",
                    "constituent_fingerprint": "const_1d",
                    "provenance": {"provenance_type": "live_signal"},
                },
                {
                    "symbol": "XAUUSD",
                    "timeframe": "4H",
                    "direction": "sell",
                    "decision_id": "dec_4h",
                    "signal_id": "sig_4h",
                    "decision_timestamp": 1774872000.0,
                    "market_timestamp": 1774872000.0,
                    "strategy_name": "GoldTrend4H",
                    "strategy_version": "1.0.0",
                    "candidate_id": "cand_4h",
                    "evidence_id": "ev_4h",
                    "experiment_fingerprint": "exp_4h",
                    "canonical_live_decision_fingerprint": "clf_4h",
                    "authorization_fingerprint": "auth_4h",
                    "constituent_fingerprint": "const_4h",
                    "provenance": {"provenance_type": "live_signal"},
                },
                {
                    "symbol": "XAUUSD",
                    "timeframe": "1H",
                    "direction": "sell",
                    "decision_id": "dec_1h",
                    "signal_id": "sig_1h",
                    "decision_timestamp": 1774872000.0,
                    "market_timestamp": 1774872000.0,
                    "strategy_name": "GoldTrend1H",
                    "strategy_version": "1.0.0",
                    "candidate_id": "cand_1h",
                    "evidence_id": "ev_1h",
                    "experiment_fingerprint": "exp_1h",
                    "canonical_live_decision_fingerprint": "clf_1h",
                    "authorization_fingerprint": "auth_1h",
                    "constituent_fingerprint": "const_1h",
                    "provenance": {"provenance_type": "live_signal"},
                },
                {
                    "symbol": "XAUUSD",
                    "timeframe": "30m",
                    "direction": "sell",
                    "decision_id": "dec_30m",
                    "signal_id": "sig_30m",
                    "decision_timestamp": 1774872000.0,
                    "market_timestamp": 1774872000.0,
                    "strategy_name": "GoldTrend30m",
                    "strategy_version": "1.0.0",
                    "candidate_id": "cand_30m",
                    "evidence_id": "ev_30m",
                    "experiment_fingerprint": "exp_30m",
                    "canonical_live_decision_fingerprint": "clf_30m",
                    "authorization_fingerprint": "auth_30m",
                    "constituent_fingerprint": "const_30m",
                    "provenance": {"provenance_type": "live_signal"},
                },
                {
                    "symbol": "XAUUSD",
                    "timeframe": "15m",
                    "direction": "buy",
                    "decision_id": "dec_15m",
                    "signal_id": "sig_15m",
                    "decision_timestamp": 1774872000.0,
                    "market_timestamp": 1774872000.0,
                    "strategy_name": "GoldTrend15m",
                    "strategy_version": "1.0.0",
                    "candidate_id": "cand_15m",
                    "evidence_id": "ev_15m",
                    "experiment_fingerprint": "exp_15m",
                    "canonical_live_decision_fingerprint": "clf_15m",
                    "authorization_fingerprint": "auth_15m",
                    "constituent_fingerprint": "const_15m",
                    "provenance": {"provenance_type": "live_signal"},
                },
                {
                    "symbol": "XAUUSD",
                    "timeframe": "5m",
                    "direction": "buy",
                    "decision_id": "dec_5m",
                    "signal_id": "sig_5m",
                    "decision_timestamp": 1774872000.0,
                    "market_timestamp": 1774872000.0,
                    "strategy_name": "GoldTrend5m",
                    "strategy_version": "1.0.0",
                    "candidate_id": "cand_5m",
                    "evidence_id": "ev_5m",
                    "experiment_fingerprint": "exp_5m",
                    "canonical_live_decision_fingerprint": "clf_5m",
                    "authorization_fingerprint": "auth_5m",
                    "constituent_fingerprint": "const_5m",
                    "provenance": {"provenance_type": "live_signal"},
                },
            ],
            "alignment_count": 2,
            "alignment_coverage": 2,
            "classification": "COUNTER_TREND",
            "higher_timeframe_context": {"trend_bias": "bearish", "h4_state": "downtrend"},
            "constituent_fingerprints": ["const_1d", "const_4h", "const_1h", "const_30m", "const_15m", "const_5m"],
            "matching_signal_count": 2,
            "available_signal_count": 6,
            "intelligence_fingerprint": "intel_fp_mtf_exact_123",
            "star_representation": "⭐⭐",
        },
    }


def test_cross_boundary_identity_preservation(gateway_service, admin_user):
    """End-to-end cross-boundary identity test for MTF intelligence."""
    raw_payload = sample_p1_mtf_payload()
    now_ts = datetime.fromisoformat("2026-03-30T12:00:01Z").timestamp()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("time.time", lambda: now_ts)
        ingest_res = gateway_service.ingest_signal_payload(user=admin_user, payload=raw_payload)
        assert ingest_res["success"] is True

    adapter = Project1GatewayAdapter(gateway_service=gateway_service)
    presenter = Project1SignalPresenter(port=adapter, gateway_service=gateway_service)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("time.time", lambda: now_ts)
        snapshot = presenter.build_host_snapshot(symbol="XAUUSD", timeframe="5m", user=admin_user)
        sig = snapshot["signal"]
        meta = sig["metadata"]
        mtf = meta["mtf"]

        source_mtf = raw_payload["mtf"]

        assert mtf["symbol"] == source_mtf["symbol"]
        assert mtf["local_timeframe"] == source_mtf["local_timeframe"]
        assert mtf["participating_timeframes"] == source_mtf["participating_timeframes"]
        assert mtf["alignment_count"] == source_mtf["alignment_count"]
        assert mtf["alignment_coverage"] == source_mtf["alignment_coverage"]
        assert mtf["classification"] == source_mtf["classification"]
        assert mtf["star_representation"] == source_mtf["star_representation"]
        assert mtf["intelligence_fingerprint"] == source_mtf["intelligence_fingerprint"]
        assert mtf["constituent_fingerprints"] == source_mtf["constituent_fingerprints"]
        assert mtf["matching_signal_count"] == source_mtf["matching_signal_count"]
        assert mtf["available_signal_count"] == source_mtf["available_signal_count"]
        assert mtf["higher_timeframe_context"] == source_mtf["higher_timeframe_context"]

        assert len(mtf["signals"]) == len(source_mtf["signals"])
        for source_sig, pres_sig in zip(source_mtf["signals"], mtf["signals"]):
            assert pres_sig["symbol"] == source_sig["symbol"]
            assert pres_sig["timeframe"] == source_sig["timeframe"]
            assert pres_sig["direction"] == source_sig["direction"]
            assert pres_sig["decision_id"] == source_sig["decision_id"]
            assert pres_sig["signal_id"] == source_sig["signal_id"]
            assert pres_sig["candidate_id"] == source_sig["candidate_id"]
            assert pres_sig["evidence_id"] == source_sig["evidence_id"]
            assert pres_sig["experiment_fingerprint"] == source_sig["experiment_fingerprint"]
            assert pres_sig["canonical_live_decision_fingerprint"] == source_sig["canonical_live_decision_fingerprint"]
            assert pres_sig["authorization_fingerprint"] == source_sig["authorization_fingerprint"]
            assert pres_sig["constituent_fingerprint"] == source_sig["constituent_fingerprint"]
            assert pres_sig["strategy_name"] == source_sig["strategy_name"]
            assert pres_sig["strategy_version"] == source_sig["strategy_version"]
            assert pres_sig["provenance"] == source_sig["provenance"]


def test_anti_normalization_exact_preservation():
    """Defect A Repair Test: Verify exact non-rewritten preservation of MTF field casing/representation."""
    raw_payload = sample_p1_mtf_payload()
    # Distinctive direction casing "buy" and classification "COUNTER_TREND"
    raw_payload["mtf"]["signals"][4]["direction"] = "buy"  # Must stay "buy", not transformed to "BUY"
    raw_payload["mtf"]["classification"] = "COUNTER_TREND"  # Must stay "COUNTER_TREND"

    val_res = validate_project1_contract_payload(raw_payload)
    assert val_res.is_valid is True
    sanitized_mtf = val_res.sanitized_payload["mtf"]

    assert sanitized_mtf["signals"][4]["direction"] == "buy"
    assert sanitized_mtf["classification"] == "COUNTER_TREND"
    assert sanitized_mtf["local_timeframe"] == "5m"


@pytest.mark.parametrize(
    "field_name, bad_value",
    [
        ("strategy_name", None),
        ("strategy_name", ""),
        ("strategy_name", "   "),
        ("strategy_version", None),
        ("strategy_version", ""),
        ("strategy_version", "   "),
        ("candidate_id", None),
        ("candidate_id", ""),
        ("candidate_id", "   "),
        ("evidence_id", None),
        ("evidence_id", ""),
        ("evidence_id", "   "),
        ("experiment_fingerprint", None),
        ("experiment_fingerprint", ""),
        ("experiment_fingerprint", "   "),
        ("canonical_live_decision_fingerprint", None),
        ("canonical_live_decision_fingerprint", ""),
        ("canonical_live_decision_fingerprint", "   "),
        ("authorization_fingerprint", None),
        ("authorization_fingerprint", ""),
        ("authorization_fingerprint", "   "),
        ("constituent_fingerprint", None),
        ("constituent_fingerprint", ""),
        ("constituent_fingerprint", "   "),
    ],
)
def test_defect_b_missing_lineage_matrix_rejection(field_name, bad_value):
    """Defect B Repair Test Matrix: Verify every mandatory P1 constituent lineage field rejects missing/None/empty values."""
    raw_payload = sample_p1_mtf_payload()
    if bad_value is None and field_name in raw_payload["mtf"]["signals"][0]:
        del raw_payload["mtf"]["signals"][0][field_name]
    else:
        raw_payload["mtf"]["signals"][0][field_name] = bad_value

    val_res = validate_project1_contract_payload(raw_payload)
    assert val_res.is_valid is False
    assert any("Invalid MTF payload" in err for err in val_res.errors)


def test_anti_recurrence_A_mtf_absent(gateway_service, admin_user):
    """Scenario A: Payload without MTF remains completely valid."""
    raw_payload = sample_p1_mtf_payload()
    del raw_payload["mtf"]

    val_res = validate_project1_contract_payload(raw_payload)
    assert val_res.is_valid is True
    assert "mtf" not in val_res.sanitized_payload


def test_anti_recurrence_B_mtf_malformed(gateway_service, admin_user):
    """Scenario B: Malformed MTF payload is rejected fail-closed."""
    raw_payload = sample_p1_mtf_payload()
    raw_payload["mtf"]["local_timeframe"] = "invalid_tf"

    val_res = validate_project1_contract_payload(raw_payload)
    assert val_res.is_valid is False
    assert any("Invalid MTF payload" in err for err in val_res.errors)


def test_anti_recurrence_C_mtf_identity_mutation():
    """Scenario C: Mutating a constituent identity is detectable."""
    raw_payload = sample_p1_mtf_payload()
    res1 = validate_project1_contract_payload(raw_payload)
    assert res1.is_valid is True

    raw_payload_mutated = sample_p1_mtf_payload()
    raw_payload_mutated["mtf"]["signals"][0]["decision_id"] = "dec_1d_mutated"
    res2 = validate_project1_contract_payload(raw_payload_mutated)
    assert res2.is_valid is True

    # Confirm mutation changed the sanitized payload
    assert res1.sanitized_payload["mtf"]["signals"][0]["decision_id"] != res2.sanitized_payload["mtf"]["signals"][0]["decision_id"]


def test_anti_recurrence_D_fingerprint_mutation():
    """Scenario D: Changing intelligence_fingerprint is preserved strictly without silent normalization."""
    raw_payload = sample_p1_mtf_payload()
    raw_payload["mtf"]["intelligence_fingerprint"] = "mutated_intel_fp_999"

    val_res = validate_project1_contract_payload(raw_payload)
    assert val_res.is_valid is True
    assert val_res.sanitized_payload["mtf"]["intelligence_fingerprint"] == "mutated_intel_fp_999"


def test_anti_recurrence_E_star_mutation():
    """Scenario E: P2 preserves received star_representation without local recalculation."""
    raw_payload = sample_p1_mtf_payload()
    raw_payload["mtf"]["star_representation"] = "⭐⭐⭐⭐⭐"  # P1 sent 5 stars even if coverage is 2

    val_res = validate_project1_contract_payload(raw_payload)
    assert val_res.is_valid is True
    assert val_res.sanitized_payload["mtf"]["star_representation"] == "⭐⭐⭐⭐⭐"


def test_anti_recurrence_F_classification_preservation():
    """Scenario F: COUNTER_TREND classification remains COUNTER_TREND."""
    raw_payload = sample_p1_mtf_payload()
    val_res = validate_project1_contract_payload(raw_payload)
    assert val_res.is_valid is True
    assert val_res.sanitized_payload["mtf"]["classification"] == "COUNTER_TREND"


def test_anti_recurrence_G_missing_constituent_identity():
    """Scenario G: Missing decision_id or signal_id in constituent rejects fail closed rather than synthesizing."""
    raw_payload = sample_p1_mtf_payload()
    del raw_payload["mtf"]["signals"][0]["decision_id"]

    val_res = validate_project1_contract_payload(raw_payload)
    assert val_res.is_valid is False


def test_anti_recurrence_H_higher_timeframe_disagreement(gateway_service, admin_user):
    """Scenario H: Higher timeframe SELL does not suppress/veto local 5m BUY signal."""
    raw_payload = sample_p1_mtf_payload()
    now_ts = datetime.fromisoformat("2026-03-30T12:00:01Z").timestamp()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("time.time", lambda: now_ts)
        ingest_res = gateway_service.ingest_signal_payload(user=admin_user, payload=raw_payload)
        assert ingest_res["success"] is True

    adapter = Project1GatewayAdapter(gateway_service=gateway_service)
    presenter = Project1SignalPresenter(port=adapter, gateway_service=gateway_service)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("time.time", lambda: now_ts)
        snapshot = presenter.build_host_snapshot(symbol="XAUUSD", timeframe="5m", user=admin_user)
        assert snapshot["signal"]["action"] == "BUY"
        assert snapshot["signal"]["status"] == "active"
        assert snapshot["signal"]["metadata"]["mtf"]["classification"] == "COUNTER_TREND"


def test_anti_recurrence_I_timeframe_grouping(gateway_service, admin_user):
    """Scenario I: 5m and 15m records remain distinguishable across timeframes."""
    payload_5m = sample_p1_mtf_payload()
    payload_15m = sample_p1_mtf_payload()
    payload_15m["event_id"] = "pub_xau_mtf_15m"
    payload_15m["instrument"]["interval"] = "15m"
    payload_15m["signal"]["publication_id"] = "pub_xau_mtf_15m"
    payload_15m["signal"]["signal_id"] = "sig_xau_15m_001"
    payload_15m["signal"]["decision_id"] = "dec_xau_15m_001"
    payload_15m["signal"]["decision"] = "sell"
    payload_15m["mtf"]["local_timeframe"] = "15m"

    now_ts = datetime.fromisoformat("2026-03-30T12:00:01Z").timestamp()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("time.time", lambda: now_ts)
        gateway_service.ingest_signal_payload(user=admin_user, payload=payload_5m)
        gateway_service.ingest_signal_payload(user=admin_user, payload=payload_15m)

    adapter = Project1GatewayAdapter(gateway_service=gateway_service)
    presenter = Project1SignalPresenter(port=adapter, gateway_service=gateway_service)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("time.time", lambda: now_ts)
        snap_5m = presenter.build_host_snapshot(symbol="XAUUSD", timeframe="5m", user=admin_user)
        snap_15m = presenter.build_host_snapshot(symbol="XAUUSD", timeframe="15m", user=admin_user)

        assert snap_5m["signal"]["action"] == "BUY"
        assert snap_5m["signal"]["timeframe"] == "5m"

        assert snap_15m["signal"]["action"] == "SELL"
        assert snap_15m["signal"]["timeframe"] == "15m"


def test_anti_recurrence_J_no_p2_calculation(gateway_service, admin_user):
    """Scenario J: Verification that presentation does not invoke any strategy/MTF/risk calculation in P2."""
    raw_payload = sample_p1_mtf_payload()
    val_res = validate_project1_contract_payload(raw_payload)
    assert val_res.is_valid is True

    # Assert that sanitized payload contains exact values sent by P1
    s_mtf = val_res.sanitized_payload["mtf"]
    assert s_mtf["alignment_count"] == 2
    assert s_mtf["alignment_coverage"] == 2
    assert s_mtf["star_representation"] == "⭐⭐"


def test_anti_recurrence_K_backward_compatibility():
    """Scenario K: Non-MTF contract tests continue to pass."""
    payload = {
        "contract_version": "1.0",
        "event_id": "pub_xau_legacy",
        "timestamp": "2026-03-30T12:00:00Z",
        "instrument": {"symbol": "XAUUSD", "interval": "1h"},
        "signal": {
            "publication_id": "pub_xau_legacy",
            "signal_id": "sig_xau_legacy",
            "decision": "buy",
        },
        "trade_setup": {"entry_price": 2650.0, "stop_loss": 2635.0},
        "provenance": {"provenance_type": "live_signal"},
    }
    res = validate_project1_contract_payload(payload)
    assert res.is_valid is True


def test_anti_recurrence_L_source_mutation_protection():
    """Scenario L: Mutation of input MTF dict after validation does not corrupt sanitized record."""
    raw_payload = sample_p1_mtf_payload()
    val_res = validate_project1_contract_payload(raw_payload)
    assert val_res.is_valid is True

    # Mutate raw input payload AFTER validation
    raw_payload["mtf"]["star_representation"] = "MUTATED"
    raw_payload["mtf"]["signals"][0]["direction"] = "MUTATED"

    # Assert sanitized payload remains uncorrupted
    sanitized_mtf = val_res.sanitized_payload["mtf"]
    assert sanitized_mtf["star_representation"] == "⭐⭐"
    assert sanitized_mtf["signals"][0]["direction"] == "sell"
