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


def test_replay_with_changed_provenance_metadata_is_integrity_conflict(setup_gateway):
    gw, _, user_a, _ = setup_gateway
    payload = _build_valid_payload("pub_metadata_integrity")
    payload["is_live"] = True
    assert gw.ingest_signal_payload(user_a, payload)["success"] is True

    changed = dict(payload)
    changed["is_live"] = False
    result = gw.ingest_signal_payload(user_a, changed)
    assert result["success"] is False
    assert result["error_code"] == "INTEGRITY_CONFLICT"


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

    with pytest.raises(StorageCorruptError):
        repo.list_records_for_user(user_id=user_a.user_id)


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
    with pytest.raises(StorageUnavailableError):
        repo.get_record_by_id("int_1")
    with pytest.raises(StorageUnavailableError):
        repo.list_records_for_user()


# ============================================================================
# 7. MUTATION BYPASS REJECTION & COLLISION TESTS
# ============================================================================

def test_save_record_mutation_bypass_rejected(setup_gateway):
    gw, repo, user_a, _ = setup_gateway
    p1 = _build_valid_payload("pub_bypass_1")
    res = gw.ingest_signal_payload(user_a, p1)
    ingested_rec = res["record"]

    # Exact float mutation reject
    mutated_record = dict(ingested_rec)
    mutated_record["entry_price"] = 2650.000000001
    with pytest.raises(ValueError, match="Mutation bypass rejected"):
        repo.save_record(mutated_record)

    # All 23 authoritative fields mutation rejection
    auth_fields = [
        ("publication_id", "pub_mutated"),
        ("event_id", "evt_mutated"),
        ("signal_id", "sig_mutated"),
        ("decision_id", "dec_mutated"),
        ("canonical_live_decision_fingerprint", "fp_mutated"),
        ("candidate_id", "cand_mutated"),
        ("research_evidence_id", "evid_mutated"),
        ("strategy_name", "strat_mutated"),
        ("research_fingerprint", "rf_mutated"),
        ("runtime_authorization_fingerprint", "rta_mutated"),
        ("strategy_version", "9.9.9"),
        ("symbol", "EURUSD"),
        ("signal_type", "sell"),
        ("timeframe", "H1"),
        ("entry_price", 1.0500),
        ("stop_loss", 1.0600),
        ("take_profit_1", 1.0400),
        ("take_profit_2", 1.0300),
        ("take_profit_3", 1.0200),
        ("confidence", 0.11),
        ("operational_stability_score", 0.22),
        ("trailing_stop", {"distance": 10.0, "is_active": False}),
        ("invalidation_condition", "Mutated condition"),
    ]

    for key, val in auth_fields:
        mutated = dict(ingested_rec)
        mutated[key] = val
        with pytest.raises(ValueError, match="Mutation bypass rejected"):
            repo.save_record(mutated)


def test_integration_id_collision_and_pairwise_mismatches(setup_gateway):
    gw, repo, user_a, user_b = setup_gateway

    p1 = _build_valid_payload("pub_pair_1", event_id="evt_pair_1", signal_id="sig_pair_1")
    res1 = gw.ingest_signal_payload(user_a, p1)
    assert res1["success"] is True

    # integration_id collision with different publication_id
    colliding = _build_valid_payload("pub_pair_other", event_id="evt_pair_other", signal_id="sig_pair_other")
    colliding["integration_id"] = res1["record"]["integration_id"]
    res_coll = repo.ingest_authoritative_record(colliding, user_id=user_a.user_id)
    assert res_coll["status"] == RepositoryStatus.IDENTITY_COLLISION

    # Pairwise identity mismatches
    # Same publication_id, different event_id
    mismatch_pub_evt = _build_valid_payload("pub_pair_1", event_id="evt_pair_diff", signal_id="sig_pair_1")
    mismatch_pub_evt["integration_id"] = "usr_tenant_a:int_mismatch_1"
    res_m1 = repo.ingest_authoritative_record(mismatch_pub_evt, user_id=user_a.user_id)
    assert res_m1["status"] == RepositoryStatus.IDENTITY_COLLISION

    # Same event_id, different publication_id
    mismatch_evt_pub = _build_valid_payload("pub_pair_diff", event_id="evt_pair_1", signal_id="sig_pair_1")
    mismatch_evt_pub["integration_id"] = "usr_tenant_a:int_mismatch_2"
    res_m2 = repo.ingest_authoritative_record(mismatch_evt_pub, user_id=user_a.user_id)
    assert res_m2["status"] == RepositoryStatus.IDENTITY_COLLISION

    # Same signal_id, different publication_id
    mismatch_sig_pub = _build_valid_payload("pub_pair_diff2", event_id="evt_pair_diff2", signal_id="sig_pair_1")
    mismatch_sig_pub["integration_id"] = "usr_tenant_a:int_mismatch_3"
    res_m3 = repo.ingest_authoritative_record(mismatch_sig_pub, user_id=user_a.user_id)
    assert res_m3["status"] == RepositoryStatus.IDENTITY_COLLISION


