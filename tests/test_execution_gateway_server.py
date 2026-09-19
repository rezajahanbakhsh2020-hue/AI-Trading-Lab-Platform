"""Integration tests for Execution Gateway & Order Intent HTTP server endpoints."""

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
from src.platform.domain.signal import Signal
from src.platform.domain.readiness import Readiness
from src.platform.domain.stability import Stability
from src.platform.domain.trade_setup import TradeSetup
from src.platform.domain.trade_signal import TradeSignal
from src.platform.domain.autonomous_authorization import AutonomousAuthorization


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


def test_execution_boundary_and_monitoring_endpoint(running_server):
    base_url, _, _ = running_server
    token = _login(base_url)

    req = urllib.request.Request(
        f"{base_url}/api/v1/execution/boundary",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        body = json.loads(resp.read().decode("utf-8"))
        assert body["success"] is True
        assert "boundary" in body
        assert "monitoring" in body
        assert body["boundary"]["boundary_name"] == "Project 2 Execution Gateway Boundary"


def test_list_order_intents_and_lifecycle_update(running_server):
    base_url, _, server = running_server
    token = _login(base_url)

    # 1. Fetch user authorization object
    valid, user = server.RequestHandlerClass.server_user_auth_service.validate_session_token(token)
    assert valid is True

    # 2. Stage an OrderIntent directly via order_intent_service
    sig = Signal(action="buy", confidence=0.88, timestamp=time.time(), strategy_name="TestStrat")
    readiness = Readiness(approved=True, reason="Ready", timestamp=time.time())
    stability = Stability(score=0.88, risk_level="low")
    setup = TradeSetup(
        symbol="XAUUSD",
        entry_price=2000.0,
        stop_loss=1980.0,
        take_profit_1=2030.0,
        take_profit_2=2050.0,
        take_profit_3=2080.0,
        timestamp=time.time(),
        direction="buy",
    )
    trade_sig = TradeSignal(
        signal=sig,
        readiness=readiness,
        stability=stability,
        reason="Server HTTP integration test",
        tradable=True,
        trade_setup=setup,
    )
    auth = AutonomousAuthorization(
        status="AUTHORIZED",
        reason="Approved for server HTTP test",
        trade_signal=trade_sig,
        timestamp=time.time(),
    )

    ok_create, msg_c, created_intent = server.RequestHandlerClass.order_intent_service.create_order_intent(
        user=user,
        authorization=auth,
        idempotency_key="idemp_http_test_001",
        symbol="XAUUSD",
    )
    assert ok_create is True
    staged_id = created_intent.order_intent_id

    # 3. Query order intents via HTTP GET endpoint
    req_list = urllib.request.Request(
        f"{base_url}/api/v1/execution/intents",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req_list) as resp:
        list_body = json.loads(resp.read().decode("utf-8"))
        assert list_body["success"] is True
        assert any(i["order_intent_id"] == staged_id for i in list_body["order_intents"])

    # 4. Submit execution request via HTTP POST
    req_exec = urllib.request.Request(
        f"{base_url}/api/v1/execution/request",
        data=json.dumps({"order_intent_id": staged_id}).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req_exec) as resp:
        exec_body = json.loads(resp.read().decode("utf-8"))
        assert "attempt" in exec_body
        assert exec_body["attempt"]["externally_executed"] is False

    # 5. Fetch execution attempts for this intent
    req_att = urllib.request.Request(
        f"{base_url}/api/v1/execution/attempts?order_intent_id={staged_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req_att) as resp:
        att_body = json.loads(resp.read().decode("utf-8"))
        assert att_body["success"] is True
        assert len(att_body["attempts"]) >= 1

    # 6. Reconcile intent via HTTP POST
    req_rec = urllib.request.Request(
        f"{base_url}/api/v1/execution/reconcile",
        data=json.dumps({"order_intent_id": staged_id}).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req_rec) as resp:
        rec_body = json.loads(resp.read().decode("utf-8"))
        assert rec_body["success"] is True
        assert rec_body["reconciliation"]["order_intent_id"] == staged_id

    # 7. Transition order intent state to CANCELLED via HTTP POST
    req_up = urllib.request.Request(
        f"{base_url}/api/v1/execution/intent/update",
        data=json.dumps({
            "order_intent_id": staged_id,
            "lifecycle_state": "CANCELLED",
            "reason": "Cancelled via HTTP test",
        }).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req_up) as resp:
        up_body = json.loads(resp.read().decode("utf-8"))
        assert up_body["success"] is True
        assert up_body["order_intent"]["lifecycle_state"] == "CANCELLED"
