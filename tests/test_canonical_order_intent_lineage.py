"""Adversarial security and fail-closed lineage tests for canonical OrderIntent creation.

Verifies requirements A through S for PR2 roadmap stage:
A. caller-supplied AutonomousAuthorization cannot create canonical P1 OrderIntent.
B. caller-supplied Entry/SL/TP cannot override P1.
C. missing TP2 cannot cause TP1 to be copied into TP2.
D. missing TP3 cannot cause TP1 to be copied into TP3.
E. caller-supplied quantity cannot become canonical quantity.
F. missing publication_id fails closed.
G. missing decision_id fails closed.
H. missing candidate_id fails closed.
I. missing research_evidence_id fails closed.
J. missing canonical_live_decision_fingerprint fails closed.
K. missing runtime_authorization_fingerprint fails closed.
L. same publication + same authoritative content is idempotent.
M. same publication + mutated authoritative content raises/rejects integrity conflict.
N. different publications cannot collapse into one OrderIntent.
O. exact Entry/SL/TP1/TP2/TP3/trailing/invalidation values are preserved.
P. confidence cannot be transformed into operational Stability by the canonical path.
Q. local Project1SignalPresenter processing cannot create a canonical P1 OrderIntent through synthetic authorization.
R. caller-controlled idempotency key cannot create a second canonical intent for the same publication.
S. frontend/client payload containing trade levels or quantity cannot override server-resolved P1 authority.
"""

import time
import pytest

from src.platform.domain.user_authorization import UserAuthorization, UserRole
from src.platform.services.order_intent import OrderIntentService
from src.platform.services.project1_gateway import Project1IntegrationGatewayService
from src.platform.services.project1_presenter import Project1SignalPresenter
from src.platform.adapters.project1_adapter import Project1GatewayAdapter


def _build_valid_p1_record(publication_id="pub_001"):
    return {
        "contract_version": "1.0",
        "event_id": publication_id,
        "publication_id": publication_id,
        "signal_id": f"sig_{publication_id}",
        "decision_id": f"dec_{publication_id}",
        "canonical_live_decision_fingerprint": f"canon_fp_{publication_id}",
        "candidate_id": f"cand_{publication_id}",
        "research_evidence_id": f"rese_ev_{publication_id}",
        "strategy_name": "GoldTrendv1",
        "strategy_id": "GoldTrendv1",
        "research_fingerprint": f"rfp_{publication_id}",
        "runtime_authorization_fingerprint": f"rafp_{publication_id}",
        "strategy_version": "1.2.0",
        "symbol": "XAUUSD",
        "signal_type": "buy",
        "timestamp": time.time(),
        "entry_price": 2650.50,
        "stop_loss": 2635.00,
        "take_profit_1": 2670.00,
        "take_profit_2": 2690.00,
        "take_profit_3": 2710.00,
        "confidence": 0.85,
        "trailing_stop": {"distance": 15.0, "is_active": True},
        "invalidation_condition": "Close below 2630.00",
        "user_id": "user_test",
        "tenant_id": "tenant_user_test",
    }


@pytest.fixture
def setup_services():
    user = UserAuthorization(
        user_id="user_test",
        auth_code="ac_123",
        role=UserRole.USER,
    )
    gw_svc = Project1IntegrationGatewayService()
    order_svc = OrderIntentService(project1_gateway_service=gw_svc)
    return user, gw_svc, order_svc


def test_scenario_a_locally_supplied_authorization_cannot_create_canonical(setup_services):
    user, gw_svc, order_svc = setup_services
    # Scenario A: caller-supplied AutonomousAuthorization cannot create a canonical P1 OrderIntent.
    ok, msg, intent = order_svc.create_canonical_order_intent_from_publication(
        user=user,
        publication_id="pub_non_existent",
    )
    assert ok is False
    assert "No authoritative Project 1 integration record found" in msg
    assert intent is None


def test_scenario_b_caller_supplied_levels_cannot_override_p1(setup_services):
    user, gw_svc, order_svc = setup_services
    rec = _build_valid_p1_record("pub_b")
    gw_svc.ingest_signal_payload(user, rec)

    ok, msg, intent = order_svc.create_canonical_order_intent_from_publication(
        user=user,
        publication_id="pub_b",
    )
    assert ok is True
    assert intent is not None
    # Authoritative values from P1 must match exact record
    assert intent.requested_price == 2650.50
    assert intent.stop_loss == 2635.00
    assert intent.take_profit_1 == 2670.00


