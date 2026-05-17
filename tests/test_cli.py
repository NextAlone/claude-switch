"""Tests for the CLI."""
import io
import json
import sys
from unittest.mock import patch

import pytest


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
    assert "deepseek" in out
    assert "claude" in out


def test_provider_use_eval(monkeypatch):
    """provider use in eval mode outputs export statements."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    out, err = _run_cli(["provider", "use", "deepseek"])
    assert "export ANTHROPIC_BASE_URL=" in out
    assert "api.deepseek.com" in out


def test_provider_use_global(tmp_home):
    """provider use --mode global writes settings.json."""
    from claude_switch.cli import cmd_provider_use
    from unittest.mock import patch

    with patch("claude_switch.cli._detect_mode", return_value="global"):
        cmd_provider_use("claude", None, None)
    settings_path = tmp_home / ".claude" / "settings.json"
    assert settings_path.exists()
    data = json.loads(settings_path.read_text())
    assert data["env"]["ANTHROPIC_BASE_URL"] == "https://api.anthropic.com/"


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
    assert "deepseek" in out
    assert "--mode" in out or "-l mode" in out
    assert "china" in out


def test_completion_zsh():
    """completion zsh emits zsh completion script."""
    out, err = _run_cli(["completion", "zsh"])
    assert "#compdef claude-switch" in out
    assert "_claude_switch()" in out
    assert "--mode[Switching mode]" in out
    assert "china" in out


def test_completion_bash():
    """completion bash emits bash completion script."""
    out, err = _run_cli(["completion", "bash"])
    assert "complete -F _claude_switch claude-switch" in out
    assert "_claude_switch()" in out
    assert "--mode) COMPREPLY" in out
    assert "china" in out


def test_account_list_empty(tmp_home):
    """account list with no accounts."""
    from unittest.mock import patch as up
    with up("claude_switch.account.ACCOUNTS_DIR", tmp_home / ".config" / "claude-switch" / "accounts",
            create=True):
        out, err = _run_cli(["account", "list"])
    assert "no saved accounts" in out.lower() or "no saved accounts" in err.lower()
