import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from daily_knowledge_learning import config
from daily_knowledge_learning.config import AppConfig, delete_api_key, get_api_key, load_config, save_config, set_api_key


def test_config_round_trip_uses_private_atomic_json(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    path = tmp_path / "settings" / "config.json"
    value = AppConfig(vault, "openai", "gpt-test", 30)
    save_config(value, path)
    assert load_config(path) == value
    assert list(path.parent.glob("*.tmp")) == []
    if os.name != "nt":
        assert path.stat().st_mode & 0o077 == 0


def test_default_config_when_file_missing(tmp_path: Path) -> None:
    assert load_config(tmp_path / "missing.json") == AppConfig()


@pytest.mark.parametrize(
    "config_value,error",
    [
        (AppConfig(Path("missing-vault")), ValueError),
        (AppConfig(Path(""), "invalid"), ValueError),
        (AppConfig(Path(""), "mock", "", True), TypeError),
        (AppConfig(Path(""), "mock", "", 0), ValueError),
    ],
)
def test_config_validation(tmp_path: Path, config_value: AppConfig, error: type[Exception]) -> None:
    with pytest.raises(error):
        save_config(config_value, tmp_path / "config.json")


def test_load_config_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid config"):
        load_config(path)


def test_api_keys_use_keyring_without_persisting_them(monkeypatch: pytest.MonkeyPatch) -> None:
    data: dict[tuple[str, str], str] = {}

    def delete(service: str, username: str) -> None:
        if (service, username) not in data:
            raise KeyError(username)
        del data[(service, username)]

    fake = SimpleNamespace(
        get_password=lambda service, username: data.get((service, username)),
        set_password=lambda service, username, password: data.__setitem__((service, username), password),
        delete_password=delete,
        errors=SimpleNamespace(PasswordDeleteError=KeyError),
    )
    monkeypatch.setattr(config, "_keyring", lambda: fake)
    set_api_key("openai", "test-secret")
    assert get_api_key("openai") == "test-secret"
    delete_api_key("openai")
    assert get_api_key("openai") is None
    assert "test-secret" not in json.dumps(data)


def test_api_key_provider_validation() -> None:
    with pytest.raises(ValueError):
        set_api_key("mock", "x")
