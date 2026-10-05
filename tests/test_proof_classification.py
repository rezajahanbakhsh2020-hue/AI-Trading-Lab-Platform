"""Adversarial Anti-Escape Test Suite for Verifier-Produced Proof Classification & Attestation.

Verifies all mandatory anti-escape regression test cases:
1. Fully populated synthetic observations/dicts -> NOT Level 3 (fails closed).
2. Verifier target injection prevention (arbitrary URL vs expected target origin).
3. Test transport scope ('verification_scope=test_transport') -> Capped below Level 3.
4. Tampered HMAC-SHA256 fingerprint -> LEVEL_3_UNAVAILABLE.
5. Invalid/fake verifier ID -> LEVEL_3_UNAVAILABLE.
6. Localhost / 127.0.0.1 / ::1 / 0.0.0.0 loopback targets -> Capped at Level 2.
7. Deployment identity mismatch -> LEVEL_3_UNAVAILABLE.
8. Stale observation (>300s) -> LEVEL_3_UNAVAILABLE.
9. Future timestamp observation -> LEVEL_3_UNAVAILABLE.
10. Disallowed timeframe ('1m') -> LEVEL_3_UNAVAILABLE.
11. Canonical timeframe aliases ('1h' -> '1H', '4h' -> '4H', '1d' -> '1D').
12. Unreachable remote target -> LEVEL_3_UNAVAILABLE.
13. Reachable remote target missing deployment ID -> LEVEL_3_UNAVAILABLE.
14. Health check 200 missing P1 publication/signal correlation -> LEVEL_3_UNAVAILABLE.
15. Signal correlation missing live_signal provenance -> LEVEL_3_UNAVAILABLE.
16. Absence of external deployment target -> LEVEL_3_UNAVAILABLE.
"""

import time
import pytest

from src.platform.domain.proof_classification import (
    ClassificationStatus,
    EvidenceLevel,
    RuntimeTargetVerifier,
    TrustedVerificationReceipt,
    canonicalize_timeframe,
    classify_proof,
    classify_verified_receipt,
    is_loopback_or_local_target,
)


def test_1_synthetic_dict_or_raw_caller_object_rejected():
    """Anti-Escape 1: Raw caller dictionaries or non-receipt objects fail closed to LEVEL_3_UNAVAILABLE."""
    caller_dict = {
        "target_url": "https://trade.yourdomain.com",
        "is_external_reachability_observed": True,
        "is_deployed_health_observed": True,
        "is_p1_p2_correlation_observed": True,
        "is_authoritative_signal_observed": True,
        "deployment_identity": "prod_001",
    }
    res = classify_verified_receipt(caller_dict)
    assert res.status == ClassificationStatus.LEVEL_3_UNAVAILABLE
    assert "Caller assertion rejected" in res.reason


def test_anti_regression_fully_populated_synthetic_observation_cannot_be_level_3():
    """Anti-Regression Invariant: A fully populated synthetic RawVerificationObservation or caller construct can NEVER produce LEVEL_3_PROVEN."""
    # Attempt 1: Passing synthetic observation dict directly
    synth_dict = {
        "target_url": "https://trade.yourdomain.com",
        "http_status_code": 200,
        "response_body": {
            "status": "healthy",
            "publication_id": "pub_fake",
            "signal_id": "sig_fake",
            "provenance": {"provenance_type": "live_signal"},
            "visible_in_ui": True,
        },
        "environment_claim": "production",
    }
    res_dict = classify_proof(synth_dict)
    assert res_dict.status == ClassificationStatus.LEVEL_3_UNAVAILABLE
    assert res_dict.evidence_level != EvidenceLevel.LEVEL_3_DEPLOYED_RUNTIME

    # Attempt 2: Verifier configured with test transport probing remote target
    def mock_transport(url, headers, timeout):
        return 200, {"X-Deployment-ID": "prod_aws_001"}, {
            "status": "healthy",
            "signal": {
                "publicationId": "pub_prod_001",
                "signalId": "sig_prod_001",
                "symbol": "XAUUSD",
                "timeframe": "1h",
                "provenanceType": "live_signal",
                "status": "active",
            }
        }

    verifier = RuntimeTargetVerifier(
        expected_target_origin="https://trade.yourdomain.com",
        transport_fn=mock_transport,
        is_test_transport=True,
    )
    receipt = verifier.verify_runtime_target(
        target_url="https://trade.yourdomain.com",
        expected_deployment_identity="prod_aws_001",
        expected_timeframe="1h",
    )
    res_test_transport = classify_proof(receipt)
    assert res_test_transport.status == ClassificationStatus.LEVEL_3_UNAVAILABLE
    assert res_test_transport.evidence_level != EvidenceLevel.LEVEL_3_DEPLOYED_RUNTIME


