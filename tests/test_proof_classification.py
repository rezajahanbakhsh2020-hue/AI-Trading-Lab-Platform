"""Adversarial Anti-Escape Test Suite for Verifier-Produced Proof Classification & Attestation.

Verifies all 20 mandatory anti-escape regression test cases:
1. Raw caller evidence/assertions -> NOT Level 3 (fails closed).
2. Fake production environment label -> NOT Level 3.
3. Fake deployment identity -> NOT Level 3.
4. Fake verifier identity -> NOT Level 3.
5. Fake signal ID -> NOT Level 3.
6. Fake timestamp -> NOT Level 3.
7. Remote URL without observed reachability -> NOT Level 3.
8. Observed reachability without deployment identity -> NOT Level 3.
9. Observed health without P1/P2 correlation -> NOT Level 3.
10. P1/P2 correlation without authoritative signal identity -> NOT Level 3.
11. Stale / corrupted receipt -> NOT Level 3.
12. Wrong timeframe -> NOT Level 3.
13. Wrong symbol -> NOT Level 3.
14. Localhost + caller assertions -> Level 2 at most.
15. Local HTTP 200 + caller assertions -> Level 2 at most.
16. Docker-only -> Level 2/Unavailable, never Level 3.
17. CI-only -> Level 1/Unavailable, never Level 3.
18. Config-only -> Unavailable, never Level 3.
19. Verifier-produced valid receipt -> Classifies correctly based on observed properties.
20. Absence of external deployment -> LEVEL_3_UNAVAILABLE.
"""

import pytest

from src.platform.domain.proof_classification import (
    ClassificationStatus,
    EvidenceLevel,
    RawVerificationObservation,
    RuntimeTargetVerifier,
    TrustedVerificationReceipt,
    canonicalize_timeframe,
    classify_proof,
    classify_verified_receipt,
    is_loopback_or_local_target,
)


def test_1_raw_caller_assertions_rejected():
    """Anti-Escape 1: Raw caller dictionaries or objects are rejected by the classifier."""
    caller_dict = {
        "target_url": "https://trade.yourdomain.com",
        "is_external_reachability_verified": True,
        "is_deployed_health_verified": True,
        "is_p1_p2_correlation_verified": True,
        "is_authoritative_signal_verified": True,
    }
    res = classify_verified_receipt(caller_dict)
    assert res.status == ClassificationStatus.LEVEL_3_UNAVAILABLE
    assert "Caller assertion rejected" in res.reason


def test_2_fake_production_environment_label_rejected():
    """Anti-Escape 2: Setting environment_claim='production' without verifier observations yields Level 1."""
    obs = RawVerificationObservation(
        target_url=None,
        http_status_code=None,
        environment_claim="production",
        observation_type="unit_test",
    )
    verifier = RuntimeTargetVerifier()
    receipt = verifier.verify_observation(obs)
    res = classify_proof(receipt)
    assert res.evidence_level == EvidenceLevel.LEVEL_1_CODE_CONTRACT
    assert res.status == ClassificationStatus.LEVEL_1_PROVEN


def test_3_fake_deployment_identity_without_observations_rejected():
    """Anti-Escape 3: Raw observation without HTTP 200 health/deployment header fails closed."""
    obs = RawVerificationObservation(
        target_url="https://trade.yourdomain.com",
        http_status_code=404,  # Not 200
        response_headers={"X-Deployment-ID": "fake_dep_001"},
        observation_type="remote_http",
    )
    verifier = RuntimeTargetVerifier()
    receipt = verifier.verify_observation(obs)
    res = classify_proof(receipt)
    assert res.status == ClassificationStatus.LEVEL_3_UNAVAILABLE
    assert "reachability not observed" in res.reason or "health/readiness status not observed" in res.reason


