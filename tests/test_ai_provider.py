from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
import requests

from daily_knowledge_learning.ai_provider import (
    AIRateLimitError,
    AIResponseError,
    AITimeoutError,
    AIUnavailableError,
    AnthropicProvider,
    MockProvider,
    OpenAIProvider,
    get_provider,
)


# --- MockProvider ---

def test_mock_provider_cycles_responses() -> None:
    provider = MockProvider(["第一", "第二"])

    assert provider.chat([]) == "第一"
    assert provider.chat([]) == "第二"
    assert provider.chat([]) == "第一"


def test_mock_provider_is_always_available() -> None:
    assert MockProvider().is_available() is True


def test_mock_provider_delay() -> None:
    provider = MockProvider(delay=0.01)

    assert provider.chat([])


def test_mock_provider_delay_beyond_timeout_raises() -> None:
    provider = MockProvider(delay=5.0)

    with pytest.raises(AITimeoutError):
        provider.chat([], timeout=0.01)


def test_mock_provider_structured_output_matches_schema() -> None:
    import json

    provider = MockProvider()
    schema = {
        "type": "object",
        "properties": {"summary": {"type": "string"}, "score": {"type": "integer"}},
        "required": ["summary", "score"],
    }

    result = json.loads(provider.chat([], schema=schema))

    assert isinstance(result["summary"], str)
    assert isinstance(result["score"], int)


def test_mock_provider_rejects_negative_delay() -> None:
    with pytest.raises(ValueError):
        MockProvider(delay=-1)


# --- OpenAIProvider availability ---

def test_openai_is_available_without_key() -> None:
    assert OpenAIProvider(api_key="").is_available() is False


def test_openai_is_available_with_key() -> None:
    assert OpenAIProvider(api_key="sk-test").is_available() is True


def test_openai_chat_without_key_raises() -> None:
    provider = OpenAIProvider(api_key="")

    with pytest.raises(AIUnavailableError):
        provider.chat([])


# --- OpenAIProvider responses ---

def _response(status: int, payload: dict) -> Mock:
    response = Mock()
    response.status_code = status
    response.json.return_value = payload
    return response


def test_openai_parses_normal_response() -> None:
    provider = OpenAIProvider(api_key="sk-test")
    payload = {"choices": [{"message": {"content": "你好"}}]}

    with patch("daily_knowledge_learning.ai_provider.requests.post", return_value=_response(200, payload)):
        assert provider.chat([]) == "你好"


def test_openai_timeout_becomes_ai_timeout() -> None:
    provider = OpenAIProvider(api_key="sk-test")

    with patch(
        "daily_knowledge_learning.ai_provider.requests.post",
        side_effect=requests.Timeout(),
    ):
        with pytest.raises(AITimeoutError):
            provider.chat([])


def test_openai_rate_limit_becomes_ai_rate_limit() -> None:
    provider = OpenAIProvider(api_key="sk-test")

    with patch("daily_knowledge_learning.ai_provider.requests.post", return_value=_response(429, {})):
        with pytest.raises(AIRateLimitError):
            provider.chat([])


def test_openai_server_error_becomes_response_error() -> None:
    provider = OpenAIProvider(api_key="sk-test")

    with patch("daily_knowledge_learning.ai_provider.requests.post", return_value=_response(500, {})):
        with pytest.raises(AIResponseError):
            provider.chat([])


def test_openai_malformed_payload_becomes_response_error() -> None:
    provider = OpenAIProvider(api_key="sk-test")

    with patch("daily_knowledge_learning.ai_provider.requests.post", return_value=_response(200, {"nope": 1})):
        with pytest.raises(AIResponseError):
            provider.chat([])


def test_openai_invalid_structured_output_is_rejected() -> None:
    provider = OpenAIProvider(api_key="sk-test")
    payload = {"choices": [{"message": {"content": "not json"}}]}
    schema = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}

    with patch("daily_knowledge_learning.ai_provider.requests.post", return_value=_response(200, payload)):
        with pytest.raises(AIResponseError):
            provider.chat([], schema=schema)


# --- AnthropicProvider ---

def test_anthropic_parses_normal_response() -> None:
    provider = AnthropicProvider(api_key="sk-ant")
    payload = {"content": [{"type": "text", "text": "回答"}]}

    with patch("daily_knowledge_learning.ai_provider.requests.post", return_value=_response(200, payload)):
        assert provider.chat([{"role": "user", "content": "问题"}]) == "回答"


def test_anthropic_moves_system_message_to_top_level() -> None:
    provider = AnthropicProvider(api_key="sk-ant")
    payload = {"content": [{"type": "text", "text": "ok"}]}

    with patch(
        "daily_knowledge_learning.ai_provider.requests.post",
        return_value=_response(200, payload),
    ) as post:
        provider.chat(
            [{"role": "system", "content": "系统设定"}, {"role": "user", "content": "问题"}]
        )

    sent = post.call_args.kwargs["json"]
    assert sent["system"] == "系统设定"
    assert all(item["role"] != "system" for item in sent["messages"])


def test_anthropic_non_2xx_becomes_response_error() -> None:
    provider = AnthropicProvider(api_key="sk-ant")

    with patch("daily_knowledge_learning.ai_provider.requests.post", return_value=_response(400, {})):
        with pytest.raises(AIResponseError):
            provider.chat([])


# --- Factory ---

def test_get_provider_returns_mock() -> None:
    assert isinstance(get_provider("mock"), MockProvider)


def test_get_provider_returns_openai() -> None:
    assert isinstance(get_provider("openai", model="gpt-4o-mini"), OpenAIProvider)


def test_get_provider_returns_anthropic() -> None:
    assert isinstance(get_provider("anthropic"), AnthropicProvider)


def test_get_provider_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        get_provider("unknown")
