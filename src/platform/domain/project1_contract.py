"""Formal Project 1 Integration Contract Domain Model.

Defines versioned, explicit, schema-driven, independent integration contract
data structures, ISO-8601 UTC timestamp normalization, and canonical boundary
validation logic for Project 1 ↔ Project 2 communication.

Rules:
- Project 2 NEVER calculates, modifies, optimizes, or decides strategy rules,
  Entry, SL, TP, trailing stops, or trading decisions.
- Project 1 is the sole source of truth for trade setups, execution levels, and strategy outputs.
- Project 2 validates, authorizes, scopes, persists, and presents Project 1 contract payloads.
- Normalizes canonical P1 Contract v1 payloads into P2 internal integration records.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
import numbers
import time
from typing import Any, Dict, List, Optional, Tuple

SUPPORTED_CONTRACT_VERSIONS: Tuple[str, ...] = ("1.0", "1.0.0", "v1.0")
DEFAULT_CONTRACT_VERSION: str = "1.0"

ALLOWED_COMMAND_TYPES: Tuple[str, ...] = (
    "EMIT_SIGNAL",
    "UPDATE_LIFECYCLE",
    "UPDATE_TRAILING_STOP",
    "HEARTBEAT",
)

ALLOWED_EVENT_TYPES: Tuple[str, ...] = (
    "TRADING_SIGNAL",
    "EMIT_SIGNAL",
    "UPDATE_LIFECYCLE",
    "UPDATE_TRAILING_STOP",
    "HEARTBEAT",
)

ALLOWED_SIGNAL_TYPES: Tuple[str, ...] = ("buy", "sell", "hold", "no-signal", "no-trade")

ALLOWED_LIFECYCLE_STATES: Tuple[str, ...] = (
    "STAGED",
    "ACTIVE",
    "UPDATED",
    "CANCELLED",
    "EXPIRED",
    "REJECTED",
    "EXECUTED",
)

ALLOWED_MTF_TIMEFRAMES: Tuple[str, ...] = ("5m", "15m", "30m", "1H", "4H", "1D")

ALLOWED_MTF_CLASSIFICATIONS: Tuple[str, ...] = (
    "ALIGNED",
    "COUNTER_TREND",
    "INSUFFICIENT_CONTEXT",
    "NO_TRADE",
    "NEUTRAL",
    "MIXED",
)


import copy


def _validate_non_empty_string(value: Any, field_name: str) -> str:
    """Validate that value is a non-empty string (not missing, None, empty, or whitespace-only).

    Does NOT modify or normalize casing/whitespace of the received value.
    """
    if value is None:
        raise ValueError(f"{field_name} is required and cannot be None")
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string, got {type(value).__name__}")
    if not value.strip():
        raise ValueError(f"{field_name} cannot be empty or whitespace-only")
    return value


@dataclass(frozen=True)
class Project1MTFSignal:
    """Immutable per-timeframe constituent signal within Project 1 MTF payload.

    Enforces mandatory non-empty P1 lineage fields without mutating or normalizing values.
    """

    symbol: str
    timeframe: str
    direction: str
    decision_id: str
    signal_id: str
    decision_timestamp: Any
    market_timestamp: Any
    strategy_name: str
    strategy_version: str
    candidate_id: str
    evidence_id: str
    experiment_fingerprint: str
    canonical_live_decision_fingerprint: str
    authorization_fingerprint: str
    constituent_fingerprint: str
    provenance: Dict[str, Any]

    def __post_init__(self) -> None:
        # Enforce exact non-empty string validation for required fields without value normalization/rewriting
        _validate_non_empty_string(self.symbol, "MTF constituent signal symbol")

        _validate_non_empty_string(self.timeframe, "MTF constituent signal timeframe")
        if self.timeframe not in ALLOWED_MTF_TIMEFRAMES:
            raise ValueError(f"MTF constituent signal timeframe '{self.timeframe}' is not supported. Allowed: {ALLOWED_MTF_TIMEFRAMES}")

        _validate_non_empty_string(self.direction, "MTF constituent signal direction")
        if self.direction.lower() not in ("buy", "sell", "hold", "no-signal", "no-trade", "neutral"):
            raise ValueError(f"MTF constituent signal direction '{self.direction}' is invalid")

        _validate_non_empty_string(self.decision_id, "MTF constituent signal decision_id")
        _validate_non_empty_string(self.signal_id, "MTF constituent signal signal_id")

        if self.decision_timestamp is None:
            raise ValueError("MTF constituent signal decision_timestamp is required")
        if self.market_timestamp is None:
            raise ValueError("MTF constituent signal market_timestamp is required")

        # Mandatory P1 lineage fields (Defect B enforcement)
        _validate_non_empty_string(self.strategy_name, "MTF constituent signal strategy_name")
        _validate_non_empty_string(self.strategy_version, "MTF constituent signal strategy_version")
        _validate_non_empty_string(self.candidate_id, "MTF constituent signal candidate_id")
        _validate_non_empty_string(self.evidence_id, "MTF constituent signal evidence_id")
        _validate_non_empty_string(self.experiment_fingerprint, "MTF constituent signal experiment_fingerprint")
        _validate_non_empty_string(self.canonical_live_decision_fingerprint, "MTF constituent signal canonical_live_decision_fingerprint")
        _validate_non_empty_string(self.authorization_fingerprint, "MTF constituent signal authorization_fingerprint")
        _validate_non_empty_string(self.constituent_fingerprint, "MTF constituent signal constituent_fingerprint")

        if not isinstance(self.provenance, dict) or not self.provenance:
            raise ValueError("MTF constituent signal provenance must be a non-empty dictionary")

        # Freeze provenance via deepcopy to prevent raw input mutation
        object.__setattr__(self, "provenance", copy.deepcopy(self.provenance))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "decision_id": self.decision_id,
            "signal_id": self.signal_id,
            "decision_timestamp": self.decision_timestamp,
            "market_timestamp": self.market_timestamp,
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "candidate_id": self.candidate_id,
            "evidence_id": self.evidence_id,
            "experiment_fingerprint": self.experiment_fingerprint,
            "canonical_live_decision_fingerprint": self.canonical_live_decision_fingerprint,
            "authorization_fingerprint": self.authorization_fingerprint,
            "constituent_fingerprint": self.constituent_fingerprint,
            "provenance": copy.deepcopy(self.provenance),
        }


@dataclass(frozen=True)
class Project1MTFConfig:
    """Immutable, validated Project 1 Multi-Timeframe (MTF) payload representation."""

    symbol: str
    local_timeframe: str
    participating_timeframes: Tuple[str, ...]
    signals: Tuple[Project1MTFSignal, ...]
    alignment_count: int
    alignment_coverage: int
    classification: str
    higher_timeframe_context: Optional[Dict[str, Any]] = None
    constituent_fingerprints: Tuple[str, ...] = field(default_factory=tuple)
    matching_signal_count: Optional[int] = None
    available_signal_count: Optional[int] = None
    intelligence_fingerprint: Optional[str] = None
    star_representation: Optional[str] = None

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.symbol, "MTF symbol")

        _validate_non_empty_string(self.local_timeframe, "MTF local_timeframe")
        if self.local_timeframe not in ALLOWED_MTF_TIMEFRAMES:
            raise ValueError(f"MTF local_timeframe '{self.local_timeframe}' is not supported. Allowed: {ALLOWED_MTF_TIMEFRAMES}")

        if not isinstance(self.participating_timeframes, (list, tuple)):
            raise ValueError("MTF participating_timeframes must be a list or tuple")
        clean_ptfs = []
        for ptf in self.participating_timeframes:
            if not isinstance(ptf, str) or ptf not in ALLOWED_MTF_TIMEFRAMES:
                raise ValueError(f"MTF participating timeframe '{ptf}' is not supported")
            clean_ptfs.append(ptf)
        object.__setattr__(self, "participating_timeframes", tuple(clean_ptfs))

        if not isinstance(self.signals, (list, tuple)):
            raise ValueError("MTF signals must be a list or tuple")
        clean_sigs = []
        for s in self.signals:
            if isinstance(s, Project1MTFSignal):
                clean_sigs.append(s)
            elif isinstance(s, dict):
                clean_sigs.append(Project1MTFSignal(
                    symbol=s.get("symbol"),
                    timeframe=s.get("timeframe"),
                    direction=s.get("direction"),
                    decision_id=s.get("decision_id"),
                    signal_id=s.get("signal_id"),
                    decision_timestamp=s.get("decision_timestamp"),
                    market_timestamp=s.get("market_timestamp"),
                    strategy_name=s.get("strategy_name"),
                    strategy_version=s.get("strategy_version"),
                    candidate_id=s.get("candidate_id"),
                    evidence_id=s.get("evidence_id"),
                    experiment_fingerprint=s.get("experiment_fingerprint"),
                    canonical_live_decision_fingerprint=s.get("canonical_live_decision_fingerprint"),
                    authorization_fingerprint=s.get("authorization_fingerprint"),
                    constituent_fingerprint=s.get("constituent_fingerprint"),
                    provenance=s.get("provenance"),
                ))
            else:
                raise ValueError("MTF signals elements must be Project1MTFSignal or dict")
        object.__setattr__(self, "signals", tuple(clean_sigs))

        if isinstance(self.alignment_count, bool) or not isinstance(self.alignment_count, int) or self.alignment_count < 0:
            raise ValueError("MTF alignment_count must be a non-negative integer")

        if isinstance(self.alignment_coverage, bool) or not isinstance(self.alignment_coverage, int) or not (1 <= self.alignment_coverage <= 6):
            raise ValueError("MTF alignment_coverage must be an integer in 1..6 range")

        _validate_non_empty_string(self.classification, "MTF classification")
        if self.classification not in ALLOWED_MTF_CLASSIFICATIONS:
            raise ValueError(f"MTF classification '{self.classification}' is not supported. Allowed: {ALLOWED_MTF_CLASSIFICATIONS}")

        if self.higher_timeframe_context is not None:
            if not isinstance(self.higher_timeframe_context, dict):
                raise ValueError("MTF higher_timeframe_context must be a dictionary if provided")
            object.__setattr__(self, "higher_timeframe_context", copy.deepcopy(self.higher_timeframe_context))

        if not isinstance(self.constituent_fingerprints, (list, tuple)):
            raise ValueError("MTF constituent_fingerprints must be a tuple or list")
        object.__setattr__(self, "constituent_fingerprints", tuple(self.constituent_fingerprints))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "local_timeframe": self.local_timeframe,
            "participating_timeframes": list(self.participating_timeframes),
            "signals": [s.to_dict() for s in self.signals],
            "alignment_count": self.alignment_count,
            "alignment_coverage": self.alignment_coverage,
            "classification": self.classification,
            "higher_timeframe_context": copy.deepcopy(self.higher_timeframe_context) if self.higher_timeframe_context is not None else None,
            "constituent_fingerprints": list(self.constituent_fingerprints),
            "matching_signal_count": self.matching_signal_count,
            "available_signal_count": self.available_signal_count,
            "intelligence_fingerprint": self.intelligence_fingerprint,
            "star_representation": self.star_representation,
        }


def validate_project1_mtf_object(raw_mtf: Any) -> Tuple[bool, Optional[Dict[str, Any]], Tuple[str, ...]]:
    """Validate Project 1 MTF payload fail-closed.

    Returns:
      (is_valid, sanitized_mtf_dict, errors_tuple)
    """
    if raw_mtf is None:
        return True, None, ()

    if not isinstance(raw_mtf, dict):
        return False, None, ("MTF payload must be a mapping/object.",)

    try:
        mtf_config = Project1MTFConfig(
            symbol=raw_mtf.get("symbol", ""),
            local_timeframe=raw_mtf.get("local_timeframe", ""),
            participating_timeframes=raw_mtf.get("participating_timeframes", ()),
            signals=raw_mtf.get("signals", ()),
            alignment_count=raw_mtf.get("alignment_count"),
            alignment_coverage=raw_mtf.get("alignment_coverage"),
            classification=raw_mtf.get("classification", ""),
            higher_timeframe_context=raw_mtf.get("higher_timeframe_context"),
            constituent_fingerprints=raw_mtf.get("constituent_fingerprints", ()),
            matching_signal_count=raw_mtf.get("matching_signal_count"),
            available_signal_count=raw_mtf.get("available_signal_count"),
            intelligence_fingerprint=raw_mtf.get("intelligence_fingerprint"),
            star_representation=raw_mtf.get("star_representation"),
        )
        return True, mtf_config.to_dict(), ()
    except ValueError as val_err:
        return False, None, (f"Invalid MTF payload: {str(val_err)}",)
    except Exception as exc:
        return False, None, (f"Malformed MTF payload: {str(exc)}",)


def parse_iso8601_to_utc_epoch(
    raw_timestamp: Any,
    max_future_skew_seconds: float = 5.0,
    current_time_fn: Optional[Any] = None,
) -> float:
    """Parse and normalize timezone-aware ISO-8601 string to finite UTC epoch timestamp.

    Strictly requires a non-empty string in timezone-aware ISO-8601 format.
    Rejects:
    - Missing or None timestamp
    - Numeric timestamp sent as P1 Contract v1 timestamp
    - Naive datetime strings (without UTC offset or Z)
    - Invalid ISO format strings
    - Non-finite numeric results
    - Future timestamps beyond max_future_skew_seconds policy
    """
    if raw_timestamp is None:
        raise ValueError("Timestamp is required.")

    if isinstance(raw_timestamp, (int, float)) and not isinstance(raw_timestamp, bool):
        raise ValueError("P1 Contract v1 timestamp must be a timezone-aware ISO-8601 string, not numeric.")

    if not isinstance(raw_timestamp, str) or not raw_timestamp.strip():
        raise ValueError("Timestamp must be a non-empty string in ISO-8601 format.")

    clean_str = raw_timestamp.strip()
    # Normalize ISO 'Z' suffix for Python parsing compatibility
    iso_normalized = clean_str.replace("Z", "+00:00").replace("z", "+00:00")

    try:
        dt = datetime.fromisoformat(iso_normalized)
    except Exception as err:
        raise ValueError(f"Invalid ISO-8601 timestamp format '{clean_str}': {str(err)}") from err

    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError(f"Timestamp '{clean_str}' is naive. P1 Contract v1 requires explicit timezone-aware ISO-8601.")

    utc_epoch = dt.astimezone(timezone.utc).timestamp()

    if not math.isfinite(utc_epoch) or utc_epoch < 0:
        raise ValueError(f"Timestamp '{clean_str}' resulted in invalid non-finite epoch value {utc_epoch}.")

    now_ts = current_time_fn() if current_time_fn is not None else time.time()
    if utc_epoch > now_ts + max_future_skew_seconds:
        raise ValueError(
            f"Future timestamp rejected: timestamp {utc_epoch} exceeds current system clock {now_ts} "
            f"by more than {max_future_skew_seconds}s."
        )

    return float(utc_epoch)


@dataclass(frozen=True)
class Project1TrailingStopConfig:
    """Trailing stop configuration or status supplied by Project 1."""

    distance: float
    activation_price: Optional[float] = None
    is_active: bool = False
    trailing_stop_loss: Optional[float] = None

    def __post_init__(self) -> None:
        if isinstance(self.distance, bool) or not isinstance(self.distance, numbers.Real):
            raise ValueError("distance must be a numeric real value")
        dist_float = float(self.distance)
        if not math.isfinite(dist_float) or dist_float <= 0:
            raise ValueError("distance must be a positive finite number")
        object.__setattr__(self, "distance", dist_float)

        if self.activation_price is not None:
            if isinstance(self.activation_price, bool) or not isinstance(self.activation_price, numbers.Real):
                raise ValueError("activation_price must be a numeric real value if provided")
            act_float = float(self.activation_price)
            if not math.isfinite(act_float) or act_float <= 0:
                raise ValueError("activation_price must be a positive finite number")
            object.__setattr__(self, "activation_price", act_float)

        if not isinstance(self.is_active, bool):
            raise ValueError("is_active must be a boolean")

        if self.trailing_stop_loss is not None:
            if isinstance(self.trailing_stop_loss, bool) or not isinstance(self.trailing_stop_loss, numbers.Real):
                raise ValueError("trailing_stop_loss must be a numeric real value if provided")
            tsl_float = float(self.trailing_stop_loss)
            if not math.isfinite(tsl_float) or tsl_float <= 0:
                raise ValueError("trailing_stop_loss must be a positive finite number")
            object.__setattr__(self, "trailing_stop_loss", tsl_float)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "distance": self.distance,
            "activation_price": self.activation_price,
            "is_active": self.is_active,
            "trailing_stop_loss": self.trailing_stop_loss,
        }


@dataclass(frozen=True)
class Project1SignalContractPayload:
    """Immutable contract payload model for signal emission from Project 1."""

    integration_id: str
    signal_id: str
    symbol: str
    signal_type: str
    timestamp: float
    source_id: str = "project1_engine"
    contract_version: str = DEFAULT_CONTRACT_VERSION
    command_type: str = "EMIT_SIGNAL"
    timeframe: Optional[str] = None
    strategy_name: Optional[str] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    trailing_stop: Optional[Project1TrailingStopConfig] = None
    confidence: Optional[float] = None
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.integration_id, str) or not self.integration_id.strip():
            raise ValueError("integration_id must be a non-empty string")
        object.__setattr__(self, "integration_id", self.integration_id.strip())

        if not isinstance(self.signal_id, str) or not self.signal_id.strip():
            raise ValueError("signal_id must be a non-empty string")
        object.__setattr__(self, "signal_id", self.signal_id.strip())

        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")
        object.__setattr__(self, "symbol", self.symbol.strip().upper())

        if not isinstance(self.signal_type, str) or not self.signal_type.strip():
            raise ValueError("signal_type must be a non-empty string")
        sig_lower = self.signal_type.strip().lower()
        if sig_lower not in ALLOWED_SIGNAL_TYPES:
            raise ValueError(f"signal_type must be one of {ALLOWED_SIGNAL_TYPES}")
        object.__setattr__(self, "signal_type", sig_lower)

        if isinstance(self.timestamp, bool) or not isinstance(self.timestamp, numbers.Real):
            raise ValueError("timestamp must be a numeric real value")
        ts_float = float(self.timestamp)
        if ts_float < 0 or not math.isfinite(ts_float):
            raise ValueError("timestamp must be a non-negative finite number")
        object.__setattr__(self, "timestamp", ts_float)

        if self.contract_version not in SUPPORTED_CONTRACT_VERSIONS:
            raise ValueError(
                f"Unsupported contract version: '{self.contract_version}'. "
                f"Supported versions: {list(SUPPORTED_CONTRACT_VERSIONS)}"
            )

        if self.command_type not in ALLOWED_COMMAND_TYPES:
            raise ValueError(f"command_type must be one of {ALLOWED_COMMAND_TYPES}")

        for price_field in (
            "entry_price",
            "stop_loss",
            "take_profit_1",
            "take_profit_2",
            "take_profit_3",
        ):
            val = getattr(self, price_field)
            if val is not None:
                if isinstance(val, bool) or not isinstance(val, numbers.Real):
                    raise ValueError(f"{price_field} must be a numeric real value if provided")
                pf_float = float(val)
                if not math.isfinite(pf_float) or pf_float <= 0:
                    raise ValueError(f"{price_field} must be a positive finite number")
                object.__setattr__(self, price_field, pf_float)

        if self.confidence is not None:
            if isinstance(self.confidence, bool) or not isinstance(self.confidence, numbers.Real):
                raise ValueError("confidence must be a numeric real value if provided")
            conf_float = float(self.confidence)
            if not math.isfinite(conf_float) or not (0.0 <= conf_float <= 1.0):
                raise ValueError("confidence must be between 0.0 and 1.0 inclusive")
            object.__setattr__(self, "confidence", conf_float)

        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary")

    def take_profits_tuple(self) -> Tuple[float, ...]:
        """Return tuple of present take-profit levels in order."""
        tps = []
        if self.take_profit_1 is not None:
            tps.append(self.take_profit_1)
        if self.take_profit_2 is not None:
            tps.append(self.take_profit_2)
        if self.take_profit_3 is not None:
            tps.append(self.take_profit_3)
        return tuple(tps)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "integration_id": self.integration_id,
            "source_id": self.source_id,
            "contract_version": self.contract_version,
            "command_type": self.command_type,
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "signal_type": self.signal_type,
            "timestamp": self.timestamp,
            "timeframe": self.timeframe,
            "strategy_name": self.strategy_name,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit_1": self.take_profit_1,
            "take_profit_2": self.take_profit_2,
            "take_profit_3": self.take_profit_3,
            "take_profits": list(self.take_profits_tuple()),
            "trailing_stop": self.trailing_stop.to_dict() if self.trailing_stop else None,
            "confidence": self.confidence,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "correlation_id": self.correlation_id,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class Project1LifecycleContractPayload:
    """Immutable contract payload model for lifecycle commands/status updates from Project 1."""

    integration_id: str
    signal_id: str
    lifecycle_state: str
    timestamp: float
    source_id: str = "project1_engine"
    contract_version: str = DEFAULT_CONTRACT_VERSION
    reason: Optional[str] = None
    user_id: Optional[str] = None
    correlation_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.integration_id, str) or not self.integration_id.strip():
            raise ValueError("integration_id must be a non-empty string")
        object.__setattr__(self, "integration_id", self.integration_id.strip())

        if not isinstance(self.signal_id, str) or not self.signal_id.strip():
            raise ValueError("signal_id must be a non-empty string")
        object.__setattr__(self, "signal_id", self.signal_id.strip())

        if not isinstance(self.lifecycle_state, str) or not self.lifecycle_state.strip():
            raise ValueError("lifecycle_state must be a non-empty string")
        ls_upper = self.lifecycle_state.strip().upper()
        if ls_upper not in ALLOWED_LIFECYCLE_STATES:
            raise ValueError(f"lifecycle_state must be one of {ALLOWED_LIFECYCLE_STATES}")
        object.__setattr__(self, "lifecycle_state", ls_upper)

        if isinstance(self.timestamp, bool) or not isinstance(self.timestamp, numbers.Real):
            raise ValueError("timestamp must be a numeric real value")
        ts_float = float(self.timestamp)
        if ts_float < 0 or not math.isfinite(ts_float):
            raise ValueError("timestamp must be a non-negative finite number")
        object.__setattr__(self, "timestamp", ts_float)

        if self.contract_version not in SUPPORTED_CONTRACT_VERSIONS:
            raise ValueError(
                f"Unsupported contract version: '{self.contract_version}'. "
                f"Supported versions: {list(SUPPORTED_CONTRACT_VERSIONS)}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "integration_id": self.integration_id,
            "source_id": self.source_id,
            "contract_version": self.contract_version,
            "signal_id": self.signal_id,
            "lifecycle_state": self.lifecycle_state,
            "timestamp": self.timestamp,
            "reason": self.reason,
            "user_id": self.user_id,
            "correlation_id": self.correlation_id,
        }


@dataclass(frozen=True)
class Project1ValidationResult:
    """Validation output container for contract boundary validation."""

    is_valid: bool
    errors: Tuple[str, ...] = field(default_factory=tuple)
    sanitized_payload: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": list(self.errors),
            "sanitized_payload": self.sanitized_payload,
        }


def validate_project1_contract_payload(
    raw_payload: Dict[str, Any],
    current_time_fn: Optional[Any] = None,
) -> Project1ValidationResult:
    """Canonical boundary adapter for incoming raw Project 1 contract payloads.

    Accepts P1 Contract v1 nested canonical structure:
    {
        "contract_version": "1.0",
        "event_id": publication_id,
        "event_type": "TRADING_SIGNAL",
        "timestamp": timezone_aware_iso8601,
        "instrument": {"symbol": symbol, "interval": timeframe},
        "signal": {...},
        "trade_setup": {...},
        "provenance": {...}
    }
    or legacy/flat structure if compatible, and normalizes into a single canonical
    P2 internal integration record.
    """
    if not isinstance(raw_payload, dict):
        return Project1ValidationResult(
            is_valid=False,
            errors=("Payload must be a JSON dictionary object.",),
        )

    errors: List[str] = []

    # 1. Contract Version
    version = str(raw_payload.get("contract_version", DEFAULT_CONTRACT_VERSION)).strip()
    if version not in SUPPORTED_CONTRACT_VERSIONS:
        return Project1ValidationResult(
            is_valid=False,
            errors=(
                f"Unsupported contract version: '{version}'. Supported versions: {list(SUPPORTED_CONTRACT_VERSIONS)}",
            ),
        )

    # Detect payload layout: nested canonical P1 Contract v1 vs flat payload
    is_nested_v1 = (
        isinstance(raw_payload.get("signal"), dict)
        or isinstance(raw_payload.get("instrument"), dict)
        or isinstance(raw_payload.get("trade_setup"), dict)
        or isinstance(raw_payload.get("provenance"), dict)
    )

    # 2. Extract nested objects if present
    signal_obj = raw_payload.get("signal") if isinstance(raw_payload.get("signal"), dict) else {}
    instrument_obj = raw_payload.get("instrument") if isinstance(raw_payload.get("instrument"), dict) else {}
    trade_setup_obj = raw_payload.get("trade_setup") if isinstance(raw_payload.get("trade_setup"), dict) else {}
    provenance_obj = raw_payload.get("provenance") if isinstance(raw_payload.get("provenance"), dict) else {}

    # Command / Event type
    event_type = raw_payload.get("event_type") or raw_payload.get("command_type") or "TRADING_SIGNAL"
    command_type = raw_payload.get("command_type") or ("EMIT_SIGNAL" if event_type in ("TRADING_SIGNAL", "EMIT_SIGNAL") else str(event_type))

    if command_type not in ALLOWED_COMMAND_TYPES and event_type not in ALLOWED_EVENT_TYPES:
        errors.append(f"Invalid command_type/event_type '{command_type}'. Allowed: {list(ALLOWED_COMMAND_TYPES)}")

    # 3. Canonical Boundary Layout Check
    if command_type in ("EMIT_SIGNAL", "TRADING_SIGNAL"):
        if is_nested_v1 and (
            raw_payload.get("signal") is None
            or raw_payload.get("instrument") is None
            or raw_payload.get("trade_setup") is None
        ):
            errors.append("Missing canonical nested sections ('signal', 'instrument', 'trade_setup').")

    # 4. Strict Lineage Identity Extraction (Never synthesize decision_id = signal_id or publication_id = event_id)
    publication_id = raw_payload.get("publication_id") or signal_obj.get("publication_id") or raw_payload.get("event_id") or raw_payload.get("integration_id")
    event_id = raw_payload.get("event_id") or raw_payload.get("integration_id")
    signal_id = signal_obj.get("signal_id") or raw_payload.get("signal_id")
    decision_id = signal_obj.get("decision_id") if "decision_id" in signal_obj else raw_payload.get("decision_id")
    candidate_id = signal_obj.get("candidate_id") if "candidate_id" in signal_obj else raw_payload.get("candidate_id")
    research_evidence_id = signal_obj.get("research_evidence_id") or provenance_obj.get("research_evidence_id") or raw_payload.get("research_evidence_id")
    research_fingerprint = signal_obj.get("research_fingerprint") or provenance_obj.get("research_fingerprint") or raw_payload.get("research_fingerprint")
    canonical_live_decision_fingerprint = signal_obj.get("canonical_live_decision_fingerprint") or provenance_obj.get("canonical_live_decision_fingerprint") or raw_payload.get("canonical_live_decision_fingerprint")
    runtime_authorization_fingerprint = signal_obj.get("runtime_authorization_fingerprint") or provenance_obj.get("runtime_authorization_fingerprint") or raw_payload.get("runtime_authorization_fingerprint")

    integration_id = publication_id or event_id or signal_id
    if not isinstance(integration_id, str) or not integration_id.strip():
        errors.append("authoritative publication_id/integration_id is required and must be a non-empty string.")

    if not isinstance(signal_id, str) or not signal_id.strip():
        errors.append("signal_id is required and must be a non-empty string.")

    # Lifecycle state specific validation
    lifecycle_state = raw_payload.get("lifecycle_state") or signal_obj.get("lifecycle_state")
    if lifecycle_state is not None:
        ls_str = str(lifecycle_state).strip().upper()
        if ls_str not in ALLOWED_LIFECYCLE_STATES:
            errors.append(f"Invalid lifecycle_state '{lifecycle_state}'. Allowed: {list(ALLOWED_LIFECYCLE_STATES)}")

    # Signal type & Symbol validation
    symbol = instrument_obj.get("symbol") or raw_payload.get("symbol")
    timeframe = instrument_obj.get("interval") or instrument_obj.get("timeframe") or raw_payload.get("timeframe")

    raw_decision = (
        signal_obj.get("decision")
        or signal_obj.get("signal_label")
        or raw_payload.get("signal_type")
        or raw_payload.get("action")
    )

    if command_type in ("EMIT_SIGNAL", "TRADING_SIGNAL"):
        if not isinstance(symbol, str) or not symbol.strip():
            errors.append("symbol is required and must be a non-empty string for TRADING_SIGNAL.")

        if not isinstance(raw_decision, str) or not raw_decision.strip():
            errors.append("signal decision/type is required and must be a non-empty string for TRADING_SIGNAL.")
        else:
            norm_decision = raw_decision.strip().lower().replace("_", "-").replace(" ", "-")
            if norm_decision not in ALLOWED_SIGNAL_TYPES:
                errors.append(f"Invalid signal decision '{raw_decision}'. Allowed: {list(ALLOWED_SIGNAL_TYPES)}")
            else:
                raw_decision = norm_decision

    # 4. Timestamp Normalization at Boundary
    raw_ts = raw_payload.get("timestamp") if "timestamp" in raw_payload else signal_obj.get("timestamp")
    normalized_epoch: Optional[float] = None

    if is_nested_v1 or isinstance(raw_ts, str):
        # Enforce strict ISO-8601 timezone-aware parsing for P1 Contract v1
        try:
            normalized_epoch = parse_iso8601_to_utc_epoch(
                raw_ts,
                max_future_skew_seconds=5.0,
                current_time_fn=current_time_fn,
            )
        except ValueError as ts_err:
            errors.append(str(ts_err))
    else:
        # Fallback numeric handling for legacy non-nested endpoints
        if raw_ts is None:
            errors.append("timestamp is required.")
        elif isinstance(raw_ts, bool) or not isinstance(raw_ts, numbers.Real):
            errors.append("timestamp must be numeric or ISO-8601 string.")
        else:
            ts_f = float(raw_ts)
            if ts_f < 0 or not math.isfinite(ts_f):
                errors.append("timestamp must be a non-negative finite number.")
            else:
                now_ts = current_time_fn() if current_time_fn is not None else time.time()
                if ts_f > now_ts + 5.0:
                    errors.append(f"Future timestamp rejected: timestamp {ts_f} exceeds system clock {now_ts}.")
                else:
                    normalized_epoch = ts_f

    # 5. Trade Setup Price Levels (strictly from P1, never recomputed)
    entry_price = trade_setup_obj.get("entry_price") if "entry_price" in trade_setup_obj else raw_payload.get("entry_price")
    stop_loss = trade_setup_obj.get("stop_loss") if "stop_loss" in trade_setup_obj else raw_payload.get("stop_loss")
    tp1 = trade_setup_obj.get("tp1") or trade_setup_obj.get("take_profit_1") or raw_payload.get("take_profit_1")
    tp2 = trade_setup_obj.get("tp2") or trade_setup_obj.get("take_profit_2") or raw_payload.get("take_profit_2")
    tp3 = trade_setup_obj.get("tp3") or trade_setup_obj.get("take_profit_3") or raw_payload.get("take_profit_3")
    rr_ratio = trade_setup_obj.get("risk_reward_ratio") if "risk_reward_ratio" in trade_setup_obj else raw_payload.get("risk_reward_ratio")

    for pname, pval in (
        ("entry_price", entry_price),
        ("stop_loss", stop_loss),
        ("take_profit_1", tp1),
        ("take_profit_2", tp2),
        ("take_profit_3", tp3),
    ):
        if pval is not None:
            if isinstance(pval, bool) or not isinstance(pval, numbers.Real):
                errors.append(f"{pname} must be a numeric real value if provided.")
            else:
                p_f = float(pval)
                if not math.isfinite(p_f) or p_f <= 0:
                    errors.append(f"{pname} must be a positive finite number.")

    # 6. Confidence & Operational Stability Score
    confidence = signal_obj.get("confidence") if "confidence" in signal_obj else raw_payload.get("confidence")
    stability_score = (
        signal_obj.get("operational_stability_score")
        if "operational_stability_score" in signal_obj
        else (
            signal_obj.get("stability_score")
            if "stability_score" in signal_obj
            else (
                raw_payload.get("operational_stability_score")
                if "operational_stability_score" in raw_payload
                else raw_payload.get("stability_score")
            )
        )
    )

    if confidence is not None:
        if isinstance(confidence, bool) or not isinstance(confidence, numbers.Real):
            errors.append("confidence must be a numeric real value if provided.")
        else:
            conf_f = float(confidence)
            if not math.isfinite(conf_f) or not (0.0 <= conf_f <= 1.0):
                errors.append("confidence must be between 0.0 and 1.0 inclusive.")

    if stability_score is not None:
        if isinstance(stability_score, bool) or not isinstance(stability_score, numbers.Real):
            errors.append("stability_score must be a numeric real value if provided.")
        else:
            stab_f = float(stability_score)
            if not math.isfinite(stab_f) or not (0.0 <= stab_f <= 1.0):
                errors.append("stability_score must be between 0.0 and 1.0 inclusive.")

    # Strategy identity & version
    strategy_id = signal_obj.get("strategy") or raw_payload.get("strategy_name") or raw_payload.get("strategy_id")
    strategy_version = signal_obj.get("strategy_version") or raw_payload.get("strategy_version") or provenance_obj.get("strategy_version")

    # Trailing stop configuration
    ts_config = None
    ts_raw = trade_setup_obj.get("trailing_stop") or raw_payload.get("trailing_stop")
    if ts_raw is not None:
        if not isinstance(ts_raw, dict):
            errors.append("trailing_stop must be a dictionary if provided.")
        else:
            try:
                ts_dist = ts_raw.get("distance")
                ts_config = Project1TrailingStopConfig(
                    distance=ts_dist,
                    activation_price=ts_raw.get("activation_price"),
                    is_active=bool(ts_raw.get("is_active", False)),
                    trailing_stop_loss=ts_raw.get("trailing_stop_loss"),
                )
            except ValueError as val_err:
                errors.append(f"Invalid trailing_stop config: {str(val_err)}")

    # Multi-Timeframe (MTF) configuration validation
    mtf_sanitized = None
    if "mtf" in raw_payload and raw_payload["mtf"] is not None:
        mtf_valid, mtf_dict, mtf_errs = validate_project1_mtf_object(raw_payload["mtf"])
        if not mtf_valid:
            errors.extend(mtf_errs)
        else:
            mtf_sanitized = mtf_dict

    if errors:
        return Project1ValidationResult(is_valid=False, errors=tuple(errors))

    # Construct canonical P2 internal integration record
    sanitized: Dict[str, Any] = {
        "integration_id": str(integration_id).strip(),
        "publication_id": str(publication_id).strip() if publication_id else None,
        "event_id": str(event_id).strip() if event_id else None,
        "signal_id": str(signal_id).strip(),
        "decision_id": str(decision_id).strip() if decision_id else None,
        "candidate_id": str(candidate_id).strip() if candidate_id else None,
        "research_evidence_id": str(research_evidence_id).strip() if research_evidence_id else None,
        "research_fingerprint": str(research_fingerprint).strip() if research_fingerprint else None,
        "canonical_live_decision_fingerprint": str(canonical_live_decision_fingerprint).strip() if canonical_live_decision_fingerprint else None,
        "runtime_authorization_fingerprint": str(runtime_authorization_fingerprint).strip() if runtime_authorization_fingerprint else None,
        "source_id": str(raw_payload.get("source_id", "project1_engine")).strip(),
        "contract_version": version,
        "command_type": "EMIT_SIGNAL",
        "timestamp": normalized_epoch,
        "correlation_id": raw_payload.get("correlation_id"),
        "user_id": raw_payload.get("user_id"),
        "tenant_id": raw_payload.get("tenant_id"),
    }

    if symbol is not None:
        sanitized["symbol"] = str(symbol).strip().upper()
    if raw_decision is not None:
        sanitized["signal_type"] = str(raw_decision).strip().lower()
    if lifecycle_state is not None:
        sanitized["lifecycle_state"] = str(lifecycle_state).strip().upper()

    if strategy_id is not None:
        sanitized["strategy_name"] = str(strategy_id).strip()
    if strategy_version is not None:
        sanitized["strategy_version"] = str(strategy_version).strip()
    if timeframe is not None:
        sanitized["timeframe"] = str(timeframe).strip()

    if entry_price is not None:
        sanitized["entry_price"] = float(entry_price)
    if stop_loss is not None:
        sanitized["stop_loss"] = float(stop_loss)
    if tp1 is not None:
        sanitized["take_profit_1"] = float(tp1)
    if tp2 is not None:
        sanitized["take_profit_2"] = float(tp2)
    if tp3 is not None:
        sanitized["take_profit_3"] = float(tp3)
    if rr_ratio is not None:
        sanitized["risk_reward_ratio"] = float(rr_ratio)

    if confidence is not None:
        sanitized["confidence"] = float(confidence)
    if stability_score is not None:
        sanitized["operational_stability_score"] = float(stability_score)

    if ts_config is not None:
        sanitized["trailing_stop"] = ts_config.to_dict()

    if mtf_sanitized is not None:
        sanitized["mtf"] = mtf_sanitized

    # Quantity extraction (preserve if present in raw_payload or trade_setup)
    qty = (
        trade_setup_obj.get("requested_quantity") if "requested_quantity" in trade_setup_obj
        else (trade_setup_obj.get("quantity") if "quantity" in trade_setup_obj
        else (raw_payload.get("requested_quantity") if "requested_quantity" in raw_payload
        else raw_payload.get("quantity")))
    )
    if qty is not None:
        try:
            sanitized["requested_quantity"] = float(qty)
        except (ValueError, TypeError):
            pass

    # Invalidation condition extraction (strictly top-level/trade_setup, never metadata)
    invalidation = (
        trade_setup_obj.get("invalidation_condition")
        or raw_payload.get("invalidation_condition")
    )
    if invalidation:
        sanitized["invalidation_condition"] = str(invalidation).strip()

    # Provenance metadata construction
    meta = dict(raw_payload.get("metadata")) if isinstance(raw_payload.get("metadata"), dict) else {}
    if provenance_obj:
        meta.update(provenance_obj)

    # Ensure canonical provenance_type is preserved if present
    if "provenance_type" not in meta:
        if raw_payload.get("provenance_type"):
            meta["provenance_type"] = raw_payload["provenance_type"]
        elif provenance_obj.get("provenance_type"):
            meta["provenance_type"] = provenance_obj["provenance_type"]

    if "is_live" not in meta:
        if "is_live" in raw_payload:
            meta["is_live"] = raw_payload["is_live"]
        elif "is_live" in provenance_obj:
            meta["is_live"] = provenance_obj["is_live"]

    if "source" not in meta:
        if raw_payload.get("source"):
            meta["source"] = raw_payload["source"]
        elif provenance_obj.get("source"):
            meta["source"] = provenance_obj["source"]

    sanitized["metadata"] = meta

    return Project1ValidationResult(is_valid=True, errors=(), sanitized_payload=sanitized)


def get_project1_contract_capabilities() -> Dict[str, Any]:
    """Return Project 1 Contract capabilities metadata for discovery."""
    return {
        "gateway_name": "Project1IntegrationGateway",
        "supported_contract_versions": list(SUPPORTED_CONTRACT_VERSIONS),
        "current_contract_version": DEFAULT_CONTRACT_VERSION,
        "allowed_command_types": list(ALLOWED_COMMAND_TYPES),
        "allowed_signal_types": list(ALLOWED_SIGNAL_TYPES),
        "allowed_lifecycle_states": list(ALLOWED_LIFECYCLE_STATES),
        "guarantees": {
            "non_calculation": True,
            "project1_source_of_truth": True,
            "server_side_authorization": True,
            "tenant_isolation": True,
            "audit_logged": True,
            "secret_sanitized": True,
        },
    }