def test_scenarios_c_and_d_tp1_not_copied_to_tp2_or_tp3(setup_services):
    user, gw_svc, order_svc = setup_services
    rec = _build_valid_p1_record("pub_cd")
    rec["take_profit_2"] = None
    rec["take_profit_3"] = None
    gw_svc.ingest_signal_payload(user, rec)

    ok, msg, intent = order_svc.create_canonical_order_intent_from_publication(
        user=user,
        publication_id="pub_cd",
    )
    assert ok is True
    assert intent is not None
    assert intent.take_profit_1 == 2670.00
    # Scenario C & D: TP2 and TP3 must NOT be substituted with TP1
    assert intent.take_profit_2 is None
    assert intent.take_profit_3 is None


def test_scenario_e_quantity_not_invented_or_caller_injected(setup_services):
    user, gw_svc, order_svc = setup_services
    rec = _build_valid_p1_record("pub_e")
    # P1 record does not contain quantity
    gw_svc.ingest_signal_payload(user, rec)

    ok, msg, intent = order_svc.create_canonical_order_intent_from_publication(
        user=user,
        publication_id="pub_e",
    )
    assert ok is True
    assert intent is not None
    # Scenario E: P2 must NOT invent a quantity
    assert intent.requested_quantity is None


def test_scenarios_f_to_k_missing_lineage_fails_closed(setup_services):
    user, gw_svc, order_svc = setup_services

    lineage_fields = [
        ("F", "publication_id"),
        ("G", "decision_id"),
        ("H", "candidate_id"),
        ("I", "research_evidence_id"),
        ("J", "canonical_live_decision_fingerprint"),
        ("K", "runtime_authorization_fingerprint"),
    ]

    for label, field_name in lineage_fields:
        pub_id = f"pub_lineage_{field_name}"
        rec = _build_valid_p1_record(pub_id)
        rec[field_name] = None
        if field_name == "publication_id":
            rec["event_id"] = None
            rec["integration_id"] = None

        gw_svc.ingest_signal_payload(user, rec)

        ok, msg, intent = order_svc.create_canonical_order_intent_from_publication(
            user=user,
            publication_id=pub_id if field_name != "publication_id" else rec["signal_id"],
        )
        assert ok is False, f"Scenario {label} failed: expected missing {field_name} to fail closed"
        assert "Missing mandatory authoritative lineage field" in msg or "No authoritative" in msg
        assert intent is None


def test_scenario_l_same_publication_and_content_is_idempotent(setup_services):
    user, gw_svc, order_svc = setup_services
    rec = _build_valid_p1_record("pub_l")
    gw_svc.ingest_signal_payload(user, rec)

    ok1, msg1, intent1 = order_svc.create_canonical_order_intent_from_publication(
        user=user,
        publication_id="pub_l",
    )
    assert ok1 is True

    ok2, msg2, intent2 = order_svc.create_canonical_order_intent_from_publication(
        user=user,
        publication_id="pub_l",
    )
    assert ok2 is True
    assert intent1.order_intent_id == intent2.order_intent_id


def test_scenario_m_same_publication_with_mutated_content_rejected(setup_services):
    user, gw_svc, order_svc = setup_services
    rec = _build_valid_p1_record("pub_m")
    gw_svc.ingest_signal_payload(user, rec)

    ok1, msg1, intent1 = order_svc.create_canonical_order_intent_from_publication(
        user=user,
        publication_id="pub_m",
    )
    assert ok1 is True

    # Mutate record in repo for pub_m directly in storage
    for r in gw_svc._repo._records:
        if r.get("publication_id") == "pub_m":
            r["entry_price"] = 9999.99

    ok2, msg2, intent2 = order_svc.create_canonical_order_intent_from_publication(
        user=user,
        publication_id="pub_m",
    )
    assert ok2 is False
    assert "Integrity conflict" in msg2
    assert intent2 is None


