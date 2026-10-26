from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .subjects import BUILTIN_SUBJECTS, normalize_custom_subjects

SERVICE_NAME = "daily-knowledge-learning"
OPENAI_COMPATIBLE_PROVIDERS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "siliconflow": "https://api.siliconflow.cn/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "custom": "",
}
_PROVIDERS = {*OPENAI_COMPATIBLE_PROVIDERS, "anthropic", "mock"}


@dataclass(frozen=True, slots=True)
class AppConfig:
    vault_path: Path = Path("")
    ai_provider: str = "mock"
    model: str = ""
    auto_save_interval: int = 30
    custom_subjects: tuple[str, ...] = ()
    api_base_url: str = ""
    api_protocol: str = "openai"


def config_file_path() -> Path:
    override = os.environ.get("DAILY_KNOWLEDGE_LEARNING_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / SERVICE_NAME / "config.json"


def _validated(config: AppConfig, *, require_vault: bool) -> AppConfig:
    if not isinstance(config.vault_path, Path):
        raise TypeError("vault_path must be a pathlib.Path")
    if config.ai_provider not in _PROVIDERS:
        raise ValueError(f"ai_provider must be one of {sorted(_PROVIDERS)}")
    if not isinstance(config.model, str):
        raise TypeError("model must be a string")
    if not isinstance(config.api_base_url, str):
        raise TypeError("api_base_url must be a string")
    if config.api_protocol not in {"openai", "anthropic"}:
        raise ValueError("api_protocol must be 'openai' or 'anthropic'")
    if config.api_base_url and not config.api_base_url.startswith(("https://", "http://")):
        raise ValueError("api_base_url must start with http:// or https://")
    if isinstance(config.auto_save_interval, bool) or not isinstance(config.auto_save_interval, int):
        raise TypeError("auto_save_interval must be an integer")
    if config.auto_save_interval < 1:
        raise ValueError("auto_save_interval must be positive")
    normalize_custom_subjects(config.custom_subjects)
    if require_vault and config.vault_path != Path("") and not config.vault_path.is_dir():
        raise ValueError(f"vault_path does not exist or is not a directory: {config.vault_path}")
    return config


def _set_private_permissions(path: Path) -> None:
    if os.name == "nt":
        identity = os.environ.get("USERDOMAIN", "") + "\\" + os.environ.get("USERNAME", "")
        if identity == "\\":
            raise OSError("cannot determine current Windows user for config ACL")
        result = subprocess.run(
            ["icacls", str(path), "/inheritance:r", "/grant:r", f"{identity}:(F)"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise OSError(f"could not restrict config permissions: {result.stderr.strip()}")
    else:
        path.chmod(0o600)


def _serialize(config: AppConfig) -> dict[str, Any]:
    values = asdict(config)
    values["vault_path"] = str(config.vault_path)
    values["custom_subjects"] = list(config.custom_subjects)
    return values


def save_config(config: AppConfig, path: Path | None = None) -> None:
    config = _validated(config, require_vault=True)
    destination = Path(path) if path is not None else config_file_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=destination.parent,
            prefix=f".{destination.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(_serialize(config), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        _set_private_permissions(temp_path)
        os.replace(temp_path, destination)
        _set_private_permissions(destination)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def load_config(path: Path | None = None) -> AppConfig:
    source = Path(path) if path is not None else config_file_path()
    if not source.exists():
        return AppConfig()
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid config file {source}: {error}") from error
    if not isinstance(raw, dict):
        raise ValueError(f"config file must contain a JSON object: {source}")
    try:
        config = AppConfig(
            vault_path=Path(raw.get("vault_path", "")).expanduser(),
            ai_provider=raw.get("ai_provider", "mock"),
            model=raw.get("model", ""),
            auto_save_interval=raw.get("auto_save_interval", 60),
            custom_subjects=tuple(raw.get("custom_subjects", ())),
            api_base_url=raw.get("api_base_url", ""),
            api_protocol=raw.get("api_protocol", "openai"),
        )
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid config values in {source}: {error}") from error
    return _validated(config, require_vault=True)


def _keyring():
    import keyring

    return keyring


def _credential_name(provider: str) -> str:
    return provider if provider in {"openai", "anthropic"} else f"api:{provider}"


def get_api_key(provider: str) -> str | None:
    if provider not in _PROVIDERS - {"mock"}:
        raise ValueError(f"unsupported API key provider: {provider}")
    return _keyring().get_password(SERVICE_NAME, _credential_name(provider))


def set_api_key(provider: str, key: str) -> None:
    if provider not in _PROVIDERS - {"mock"}:
        raise ValueError(f"unsupported API key provider: {provider}")
    if not isinstance(key, str) or not key:
        raise ValueError("key must be a non-empty string")
    _keyring().set_password(SERVICE_NAME, _credential_name(provider), key)


def delete_api_key(provider: str) -> None:
    if provider not in _PROVIDERS - {"mock"}:
        raise ValueError(f"unsupported API key provider: {provider}")
    try:
        _keyring().delete_password(SERVICE_NAME, _credential_name(provider))
    except _keyring().errors.PasswordDeleteError:
        pass
