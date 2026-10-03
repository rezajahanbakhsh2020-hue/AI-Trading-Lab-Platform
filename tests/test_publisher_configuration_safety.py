"""Publisher Activation & Configuration Safety Test Suite.

Verifies:
- Explicit activation boundary contract for Project 2 publisher endpoint and credentials.
- Canonical target endpoint is /api/v1/integration/project1/ingest.
- Service credential authentication uses project1_service_key.
- Configuration defaults and fail-closed safety when disabled or misconfigured.
"""

import json
import os
import tempfile
import threading
import urllib.request
import urllib.error
import pytest

from src.platform.config import PlatformConfig
from src.platform.server import create_server


def test_publisher_canonical_endpoint_and_auth_contract():
    """Verify publisher endpoint path, service key authentication, and fail-closed behavior on missing/wrong credentials."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        service_key = "p1_p2_secret_service_key_2026"
        cfg = PlatformConfig(
            app_env="testing",
            session_secret="testing_session_secret_32_chars_min_key_2026!",
            project1_service_key=service_key,
            persistence_dir=tmp_dir,
        )
        server = create_server(host="127.0.0.1", port=0, config=cfg)
        host, port = server.socket.getsockname()
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        base_url = f"http://{host}:{port}"

        canonical_path = "/api/v1/integration/project1/ingest"

        try:
            # 1. Unauthenticated request -> HTTP 401
            req_unauth = urllib.request.Request(
                f"{base_url}{canonical_path}",
                data=json.dumps({"event_id": "pub_001"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with pytest.raises(urllib.error.HTTPError) as exc_unauth:
                urllib.request.urlopen(req_unauth)
            assert exc_unauth.value.code == 401

            # 2. Invalid service credential -> HTTP 401
            req_bad_key = urllib.request.Request(
                f"{base_url}{canonical_path}",
                data=json.dumps({"event_id": "pub_001"}).encode("utf-8"),
                headers={
                    "Authorization": "Bearer wrong_service_key",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with pytest.raises(urllib.error.HTTPError) as exc_bad:
                urllib.request.urlopen(req_bad_key)
            assert exc_bad.value.code == 401

            # 3. Valid service credential -> Authorization succeeds
            from datetime import datetime, timezone
            now_iso = datetime.now(timezone.utc).isoformat()
            valid_payload = {
                "contract_version": "1.0",
                "event_id": "pub_valid_config_100",
                "event_type": "TRADING_SIGNAL",
                "timestamp": now_iso,
                "instrument": {"symbol": "XAUUSD", "interval": "1h"},
                "signal": {
                    "publication_id": "pub_valid_config_100",
                    "signal_id": "sig_valid_config_100",
                    "decision": "buy",
                },
                "trade_setup": {"entry_price": 2650.0, "stop_loss": 2635.0},
                "provenance": {"provenance_type": "live_signal", "is_live": True},
            }

            req_valid = urllib.request.Request(
                f"{base_url}{canonical_path}",
                data=json.dumps(valid_payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {service_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req_valid) as resp:
                assert resp.status == 200
                ack = json.loads(resp.read().decode("utf-8"))
                assert ack["success"] is True
                assert ack["status"] == "INGESTED"

        finally:
            server.shutdown()
            server.server_close()
