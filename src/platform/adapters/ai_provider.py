"""AI Provider Port contract and replaceable provider adapters.

Defines the abstract AIProviderPort interface, a safe UnavailableAIProviderAdapter
for production when unconfigured, an HttpAIProviderAdapter for connecting real HTTP/LLM APIs,
and a factory function create_default_ai_provider.
"""

from abc import ABC, abstractmethod
import json
import os
import socket
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Union

from src.platform.domain.ai_gateway import (
    AICapability,
    AIProviderStatus,
    AIRequest,
    AIResponse,
    AllowedIntelligenceContext,
)
from src.platform.providers.http import read_limited
from src.platform.services.security import SecretSanitizer


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


def _format_prompt_messages(
    context: AllowedIntelligenceContext, request: AIRequest
) -> List[Dict[str, str]]:
    """Format sanitized, user-scoped AllowedIntelligenceContext into standard chat prompt messages."""
    system_message = (
        "You are a Trading Intelligence AI assistant. Provide concise, clear, and "
        "objective explanations based ONLY on the permitted context provided. "
        "Do NOT provide financial advice, invent strategy formulas, or expose private parameters."
    )

    query_part = (
        f"\nUser Question: {SecretSanitizer.sanitize_string(request.prompt_query)}"
        if request.prompt_query
        else ""
    )

    user_message = (
        f"Capability: {context.capability.value}\n"
        f"Symbol: {context.permitted_symbol or 'N/A'}\n"
        f"Signal Context: {json.dumps(context.permitted_signal) if context.permitted_signal else 'None'}\n"
        f"Market Context: {json.dumps(context.permitted_market) if context.permitted_market else 'None'}\n"
        f"Timeline Event Count: {len(context.permitted_timeline)}\n"
        f"Health Context: {json.dumps(context.permitted_health) if context.permitted_health else 'None'}"
        f"{query_part}"
    )

    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message},
    ]


