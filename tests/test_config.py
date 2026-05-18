"""Tests for config.py."""
import pytest
from claude_switch.config import load_providers, resolve_provider, Provider
from claude_switch.exceptions import ProviderNotFoundError


def test_load_user_providers(tmp_providers_toml, monkeypatch):
    """User-defined providers load without errors."""
    from claude_switch import config
    monkeypatch.setattr(config, "USER_PROVIDERS_PATH", tmp_providers_toml)
    providers = load_providers()
    assert len(providers) == 2

    names = {p.name for p in providers}
    assert "testprov" in names
    assert "foxcode" in names


def test_resolve_by_name(tmp_providers_toml, monkeypatch):
    """Can find a provider by exact name."""
    from claude_switch import config
    monkeypatch.setattr(config, "USER_PROVIDERS_PATH", tmp_providers_toml)
    providers = load_providers()
    p = resolve_provider("testprov", providers)
    assert p.name == "testprov"
    assert p.env["ANTHROPIC_BASE_URL"] == "https://test.example.com/api"


def test_resolve_by_alias(tmp_providers_toml, monkeypatch):
    """Can find a provider by alias."""
    from claude_switch import config
    monkeypatch.setattr(config, "USER_PROVIDERS_PATH", tmp_providers_toml)
    providers = load_providers()
    p = resolve_provider("tp", providers)
    assert p.name == "testprov"


def test_resolve_not_found(tmp_providers_toml, monkeypatch):
    """Raises ProviderNotFoundError for unknown provider."""
    from claude_switch import config
    monkeypatch.setattr(config, "USER_PROVIDERS_PATH", tmp_providers_toml)
    providers = load_providers()
    with pytest.raises(ProviderNotFoundError):
        resolve_provider("nonexistent", providers)


def test_user_only_without_builtin(tmp_providers_toml, monkeypatch):
    """Providers come only from user providers.toml."""
    from claude_switch import config
    monkeypatch.setattr(config, "USER_PROVIDERS_PATH", tmp_providers_toml)
    providers = load_providers()
    names = {p.name for p in providers}
    assert names == {"testprov", "foxcode"}