def test_pre_replace_fsync_failure_rolls_back_memory_and_cleans_tmp(setup_gateway, monkeypatch):
    gw, repo, user_a, _ = setup_gateway
    p1 = _build_valid_payload("pub_pre_replace_fail")
    p1["integration_id"] = "usr_tenant_a:int_pub_pre_replace_fail"
    p1["user_id"] = user_a.user_id

    def mock_fsync_fail(fd):
        raise OSError("Simulator file fsync error")

    monkeypatch.setattr(os, "fsync", mock_fsync_fail)

    res = repo.ingest_authoritative_record(p1, user_id=user_a.user_id)
    assert res["status"] == RepositoryStatus.PERSISTENCE_FAILURE
    assert len(repo.list_records_for_user(user_id=user_a.user_id)) == 0


def test_post_replace_directory_fsync_warning_preserves_commit_and_memory_sync(setup_gateway, monkeypatch):
    gw, repo, user_a, _ = setup_gateway
    p1 = _build_valid_payload("pub_post_replace_dir_fail")
    p1["integration_id"] = "usr_tenant_a:int_pub_post_replace_dir_fail"
    p1["user_id"] = user_a.user_id

    orig_fsync = os.fsync

    def mock_conditional_fsync(fd):
        try:
            st = os.fstat(fd)
            import stat
            if stat.S_ISDIR(st.st_mode):
                raise OSError("Simulated directory fsync failure")
        except Exception as e:
            if "directory" in str(e):
                raise
        orig_fsync(fd)

    monkeypatch.setattr(os, "fsync", mock_conditional_fsync)

    res = repo.ingest_authoritative_record(p1, user_id=user_a.user_id)
    assert res["status"] == RepositoryStatus.DURABILITY_UNCERTAIN

    recs = repo.list_records_for_user(user_id=user_a.user_id)
    assert len(recs) == 1
    assert recs[0]["publication_id"] == "pub_post_replace_dir_fail"

    # Exact retry on DURABILITY_UNCERTAIN is idempotent duplicate accepted
    res_retry = repo.ingest_authoritative_record(p1, user_id=user_a.user_id)
    assert res_retry["status"] == RepositoryStatus.DUPLICATE_ACCEPTED


def test_no_parent_directory_fsync_failure_durability_uncertain(monkeypatch):
    no_parent_filepath = "records_test_no_parent.json"
    if os.path.exists(no_parent_filepath):
        os.remove(no_parent_filepath)

    try:
        sec = SecurityBoundaryService()
        audit = PlatformAuditControlService(security_boundary=sec)
        repo = FileBackedProject1IntegrationRepository(storage_filepath=no_parent_filepath, audit_control=audit)

        orig_fsync = os.fsync

        def mock_conditional_fsync(fd):
            try:
                st = os.fstat(fd)
                import stat
                if stat.S_ISDIR(st.st_mode):
                    raise OSError("Simulated current dir '.' fsync failure")
            except Exception as e:
                if "dir" in str(e):
                    raise
            orig_fsync(fd)

        monkeypatch.setattr(os, "fsync", mock_conditional_fsync)

        p1 = _build_valid_payload("pub_no_parent")
        p1["user_id"] = "usr_tenant_a"
        p1["integration_id"] = "usr_tenant_a:int_no_parent"

        res = repo.ingest_authoritative_record(p1, user_id="usr_tenant_a")
        assert res["status"] == RepositoryStatus.DURABILITY_UNCERTAIN

        recs = repo.list_records_for_user(user_id="usr_tenant_a")
        assert len(recs) == 1
        assert recs[0]["publication_id"] == "pub_no_parent"

        # Retry is idempotent
        res_retry = repo.ingest_authoritative_record(p1, user_id="usr_tenant_a")
        assert res_retry["status"] == RepositoryStatus.DUPLICATE_ACCEPTED
    finally:
        if os.path.exists(no_parent_filepath):
            os.remove(no_parent_filepath)
        if os.path.exists(f"{no_parent_filepath}.lock"):
            os.remove(f"{no_parent_filepath}.lock")


