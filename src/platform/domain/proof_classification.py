"""Proof Evidence Classification and Verification Domain Model.

Defines the explicit 3-level proof classification hierarchy and canonical timeframe
canonicalization rules for Project 1 ↔ Project 2 runtime signal path verification.

Proof Classification Levels:
1. LEVEL_1_CODE_CONTRACT: Repository code path, contract schemas, unit/domain tests.
2. LEVEL_2_LOCAL_HTTP: Local HTTP process boundary (localhost, loopback, ThreadingHTTPServer, local containers).
3. LEVEL_3_DEPLOYED_RUNTIME: Actual remote public deployed runtime verified against external deployment target.

Rules:
- Localhost/loopback/test-server evidence MUST NEVER be classified as LEVEL_3_DEPLOYED_RUNTIME.
- Missing deployment identity, missing external reachability, or missing correlation MUST result in LEVEL_3_UNAVAILABLE.
- Canonical production timeframes are strictly: "5m", "15m", "30m", "1H", "4H", "1D".
  Aliases "1h", "4h", "1d" map to "1H", "4H", "1D". "1m" is explicitly rejected.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
import re
from typing import Any, Dict, Optional, Tuple

CANONICAL_PRODUCTION_TIMEFRAMES: Tuple[str, ...] = ("5m", "15m", "30m", "1H", "4H", "1D")

TIMEFRAME_ALIAS_MAP: Dict[str, str] = {
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1H",
    "1H": "1H",
    "4h": "4H",
    "4H": "4H",
    "1d": "1D",
    "1D": "1D",
}


def canonicalize_timeframe(raw_tf: Any) -> str:
    """Canonicalize a raw timeframe string into the canonical production timeframe set.

    Canonical set: ("5m", "15m", "30m", "1H", "4H", "1D")
    - "1h" -> "1H"
    - "4h" -> "4H"
    - "1d" -> "1D"
    - "1m" -> Raises ValueError (not in canonical production timeframe set)
    """
    if not isinstance(raw_tf, str) or not raw_tf.strip():
        raise ValueError("Timeframe must be a non-empty string.")

    tf_str = raw_tf.strip()

    # Check map
    if tf_str in TIMEFRAME_ALIAS_MAP:
        return TIMEFRAME_ALIAS_MAP[tf_str]

    tf_lower = tf_str.lower()
    if tf_lower in TIMEFRAME_ALIAS_MAP:
        return TIMEFRAME_ALIAS_MAP[tf_lower]

    raise ValueError(
        f"Timeframe '{raw_tf}' is not supported. Allowed canonical timeframes: {CANONICAL_PRODUCTION_TIMEFRAMES}"
    )


class EvidenceLevel(Enum):
    LEVEL_1_CODE_CONTRACT = "LEVEL_1_CODE_CONTRACT"
    LEVEL_2_LOCAL_HTTP = "LEVEL_2_LOCAL_HTTP"
    LEVEL_3_DEPLOYED_RUNTIME = "LEVEL_3_DEPLOYED_RUNTIME"


class ClassificationStatus(Enum):
    LEVEL_3_PROVEN = "LEVEL_3_PROVEN"
    LEVEL_3_UNAVAILABLE = "LEVEL_3_UNAVAILABLE"
    LEVEL_2_PROVEN = "LEVEL_2_PROVEN"
    LEVEL_1_PROVEN = "LEVEL_1_PROVEN"
    BLOCKED_BY_DEFECT = "BLOCKED_BY_DEFECT"


LOOPBACK_HOST_PATTERNS = (
    r"^localhost$",
    r"^127\.\d+\.\d+\.\d+$",
    r"^::1$",
    r"^0\.0\.0\.0$",
)


def is_loopback_or_local_target(target_url_or_host: Optional[str]) -> bool:
    """Check if a target URL or hostname represents loopback/localhost/local test server."""
    if not target_url_or_host or not isinstance(target_url_or_host, str):
        return True

    target_clean = target_url_or_host.strip().lower()

    # Strip scheme
    if "://" in target_clean:
        target_clean = target_clean.split("://", 1)[1]

    # Strip path
    host_part = target_clean.split("/", 1)[0]

    # Handle IPv6 brackets e.g. [::1]:8000
    if host_part.startswith("["):
        bracket_end = host_part.find("]")
        if bracket_end != -1:
            host_part = host_part[1:bracket_end]
    else:
        # Strip port for IPv4 / domain
        host_part = host_part.split(":", 1)[0]

    for pat in LOOPBACK_HOST_PATTERNS:
        if re.match(pat, host_part):
            return True

    return False


@dataclass(frozen=True)
class VerificationEvidence:
    """Container for proof evidence collected during P1 -> P2 signal path testing."""

    evidence_type: str  # e.g., "unit_test", "local_http", "remote_http"
    environment_identity: str  # e.g., "local_test", "staging", "production"
    target_url: Optional[str] = None
    deployment_identity: Optional[str] = None
    is_external_reachability_verified: bool = False
    is_deployed_health_verified: bool = False
    is_p1_p2_correlation_verified: bool = False
    is_authoritative_signal_verified: bool = False
    is_runtime_ui_observed: bool = False
    timestamp: Optional[float] = None
    timeframe: Optional[str] = None
    signal_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProofClassificationResult:
    """Immutable classification result for proof evidence."""

    status: ClassificationStatus
    evidence_level: EvidenceLevel
    reason: str
    target_url: Optional[str] = None
    deployment_identity: Optional[str] = None
    canonical_timeframe: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "evidence_level": self.evidence_level.value,
            "reason": self.reason,
            "target_url": self.target_url,
            "deployment_identity": self.deployment_identity,
            "canonical_timeframe": self.canonical_timeframe,
        }


def classify_proof(evidence: Optional[VerificationEvidence]) -> ProofClassificationResult:
    """Classify verification evidence into Level 1, Level 2, or Level 3 fail-closed.

    Enforces:
    - INVARIANT 1-2: Localhost / loopback / local test server -> LEVEL_2_LOCAL_HTTP or LEVEL_1_CODE_CONTRACT. Never LEVEL_3.
    - INVARIANT 8: Missing deployment identity -> LEVEL_3_UNAVAILABLE.
    - INVARIANT 9: Missing actual external reachability -> LEVEL_3_UNAVAILABLE.
    - INVARIANT 10: Missing actual external P1->P2 boundary evidence -> LEVEL_3_UNAVAILABLE.
    - INVARIANT 11: Missing authoritative signal correlation -> LEVEL_3_UNAVAILABLE.
    """
    if evidence is None:
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
            evidence_level=EvidenceLevel.LEVEL_1_CODE_CONTRACT,
            reason="Missing verification evidence object.",
        )

    # Canonicalize timeframe if present
    canonical_tf: Optional[str] = None
    if evidence.timeframe:
        try:
            canonical_tf = canonicalize_timeframe(evidence.timeframe)
        except ValueError as err:
            return ProofClassificationResult(
                status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
                evidence_level=EvidenceLevel.LEVEL_1_CODE_CONTRACT,
                reason=f"Invalid evidence timeframe: {str(err)}",
            )

    # Check target host
    target_is_local = is_loopback_or_local_target(evidence.target_url)

    # Unit test / code contract proof check
    if evidence.evidence_type == "unit_test" or not evidence.target_url:
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_1_PROVEN,
            evidence_level=EvidenceLevel.LEVEL_1_CODE_CONTRACT,
            reason="Verified code path/contract via Level 1 code contract test.",
            target_url=evidence.target_url,
            canonical_timeframe=canonical_tf,
        )

    # Local HTTP proof check
    if target_is_local or evidence.evidence_type == "local_http" or evidence.environment_identity in ("local", "testing", "localhost"):
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_2_PROVEN,
            evidence_level=EvidenceLevel.LEVEL_2_LOCAL_HTTP,
            reason="Verified local HTTP boundary (localhost/loopback server). Cannot classify as Level 3.",
            target_url=evidence.target_url,
            canonical_timeframe=canonical_tf,
        )

    # Level 3 Candidate — Remote/Deployed Target Verification
    if not evidence.deployment_identity or not evidence.deployment_identity.strip():
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
            evidence_level=EvidenceLevel.LEVEL_2_LOCAL_HTTP,
            reason="Missing deployment identity for remote target.",
            target_url=evidence.target_url,
            canonical_timeframe=canonical_tf,
        )

    if not evidence.is_external_reachability_verified:
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
            evidence_level=EvidenceLevel.LEVEL_2_LOCAL_HTTP,
            reason="External network reachability not verified for remote target.",
            target_url=evidence.target_url,
            deployment_identity=evidence.deployment_identity,
            canonical_timeframe=canonical_tf,
        )

    if not evidence.is_deployed_health_verified:
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
            evidence_level=EvidenceLevel.LEVEL_2_LOCAL_HTTP,
            reason="Deployed instance health/readiness not verified.",
            target_url=evidence.target_url,
            deployment_identity=evidence.deployment_identity,
            canonical_timeframe=canonical_tf,
        )

    if not evidence.is_p1_p2_correlation_verified or not evidence.is_authoritative_signal_verified:
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
            evidence_level=EvidenceLevel.LEVEL_2_LOCAL_HTTP,
            reason="Authoritative P1->P2 signal payload ingestion/correlation not verified on deployed runtime.",
            target_url=evidence.target_url,
            deployment_identity=evidence.deployment_identity,
            canonical_timeframe=canonical_tf,
        )

    return ProofClassificationResult(
        status=ClassificationStatus.LEVEL_3_PROVEN,
        evidence_level=EvidenceLevel.LEVEL_3_DEPLOYED_RUNTIME,
        reason="Genuine deployed runtime proof established with all required external evidence.",
        target_url=evidence.target_url,
        deployment_identity=evidence.deployment_identity,
        canonical_timeframe=canonical_tf,
    )
