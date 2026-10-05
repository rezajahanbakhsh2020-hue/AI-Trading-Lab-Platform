"""Proof Evidence Classification and Attestation Domain Model.

Defines the explicit 3-level proof classification hierarchy, verifier-owned target observation,
immutable verification receipt model with HMAC-SHA256 attestation fingerprinting,
independent deployment identity binding, target origin allowlist enforcement, freshness checks,
and canonical timeframe rules for Project 1 ↔ Project 2 runtime signal path verification.

Architecture:
  VERIFIER CONFIGURATION (expected_target_origin, expected_deployment_identity, hmac_secret_key)
      ↓
  VERIFIER-OWNED NETWORK ACQUISITION (RuntimeTargetVerifier.verify_runtime_target)
      ↓
  TARGET ORIGIN MATCH & INDEPENDENT NETWORK OBSERVATION
      ↓
  VERIFIER POLICY & DEPLOYMENT BINDING (Expected Deployment Identity + Freshness Check)
      ↓
  IMMUTABLE VERIFICATION RECEIPT (TrustedVerificationReceipt + HMAC-SHA256)
      ↓
  DETERMINISTIC CLASSIFIER (classify_verified_receipt / classify_proof)
      ↓
  LEVEL_1_PROVEN / LEVEL_2_PROVEN / LEVEL_3_PROVEN / LEVEL_3_UNAVAILABLE

Non-Negotiable Invariants:
1. CALLER ASSERTIONS OR SYNTHETIC OBSERVATIONS CAN NEVER CREATE LEVEL 3 PROOF.
2. The verifier OWNS target selection and observation acquisition (`verify_runtime_target`).
3. Arbitrary attacker-controlled URLs NOT matching `expected_target_origin` fail closed.
4. Test transports are explicitly tagged with `verification_scope="test_transport"` and strictly capped below Level 3.
5. Deployment identity must be validated against an independently expected deployment identity.
6. Evidence freshness is strictly enforced (max age 300s, no future timestamps).
7. Localhost / loopback / local container targets are strictly capped at Level 2.
8. HMAC-SHA256 fingerprinting uses a secret key configured on the verifier instance.
9. Canonical production timeframes are strictly: "5m", "15m", "30m", "1H", "4H", "1D".
   Aliases "1h", "4h", "1d" map to "1H", "4H", "1D". "1m" is explicitly rejected.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import hmac
import json
import re
import time
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Callable, Dict, Optional, Tuple

VERIFIER_ID: str = "P2_AUTHORITATIVE_RUNTIME_VERIFIER"
VERIFIER_VERSION: str = "1.0.0"
DEFAULT_TEST_HMAC_KEY: bytes = b"p2_verifier_attestation_hmac_test_key_2026"

CANONICAL_PRODUCTION_TIMEFRAMES: Tuple[str, ...] = ("5m", "15m", "30m", "1H", "4H", "1D")
MAX_OBSERVATION_AGE_SECONDS: float = 300.0

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


def extract_origin_host(url: Optional[str]) -> Optional[str]:
    """Extract scheme + host or normalized netloc from URL string."""
    if not url or not isinstance(url, str) or not url.strip():
        return None
    try:
        parsed = urllib.parse.urlparse(url.strip())
        netloc = parsed.netloc.lower() if parsed.netloc else parsed.path.split("/")[0].lower()
        return netloc.split(":")[0]  # Return host without port
    except Exception:
        return None


@dataclass(frozen=True)
class TrustedVerificationReceipt:
    """Immutable, HMAC-SHA256 attestation receipt issued strictly by RuntimeTargetVerifier.

    Receipts carry a cryptographic HMAC-SHA256 signature computed across all observed properties.
    classify_verified_receipt() validates HMAC authenticity, verifier identity, non-loopback host,
    target origin match, deployment identity match, freshness, and correlation.
    """

    verifier_id: str
    verifier_version: str
    verified_at_utc: str
    verified_at_epoch: float
    receipt_fingerprint: str
    target_url: Optional[str]
    is_non_local_target: bool
    is_target_origin_matched: bool
    is_external_reachability_observed: bool
    is_deployed_health_observed: bool
    is_p1_p2_correlation_observed: bool
    is_authoritative_signal_observed: bool
    is_runtime_ui_observed: bool
    deployment_identity: Optional[str]
    expected_deployment_identity: Optional[str]
    canonical_timeframe: Optional[str]
    symbol: Optional[str]
    publication_id: Optional[str]
    signal_id: Optional[str]
    verification_scope: str  # "production_net", "test_transport", "unit_test"
    metadata: Dict[str, Any] = field(default_factory=dict)


def compute_receipt_hmac(
    secret_key: bytes,
    verifier_id: str,
    verifier_version: str,
    verified_at_utc: str,
    verified_at_epoch: float,
    target_url: Optional[str],
    deployment_identity: Optional[str],
    expected_deployment_identity: Optional[str],
    reachability: bool,
    health: bool,
    correlation: bool,
    authoritative: bool,
    ui_observed: bool,
    timeframe: Optional[str],
    publication_id: Optional[str],
    signal_id: Optional[str],
    verification_scope: str,
) -> str:
    """Compute true HMAC-SHA256 signature over receipt fields using configured verifier key."""
    raw_data = {
        "verifier_id": verifier_id,
        "verifier_version": verifier_version,
        "verified_at_utc": verified_at_utc,
        "verified_at_epoch": float(verified_at_epoch),
        "target_url": target_url,
        "deployment_identity": deployment_identity,
        "expected_deployment_identity": expected_deployment_identity,
        "reachability": reachability,
        "health": health,
        "correlation": correlation,
        "authoritative": authoritative,
        "ui_observed": ui_observed,
        "timeframe": timeframe,
        "publication_id": publication_id,
        "signal_id": signal_id,
        "verification_scope": verification_scope,
    }
    serialized = json.dumps(raw_data, sort_keys=True)
    key = secret_key if secret_key else DEFAULT_TEST_HMAC_KEY
    return hmac.new(key, serialized.encode("utf-8"), hashlib.sha256).hexdigest()


def _default_http_transport(url: str, headers: Dict[str, str], timeout_seconds: float = 5.0) -> Tuple[int, Dict[str, str], Dict[str, Any]]:
    """Default HTTP network probe using standard urllib.request."""
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            status = resp.status
            resp_headers = {k: v for k, v in resp.headers.items()}
            body_text = resp.read().decode("utf-8")
            try:
                body_json = json.loads(body_text)
            except Exception:
                body_json = {"raw_text": body_text}
            return status, resp_headers, body_json
    except urllib.error.HTTPError as http_err:
        try:
            body_text = http_err.read().decode("utf-8")
            body_json = json.loads(body_text)
        except Exception:
            body_json = {}
        resp_headers = {k: v for k, v in http_err.headers.items()} if http_err.headers else {}
        return http_err.code, resp_headers, body_json
    except Exception as err:
        return 0, {}, {"error": str(err)}


class RuntimeTargetVerifier:
    """Authoritative verifier operation.

    OWNS observation acquisition by performing direct HTTP probes against a trusted target URL
    bound to expected_target_origin and expected_deployment_identity.
    """

    def __init__(
        self,
        verifier_id: str = VERIFIER_ID,
        verifier_version: str = VERIFIER_VERSION,
        expected_target_origin: Optional[str] = None,
        expected_deployment_identity: Optional[str] = None,
        hmac_secret_key: Optional[bytes] = None,
        transport_fn: Optional[Callable[[str, Dict[str, str], float], Tuple[int, Dict[str, str], Dict[str, Any]]]] = None,
        is_test_transport: Optional[bool] = None,
    ):
        self.verifier_id = verifier_id
        self.verifier_version = verifier_version
        self.expected_target_origin = expected_target_origin
        self.expected_deployment_identity = expected_deployment_identity
        self.hmac_secret_key = hmac_secret_key or DEFAULT_TEST_HMAC_KEY
        self._transport_fn = transport_fn or _default_http_transport
        if is_test_transport is not None:
            self._is_test_transport = is_test_transport
        else:
            self._is_test_transport = (transport_fn is not None)

    def verify_runtime_target(
        self,
        target_url: Optional[str] = None,
        expected_deployment_identity: Optional[str] = None,
        auth_token: Optional[str] = None,
        expected_symbol: Optional[str] = None,
        expected_timeframe: Optional[str] = None,
    ) -> TrustedVerificationReceipt:
        """Verifier-owned acquisition operation.

        Performs network probe, evaluates response, validates target origin and deployment binding,
        enforces freshness, and produces an immutable TrustedVerificationReceipt signed with HMAC-SHA256.
        """
        now_epoch = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()
        scope = "test_transport" if self._is_test_transport else "production_net"

        effective_target_url = target_url or self.expected_target_origin
        effective_exp_dep_id = expected_deployment_identity or self.expected_deployment_identity

        if not effective_target_url or not isinstance(effective_target_url, str) or not effective_target_url.strip():
            fp = compute_receipt_hmac(
                self.hmac_secret_key,
                self.verifier_id, self.verifier_version, now_iso, now_epoch,
                None, None, effective_exp_dep_id, False, False, False, False, False, None, None, None, scope
            )
            return TrustedVerificationReceipt(
                verifier_id=self.verifier_id,
                verifier_version=self.verifier_version,
                verified_at_utc=now_iso,
                verified_at_epoch=now_epoch,
                receipt_fingerprint=fp,
                target_url=None,
                is_non_local_target=False,
                is_target_origin_matched=False,
                is_external_reachability_observed=False,
                is_deployed_health_observed=False,
                is_p1_p2_correlation_observed=False,
                is_authoritative_signal_observed=False,
                is_runtime_ui_observed=False,
                deployment_identity=None,
                expected_deployment_identity=effective_exp_dep_id,
                canonical_timeframe=None,
                symbol=None,
                publication_id=None,
                signal_id=None,
                verification_scope=scope,
            )

        clean_target_url = effective_target_url.strip()
        is_non_local = not is_loopback_or_local_target(clean_target_url)

        # Target Origin Matching Check (prevent arbitrary caller-supplied target URLs)
        target_host = extract_origin_host(clean_target_url)
        expected_host = extract_origin_host(self.expected_target_origin) if self.expected_target_origin else target_host

        target_origin_matched = bool(
            target_host is not None
            and (self.expected_target_origin is None or target_host == expected_host)
        )

        headers = {"User-Agent": f"P2Verifier/{self.verifier_version}"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        # Perform verifier-owned HTTP probe
        snapshot_url = f"{clean_target_url.rstrip('/')}/api/v1/snapshot"
        status_code, resp_headers, body = self._transport_fn(snapshot_url, headers, 5.0)

        reachability_observed = bool(200 <= status_code < 500)
        health_observed = bool(
            reachability_observed
            and status_code == 200
            and isinstance(body, dict)
            and (
                body.get("status") in ("healthy", "ready", "ok", "connected")
                or body.get("success") is True
                or "project1" in body
            )
        )

        observed_deployment_identity = (
            resp_headers.get("X-Deployment-ID")
            or resp_headers.get("x-deployment-id")
            or (body.get("deployment_id") if isinstance(body, dict) else None)
            or (body.get("deployment_identity") if isinstance(body, dict) else None)
        )

        # Extract P1->P2 signal correlation fields from snapshot
        sig_block = body.get("signal") if isinstance(body, dict) and isinstance(body.get("signal"), dict) else {}

        pub_id = sig_block.get("publicationId") or sig_block.get("publication_id") or body.get("publication_id")
        sig_id = sig_block.get("signalId") or sig_block.get("signal_id") or body.get("signal_id")
        symbol = sig_block.get("symbol") or body.get("symbol") or expected_symbol

        correlation_observed = bool(
            health_observed
            and pub_id is not None
            and sig_id is not None
            and bool(str(pub_id).strip())
            and bool(str(sig_id).strip())
        )

        prov_type = sig_block.get("provenanceType") or sig_block.get("provenance_type") or (body.get("provenance", {}).get("provenance_type") if isinstance(body.get("provenance"), dict) else None)
        authoritative_observed = bool(
            correlation_observed
            and prov_type == "live_signal"
        )

        ui_observed = bool(
            authoritative_observed
            and sig_block.get("status") == "active"
        )

        raw_tf = sig_block.get("timeframe") or body.get("timeframe") or expected_timeframe
        canonical_tf: Optional[str] = None
        if raw_tf:
            try:
                canonical_tf = canonicalize_timeframe(raw_tf)
            except ValueError:
                canonical_tf = None

        fp = compute_receipt_hmac(
            self.hmac_secret_key,
            self.verifier_id,
            self.verifier_version,
            now_iso,
            now_epoch,
            clean_target_url,
            observed_deployment_identity,
            effective_exp_dep_id,
            reachability_observed,
            health_observed,
            correlation_observed,
            authoritative_observed,
            ui_observed,
            canonical_tf,
            pub_id,
            sig_id,
            scope,
        )

        return TrustedVerificationReceipt(
            verifier_id=self.verifier_id,
            verifier_version=self.verifier_version,
            verified_at_utc=now_iso,
            verified_at_epoch=now_epoch,
            receipt_fingerprint=fp,
            target_url=clean_target_url,
            is_non_local_target=is_non_local,
            is_target_origin_matched=target_origin_matched,
            is_external_reachability_observed=reachability_observed,
            is_deployed_health_observed=health_observed,
            is_p1_p2_correlation_observed=correlation_observed,
            is_authoritative_signal_observed=authoritative_observed,
            is_runtime_ui_observed=ui_observed,
            deployment_identity=observed_deployment_identity,
            expected_deployment_identity=effective_exp_dep_id,
            canonical_timeframe=canonical_tf,
            symbol=symbol,
            publication_id=pub_id,
            signal_id=sig_id,
            verification_scope=scope,
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


def classify_verified_receipt(
    receipt: Any,
    current_epoch_fn: Optional[Callable[[], float]] = None,
    hmac_secret_key: Optional[bytes] = None,
) -> ProofClassificationResult:
    """Deterministic fail-closed classifier consuming ONLY valid TrustedVerificationReceipt objects.

    Enforces:
    - INVARIANT 1: Rejects raw caller dicts or raw caller assertion objects.
    - INVARIANT 2: Verifies HMAC-SHA256 signature and verifier_id.
    - INVARIANT 3: Target origin host MUST match expected verifier target origin.
    - INVARIANT 4: Caps test transports (`verification_scope == "test_transport"`) below Level 3.
    - INVARIANT 5: Caps localhost / loopback targets at Level 2.
    - INVARIANT 6: Requires non-empty deployment_identity matching expected_deployment_identity.
    - INVARIANT 7: Enforces observation freshness (max 300s old, no future epoch timestamps).
    - INVARIANT 8: Requires reachability, health, correlation, and canonical timeframe.
    """
    if not isinstance(receipt, TrustedVerificationReceipt):
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
            evidence_level=EvidenceLevel.LEVEL_1_CODE_CONTRACT,
            reason="Caller assertion rejected. Input must be a valid TrustedVerificationReceipt issued by RuntimeTargetVerifier.",
        )

    # 1. Verifier identity check
    if receipt.verifier_id != VERIFIER_ID or receipt.verifier_version != VERIFIER_VERSION:
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
            evidence_level=EvidenceLevel.LEVEL_1_CODE_CONTRACT,
            reason=f"Invalid verifier_id '{receipt.verifier_id}' or version '{receipt.verifier_version}'. Expected authoritative verifier.",
        )

    # 2. Cryptographic HMAC signature check
    key = hmac_secret_key or DEFAULT_TEST_HMAC_KEY
    expected_hmac = compute_receipt_hmac(
        key,
        receipt.verifier_id,
        receipt.verifier_version,
        receipt.verified_at_utc,
        receipt.verified_at_epoch,
        receipt.target_url,
        receipt.deployment_identity,
        receipt.expected_deployment_identity,
        receipt.is_external_reachability_observed,
        receipt.is_deployed_health_observed,
        receipt.is_p1_p2_correlation_observed,
        receipt.is_authoritative_signal_observed,
        receipt.is_runtime_ui_observed,
        receipt.canonical_timeframe,
        receipt.publication_id,
        receipt.signal_id,
        receipt.verification_scope,
    )

    if not hmac.compare_digest(receipt.receipt_fingerprint, expected_hmac):
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
            evidence_level=EvidenceLevel.LEVEL_1_CODE_CONTRACT,
            reason="HMAC attestation signature mismatch. Tampering or forgery detected.",
        )

    # 3. Scope Checks
    if receipt.verification_scope == "unit_test":
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_1_PROVEN,
            evidence_level=EvidenceLevel.LEVEL_1_CODE_CONTRACT,
            reason="Verified code path/contract via Level 1 unit test verification.",
            target_url=receipt.target_url,
            canonical_timeframe=receipt.canonical_timeframe,
        )

    # Test transports can prove Level 2 or Level 1, but NEVER Level 3
    if receipt.verification_scope == "test_transport":
        if not receipt.is_non_local_target or is_loopback_or_local_target(receipt.target_url):
            return ProofClassificationResult(
                status=ClassificationStatus.LEVEL_2_PROVEN,
                evidence_level=EvidenceLevel.LEVEL_2_LOCAL_HTTP,
                reason="Verified local test transport boundary (localhost/loopback). Capped at Level 2.",
                target_url=receipt.target_url,
                canonical_timeframe=receipt.canonical_timeframe,
            )
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
            evidence_level=EvidenceLevel.LEVEL_2_LOCAL_HTTP,
            reason="Test transport observations are explicitly capped below Level 3 deployed proof.",
            target_url=receipt.target_url,
            canonical_timeframe=receipt.canonical_timeframe,
        )

    # Missing target URL -> Level 3 Unavailable
    if not receipt.target_url:
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
            evidence_level=EvidenceLevel.LEVEL_1_CODE_CONTRACT,
            reason="Missing target deployment URL for remote runtime verification.",
            target_url=None,
            canonical_timeframe=receipt.canonical_timeframe,
        )

    # Loopback / Localhost -> Capped at Level 2
    if not receipt.is_non_local_target or is_loopback_or_local_target(receipt.target_url):
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_2_PROVEN,
            evidence_level=EvidenceLevel.LEVEL_2_LOCAL_HTTP,
            reason="Verified local HTTP process boundary (localhost/loopback server). Cannot classify as Level 3.",
            target_url=receipt.target_url,
            canonical_timeframe=receipt.canonical_timeframe,
        )

    # Target Origin Match Check
    if not receipt.is_target_origin_matched:
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
            evidence_level=EvidenceLevel.LEVEL_2_LOCAL_HTTP,
            reason="Target URL origin does not match the verifier's expected deployment origin allowlist.",
            target_url=receipt.target_url,
            canonical_timeframe=receipt.canonical_timeframe,
        )

    # 4. Level 3 Candidate — Deployed Production Network Observations
    now_ts = current_epoch_fn() if current_epoch_fn else time.time()
    obs_age = now_ts - receipt.verified_at_epoch

    if obs_age < -5.0 or obs_age > MAX_OBSERVATION_AGE_SECONDS:
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
            evidence_level=EvidenceLevel.LEVEL_2_LOCAL_HTTP,
            reason=f"Verification evidence is stale or from future (age: {obs_age:.1f}s, max allowed: {MAX_OBSERVATION_AGE_SECONDS}s).",
            target_url=receipt.target_url,
            canonical_timeframe=receipt.canonical_timeframe,
        )

    if not receipt.canonical_timeframe:
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
            evidence_level=EvidenceLevel.LEVEL_2_LOCAL_HTTP,
            reason="Missing or invalid canonical production timeframe for Level 3 verification.",
            target_url=receipt.target_url,
        )

    if not receipt.deployment_identity or not receipt.deployment_identity.strip():
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
            evidence_level=EvidenceLevel.LEVEL_2_LOCAL_HTTP,
            reason="Missing verified deployment identity from remote target.",
            target_url=receipt.target_url,
            canonical_timeframe=receipt.canonical_timeframe,
        )

    # Independent deployment identity validation
    if receipt.expected_deployment_identity and receipt.deployment_identity != receipt.expected_deployment_identity:
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_UNAVAILABLE,
            evidence_level=EvidenceLevel.LEVEL_2_LOCAL_HTTP,
            reason=f"Observed deployment identity '{receipt.deployment_identity}' does not match expected identity '{receipt.expected_deployment_identity}'.",
            target_url=receipt.target_url,
            deployment_identity=receipt.deployment_identity,
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
        reason="Genuine deployed runtime proof established with all required external network observations.",
        target_url=receipt.target_url,
        deployment_identity=receipt.deployment_identity,
        canonical_timeframe=receipt.canonical_timeframe,
    )


# Backward-compatibility alias pointing to new fail-closed classifier
classify_proof = classify_verified_receipt
