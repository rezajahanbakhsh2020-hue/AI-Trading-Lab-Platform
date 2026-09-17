"""Unavailable execution gateway adapter.

Explicit fail-closed execution adapter that rejects all execution requests
when no external execution provider or broker is configured.
Ensures externally_executed is ALWAYS False and never fabricates fills or executions.
"""

import time
from typing import Any, Dict

from src.platform.domain.execution_gateway import (
    ExecutionAttemptResult,
    ExecutionBoundaryStatus,
    ExecutionReconciliationRecord,
    ExecutionReconciliationStatus,
    ExecutionRequestCommand,
)
from src.platform.integrations.execution_gateway import (
    ExecutionGatewayPort,
    ExecutionReconciliationPort,
)


class UnavailableExecutionAdapter(ExecutionGatewayPort):
    """Adapter for unconfigured execution gateway environment.

    Rejects all execution attempts with explicit UNCONFIGURED / REJECTED_UNAVAILABLE status.
    """

    def __init__(self, provider_id: str = "unavailable_execution_adapter") -> None:
        self.provider_id = provider_id

    def request_execution(
        self, command: ExecutionRequestCommand
    ) -> ExecutionAttemptResult:
        if not isinstance(command, ExecutionRequestCommand):
            raise ValueError("command must be an ExecutionRequestCommand instance")

        return ExecutionAttemptResult(
            success=False,
            user_id=command.user_id,
            order_intent_id=command.order_intent_id,
            status=ExecutionBoundaryStatus.UNCONFIGURED,
            reason="No external execution provider configured for Project 2 Execution Gateway.",
            externally_executed=False,
            detail="Project 2 host operates without real broker/exchange connections. Execution disabled.",
            timestamp=time.time(),
            provider_id=self.provider_id,
        )

    def describe(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "configured": False,
            "connected": False,
            "allows_execution": False,
            "message": "Execution gateway unconfigured. Real broker execution adapter is omitted.",
        }


class UnavailableExecutionReconciliationAdapter(ExecutionReconciliationPort):
    """Adapter for unconfigured execution reconciliation environment.

    Returns empty evidence with configured=False and allows_reconciliation=False.
    """

    def __init__(self, provider_id: str = "unavailable_execution_reconciliation_adapter") -> None:
        self.provider_id = provider_id

    def fetch_external_evidence(
        self, order_intent_id: str, user_id: str
    ) -> Dict[str, Any]:
        return {
            "configured": False,
            "connected": False,
            "external_evidence_found": False,
            "external_state": None,
            "externally_executed": False,
            "provider_id": self.provider_id,
            "message": "No external execution provider is configured for Project 2.",
        }

    def describe(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "configured": False,
            "connected": False,
            "allows_reconciliation": False,
            "message": "Execution reconciliation adapter unconfigured. External evidence unavailable.",
        }
