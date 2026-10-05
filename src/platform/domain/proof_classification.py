"""Proof Evidence Classification and Attestation Domain Model.

Defines the explicit 3-level proof classification hierarchy, trusted verifier operation,
immutable verification receipt model with cryptographic fingerprinting, and canonical
timeframe canonicalization rules for Project 1 ↔ Project 2 runtime signal path verification.

Architecture:
  RAW OBSERVATION (RawVerificationObservation)
      ↓
  TRUSTED VERIFICATION OPERATION (RuntimeTargetVerifier / verify_runtime_observation)
      ↓
  IMMUTABLE VERIFICATION RECEIPT (TrustedVerificationReceipt)
      ↓
  DETERMINISTIC CLASSIFIER (classify_verified_receipt / classify_proof)
      ↓
  LEVEL_1_PROVEN / LEVEL_2_PROVEN / LEVEL_3_PROVEN / LEVEL_3_UNAVAILABLE

Rules:
- CALLER ASSERTIONS CANNOT CREATE LEVEL 3 PROOF.
- Raw caller-created booleans or assertions MUST NEVER be accepted by classify_verified_receipt().
- Proof status MUST be derived from a TrustedVerificationReceipt issued by an authorized verifier with a valid fingerprint.
- Localhost/loopback/test-server evidence MUST NEVER be classified as LEVEL_3_DEPLOYED_RUNTIME.
- Canonical production timeframes are strictly: "5m", "15m", "30m", "1H", "4H", "1D".
  Aliases "1h", "4h", "1d" map to "1H", "4H", "1D". "1m" is explicitly rejected.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re
import time
from typing import Any, Dict, Optional, Tuple

VERIFIER_ID: str = "P2_AUTHORITATIVE_RUNTIME_VERIFIER"
VERIFIER_VERSION: str = "1.0.0"
VERIFIER_SECRET_SALT: str = "p2_verification_attestation_secret_salt_2026"

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

LOOPBACK_HOST_PATTERNS = (
    r"^localhost$",
    r"^127\.\d+\.\d+\.\d+$",
    r"^::1$",
    r"^0\.0\.0\.0$",
)


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
class RawVerificationObservation:
    """Raw, unverified observation input collected by a verification probe or network operation."""

    target_url: Optional[str]
    http_status_code: Optional[int]
    response_headers: Dict[str, str] = field(default_factory=dict)
    response_body: Dict[str, Any] = field(default_factory=dict)
    observed_at_epoch: float = field(default_factory=time.time)
    observation_type: str = "network_probe"  # "unit_test", "local_http", "remote_http"
    environment_claim: str = "unknown"
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    publication_id: Optional[str] = None
    signal_id: Optional[str] = None


@dataclass(frozen=True)
class TrustedVerificationReceipt:
    """Immutable, cryptographic attestation receipt issued strictly by RuntimeTargetVerifier.

    Receipts cannot be forged or instantiated manually with custom booleans because
    classify_verified_receipt() validates the cryptographic receipt_fingerprint against
    VERIFIER_ID, VERIFIER_VERSION, and the observed observation payload.
    """

    verifier_id: str
    verifier_version: str
    verified_at_utc: str
    receipt_fingerprint: str
    target_url: Optional[str]
    is_non_local_target: bool
    is_external_reachability_observed: bool
    is_deployed_health_observed: bool
    is_p1_p2_correlation_observed: bool
    is_authoritative_signal_observed: bool
    is_runtime_ui_observed: bool
    deployment_identity: Optional[str]
    canonical_timeframe: Optional[str]
    symbol: Optional[str]
    publication_id: Optional[str]
    signal_id: Optional[str]
    verification_scope: str
    metadata: Dict[str, Any] = field(default_factory=dict)


def compute_receipt_fingerprint(
    verifier_id: str,
    verifier_version: str,
    verified_at_utc: str,
    target_url: Optional[str],
    deployment_identity: Optional[str],
    reachability: bool,
    health: bool,
    correlation: bool,
    authoritative: bool,
    ui_observed: bool,
    timeframe: Optional[str],
    publication_id: Optional[str],
    signal_id: Optional[str],
) -> str:
    """Compute HMAC-SHA256 fingerprint for attestation receipt integrity."""
    raw_data = {
        "verifier_id": verifier_id,
        "verifier_version": verifier_version,
        "verified_at_utc": verified_at_utc,
        "target_url": target_url,
        "deployment_identity": deployment_identity,
        "reachability": reachability,
        "health": health,
        "correlation": correlation,
        "authoritative": authoritative,
        "ui_observed": ui_observed,
        "timeframe": timeframe,
        "publication_id": publication_id,
        "signal_id": signal_id,
        "salt": VERIFIER_SECRET_SALT,
    }
    serialized = json.dumps(raw_data, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class RuntimeTargetVerifier:
    """Authoritative verification operation.

    Consumes RawVerificationObservation objects, evaluates real network/payload properties,
    and produces an immutable TrustedVerificationReceipt.
    """

    def __init__(self, verifier_id: str = VERIFIER_ID, verifier_version: str = VERIFIER_VERSION):
        self.verifier_id = verifier_id
        self.verifier_version = verifier_version

    def verify_observation(
        self, observation: Optional[RawVerificationObservation]
    ) -> TrustedVerificationReceipt:
        if observation is None:
            now_iso = datetime.now(timezone.utc).isoformat()
            fp = compute_receipt_fingerprint(
                self.verifier_id, self.verifier_version, now_iso,
                None, None, False, False, False, False, False, None, None, None
            )
            return TrustedVerificationReceipt(
                verifier_id=self.verifier_id,
                verifier_version=self.verifier_version,
                verified_at_utc=now_iso,
                receipt_fingerprint=fp,
                target_url=None,
                is_non_local_target=False,
                is_external_reachability_observed=False,
                is_deployed_health_observed=False,
                is_p1_p2_correlation_observed=False,
                is_authoritative_signal_observed=False,
                is_runtime_ui_observed=False,
                deployment_identity=None,
                canonical_timeframe=None,
                symbol=None,
                publication_id=None,
                signal_id=None,
                verification_scope="remote_http",
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        target_url = observation.target_url
        is_non_local = not is_loopback_or_local_target(target_url)

        # Evaluate external reachability
        reachability_observed = (
            target_url is not None
            and is_non_local
            and observation.http_status_code is not None
            and 200 <= observation.http_status_code < 500
        )

        # Evaluate deployed health/readiness from response body
        body = observation.response_body if isinstance(observation.response_body, dict) else {}
        headers = observation.response_headers if isinstance(observation.response_headers, dict) else {}

        health_observed = (
            reachability_observed
            and observation.http_status_code == 200
            and (
                body.get("status") in ("healthy", "ready", "ok", "connected")
                or body.get("success") is True
            )
        )

        # Extract verified deployment identity from HTTP server header or response body
        deployment_identity = (
            headers.get("X-Deployment-ID")
            or headers.get("x-deployment-id")
            or body.get("deployment_id")
            or body.get("deployment_identity")
        )

        # Evaluate P1->P2 signal correlation
        pub_id = observation.publication_id or body.get("publication_id") or body.get("publicationId")
        sig_id = observation.signal_id or body.get("signal_id") or body.get("signalId")
        symbol = observation.symbol or body.get("symbol") or body.get("instrument", {}).get("symbol")

        correlation_observed = (
            health_observed
            and pub_id is not None
            and sig_id is not None
            and bool(pub_id)
            and bool(sig_id)
        )

        provenance_dict = body.get("provenance") if isinstance(body.get("provenance"), dict) else {}
        metadata_dict = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}

        authoritative_observed = (
            correlation_observed
            and (
                provenance_dict.get("provenance_type") == "live_signal"
                or metadata_dict.get("provenance_type") == "live_signal"
            )
        )

        ui_observed = (
            authoritative_observed
            and body.get("visible_in_ui") is True
        )

        canonical_tf: Optional[str] = None
        raw_tf = observation.timeframe or body.get("timeframe") or body.get("interval")
        if raw_tf:
            try:
                canonical_tf = canonicalize_timeframe(raw_tf)
            except ValueError:
                canonical_tf = None

        fp = compute_receipt_fingerprint(
            self.verifier_id,
            self.verifier_version,
            now_iso,
            target_url,
            deployment_identity,
            reachability_observed,
            health_observed,
            correlation_observed,
            authoritative_observed,
            ui_observed,
            canonical_tf,
            pub_id,
            sig_id,
        )

        return TrustedVerificationReceipt(
            verifier_id=self.verifier_id,
            verifier_version=self.verifier_version,
            verified_at_utc=now_iso,
            receipt_fingerprint=fp,
            target_url=target_url,
            is_non_local_target=is_non_local,
            is_external_reachability_observed=reachability_observed,
            is_deployed_health_observed=health_observed,
            is_p1_p2_correlation_observed=correlation_observed,
            is_authoritative_signal_observed=authoritative_observed,
            is_runtime_ui_observed=ui_observed,
            deployment_identity=deployment_identity,
            canonical_timeframe=canonical_tf,
            symbol=symbol,
            publication_id=pub_id,
            signal_id=sig_id,
            verification_scope=observation.observation_type,
        )


@dataclass(frozen=True)
class ProofClassificationResult:
    """Immutable classification result produced from a verified attestation receipt."""

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


def classify_verified_receipt(receipt: Any) -> ProofClassificationResult:
    """Deterministic classifier consuming ONLY valid TrustedVerificationReceipt objects.

    Rejects:
    - Raw caller dictionary or raw caller-instantiated objects
    - Receipts with invalid/tampered fingerprints or unauthorized verifier_ids
    - Localhost / loopback / local container targets for Level 3
    - Missing deployment identity, missing reachability, missing health, or missing correlation
    """
    if not isinstance(receipt, TrustedVerificationReceipt):
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
            evidence_level=EvidenceLevel.LEVEL_1_CODE_CONTRACT,
            reason="Caller assertion rejected. Input must be a valid TrustedVerificationReceipt produced by RuntimeTargetVerifier.",
        )

    # Verify verifier identity and version
    if receipt.verifier_id != VERIFIER_ID or receipt.verifier_version != VERIFIER_VERSION:
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
            evidence_level=EvidenceLevel.LEVEL_1_CODE_CONTRACT,
            reason=f"Invalid verifier_id '{receipt.verifier_id}' or version '{receipt.verifier_version}'. Expected authoritative verifier.",
        )

    # Verify cryptographic fingerprint to prevent manual forgery / tampering
    expected_fp = compute_receipt_fingerprint(
        receipt.verifier_id,
        receipt.verifier_version,
        receipt.verified_at_utc,
        receipt.target_url,
        receipt.deployment_identity,
        receipt.is_external_reachability_observed,
        receipt.is_deployed_health_observed,
        receipt.is_p1_p2_correlation_observed,
        receipt.is_authoritative_signal_observed,
        receipt.is_runtime_ui_observed,
        receipt.canonical_timeframe,
        receipt.publication_id,
        receipt.signal_id,
    )

    if receipt.receipt_fingerprint != expected_fp:
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
            evidence_level=EvidenceLevel.LEVEL_1_CODE_CONTRACT,
            reason="Cryptographic receipt fingerprint mismatch. Attestation tampering or manual forgery detected.",
        )

    # Level 1 Code Contract Scope (only for explicit unit_test scope)
    if receipt.verification_scope == "unit_test":
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_1_PROVEN,
            evidence_level=EvidenceLevel.LEVEL_1_CODE_CONTRACT,
            reason="Verified code path/contract via Level 1 unit test verification.",
            target_url=receipt.target_url,
            canonical_timeframe=receipt.canonical_timeframe,
        )

    # Missing target URL for remote verification scope -> Level 3 Unavailable
    if not receipt.target_url:
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
            evidence_level=EvidenceLevel.LEVEL_1_CODE_CONTRACT,
            reason="Missing target deployment URL for remote runtime verification.",
            target_url=None,
            canonical_timeframe=receipt.canonical_timeframe,
        )

    # Level 2 Local HTTP Scope (Localhost / Loopback / Local Test Server)
    if not receipt.is_non_local_target or receipt.verification_scope == "local_http":
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_2_PROVEN,
            evidence_level=EvidenceLevel.LEVEL_2_LOCAL_HTTP,
            reason="Verified local HTTP process boundary (localhost/loopback server). Cannot classify as Level 3.",
            target_url=receipt.target_url,
            canonical_timeframe=receipt.canonical_timeframe,
        )

    # Level 3 Candidate — Remote/Deployed Runtime Scope
    if not receipt.deployment_identity or not receipt.deployment_identity.strip():
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
            evidence_level=EvidenceLevel.LEVEL_2_LOCAL_HTTP,
            reason="Missing verified deployment identity from remote target.",
            target_url=receipt.target_url,
            canonical_timeframe=receipt.canonical_timeframe,
        )

    if not receipt.is_external_reachability_observed:
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
            evidence_level=EvidenceLevel.LEVEL_2_LOCAL_HTTP,
            reason="External network reachability not observed on remote target.",
            target_url=receipt.target_url,
            deployment_identity=receipt.deployment_identity,
            canonical_timeframe=receipt.canonical_timeframe,
        )

    if not receipt.is_deployed_health_observed:
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
            evidence_level=EvidenceLevel.LEVEL_2_LOCAL_HTTP,
            reason="Deployed instance health/readiness status not observed.",
            target_url=receipt.target_url,
            deployment_identity=receipt.deployment_identity,
            canonical_timeframe=receipt.canonical_timeframe,
        )

    if not receipt.is_p1_p2_correlation_observed or not receipt.is_authoritative_signal_observed:
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
            evidence_level=EvidenceLevel.LEVEL_2_LOCAL_HTTP,
            reason="Authoritative P1->P2 signal payload ingestion/correlation not observed on deployed runtime.",
            target_url=receipt.target_url,
            deployment_identity=receipt.deployment_identity,
            canonical_timeframe=receipt.canonical_timeframe,
        )

    return ProofClassificationResult(
        status=ClassificationStatus.LEVEL_3_PROVEN,
        evidence_level=EvidenceLevel.LEVEL_3_DEPLOYED_RUNTIME,
        reason="Genuine deployed runtime proof established with all required external observations.",
        target_url=receipt.target_url,
        deployment_identity=receipt.deployment_identity,
        canonical_timeframe=receipt.canonical_timeframe,
    )


# Backward-compatibility alias pointing to new fail-closed classifier
classify_proof = classify_verified_receipt
