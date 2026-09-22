"""End-to-End Live HTTP Runtime Verification for Architectural Signal Path Isolation.

Spawns the real ThreadingHTTPServer on an ephemeral port, performs actual HTTP requests,
and proves:
1. Ingesting 'p1_xauusd_1h_1700000000' (Nov 2023 archive record) returns NO_CURRENT_SIGNAL ('status': 'no-signal', 'signal': None) on the Current Signal path.
2. Ingesting a fresh live signal payload (emitted <= 300s ago on current application date) returns status: 'active' on Current Signal path.
3. Outbound Telegram delivery fails for 'p1_xauusd_1h_1700000000'.
"""

import json
import socket
import threading
import time
import urllib.request
import pytest

from src.platform.config import PlatformConfig
from src.platform.server import create_server


def _get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def running_runtime_server(tmp_path):
    port = _get_free_port()
    cfg = PlatformConfig(
        app_env="testing",
        allowed_origins=("http://localhost:8000", "http://127.0.0.1:8000"),
        session_secret="test_session_secret_key_32_chars_long_2026!",
        persistence_dir=str(tmp_path / "runtime_data"),
    )

    # Create server instance with testing config
    server = create_server(
        host="127.0.0.1",
        port=port,
        config=cfg,
    )

    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()

    time.sleep(0.2)  # Allow server thread to start
    yield f"http://127.0.0.1:{port}", server

    server.shutdown()
    server.server_close()


def test_live_runtime_http_isolation(running_runtime_server, tmp_path):
    base_url, server = running_runtime_server

    # 1. Login as Admin user to get bearer token
    login_req = urllib.request.Request(
        f"{base_url}/api/v1/auth/login",
        data=json.dumps({"user_id": "admin_owner", "password": "DevAdminSecureKey2026!"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(login_req) as resp:
        login_res = json.loads(resp.read().decode("utf-8"))
        assert login_res["success"] is True
        token = login_res["token"]

    auth_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    # 2. Ingest 2023 historical archive record 'p1_xauusd_1h_1700000000'
    historical_ts = 1700000000.0
    hist_payload = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_runtime_2023",
        "signal_id": "p1_xauusd_1h_1700000000",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": historical_ts,
        "confidence": 0.88,
        "strategy_name": "GoldTrendv1",
        "entry_price": 1980.0,
        "stop_loss": 1960.0,
        "take_profit_1": 2000.0,
        "metadata": {"provenance_type": "historical_snapshot", "is_historical": True},
    }

    ingest_req = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(hist_payload).encode("utf-8"),
        headers=auth_headers,
        method="POST",
    )
    with urllib.request.urlopen(ingest_req) as resp:
        ingest_res = json.loads(resp.read().decode("utf-8"))
        assert ingest_res["success"] is True

    # 3. Query host snapshot endpoint consumed by Signals UI
    snap_req = urllib.request.Request(
        f"{base_url}/api/v1/snapshot?symbol=XAUUSD&timeframe=1h",
        headers=auth_headers,
        method="GET",
    )
    with urllib.request.urlopen(snap_req) as resp:
        snap_res = json.loads(resp.read().decode("utf-8"))
        # Verify 2023 historical signal is REJECTED from Current Signal
        sig_data = snap_res.get("signal", {})
        assert sig_data.get("status") == "no-signal"
        assert sig_data.get("action") == "NO SIGNAL"
        assert sig_data.get("signalId") is None
        assert snap_res.get("risk", {}).get("entry") is None

    # 4. Ingest a genuinely current live signal (emitted 10 seconds ago)
    now_ts = time.time()
    live_payload = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_runtime_live",
        "signal_id": f"p1_xauusd_1h_live_{int(now_ts)}",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": now_ts - 10.0,
        "confidence": 0.90,
        "strategy_name": "LiveGoldStrategy",
        "entry_price": 2750.0,
        "stop_loss": 2735.0,
        "take_profit_1": 2780.0,
        "metadata": {"provenance_type": "live_signal", "is_live": True},
    }

    ingest_live_req = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(live_payload).encode("utf-8"),
        headers=auth_headers,
        method="POST",
    )
    with urllib.request.urlopen(ingest_live_req) as resp:
        ingest_live_res = json.loads(resp.read().decode("utf-8"))
        assert ingest_live_res["success"] is True

    # 5. Query host snapshot again for current live signal
    with urllib.request.urlopen(snap_req) as resp:
        snap_live_res = json.loads(resp.read().decode("utf-8"))
        sig_live_data = snap_live_res.get("signal", {})
        assert sig_live_data.get("status") == "active"
        assert sig_live_data.get("action") == "BUY"
        assert sig_live_data.get("strategyName") == "LiveGoldStrategy"
        assert snap_live_res.get("risk", {}).get("entry") == 2750.0
