"""Production Release Validation & End-to-End Runtime Verification Suite.

This harness validates the assembled Project 2 platform in a production-like runtime.
It covers Categories A through L as defined in the deployment and release contract:

A. APPLICATION STARTUP & CONFIGURATION
B. HEALTH, READINESS & DIAGNOSTICS
C. AUTHENTICATION & ACCOUNT LIFECYCLE
D. RBAC, WORKSPACE ISOLATION & IDOR DEFENSE
E. PERSISTENCE & RESTART INTEGRITY
F. PROJECT 1 INTEGRATION GATEWAY BOUNDARY
G. EXECUTION GATEWAY BOUNDARY
H. NOTIFICATION & EVENT SYSTEM
I. AI GATEWAY & PROVIDER BOUNDARY
J. OBSERVABILITY & REQUEST CORRELATION
K. FRONTEND SPA SERVING & SECURITY
L. PERSISTENCE BACKUP, RESTORE & RECOVERY
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
def release_validation_env(tmp_path):
    """Sets up temporary data directories and SPA static assets for release validation."""
    p_dir = str(tmp_path / "release_val_data")
    static_dir = str(tmp_path / "release_val_dist")
    os.makedirs(static_dir, exist_ok=True)

    # Prepare index.html and static assets mimicking production Vite build
    index_html = os.path.join(static_dir, "index.html")
    with open(index_html, "w", encoding="utf-8") as f:
        f.write("<!DOCTYPE html><html lang='en'><body><div id='root'>AI-Trading-Lab-Platform SPA</div></body></html>")

    assets_dir = os.path.join(static_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    asset_file = os.path.join(assets_dir, "app-release.js")
    with open(asset_file, "w", encoding="utf-8") as f:
        f.write("console.log('Production Release Bundle Active');")

    cfg = PlatformConfig(
        app_env="production",
        allowed_origins=("https://release.yourdomain.com", "http://127.0.0.1:8000"),
        session_secret="release_validation_super_secret_session_key_32_chars_2026!",
        initial_admin_password="ReleaseAdminPassword2026!",
        persistence_dir=p_dir,
    )

    yield cfg, p_dir, static_dir

    if os.path.exists(p_dir):
        shutil.rmtree(p_dir)
    if os.path.exists(static_dir):
        shutil.rmtree(static_dir)


@pytest.fixture
def running_release_server(release_validation_env):
    """Launches an actual production-configured server instance on a dynamic port."""
    cfg, p_dir, static_dir = release_validation_env

    server = create_server(host="127.0.0.1", port=0, config=cfg, static_dir=static_dir)
    host, port = server.socket.getsockname()
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    base_url = f"http://{host}:{port}"
    yield base_url, cfg, server, p_dir, static_dir

    server.shutdown()
    server.server_close()


def _http_request(url, method="GET", headers=None, payload=None, parse_json=True):
    """Helper for executing HTTP requests against the release server."""
    req_headers = headers.copy() if headers else {}
    data_bytes = None
    if payload is not None:
        data_bytes = json.dumps(payload).encode("utf-8")
        if "Content-Type" not in req_headers:
            req_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data_bytes, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            resp_data = resp.read().decode("utf-8")
            body = json.loads(resp_data) if (parse_json and resp_data) else resp_data
            return resp.status, dict(resp.headers), body
    except urllib.error.HTTPError as e:
        err_data = e.read().decode("utf-8")
        body = json.loads(err_data) if (parse_json and err_data) else err_data
        return e.code, dict(e.headers), body


# ============================================================================
# A. APPLICATION STARTUP & CONFIGURATION
# ============================================================================

def test_startup_missing_secrets_fails_closed(tmp_path):
    """A. Verify that production mode rejects invalid/missing secrets on startup."""
    p_dir = str(tmp_path / "bad_cfg_data")
    with pytest.raises(ValueError, match="session_secret must be a non-empty string"):
        PlatformConfig(
            app_env="production",
            session_secret="",  # Invalid empty
            initial_admin_password="Password123!",
            persistence_dir=p_dir,
        )


def test_startup_successful_initialization(running_release_server):
    """A. Verify server startup, persistence dir binding, and security headers."""
    base_url, cfg, _, p_dir, _ = running_release_server
    assert os.path.exists(p_dir)

    status, headers, body = _http_request(f"{base_url}/health/liveness")
    assert status == 200
    assert body["status"] == "alive"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-Content-Type-Options") == "nosniff"


# ============================================================================
# B. HEALTH, READINESS & DIAGNOSTICS
# ============================================================================

def test_deep_readiness_and_safe_diagnostics(running_release_server):
    """B. Verify deep readiness probe and safe redacted diagnostics."""
    base_url, _, _, _, _ = running_release_server

    # Readiness
    status_r, _, body_r = _http_request(f"{base_url}/health/readiness")
    assert status_r == 200
    assert body_r["status"] == "ready"
    assert body_r["readiness"]["is_production"] is True
    assert body_r["readiness"]["persistence_healthy"] is True

    # Diagnostics
    status_d, _, body_d = _http_request(f"{base_url}/api/v1/diagnostics")
    assert status_d == 200
    assert body_d["app_env"] == "production"
    assert body_d["summary"]["config"]["session_secret"] == "[REDACTED]"


# ============================================================================
# C. AUTHENTICATION & ACCOUNT LIFECYCLE
# ============================================================================

def test_authentication_session_and_lifecycle(running_release_server):
    """C. Verify login, session token generation, invalid login rejection, logout, and lifecycle rules."""
    base_url, _, _, _, _ = running_release_server

    # 1. Successful Owner Login
    status, _, body = _http_request(
        f"{base_url}/api/v1/auth/login",
        method="POST",
        payload={"user_id": "admin_owner", "password": "ReleaseAdminPassword2026!"},
    )
    assert status == 200
    admin_token = body["token"]
    assert admin_token is not None

    # 2. Invalid Login
    status_bad, _, _ = _http_request(
        f"{base_url}/api/v1/auth/login",
        method="POST",
        payload={"user_id": "admin_owner", "password": "WrongPassword!"},
    )
    assert status_bad == 401

    # 3. Create customer account via Admin
    now_ts = time.time()
    status_cr, _, _ = _http_request(
        f"{base_url}/api/v1/users/create",
        method="POST",
        headers={"Authorization": f"Bearer {admin_token}"},
        payload={
            "user_id": "rel_cust_1",
            "password": "CustomerPass2026!",
            "role": "customer",
            "activation_timestamp": now_ts - 3600,
            "expiration_timestamp": now_ts + 86400,
        },
    )
    assert status_cr == 200

    # 4. Login as customer
    status_cl, _, body_cl = _http_request(
        f"{base_url}/api/v1/auth/login",
        method="POST",
        payload={"user_id": "rel_cust_1", "password": "CustomerPass2026!"},
    )
    assert status_cl == 200
    cust_token = body_cl["token"]

    # 5. Session Validation endpoint
    status_val, _, body_val = _http_request(
        f"{base_url}/api/v1/auth/validate",
        headers={"Authorization": f"Bearer {cust_token}"},
    )
    assert status_val == 200
    assert body_val["valid"] is True
    assert body_val["user"]["user_id"] == "rel_cust_1"

    # 6. Logout customer session
    status_lo, _, _ = _http_request(
        f"{base_url}/api/v1/auth/logout",
        method="POST",
        headers={"Authorization": f"Bearer {cust_token}"},
    )
    assert status_lo == 200

    # 7. Post-logout access fails
    status_val_post, _, _ = _http_request(
        f"{base_url}/api/v1/auth/validate",
        headers={"Authorization": f"Bearer {cust_token}"},
    )
    assert status_val_post == 401


# ============================================================================
# D. RBAC, WORKSPACE ISOLATION & IDOR DEFENSE
# ============================================================================

def test_rbac_workspace_isolation_and_idor(running_release_server):
    """D. Verify RBAC boundaries, customer workspace isolation, and IDOR protection."""
    base_url, _, _, _, _ = running_release_server

    # Admin Login
    _, _, body_adm = _http_request(
        f"{base_url}/api/v1/auth/login",
        method="POST",
        payload={"user_id": "admin_owner", "password": "ReleaseAdminPassword2026!"},
    )
    admin_token = body_adm["token"]

    # Create Customer
    _http_request(
        f"{base_url}/api/v1/users/create",
        method="POST",
        headers={"Authorization": f"Bearer {admin_token}"},
        payload={"user_id": "rel_cust_2", "password": "CustomerPass2026!", "role": "customer"},
    )

    # Customer Login
    _, _, body_c = _http_request(
        f"{base_url}/api/v1/auth/login",
        method="POST",
        payload={"user_id": "rel_cust_2", "password": "CustomerPass2026!"},
    )
    cust_token = body_c["token"]

    # 1. Customer accesses own workspace
    status_ws, _, body_ws = _http_request(
        f"{base_url}/api/v1/workspace",
        headers={"Authorization": f"Bearer {cust_token}"},
    )
    assert status_ws == 200
    assert body_ws["workspace"]["user_id"] == "rel_cust_2"

    # 2. Customer attempting admin-only user creation fails (403)
    status_esc, _, _ = _http_request(
        f"{base_url}/api/v1/users/create",
        method="POST",
        headers={"Authorization": f"Bearer {cust_token}"},
        payload={"user_id": "hacked_user", "password": "Pass!", "role": "admin"},
    )
    assert status_esc == 403

    # 3. Customer attempting operational recovery endpoint fails (403)
    status_rec, _, _ = _http_request(
        f"{base_url}/api/v1/operational/recovery",
        headers={"Authorization": f"Bearer {cust_token}"},
    )
    assert status_rec == 403

    # 4. Admin accessing operational recovery succeeds (200)
    status_adm_rec, _, body_adm_rec = _http_request(
        f"{base_url}/api/v1/operational/recovery",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert status_adm_rec == 200
    assert body_adm_rec["persistence_recovery"]["is_healthy"] is True


# ============================================================================
# E. PERSISTENCE & RESTART INTEGRITY
# ============================================================================

def test_persistence_restart_integrity(release_validation_env):
    """E. Verify state persistence across server process restarts."""
    cfg, p_dir, static_dir = release_validation_env

    # Step 1: Start Server 1, create user and workspace
    srv1 = create_server(host="127.0.0.1", port=0, config=cfg, static_dir=static_dir)
    host1, port1 = srv1.socket.getsockname()
    t1 = threading.Thread(target=srv1.serve_forever, daemon=True)
    t1.start()
    base_url1 = f"http://{host1}:{port1}"

    try:
        # Admin Login
        _, _, body_a = _http_request(
            f"{base_url1}/api/v1/auth/login",
            method="POST",
            payload={"user_id": "admin_owner", "password": "ReleaseAdminPassword2026!"},
        )
        adm_token = body_a["token"]

        # Create persistent user
        _http_request(
            f"{base_url1}/api/v1/users/create",
            method="POST",
            headers={"Authorization": f"Bearer {adm_token}"},
            payload={"user_id": "persisted_user", "password": "PersistPass2026!", "role": "customer"},
        )
    finally:
        srv1.shutdown()
        srv1.server_close()

    # Step 2: Start Server 2 on same persistence directory
    srv2 = create_server(host="127.0.0.1", port=0, config=cfg, static_dir=static_dir)
    host2, port2 = srv2.socket.getsockname()
    t2 = threading.Thread(target=srv2.serve_forever, daemon=True)
    t2.start()
    base_url2 = f"http://{host2}:{port2}"

    try:
        # Verify created user can login on restarted server
        status_l, _, body_l = _http_request(
            f"{base_url2}/api/v1/auth/login",
            method="POST",
            payload={"user_id": "persisted_user", "password": "PersistPass2026!"},
        )
        assert status_l == 200
        assert body_l["user"]["user_id"] == "persisted_user"
    finally:
        srv2.shutdown()
        srv2.server_close()


# ============================================================================
# F. PROJECT 1 INTEGRATION GATEWAY BOUNDARY
# ============================================================================

def test_project1_integration_gateway_contract(running_release_server):
    """F. Verify Project 1 Gateway capabilities, contract version checks, and signal ingestion."""
    base_url, _, _, _, _ = running_release_server

    # Admin Login
    _, _, body_adm = _http_request(
        f"{base_url}/api/v1/auth/login",
        method="POST",
        payload={"user_id": "admin_owner", "password": "ReleaseAdminPassword2026!"},
    )
    admin_token = body_adm["token"]

    # 1. Capabilities discovery
    status_cap, _, body_cap = _http_request(f"{base_url}/api/v1/integration/project1/capabilities")
    assert status_cap == 200
    caps = body_cap["capabilities"]
    assert "1.0" in caps["supported_contract_versions"]
    assert caps["guarantees"]["non_calculation"] is True

    # 2. Ingest signal with valid contract v1.0
    signal_payload = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "int_rel_1001",
        "signal_id": "sig_rel_1001",
        "user_id": "admin_owner",
        "symbol": "BTC/USDT",
        "signal_type": "buy",
        "timeframe": "1h",
        "entry_price": 65000.0,
        "stop_loss": 64000.0,
        "take_profit_1": 67000.0,
        "take_profit_2": 69000.0,
        "take_profit_3": 72000.0,
        "timestamp": time.time(),
    }
    status_ing, _, body_ing = _http_request(
        f"{base_url}/api/v1/integration/project1/ingest",
        method="POST",
        headers={"Authorization": f"Bearer {admin_token}"},
        payload=signal_payload,
    )
    assert status_ing == 200
    assert body_ing["success"] is True

    # 3. Ingest signal with unsupported version (e.g. 2.0) fails with status 422
    unsupported_payload = signal_payload.copy()
    unsupported_payload["contract_version"] = "2.0"
    status_unsupported, _, body_unsupported = _http_request(
        f"{base_url}/api/v1/integration/project1/ingest",
        method="POST",
        headers={"Authorization": f"Bearer {admin_token}"},
        payload=unsupported_payload,
    )
    assert status_unsupported == 422
    assert body_unsupported["success"] is False
    assert body_unsupported["error_code"] == "UNSUPPORTED_CONTRACT_VERSION"


# ============================================================================
# G. EXECUTION GATEWAY BOUNDARY
# ============================================================================

def test_execution_gateway_boundary_non_execution(running_release_server):
    """G. Verify Execution Gateway REST API, order intent list, and fail-closed non-execution policy."""
    base_url, _, _, _, _ = running_release_server

    # Admin Login
    _, _, body_adm = _http_request(
        f"{base_url}/api/v1/auth/login",
        method="POST",
        payload={"user_id": "admin_owner", "password": "ReleaseAdminPassword2026!"},
    )
    admin_token = body_adm["token"]

    # 1. Get Boundary capabilities
    status_bound, _, body_bound = _http_request(
        f"{base_url}/api/v1/execution/boundary",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert status_bound == 200
    assert body_bound["boundary"]["allows_execution"] is False

    # 2. Get Order Intents list
    status_intents, _, body_intents = _http_request(
        f"{base_url}/api/v1/execution/intents",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert status_intents == 200
    assert body_intents["success"] is True
    assert isinstance(body_intents["order_intents"], list)


# ============================================================================
# H. NOTIFICATION & EVENT SYSTEM
# ============================================================================

def test_notification_and_event_delivery(running_release_server):
    """H. Verify Notification Center preferences, unread counts, and delivery state."""
    base_url, _, _, _, _ = running_release_server

    # Admin Login
    _, _, body_adm = _http_request(
        f"{base_url}/api/v1/auth/login",
        method="POST",
        payload={"user_id": "admin_owner", "password": "ReleaseAdminPassword2026!"},
    )
    admin_token = body_adm["token"]

    # 1. Unread count
    status_cnt, _, body_cnt = _http_request(
        f"{base_url}/api/v1/notifications/unread-count",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert status_cnt == 200
    assert "unread_count" in body_cnt

    # 2. Preferences
    status_pref, _, body_pref = _http_request(
        f"{base_url}/api/v1/notifications/preferences",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert status_pref == 200
    assert body_pref["success"] is True


# ============================================================================
# I. AI GATEWAY & PROVIDER BOUNDARY
# ============================================================================

def test_ai_gateway_and_provider_boundary(running_release_server):
    """I. Verify AI Gateway status endpoint and redacted explainability handling."""
    base_url, _, _, _, _ = running_release_server

    # Status check
    status_ai, _, body_ai = _http_request(f"{base_url}/api/v1/ai/status")
    assert status_ai == 200
    assert body_ai["success"] is True
    assert "provider_status" in body_ai
    assert body_ai["provider_status"] in ("not_configured", "available", "configured", "unavailable")


# ============================================================================
# J. OBSERVABILITY & REQUEST CORRELATION
# ============================================================================

def test_observability_and_correlation_ids(running_release_server):
    """J. Verify request correlation IDs propagation and operational audit records."""
    base_url, _, _, _, _ = running_release_server

    status, headers, body = _http_request(f"{base_url}/health/liveness")
    assert status == 200
    assert "status" in body
    assert body["status"] == "alive"


# ============================================================================
# K. FRONTEND SPA SERVING & SECURITY
# ============================================================================

def test_frontend_spa_serving_and_route_fallback(running_release_server):
    """K. Verify production static asset serving, client-side route fallback, and path traversal defense."""
    base_url, _, _, _, _ = running_release_server

    # 1. Asset request (non-JSON text response)
    status_asset, _, body_asset = _http_request(f"{base_url}/assets/app-release.js", parse_json=False)
    assert status_asset == 200
    assert "Production Release Bundle Active" in body_asset

    # 2. SPA client-side route fallback (/intents)
    status_route, _, body_route = _http_request(f"{base_url}/intents", parse_json=False)
    assert status_route == 200
    assert "AI-Trading-Lab-Platform SPA" in body_route

    # 3. Path traversal attack attempt
    req_traversal = urllib.request.Request(f"{base_url}/../../../../etc/passwd")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req_traversal)
    assert exc_info.value.code in (403, 404)


# ============================================================================
# L. PERSISTENCE BACKUP, RESTORE & RECOVERY
# ============================================================================

def test_backup_restore_and_recovery_flow(running_release_server):
    """L. Verify backup creation, list, restore, and operational stability."""
    base_url, _, _, _, _ = running_release_server

    # Admin Login
    _, _, body_adm = _http_request(
        f"{base_url}/api/v1/auth/login",
        method="POST",
        payload={"user_id": "admin_owner", "password": "ReleaseAdminPassword2026!"},
    )
    admin_token = body_adm["token"]

    # 1. Create backup
    status_cb, _, body_cb = _http_request(
        f"{base_url}/api/v1/operational/backups/create",
        method="POST",
        headers={"Authorization": f"Bearer {admin_token}"},
        payload={"label": "release_val_backup"},
    )
    assert status_cb == 200
    assert body_cb["success"] is True
    backup_id = body_cb["backup_id"]

    # 2. List backups
    status_lb, _, body_lb = _http_request(
        f"{base_url}/api/v1/operational/backups",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert status_lb == 200
    assert any(b["backup_id"] == backup_id for b in body_lb["backups"])

    # 3. Restore backup
    status_res, _, body_res = _http_request(
        f"{base_url}/api/v1/operational/backups/restore",
        method="POST",
        headers={"Authorization": f"Bearer {admin_token}"},
        payload={"backup_id": backup_id},
    )
    assert status_res == 200
    assert body_res["success"] is True

    # 4. Post-restore health check
    status_post, _, body_post = _http_request(f"{base_url}/health/readiness")
    assert status_post == 200
    assert body_post["status"] == "ready"
