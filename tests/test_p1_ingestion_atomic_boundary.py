"""Multi-Dimensional Integration & Boundary Verification Suite for P1 Ingestion Identity & Persistence.

Tests Positive, Negative, Adversarial/Conflict, Concurrency/Replay,
Crash/Failure Recovery, Process Locking, Corruption Fail-Closed, Tenant/Scope Isolation,
Mutation Bypass Rejection, and Multiprocessing Concurrency.
"""

import json
import multiprocessing
import os
import shutil
import tempfile
import threading
import time
from typing import Any, Dict

import pytest

from src.platform.adapters.project1_repository import (
    FileBackedProject1IntegrationRepository,
    RepositoryStatus,
    StorageCorruptError,
    StorageUnavailableError,
    _ProcessLock,
)
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

    res_unauth = gw.ingest_signal_payload(None, _build_valid_payload("pub_neg_1"))
    assert res_unauth["success"] is False
    assert res_unauth["error_code"] == "UNAUTHENTICATED"

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

    res1 = gw.ingest_signal_payload(user_a, payload)
    assert res1["success"] is True
    assert res1["status"] == "INGESTED"

    res_replay = gw.ingest_signal_payload(user_a, payload)
    assert res_replay["success"] is True
    assert res_replay["status"] == "DUPLICATE_ACCEPTED"

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

    res2 = gw.ingest_signal_payload(user_a, p2)
    assert res2["success"] is False
    assert res2["error_code"] in ("INTEGRITY_CONFLICT", "IDENTITY_COLLISION")


# ============================================================================
# 4. AMBIGUOUS PERSISTED STATE FAIL-CLOSED TESTS
# ============================================================================

def test_ambiguous_persisted_state_fails_closed_never_creates(temp_repo_file, setup_gateway):
    gw, repo, user_a, _ = setup_gateway

    ambiguous_payload = {
        "schema_version": 1,
        "updated_at": time.time(),
        "records": [
            {
                "integration_id": "usr_tenant_a:p1_pub_ambig_evt_1",
                "user_id": "usr_tenant_a",
                "publication_id": "pub_ambig",
                "event_id": "evt_1",
                "signal_id": "sig_1",
                "entry_price": 2650.0,
                "symbol": "XAUUSD",
            },
            {
                "integration_id": "usr_tenant_a:p1_pub_ambig_evt_2",
                "user_id": "usr_tenant_a",
                "publication_id": "pub_ambig",
                "event_id": "evt_2",
                "signal_id": "sig_2",
                "entry_price": 9999.0,
                "symbol": "XAUUSD",
            },
        ],
    }

    with open(temp_repo_file, "w", encoding="utf-8") as f:
        json.dump(ambiguous_payload, f)

    repo._load_from_storage_unlocked()

    new_candidate = _build_valid_payload("pub_ambig", event_id="evt_new", signal_id="sig_new")
    res = gw.ingest_signal_payload(user_a, new_candidate)

    assert res["success"] is False
    assert res["error_code"] == "IDENTITY_AMBIGUOUS"

    recs = repo.list_records_for_user(user_id=user_a.user_id)
    assert len(recs) == 2


# ============================================================================
# 5. CORRUPTED STORAGE FAIL-CLOSED TESTS
# ============================================================================

def test_corrupted_storage_fails_closed_never_creates(temp_repo_file, setup_gateway):
    gw, repo, user_a, _ = setup_gateway

    with open(temp_repo_file, "w", encoding="utf-8") as f:
        f.write("{ invalid json corrupted content ...")

    new_candidate = _build_valid_payload("pub_corrupt_1")
    res = gw.ingest_signal_payload(user_a, new_candidate)

    assert res["success"] is False
    assert res["error_code"] == "STORAGE_CORRUPT"

    assert len(repo.list_records_for_user(user_id=user_a.user_id)) == 0


# ============================================================================
# 6. PROCESS LOCK FAIL-CLOSED & CONSTRUCTOR FAILURE TESTS
# ============================================================================

def test_process_lock_failure_fails_closed(setup_gateway, monkeypatch):
    gw, repo, user_a, _ = setup_gateway

    def mock_lock_fail(self_lock):
        raise StorageUnavailableError("Failed acquiring process lock on simulated lock file")

    monkeypatch.setattr(_ProcessLock, "__enter__", mock_lock_fail)

    new_candidate = _build_valid_payload("pub_lock_fail")
    res = gw.ingest_signal_payload(user_a, new_candidate)

    assert res["success"] is False
    assert res["error_code"] == "STORAGE_UNAVAILABLE"