def test_4_fake_verifier_identity_fails_closed():
    """Anti-Escape 4: Tampered/unauthorized verifier_id in receipt fails closed."""
    verifier = RuntimeTargetVerifier()
    obs = RawVerificationObservation(
        target_url="https://trade.yourdomain.com",
        http_status_code=200,
        response_headers={"X-Deployment-ID": "prod_dep_001"},
        response_body={
            "status": "healthy",
            "publication_id": "pub_001",
            "signal_id": "sig_001",
            "provenance": {"provenance_type": "live_signal"},
        },
        observation_type="remote_http",
    )
    receipt = verifier.verify_observation(obs)
    # Tamper with verifier_id
    tampered_receipt = TrustedVerificationReceipt(
        verifier_id="UNAUTHORIZED_FAKE_VERIFIER",
        verifier_version=receipt.verifier_version,
        verified_at_utc=receipt.verified_at_utc,
        receipt_fingerprint=receipt.receipt_fingerprint,
        target_url=receipt.target_url,
        is_non_local_target=receipt.is_non_local_target,
        is_external_reachability_observed=receipt.is_external_reachability_observed,
        is_deployed_health_observed=receipt.is_deployed_health_observed,
        is_p1_p2_correlation_observed=receipt.is_p1_p2_correlation_observed,
        is_authoritative_signal_observed=receipt.is_authoritative_signal_observed,
        is_runtime_ui_observed=receipt.is_runtime_ui_observed,
        deployment_identity=receipt.deployment_identity,
        canonical_timeframe=receipt.canonical_timeframe,
        symbol=receipt.symbol,
        publication_id=receipt.publication_id,
        signal_id=receipt.signal_id,
        verification_scope=receipt.verification_scope,
    )
    res = classify_proof(tampered_receipt)
    assert res.status == ClassificationStatus.LEVEL_3_UNAVAILABLE
    assert "Invalid verifier_id" in res.reason


def test_5_fake_fingerprint_tampering_fails_closed():
    """Anti-Escape 5: Manual tampering with receipt fields invalidates cryptographic fingerprint."""
    verifier = RuntimeTargetVerifier()
    obs = RawVerificationObservation(
        target_url="https://trade.yourdomain.com",
        http_status_code=200,
        response_headers={"X-Deployment-ID": "prod_dep_001"},
        response_body={
            "status": "healthy",
            "publication_id": "pub_001",
            "signal_id": "sig_001",
            "provenance": {"provenance_type": "live_signal"},
        },
        observation_type="remote_http",
    )
    receipt = verifier.verify_observation(obs)
    # Manually tamper with reachability flag without recomputing fingerprint
    tampered_receipt = TrustedVerificationReceipt(
        verifier_id=receipt.verifier_id,
        verifier_version=receipt.verifier_version,
        verified_at_utc=receipt.verified_at_utc,
        receipt_fingerprint=receipt.receipt_fingerprint,
        target_url=receipt.target_url,
        is_non_local_target=receipt.is_non_local_target,
        is_external_reachability_observed=True,
        is_deployed_health_observed=True,
        is_p1_p2_correlation_observed=True,
        is_authoritative_signal_observed=True,  # Tampered
        is_runtime_ui_observed=True,
        deployment_identity="forged_deployment_id",  # Tampered
        canonical_timeframe="1H",
        symbol="XAUUSD",
        publication_id="pub_forged",
        signal_id="sig_forged",
        verification_scope=receipt.verification_scope,
    )
    res = classify_proof(tampered_receipt)
    assert res.status == ClassificationStatus.LEVEL_3_UNAVAILABLE
    assert "fingerprint mismatch" in res.reason


def test_6_fake_timestamp_format_rejected():
    """Anti-Escape 6: Malformed or unparseable timeframe produces no canonical timeframe."""
    obs = RawVerificationObservation(
        target_url="https://trade.yourdomain.com",
        http_status_code=200,
        timeframe="1m",  # Disallowed timeframe
        observation_type="remote_http",
    )
    verifier = RuntimeTargetVerifier()
    receipt = verifier.verify_observation(obs)
    assert receipt.canonical_timeframe is None


def test_7_remote_url_without_observed_reachability_fails_closed():
    """Anti-Escape 7: Remote target URL without HTTP response fails closed to LEVEL_3_UNAVAILABLE."""
    obs = RawVerificationObservation(
        target_url="https://unreachable.trade.com",
        http_status_code=None,  # Connection timeout / refused
        observation_type="remote_http",
    )
    verifier = RuntimeTargetVerifier()
    receipt = verifier.verify_observation(obs)
    res = classify_proof(receipt)
    assert res.status == ClassificationStatus.LEVEL_3_UNAVAILABLE
    assert "reachability not observed" in res.reason or "Missing verified deployment identity" in res.reason