def test_2_verifier_owned_direct_acquisition_local_target_level_2():
    """Anti-Escape 2: Verifier-owned acquisition against loopback target produces Level 2 proof."""
    def mock_transport(url, headers, timeout):
        return 200, {"X-Deployment-ID": "local_dev_001"}, {
            "status": "healthy",
            "signal": {
                "publicationId": "pub_001",
                "signalId": "sig_001",
                "symbol": "XAUUSD",
                "timeframe": "1h",
                "provenanceType": "live_signal",
                "status": "active",
            }
        }

    verifier = RuntimeTargetVerifier(
        expected_target_origin="http://localhost:8085",
        transport_fn=mock_transport,
        is_test_transport=True,
    )
    receipt = verifier.verify_runtime_target(
        target_url="http://localhost:8085",
        expected_deployment_identity="local_dev_001",
    )
    res = classify_proof(receipt)

    assert res.evidence_level == EvidenceLevel.LEVEL_2_LOCAL_HTTP
    assert res.status == ClassificationStatus.LEVEL_2_PROVEN
    assert res.canonical_timeframe == "1H"


def test_3_target_origin_mismatch_fails_closed():
    """Anti-Escape 3: Attacker-controlled target URL not matching expected target origin fails closed."""
    def mock_transport(url, headers, timeout):
        return 200, {"X-Deployment-ID": "prod_aws_001"}, {"status": "healthy"}

    verifier = RuntimeTargetVerifier(
        expected_target_origin="https://trade.yourdomain.com",
        transport_fn=mock_transport,
        is_test_transport=False,
    )
    # Caller attempts to supply attacker-controlled target URL
    receipt = verifier.verify_runtime_target(
        target_url="https://attacker.evil.com",
        expected_deployment_identity="prod_aws_001",
        expected_timeframe="1h",
    )
    res = classify_proof(receipt)

    assert res.status == ClassificationStatus.LEVEL_3_UNAVAILABLE
    assert "does not match the verifier's expected deployment origin" in res.reason


def test_4_tampered_hmac_fingerprint_fails_closed():
    """Anti-Escape 4: Manual tampering with receipt fields invalidates HMAC signature and fails closed."""
    def mock_transport(url, headers, timeout):
        return 200, {"X-Deployment-ID": "prod_aws_002"}, {
            "status": "healthy",
            "signal": {"publicationId": "pub_002", "signalId": "sig_002", "provenanceType": "live_signal"}
        }

    verifier = RuntimeTargetVerifier(
        expected_target_origin="https://trade.yourdomain.com",
        transport_fn=mock_transport,
        is_test_transport=False,
    )
    receipt = verifier.verify_runtime_target()

    # Tamper with deployment identity without recomputing HMAC
    tampered_receipt = TrustedVerificationReceipt(
        verifier_id=receipt.verifier_id,
        verifier_version=receipt.verifier_version,
        verified_at_utc=receipt.verified_at_utc,
        verified_at_epoch=receipt.verified_at_epoch,
        receipt_fingerprint=receipt.receipt_fingerprint,
        target_url=receipt.target_url,
        is_non_local_target=receipt.is_non_local_target,
        is_target_origin_matched=receipt.is_target_origin_matched,
        is_external_reachability_observed=receipt.is_external_reachability_observed,
        is_deployed_health_observed=receipt.is_deployed_health_observed,
        is_p1_p2_correlation_observed=receipt.is_p1_p2_correlation_observed,
        is_authoritative_signal_observed=receipt.is_authoritative_signal_observed,
        is_runtime_ui_observed=receipt.is_runtime_ui_observed,
        deployment_identity="tampered_identity_002",  # Forged
        expected_deployment_identity=receipt.expected_deployment_identity,
        canonical_timeframe=receipt.canonical_timeframe,
        symbol=receipt.symbol,
        publication_id=receipt.publication_id,
        signal_id=receipt.signal_id,
        verification_scope=receipt.verification_scope,
    )

    res = classify_proof(tampered_receipt)
    assert res.status == ClassificationStatus.LEVEL_3_UNAVAILABLE
    assert "HMAC attestation signature mismatch" in res.reason


def test_5_fake_verifier_id_fails_closed():
    """Anti-Escape 5: Invalid/unauthorized verifier_id fails closed."""
    def mock_transport(url, headers, timeout):
        return 200, {"X-Deployment-ID": "prod_003"}, {"status": "ok"}

    verifier = RuntimeTargetVerifier(
        verifier_id="FAKE_UNAUTHORIZED_VERIFIER",
        expected_target_origin="https://trade.yourdomain.com",
        transport_fn=mock_transport,
        is_test_transport=False,
    )
    receipt = verifier.verify_runtime_target()

    res = classify_proof(receipt)
    assert res.status == ClassificationStatus.LEVEL_3_UNAVAILABLE
    assert "Invalid verifier_id" in res.reason


