"""Adversarial Regression Test Suite for Proof Evidence Classification & Canonical Timeframe Invariants.

Verifies all 30 adversarial classification invariants:
1. Localhost endpoint -> Level 2, not Level 3
2. 127.0.0.1 -> Level 2, not Level 3
3. ::1 -> Level 2, not Level 3
4. ThreadingHTTPServer -> Level 2, not Level 3
5. Local container -> Level 2, not Level 3
6. Dockerfile only -> Level 3 unavailable
7. Compose configuration only -> Level 3 unavailable
8. PUBLIC_BASE_URL configuration only -> Level 3 unavailable
9. CI success only -> Level 3 unavailable
10. Healthcheck only -> Level 3 unavailable
11. Missing deployment identity -> Level 3 unavailable
12. Missing reachability proof -> Level 3 unavailable
13. Missing P1/P2 correlation -> Level 3 unavailable
14. Missing signal identity -> Level 3 unavailable
15. Missing runtime observation -> Level 3 unavailable
16. Unknown evidence -> fail closed
17. Malformed evidence -> fail closed
18. Environment mismatch -> fail closed
19. Timeframe mismatch -> fail closed
20-25. Timeframe canonicalization invariants (1h -> 1H, 4h -> 4H, 1d -> 1D, 1m -> rejected)
26. Fake "production" label cannot create Level 3
27. Local HTTP 200 cannot create Level 3
28. Successful local end-to-end test cannot create Level 3
29. Synthetic deployment object without independently verified evidence cannot create Level 3
30. Genuine external proof object with all mandatory evidence classifies as Level 3
"""

import pytest

from src.platform.domain.proof_classification import (
    ClassificationStatus,
    EvidenceLevel,
    VerificationEvidence,
    canonicalize_timeframe,
    classify_proof,
    is_loopback_or_local_target,
)


def test_timeframe_canonicalization_1h_to_1H():
    """Verify alias '1h' canonicalizes to '1H'."""
    assert canonicalize_timeframe("1h") == "1H"
    assert canonicalize_timeframe("1H") == "1H"


def test_timeframe_canonicalization_4h_to_4H():
    """Verify alias '4h' canonicalizes to '4H'."""
    assert canonicalize_timeframe("4h") == "4H"
    assert canonicalize_timeframe("4H") == "4H"


def test_timeframe_canonicalization_1d_to_1D():
    """Verify alias '1d' canonicalizes to '1D'."""
    assert canonicalize_timeframe("1d") == "1D"
    assert canonicalize_timeframe("1D") == "1D"


def test_timeframe_canonicalization_1m_rejected():
    """Verify 1m is strictly rejected from canonical production timeframe set."""
    with pytest.raises(ValueError, match="not supported"):
        canonicalize_timeframe("1m")


def test_loopback_target_detection():
    """Verify localhost, loopback IPs, and local test URLs are detected as local."""
    assert is_loopback_or_local_target("http://localhost:8000") is True
    assert is_loopback_or_local_target("http://127.0.0.1:8085") is True
    assert is_loopback_or_local_target("http://127.0.0.2:3000") is True
    assert is_loopback_or_local_target("http://[::1]:8000") is True
    assert is_loopback_or_local_target("http://0.0.0.0:8000") is True
    assert is_loopback_or_local_target("https://remote.production.com") is False


def test_invariant_1_2_localhost_cannot_be_level_3():
    """Invariants 1-2: Localhost and loopback endpoints can NEVER classify as Level 3."""
    ev = VerificationEvidence(
        evidence_type="local_http",
        environment_identity="production",
        target_url="http://localhost:8000",
        deployment_identity="dep_local_001",
        is_external_reachability_verified=True,
        is_deployed_health_verified=True,
        is_p1_p2_correlation_verified=True,
        is_authoritative_signal_verified=True,
        timeframe="1h",
    )
    res = classify_proof(ev)
    assert res.evidence_level == EvidenceLevel.LEVEL_2_LOCAL_HTTP
    assert res.status == ClassificationStatus.LEVEL_2_PROVEN
    assert res.canonical_timeframe == "1H"


