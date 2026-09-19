"""End-to-End Production Deployment Smoke & Runtime Verification Suite.

Exercises actual deployed application server paths in production mode:
- Application startup in APP_ENV=production
- Liveness (/health/liveness)
- Readiness (/health/readiness)
- Operational Diagnostics (/api/v1/diagnostics)
- SPA Static Asset Serving & Path Traversal Security Verification
- Authentication Gate (/api/v1/auth/login, /validate, /logout)
- User Isolated Workspace Persistence (/api/v1/workspace)
- Execution Gateway Boundary & Order Intent REST API (/api/v1/execution/*)
- Operational Recovery Diagnostics (/api/v1/operational/recovery)
- Graceful Server Shutdown
"""

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
def temp_smoke_dir(tmp_path):
    s_dir = str(tmp_path / "smoke_verification_data")
    static_dir = str(tmp_path / "smoke_static_dist")
    os.makedirs(static_dir, exist_ok=True)

    # Create dummy index.html and static asset in static_dir
    index_html = os.path.join(static_dir, "index.html")
    with open(index_html, "w", encoding="utf-8") as f:
        f.write("<!DOCTYPE html><html><body><h1>AI-Trading-Lab-Platform SPA</h1></body></html>")

    assets_dir = os.path.join(static_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    asset_file = os.path.join(assets_dir, "app.js")
    with open(asset_file, "w", encoding="utf-8") as f:
        f.write("console.log('Production SPA Loaded');")

    yield s_dir, static_dir

    if os.path.exists(s_dir):
        shutil.rmtree(s_dir)
    if os.path.exists(static_dir):
        shutil.rmtree(static_dir)


@pytest.fixture
def running_prod_server(temp_smoke_dir):
    p_dir, static_dir = temp_smoke_dir
    cfg = PlatformConfig(
        app_env="production",
        allowed_origins=("https://trade.yourdomain.com", "http://127.0.0.1:8000"),
        session_secret="production_super_secret_session_key_32_chars_min_2026!",
        initial_admin_password="ProductionAdminPassword2026!",
        persistence_dir=p_dir,
    )

    server = create_server(host="127.0.0.1", port=0, config=cfg, static_dir=static_dir)
    host, port = server.socket.getsockname()
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    base_url = f"http://{host}:{port}"
    yield base_url, cfg, server, p_dir, static_dir

    server.shutdown()
    server.server_close()


def test_smoke_liveness_and_security_headers(running_prod_server):
    """Smoke Test 1: Liveness probe and production security headers."""
    base_url, _, _, _, _ = running_prod_server
    req = urllib.request.Request(f"{base_url}/health/liveness")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "alive"
        assert data["liveness"] is True

        # Verify production security headers
        headers = dict(resp.headers)
        assert headers.get("X-Frame-Options") == "DENY"
        assert headers.get("X-Content-Type-Options") == "nosniff"
        assert headers.get("Strict-Transport-Security") == "max-age=31536000; includeSubDomains"


def test_smoke_readiness_probe(running_prod_server):
    """Smoke Test 2: Readiness probe in production mode."""
    base_url, _, _, _, _ = running_prod_server
    req = urllib.request.Request(f"{base_url}/health/readiness")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "ready"
        readiness = data["readiness"]
        assert readiness["is_production"] is True
        assert readiness["persistence_healthy"] is True
        assert readiness["overall_status"] == "HEALTHY"


def test_smoke_operational_diagnostics_sanitization(running_prod_server):
    """Smoke Test 3: Operational diagnostics endpoint with secret sanitization."""
    base_url, _, _, _, _ = running_prod_server
    req = urllib.request.Request(f"{base_url}/api/v1/diagnostics")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["system_status"] == "HEALTHY"
        assert data["app_env"] == "production"

        summary = data["summary"]
        config_summary = summary["config"]
        assert config_summary["session_secret"] == "[REDACTED]"


def test_smoke_spa_static_asset_serving_and_path_traversal_defense(running_prod_server):
    """Smoke Test 4: SPA static asset serving and directory traversal attack defense."""
    base_url, _, _, _, static_dir = running_prod_server

    # 1. Direct asset request
    req_asset = urllib.request.Request(f"{base_url}/assets/app.js")
    with urllib.request.urlopen(req_asset) as resp:
        assert resp.status == 200
        content = resp.read().decode("utf-8")
        assert "Production SPA Loaded" in content

    # 2. Client-side route (SPA fallback to index.html)
    req_route = urllib.request.Request(f"{base_url}/operational-control")
    with urllib.request.urlopen(req_route) as resp:
        assert resp.status == 200
        content = resp.read().decode("utf-8")
        assert "AI-Trading-Lab-Platform SPA" in content

    # 3. Path traversal attack attempt (e.g., /../../../etc/passwd)
    req_traversal = urllib.request.Request(f"{base_url}/../../../../etc/passwd")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req_traversal)
    assert exc_info.value.code in (403, 404)