def test_constructor_lock_failure_marks_repo_unavailable(temp_repo_file, monkeypatch):
    def mock_lock_fail(self_lock):
        raise StorageUnavailableError("Failed acquiring lock on startup")

    monkeypatch.setattr(_ProcessLock, "__enter__", mock_lock_fail)

    repo = FileBackedProject1IntegrationRepository(storage_filepath=temp_repo_file)
    assert repo._is_unavailable is True

    res = repo.ingest_authoritative_record({"integration_id": "int_1", "publication_id": "pub_1"})
    assert res["status"] == RepositoryStatus.STORAGE_UNAVAILABLE
    assert repo.get_record_by_id("int_1") is None
    assert repo.list_records_for_user() == []


# ============================================================================
# 7. MUTATION BYPASS REJECTION TESTS
# ============================================================================

def test_save_record_mutation_bypass_rejected(setup_gateway):
    gw, repo, user_a, _ = setup_gateway
    p1 = _build_valid_payload("pub_bypass_1")
    res = gw.ingest_signal_payload(user_a, p1)
    ingested_rec = res["record"]

    # Attempting to mutate entry_price directly via save_record must be rejected
    mutated_record = dict(ingested_rec)
    mutated_record["entry_price"] = 9999.0

    with pytest.raises(ValueError, match="Mutation bypass rejected"):
        repo.save_record(mutated_record)


# ============================================================================
# 8. CONCURRENCY & MULTIPROCESSING TESTS
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


def _process_worker_ingest(storage_filepath: str, pub_id: str, evt_id: str, result_queue: multiprocessing.Queue):
    try:
        sec = SecurityBoundaryService()
        audit = PlatformAuditControlService(security_boundary=sec)
        repo = FileBackedProject1IntegrationRepository(storage_filepath=storage_filepath, audit_control=audit)
        gw = Project1IntegrationGatewayService(repository=repo, security_boundary=sec, audit_control=audit)
        user = UserAuthorization(user_id="usr_mp_worker", auth_code="code_mp", role=UserRole.USER)
        payload = _build_valid_payload(pub_id, event_id=evt_id, signal_id=f"sig_{evt_id}")
        res = gw.ingest_signal_payload(user, payload)
        result_queue.put(res)
    except Exception as exc:
        result_queue.put({"success": False, "error": str(exc)})


def test_multiprocessing_process_concurrency_proof(temp_repo_file):
    queue = multiprocessing.Queue()
    processes = []
    num_procs = 4

    for i in range(num_procs):
        p = multiprocessing.Process(
            target=_process_worker_ingest,
            args=(temp_repo_file, f"pub_mp_{i}", f"evt_mp_{i}", queue),
        )
        processes.append(p)

    for p in processes:
        p.start()

    for p in processes:
        p.join(timeout=5)

    results = []
    while not queue.empty():
        results.append(queue.get())

    assert len(results) == num_procs
    for res in results:
        assert res["success"] is True

    sec = SecurityBoundaryService()
    repo = FileBackedProject1IntegrationRepository(storage_filepath=temp_repo_file)
    recs = repo.list_records_for_user(user_id="usr_mp_worker")
    assert len(recs) == num_procs


# ============================================================================
# 9. CRASH SAFETY & PERSISTENCE FAILURE RECOVERY
# ============================================================================

def test_crash_safety_rollback_on_write_failure(setup_gateway):
    gw, repo, user_a, _ = setup_gateway
    payload = _build_valid_payload("pub_crash_1")
    payload["integration_id"] = "usr_tenant_a:int_pub_crash_1"

    def mock_flush_fail():
        raise RuntimeError("Disk full / Write failure simulated")

    repo._flush_to_storage_unlocked = mock_flush_fail

    res = repo.ingest_authoritative_record(payload, user_id=user_a.user_id)
    assert res["status"] == RepositoryStatus.PERSISTENCE_FAILURE

    recs = repo.list_records_for_user(user_id=user_a.user_id)
    assert len(recs) == 0


# ============================================================================
# 10. TENANT & SCOPE ISOLATION TESTS
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
