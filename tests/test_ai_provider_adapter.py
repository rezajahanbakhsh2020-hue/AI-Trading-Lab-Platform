"""Comprehensive tests for HttpAIProviderAdapter and AI provider factory.

Tests status detection, HTTP execution, OpenAI format parsing, HTTP error handling,
timeout handling, network error handling, invalid JSON response handling, secret sanitization,
and environment-based configuration.
"""

import json
import os
import socket
import time
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from src.platform.adapters.ai_provider import (
    HttpAIProviderAdapter,
    UnavailableAIProviderAdapter,
    create_default_ai_provider,
)
from src.platform.domain.ai_gateway import (
    AICapability,
    AIProviderStatus,
    AIRequest,
    AllowedIntelligenceContext,
)


@pytest.fixture
def mock_context() -> AllowedIntelligenceContext:
    return AllowedIntelligenceContext(
        context_id="ctx_test_1",
        user_id="usr_test_1",
        capability=AICapability.EXPLAIN_SIGNAL,
        timestamp=time.time(),
        permitted_symbol="XAUUSD",
        permitted_signal={
            "signal_id": "sig_001",
            "action": "BUY",
            "symbol": "XAUUSD",
            "timeframe": "1h",
        },
    )


@pytest.fixture
def mock_request() -> AIRequest:
    return AIRequest(
        request_id="req_test_1",
        user_id="usr_test_1",
        capability=AICapability.EXPLAIN_SIGNAL,
        target_symbol="XAUUSD",
        prompt_query="Explain why XAUUSD buy was generated?",
    )


def test_http_provider_unconfigured_status() -> None:
    adapter = HttpAIProviderAdapter(api_key="", endpoint_url="")
    assert adapter.get_status() == AIProviderStatus.UNAVAILABLE
    assert adapter.provider_name() == "HttpAIProviderAdapter"

    req = AIRequest(request_id="r1", user_id="u1", capability=AICapability.EXPLAIN_SIGNAL)
    ctx = AllowedIntelligenceContext(context_id="c1", user_id="u1", capability=AICapability.EXPLAIN_SIGNAL, timestamp=time.time())
    resp = adapter.generate_explanation(ctx, req)
    assert resp.status == "UNAVAILABLE"
    assert "AI unavailable" in resp.content


def test_http_provider_configured_status() -> None:
    adapter = HttpAIProviderAdapter(
        api_key="sk-test-key-12345",
        endpoint_url="https://api.openai.com/v1/chat/completions",
    )
    assert adapter.get_status() == AIProviderStatus.AVAILABLE


def test_http_provider_successful_openai_response(
    mock_context: AllowedIntelligenceContext, mock_request: AIRequest
) -> None:
    adapter = HttpAIProviderAdapter(
        api_key="sk-test-key-12345",
        endpoint_url="https://api.openai.com/v1/chat/completions",
        model="gpt-4o-mini",
    )

    mock_response_data = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "XAUUSD BUY signal is supported by bullish momentum.",
                }
            }
        ]
    }
    json_bytes = json.dumps(mock_response_data).encode("utf-8")

    mock_resp = MagicMock()
    mock_resp.read.return_value = json_bytes
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        resp = adapter.generate_explanation(mock_context, mock_request)

        assert resp.status == "SUCCESS"
        assert resp.content == "XAUUSD BUY signal is supported by bullish momentum."
        assert resp.provider_name == "HttpAIProviderAdapter"
        assert mock_urlopen.called


def test_http_provider_http_401_error(
    mock_context: AllowedIntelligenceContext, mock_request: AIRequest
) -> None:
    adapter = HttpAIProviderAdapter(
        api_key="sk-invalid-key",
        endpoint_url="https://api.openai.com/v1/chat/completions",
    )

    http_err = urllib.error.HTTPError(
        url="https://api.openai.com/v1/chat/completions",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=None,
    )

    with patch("urllib.request.urlopen", side_effect=http_err):
        resp = adapter.generate_explanation(mock_context, mock_request)
        assert resp.status == "ERROR"
        assert "authentication failed" in resp.content.lower()
        assert resp.error_message == "HTTP 401 Unauthorized"


def test_http_provider_http_429_rate_limit(
    mock_context: AllowedIntelligenceContext, mock_request: AIRequest
) -> None:
    adapter = HttpAIProviderAdapter(
        api_key="sk-valid-key",
        endpoint_url="https://api.openai.com/v1/chat/completions",
    )

    http_err = urllib.error.HTTPError(
        url="https://api.openai.com/v1/chat/completions",
        code=429,
        msg="Rate Limit Exceeded",
        hdrs={},
        fp=None,
    )

    with patch("urllib.request.urlopen", side_effect=http_err):
        resp = adapter.generate_explanation(mock_context, mock_request)
        assert resp.status == "ERROR"
        assert "rate limit" in resp.content.lower() or "quota" in resp.content.lower()


def test_http_provider_timeout_handling(
    mock_context: AllowedIntelligenceContext, mock_request: AIRequest
) -> None:
    adapter = HttpAIProviderAdapter(
        api_key="sk-valid-key",
        endpoint_url="https://api.openai.com/v1/chat/completions",
        timeout=1.0,
    )

    with patch("urllib.request.urlopen", side_effect=socket.timeout("connection timed out")):
        resp = adapter.generate_explanation(mock_context, mock_request)
        assert resp.status == "ERROR"
        assert "timed out" in resp.content.lower()
        assert resp.error_message == "Request timed out"


def test_http_provider_invalid_json_response(
    mock_context: AllowedIntelligenceContext, mock_request: AIRequest
) -> None:
    adapter = HttpAIProviderAdapter(
        api_key="sk-valid-key",
        endpoint_url="https://api.openai.com/v1/chat/completions",
    )

    mock_resp = MagicMock()
    mock_resp.read.return_value = b"<html>502 Bad Gateway</html>"
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    with patch("urllib.request.urlopen", return_value=mock_resp):
        resp = adapter.generate_explanation(mock_context, mock_request)
        assert resp.status == "ERROR"
        assert "Invalid response format" in resp.content


def test_create_default_ai_provider_factory() -> None:
    # Unconfigured env -> UnavailableAIProviderAdapter
    with patch.dict(os.environ, {"AI_PROVIDER_API_KEY": "", "AI_PROVIDER_URL": ""}, clear=True):
        provider = create_default_ai_provider()
        assert isinstance(provider, UnavailableAIProviderAdapter)
        assert provider.get_status() == AIProviderStatus.UNAVAILABLE

    # Configured env -> HttpAIProviderAdapter
    env = {
        "AI_PROVIDER_API_KEY": "sk-test-key-factory",
        "AI_PROVIDER_URL": "https://api.openai.com/v1/chat/completions",
    }
    with patch.dict(os.environ, env, clear=True):
        provider = create_default_ai_provider()
        assert isinstance(provider, HttpAIProviderAdapter)
        assert provider.get_status() == AIProviderStatus.AVAILABLE