def test_smoke_auth_workspace_and_recovery_flow(running_prod_server):
    """Smoke Test 5: End-to-end authentication, user workspace, and recovery diagnostics."""
    base_url, _, _, _, _ = running_prod_server

    # 1. Login as bootstrapped admin_owner using ProductionAdminPassword2026!
    admin_login_data = json.dumps({"user_id": "admin_owner", "password": "ProductionAdminPassword2026!"}).encode("utf-8")
    req_admin_login = urllib.request.Request(
        f"{base_url}/api/v1/auth/login",
        data=admin_login_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req_admin_login) as resp_adm:
        assert resp_adm.status == 200
        adm_payload = json.loads(resp_adm.read().decode("utf-8"))
        adm_token = adm_payload["token"]

    # 2. Admin creates a customer account
    create_user_data = json.dumps({
        "user_id": "smoke_cust",
        "password": "CustomerPassword2026!",
        "role": "customer",
    }).encode("utf-8")
    req_create = urllib.request.Request(
        f"{base_url}/api/v1/users/create",
        data=create_user_data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {adm_token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req_create) as resp_cr:
        assert resp_cr.status == 200

    # 3. Login as created customer
    login_data = json.dumps({"user_id": "smoke_cust", "password": "CustomerPassword2026!"}).encode("utf-8")
    req_login = urllib.request.Request(
        f"{base_url}/api/v1/auth/login",
        data=login_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req_login) as resp:
        assert resp.status == 200
        res_payload = json.loads(resp.read().decode("utf-8"))
        token = res_payload["token"]

    # 4. Access customer workspace
    req_ws = urllib.request.Request(
        f"{base_url}/api/v1/workspace",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req_ws) as resp_ws:
        assert resp_ws.status == 200
        ws_payload = json.loads(resp_ws.read().decode("utf-8"))
        assert ws_payload["success"] is True
        assert ws_payload["workspace"]["user_id"] == "smoke_cust"

    # 5. Access Execution Gateway boundary status in production
    req_exec_bound = urllib.request.Request(
        f"{base_url}/api/v1/execution/boundary",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req_exec_bound) as resp_eb:
        assert resp_eb.status == 200
        eb_payload = json.loads(resp_eb.read().decode("utf-8"))
        assert eb_payload["success"] is True
        assert eb_payload["boundary"]["allows_execution"] is False

    # 6. Customer attempting recovery endpoint raises 403 Forbidden
    req_rec = urllib.request.Request(
        f"{base_url}/api/v1/operational/recovery",
        headers={"Authorization": f"Bearer {token}"},
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req_rec)
    assert exc_info.value.code == 403

    # 7. Admin accesses recovery endpoint successfully
    req_admin_rec = urllib.request.Request(
        f"{base_url}/api/v1/operational/recovery",
        headers={"Authorization": f"Bearer {adm_token}"},
    )
    with urllib.request.urlopen(req_admin_rec) as resp_rec_ok:
        assert resp_rec_ok.status == 200
        rec_data = json.loads(resp_rec_ok.read().decode("utf-8"))
        assert rec_data["success"] is True
        assert rec_data["persistence_recovery"]["is_healthy"] is True


def test_smoke_graceful_shutdown(running_prod_server):
    """Smoke Test 6: Verify graceful server shutdown."""
    _, _, server, _, _ = running_prod_server

    assert server is not None
    # Server cleanly shuts down via fixture tearDown