def test_gateway_durability_uncertain_handling(setup_gateway, monkeypatch):
    gw, repo, user_a, _ = setup_gateway
    p1 = _build_valid_payload("pub_gw_durability")

    def mock_ingest_durability_uncertain(record, user_id=None):
        return {
            "status": RepositoryStatus.DURABILITY_UNCERTAIN,
            "record": record,
            "message": "Directory fsync failed after replace",
        }

    monkeypatch.setattr(repo, "ingest_authoritative_record", mock_ingest_durability_uncertain)

    res = gw.ingest_signal_payload(user_a, p1)
    assert res["success"] is False
    assert res["status"] == "DURABILITY_UNCERTAIN"
    assert res["error_code"] == "DURABILITY_UNCERTAIN"


def test_gateway_unknown_repository_status_fails_closed(setup_gateway, monkeypatch):
    gw, repo, user_a, _ = setup_gateway
    p1 = _build_valid_payload("pub_gw_unknown_status")

    def mock_ingest_unknown_status(record, user_id=None):
        return {
            "status": "FUTURE_UNHANDLED_STATUS",
            "record": record,
            "message": "Future repository status not handled",
        }

    monkeypatch.setattr(repo, "ingest_authoritative_record", mock_ingest_unknown_status)

    res = gw.ingest_signal_payload(user_a, p1)
    assert res["success"] is False
    assert res["error_code"] == "UNKNOWN_REPOSITORY_STATUS"


def test_typeerror_compatibility_escape_proof(setup_gateway):
    from src.platform.adapters.project1_adapter import Project1GatewayAdapter

    class BuggyRepoPort:
        def list_records_for_user(self, user_id=None, symbol=None, lifecycle_state=None, limit=500, allow_system=False, publication_order=False):
            raise TypeError("Internal bug in repository implementation")

    class BuggyGatewayService:
        def __init__(self):
            self._repo = BuggyRepoPort()

    adapter = Project1GatewayAdapter(gateway_service=BuggyGatewayService())

    with pytest.raises(TypeError, match="Internal bug in repository implementation"):
        adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h")


def test_all_repository_statuses_mapped_in_gateway(setup_gateway):
    import inspect
    from src.platform.adapters.project1_repository import RepositoryStatus

    gw, repo, user_a, _ = setup_gateway
    gw_code = inspect.getsource(gw.ingest_signal_payload)

    for status in RepositoryStatus:
        assert str(status.value) in gw_code or status.name in gw_code, f"RepositoryStatus member {status} missing explicit mapping in gateway!"


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
        p.join(timeout=10.0)
        assert p.exitcode == 0, f"Worker process failed with exitcode {p.exitcode}"

    results = []
    for _ in range(num_procs):
        results.append(queue.get(timeout=5.0))

    assert len(results) == num_procs
    for res in results:
        assert res.get("success") is True, f"Multiprocessing worker failed: {res}"

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


