"""Cross-Repository Behavioral E2E Proof and Adversarial Visibility Test Suite.

Proves end-to-end that an authoritative Project 1 live publication passes through:
Contract v1.0 Payload -> Ingestion Endpoint -> Integration Repository -> Gateway Adapter -> Signal Presenter -> Snapshot Endpoint -> Visible Signal
and is accurately presented as an ACTIVE, current Project 1 signal in HostSnapshot.

Also asserts adversarial visibility rules A through J.
"""

from datetime import datetime, timezone
import json
import os
import tempfile
import threading
import time
import urllib.request
import urllib.error
import pytest

from src.platform.config import PlatformConfig
from src.platform.server import create_server


@pytest.fixture
def p2_e2e_server():
    """Start a production-configured Project 2 server instance for cross-boundary E2E testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = PlatformConfig(
            app_env="testing",
            session_secret="testing_session_secret_32_chars_min_key_2026!",
            project1_service_key="test_p1_service_key_secret_2026",
            persistence_dir=tmp_dir,
        )
        server = create_server(host="127.0.0.1", port=0, config=cfg)
        host, port = server.socket.getsockname()
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        base_url = f"http://{host}:{port}"

        yield base_url, cfg, server

        server.shutdown()
        server.server_close()


def test_positive_cross_boundary_p1_to_p2_visible_signal(p2_e2e_server):
    """Phase 3: Prove end-to-end that an authoritative P1 signal payload becomes a visible active signal in HostSnapshot."""
    base_url, cfg, server_inst = p2_e2e_server

    now_iso = datetime.now(timezone.utc).isoformat()
    publication_id = "pub_xau_live_8888"
    event_id = publication_id
    signal_id = "sig_xau_live_8888"
    decision_id = "dec_xau_live_8888"
    candidate_id = "cand_xau_live_8888"
    research_evidence_id = "ev_xau_live_8888"
    decision_fp = "fp_live_decision_12345"
    auth_fp = "fp_runtime_auth_67890"

    # Step 3: P1 Contract v1.0 Payload
    payload = {
        "contract_version": "1.0",
        "event_id": event_id,
        "event_type": "TRADING_SIGNAL",
        "timestamp": now_iso,
        "instrument": {
            "symbol": "XAUUSD",
            "interval": "1h",
        },
        "signal": {
            "publication_id": publication_id,
            "signal_id": signal_id,
            "decision_id": decision_id,
            "decision": "buy",
            "strategy": "GoldTrendv1",
            "candidate_id": candidate_id,
            "confidence": 0.94,
            "stability_score": 0.91,
            "canonical_live_decision_fingerprint": decision_fp,
            "runtime_authorization_fingerprint": auth_fp,
        },
        "trade_setup": {
            "entry_price": 2650.5,
            "stop_loss": 2635.0,
            "tp1": 2670.0,
            "tp2": 2690.0,
            "tp3": 2710.0,
            "risk_reward_ratio": 2.63,
        },
        "provenance": {
            "provenance_type": "live_signal",
            "is_live": True,
            "produced_at": now_iso,
            "source": "AI-Trading-Lab",
            "research_evidence_id": research_evidence_id,
            "research_fingerprint": "rfp_999",
        },
    }

    # Step 4: POST /api/v1/integration/project1/ingest with PROJECT1_SERVICE_KEY
    headers = {
        "Authorization": f"Bearer {cfg.project1_service_key}",
        "Content-Type": "application/json",
    }
    req_ingest = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    # Step 5: Verify HTTP 200 and acknowledgement identity
    with urllib.request.urlopen(req_ingest) as resp:
        assert resp.status == 200
        ack = json.loads(resp.read().decode("utf-8"))
        assert ack["success"] is True
        assert ack["status"] == "INGESTED"
        assert ack["event_id"] == event_id
        assert ack["publication_id"] == publication_id
        assert ack["signal_id"] == signal_id

    # Step 6 & 7: Verify record persisted in repository
    from src.platform.server import PlatformRequestHandler
    handler_cls = server_inst.RequestHandlerClass
    gateway_svc = handler_cls.gateway_service
    repo = gateway_svc._repo
    records = repo.list_records_for_user(user_id=None, symbol="XAUUSD", limit=10, allow_system=True)
    assert len(records) > 0
    rec = next(r for r in records if r["signal_id"] == signal_id)
    assert rec["publication_id"] == publication_id

    # Step 8, 9, 10, 11, 12: Verify Project1GatewayAdapter
    presenter = handler_cls.presenter
    adapter = presenter._port
    pres_sig = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h")
    assert pres_sig is not None
    assert pres_sig.signal_id == signal_id
    assert pres_sig.symbol == "XAUUSD"
    assert pres_sig.signal_type == "buy"
    assert pres_sig.metadata.get("provenance_type") == "live_signal"
    assert pres_sig.metadata.get("publication_id") == publication_id
    assert pres_sig.metadata.get("decision_id") == decision_id

    # Step 13: Verify Project1SignalPresenter
    pres_res = presenter.present_signal(symbol="XAUUSD", timeframe="1h")
    assert pres_res["status"] == "active"
    assert pres_res["signal"] is not None
    assert pres_res["signal"]["signal_type"] == "buy"

    # Step 14: Query GET /api/v1/snapshot?symbol=XAUUSD&timeframe=1h
    req_snap = urllib.request.Request(
        f"{base_url}/api/v1/snapshot?symbol=XAUUSD&timeframe=1h",
        headers={"Content-Type": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req_snap) as snap_resp:
        assert snap_resp.status == 200
        snapshot = json.loads(snap_resp.read().decode("utf-8"))

        # Step 15: Verify Snapshot Fields
        assert snapshot["project1"]["connected"] is True
        assert snapshot["signal"]["status"] == "active"
        assert snapshot["signal"]["action"] == "BUY"
        assert snapshot["signal"]["signalId"] == signal_id
        assert snapshot["signal"]["metadata"]["publication_id"] == publication_id
        assert snapshot["signal"]["symbol"] == "XAUUSD"
        assert snapshot["signal"]["timeframe"] == "1h"

        # Verify trade setup levels
        assert snapshot["risk"]["entry"] == 2650.5
        assert snapshot["risk"]["stopLoss"] == 2635.0
        assert snapshot["risk"]["takeProfits"] == [2670.0, 2690.0, 2710.0]

        # Verify lineage metadata
        sig_meta = snapshot["signal"]["metadata"]
        assert sig_meta.get("publication_id") == publication_id
        assert sig_meta.get("event_id") == event_id
        assert sig_meta.get("decision_id") == decision_id
        assert sig_meta.get("candidate_id") == candidate_id
        assert sig_meta.get("canonical_live_decision_fingerprint") == decision_fp
        assert sig_meta.get("runtime_authorization_fingerprint") == auth_fp

        # Step 16: Final assertion
        assert snapshot["signal"]["status"] == "active", "P1 signal is visible through the Project 2 host snapshot."


def test_adversarial_A_missing_provenance_type(p2_e2e_server):
    """Adversarial A: Payload missing provenance_type must ingest but NOT become active Current Signal."""
    base_url, cfg, _ = p2_e2e_server
    now_iso = datetime.now(timezone.utc).isoformat()

    payload = {
        "contract_version": "1.0",
        "event_id": "pub_adv_A",
        "event_type": "TRADING_SIGNAL",
        "timestamp": now_iso,
        "instrument": {"symbol": "XAUUSD", "interval": "1h"},
        "signal": {
            "publication_id": "pub_adv_A",
            "signal_id": "sig_adv_A",
            "decision": "buy",
            "strategy": "GoldStrategy",
        },
        "trade_setup": {"entry_price": 2650.0, "stop_loss": 2635.0},
        "provenance": {},  # Missing provenance_type
    }

    req = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {cfg.project1_service_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        ack = json.loads(resp.read().decode("utf-8"))
        assert ack["success"] is True

    # Check snapshot: MUST NOT be active
    req_snap = urllib.request.Request(f"{base_url}/api/v1/snapshot?symbol=XAUUSD&timeframe=1h")
    with urllib.request.urlopen(req_snap) as snap_resp:
        snap = json.loads(snap_resp.read().decode("utf-8"))
        assert snap["signal"]["status"] != "active"
        assert snap["signal"]["action"] == "NO SIGNAL" or snap["signal"]["signalId"] != "sig_adv_A"


def test_adversarial_B_historical_provenance(p2_e2e_server):
    """Adversarial B: Payload with provenance_type='lab_artifact' must NOT become active Current Signal."""
    base_url, cfg, _ = p2_e2e_server
    now_iso = datetime.now(timezone.utc).isoformat()

    payload = {
        "contract_version": "1.0",
        "event_id": "pub_adv_B",
        "event_type": "TRADING_SIGNAL",
        "timestamp": now_iso,
        "instrument": {"symbol": "XAUUSD", "interval": "1h"},
        "signal": {
            "publication_id": "pub_adv_B",
            "signal_id": "sig_adv_B",
            "decision": "buy",
            "strategy": "GoldStrategy",
        },
        "trade_setup": {"entry_price": 2650.0, "stop_loss": 2635.0},
        "provenance": {"provenance_type": "lab_artifact", "is_historical": True},
    }

    req = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {cfg.project1_service_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        ack = json.loads(resp.read().decode("utf-8"))
        assert ack["success"] is True

    req_snap = urllib.request.Request(f"{base_url}/api/v1/snapshot?symbol=XAUUSD&timeframe=1h")
    with urllib.request.urlopen(req_snap) as snap_resp:
        snap = json.loads(snap_resp.read().decode("utf-8"))
        assert snap["signal"]["status"] != "active"


def test_adversarial_C_stale_signal(p2_e2e_server):
    """Adversarial C: Signal with publication timestamp > 300s old remains active signal according to contract."""
    base_url, cfg, _ = p2_e2e_server
    stale_iso = datetime.fromtimestamp(time.time() - 600, tz=timezone.utc).isoformat()

    payload = {
        "contract_version": "1.0",
        "event_id": "pub_adv_C",
        "event_type": "TRADING_SIGNAL",
        "timestamp": stale_iso,
        "instrument": {"symbol": "XAUUSD", "interval": "1h"},
        "signal": {
            "publication_id": "pub_adv_C",
            "signal_id": "sig_adv_C",
            "decision": "buy",
            "strategy": "GoldStrategy",
        },
        "trade_setup": {"entry_price": 2650.0, "stop_loss": 2635.0},
        "provenance": {"provenance_type": "live_signal", "is_live": True, "produced_at": stale_iso},
    }

    req = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {cfg.project1_service_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        ack = json.loads(resp.read().decode("utf-8"))
        assert ack["success"] is True

    req_snap = urllib.request.Request(f"{base_url}/api/v1/snapshot?symbol=XAUUSD&timeframe=1h")
    with urllib.request.urlopen(req_snap) as snap_resp:
        snap = json.loads(snap_resp.read().decode("utf-8"))
        assert snap["signal"]["status"] == "active"


def test_adversarial_D_future_timestamp(p2_e2e_server):
    """Adversarial D: Signal with future timestamp (>5s) must be rejected at ingestion boundary."""
    base_url, cfg, _ = p2_e2e_server
    future_iso = datetime.fromtimestamp(time.time() + 3600, tz=timezone.utc).isoformat()

    payload = {
        "contract_version": "1.0",
        "event_id": "pub_adv_D",
        "event_type": "TRADING_SIGNAL",
        "timestamp": future_iso,
        "instrument": {"symbol": "XAUUSD", "interval": "1h"},
        "signal": {
            "publication_id": "pub_adv_D",
            "signal_id": "sig_adv_D",
            "decision": "buy",
            "strategy": "GoldStrategy",
        },
        "trade_setup": {"entry_price": 2650.0, "stop_loss": 2635.0},
        "provenance": {"provenance_type": "live_signal"},
    }

    req = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {cfg.project1_service_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)

    assert exc_info.value.code in (400, 422)


def test_adversarial_E_wrong_symbol_mismatch(p2_e2e_server):
    """Adversarial E: XAUUSD signal must NOT be presented when querying EURUSD snapshot."""
    base_url, cfg, _ = p2_e2e_server
    now_iso = datetime.now(timezone.utc).isoformat()

    payload = {
        "contract_version": "1.0",
        "event_id": "pub_adv_E",
        "event_type": "TRADING_SIGNAL",
        "timestamp": now_iso,
        "instrument": {"symbol": "XAUUSD", "interval": "1h"},
        "signal": {
            "publication_id": "pub_adv_E",
            "signal_id": "sig_adv_E",
            "decision": "buy",
            "strategy": "GoldStrategy",
        },
        "trade_setup": {"entry_price": 2650.0, "stop_loss": 2635.0},
        "provenance": {"provenance_type": "live_signal", "is_live": True},
    }

    req = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {cfg.project1_service_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        ack = json.loads(resp.read().decode("utf-8"))
        assert ack["success"] is True

    # Query EURUSD snapshot
    req_snap = urllib.request.Request(f"{base_url}/api/v1/snapshot?symbol=EURUSD&timeframe=1h")
    with urllib.request.urlopen(req_snap) as snap_resp:
        snap = json.loads(snap_resp.read().decode("utf-8"))
        assert snap["signal"]["status"] != "active" or snap["signal"]["symbol"] == "EURUSD"
        assert snap["signal"]["signalId"] != "sig_adv_E"


def test_adversarial_F_cancelled_lifecycle_state(p2_e2e_server):
    """Adversarial F: Inactive lifecycle state (e.g. CANCELLED) must NOT become active Current Signal."""
    base_url, cfg, _ = p2_e2e_server
    now_iso = datetime.now(timezone.utc).isoformat()

    payload = {
        "contract_version": "1.0",
        "event_id": "pub_adv_F",
        "event_type": "TRADING_SIGNAL",
        "timestamp": now_iso,
        "instrument": {"symbol": "XAUUSD", "interval": "1h"},
        "signal": {
            "publication_id": "pub_adv_F",
            "signal_id": "sig_adv_F",
            "decision": "buy",
            "lifecycle_state": "CANCELLED",
            "strategy": "GoldStrategy",
        },
        "trade_setup": {"entry_price": 2650.0, "stop_loss": 2635.0},
        "provenance": {"provenance_type": "live_signal", "is_live": True},
    }

    req = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {cfg.project1_service_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        ack = json.loads(resp.read().decode("utf-8"))
        assert ack["success"] is True

    req_snap = urllib.request.Request(f"{base_url}/api/v1/snapshot?symbol=XAUUSD&timeframe=1h")
    with urllib.request.urlopen(req_snap) as snap_resp:
        snap = json.loads(snap_resp.read().decode("utf-8"))
        assert snap["signal"]["status"] != "active" or snap["signal"]["signalId"] != "sig_adv_F"


def test_adversarial_G_no_trade_decision(p2_e2e_server):
    """Adversarial G: NO TRADE / no-trade decision must ingest but NOT become an active BUY/SELL signal."""
    base_url, cfg, _ = p2_e2e_server
    now_iso = datetime.now(timezone.utc).isoformat()

    payload = {
        "contract_version": "1.0",
        "event_id": "pub_adv_G",
        "event_type": "TRADING_SIGNAL",
        "timestamp": now_iso,
        "instrument": {"symbol": "XAUUSD", "interval": "1h"},
        "signal": {
            "publication_id": "pub_adv_G",
            "signal_id": "sig_adv_G",
            "decision": "NO TRADE",
            "strategy": "GoldStrategy",
        },
        "trade_setup": {},
        "provenance": {"provenance_type": "live_signal", "is_live": True, "produced_at": now_iso},
    }

    req = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {cfg.project1_service_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        ack = json.loads(resp.read().decode("utf-8"))
        assert ack["success"] is True

    req_snap = urllib.request.Request(f"{base_url}/api/v1/snapshot?symbol=XAUUSD&timeframe=1h")
    with urllib.request.urlopen(req_snap) as snap_resp:
        snap = json.loads(snap_resp.read().decode("utf-8"))
        assert snap["signal"]["status"] == "no-trade"
        assert snap["signal"]["action"] == "NO TRADE"
        assert snap["risk"]["entry"] is None


def test_adversarial_H_corrupted_missing_timestamp(p2_e2e_server):
    """Adversarial H: Missing/corrupted timestamp must be rejected at ingestion boundary."""
    base_url, cfg, _ = p2_e2e_server

    payload = {
        "contract_version": "1.0",
        "event_id": "pub_adv_H",
        "event_type": "TRADING_SIGNAL",
        "timestamp": "invalid-timestamp-str",
        "instrument": {"symbol": "XAUUSD", "interval": "1h"},
        "signal": {
            "publication_id": "pub_adv_H",
            "signal_id": "sig_adv_H",
            "decision": "buy",
        },
        "provenance": {"provenance_type": "live_signal"},
    }

    req = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {cfg.project1_service_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)

    assert exc_info.value.code in (400, 422)


def test_adversarial_I_missing_publication_identity(p2_e2e_server):
    """Adversarial I: Missing publication/event identity must fail closed (HTTP 400)."""
    base_url, cfg, _ = p2_e2e_server
    now_iso = datetime.now(timezone.utc).isoformat()

    payload = {
        "contract_version": "1.0",
        "event_type": "TRADING_SIGNAL",
        "timestamp": now_iso,
        "instrument": {"symbol": "XAUUSD", "interval": "1h"},
        "signal": {
            "signal_id": "sig_adv_I",
            "decision": "buy",
        },
        "provenance": {"provenance_type": "live_signal"},
    }

    req = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {cfg.project1_service_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)

    assert exc_info.value.code in (400, 422)


def test_adversarial_J_conflicting_identities_integrity_conflict(p2_e2e_server):
    """Adversarial J: Re-submitting same event_id with mutated trade setup levels must fail closed with INTEGRITY_CONFLICT."""
    base_url, cfg, _ = p2_e2e_server
    now_iso = datetime.now(timezone.utc).isoformat()

    payload1 = {
        "contract_version": "1.0",
        "event_id": "pub_adv_J_conflict",
        "event_type": "TRADING_SIGNAL",
        "timestamp": now_iso,
        "instrument": {"symbol": "XAUUSD", "interval": "1h"},
        "signal": {
            "publication_id": "pub_adv_J_conflict",
            "signal_id": "sig_adv_J_conflict",
            "decision": "buy",
            "strategy": "GoldStrategy",
        },
        "trade_setup": {"entry_price": 2650.0, "stop_loss": 2635.0},
        "provenance": {"provenance_type": "live_signal", "is_live": True},
    }

    headers = {"Authorization": f"Bearer {cfg.project1_service_key}", "Content-Type": "application/json"}

    # Ingest payload 1
    req1 = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(payload1).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req1) as resp1:
        ack1 = json.loads(resp1.read().decode("utf-8"))
        assert ack1["success"] is True
        assert ack1["status"] == "INGESTED"

    # Mutate entry_price with same event_id
    payload2 = dict(payload1)
    payload2["trade_setup"] = {"entry_price": 2720.0, "stop_loss": 2635.0}

    req2 = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(payload2).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req2)

    assert exc_info.value.code in (400, 409, 422)
    err_body = json.loads(exc_info.value.read().decode("utf-8"))
    assert err_body.get("error_code") == "INTEGRITY_CONFLICT" or err_body.get("success") is False