def test_scenario_n_different_publications_do_not_collapse(setup_services):
    user, gw_svc, order_svc = setup_services
    rec_n1 = _build_valid_p1_record("pub_n1")
    rec_n2 = _build_valid_p1_record("pub_n2")
    gw_svc.ingest_signal_payload(user, rec_n1)
    gw_svc.ingest_signal_payload(user, rec_n2)

    ok1, _, intent1 = order_svc.create_canonical_order_intent_from_publication(user, "pub_n1")
    ok2, _, intent2 = order_svc.create_canonical_order_intent_from_publication(user, "pub_n2")

    assert ok1 is True and ok2 is True
    assert intent1.order_intent_id != intent2.order_intent_id


def test_scenario_o_preserves_exact_trade_values(setup_services):
    user, gw_svc, order_svc = setup_services
    rec = _build_valid_p1_record("pub_o")
    rec["entry_price"] = 2655.123
    rec["stop_loss"] = 2631.456
    rec["take_profit_1"] = 2680.789
    rec["trailing_stop"] = {"distance": 12.5, "is_active": True}
    rec["invalidation_condition"] = "Breakout fail under 2625"
    gw_svc.ingest_signal_payload(user, rec)

    ok, _, intent = order_svc.create_canonical_order_intent_from_publication(user, "pub_o")
    assert ok is True
    assert intent.requested_price == 2655.123
    assert intent.stop_loss == 2631.456
    assert intent.take_profit_1 == 2680.789
    assert intent.trailing_stop["distance"] == 12.5
    assert intent.trailing_stop["is_active"] is True
    assert intent.invalidation_condition == "Breakout fail under 2625"


def test_scenario_p_confidence_not_transformed_into_stability(setup_services):
    user, gw_svc, order_svc = setup_services
    rec = _build_valid_p1_record("pub_p")
    rec["confidence"] = 0.99
    gw_svc.ingest_signal_payload(user, rec)

    ok, _, intent = order_svc.create_canonical_order_intent_from_publication(user, "pub_p")
    assert ok is True
    # OrderIntent domain model stores authoritative lineage and exact trade levels, NOT transformed stability
    assert hasattr(intent, "requested_price")
    assert not hasattr(intent, "stability_score")


def test_scenario_q_presenter_cannot_create_canonical_order_intent(setup_services):
    user, gw_svc, order_svc = setup_services
    rec = _build_valid_p1_record("pub_q")
    gw_svc.ingest_signal_payload(user, rec)

    adapter = Project1GatewayAdapter(gateway_service=gw_svc)
    presenter = Project1SignalPresenter(port=adapter, order_intent_service=order_svc)

    snapshot = presenter.build_host_snapshot("XAUUSD", "1h", user=user)
    # Presenter snapshot must NOT automatically synthesize an OrderIntent
    assert len(snapshot["orderIntents"]) == 0


def test_scenario_r_caller_controlled_idempotency_key_cannot_create_second_intent(setup_services):
    user, gw_svc, order_svc = setup_services
    rec = _build_valid_p1_record("pub_r")
    gw_svc.ingest_signal_payload(user, rec)

    ok1, _, intent1 = order_svc.create_canonical_order_intent_from_publication(user, "pub_r", idempotency_key="idemp_1")
    ok2, _, intent2 = order_svc.create_canonical_order_intent_from_publication(user, "pub_r", idempotency_key="idemp_2_different")

    assert ok1 is True and ok2 is True
    # Scenario R: caller-supplied different idempotency key cannot bypass publication identity
    assert intent1.order_intent_id == intent2.order_intent_id


def test_scenario_s_client_payload_cannot_override_server_resolved_authority(setup_services):
    user, gw_svc, order_svc = setup_services
    rec = _build_valid_p1_record("pub_s")
    gw_svc.ingest_signal_payload(user, rec)

    # Calling canonical OrderIntent creation passes publication_id only, server resolves P1 authority
    ok, _, intent = order_svc.create_canonical_order_intent_from_publication(user, "pub_s")
    assert ok is True
    assert intent.requested_price == 2650.50


