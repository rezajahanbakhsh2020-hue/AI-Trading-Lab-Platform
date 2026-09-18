"""Formal Project 1 Integration Contract Domain Model.

Defines versioned, explicit, schema-driven, independent integration contract
data structures and validation logic for Project 1 ↔ Project 2 communication.

Rules:
- Project 2 NEVER calculates, modifies, optimizes, or decides strategy rules,
  Entry, SL, TP, trailing stops, or trading decisions.
- Project 1 is the sole source of truth for trade setups, execution levels, and strategy outputs.
- Project 2 validates, authorizes, scopes, persists, and presents Project 1 contract payloads.
"""

from dataclasses import dataclass, field
import math
import numbers
from typing import Any, Dict, List, Optional, Tuple

SUPPORTED_CONTRACT_VERSIONS: Tuple[str, ...] = ("1.0", "1.0.0", "v1.0")
DEFAULT_CONTRACT_VERSION: str = "1.0"

ALLOWED_COMMAND_TYPES: Tuple[str, ...] = (
    "EMIT_SIGNAL",
    "UPDATE_LIFECYCLE",
    "UPDATE_TRAILING_STOP",
    "HEARTBEAT",
)

ALLOWED_SIGNAL_TYPES: Tuple[str, ...] = ("buy", "sell", "hold", "no-signal")

ALLOWED_LIFECYCLE_STATES: Tuple[str, ...] = (
    "STAGED",
    "ACTIVE",
    "UPDATED",
    "CANCELLED",
    "EXPIRED",
    "REJECTED",
    "EXECUTED",
)


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


def validate_project1_contract_payload(raw_payload: Dict[str, Any]) -> Project1ValidationResult:
    """Validate incoming raw Project 1 payload at the integration gateway boundary.

    Enforces contract version, mandatory fields, numeric bounds, finite real values,
    and returns a structured Project1ValidationResult.
    """
    if not isinstance(raw_payload, dict):
        return Project1ValidationResult(
            is_valid=False,
            errors=("Payload must be a JSON dictionary object.",),
        )

    errors: List[str] = []

    # 1. Contract version check
    version = str(raw_payload.get("contract_version", DEFAULT_CONTRACT_VERSION)).strip()
    if version not in SUPPORTED_CONTRACT_VERSIONS:
        return Project1ValidationResult(
            is_valid=False,
            errors=(
                f"Unsupported contract version: '{version}'. Supported versions: {list(SUPPORTED_CONTRACT_VERSIONS)}",
            ),
        )

    # 2. Command type check
    command_type = str(raw_payload.get("command_type", "EMIT_SIGNAL")).strip()
    if command_type not in ALLOWED_COMMAND_TYPES:
        errors.append(f"Invalid command_type '{command_type}'. Allowed: {list(ALLOWED_COMMAND_TYPES)}")

    # 3. Mandatory string identity fields
    integration_id = raw_payload.get("integration_id")
    if not isinstance(integration_id, str) or not integration_id.strip():
        errors.append("integration_id is required and must be a non-empty string.")

    signal_id = raw_payload.get("signal_id")
    if not isinstance(signal_id, str) or not signal_id.strip():
        errors.append("signal_id is required and must be a non-empty string.")

    # Lifecycle state specific validation
    lifecycle_state = raw_payload.get("lifecycle_state")
    if lifecycle_state is not None:
        ls_str = str(lifecycle_state).strip().upper()
        if ls_str not in ALLOWED_LIFECYCLE_STATES:
            errors.append(f"Invalid lifecycle_state '{lifecycle_state}'. Allowed: {list(ALLOWED_LIFECYCLE_STATES)}")

    # Signal emission specific validation
    symbol = raw_payload.get("symbol")
    signal_type = raw_payload.get("signal_type")
    if command_type == "EMIT_SIGNAL":
        if not isinstance(symbol, str) or not symbol.strip():
            errors.append("symbol is required and must be a non-empty string for EMIT_SIGNAL.")

        if not isinstance(signal_type, str) or not signal_type.strip():
            errors.append("signal_type is required and must be a non-empty string for EMIT_SIGNAL.")
        elif signal_type.strip().lower() not in ALLOWED_SIGNAL_TYPES:
            errors.append(f"Invalid signal_type '{signal_type}'. Allowed: {list(ALLOWED_SIGNAL_TYPES)}")

    # Timestamp validation
    timestamp = raw_payload.get("timestamp")
    if timestamp is None:
        errors.append("timestamp is required.")
    elif isinstance(timestamp, bool) or not isinstance(timestamp, numbers.Real):
        errors.append("timestamp must be a numeric real value.")
    else:
        ts_f = float(timestamp)
        if ts_f < 0 or not math.isfinite(ts_f):
            errors.append("timestamp must be a non-negative finite number.")

    # Price levels validation
    for pfield in ("entry_price", "stop_loss", "take_profit_1", "take_profit_2", "take_profit_3"):
        val = raw_payload.get(pfield)
        if val is not None:
            if isinstance(val, bool) or not isinstance(val, numbers.Real):
                errors.append(f"{pfield} must be a numeric real value if provided.")
            else:
                p_f = float(val)
                if not math.isfinite(p_f) or p_f <= 0:
                    errors.append(f"{pfield} must be a positive finite number.")

    # Confidence validation
    conf = raw_payload.get("confidence")
    if conf is not None:
        if isinstance(conf, bool) or not isinstance(conf, numbers.Real):
            errors.append("confidence must be a numeric real value if provided.")
        else:
            conf_f = float(conf)
            if not math.isfinite(conf_f) or not (0.0 <= conf_f <= 1.0):
                errors.append("confidence must be between 0.0 and 1.0 inclusive.")

    # Trailing stop validation
    ts_config = None
    ts_raw = raw_payload.get("trailing_stop")
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

    if errors:
        return Project1ValidationResult(is_valid=False, errors=tuple(errors))

    # Construct clean sanitized dictionary payload
    sanitized: Dict[str, Any] = {
        "integration_id": str(integration_id).strip(),
        "source_id": str(raw_payload.get("source_id", "project1_engine")).strip(),
        "contract_version": version,
        "command_type": command_type,
        "signal_id": str(signal_id).strip(),
        "timestamp": float(timestamp),
        "correlation_id": raw_payload.get("correlation_id"),
        "user_id": raw_payload.get("user_id"),
        "tenant_id": raw_payload.get("tenant_id"),
    }

    if symbol is not None:
        sanitized["symbol"] = str(symbol).strip().upper()
    if signal_type is not None:
        sanitized["signal_type"] = str(signal_type).strip().lower()
    if lifecycle_state is not None:
        sanitized["lifecycle_state"] = str(lifecycle_state).strip().upper()

    for pfield in ("entry_price", "stop_loss", "take_profit_1", "take_profit_2", "take_profit_3"):
        if raw_payload.get(pfield) is not None:
            sanitized[pfield] = float(raw_payload[pfield])

    if conf is not None:
        sanitized["confidence"] = float(conf)
    if raw_payload.get("timeframe") is not None:
        sanitized["timeframe"] = str(raw_payload["timeframe"]).strip()
    if raw_payload.get("strategy_name") is not None:
        sanitized["strategy_name"] = str(raw_payload["strategy_name"]).strip()
    if ts_config is not None:
        sanitized["trailing_stop"] = ts_config.to_dict()

    sanitized["metadata"] = dict(raw_payload.get("metadata")) if isinstance(raw_payload.get("metadata"), dict) else {}

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
