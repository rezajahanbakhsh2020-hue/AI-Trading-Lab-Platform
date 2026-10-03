"""Multi-Dimensional Integration & Boundary Verification Suite for P1 Ingestion Identity & Persistence.

Tests Positive, Negative, Adversarial/Conflict, Concurrency/Replay,
Crash/Failure Recovery, and Tenant/Scope Isolation invariants.
"""

import concurrent.futures
import os
import shutil
import tempfile
import threading
import time
from typing import Any, Dict

import pytest

from src.platform.adapters.project1_repository import FileBackedProject1IntegrationRepository
from src.platform.domain.user_authorization import UserAuthorization, UserRole
from src.platform.services.audit_control import PlatformAuditControlService
from src.platform.services.project1_gateway import Project1IntegrationGatewayService
from src.platform.services.security import SecurityBoundaryService


def _build_valid_payload(pub_id: str, event_id: str = "evt_1001", signal_id: str = "sig_1001") -> Dict[str, Any]:
    return {
        "event_id": event_id,
        "publication_id": pub_id,
        "signal_id": signal_id,
        "decision_id": f"dec_{pub_id}",
        "canonical_live_decision_fingerprint": f"canon_fp_{pub_id}",
        "candidate_id": f"cand_{pub_id}",
        "research_evidence_id": f"evid_{pub_id}",
        "strategy_name": "alpha_v1",
        "research_fingerprint": f"rf_{pub_id}",
        "runtime_authorization_fingerprint": f"rta_{pub_id}",
        "strategy_version": "1.0.0",
        "symbol": "XAUUSD",
        "signal_type": "buy",
        "timeframe": "M15",
        "entry_price": 2650.0,
        "stop_loss": 2640.0,
        "take_profit_1": 2670.0,
        "take_profit_2": 2680.0,
        "take_profit_3": 2690.0,
        "confidence": 0.85,
        "operational_stability_score": 0.95,
        "trailing_stop": {"distance": 5.0, "is_active": True},
        "invalidation_condition": "Close below 2635.00",
        "contract_version": "1.0",
        "provenance_type": "live_signal",
        "timestamp": time.time(),
    }


@pytest.fixture
def temp_repo_file():
    tmp_dir = tempfile.mkdtemp()
    filepath = os.path.join(tmp_dir, "test_p1_records.json")
    yield filepath
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture
def setup_gateway(temp_repo_file):
    sec = SecurityBoundaryService()
    audit = PlatformAuditControlService(security_boundary=sec)
    repo = FileBackedProject1IntegrationRepository(storage_filepath=temp_repo_file, audit_control=audit)
    gw = Project1IntegrationGatewayService(repository=repo, security_boundary=sec, audit_control=audit)
    user_a = UserAuthorization(
        user_id="usr_tenant_a",
        auth_code="code_a",
        telegram_chat_id="111",
        delivery_enabled=True,
        allowed_symbols=["XAUUSD", "EURUSD"],
        role=UserRole.USER,
    )
    user_b = UserAuthorization(
        user_id="usr_tenant_b",
        auth_code="code_b",
        telegram_chat_id="222",
        delivery_enabled=True,
        allowed_symbols=["XAUUSD", "EURUSD"],
        role=UserRole.USER,
    )
    return gw, repo, user_a, user_b


# ============================================================================
# 1. POSITIVE TESTS
# ============================================================================

def test_positive_single_ingest_and_authoritative_resolution(setup_gateway):
    gw, repo, user_a, _ = setup_gateway
    payload = _build_valid_payload("pub_pos_1")

    res = gw.ingest_signal_payload(user_a, payload)
    assert res["success"] is True
    assert res["status"] == "INGESTED"
    assert res["record"]["publication_id"] == "pub_pos_1"

    resolved = gw.resolve_authoritative_publication(user_a, "pub_pos_1")
    assert resolved is not None
    assert resolved["publication_id"] == "pub_pos_1"
    assert resolved["symbol"] == "XAUUSD"


# ============================================================================
# 2. NEGATIVE TESTS
# ============================================================================

def test_negative_invalid_contract_and_unauthorized(setup_gateway):
    gw, repo, user_a, _ = setup_gateway

    # Unauthenticated
    res_unauth = gw.ingest_signal_payload(None, _build_valid_payload("pub_neg_1"))
    assert res_unauth["success"] is False
    assert res_unauth["error_code"] == "UNAUTHENTICATED"

    # Malformed contract payload
    invalid_payload = {"publication_id": "pub_neg_2"}
    res_invalid = gw.ingest_signal_payload(user_a, invalid_payload)
    assert res_invalid["success"] is False
    assert res_invalid["error_code"] in ("INVALID_CONTRACT_SCHEMA", "UNSUPPORTED_CONTRACT_VERSION")


# ============================================================================
# 3. ADVERSARIAL & INTEGRITY CONFLICT TESTS
# ============================================================================

