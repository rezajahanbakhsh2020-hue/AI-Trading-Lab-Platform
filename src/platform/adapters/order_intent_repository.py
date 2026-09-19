"""Order Intent Repository Port & File-Backed Persistence Adapter.

Hexagonal storage port and persistence adapter for OrderIntents.
Provides schema-versioned, user-isolated, atomic JSON file persistence across process restarts.
"""

from abc import ABC, abstractmethod
import json
import os
import shutil
import time
from typing import Any, Dict, List, Optional

from src.platform.domain.order_intent import OrderIntent, OrderLifecycleState

CURRENT_SCHEMA_VERSION = "1.0"
DEFAULT_ORDER_INTENT_STORAGE_PATH = "data/order_intents.json"


class OrderIntentRepositoryPort(ABC):
    """Abstract outbound port for persisting OrderIntents."""

    @abstractmethod
    def save_order_intent(self, intent: OrderIntent) -> OrderIntent:
        """Save or update an OrderIntent."""
        raise NotImplementedError

    @abstractmethod
    def get_order_intent(
        self, order_intent_id: str, user_id: Optional[str] = None
    ) -> Optional[OrderIntent]:
        """Retrieve OrderIntent by ID, enforcing user isolation if user_id is specified."""
        raise NotImplementedError

    @abstractmethod
    def get_by_idempotency_key(
        self, user_id: str, idempotency_key: str
    ) -> Optional[OrderIntent]:
        """Retrieve OrderIntent by user_id and idempotency_key."""
        raise NotImplementedError

    @abstractmethod
    def list_order_intents(
        self,
        user_id: Optional[str] = None,
        symbol: Optional[str] = None,
        lifecycle_state: Optional[str] = None,
        limit: int = 100,
    ) -> List[OrderIntent]:
        """List OrderIntents with optional filtering and limit."""
        raise NotImplementedError


class FileBackedOrderIntentRepository(OrderIntentRepositoryPort):
    """File-backed persistence adapter for OrderIntents with atomic writes and corrupt recovery."""

    def __init__(
        self,
        storage_filepath: str = DEFAULT_ORDER_INTENT_STORAGE_PATH,
        audit_control: Optional[Any] = None,
    ) -> None:
        self._storage_filepath = storage_filepath
        self._audit_control = audit_control
        self._intents_by_id: Dict[str, OrderIntent] = {}
        self._idempotency_map: Dict[str, str] = {}  # "user_id:idempotency_key" -> order_intent_id
        self._load_from_storage()

    def _load_from_storage(self) -> None:
        if not os.path.exists(self._storage_filepath):
            self._intents_by_id = {}
            self._idempotency_map = {}
            return

        try:
            with open(self._storage_filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                intents_raw = []
                if isinstance(data, dict) and "intents" in data:
                    intents_raw = data.get("intents", [])
                elif isinstance(data, list):
                    intents_raw = data

                loaded_by_id: Dict[str, OrderIntent] = {}
                loaded_idemp: Dict[str, str] = {}

                for raw in intents_raw:
                    if isinstance(raw, dict):
                        try:
                            intent = OrderIntent.from_dict(raw)
                            loaded_by_id[intent.order_intent_id] = intent
                            if intent.idempotency_key:
                                key = f"{intent.user_id}:{intent.idempotency_key}"
                                loaded_idemp[key] = intent.order_intent_id
                        except Exception:
                            continue

                self._intents_by_id = loaded_by_id
                self._idempotency_map = loaded_idemp

        except Exception as exc:
            # Corrupt file handling: backup corrupt file and start fresh
            backup_path = f"{self._storage_filepath}.corrupt.{int(time.time())}"
            try:
                shutil.copy2(self._storage_filepath, backup_path)
            except Exception:
                pass
            self._intents_by_id = {}
            self._idempotency_map = {}
            if self._audit_control is not None and hasattr(self._audit_control, "record_failure"):
                self._audit_control.record_failure(
                    component="FileBackedOrderIntentRepository",
                    error_type="CORRUPT_STORAGE_DETECTED",
                    message=f"Corrupt OrderIntent repository file backed up to {backup_path}: {str(exc)}",
                    diagnostic_details=f"Filepath: {self._storage_filepath}",
                )

    def _flush_to_storage(self) -> None:
        dir_name = os.path.dirname(self._storage_filepath)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)

        intents_list = [intent.to_dict() for intent in self._intents_by_id.values()]
        payload = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "updated_at": time.time(),
            "intents": intents_list,
        }

        tmp_path = f"{self._storage_filepath}.tmp.{int(time.time()*1000)}"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)

            os.replace(tmp_path, self._storage_filepath)
        except Exception as exc:
            if self._audit_control is not None and hasattr(self._audit_control, "record_failure"):
                self._audit_control.record_failure(
                    component="FileBackedOrderIntentRepository",
                    error_type="STORAGE_WRITE_FAILURE",
                    message=f"Failed flushing OrderIntents: {str(exc)}",
                    diagnostic_details=f"Filepath: {self._storage_filepath}",
                )
            raise

    def save_order_intent(self, intent: OrderIntent) -> OrderIntent:
        if not isinstance(intent, OrderIntent):
            raise ValueError("intent must be an OrderIntent instance")

        self._intents_by_id[intent.order_intent_id] = intent
        if intent.idempotency_key:
            key = f"{intent.user_id}:{intent.idempotency_key}"
            self._idempotency_map[key] = intent.order_intent_id

        self._flush_to_storage()
        return intent

    def get_order_intent(
        self, order_intent_id: str, user_id: Optional[str] = None
    ) -> Optional[OrderIntent]:
        intent = self._intents_by_id.get(order_intent_id)
        if intent is None:
            return None
        if user_id is not None and intent.user_id != user_id and user_id != "admin":
            return None
        return intent

    def get_by_idempotency_key(
        self, user_id: str, idempotency_key: str
    ) -> Optional[OrderIntent]:
        key = f"{user_id}:{idempotency_key}"
        intent_id = self._idempotency_map.get(key)
        if intent_id:
            return self._intents_by_id.get(intent_id)
        return None

    def list_order_intents(
        self,
        user_id: Optional[str] = None,
        symbol: Optional[str] = None,
        lifecycle_state: Optional[str] = None,
        limit: int = 100,
    ) -> List[OrderIntent]:
        results: List[OrderIntent] = []
        clean_symbol = symbol.strip().upper() if symbol and symbol.strip() else None
        clean_ls = lifecycle_state.strip().upper() if lifecycle_state and lifecycle_state.strip() else None

        for intent in self._intents_by_id.values():
            if user_id is not None and intent.user_id != user_id and user_id != "admin":
                continue
            if clean_symbol and intent.symbol != clean_symbol:
                continue
            if clean_ls and intent.lifecycle_state.value != clean_ls:
                continue
            results.append(intent)

        # Sort descending by creation timestamp
        results.sort(key=lambda x: x.creation_timestamp, reverse=True)
        return results[:limit]