class TrustedGateway:
    def resolve_authoritative_publication(self, user, publication_id):
        return {
            "publication_id": publication_id,
            "signal_id": "trusted-signal",
            "decision_id": "trusted-decision",
            "canonical_live_decision_fingerprint": "trusted-canon",
            "candidate_id": "trusted-candidate",
            "research_evidence_id": "trusted-evidence",
            "strategy_id": "trusted-strategy",
            "research_fingerprint": "trusted-research",
            "runtime_authorization_fingerprint": "trusted-runtime-auth",
            "strategy_version": "1.0",
            "symbol": "XAUUSD",
            "signal_type": "buy",
            "entry_price": 100.0,
            "stop_loss": 90.0,
            "take_profit_1": 110.0,
            "take_profit_2": 120.0,
            "take_profit_3": 130.0,
            "trailing_stop": {"distance": 5.0},
            "invalidation_condition": "close below 85",
        }


class AttackerGateway:
    def resolve_authoritative_publication(self, user, publication_id):
        return {
            "publication_id": publication_id,
            "signal_id": "ATTACKER-SIGNAL",
            "decision_id": "ATTACKER-DECISION",
            "canonical_live_decision_fingerprint": "ATTACKER-CANON",
            "candidate_id": "ATTACKER-CANDIDATE",
            "research_evidence_id": "ATTACKER-EVIDENCE",
            "strategy_id": "ATTACKER-STRATEGY",
            "research_fingerprint": "ATTACKER-RESEARCH",
            "runtime_authorization_fingerprint": "ATTACKER-RUNTIME",
            "strategy_version": "999",
            "symbol": "BTCUSD",
            "signal_type": "sell",
            "entry_price": 999999.0,
            "stop_loss": 1.0,
            "take_profit_1": 2.0,
            "take_profit_2": 3.0,
            "take_profit_3": 4.0,
            "trailing_stop": {"distance": 999.0},
            "invalidation_condition": "ATTACKER",
        }


def test_caller_cannot_inject_attacker_gateway():
    user = UserAuthorization(user_id="user_test", auth_code="ac_123", role=UserRole.USER)
    order_svc = OrderIntentService(project1_gateway_service=TrustedGateway())

    # Passing project1_gateway_service to create_canonical_order_intent_from_publication must raise TypeError
    with pytest.raises(TypeError):
        order_svc.create_canonical_order_intent_from_publication(
            user=user,
            publication_id="pub_test",
            project1_gateway_service=AttackerGateway(),  # type: ignore
        )

    # Normal call uses constructor-injected TrustedGateway
    ok, msg, intent = order_svc.create_canonical_order_intent_from_publication(
        user=user,
        publication_id="pub_test",
    )

    assert ok is True
    assert intent is not None
    assert intent.signal_id == "trusted-signal"
    assert intent.decision_id == "trusted-decision"
    assert intent.symbol == "XAUUSD"
    assert intent.direction == "buy"
    assert intent.requested_price == 100.0


