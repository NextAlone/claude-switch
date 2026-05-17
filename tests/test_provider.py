"""Tests for provider.py."""
import pytest
from claude_switch.config import Provider
from claude_switch.provider import resolve_env, format_exports


def make_provider(**kwargs) -> Provider:
    defaults = {"name": "test", "env": {"ANTHROPIC_BASE_URL": "https://test.com"}}
    defaults.update(kwargs)
    return Provider(**defaults)


def test_resolve_simple_env():
    """Simple env dict resolves without substitution."""
    p = make_provider(env={
        "ANTHROPIC_BASE_URL": "https://test.com",
        "ANTHROPIC_MODEL": "test-model",
    })
    env = resolve_env(p)
    assert env["ANTHROPIC_BASE_URL"] == "https://test.com"
    assert env["ANTHROPIC_MODEL"] == "test-model"


def test_resolve_var_substitution(monkeypatch):
    """${VAR} references are resolved from os.environ."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-123")
    p = make_provider(env={
        "ANTHROPIC_BASE_URL": "https://test.com",
        "ANTHROPIC_AUTH_TOKEN": "${DEEPSEEK_API_KEY}",
    })
    env = resolve_env(p)
    assert env["ANTHROPIC_AUTH_TOKEN"] == "sk-test-123"


def test_resolve_chained_substitution():
    """${VAR} references to other resolved env vars work."""
    p = make_provider(env={
        "ANTHROPIC_BASE_URL": "https://test.com",
        "ANTHROPIC_MODEL": "deepseek-chat",
        "CLAUDE_CODE_SUBAGENT_MODEL": "${ANTHROPIC_MODEL}",
    })
    env = resolve_env(p)
    assert env["CLAUDE_CODE_SUBAGENT_MODEL"] == "deepseek-chat"


def test_resolve_with_variant():
    """Variant overrides base env."""
    p = make_provider(
        env={"ANTHROPIC_BASE_URL": "https://global.example.com", "ANTHROPIC_MODEL": "base-model"},
        variants={"china": {"ANTHROPIC_BASE_URL": "https://china.example.com"}},
    )
    env = resolve_env(p, variant="china")
    assert env["ANTHROPIC_BASE_URL"] == "https://china.example.com"
    assert env["ANTHROPIC_MODEL"] == "base-model"  # not overridden


def test_resolve_invalid_variant():
    """Raises ValueError for unknown variant."""
    p = make_provider(variants={"global": {}})
    with pytest.raises(ValueError, match="no variant"):
        resolve_env(p, variant="nonexistent")


def test_format_exports():
    """format_exports produces valid shell export statements."""
    env = {"ANTHROPIC_BASE_URL": "https://test.com", "ANTHROPIC_MODEL": "gpt-5"}
    output = format_exports(env)
    assert "export ANTHROPIC_BASE_URL='https://test.com'" in output
    assert "export ANTHROPIC_MODEL='gpt-5'" in output


def test_format_exports_escapes_quotes():
    """Single quotes in values are escaped."""
    env = {"KEY": "val'ue"}
    output = format_exports(env)
    assert "export KEY='val'\\''ue'" in output