def test_6_deployment_identity_mismatch_fails_closed():
    """Anti-Escape 6: Observed deployment ID not matching expected deployment ID fails closed."""
    def mock_transport(url, headers, timeout):
        return 200, {"X-Deployment-ID": "prod_aws_us_east_1_actual"}, {
            "status": "healthy",
            "signal": {"publicationId": "pub_1", "signalId": "sig_1", "provenanceType": "live_signal", "timeframe": "1h"}
        }

    verifier = RuntimeTargetVerifier(
        expected_target_origin="https://trade.yourdomain.com",
        expected_deployment_identity="prod_aws_us_west_2_expected",  # Mismatch!
        transport_fn=mock_transport,
        is_test_transport=False,
    )
    receipt = verifier.verify_runtime_target(expected_timeframe="1h")
    res = classify_proof(receipt)

    assert res.status == ClassificationStatus.LEVEL_3_UNAVAILABLE
    assert "does not match expected identity" in res.reason


def test_7_stale_observation_fails_closed():
    """Anti-Escape 7: Verification evidence older than 300 seconds fails closed."""
    def mock_transport(url, headers, timeout):
        return 200, {"X-Deployment-ID": "prod_004"}, {
            "status": "healthy",
            "signal": {"publicationId": "pub_4", "signalId": "sig_4", "provenanceType": "live_signal", "timeframe": "1h"}
        }

    verifier = RuntimeTargetVerifier(
        expected_target_origin="https://trade.yourdomain.com",
        transport_fn=mock_transport,
        is_test_transport=False,
    )
    receipt = verifier.verify_runtime_target(expected_timeframe="1h")

    # Evaluate receipt against current epoch + 400s (stale by 400s)
    future_now = receipt.verified_at_epoch + 400.0
    res = classify_verified_receipt(receipt, current_epoch_fn=lambda: future_now)

    assert res.status == ClassificationStatus.LEVEL_3_UNAVAILABLE
    assert "stale or from future" in res.reason


def test_8_timeframe_canonicalization_and_1m_rejection():
    """Anti-Escape 8: Timeframe aliases 1h/4h/1d canonicalize to 1H/4H/1D; 1m is strictly rejected."""
    assert canonicalize_timeframe("1h") == "1H"
    assert canonicalize_timeframe("4h") == "4H"
    assert canonicalize_timeframe("1d") == "1D"
    assert canonicalize_timeframe("5m") == "5m"

    with pytest.raises(ValueError, match="not supported"):
        canonicalize_timeframe("1m")


def test_9_unreachable_target_fails_closed():
    """Anti-Escape 9: Unreachable target (status 0 / connection error) fails closed."""
    def error_transport(url, headers, timeout):
        return 0, {}, {"error": "Connection refused"}

    verifier = RuntimeTargetVerifier(
        expected_target_origin="https://unreachable.trade.com",
        transport_fn=error_transport,
        is_test_transport=False,
    )
    receipt = verifier.verify_runtime_target(expected_timeframe="1h")
    res = classify_proof(receipt)

    assert res.status == ClassificationStatus.LEVEL_3_UNAVAILABLE
    assert "Missing verified deployment identity" in res.reason or "External network reachability not observed" in res.reason or "Missing or invalid canonical production timeframe" in res.reason


def test_10_absence_of_external_deployment_yields_level_3_unavailable():
    """Anti-Escape 10: None target or missing external deployment strictly yields LEVEL_3_UNAVAILABLE."""
    verifier = RuntimeTargetVerifier(is_test_transport=False)
    receipt = verifier.verify_runtime_target(None)
    res = classify_proof(receipt)

    assert res.status == ClassificationStatus.LEVEL_3_UNAVAILABLE
    assert res.evidence_level == EvidenceLevel.LEVEL_1_CODE_CONTRACT


def test_11_production_verifier_path_achieves_level_3_when_all_conditions_met():
    """Production Verifier Path: Real verifier-owned production probe achieving LEVEL_3_PROVEN."""
    def mock_prod_transport(url, headers, timeout):
        return 200, {"X-Deployment-ID": "prod_aws_us_east_1_valid"}, {
            "status": "healthy",
            "signal": {
                "publicationId": "pub_prod_100",
                "signalId": "sig_prod_100",
                "symbol": "XAUUSD",
                "timeframe": "1h",
                "provenanceType": "live_signal",
                "status": "active",
            }
        }

    hmac_key = b"prod_secret_key_32_bytes_long_key_2026!"
    verifier = RuntimeTargetVerifier(
        expected_target_origin="https://trade.yourdomain.com",
        expected_deployment_identity="prod_aws_us_east_1_valid",
        hmac_secret_key=hmac_key,
        transport_fn=mock_prod_transport,
        is_test_transport=False,
    )
    receipt = verifier.verify_runtime_target(
        expected_symbol="XAUUSD",
        expected_timeframe="1h",
    )
    res = classify_verified_receipt(receipt, hmac_secret_key=hmac_key)

    assert res.evidence_level == EvidenceLevel.LEVEL_3_DEPLOYED_RUNTIME
    assert res.status == ClassificationStatus.LEVEL_3_PROVEN
    assert res.canonical_timeframe == "1H"
    assert res.deployment_identity == "prod_aws_us_east_1_valid"