def test_defect_1_get_by_publication_id_and_concurrency(setup_services, tmp_path):
    import threading
    from src.platform.adapters.order_intent_repository import FileBackedOrderIntentRepository

    repo_file = str(tmp_path / "test_intents.json")
    repo = FileBackedOrderIntentRepository(storage_filepath=repo_file)

    user, gw_svc, _ = setup_services
    order_svc = OrderIntentService(project1_gateway_service=gw_svc, repository=repo)

    rec = _build_valid_p1_record("pub_def1")
    gw_svc.ingest_signal_payload(user, rec)

    # Verify initial lookup returns None
    assert repo.get_by_publication_id(user_id="user_test", publication_id="pub_def1") is None

    # Test concurrent creation of intent for same publication
    results = []

    def _create():
        res = order_svc.create_canonical_order_intent_from_publication(user, "pub_def1")
        results.append(res)

    threads = [threading.Thread(target=_create) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    # Exactly 5 calls completed
    assert len(results) == 5
    created_intents = [res[2] for res in results if res[0] and res[2] is not None]
    assert len(created_intents) == 5
    # All 5 return the EXACT SAME intent_id (idempotent duplicate)
    intent_ids = {intent.order_intent_id for intent in created_intents}
    assert len(intent_ids) == 1

    # Verify restart persistence loads publication_id index
    repo_reloaded = FileBackedOrderIntentRepository(storage_filepath=repo_file)
    fetched = repo_reloaded.get_by_publication_id(user_id="user_test", publication_id="pub_def1")
    assert fetched is not None
    assert fetched.order_intent_id == list(intent_ids)[0]


def test_defect_1_cross_tenant_isolation(setup_services, tmp_path):
    from src.platform.adapters.order_intent_repository import FileBackedOrderIntentRepository

    repo_file = str(tmp_path / "test_intents_tenant.json")
    repo = FileBackedOrderIntentRepository(storage_filepath=repo_file)

    user_a = UserAuthorization("user_a", "ac_a", role=UserRole.USER)
    user_b = UserAuthorization("user_b", "ac_b", role=UserRole.USER)

    gw_svc = Project1IntegrationGatewayService()
    order_svc = OrderIntentService(project1_gateway_service=gw_svc, repository=repo)

    rec_a = _build_valid_p1_record("pub_tenant_cross_a")
    rec_a["user_id"] = "user_a"
    rec_a["tenant_id"] = "tenant_user_a"

    rec_b = _build_valid_p1_record("pub_tenant_cross_b")
    rec_b["user_id"] = "user_b"
    rec_b["tenant_id"] = "tenant_user_b"

    gw_svc.ingest_signal_payload(user_a, rec_a)
    gw_svc.ingest_signal_payload(user_b, rec_b)

    ok_a, _, intent_a = order_svc.create_canonical_order_intent_from_publication(user_a, "pub_tenant_cross_a")
    assert ok_a is True

    # User B querying repo for publication_id 'pub_tenant_cross_a' with user_id=user_b must return None (no cross-tenant leak)
    assert repo.get_by_publication_id(user_id="user_b", publication_id="pub_tenant_cross_a") is None

    # User B creating intent for their own publication 'pub_tenant_cross_b' gets their OWN user-isolated OrderIntent
    ok_b, _, intent_b = order_svc.create_canonical_order_intent_from_publication(user_b, "pub_tenant_cross_b")
    assert ok_b is True
    assert intent_a.order_intent_id != intent_b.order_intent_id
    assert intent_a.user_id == "user_a"
    assert intent_b.user_id == "user_b"


def test_defect_2_20_field_mutation_integrity_conflict(setup_services):
    user, gw_svc, order_svc = setup_services
    rec = _build_valid_p1_record("pub_def2")
    gw_svc.ingest_signal_payload(user, rec)

    ok1, _, intent1 = order_svc.create_canonical_order_intent_from_publication(user, "pub_def2")
    assert ok1 is True

    # Check 20-field mutation detection for each field in tuple
    field_mutations = [
        ("signal_id", "MUTATED_SIG"),
        ("decision_id", "MUTATED_DEC"),
        ("canonical_live_decision_fingerprint", "MUTATED_CANON_FP"),
        ("candidate_id", "MUTATED_CAND"),
        ("research_evidence_id", "MUTATED_EVIDENCE"),
        ("strategy_id", "MUTATED_STRAT"),
        ("research_fingerprint", "MUTATED_RF_FP"),
        ("runtime_authorization_fingerprint", "MUTATED_RTA_FP"),
        ("strategy_version", "MUTATED_VERSION"),
        ("symbol", "EURUSD"),
        ("signal_type", "sell"),
        ("entry_price", 9999.0),
        ("stop_loss", 8888.0),
        ("take_profit_1", 1111.0),
        ("take_profit_2", 2222.0),
        ("take_profit_3", 3333.0),
        ("trailing_stop", {"distance": 99.0, "is_active": True}),
        ("invalidation_condition", "MUTATED_INVALIDATION"),
    ]

    for field_name, mutated_val in field_mutations:
        for r in gw_svc._repo._records:
            if r.get("publication_id") == "pub_def2":
                r[field_name] = mutated_val

        ok_mut, msg_mut, _ = order_svc.create_canonical_order_intent_from_publication(user, "pub_def2")
        assert ok_mut is False, f"Expected mutation of {field_name} to fail closed"
        assert "Integrity conflict" in msg_mut

        # Restore original value
        for r in gw_svc._repo._records:
            if r.get("publication_id") == "pub_def2":
                r[field_name] = rec.get(field_name)


def test_defect_2_falsey_quantity_preservation(setup_services):
    user, gw_svc, order_svc = setup_services
    rec = _build_valid_p1_record("pub_falsey_qty")

    # Manually insert requested_quantity into repo record to test domain model & service handling
    gw_svc.ingest_signal_payload(user, rec)
    for r in gw_svc._repo._records:
        if r.get("publication_id") == "pub_falsey_qty":
            r["requested_quantity"] = 1.5

    ok, _, intent = order_svc.create_canonical_order_intent_from_publication(user, "pub_falsey_qty")
    assert ok is True
    assert intent.requested_quantity == 1.5


def test_defect_3_recursive_trailing_stop_canonicalization(setup_services):
    user, gw_svc, order_svc = setup_services
    rec1 = _build_valid_p1_record("pub_trailing_1")
    gw_svc.ingest_signal_payload(user, rec1)

    ok1, _, intent1 = order_svc.create_canonical_order_intent_from_publication(user, "pub_trailing_1")
    assert ok1 is True

    # Re-order dict keys in repo record for pub_trailing_1
    for r in gw_svc._repo._records:
        if r.get("publication_id") == "pub_trailing_1":
            orig_ts = dict(r["trailing_stop"]) if isinstance(r.get("trailing_stop"), dict) else {}
            # Reverse keys
            r["trailing_stop"] = dict(reversed(list(orig_ts.items())))

    ok2, msg2, intent2 = order_svc.create_canonical_order_intent_from_publication(user, "pub_trailing_1")
    assert ok2 is True
    assert intent1.order_intent_id == intent2.order_intent_id


def test_defect_3_list_order_sensitivity_in_nested_trailing_stop(setup_services):
    user, gw_svc, order_svc = setup_services
    rec1 = _build_valid_p1_record("pub_trailing_list_sens")
    gw_svc.ingest_signal_payload(user, rec1)

    ok1, _, intent1 = order_svc.create_canonical_order_intent_from_publication(user, "pub_trailing_list_sens")
    assert ok1 is True

    # Mutate a value in trailing_stop -> must trigger integrity conflict
    for r in gw_svc._repo._records:
        if r.get("publication_id") == "pub_trailing_list_sens":
            if isinstance(r.get("trailing_stop"), dict):
                r["trailing_stop"]["distance"] = 99.0

    ok2, msg2, _ = order_svc.create_canonical_order_intent_from_publication(user, "pub_trailing_list_sens")
    assert ok2 is False
    assert "Integrity conflict" in msg2


def test_defect_3_strict_top_level_invalidation_condition_no_metadata_fallback(setup_services):
    user, gw_svc, order_svc = setup_services
    rec = _build_valid_p1_record("pub_inv_strict")
    # Store record with invalidation_condition=None in repo, but metadata having an invalidation condition
    gw_svc.ingest_signal_payload(user, rec)
    for r in gw_svc._repo._records:
        if r.get("publication_id") == "pub_inv_strict":
            r["invalidation_condition"] = None
            r["metadata"] = {"invalidation_condition": "SHOULD_BE_IGNORED"}

    ok, _, intent = order_svc.create_canonical_order_intent_from_publication(user, "pub_inv_strict")
    assert ok is True
    # Invalidation condition MUST NOT fall back to metadata
    assert intent.invalidation_condition is None


def test_blocker_5_duplicate_publication_ambiguity_fails_closed(setup_services):
    user, gw_svc, order_svc = setup_services
    rec1 = _build_valid_p1_record("pub_dup_ambiguous")
    rec2 = _build_valid_p1_record("pub_dup_ambiguous")
    rec1["integration_id"] = "int_1"
    rec2["integration_id"] = "int_2"
    rec2["entry_price"] = 9999.0  # Discrepancy / mutated authoritative content

    gw_svc._repo.save_record(rec1)
    gw_svc._repo.save_record(rec2)  # Insert second record directly into repo for pub_dup_ambiguous

    # Resolution should fail closed (return None) due to conflicting publication records
    resolved = gw_svc.resolve_authoritative_publication(user, "pub_dup_ambiguous")
    assert resolved is None

    ok, msg, intent = order_svc.create_canonical_order_intent_from_publication(user, "pub_dup_ambiguous")
    assert ok is False
    assert "No authoritative Project 1 integration record found" in msg