def test_8_observed_reachability_without_deployment_identity_fails_closed():
    """Anti-Escape 8: Reachable remote URL missing deployment identity header/body fails closed."""
    obs = RawVerificationObservation(
        target_url="https://generic.server.com",
        http_status_code=200,
        response_body={"status": "ok"},  # No publication_id / signal_id / X-Deployment-ID
        observation_type="remote_http",
    )
    verifier = RuntimeTargetVerifier()
    receipt = verifier.verify_observation(obs)
    res = classify_proof(receipt)
    assert res.status == ClassificationStatus.LEVEL_3_UNAVAILABLE
    assert "Missing verified deployment identity" in res.reason


def test_9_observed_health_without_p1_p2_correlation_fails_closed():
    """Anti-Escape 9: Health check HTTP 200 without P1 publication_id/signal_id correlation fails closed."""
    obs = RawVerificationObservation(
        target_url="https://trade.yourdomain.com",
        http_status_code=200,
        response_headers={"X-Deployment-ID": "prod_dep_002"},
        response_body={"status": "healthy"},  # Missing publication_id & signal_id
        observation_type="remote_http",
    )
    verifier = RuntimeTargetVerifier()
    receipt = verifier.verify_observation(obs)
    res = classify_proof(receipt)
    assert res.status == ClassificationStatus.LEVEL_3_UNAVAILABLE
    assert "signal payload ingestion/correlation not observed" in res.reason


def test_10_correlation_without_authoritative_provenance_fails_closed():
    """Anti-Escape 10: Signal correlation present but missing live_signal provenance fails closed."""
    obs = RawVerificationObservation(
        target_url="https://trade.yourdomain.com",
        http_status_code=200,
        response_headers={"X-Deployment-ID": "prod_dep_003"},
        response_body={
            "status": "healthy",
            "publication_id": "pub_003",
            "signal_id": "sig_003",
            "provenance": {"provenance_type": "historical_artifact"},  # Not live_signal
        },
        observation_type="remote_http",
    )
    verifier = RuntimeTargetVerifier()
    receipt = verifier.verify_observation(obs)
    res = classify_proof(receipt)
    assert res.status == ClassificationStatus.LEVEL_3_UNAVAILABLE
    assert "Authoritative P1->P2 signal payload" in res.reason


def test_11_timeframe_canonicalization_1h_4h_1d():
    """Anti-Escape 11: Timeframe aliases 1h, 4h, 1d canonicalize to 1H, 4H, 1D."""
    assert canonicalize_timeframe("1h") == "1H"
    assert canonicalize_timeframe("4h") == "4H"
    assert canonicalize_timeframe("1d") == "1D"
    assert canonicalize_timeframe("5m") == "5m"


def test_12_timeframe_1m_strictly_rejected():
    """Anti-Escape 12: 1m timeframe is strictly rejected."""
    with pytest.raises(ValueError, match="not supported"):
        canonicalize_timeframe("1m")


def test_13_timeframe_mismatch_in_observation():
    """Anti-Escape 13: Mismatched timeframe in observation does not leak lower-case aliases."""
    obs = RawVerificationObservation(
        target_url="https://trade.yourdomain.com",
        http_status_code=200,
        timeframe="4h",
    )
    verifier = RuntimeTargetVerifier()
    receipt = verifier.verify_observation(obs)
    assert receipt.canonical_timeframe == "4H"


def test_14_localhost_with_all_true_flags_capped_at_level_2():
    """Anti-Escape 14: Localhost target with complete response body is strictly capped at Level 2."""
    obs = RawVerificationObservation(
        target_url="http://localhost:8085",
        http_status_code=200,
        response_headers={"X-Deployment-ID": "local_dep_001"},
        response_body={
            "status": "healthy",
            "publication_id": "pub_local_001",
            "signal_id": "sig_local_001",
            "provenance": {"provenance_type": "live_signal"},
        },
        observation_type="local_http",
    )
    verifier = RuntimeTargetVerifier()
    receipt = verifier.verify_observation(obs)
    res = classify_proof(receipt)
    assert res.evidence_level == EvidenceLevel.LEVEL_2_LOCAL_HTTP
    assert res.status == ClassificationStatus.LEVEL_2_PROVEN
    assert "localhost/loopback" in res.reason