class HttpAIProviderAdapter(AIProviderPort):
    """Replaceable HTTP AI provider adapter supporting OpenAI-compatible or generic HTTP LLM endpoints.

    Fully configured via runtime environment variables or explicit parameters.
    Returns honest UNAVAILABLE or ERROR states when unconfigured or network/API errors occur.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[Union[float, int, str]] = None,
        provider_name_override: Optional[str] = None,
    ) -> None:
        raw_key = api_key if api_key is not None else os.getenv("AI_PROVIDER_API_KEY", "")
        self._api_key = str(raw_key).strip()

        raw_url = endpoint_url if endpoint_url is not None else os.getenv("AI_PROVIDER_URL", "")
        self._endpoint_url = str(raw_url).strip()

        raw_model = model if model is not None else os.getenv("AI_PROVIDER_MODEL", "gpt-4o-mini")
        self._model = str(raw_model).strip() or "gpt-4o-mini"

        if timeout is not None:
            try:
                self._timeout = max(0.1, float(timeout))
            except (ValueError, TypeError):
                self._timeout = 5.0
        else:
            try:
                self._timeout = max(0.1, float(os.getenv("AI_PROVIDER_TIMEOUT", "5.0")))
            except (ValueError, TypeError):
                self._timeout = 5.0

        self._provider_name = str(provider_name_override).strip() if provider_name_override else "HttpAIProviderAdapter"

    def get_status(self) -> AIProviderStatus:
        if (
            self._api_key
            and self._endpoint_url
            and not self._api_key.lower().startswith("placeholder")
            and not self._api_key.lower().startswith("your_api_key")
            and (self._endpoint_url.startswith("http://") or self._endpoint_url.startswith("https://"))
        ):
            return AIProviderStatus.AVAILABLE
        return AIProviderStatus.UNAVAILABLE

    def provider_name(self) -> str:
        return self._provider_name

    def generate_explanation(
        self, context: AllowedIntelligenceContext, request: AIRequest
    ) -> AIResponse:
        if self.get_status() != AIProviderStatus.AVAILABLE:
            return AIResponse(
                request_id=request.request_id,
                status="UNAVAILABLE",
                capability=request.capability,
                provider_name=self.provider_name(),
                content="AI unavailable / provider not configured",
                created_at=time.time(),
                context_summary=context.to_dict(),
                error_message="AI provider API key or endpoint URL is not configured.",
            )

        messages = _format_prompt_messages(context, request)
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 500,
        }

        json_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
            "User-Agent": "AI-Trading-Lab-Platform/1.0",
        }

        req = urllib.request.Request(
            url=self._endpoint_url,
            data=json_bytes,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw_data = read_limited(resp)
                data = json.loads(raw_data.decode("utf-8"))

                content = ""
                if isinstance(data, dict):
                    if (
                        "choices" in data
                        and isinstance(data["choices"], list)
                        and len(data["choices"]) > 0
                    ):
                        choice = data["choices"][0]
                        if (
                            isinstance(choice, dict)
                            and "message" in choice
                            and isinstance(choice["message"], dict)
                        ):
                            content = choice["message"].get("content", "").strip()
                    elif "content" in data and isinstance(data["content"], str):
                        content = data["content"].strip()
                    elif "explanation" in data and isinstance(data["explanation"], str):
                        content = data["explanation"].strip()

                if not content:
                    content = "AI response received, but no text content could be extracted."

                return AIResponse(
                    request_id=request.request_id,
                    status="SUCCESS",
                    capability=request.capability,
                    provider_name=self.provider_name(),
                    content=SecretSanitizer.sanitize_string(content),
                    created_at=time.time(),
                    context_summary=context.to_dict(),
                )

        except urllib.error.HTTPError as http_err:
            status_code = http_err.code
            if status_code in (401, 403):
                err_content = "AI provider authentication failed."
                err_msg = f"HTTP {status_code} Unauthorized"
            elif status_code == 429:
                err_content = "AI provider rate limit or quota exceeded."
                err_msg = "HTTP 429 Rate Limit Exceeded"
            elif status_code >= 500:
                err_content = "AI provider service error."
                err_msg = f"HTTP {status_code} Server Error"
            else:
                err_content = f"AI provider returned HTTP status {status_code}."
                err_msg = f"HTTP {status_code}"

            return AIResponse(
                request_id=request.request_id,
                status="ERROR",
                capability=request.capability,
                provider_name=self.provider_name(),
                content=err_content,
                created_at=time.time(),
                context_summary=context.to_dict(),
                error_message=err_msg,
            )

        except (urllib.error.URLError, socket.timeout) as net_err:
            is_timeout = isinstance(net_err, socket.timeout) or (
                isinstance(net_err, urllib.error.URLError)
                and isinstance(net_err.reason, socket.timeout)
            )
            if is_timeout:
                return AIResponse(
                    request_id=request.request_id,
                    status="ERROR",
                    capability=request.capability,
                    provider_name=self.provider_name(),
                    content="AI provider request timed out.",
                    created_at=time.time(),
                    context_summary=context.to_dict(),
                    error_message="Request timed out",
                )

            err_reason = str(getattr(net_err, "reason", net_err))
            sanitized_reason = SecretSanitizer.sanitize_string(err_reason)
            return AIResponse(
                request_id=request.request_id,
                status="ERROR",
                capability=request.capability,
                provider_name=self.provider_name(),
                content="Unable to reach AI provider endpoint.",
                created_at=time.time(),
                context_summary=context.to_dict(),
                error_message=f"Network error: {sanitized_reason}",
            )

        except (json.JSONDecodeError, KeyError, ValueError) as parse_err:
            return AIResponse(
                request_id=request.request_id,
                status="ERROR",
                capability=request.capability,
                provider_name=self.provider_name(),
                content="Invalid response format received from AI provider.",
                created_at=time.time(),
                context_summary=context.to_dict(),
                error_message=f"Parse error: {SecretSanitizer.sanitize_string(str(parse_err))}",
            )

        except Exception as gen_err:
            clean_err = SecretSanitizer.sanitize_string(str(gen_err))
            return AIResponse(
                request_id=request.request_id,
                status="ERROR",
                capability=request.capability,
                provider_name=self.provider_name(),
                content="An error occurred while communicating with the AI provider.",
                created_at=time.time(),
                context_summary=context.to_dict(),
                error_message=clean_err,
            )


def create_default_ai_provider() -> AIProviderPort:
    """Factory helper creating configured HttpAIProviderAdapter if environment variables are set, else UnavailableAIProviderAdapter."""
    try:
        http_adapter = HttpAIProviderAdapter()
        if http_adapter.get_status() == AIProviderStatus.AVAILABLE:
            return http_adapter
    except Exception:
        pass
    return UnavailableAIProviderAdapter()