def test_adversarial_strict_user_isolation_rejects_cross_user_and_system_claim(temp_repo_file, setup_gateway):
    gw, repo, user_a, user_b = setup_gateway

    # Insert records with user_id = user_b, system, p1_service_ingest, global, and None directly into repo
    recs = [
        {"integration_id": "int_b", "user_id": "usr_tenant_b", "publication_id": "pub_b", "event_id": "evt_b", "signal_id": "sig_b", "lifecycle_state": "STAGED"},
        {"integration_id": "int_sys", "user_id": "system", "publication_id": "pub_sys", "event_id": "evt_sys", "signal_id": "sig_sys", "lifecycle_state": "STAGED"},
        {"integration_id": "int_p1", "user_id": "p1_service_ingest", "publication_id": "pub_p1", "event_id": "evt_p1", "signal_id": "sig_p1", "lifecycle_state": "STAGED"},
        {"integration_id": "int_glob", "user_id": "global", "publication_id": "pub_glob", "event_id": "evt_glob", "signal_id": "sig_glob", "lifecycle_state": "STAGED"},
        {"integration_id": "int_none", "user_id": None, "publication_id": "pub_none", "event_id": "evt_none", "signal_id": "sig_none", "lifecycle_state": "STAGED"},
    ]

    for r in recs:
        repo.save_record(r)

    # 1. User A get_record_by_id MUST NOT return User B or system/global/None records
    for target_int_id in ("int_b", "int_sys", "int_p1", "int_glob", "int_none"):
        assert repo.get_record_by_id(target_int_id, user_id=user_a.user_id) is None

    # 2. User A list_records_for_user MUST NOT return User B or system/global/None records when allow_system=False
    assert len(repo.list_records_for_user(user_id=user_a.user_id, allow_system=False)) == 0

    # 3. User A is_duplicate_request MUST NOT match User B or system/global/None signals
    for target_sig in ("sig_b", "sig_sys", "sig_p1", "sig_glob", "sig_none"):
        assert repo.is_duplicate_request(target_sig, user_id=user_a.user_id) is False

    # 4. User A update_lifecycle_state MUST NOT mutate User B or system/global/None signals
    for target_sig in ("sig_b", "sig_sys", "sig_p1", "sig_glob", "sig_none"):
        updated = repo.update_lifecycle_state(target_sig, "CANCELLED", user_id=user_a.user_id)
        assert updated is False

    # 5. User A find_authoritative_record MUST NOT return User B or system/global/None signals
    for pub_id in ("pub_b", "pub_sys", "pub_p1", "pub_glob", "pub_none"):
        found = repo.find_authoritative_record({"publication_id": pub_id}, user_id=user_a.user_id)
        assert found is None

    # 6. Explicit system scope query (allow_system=True or user_id=None) CAN view system records
    sys_recs = repo.list_records_for_user(user_id=user_a.user_id, allow_system=True)
    assert len(sys_recs) == 3  # system, p1_service_ingest, global; tenantless is ambiguous


def test_initialization_durability_failures_raise_storage_unavailable(tmp_path, monkeypatch):
    non_existent_file = str(tmp_path / "non_existent_dir" / "records.json")

    # Initial directory creation failure
    def mock_makedirs_fail(path, exist_ok=False):
        raise OSError("Directory creation denied")

    monkeypatch.setattr(os, "makedirs", mock_makedirs_fail)

    repo = FileBackedProject1IntegrationRepository(storage_filepath=non_existent_file)
    assert repo._is_unavailable is True
    with pytest.raises(StorageUnavailableError):
        repo.list_records_for_user()


def test_complete_6_direction_pairwise_identity_collision_matrix(setup_gateway):
    gw, repo, user_a, _ = setup_gateway

    base_p = _build_valid_payload("pub_matrix", event_id="evt_matrix", signal_id="sig_matrix")
    base_p["integration_id"] = "usr_tenant_a:int_base_matrix"
    base_p["user_id"] = user_a.user_id
    res_base = repo.ingest_authoritative_record(base_p, user_id=user_a.user_id)
    assert res_base["status"] == RepositoryStatus.CREATED

    matrix_cases = [
        ("1. same pub, diff evt", "pub_matrix", "evt_diff_1", "sig_matrix", "usr_tenant_a:int_m1"),
        ("2. same pub, diff sig", "pub_matrix", "evt_matrix", "sig_diff_2", "usr_tenant_a:int_m2"),
        ("3. same evt, diff pub", "pub_diff_3", "evt_matrix", "sig_matrix", "usr_tenant_a:int_m3"),
        ("4. same evt, diff sig", "pub_diff_4", "evt_matrix", "sig_diff_4", "usr_tenant_a:int_m4"),
        ("5. same sig, diff pub", "pub_diff_5", "evt_diff_5", "sig_matrix", "usr_tenant_a:int_m5"),
        ("6. same sig, diff evt", "pub_diff_6", "evt_diff_6", "sig_matrix", "usr_tenant_a:int_m6"),
    ]

    for label, pub, evt, sig, int_id in matrix_cases:
        case_payload = _build_valid_payload(pub, event_id=evt, signal_id=sig)
        case_payload["integration_id"] = int_id
        case_payload["user_id"] = user_a.user_id
        res = repo.ingest_authoritative_record(case_payload, user_id=user_a.user_id)
        assert res["status"] == RepositoryStatus.IDENTITY_COLLISION, f"Failed case {label}"
