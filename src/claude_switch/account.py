"""OAuth account management for Claude Code — save, list, switch, remove."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from claude_switch.exceptions import AccountNotFoundError, ConfigError, CredentialError
from claude_switch.credential import (
    read_credentials, write_credentials,
    encode_creds, decode_creds,
)
from claude_switch.printer import accent, bolded, dimmed, error, warning

ACCOUNTS_DIR = Path.home() / ".config" / "claude-switch" / "accounts"


def _sequence_file() -> Path:
    return ACCOUNTS_DIR / "sequence.json"


def _init() -> None:
    ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
    sequence_file = _sequence_file()
    if not sequence_file.exists():
        sequence_file.write_text(
            json.dumps({"active": None, "accounts": {}, "order": []}, indent=2),
            encoding="utf-8",
        )
        sequence_file.chmod(0o600)


def _read_seq() -> dict:
    _init()
    return json.loads(_sequence_file().read_text(encoding="utf-8"))


def _write_seq(data: dict) -> None:
    data["_updated"] = datetime.now(timezone.utc).isoformat()
    sequence_file = _sequence_file()
    sequence_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    sequence_file.chmod(0o600)


def _next_slot(data: dict) -> int:
    if data["accounts"]:
        return max(int(k) for k in data["accounts"].keys()) + 1
    return 1


def _cred_file(slot: int) -> Path:
    return ACCOUNTS_DIR / f"{slot}.creds.enc"


def cmd_account_list() -> None:
    """List all saved accounts."""
    data = _read_seq()
    if not data["accounts"]:
        print(dimmed("No saved accounts."))
        print(f"Run {accent('claude-switch account add <name>')} to save the current account.")
        return

    # Detect current account
    current_creds = read_credentials()

    print(bolded("Saved accounts:"))
    for slot_str in data["order"]:
        slot = int(slot_str)
        info = data["accounts"].get(slot_str, {})
        label = info.get("name", f"account-{slot}")
        email = info.get("email", "unknown")
        active_marker = ""
        if current_creds:
            stored = _cred_file(slot)
            if stored.exists():
                stored_creds = decode_creds(stored.read_text(encoding="utf-8"))
                if stored_creds == current_creds:
                    active_marker = f" {bolded('(active)')}"
        print(f"  {accent(str(slot))}: {label}  {dimmed(email)}{active_marker}")


def cmd_account_add(name: str | None) -> None:
    """Save current credentials as a new account."""
    creds = read_credentials()
    if not creds:
        raise CredentialError(
            "No credentials found. Please log into Claude Code first (`claude login`)."
        )

    data = _read_seq()

    # Try to extract email from credentials JSON
    email = "unknown"
    try:
        cred_data = json.loads(creds)
        oauth = cred_data.get("claudeAiOauth", {})
        if isinstance(oauth, str):
            import base64 as b64
            parts = oauth.split(".")
            if len(parts) >= 2:
                padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
                try:
                    payload = json.loads(b64.urlsafe_b64decode(padded))
                    email = payload.get("email", email)
                except Exception:
                    pass
    except Exception:
        pass

    # Generate slot
    slot = _next_slot(data)
    label = name or f"account-{slot}"

    # Check for duplicate
    for existing_slot, info in data["accounts"].items():
        if info.get("email") == email and info.get("name") == label:
            print(f"Updating existing account {existing_slot}: {label} ({email})")
            slot = int(existing_slot)
            break

    # Store
    _cred_file(slot).write_text(encode_creds(creds), encoding="utf-8")
    _cred_file(slot).chmod(0o600)

    data["accounts"][str(slot)] = {
        "name": label,
        "email": email,
        "added": datetime.now(timezone.utc).isoformat(),
    }
    if str(slot) not in data["order"]:
        data["order"].append(str(slot))
    data["active"] = str(slot)
    _write_seq(data)
    print(f"{accent('Saved')} account {slot}: {label} ({email})")


def cmd_account_switch(name: str) -> None:
    """Switch to a saved account by label or slot number."""
    data = _read_seq()
    target_slot = None

    # Try as slot number first
    if name.isdigit() and name in data["accounts"]:
        target_slot = int(name)
    else:
        # Try as label
        for slot_str, info in data["accounts"].items():
            if info.get("name") == name:
                target_slot = int(slot_str)
                break

    if target_slot is None:
        raise AccountNotFoundError(
            f"Account '{name}' not found. Run `claude-switch account list` to see saved accounts."
        )

    cred_file = _cred_file(target_slot)
    if not cred_file.exists():
        raise AccountNotFoundError(f"Credential file missing for account {target_slot}")

    creds = decode_creds(cred_file.read_text(encoding="utf-8"))
    write_credentials(creds)

    info = data["accounts"][str(target_slot)]
    data["active"] = str(target_slot)
    _write_seq(data)

    print(f"{accent('Switched to')} account {target_slot}: {info.get('name')} ({info.get('email')})")
    print()
    print(warning("Restart Claude Code for the new authentication to take effect."))


def cmd_account_remove(name: str) -> None:
    """Remove a saved account."""
    data = _read_seq()
    target_slot = None

    if name.isdigit() and name in data["accounts"]:
        target_slot = int(name)
    else:
        for slot_str, info in data["accounts"].items():
            if info.get("name") == name:
                target_slot = int(slot_str)
                break

    if target_slot is None:
        raise AccountNotFoundError(f"Account '{name}' not found.")

    info = data["accounts"][str(target_slot)]
    is_active = data.get("active") == str(target_slot)

    if is_active:
        print(warning(f"Warning: Account {target_slot} ({info.get('name')}) is currently active."))

    # Delete credential file
    cf = _cred_file(target_slot)
    if cf.exists():
        cf.unlink()

    # Update sequence.json
    del data["accounts"][str(target_slot)]
    data["order"] = [s for s in data["order"] if s != str(target_slot)]
    if data.get("active") == str(target_slot):
        data["active"] = None
    _write_seq(data)

    print(f"{accent('Removed')} account {target_slot}: {info.get('name')} ({info.get('email')})")
