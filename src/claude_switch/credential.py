"""Platform-aware credential storage for Claude Code OAuth tokens.

macOS:  Keychain via `security` CLI
Linux:  ~/.claude/.credentials.json file
Windows: Keyring library (optional dependency)
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path

from claude_switch.exceptions import CredentialError


CREDENTIALS_FILE = Path.home() / ".claude" / ".credentials.json"
KEYCHAIN_SERVICE = "Claude Code-credentials"


def read_credentials() -> str | None:
    """Read current Claude Code OAuth credentials.

    Returns the raw JSON string, or None if not found.
    """
    if sys.platform == "darwin":
        return _read_macos_keychain()
    else:
        return _read_linux_file()


def write_credentials(credentials: str) -> None:
    """Write credentials to Claude Code storage."""
    if sys.platform == "darwin":
        _write_macos_keychain(credentials)
    else:
        _write_linux_file(credentials)


def _read_macos_keychain() -> str | None:
    try:
        result = subprocess.run(
            ["security", "find-generic-password",
             "-a", os.environ.get("USER", "user"),
             "-s", KEYCHAIN_SERVICE,
             "-w"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        elif result.returncode == 44:  # Item not found
            return None
        return None
    except Exception:
        return None


def _write_macos_keychain(credentials: str) -> None:
    result = subprocess.run(
        ["security", "add-generic-password",
         "-U",
         "-a", os.environ.get("USER", "user"),
         "-s", KEYCHAIN_SERVICE,
         "-w", credentials],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        raise CredentialError(f"Failed to write to Keychain: {result.stderr}")


def _read_linux_file() -> str | None:
    if CREDENTIALS_FILE.exists():
        try:
            return CREDENTIALS_FILE.read_text(encoding="utf-8")
        except Exception:
            return None
    return None


def _write_linux_file(credentials: str) -> None:
    CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    import tempfile
    fd, tmp_path = tempfile.mkstemp(dir=str(CREDENTIALS_FILE.parent), suffix=".tmp")
    try:
        os.write(fd, credentials.encode("utf-8"))
        os.close(fd)
        os.replace(tmp_path, str(CREDENTIALS_FILE))
        os.chmod(str(CREDENTIALS_FILE), 0o600)
    except Exception as e:
        raise CredentialError(f"Failed to write credentials file: {e}")


def encode_creds(raw: str) -> str:
    """Base64-encode credentials for storage."""
    return base64.b64encode(raw.encode("utf-8")).decode("utf-8")


def decode_creds(encoded: str) -> str:
    """Base64-decode credentials from storage."""
    return base64.b64decode(encoded.encode("utf-8")).decode("utf-8")
