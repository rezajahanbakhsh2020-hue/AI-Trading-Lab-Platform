"""Execution gateway integration port.

Outbound Ports-and-Adapters boundary for submitting ExecutionRequestCommands
derived from authorized OrderIntents to downstream execution providers.
Concrete broker or venue execution adapters will live behind this port.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict

from src.platform.domain.execution_gateway import (
    ExecutionAttemptResult,
    ExecutionRequestCommand,
)


class ExecutionGatewayPort(ABC):
    """Abstract outbound port for requesting order intent execution at the boundary."""

    @abstractmethod
    def request_execution(
        self, command: ExecutionRequestCommand
    ) -> ExecutionAttemptResult:
        """Submit an ExecutionRequestCommand to the boundary adapter."""
        raise NotImplementedError

    @abstractmethod
    def describe(self) -> Dict[str, Any]:
        """Return an I/O-free description of the execution gateway provider boundary."""
        raise NotImplementedError