def test_adversarial_idempotent_replay_vs_mutated_conflict(setup_gateway):
    gw, repo, user_a, _ = setup_gateway
    payload = _build_valid_payload("pub_adv_1")

    # Ingest 1
    res1 = gw.ingest_signal_payload(user_a, payload)
    assert res1["success"] is True
    assert res1["status"] == "INGESTED"

    # Exact replay -> DUPLICATE_ACCEPTED
    res_replay = gw.ingest_signal_payload(user_a, payload)
    assert res_replay["success"] is True
    assert res_replay["status"] == "DUPLICATE_ACCEPTED"

    # Mutated payload (changed entry_price) -> INTEGRITY_CONFLICT
    mutated_payload = _build_valid_payload("pub_adv_1")
    mutated_payload["entry_price"] = 9999.0
    res_conflict = gw.ingest_signal_payload(user_a, mutated_payload)
    assert res_conflict["success"] is False
    assert res_conflict["error_code"] == "INTEGRITY_CONFLICT"


def test_adversarial_same_event_different_publication_conflict(setup_gateway):
    gw, repo, user_a, _ = setup_gateway
    p1 = _build_valid_payload("pub_adv_evt_1", event_id="same_evt_100")
    p2 = _build_valid_payload("pub_adv_evt_2", event_id="same_evt_100")

    gw.ingest_signal_payload(user_a, p1)

    # Attempting to map same event_id to a different publication_id -> INTEGRITY_CONFLICT
    res2 = gw.ingest_signal_payload(user_a, p2)
    assert res2["success"] is False
    assert res2["error_code"] == "INTEGRITY_CONFLICT"


# ============================================================================
# 4. CONCURRENCY & REPLAY MATRIX TESTS
# ============================================================================

def test_concurrency_identical_payloads_single_creation(setup_gateway):
    gw, repo, user_a, _ = setup_gateway
    payload = _build_valid_payload("pub_conc_1")
    num_threads = 16
    barrier = threading.Barrier(num_threads)
    results = []

    def worker():
        barrier.wait()
        res = gw.ingest_signal_payload(user_a, payload)
        results.append(res)

    threads = [threading.Thread(target=worker) for _ in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == num_threads
    created_count = sum(1 for r in results if r.get("status") == "INGESTED")
    duplicate_count = sum(1 for r in results if r.get("status") == "DUPLICATE_ACCEPTED")

    assert created_count == 1
    assert duplicate_count == num_threads - 1

    records = repo.list_records_for_user(user_id=user_a.user_id)
    pub_records = [r for r in records if r.get("publication_id") == "pub_conc_1"]
    assert len(pub_records) == 1


def test_concurrency_conflicting_payloads_fail_closed(setup_gateway):
    gw, repo, user_a, _ = setup_gateway
    num_threads = 8
    barrier = threading.Barrier(num_threads)
    results = []

    def worker(idx):
        p = _build_valid_payload("pub_conc_conflict")
        p["entry_price"] = 2600.0 + idx  # Different entry_price for each thread
        barrier.wait()
        res = gw.ingest_signal_payload(user_a, p)
        results.append(res)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == num_threads
    created_count = sum(1 for r in results if r.get("status") == "INGESTED")
    conflict_count = sum(1 for r in results if r.get("error_code") == "INTEGRITY_CONFLICT")

    assert created_count == 1
    assert conflict_count == num_threads - 1


# ============================================================================
# 5. CRASH SAFETY & PERSISTENCE FAILURE RECOVERY
# ============================================================================

def test_crash_safety_rollback_on_write_failure(setup_gateway):
    gw, repo, user_a, _ = setup_gateway
    payload = _build_valid_payload("pub_crash_1")
    payload["integration_id"] = "int_pub_crash_1"

    def mock_flush_fail():
        raise RuntimeError("Disk full / Write failure simulated")

    repo._flush_to_storage_unlocked = mock_flush_fail

    with pytest.raises(RuntimeError, match="Disk full / Write failure simulated"):
        repo.ingest_authoritative_record(payload, user_id=user_a.user_id)

    recs = repo.list_records_for_user(user_id=user_a.user_id)
    assert len(recs) == 0


# ============================================================================
# 6. TENANT & SCOPE ISOLATION TESTS
# ============================================================================

def test_tenant_isolation_no_cross_tenant_collision(setup_gateway):
    gw, repo, user_a, user_b = setup_gateway
    payload_a = _build_valid_payload("pub_tenant_cross")
    payload_b = _build_valid_payload("pub_tenant_cross")

    res_a = gw.ingest_signal_payload(user_a, payload_a)
    assert res_a["success"] is True

    res_b = gw.ingest_signal_payload(user_b, payload_b)
    assert res_b["success"] is True

    recs_a = repo.list_records_for_user(user_id=user_a.user_id)
    recs_b = repo.list_records_for_user(user_id=user_b.user_id)

    assert len(recs_a) == 1
    assert recs_a[0]["user_id"] == "usr_tenant_a"

    assert len(recs_b) == 1
    assert recs_b[0]["user_id"] == "usr_tenant_b"
