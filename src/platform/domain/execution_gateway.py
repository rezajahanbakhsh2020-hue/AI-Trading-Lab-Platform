"""Execution gateway boundary domain models.

Immutable domain contract for execution commands and execution attempt results
at the Project 2 Execution Gateway boundary.
Represents the boundary contract where an authorized OrderIntent may be submitted
for execution downstream without implementing real broker/exchange routing,
fake execution, fills, or paper trading.
"""

from dataclasses import dataclass
from enum import Enum
import numbers
import time
from typing import Any, Dict, Optional, Union

from src.platform.domain.order_intent import OrderIntent, OrderLifecycleState


class ExecutionBoundaryStatus(str, Enum):
    """Domain state model for execution boundary responses."""

    UNCONFIGURED = "UNCONFIGURED"
    REJECTED_UNAUTHORIZED = "REJECTED_UNAUTHORIZED"
    REJECTED_UNAVAILABLE = "REJECTED_UNAVAILABLE"
    REJECTED_INVALID_STATE = "REJECTED_INVALID_STATE"
    SUBMITTED_TO_PORT = "SUBMITTED_TO_PORT"


@dataclass(frozen=True)
class ExecutionRequestCommand:
    """Immutable execution request command derived directly from an authorized OrderIntent.

    Preserves exact symbol, direction, prices, quantities, and parameters from
    the source OrderIntent without recalculation or modification.
    """

    execution_command_id: str
    order_intent_id: str
    authorization_id: str
    user_id: str
    symbol: str
    direction: str
    idempotency_key: str
    timestamp: float
    order_type: str = "market"
    requested_price: Optional[float] = None
    requested_quantity: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    time_in_force: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.execution_command_id, str) or not self.execution_command_id.strip():
            raise ValueError("execution_command_id must be a non-empty string")
        object.__setattr__(self, "execution_command_id", self.execution_command_id.strip())

        if not isinstance(self.order_intent_id, str) or not self.order_intent_id.strip():
            raise ValueError("order_intent_id must be a non-empty string")
        object.__setattr__(self, "order_intent_id", self.order_intent_id.strip())

        if not isinstance(self.authorization_id, str) or not self.authorization_id.strip():
            raise ValueError("authorization_id must be a non-empty string")
        object.__setattr__(self, "authorization_id", self.authorization_id.strip())

        if not isinstance(self.user_id, str) or not self.user_id.strip():
            raise ValueError("user_id must be a non-empty string")
        object.__setattr__(self, "user_id", self.user_id.strip())

        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")
        object.__setattr__(self, "symbol", self.symbol.strip().upper())

        if not isinstance(self.direction, str) or self.direction.strip().lower() not in ("buy", "sell"):
            raise ValueError("direction must be either 'buy' or 'sell'")
        object.__setattr__(self, "direction", self.direction.strip().lower())

        if not isinstance(self.idempotency_key, str) or not self.idempotency_key.strip():
            raise ValueError("idempotency_key must be a non-empty string")
        object.__setattr__(self, "idempotency_key", self.idempotency_key.strip())

        if isinstance(self.timestamp, bool) or not isinstance(self.timestamp, numbers.Real):
            raise ValueError("timestamp must be a non-negative real number")
        ts_float = float(self.timestamp)
        if ts_float < 0:
            raise ValueError("timestamp must be non-negative")
        object.__setattr__(self, "timestamp", ts_float)

        if not isinstance(self.order_type, str) or not self.order_type.strip():
            raise ValueError("order_type must be a non-empty string")
        object.__setattr__(self, "order_type", self.order_type.strip().lower())

        for field_name in (
            "requested_price",
            "requested_quantity",
            "stop_loss",
            "take_profit_1",
            "take_profit_2",
            "take_profit_3",
        ):
            val = getattr(self, field_name)
            if val is not None:
                if isinstance(val, bool) or not isinstance(val, numbers.Real):
                    raise ValueError(f"{field_name} must be a numeric real value if provided")
                val_float = float(val)
                if val_float <= 0:
                    raise ValueError(f"{field_name} must be greater than zero if provided")
                object.__setattr__(self, field_name, val_float)

        if self.time_in_force is not None:
            if not isinstance(self.time_in_force, str) or not self.time_in_force.strip():
                raise ValueError("time_in_force must be a non-empty string if provided")
            object.__setattr__(self, "time_in_force", self.time_in_force.strip().upper())

    @classmethod
    def from_order_intent(
        cls,
        order_intent: OrderIntent,
        command_id: Optional[str] = None,
        timestamp: Optional[Union[int, float]] = None,
    ) -> "ExecutionRequestCommand":
        """Factory method deriving an ExecutionRequestCommand from a staged OrderIntent."""
        if not isinstance(order_intent, OrderIntent):
            raise ValueError("order_intent must be an OrderIntent instance")

        if not order_intent.is_staged:
            raise ValueError(
                f"Cannot create execution command from OrderIntent in non-staged state '{order_intent.lifecycle_state.value}'"
            )

        cmd_id = command_id if command_id and command_id.strip() else f"cmd_{order_intent.order_intent_id}"
        ts = float(timestamp if timestamp is not None else time.time())

        return cls(
            execution_command_id=cmd_id,
            order_intent_id=order_intent.order_intent_id,
            authorization_id=order_intent.authorization_id,
            user_id=order_intent.user_id,
            symbol=order_intent.symbol,
            direction=order_intent.direction,
            idempotency_key=f"exec_{order_intent.idempotency_key}",
            timestamp=ts,
            order_type=order_intent.order_type,
            requested_price=order_intent.requested_price,
            requested_quantity=order_intent.requested_quantity,
            stop_loss=order_intent.stop_loss,
            take_profit_1=order_intent.take_profit_1,
            take_profit_2=order_intent.take_profit_2,
            take_profit_3=order_intent.take_profit_3,
            time_in_force=order_intent.time_in_force,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Return dictionary representation of ExecutionRequestCommand."""
        return {
            "execution_command_id": self.execution_command_id,
            "order_intent_id": self.order_intent_id,
            "authorization_id": self.authorization_id,
            "user_id": self.user_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "order_type": self.order_type,
            "requested_price": self.requested_price,
            "requested_quantity": self.requested_quantity,
            "stop_loss": self.stop_loss,
            "take_profit_1": self.take_profit_1,
            "take_profit_2": self.take_profit_2,
            "take_profit_3": self.take_profit_3,
            "time_in_force": self.time_in_force,
            "idempotency_key": self.idempotency_key,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class ExecutionAttemptResult:
    """Immutable infrastructure result of an attempt at the execution boundary."""

    success: bool
    user_id: str
    order_intent_id: str
    status: ExecutionBoundaryStatus
    reason: str
    externally_executed: bool = False
    detail: Optional[str] = None
    timestamp: float = 0.0
    provider_id: str = "none"

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise ValueError("success must be a boolean")

        if not isinstance(self.user_id, str) or not self.user_id.strip():
            raise ValueError("user_id must be a non-empty string")
        object.__setattr__(self, "user_id", self.user_id.strip())

        if not isinstance(self.order_intent_id, str) or not self.order_intent_id.strip():
            raise ValueError("order_intent_id must be a non-empty string")
        object.__setattr__(self, "order_intent_id", self.order_intent_id.strip())

        if isinstance(self.status, str):
            try:
                status_enum = ExecutionBoundaryStatus(self.status.upper())
            except ValueError:
                raise ValueError(f"status must be a valid ExecutionBoundaryStatus, got {self.status!r}")
            object.__setattr__(self, "status", status_enum)
        elif not isinstance(self.status, ExecutionBoundaryStatus):
            raise ValueError("status must be an ExecutionBoundaryStatus instance")

        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be a non-empty string")
        object.__setattr__(self, "reason", self.reason.strip())

        if not isinstance(self.externally_executed, bool):
            raise ValueError("externally_executed must be a boolean")

        if self.detail is not None:
            if not isinstance(self.detail, str) or not self.detail.strip():
                raise ValueError("detail must be a non-empty string if provided")
            object.__setattr__(self, "detail", self.detail.strip())

        if isinstance(self.timestamp, bool) or not isinstance(self.timestamp, numbers.Real):
            raise ValueError("timestamp must be a non-negative real number")
        ts_float = float(self.timestamp) if float(self.timestamp) > 0 else time.time()
        object.__setattr__(self, "timestamp", ts_float)

        if not isinstance(self.provider_id, str) or not self.provider_id.strip():
            raise ValueError("provider_id must be a non-empty string")
        object.__setattr__(self, "provider_id", self.provider_id.strip())

    def to_dict(self) -> Dict[str, Any]:
        """Return dictionary representation of ExecutionAttemptResult."""
        return {
            "success": self.success,
            "user_id": self.user_id,
            "order_intent_id": self.order_intent_id,
            "status": self.status.value,
            "reason": self.reason,
            "externally_executed": self.externally_executed,
            "detail": self.detail,
            "timestamp": self.timestamp,
            "provider_id": self.provider_id,
        }
