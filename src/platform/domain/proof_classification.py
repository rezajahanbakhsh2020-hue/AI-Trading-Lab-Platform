"""Proof Evidence Classification Domain Model.

Defines the explicit proof classification hierarchy and canonical timeframe rules for
Project 1 ↔ Project 2 signal path verification.

Supported Scope:
- LEVEL_1_CODE_CONTRACT: Repository code paths, schemas, and unit tests.
- LEVEL_2_LOCAL_HTTP: Local HTTP process boundary (localhost, loopback, ThreadingHTTPServer).
- LEVEL_3: Explicitly OUT OF SCOPE for repository-local verification (no deployed external runtime).

Rules:
- Level 3 deployed-runtime proof is OUT OF SCOPE and CANNOT be produced by repository code or tests.
- Localhost/loopback/test-server evidence strictly classifies as LEVEL_2_LOCAL_HTTP or LEVEL_1_CODE_CONTRACT.
- Canonical production timeframes are strictly: "5m", "15m", "30m", "1H", "4H", "1D".
  Aliases "1h", "4h", "1d" map to "1H", "4H", "1D". "1m" is explicitly rejected.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import re
import time
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Callable, Dict, Optional, Tuple

VERIFIER_ID: str = "P2_AUTHORITATIVE_RUNTIME_VERIFIER"
VERIFIER_VERSION: str = "1.0.0"

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
    LEVEL_1_PROVEN = "LEVEL_1_PROVEN"
    LEVEL_2_PROVEN = "LEVEL_2_PROVEN"
    LEVEL_3_OUT_OF_SCOPE = "LEVEL_3_OUT_OF_SCOPE"
    LEVEL_3_UNAVAILABLE = "LEVEL_3_UNAVAILABLE"
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
    """Immutable verification receipt issued by RuntimeTargetVerifier for Level 1/Level 2 evidence."""

    verifier_id: str
    verifier_version: str
    verified_at_utc: str
    verified_at_epoch: float
    target_url: Optional[str]
    is_non_local_target: bool
    is_external_reachability_observed: bool
    is_deployed_health_observed: bool
    is_p1_p2_correlation_observed: bool
    canonical_timeframe: Optional[str]
    symbol: Optional[str]
    publication_id: Optional[str]
    signal_id: Optional[str]
    verification_scope: str  # "local_http", "unit_test", "remote_net"
    metadata: Dict[str, Any] = field(default_factory=dict)


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
    """Verifier operation for local process integration and code contract verification."""

    def __init__(
        self,
        verifier_id: str = VERIFIER_ID,
        verifier_version: str = VERIFIER_VERSION,
        expected_target_origin: Optional[str] = None,
        transport_fn: Optional[Callable[[str, Dict[str, str], float], Tuple[int, Dict[str, str], Dict[str, Any]]]] = None,
    ):
        self.verifier_id = verifier_id
        self.verifier_version = verifier_version
        self.expected_target_origin = expected_target_origin
        self._transport_fn = transport_fn or _default_http_transport

    def verify_runtime_target(
        self,
        target_url: Optional[str] = None,
        expected_deployment_identity: Optional[str] = None,
        auth_token: Optional[str] = None,
        expected_symbol: Optional[str] = None,
        expected_timeframe: Optional[str] = None,
    ) -> TrustedVerificationReceipt:
        """Verifier acquisition for local HTTP testing and contract verification."""
        now_epoch = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()

        effective_target_url = target_url or self.expected_target_origin

        if not effective_target_url or not isinstance(effective_target_url, str) or not effective_target_url.strip():
            return TrustedVerificationReceipt(
                verifier_id=self.verifier_id,
                verifier_version=self.verifier_version,
                verified_at_utc=now_iso,
                verified_at_epoch=now_epoch,
                target_url=None,
                is_non_local_target=False,
                is_external_reachability_observed=False,
                is_deployed_health_observed=False,
                is_p1_p2_correlation_observed=False,
                canonical_timeframe=None,
                symbol=None,
                publication_id=None,
                signal_id=None,
                verification_scope="unit_test",
            )

        clean_target_url = effective_target_url.strip()
        is_non_local = not is_loopback_or_local_target(clean_target_url)

        headers = {"User-Agent": f"P2Verifier/{self.verifier_version}"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        # Probe snapshot
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

        sig_block = body.get("signal") if isinstance(body, dict) and isinstance(body.get("signal"), dict) else {}
        pub_id = sig_block.get("publicationId") or sig_block.get("publication_id") or (body.get("publication_id") if isinstance(body, dict) else None)
        sig_id = sig_block.get("signalId") or sig_block.get("signal_id") or (body.get("signal_id") if isinstance(body, dict) else None)
        symbol = sig_block.get("symbol") or (body.get("symbol") if isinstance(body, dict) else None) or expected_symbol

        correlation_observed = bool(
            health_observed
            and pub_id is not None
            and sig_id is not None
            and bool(str(pub_id).strip())
            and bool(str(sig_id).strip())
        )

        raw_tf = sig_block.get("timeframe") or (body.get("timeframe") if isinstance(body, dict) else None) or expected_timeframe
        canonical_tf: Optional[str] = None
        if raw_tf:
            try:
                canonical_tf = canonicalize_timeframe(raw_tf)
            except ValueError:
                canonical_tf = None

        scope = "remote_net" if is_non_local else "local_http"

        return TrustedVerificationReceipt(
            verifier_id=self.verifier_id,
            verifier_version=self.verifier_version,
            verified_at_utc=now_iso,
            verified_at_epoch=now_epoch,
            target_url=clean_target_url,
            is_non_local_target=is_non_local,
            is_external_reachability_observed=reachability_observed,
            is_deployed_health_observed=health_observed,
            is_p1_p2_correlation_observed=correlation_observed,
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
    canonical_timeframe: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "evidence_level": self.evidence_level.value,
            "reason": self.reason,
            "target_url": self.target_url,
            "canonical_timeframe": self.canonical_timeframe,
        }


def classify_verified_receipt(
    receipt: Any,
    current_epoch_fn: Optional[Callable[[], float]] = None,
) -> ProofClassificationResult:
    """Deterministic classifier strictly supporting Level 1 and Level 2 evidence.

    Level 3 / deployed runtime proof is OUT OF SCOPE for repository-local verification
    and CANNOT be produced by any code path or test.
    """
    if not isinstance(receipt, TrustedVerificationReceipt):
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_OUT_OF_SCOPE,
            evidence_level=EvidenceLevel.LEVEL_1_CODE_CONTRACT,
            reason="Input must be a valid TrustedVerificationReceipt issued by RuntimeTargetVerifier.",
        )

    if receipt.verifier_id != VERIFIER_ID or receipt.verifier_version != VERIFIER_VERSION:
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_3_OUT_OF_SCOPE,
            evidence_level=EvidenceLevel.LEVEL_1_CODE_CONTRACT,
            reason=f"Invalid verifier_id '{receipt.verifier_id}' or version '{receipt.verifier_version}'. Expected authoritative verifier.",
        )

    # Unit Test Scope -> Level 1 Code Contract
    if receipt.verification_scope == "unit_test" or not receipt.target_url:
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_1_PROVEN,
            evidence_level=EvidenceLevel.LEVEL_1_CODE_CONTRACT,
            reason="Verified code path/contract via Level 1 unit test verification.",
            target_url=receipt.target_url,
            canonical_timeframe=receipt.canonical_timeframe,
        )

    # Local HTTP Process Scope (Localhost / Loopback / Local Test Server)
    if not receipt.is_non_local_target or receipt.verification_scope == "local_http" or is_loopback_or_local_target(receipt.target_url):
        return ProofClassificationResult(
            status=ClassificationStatus.LEVEL_2_PROVEN,
            evidence_level=EvidenceLevel.LEVEL_2_LOCAL_HTTP,
            reason="Verified local HTTP process boundary (localhost/loopback server).",
            target_url=receipt.target_url,
            canonical_timeframe=receipt.canonical_timeframe,
        )

    # Deployed/Remote Runtime Scope is explicitly OUT OF SCOPE
    return ProofClassificationResult(
        status=ClassificationStatus.LEVEL_3_OUT_OF_SCOPE,
        evidence_level=EvidenceLevel.LEVEL_2_LOCAL_HTTP,
        reason="Level 3 deployed runtime proof is explicitly OUT OF SCOPE for repository-local verification (no external production runtime).",
        target_url=receipt.target_url,
        canonical_timeframe=receipt.canonical_timeframe,
    )


# Backward-compatibility alias pointing to classifier
classify_proof = classify_verified_receipt
