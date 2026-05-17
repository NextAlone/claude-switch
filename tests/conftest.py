"""Shared fixtures for claude-switch tests."""
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    """Set up a temporary HOME directory."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: home)
    return home


@pytest.fixture
def tmp_claude_config(tmp_home):
    """Create a .claude/ directory under tmp_home."""
    claude_dir = tmp_home / ".claude"
    claude_dir.mkdir()
    return claude_dir


@pytest.fixture
def tmp_providers_toml(tmp_home):
    """Create a temporary providers.toml with a test provider."""
    cs_dir = tmp_home / ".config" / "claude-switch"
    cs_dir.mkdir(parents=True)
    toml_path = cs_dir / "providers.toml"
    toml_path.write_text("""\
[[provider]]
name = "testprov"
aliases = ["tp"]
description = "Test provider"

[provider.env]
ANTHROPIC_BASE_URL = "https://test.example.com/api"
ANTHROPIC_AUTH_TOKEN = "${TEST_KEY}"
ANTHROPIC_MODEL = "test-model"
""", encoding="utf-8")
    return toml_path


@pytest.fixture
def mock_keychain(monkeypatch):
    """Mock credential module's read/write."""
    store = {}

    def mock_read():
        return store.get("__creds__")

    def mock_write(creds):
        store["__creds__"] = creds

    monkeypatch.setattr("claude_switch.credential.read_credentials", mock_read)
    monkeypatch.setattr("claude_switch.credential.write_credentials", mock_write)
    return store
