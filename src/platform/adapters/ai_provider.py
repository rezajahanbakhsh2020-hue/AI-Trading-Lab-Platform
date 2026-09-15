"""AI Provider Port contract and default unavailable provider adapter.

Defines the abstract AIProviderPort interface and a safe UnavailableAIProviderAdapter
for production readiness when no external AI vendor is configured.
"""

from abc import ABC, abstractmethod
import time
from typing import Any, Dict, Optional

from src.platform.domain.ai_gateway import (
    AICapability,
    AIProviderStatus,
    AIRequest,
    AIResponse,
    AllowedIntelligenceContext,
)


class AIProviderPort(ABC):
    """Abstract port for configurable AI providers (cloud, local model, or mock)."""

    @abstractmethod
    def get_status(self) -> AIProviderStatus:
        """Return the current operational status of the AI provider."""
        pass

    @abstractmethod
    def provider_name(self) -> str:
        """Return the unique provider name or identifier."""
        pass

    @abstractmethod
    def generate_explanation(
        self, context: AllowedIntelligenceContext, request: AIRequest
    ) -> AIResponse:
        """Generate an AI explanation/summary consuming only the permitted context."""
        pass


class UnavailableAIProviderAdapter(AIProviderPort):
    """Default adapter returned when no external AI provider is configured.

    Ensures honest reporting ('AI unavailable / provider not configured') without fake AI data.
    """

    def __init__(self, message: str = "AI unavailable / provider not configured") -> None:
        self._message = message

    def get_status(self) -> AIProviderStatus:
        return AIProviderStatus.UNAVAILABLE

    def provider_name(self) -> str:
        return "UnavailableAIProviderAdapter"

    def generate_explanation(
        self, context: AllowedIntelligenceContext, request: AIRequest
    ) -> AIResponse:
        return AIResponse(
            request_id=request.request_id,
            status="UNAVAILABLE",
            capability=request.capability,
            provider_name=self.provider_name(),
            content=self._message,
            created_at=time.time(),
            context_summary=context.to_dict(),
            error_message="No real AI provider adapter attached.",
        )
