"""Tests for config.py."""
import pytest
from claude_switch.config import load_providers, resolve_provider, Provider
from claude_switch.exceptions import ProviderNotFoundError


def test_load_builtin_providers():
    """Built-in presets load without errors."""
    providers = load_providers()
    assert len(providers) >= 9

    names = {p.name for p in providers}
    assert "claude" in names
    assert "deepseek" in names
    assert "glm" in names
    assert "kimi" in names
    assert "qwen" in names
    assert "minimax" in names
    assert "seed" in names
    assert "stepfun" in names
    assert "openrouter" in names


def test_resolve_by_name():
    """Can find a provider by exact name."""
    providers = load_providers()
    p = resolve_provider("deepseek", providers)
    assert p.name == "deepseek"
    assert "api.deepseek.com" in p.env.get("ANTHROPIC_BASE_URL", "")


def test_resolve_by_alias():
    """Can find a provider by alias."""
    providers = load_providers()
    p = resolve_provider("ds", providers)
    assert p.name == "deepseek"


def test_resolve_not_found():
    """Raises ProviderNotFoundError for unknown provider."""
    providers = load_providers()
    with pytest.raises(ProviderNotFoundError):
        resolve_provider("nonexistent", providers)


def test_user_override_builtin(tmp_providers_toml, monkeypatch):
    """User providers.toml overrides built-in presets."""
    from claude_switch import config
    monkeypatch.setattr(config, "USER_PROVIDERS_PATH", tmp_providers_toml)
    providers = load_providers()
    # testprov was added
    p = resolve_provider("testprov", providers)
    assert p.name == "testprov"
    assert p.env["ANTHROPIC_BASE_URL"] == "https://test.example.com/api"
    # deepseek still exists (not removed)
    p2 = resolve_provider("deepseek", providers)
    assert p2.name == "deepseek"
