"""Integration and unit regression tests for platform production HTTP application server."""

import json
import os
import shutil
import threading
import time
import urllib.request
import urllib.error
import pytest

from src.platform.config import PlatformConfig
from src.platform.server import create_server


@pytest.fixture
def temp_persistence_dir(tmp_path):
    p_dir = str(tmp_path / "server_test_data")
    yield p_dir
    if os.path.exists(p_dir):
        shutil.rmtree(p_dir)


@pytest.fixture
def running_server(temp_persistence_dir):
    cfg = PlatformConfig(
        app_env="testing",
        allowed_origins=("http://localhost:8000", "http://127.0.0.1:8000", "http://testorigin.com"),
        session_secret="test_session_secret_key_32_chars_long_2026!",
        persistence_dir=temp_persistence_dir,
    )
    # Bind to random port by using port 0
    server = create_server(host="127.0.0.1", port=0, config=cfg)
    host, port = server.socket.getsockname()
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    base_url = f"http://{host}:{port}"
    yield base_url, cfg, server

    server.shutdown()
    server.server_close()


def test_server_liveness_endpoint(running_server):
    base_url, _, _ = running_server
    req = urllib.request.Request(f"{base_url}/health/liveness")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "alive"
        assert data["liveness"] is True
        assert "X-Frame-Options" in resp.headers
        assert resp.headers["X-Frame-Options"] == "DENY"


def test_server_readiness_endpoint(running_server):
    base_url, _, _ = running_server
    req = urllib.request.Request(f"{base_url}/health/readiness")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "ready"
        assert data["readiness"]["persistence_healthy"] is True


def test_server_diagnostics_endpoint(running_server):
    base_url, _, _ = running_server
    req = urllib.request.Request(f"{base_url}/api/v1/diagnostics")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["system_status"] == "HEALTHY"
        assert data["app_env"] == "testing"


def test_server_cors_headers(running_server):
    base_url, _, _ = running_server
    req = urllib.request.Request(
        f"{base_url}/health/liveness",
        headers={"Origin": "http://testorigin.com"},
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        assert resp.headers.get("Access-Control-Allow-Origin") == "http://testorigin.com"


def test_server_auth_login_and_validation_workflow(running_server):
    base_url, _, _ = running_server

    # 1. Invalid login
    login_data = json.dumps({"user_id": "demo_user", "password": "WrongPassword!"}).encode("utf-8")
    req_bad = urllib.request.Request(
        f"{base_url}/api/v1/auth/login",
        data=login_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req_bad)
    assert exc_info.value.code == 401

    # 2. Valid login
    valid_login_data = json.dumps({"user_id": "demo_user", "password": "DevCustomerPass2026!"}).encode("utf-8")
    req_good = urllib.request.Request(
        f"{base_url}/api/v1/auth/login",
        data=valid_login_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req_good) as resp:
        assert resp.status == 200
        res_payload = json.loads(resp.read().decode("utf-8"))
        assert res_payload["success"] is True
        token = res_payload["token"]
        assert token is not None

    # 3. Validate token
    req_val = urllib.request.Request(
        f"{base_url}/api/v1/auth/validate",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req_val) as resp_val:
        assert resp_val.status == 200
        val_payload = json.loads(resp_val.read().decode("utf-8"))
        assert val_payload["valid"] is True
        assert val_payload["user"]["user_id"] == "demo_user"


def test_server_snapshot_endpoint(running_server):
    base_url, _, _ = running_server
    req = urllib.request.Request(f"{base_url}/api/v1/snapshot")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        snapshot = json.loads(resp.read().decode("utf-8"))
        assert "authorization" in snapshot
        assert "platform" in snapshot
        assert "project1" in snapshot


def test_production_fail_closed_on_weak_secret():
    weak_cfg = PlatformConfig(
        app_env="production",
        session_secret="prod_strong_session_secret_32_chars_2026_key!",
        initial_admin_password="AdminPassword123!",
        public_base_url="https://trade.yourdomain.com",
    )
    object.__setattr__(weak_cfg, "session_secret", "dev_session_secret_key_change_in_production_2026")
    with pytest.raises(RuntimeError, match="CRITICAL PRODUCTION SECURITY FAILURE"):
        create_server(config=weak_cfg)
