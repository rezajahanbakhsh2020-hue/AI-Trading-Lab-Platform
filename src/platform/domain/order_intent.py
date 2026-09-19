"""Order intent domain model and lifecycle state representation.

Immutable domain contract for an authorized order intent within Project 2.
Represents intent staged for potential execution downstream without claiming execution,
broker routing, fills, or position creation.
"""

from dataclasses import dataclass
from enum import Enum
import numbers
from typing import Any, Dict, Optional, Set, Tuple


class OrderLifecycleState(str, Enum):
    """Domain state model for order intent lifecycle."""

    STAGED = "STAGED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


# Terminal states cannot transition to any other state
TERMINAL_ORDER_LIFECYCLE_STATES: Set[OrderLifecycleState] = {
    OrderLifecycleState.REJECTED,
    OrderLifecycleState.CANCELLED,
    OrderLifecycleState.EXPIRED,
}

# Legal state transitions map
LEGAL_LIFECYCLE_TRANSITIONS: Dict[OrderLifecycleState, Set[OrderLifecycleState]] = {
    OrderLifecycleState.STAGED: {
        OrderLifecycleState.REJECTED,
        OrderLifecycleState.CANCELLED,
        OrderLifecycleState.EXPIRED,
    },
    OrderLifecycleState.REJECTED: set(),
    OrderLifecycleState.CANCELLED: set(),
    OrderLifecycleState.EXPIRED: set(),
}


def validate_lifecycle_transition(
    current_state: OrderLifecycleState, target_state: OrderLifecycleState
) -> bool:
    """Validate whether transitioning from current_state to target_state is legal.

    Raises:
        ValueError: If transition is invalid or from a terminal state.
    """
    if not isinstance(current_state, OrderLifecycleState):
        try:
            current_state = OrderLifecycleState(str(current_state).upper())
        except ValueError:
            raise ValueError(f"Invalid current lifecycle state: {current_state!r}")

    if not isinstance(target_state, OrderLifecycleState):
        try:
            target_state = OrderLifecycleState(str(target_state).upper())
        except ValueError:
            raise ValueError(f"Invalid target lifecycle state: {target_state!r}")

    if current_state in TERMINAL_ORDER_LIFECYCLE_STATES:
        raise ValueError(
            f"Cannot transition order intent from terminal state '{current_state.value}' to '{target_state.value}'"
        )

    if target_state not in LEGAL_LIFECYCLE_TRANSITIONS.get(current_state, set()):
        raise ValueError(
            f"Illegal order intent state transition from '{current_state.value}' to '{target_state.value}'"
        )

    return True


VALID_DIRECTIONS = ("buy", "sell")
VALID_ORDER_TYPES = ("market", "limit", "stop")


