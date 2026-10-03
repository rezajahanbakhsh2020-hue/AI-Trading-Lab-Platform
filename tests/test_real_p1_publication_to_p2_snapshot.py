"""True Real-Producer Cross-Repository Integration Test Suite.

Executes real Project 1 ProductionIntelligencePublication artifact creation,
serializes it using real P1 to_contract_v1_payload(), transmits via HTTP POST
to Project 2 server, and verifies persistence, adapter, presenter, and snapshot presentation.

Also implements Anti-Recurrence Control K (provenance removal regression test).
"""

from datetime import datetime, timezone
import json
import sys
import tempfile
import threading
import urllib.request
import urllib.error
import pytest

sys.path.insert(0, "/tmp/AI-Trading-Lab")

from tests.test_production_publication_boundary import make_test_artifacts
from src.evaluation.live_production_decision import ProductionIntelligencePublication

from src.platform.config import PlatformConfig
from src.platform.server import create_server


@pytest.fixture
def p2_e2e_server():
    """Start a production-configured Project 2 server instance."""
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


def test_real_p1_publication_to_p2_snapshot_visible_signal(p2_e2e_server):
    """Prove end-to-end that an actual P1 ProductionIntelligencePublication flows through P2 to Snapshot."""
    base_url, cfg, server_inst = p2_e2e_server

    # 1. Create real P1 ProductionIntelligencePublication object using real P1 factory
    cand, dec, sig, risk, pub = make_test_artifacts()

    # 2. Serialize real payload via P1 to_contract_v1_payload()
    real_payload = pub.to_contract_v1_payload()

    # Extract authoritative P1 lineage and trade setup levels
    actual_event_id = pub.publication_id
    actual_publication_id = pub.publication_id
    actual_signal_id = pub.signal_id
    actual_decision_id = pub.decision_id
    actual_candidate_id = pub.candidate_id
    actual_symbol = pub.symbol.upper()
    actual_timeframe = pub.timeframe
    actual_entry = pub.entry
    actual_stop = pub.stop_loss
    actual_tp1 = pub.tp1
    actual_tp2 = pub.tp2
    actual_tp3 = pub.tp3

    # Assert P1 canonical provenance contract invariant
    assert real_payload["provenance"]["provenance_type"] == "live_signal"
    assert real_payload["provenance"]["is_live"] is True
    assert real_payload["provenance"]["source"] == "AI-Trading-Lab"

    # 3. HTTP POST real payload to P2 canonical endpoint
    headers = {
        "Authorization": f"Bearer {cfg.project1_service_key}",
        "Content-Type": "application/json",
    }
    req_ingest = urllib.request.Request(
        f"{base_url}/api/v1/integration/project1/ingest",
        data=json.dumps(real_payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    with urllib.request.urlopen(req_ingest) as resp:
        assert resp.status == 200
        ack = json.loads(resp.read().decode("utf-8"))
        assert ack["success"] is True
        assert ack["status"] == "INGESTED"
        assert ack["event_id"] == actual_event_id
        assert ack["publication_id"] == actual_publication_id
        assert ack["signal_id"] == actual_signal_id

    # 4. Verify P2 Repository Persistence
    handler_cls = server_inst.RequestHandlerClass
    gateway_svc = handler_cls.gateway_service
    repo = gateway_svc._repo
    records = repo.list_records_for_user(user_id=None, symbol=actual_symbol, limit=10, allow_system=True)
    assert len(records) > 0
    rec = next(r for r in records if r["signal_id"] == actual_signal_id)
    assert rec["publication_id"] == actual_publication_id

    # 5. Verify P2 Adapter
    presenter = handler_cls.presenter
    adapter = presenter._port
    pres_sig = adapter.fetch_latest_signal(symbol=actual_symbol, timeframe=actual_timeframe)
    assert pres_sig is not None
    assert pres_sig.signal_id == actual_signal_id
    assert pres_sig.symbol == actual_symbol
    assert pres_sig.signal_type.lower() == "buy"
    assert pres_sig.metadata.get("provenance_type") == "live_signal"
    assert pres_sig.metadata.get("publication_id") == actual_publication_id

    # 6. Verify P2 Presenter
    pres_res = presenter.present_signal(symbol=actual_symbol, timeframe=actual_timeframe)
    assert pres_res["status"] == "active"
    assert pres_res["signal"] is not None

    # 7. Verify P2 GET /api/v1/snapshot
    req_snap = urllib.request.Request(
        f"{base_url}/api/v1/snapshot?symbol={actual_symbol}&timeframe={actual_timeframe}",
        headers={"Content-Type": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req_snap) as snap_resp:
        assert snap_resp.status == 200
        snapshot = json.loads(snap_resp.read().decode("utf-8"))

        assert snapshot["project1"]["connected"] is True
        assert snapshot["signal"]["status"] == "active"
        assert snapshot["signal"]["action"] == "BUY"
        assert snapshot["signal"]["signalId"] == actual_signal_id
        assert snapshot["signal"]["metadata"]["publication_id"] == actual_publication_id

        # Verify trade setup levels match P1 values exactly without recalculation
        assert snapshot["risk"]["entry"] == actual_entry
        assert snapshot["risk"]["stopLoss"] == actual_stop
        assert snapshot["risk"]["takeProfits"] == [actual_tp1, actual_tp2, actual_tp3]


def test_anti_recurrence_K_mutated_provenance_type_fails_closed(p2_e2e_server):
    """Anti-Recurrence Control K: Removing provenance_type from real P1 payload MUST fail closed in P2."""
    base_url, cfg, _ = p2_e2e_server

    cand, dec, sig, risk, pub = make_test_artifacts()
    payload = pub.to_contract_v1_payload()

    # Deliberately remove provenance_type to simulate historical escape
    if "provenance_type" in payload["provenance"]:
        del payload["provenance"]["provenance_type"]

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

    with urllib.request.urlopen(req_ingest) as resp:
        ack = json.loads(resp.read().decode("utf-8"))
        assert ack["success"] is True

    # Query snapshot: MUST NOT show active BUY
    req_snap = urllib.request.Request(f"{base_url}/api/v1/snapshot?symbol={pub.symbol}&timeframe={pub.timeframe}")
    with urllib.request.urlopen(req_snap) as snap_resp:
        snap = json.loads(snap_resp.read().decode("utf-8"))
        assert snap["signal"]["status"] != "active"
        assert snap["signal"]["action"] == "NO SIGNAL" or snap["signal"]["signalId"] != pub.signal_id