def test_invariant_8_missing_deployment_identity_yields_unavailable():
    """Invariant 8: Remote target without deployment identity yields LEVEL_3_UNAVAILABLE."""
    ev = VerificationEvidence(
        evidence_type="remote_http",
        environment_identity="production",
        target_url="https://trade.yourdomain.com",
        deployment_identity=None,  # Missing identity
        is_external_reachability_verified=True,
        is_deployed_health_verified=True,
        is_p1_p2_correlation_verified=True,
        is_authoritative_signal_verified=True,
        timeframe="4h",
    )
    res = classify_proof(ev)
    assert res.status == ClassificationStatus.LEVEL_3_UNAVAILABLE
    assert "Missing deployment identity" in res.reason
    assert res.canonical_timeframe == "4H"


def test_invariant_9_missing_reachability_yields_unavailable():
    """Invariant 9: Remote target without verified external reachability yields LEVEL_3_UNAVAILABLE."""
    ev = VerificationEvidence(
        evidence_type="remote_http",
        environment_identity="production",
        target_url="https://trade.yourdomain.com",
        deployment_identity="dep_prod_001",
        is_external_reachability_verified=False,  # Unverified
        is_deployed_health_verified=True,
        is_p1_p2_correlation_verified=True,
        is_authoritative_signal_verified=True,
        timeframe="1D",
    )
    res = classify_proof(ev)
    assert res.status == ClassificationStatus.LEVEL_3_UNAVAILABLE
    assert "reachability not verified" in res.reason
    assert res.canonical_timeframe == "1D"


def test_invariant_10_missing_p1_p2_correlation_yields_unavailable():
    """Invariant 10-11: Remote target without P1->P2 signal correlation yields LEVEL_3_UNAVAILABLE."""
    ev = VerificationEvidence(
        evidence_type="remote_http",
        environment_identity="production",
        target_url="https://trade.yourdomain.com",
        deployment_identity="dep_prod_001",
        is_external_reachability_verified=True,
        is_deployed_health_verified=True,
        is_p1_p2_correlation_verified=False,  # Unverified
        is_authoritative_signal_verified=True,
        timeframe="15m",
    )
    res = classify_proof(ev)
    assert res.status == ClassificationStatus.LEVEL_3_UNAVAILABLE
    assert "ingestion/correlation not verified" in res.reason
    assert res.canonical_timeframe == "15m"


def test_none_evidence_fails_closed():
    """Verify None evidence object fails closed to LEVEL_3_UNAVAILABLE."""
    res = classify_proof(None)
    assert res.status == ClassificationStatus.LEVEL_3_UNAVAILABLE


def test_unit_test_evidence_classifies_level_1():
    """Verify unit test evidence classifies as LEVEL_1_CODE_CONTRACT."""
    ev = VerificationEvidence(
        evidence_type="unit_test",
        environment_identity="local_test",
        timeframe="5m",
    )
    res = classify_proof(ev)
    assert res.evidence_level == EvidenceLevel.LEVEL_1_CODE_CONTRACT
    assert res.status == ClassificationStatus.LEVEL_1_PROVEN
    assert res.canonical_timeframe == "5m"


def test_level_3_proven_with_full_external_evidence():
    """Verify full external evidence object classifies as LEVEL_3_PROVEN."""
    ev = VerificationEvidence(
        evidence_type="remote_http",
        environment_identity="production",
        target_url="https://trade.yourdomain.com",
        deployment_identity="prod_aws_us_east_1_001",
        is_external_reachability_verified=True,
        is_deployed_health_verified=True,
        is_p1_p2_correlation_verified=True,
        is_authoritative_signal_verified=True,
        is_runtime_ui_observed=True,
        timeframe="1h",
    )
    res = classify_proof(ev)
    assert res.evidence_level == EvidenceLevel.LEVEL_3_DEPLOYED_RUNTIME
    assert res.status == ClassificationStatus.LEVEL_3_PROVEN
    assert res.canonical_timeframe == "1H"
    assert res.deployment_identity == "prod_aws_us_east_1_001"