@dataclass(frozen=True)
class OrderIntent:
    """Immutable domain representation of an authorized order intent."""

    order_intent_id: str
    authorization_id: str
    user_id: str
    symbol: str
    direction: str
    idempotency_key: str
    creation_timestamp: float
    lifecycle_state: OrderLifecycleState = OrderLifecycleState.STAGED
    order_type: str = "market"
    requested_price: Optional[float] = None
    requested_quantity: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    time_in_force: Optional[str] = None
    rejection_reason: Optional[str] = None

    def __post_init__(self) -> None:
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

        if not isinstance(self.direction, str):
            raise ValueError("direction must be a string")
        direction_normalized = self.direction.strip().lower()
        if direction_normalized not in VALID_DIRECTIONS:
            raise ValueError(
                f"direction must be one of {VALID_DIRECTIONS}, got {self.direction!r}"
            )
        object.__setattr__(self, "direction", direction_normalized)

        if not isinstance(self.idempotency_key, str) or not self.idempotency_key.strip():
            raise ValueError("idempotency_key must be a non-empty string")
        object.__setattr__(self, "idempotency_key", self.idempotency_key.strip())

        if isinstance(self.creation_timestamp, bool) or not isinstance(
            self.creation_timestamp, numbers.Real
        ):
            raise ValueError("creation_timestamp must be a numeric real value")
        ts_float = float(self.creation_timestamp)
        if ts_float < 0:
            raise ValueError("creation_timestamp must be non-negative")
        object.__setattr__(self, "creation_timestamp", ts_float)

        if isinstance(self.lifecycle_state, str):
            try:
                state_enum = OrderLifecycleState(self.lifecycle_state.upper())
            except ValueError:
                raise ValueError(
                    f"lifecycle_state must be a valid OrderLifecycleState, got {self.lifecycle_state!r}"
                )
            object.__setattr__(self, "lifecycle_state", state_enum)
        elif not isinstance(self.lifecycle_state, OrderLifecycleState):
            raise ValueError("lifecycle_state must be an OrderLifecycleState instance")

        if not isinstance(self.order_type, str):
            raise ValueError("order_type must be a string")
        order_type_normalized = self.order_type.strip().lower()
        if order_type_normalized not in VALID_ORDER_TYPES:
            raise ValueError(
                f"order_type must be one of {VALID_ORDER_TYPES}, got {self.order_type!r}"
            )
        object.__setattr__(self, "order_type", order_type_normalized)

        # Optional numeric price / quantity fields validation
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

        if self.rejection_reason is not None:
            if not isinstance(self.rejection_reason, str) or not self.rejection_reason.strip():
                raise ValueError("rejection_reason must be a non-empty string if provided")
            object.__setattr__(self, "rejection_reason", self.rejection_reason.strip())

    @property
    def is_staged(self) -> bool:
        """Return True if in STAGED lifecycle state."""
        return self.lifecycle_state == OrderLifecycleState.STAGED

    @property
    def is_terminal(self) -> bool:
        """Return True if in a terminal lifecycle state."""
        return self.lifecycle_state in TERMINAL_ORDER_LIFECYCLE_STATES

    def with_lifecycle_state(
        self, new_state: OrderLifecycleState, reason: Optional[str] = None
    ) -> "OrderIntent":
        """Return a new OrderIntent instance with updated lifecycle state.

        Validates that the transition from current state to new_state is legal.
        """
        validate_lifecycle_transition(self.lifecycle_state, new_state)

        return OrderIntent(
            order_intent_id=self.order_intent_id,
            authorization_id=self.authorization_id,
            user_id=self.user_id,
            symbol=self.symbol,
            direction=self.direction,
            idempotency_key=self.idempotency_key,
            creation_timestamp=self.creation_timestamp,
            lifecycle_state=new_state,
            order_type=self.order_type,
            requested_price=self.requested_price,
            requested_quantity=self.requested_quantity,
            stop_loss=self.stop_loss,
            take_profit_1=self.take_profit_1,
            take_profit_2=self.take_profit_2,
            take_profit_3=self.take_profit_3,
            time_in_force=self.time_in_force,
            rejection_reason=reason if reason else self.rejection_reason,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Return dictionary representation of OrderIntent."""
        return {
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
            "creation_timestamp": self.creation_timestamp,
            "lifecycle_state": self.lifecycle_state.value,
            "is_staged": self.is_staged,
            "is_terminal": self.is_terminal,
            "rejection_reason": self.rejection_reason,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "OrderIntent":
        """Reconstruct OrderIntent from dictionary representation."""
        if not isinstance(d, dict):
            raise ValueError("d must be a dictionary")

        return cls(
            order_intent_id=d["order_intent_id"],
            authorization_id=d["authorization_id"],
            user_id=d["user_id"],
            symbol=d["symbol"],
            direction=d["direction"],
            idempotency_key=d["idempotency_key"],
            creation_timestamp=float(d["creation_timestamp"]),
            lifecycle_state=OrderLifecycleState(d.get("lifecycle_state", "STAGED")),
            order_type=d.get("order_type", "market"),
            requested_price=float(d["requested_price"]) if d.get("requested_price") is not None else None,
            requested_quantity=float(d["requested_quantity"]) if d.get("requested_quantity") is not None else None,
            stop_loss=float(d["stop_loss"]) if d.get("stop_loss") is not None else None,
            take_profit_1=float(d["take_profit_1"]) if d.get("take_profit_1") is not None else None,
            take_profit_2=float(d["take_profit_2"]) if d.get("take_profit_2") is not None else None,
            take_profit_3=float(d["take_profit_3"]) if d.get("take_profit_3") is not None else None,
            time_in_force=d.get("time_in_force"),
            rejection_reason=d.get("rejection_reason"),
        )
