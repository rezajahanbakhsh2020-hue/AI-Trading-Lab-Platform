"""Regression test suite for Project 1 -> Project 2 ingestion acknowledgement compatibility.

Verifies:
A - First ingestion returns HTTP 200 with success=True, status="INGESTED",
    and exact top-level identity event_id and publication_id matching request event_id.
B - Idempotent replay returns HTTP 200 with success=True, status="DUPLICATE_ACCEPTED",
    and exact top-level event_id and publication_id matching original request.
C - Identity mismatch protection ensures acknowledgement never produces synthetic IDs or
    mutated event_ids, and fails closed (HTTP 400) when event_id is missing.
D - P1 Project2Publisher compatible shape assertion verifying response schema against P1 requirements.
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
def p1_server():
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


def test_first_ingestion_acknowledgement_identity(p1_server):
    """Test A: First ingestion returns HTTP 200, INGESTED, and exact event_id & publication_id."""
    base_url, cfg, _ = p1_server
    token = _login(base_url)

    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    sent_event_id = "pub_test_001"

    payload = {
        "contract_version": "1.0",
        "event_id": sent_event_id,
        "event_type": "TRADING_SIGNAL",
        "timestamp": now_iso,
        "instrument": {"symbol": "XAUUSD", "interval": "1h"},
        "signal": {
            "publication_id": sent_event_id,
            "signal_id": "sig_test_001",
            "decision": "buy",
            "strategy": "GoldTrendStrategy",
            "confidence": 0.90,
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
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {cfg.project1_service_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req_ingest) as resp:
        assert resp.status == 200
        ack = json.loads(resp.read().decode("utf-8"))

        assert ack["success"] is True
        assert ack["status"] == "INGESTED"
        assert ack["event_id"] == sent_event_id
        assert ack["publication_id"] == sent_event_id
        assert ack["signal_id"] == "sig_test_001"
        assert "correlation_id" in ack
        assert "message" in ack
        assert "record" in ack
        assert ack["record"]["symbol"] == "XAUUSD"


def test_idempotent_replay_acknowledgement_identity(p1_server):
    """Test B: Idempotent replay returns HTTP 200, DUPLICATE_ACCEPTED, with exact same event_id."""
    base_url, cfg, _ = p1_server

    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    sent_event_id = "pub_replay_002"

    payload = {
        "contract_version": "1.0",
        "event_id": sent_event_id,
        "event_type": "TRADING_SIGNAL",
        "timestamp": now_iso,
        "instrument": {"symbol": "XAUUSD", "interval": "1h"},
        "signal": {
            "publication_id": sent_event_id,
            "signal_id": "sig_replay_002",
            "decision": "buy",
            "strategy": "ReplayStrategy",
            "confidence": 0.88,
        },
        "trade_setup": {
            "entry_price": 2710.00,
            "stop_loss": 2690.00,
            "tp1": 2730.00,
        },
        "provenance": {"provenance_type": "live_signal"},
    }

    headers = {"Authorization": f"Bearer {cfg.project1_service_key}", "Content-Type": "application/json"}

    # 1st Ingestion
    req1 = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req1) as resp1:
        ack1 = json.loads(resp1.read().decode("utf-8"))
        assert ack1["success"] is True
        assert ack1["status"] == "INGESTED"
        assert ack1["event_id"] == sent_event_id
        assert ack1["publication_id"] == sent_event_id

    # 2nd Ingestion (Replay)
    req2 = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req2) as resp2:
        assert resp2.status == 200
        ack2 = json.loads(resp2.read().decode("utf-8"))
        assert ack2["success"] is True
        assert ack2["status"] == "DUPLICATE_ACCEPTED"
        assert ack2["event_id"] == sent_event_id
        assert ack2["publication_id"] == sent_event_id
        assert ack2["signal_id"] == "sig_replay_002"


def test_identity_mismatch_and_fail_closed_protection(p1_server):
    """Test C: Fail-closed on missing event_id and protection against synthetic/mutated IDs."""
    base_url, cfg, _ = p1_server

    headers = {"Authorization": f"Bearer {cfg.project1_service_key}", "Content-Type": "application/json"}

    # Payload with missing event_id
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    payload_missing_event_id = {
        "contract_version": "1.0",
        "event_type": "TRADING_SIGNAL",
        "timestamp": now_iso,
        "instrument": {"symbol": "XAUUSD", "interval": "1h"},
        "signal": {
            "signal_id": "sig_no_event_003",
            "decision": "buy",
        },
        "trade_setup": {"entry_price": 2700.00, "stop_loss": 2680.00},
    }

    req_bad = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(payload_missing_event_id).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    # Must fail closed with HTTP 400 Bad Request
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req_bad)

    assert exc_info.value.code in (400, 422)
    err_body = json.loads(exc_info.value.read().decode("utf-8"))
    assert err_body.get("error") is True or err_body.get("success") is False

    # Also verify that a valid payload returns exact event_id without synthetic transformation or prefix/suffix mutation
    sent_event_id = "pub_exact_identity_999"
    payload_exact = {
        "contract_version": "1.0",
        "event_id": sent_event_id,
        "event_type": "TRADING_SIGNAL",
        "timestamp": now_iso,
        "instrument": {"symbol": "XAUUSD", "interval": "1h"},
        "signal": {
            "publication_id": sent_event_id,
            "signal_id": "sig_exact_999",
            "decision": "buy",
        },
        "trade_setup": {"entry_price": 2700.00, "stop_loss": 2680.00},
        "provenance": {"provenance_type": "live_signal"},
    }

    req_exact = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(payload_exact).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req_exact) as resp:
        ack = json.loads(resp.read().decode("utf-8"))
        assert ack["event_id"] == sent_event_id
        assert ack["event_id"] != f"fake_{sent_event_id}"
        assert ack["publication_id"] == sent_event_id


def test_p1_publisher_compatible_shape(p1_server):
    """Test D: Response shape meets Project1 Project2Publisher requirements."""
    base_url, cfg, _ = p1_server

    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    sent_event_id = "pub_p1_compat_777"

    payload = {
        "contract_version": "1.0",
        "event_id": sent_event_id,
        "event_type": "TRADING_SIGNAL",
        "timestamp": now_iso,
        "instrument": {"symbol": "XAUUSD", "interval": "1h"},
        "signal": {
            "publication_id": sent_event_id,
            "signal_id": "sig_p1_compat_777",
            "decision": "sell",
            "strategy": "P1CompatStrategy",
            "confidence": 0.95,
        },
        "trade_setup": {
            "entry_price": 2720.00,
            "stop_loss": 2735.00,
            "tp1": 2700.00,
        },
        "provenance": {"provenance_type": "live_signal"},
    }

    req = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {cfg.project1_service_key}", "Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        body = json.loads(resp.read().decode("utf-8"))

        # P1 Project2Publisher requirements:
        # 1. HTTP Status 2xx
        # 2. top-level success is True
        # 3. top-level status is in acceptable set (INGESTED / DUPLICATE_ACCEPTED)
        # 4. identity acknowledgement in top-level event_id or publication_id matching sent_event_id
        assert body["success"] is True
        assert body["status"] in ("INGESTED", "DUPLICATE_ACCEPTED")
        assert body["event_id"] == sent_event_id
        assert body["publication_id"] == sent_event_id
        assert body["signal_id"] == "sig_p1_compat_777"
        assert isinstance(body["correlation_id"], str)