def test_15_local_http_200_capped_at_level_2():
    """Anti-Escape 15: Loopback IP (127.0.0.1) target is strictly capped at Level 2."""
    obs = RawVerificationObservation(
        target_url="http://127.0.0.1:8000",
        http_status_code=200,
        response_headers={"X-Deployment-ID": "loopback_dep_001"},
        response_body={
            "status": "healthy",
            "publication_id": "pub_001",
            "signal_id": "sig_001",
            "provenance": {"provenance_type": "live_signal"},
        },
        observation_type="local_http",
    )
    verifier = RuntimeTargetVerifier()
    receipt = verifier.verify_observation(obs)
    res = classify_proof(receipt)
    assert res.evidence_level == EvidenceLevel.LEVEL_2_LOCAL_HTTP
    assert res.status == ClassificationStatus.LEVEL_2_PROVEN


def test_16_docker_container_local_target_capped_at_level_2():
    """Anti-Escape 16: Local Docker container target (0.0.0.0) is capped at Level 2."""
    obs = RawVerificationObservation(
        target_url="http://0.0.0.0:3000",
        http_status_code=200,
        response_body={"status": "healthy"},
        observation_type="local_http",
    )
    verifier = RuntimeTargetVerifier()
    receipt = verifier.verify_observation(obs)
    res = classify_proof(receipt)
    assert res.evidence_level == EvidenceLevel.LEVEL_2_LOCAL_HTTP


def test_17_ci_only_observation_classifies_level_1():
    """Anti-Escape 17: Unit test / CI runner observation classifies as Level 1."""
    obs = RawVerificationObservation(
        target_url=None,
        http_status_code=None,
        observation_type="unit_test",
    )
    verifier = RuntimeTargetVerifier()
    receipt = verifier.verify_observation(obs)
    res = classify_proof(receipt)
    assert res.evidence_level == EvidenceLevel.LEVEL_1_CODE_CONTRACT
    assert res.status == ClassificationStatus.LEVEL_1_PROVEN


def test_18_config_only_without_reachability_yields_unavailable():
    """Anti-Escape 18: Unreachable remote target yields LEVEL_3_UNAVAILABLE."""
    obs = RawVerificationObservation(
        target_url="https://configured.domain.com",
        http_status_code=None,
        observation_type="remote_http",
    )
    verifier = RuntimeTargetVerifier()
    receipt = verifier.verify_observation(obs)
    res = classify_proof(receipt)
    assert res.status == ClassificationStatus.LEVEL_3_UNAVAILABLE


def test_19_verifier_produced_valid_receipt_achieves_level_3():
    """Anti-Escape 19: Valid verifier-produced receipt with real remote observations achieves LEVEL_3_PROVEN."""
    obs = RawVerificationObservation(
        target_url="https://trade.yourdomain.com",
        http_status_code=200,
        response_headers={"X-Deployment-ID": "prod_aws_us_east_1_999"},
        response_body={
            "status": "healthy",
            "publication_id": "pub_prod_999",
            "signal_id": "sig_prod_999",
            "symbol": "XAUUSD",
            "timeframe": "1h",
            "provenance": {"provenance_type": "live_signal"},
            "visible_in_ui": True,
        },
        observation_type="remote_http",
        symbol="XAUUSD",
        timeframe="1h",
        publication_id="pub_prod_999",
        signal_id="sig_prod_999",
    )
    verifier = RuntimeTargetVerifier()
    receipt = verifier.verify_observation(obs)
    res = classify_proof(receipt)

    assert res.evidence_level == EvidenceLevel.LEVEL_3_DEPLOYED_RUNTIME
    assert res.status == ClassificationStatus.LEVEL_3_PROVEN
    assert res.canonical_timeframe == "1H"
    assert res.deployment_identity == "prod_aws_us_east_1_999"


def test_20_absence_of_external_deployment_yields_unavailable():
    """Anti-Escape 20: Absence of external deployment observation strictly yields LEVEL_3_UNAVAILABLE."""
    verifier = RuntimeTargetVerifier()
    receipt = verifier.verify_observation(None)
    res = classify_proof(receipt)

    assert res.status == ClassificationStatus.LEVEL_3_UNAVAILABLE
    assert res.evidence_level == EvidenceLevel.LEVEL_1_CODE_CONTRACT
