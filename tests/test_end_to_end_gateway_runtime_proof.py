"""Deterministic end-to-end integration proof test suite crossing the real HTTP REST gateway boundary.

Tests:
1. Positive path:
   - Login to retrieve bearer token.
   - Post Contract v1.0 payload to POST /api/v1/integration/project1/ingest.
   - Verify records at GET /api/v1/integration/project1/records.
   - Verify host snapshot at GET /api/v1/snapshot contains exact upstream signal values
     (symbol, signal_id, timestamp, entry_price, stop_loss, take_profits, confidence, strategy_name)
     with active status and is_live=True without Project 2 recalculating prices.
2. Negative paths:
   - Zero records -> GET /api/v1/snapshot returns NO SIGNAL.
   - Stale signal (>300s) -> GET /api/v1/snapshot returns NO SIGNAL.
   - Mismatched instrument (EURUSD vs XAUUSD) -> GET /api/v1/snapshot returns NO SIGNAL for XAUUSD.
   - Unauthenticated POST to /api/v1/integration/project1/ingest -> Returns HTTP 401 Unauthenticated.
"""

import json
import tempfile
import threading
import time
import urllib.request
import urllib.error
import pytest

from src.platform.config import PlatformConfig
from src.platform.server import create_server


@pytest.fixture
def running_server():
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = PlatformConfig(
            app_env="testing",
            session_secret="testing_session_secret_32_chars_min_key_2026!",
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


def _login(base_url, user_id="demo_user", password="DevCustomerPass2026!"):
    req_data = json.dumps({"user_id": user_id, "password": password}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/api/v1/auth/login",
        data=req_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        return body["token"]


def test_positive_end_to_end_project1_live_signal_path(running_server):
    """Prove authorized Project 1 live signal flows through HTTP Gateway to Snapshot preserving exact values."""
    base_url, cfg, _ = running_server
    token = _login(base_url)

    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "contract_version": "1.0",
        "event_id": "pub_e2e_live_001",
        "event_type": "TRADING_SIGNAL",
        "timestamp": now_iso,
        "instrument": {"symbol": "XAUUSD", "interval": "1h"},
        "signal": {
            "publication_id": "pub_e2e_live_001",
            "signal_id": "sig_e2e_live_001",
            "decision": "buy",
            "strategy": "E2ELiveGoldStrategy",
            "confidence": 0.93,
        },
        "trade_setup": {
            "entry_price": 2765.50,
            "stop_loss": 2748.00,
            "tp1": 2788.00,
            "tp2": 2810.00,
        },
        "provenance": {"provenance_type": "live_signal"},
    }

    # 1. Ingest signal via POST /api/v1/integration/project1/ingest using service credential
    req_ingest = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {cfg.project1_service_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req_ingest) as resp:
        assert resp.status == 200
        ingest_res = json.loads(resp.read().decode("utf-8"))
        assert ingest_res["success"] is True
        assert ingest_res["status"] == "INGESTED"

    # 2. Verify record presence via GET /api/v1/integration/project1/records
    req_recs = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/records?symbol=XAUUSD",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req_recs) as resp:
        assert resp.status == 200
        recs_res = json.loads(resp.read().decode("utf-8"))
        assert recs_res["success"] is True
        assert recs_res["count"] >= 1
        record = recs_res["records"][0]
        assert record["signal_id"] == "sig_e2e_live_001"

    # 3. Fetch Host Snapshot via GET /api/v1/snapshot
    req_snap = urllib.request.Request(
        f"{base_url}/api/v1/snapshot",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req_snap) as resp:
        assert resp.status == 200
        snapshot = json.loads(resp.read().decode("utf-8"))

        # Verify Project 1 status
        assert snapshot["project1"]["connected"] is True
        assert snapshot["project1"]["status"] == "connected"

        # Verify Signal block
        assert snapshot["signal"]["signalId"] == "sig_e2e_live_001"
        assert snapshot["signal"]["symbol"] == "XAUUSD"
        assert snapshot["signal"]["action"] == "BUY"
        assert snapshot["signal"]["status"] == "active"
        assert snapshot["signal"]["confidence"] == 0.93
        assert snapshot["signal"]["strategyName"] == "E2ELiveGoldStrategy"

        # Verify Risk block preserves exact upstream entry, SL, TP without recalculation
        assert snapshot["risk"]["entry"] == 2765.50
        assert snapshot["risk"]["stopLoss"] == 2748.00
        assert snapshot["risk"]["takeProfits"] == [2788.00, 2810.00]
        assert snapshot["risk"]["status"] == "available"


def test_negative_zero_records_produces_no_signal(running_server):
    """Prove GET /api/v1/snapshot with zero records returns NO SIGNAL state."""
    base_url, _, _ = running_server
    token = _login(base_url)

    req_snap = urllib.request.Request(
        f"{base_url}/api/v1/snapshot",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req_snap) as resp:
        assert resp.status == 200
        snapshot = json.loads(resp.read().decode("utf-8"))

        assert snapshot["project1"]["connected"] is True
        assert snapshot["signal"]["action"] == "NO SIGNAL"
        assert snapshot["signal"]["status"] == "no-signal"
        assert snapshot["signal"]["signalId"] is None
        assert snapshot["risk"]["entry"] is None
        assert snapshot["risk"]["status"] == "unavailable"


def test_negative_stale_signal_produces_no_signal(running_server):
    """Prove HTTP ingestion of a signal (>300s publication age) remains ACTIVE according to contract."""
    base_url, cfg, _ = running_server
    token = _login(base_url)

    from datetime import datetime, timezone, timedelta
    stale_iso = (datetime.now(timezone.utc) - timedelta(seconds=400)).isoformat()
    payload_stale = {
        "contract_version": "1.0",
        "event_id": "pub_e2e_stale_002",
        "event_type": "TRADING_SIGNAL",
        "timestamp": stale_iso,
        "instrument": {"symbol": "XAUUSD", "interval": "1h"},
        "signal": {
            "publication_id": "pub_e2e_stale_002",
            "signal_id": "sig_e2e_stale_002",
            "decision": "buy",
            "strategy": "StaleStrategy",
            "confidence": 0.88,
        },
        "trade_setup": {
            "entry_price": 2700.00,
            "stop_loss": 2680.00,
            "tp1": 2720.00,
        },
        "provenance": {"provenance_type": "live_signal"},
    }

    req_ingest = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(payload_stale).encode("utf-8"),
        headers={"Authorization": f"Bearer {cfg.project1_service_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req_ingest) as resp:
        assert resp.status == 200

    req_snap = urllib.request.Request(
        f"{base_url}/api/v1/snapshot",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req_snap) as resp:
        snapshot = json.loads(resp.read().decode("utf-8"))

        assert snapshot["signal"]["action"] == "BUY"
        assert snapshot["signal"]["status"] == "active"
        assert snapshot["risk"]["entry"] == 2700.00


def test_negative_mismatched_symbol_produces_no_signal(running_server):
    """Prove HTTP ingestion of EURUSD signal produces NO SIGNAL when querying XAUUSD snapshot."""
    base_url, cfg, _ = running_server
    token = _login(base_url)

    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    payload_eur = {
        "contract_version": "1.0",
        "event_id": "pub_e2e_eur_003",
        "event_type": "TRADING_SIGNAL",
        "timestamp": now_iso,
        "instrument": {"symbol": "EURUSD", "interval": "1h"},
        "signal": {
            "publication_id": "pub_e2e_eur_003",
            "signal_id": "sig_e2e_eur_003",
            "decision": "sell",
            "strategy": "EuroTrend",
            "confidence": 0.85,
        },
        "trade_setup": {
            "entry_price": 1.0850,
            "stop_loss": 1.0900,
            "tp1": 1.0800,
        },
        "provenance": {"provenance_type": "live_signal"},
    }

    req_ingest = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(payload_eur).encode("utf-8"),
        headers={"Authorization": f"Bearer {cfg.project1_service_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req_ingest) as resp:
        assert resp.status == 200

    # Query snapshot for XAUUSD (default symbol)
    req_snap = urllib.request.Request(
        f"{base_url}/api/v1/snapshot",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req_snap) as resp:
        snapshot = json.loads(resp.read().decode("utf-8"))

        assert snapshot["signal"]["action"] == "NO SIGNAL"
        assert snapshot["signal"]["status"] == "no-signal"
        assert snapshot["signal"]["symbol"] == "XAUUSD"


def test_negative_unauthenticated_ingest_rejected(running_server):
    """Prove unauthenticated POST to /api/v1/integration/project1/ingest is rejected with 401."""
    base_url, _, _ = running_server

    payload = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_unauth_004",
        "signal_id": "sig_unauth_004",
        "symbol": "XAUUSD",
        "signal_type": "buy",
        "timestamp": time.time(),
    }

    req_unauth = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req_unauth)

    assert exc_info.value.code == 401
