"""Provider boundary for AI requests; credentials and HTTP details stay local."""

from __future__ import annotations

import json
import time
from itertools import cycle
from typing import Protocol, runtime_checkable

import requests

from . import config


class AIProviderError(Exception):
    """Base class for user-presentable AI request failures."""


class AITimeoutError(AIProviderError):
    """The provider did not respond before the timeout."""


class AIRateLimitError(AIProviderError):
    """The provider rejected the request due to rate limits."""


class AIResponseError(AIProviderError):
    """The provider returned an invalid or unsuccessful response."""


class AIUnavailableError(AIProviderError):
    """The provider is not configured for use."""


@runtime_checkable
class AIProvider(Protocol):
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        schema: dict | None = None,
        timeout: float = 30.0,
    ) -> str:
        """Send messages and return assistant text, optionally as JSON."""
        ...

    def is_available(self) -> bool:
        """Check local configuration without making a network request."""
        ...


_DEFAULT_RESPONSES = ("我们可以从一个具体例子开始，看看这个知识点如何解释你的观察。",)


def _schema_example(schema: dict) -> object:
    """Create a small valid-shaped value for the common JSON Schema subset."""
    if "enum" in schema:
        return schema["enum"][0] if schema["enum"] else None
    kind = schema.get("type")
    if kind == "object" or "properties" in schema:
        properties = schema.get("properties", {})
        required = schema.get("required", list(properties))
        return {key: _schema_example(properties[key]) for key in required if key in properties}
    if kind == "array":
        return [_schema_example(schema.get("items", {}))]
    if kind == "string":
        return "示例"
    if kind == "integer":
        return 1
    if kind == "number":
        return 1.0
    if kind == "boolean":
        return True
    if kind == "null":
        return None
    return {}


def _validate_schema_value(value: object, schema: dict, path: str = "$") -> None:
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(path)
    kind = schema.get("type")
    expected = {
        "object": dict,
        "array": list,
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "null": type(None),
    }.get(kind)
    if expected and (
        not isinstance(value, expected)
        or (kind == "integer" and isinstance(value, bool))
        or (kind == "number" and isinstance(value, bool))
    ):
        raise ValueError(path)
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise ValueError(f"{path}.{key}")
        for key, child_schema in schema.get("properties", {}).items():
            if key in value:
                _validate_schema_value(value[key], child_schema, f"{path}.{key}")
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            _validate_schema_value(item, schema["items"], f"{path}[{index}]")


def _structured_text(content: str, schema: dict | None) -> str:
    if schema is None:
        return content
    try:
        parsed = json.loads(content)
        _validate_schema_value(parsed, schema)
    except (json.JSONDecodeError, TypeError, ValueError):
        raise AIResponseError("AI 返回的结构化内容格式无效，请重试。") from None
    return content


class MockProvider:
    def __init__(self, responses: list[str] | None = None, *, delay: float = 0.0):
        if delay < 0:
            raise ValueError("模拟延迟不能小于 0 秒。")
        self._responses = cycle(responses or _DEFAULT_RESPONSES)
        self._delay = delay

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        schema: dict | None = None,
        timeout: float = 30.0,
    ) -> str:
        if self._delay > timeout:
            time.sleep(max(timeout, 0))
            raise AITimeoutError("AI 请求超时，请稍后重试。")
        if self._delay:
            time.sleep(self._delay)
        if schema is not None:
            return json.dumps(_schema_example(schema), ensure_ascii=False)
        return next(self._responses)

    def is_available(self) -> bool:
        return True


class _HTTPProvider:
    api_key: str | None

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _check_available(self) -> None:
        if not self.is_available():
            raise AIUnavailableError("尚未配置此 AI 服务的 API 密钥。")

    @staticmethod
    def _raise_request_error(error: requests.RequestException) -> None:
        if isinstance(error, requests.Timeout):
            raise AITimeoutError("AI 请求超时，请稍后重试。") from None
        raise AIResponseError("无法连接 AI 服务，请检查网络后重试。") from None

    @staticmethod
    def _check_status(response: requests.Response) -> None:
        if response.status_code == 429:
            raise AIRateLimitError("AI 服务请求过于频繁，请稍后重试。")
        if not 200 <= response.status_code < 300:
            raise AIResponseError("AI 服务暂时无法处理请求，请稍后重试。")


class OpenAIProvider(_HTTPProvider):
    def __init__(self, *, model: str = "gpt-4o-mini", api_key: str | None = None):
        self.model = model
        self.api_key = api_key if api_key is not None else config.get_api_key("openai")

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        schema: dict | None = None,
        timeout: float = 30.0,
    ) -> str:
        self._check_available()
        payload: dict = {"model": self.model, "messages": messages}
        if schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response", "strict": True, "schema": schema},
            }
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=timeout,
            )
        except requests.RequestException as error:
            self._raise_request_error(error)
        self._check_status(response)
        try:
            content = response.json()["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError
        except (ValueError, KeyError, IndexError, TypeError):
            raise AIResponseError("AI 服务返回了无法识别的响应，请重试。") from None
        return _structured_text(content, schema)


class AnthropicProvider(_HTTPProvider):
    def __init__(self, *, model: str = "claude-opus-5-5", api_key: str | None = None):
        self.model = model
        self.api_key = api_key if api_key is not None else config.get_api_key("anthropic")

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        schema: dict | None = None,
        timeout: float = 30.0,
    ) -> str:
        self._check_available()
        system_messages = [item["content"] for item in messages if item.get("role") == "system"]
        conversation = [item for item in messages if item.get("role") != "system"]
        payload: dict = {"model": self.model, "max_tokens": 1024, "messages": conversation}
        if system_messages:
            payload["system"] = "\n".join(system_messages)
        if schema is not None:
            payload["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key or "",
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
                timeout=timeout,
            )
        except requests.RequestException as error:
            self._raise_request_error(error)
        self._check_status(response)
        try:
            blocks = response.json()["content"]
            content = "".join(block["text"] for block in blocks if block.get("type") == "text")
            if not content:
                raise ValueError
        except (ValueError, KeyError, TypeError):
            raise AIResponseError("AI 服务返回了无法识别的响应，请重试。") from None
        return _structured_text(content, schema)


def get_provider(provider_name: str, *, model: str | None = None) -> AIProvider:
    """Build a provider by its configuration name."""
    name = provider_name.lower()
    if name == "mock":
        return MockProvider()
    if name == "openai":
        return OpenAIProvider(model=model or "gpt-4o-mini")
    if name == "anthropic":
        return AnthropicProvider(model=model or "claude-opus-5-5")
    raise ValueError(f"不支持的 AI 服务提供方：{provider_name}")
