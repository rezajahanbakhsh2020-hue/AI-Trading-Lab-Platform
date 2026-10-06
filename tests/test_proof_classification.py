"""Adversarial Anti-Escape Test Suite for Proof Evidence Classification.

Verifies:
1. Raw caller objects / dicts fail closed to LEVEL_3_OUT_OF_SCOPE.
2. Localhost / 127.0.0.1 / ::1 / 0.0.0.0 targets classify as LEVEL_2_PROVEN.
3. Unit test scopes classify as LEVEL_1_PROVEN.
4. Remote target observations strictly return LEVEL_3_OUT_OF_SCOPE (no LEVEL_3_PROVEN possible).
5. Canonical production timeframe set ('5m', '15m', '30m', '1H', '4H', '1D') is enforced.
6. Timeframe aliases '1h', '4h', '1d' canonicalize to '1H', '4H', '1D'.
7. Disallowed timeframe '1m' is strictly rejected.
8. Anti-regression invariant: NO PATH OR MOCK CAN EVER PRODUCE LEVEL_3_PROVEN.
"""

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


def test_1_raw_caller_dict_fails_closed_to_out_of_scope():
    """Anti-Escape 1: Raw caller dicts fail closed to LEVEL_3_OUT_OF_SCOPE."""
    caller_dict = {
        "target_url": "https://trade.yourdomain.com",
        "is_external_reachability_observed": True,
        "is_deployed_health_observed": True,
    }
    res = classify_verified_receipt(caller_dict)
    assert res.status == ClassificationStatus.LEVEL_3_OUT_OF_SCOPE
    assert "Input must be a valid TrustedVerificationReceipt" in res.reason


def test_2_anti_regression_level_3_proven_is_impossible():
    """Anti-Regression Invariant: NO test, mock, or call can ever produce LEVEL_3_PROVEN."""
    def mock_prod_transport(url, headers, timeout):
        return 200, {"X-Deployment-ID": "prod_aws_us_east_1"}, {
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

    verifier = RuntimeTargetVerifier(
        expected_target_origin="https://trade.yourdomain.com",
        transport_fn=mock_prod_transport,
    )
    receipt = verifier.verify_runtime_target(
        target_url="https://trade.yourdomain.com",
        expected_deployment_identity="prod_aws_us_east_1",
        expected_timeframe="1h",
    )
    res = classify_proof(receipt)

    # Must be OUT_OF_SCOPE, NEVER LEVEL_3_PROVEN
    assert res.status == ClassificationStatus.LEVEL_3_OUT_OF_SCOPE
    assert res.status.value != "LEVEL_3_PROVEN"
    assert res.evidence_level != EvidenceLevel.LEVEL_3_DEPLOYED_RUNTIME


def test_3_local_http_process_boundary_classifies_as_level_2():
    """Level 2 Verification: Localhost HTTP server produces LEVEL_2_PROVEN."""
    def mock_local_transport(url, headers, timeout):
        return 200, {}, {
            "status": "healthy",
            "signal": {
                "publicationId": "pub_local_001",
                "signalId": "sig_local_001",
                "symbol": "XAUUSD",
                "timeframe": "1h",
            }
        }

    verifier = RuntimeTargetVerifier(transport_fn=mock_local_transport)
    receipt = verifier.verify_runtime_target(target_url="http://localhost:8085")
    res = classify_proof(receipt)

    assert res.evidence_level == EvidenceLevel.LEVEL_2_LOCAL_HTTP
    assert res.status == ClassificationStatus.LEVEL_2_PROVEN
    assert res.canonical_timeframe == "1H"


def test_4_loopback_ip_targets_classify_as_level_2():
    """Level 2 Verification: Loopback IPs (127.0.0.1, ::1, 0.0.0.0) classify as Level 2."""
    for loopback_url in (
        "http://127.0.0.1:8000",
        "http://[::1]:8085",
        "http://0.0.0.0:3000",
    ):
        assert is_loopback_or_local_target(loopback_url) is True

        verifier = RuntimeTargetVerifier(transport_fn=lambda url, h, t: (200, {}, {"status": "ok"}))
        receipt = verifier.verify_runtime_target(target_url=loopback_url)
        res = classify_proof(receipt)

        assert res.evidence_level == EvidenceLevel.LEVEL_2_LOCAL_HTTP
        assert res.status == ClassificationStatus.LEVEL_2_PROVEN


def test_5_unit_test_scope_classifies_as_level_1():
    """Level 1 Verification: Unit test verification scope produces LEVEL_1_PROVEN."""
    verifier = RuntimeTargetVerifier()
    receipt = verifier.verify_runtime_target(target_url=None)
    res = classify_proof(receipt)

    assert res.evidence_level == EvidenceLevel.LEVEL_1_CODE_CONTRACT
    assert res.status == ClassificationStatus.LEVEL_1_PROVEN


def test_6_timeframe_canonicalization_rules():
    """Timeframe Rules: Aliases 1h, 4h, 1d canonicalize to 1H, 4H, 1D."""
    assert canonicalize_timeframe("1h") == "1H"
    assert canonicalize_timeframe("4h") == "4H"
    assert canonicalize_timeframe("1d") == "1D"
    assert canonicalize_timeframe("5m") == "5m"
    assert canonicalize_timeframe("15m") == "15m"
    assert canonicalize_timeframe("30m") == "30m"


def test_7_timeframe_1m_strictly_rejected():
    """Timeframe Rules: 1m is strictly rejected."""
    with pytest.raises(ValueError, match="not supported"):
        canonicalize_timeframe("1m")


def test_8_invalid_verifier_id_fails_closed():
    """Safety: Receipt with invalid verifier_id fails closed to LEVEL_3_OUT_OF_SCOPE."""
    invalid_receipt = TrustedVerificationReceipt(
        verifier_id="FAKE_VERIFIER",
        verifier_version="1.0.0",
        verified_at_utc="2026-01-01T00:00:00Z",
        verified_at_epoch=1700000000.0,
        target_url="https://trade.yourdomain.com",
        is_non_local_target=True,
        is_external_reachability_observed=True,
        is_deployed_health_observed=True,
        is_p1_p2_correlation_observed=True,
        canonical_timeframe="1H",
        symbol="XAUUSD",
        publication_id="pub_1",
        signal_id="sig_1",
        verification_scope="remote_net",
    )
    res = classify_proof(invalid_receipt)
    assert res.status == ClassificationStatus.LEVEL_3_OUT_OF_SCOPE
    assert "Invalid verifier_id" in res.reason
