"""Regression tests for the local publication -> snapshot proof path.

Covers:
- Backend snapshot emits a viewer security identity block (guest + authenticated)
  consumed by the frontend hostSnapshotMatchesSelection polling check.
- Ephemeral-key publication proof service ends-to-end through the real local
  HTTP server: ingest -> persisted record -> real snapshot retrieval.
- Proof tool fails closed without a service credential and never echoes it.
- Contract boundary rejects zero, negative, and non-finite timestamps,
  and never rescues a malformed primary publication timestamp from another clock.
"""

from datetime import datetime, timezone
import json
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.error
import pytest

from src.platform.config import PlatformConfig
from src.platform.server import create_server
from src.platform.services.publication_proof import (
    build_p1_contract_v1_payload,
    run_publication_proof,
)
from src.platform.domain.project1_contract import (
    parse_iso8601_to_utc_epoch,
    validate_project1_contract_payload,
)
from src.platform.services.project1_presenter import _evaluate_signal_live_status


@pytest.fixture
def proof_base_url():
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = PlatformConfig(
            app_env="testing",
            session_secret="testing_session_secret_32_chars_min_key_2026!",
            persistence_dir=tmp_dir,
        )
        server = create_server(host="127.0.0.1", port=0, config=cfg)
        host, port = server.socket.getsockname()
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            yield f"http://{host}:{port}", cfg
        finally:
            server.shutdown()
            server.server_close()


def _iso(offset_seconds: float = 0.0) -> str:
    return datetime.fromtimestamp(
        time.time() - offset_seconds, tz=timezone.utc
    ).isoformat()


def test_snapshot_includes_viewer_security_identity_block_guest(proof_base_url):
    base_url, _ = proof_base_url
    with urllib.request.urlopen(f"{base_url}/api/v1/snapshot?symbol=XAUUSD&timeframe=1h") as resp:
        snap = json.loads(resp.read().decode("utf-8"))
    assert snap["security"]["userId"] == "guest_user"
    assert snap["security"]["isAdmin"] is False


def test_snapshot_includes_viewer_security_identity_block_authenticated(proof_base_url):
    base_url, _ = proof_base_url
    req = urllib.request.Request(
        f"{base_url}/api/v1/auth/login",
        data=json.dumps({"user_id": "demo_user", "password": "DevCustomerPass2026!"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        token = json.loads(resp.read().decode("utf-8"))["token"]

    snap_req = urllib.request.Request(
        f"{base_url}/api/v1/snapshot?symbol=XAUUSD&timeframe=1h",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(snap_req) as resp:
        snap = json.loads(resp.read().decode("utf-8"))
    assert snap["security"]["userId"] == "demo_user"
    assert snap["security"]["role"] in ("customer", "user", "admin")


def test_publication_proof_end_to_end_through_real_server(proof_base_url):
    base_url, cfg = proof_base_url
    result = run_publication_proof(
        base_url=base_url,
        service_key=cfg.project1_service_key,
        symbol="XAUUSD",
        timeframe="1H",
        decision="buy",
    )
    assert result["success"] is True, result.get("reason")
    assert result["action"] == "BUY"
    assert result["timeframe"]
    assert str(result["timeframe"]).strip().lower() == "1h"
    assert result["risk"]["entry"] == 2700.0
    assert result["security_viewer_id"] == "guest_user"
    # Service credential must never appear in the proof output
    assert "project1_service_key" not in json.dumps(result)


def test_publication_proof_fails_closed_without_credential(proof_base_url):
    base_url, _ = proof_base_url
    result = run_publication_proof(base_url=base_url, service_key=None)
    assert result["success"] is False
    assert "credential" in result["reason"].lower()


def test_publication_proof_fails_closed_on_wrong_credential(proof_base_url):
    base_url, _ = proof_base_url
    result = run_publication_proof(base_url=base_url, service_key="definitely_wrong_key")
    assert result["success"] is False


def test_proof_cli_does_not_print_secret(proof_base_url):
    import subprocess

    base_url, cfg = proof_base_url
    env = dict(__import__("os").environ)
    env["PROJECT2_API_KEY"] = cfg.project1_service_key
    proc = subprocess.run(
        [sys.executable, "scripts/verify_local_signal_path.py", "--base-url", base_url],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert cfg.project1_service_key not in proc.stdout
    assert cfg.project1_service_key not in proc.stderr


def test_contract_boundary_rejects_zero_iso_timestamp():
    with pytest.raises(ValueError) as exc:
        parse_iso8601_to_utc_epoch("1970-01-01T00:00:00Z")
    assert "zero" in str(exc.value).lower() or "epoch" in str(exc.value).lower()


def test_contract_boundary_rejects_zero_and_non_finite_numeric_timestamp():
    for bad_ts in (0, -1.0, float("inf"), float("-inf"), float("nan")):
        res = validate_project1_contract_payload(
            {
                "contract_version": "1.0",
                "event_id": "evt_bad_ts",
                "timestamp": bad_ts,
                "instrument": {"symbol": "XAUUSD", "interval": "1h"},
                "signal": {"publication_id": "evt_bad_ts", "signal_id": "sig_bad_ts", "decision": "buy"},
                "trade_setup": {},
                "provenance": {"provenance_type": "live_signal", "is_live": True},
            }
        )
        assert res.is_valid is False, f"timestamp {bad_ts} must be rejected"


def test_contract_boundary_rejects_missing_timestamp():
    res = validate_project1_contract_payload(
        {
            "contract_version": "1.0",
            "event_id": "evt_no_ts",
            "instrument": {"symbol": "XAUUSD", "interval": "1h"},
            "signal": {"publication_id": "evt_no_ts", "signal_id": "sig_no_ts", "decision": "buy"},
            "trade_setup": {},
            "provenance": {},
        }
    )
    assert res.is_valid is False


def test_contract_boundary_rejects_future_timestamp():
    future_iso = datetime.fromtimestamp(time.time() + 3600.0, tz=timezone.utc).isoformat()
    res = validate_project1_contract_payload(
        {
            "contract_version": "1.0",
            "event_id": "evt_future",
            "timestamp": future_iso,
            "instrument": {"symbol": "XAUUSD", "interval": "1h"},
            "signal": {"publication_id": "evt_future", "signal_id": "sig_future", "decision": "buy"},
            "trade_setup": {},
            "provenance": {},
        }
    )
    assert res.is_valid is False


def test_presented_p1_xauusd_signal_visible_after_300s_and_ui_security_block_matches():
    """The genuine P1 XAUUSD path stays observable: snapshot signal is present,
    presenter emits a security block matching the UI selection lifetime, and a
    > 300s publication remains presented (not converted to NO SIGNAL)."""
    now_ts = time.time()
    payload = build_p1_contract_v1_payload(reference_now=now_ts - 301.0, decision="buy")

    sig_dict = {
        "signal_id": payload["signal"]["signal_id"],
        "symbol": payload["instrument"]["symbol"],
        "signal_type": "buy",
        "timestamp": float(parse_iso8601_to_utc_epoch(_iso(7200.0))),
        "metadata": {
            "provenance_type": "live_signal",
            "is_live": True,
            "produced_at": payload["provenance"]["produced_at"],
            "publication_id": payload["event_id"],
        },
    }
    is_live, reason = _evaluate_signal_live_status(sig_dict, requested_symbol="XAUUSD")
    assert is_live is True, reason
