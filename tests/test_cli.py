"""Tests for the CLI."""
import io
import json
import sys
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def use_tmp_user_providers(tmp_providers_toml, monkeypatch):
    """Force CLI tests to use temporary user providers.toml."""
    monkeypatch.setattr("claude_switch.config.USER_PROVIDERS_PATH", tmp_providers_toml)
    monkeypatch.setattr("claude_switch.cli.USER_PROVIDERS_PATH", tmp_providers_toml)
    return tmp_providers_toml


def _run_cli(args: list[str]):
    """Run the CLI with given args and return stdout/stderr captures."""
    from claude_switch.cli import main
    out = io.StringIO()
    err = io.StringIO()
    with patch.object(sys, "argv", ["claude-switch"] + args), \
         patch.object(sys, "stdout", out), \
         patch.object(sys, "stderr", err):
        try:
            main()
        except SystemExit:
            pass
    return out.getvalue(), err.getvalue()


def test_version():
    """--version prints version."""
    out, err = _run_cli(["--version"])
    assert "0.1.0" in out


def test_help():
    """--help prints usage."""
    out, err = _run_cli(["--help"])
    assert "usage" in out.lower() or "provider" in out.lower()


def test_provider_list():
    """provider list outputs known providers."""
    out, err = _run_cli(["provider", "list"])
    assert "testprov" in out
    assert "foxcode" in out


def test_provider_use_eval(monkeypatch):
    """provider use in eval mode outputs export statements."""
    monkeypatch.setenv("TEST_KEY", "sk-test")
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    out, err = _run_cli(["provider", "use", "testprov"])
    assert "export ANTHROPIC_BASE_URL=" in out
    assert "test.example.com" in out


def test_provider_use_global(tmp_home):
    """provider use --mode global writes settings.json."""
    from claude_switch.cli import cmd_provider_use
    from unittest.mock import patch

    with patch("claude_switch.cli._detect_mode", return_value="global"):
        cmd_provider_use("testprov", None, None)
    settings_path = tmp_home / ".claude" / "settings.json"
    assert settings_path.exists()
    data = json.loads(settings_path.read_text())
    assert data["env"]["ANTHROPIC_BASE_URL"] == "https://test.example.com/api"


def test_provider_use_unknown(monkeypatch):
    """Unknown provider gives error."""
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    out, err = _run_cli(["provider", "use", "nonexistent"])
    assert "not found" in err


def test_completion_fish():
    """completion fish emits fish completion script."""
    out, err = _run_cli(["completion", "fish"])
    assert "complete -c claude-switch" in out
    assert "provider account status config completion" in out
    assert "claude-switch __complete providers" in out
    assert "claude-switch __complete variants" in out
    assert "--mode" in out or "-l mode" in out


def test_completion_zsh():
    """completion zsh emits zsh completion script."""
    out, err = _run_cli(["completion", "zsh"])
    assert "#compdef claude-switch" in out
    assert "_claude_switch()" in out
    assert "--mode[Switching mode]" in out
    assert "claude-switch __complete providers" in out
    assert "claude-switch __complete variants" in out


def test_completion_bash():
    """completion bash emits bash completion script."""
    out, err = _run_cli(["completion", "bash"])
    assert "complete -F _claude_switch claude-switch" in out
    assert "_claude_switch()" in out
    assert "--mode) COMPREPLY" in out
    assert "claude-switch __complete providers" in out
    assert "claude-switch __complete variants" in out


def test_internal_complete_user_providers():
    """__complete providers returns user providers dynamically."""
    out, err = _run_cli(["__complete", "providers"])
    assert "testprov" in out
    assert "foxcode" in out


def test_internal_complete_variants():
    """__complete variants returns variants for the selected provider."""
    out, err = _run_cli(["__complete", "variants", "foxcode"])
    assert "codex" in out


def test_internal_complete_variants_without_provider_is_empty():
    """__complete variants without provider does not error."""
    out, err = _run_cli(["__complete", "variants"])
    assert out.strip() == ""
    assert err.strip() == ""


def test_account_list_empty(tmp_home):
    """account list with no accounts."""
    from unittest.mock import patch as up
    with up("claude_switch.account.ACCOUNTS_DIR", tmp_home / ".config" / "claude-switch" / "accounts",
            create=True):
        out, err = _run_cli(["account", "list"])
    assert "no saved accounts" in out.lower() or "no saved accounts" in err.lower()
