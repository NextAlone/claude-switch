"""CLI entry point for claude-switch."""
from __future__ import annotations

import argparse
import os
import sys

from claude_switch import __version__
from claude_switch.config import get_all_env_keys, load_providers, resolve_provider, USER_PROVIDERS_PATH
from claude_switch.exceptions import ClaudeSwitchError
from claude_switch.printer import accent, dimmed, error, warning
from claude_switch.provider import resolve_env, format_exports
from claude_switch.settings import (
    merge_into_user_settings,
    write_project_settings,
    remove_project_settings,
)


def _detect_mode(mode: str | None) -> str:
    """Determine switching mode."""
    if mode:
        return mode
    return "global" if sys.stdout.isatty() else "eval"


def cmd_provider_list() -> None:
    """List all known providers."""
    providers = load_providers()
    print("Available providers:")
    print()
    for p in providers:
        aliases_str = f" ({', '.join(p.aliases)})" if p.aliases else ""
        variants_str = f" [variants: {', '.join(p.variants.keys())}]" if p.variants else ""
        print(f"  {accent(p.name)}{aliases_str}  {dimmed(p.description)}{variants_str}")
    print()
    cfg = USER_PROVIDERS_PATH
    print(dimmed(f"User config: {cfg}" if cfg.exists() else f"User config: {cfg} (not created yet)"))


def cmd_provider_add(name: str, aliases: list[str] | None,
                      base_url: str | None, model: str | None,
                      auth_token_var: str | None) -> None:
    """Add a user-defined provider (appends to providers.toml)."""
    USER_PROVIDERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = ""
    if USER_PROVIDERS_PATH.exists():
        existing = USER_PROVIDERS_PATH.read_text(encoding="utf-8")

    aliases_str = ", ".join(f'"{a}"' for a in (aliases or []))
    lines = [
        "",
        "[[provider]]",
        f'name = "{name}"',
    ]
    if aliases:
        lines.append(f"aliases = [{aliases_str}]")
    lines.append(f'description = "User-defined provider"')
    lines.append("")
    lines.append("[provider.env]")
    if base_url:
        lines.append(f'ANTHROPIC_BASE_URL = "{base_url}"')
    if model:
        lines.append(f'ANTHROPIC_MODEL = "{model}"')
        lines.append(f'ANTHROPIC_DEFAULT_SONNET_MODEL = "{model}"')
        lines.append(f'ANTHROPIC_DEFAULT_OPUS_MODEL = "{model}"')
        lines.append(f'ANTHROPIC_DEFAULT_HAIKU_MODEL = "{model}"')
        lines.append('CLAUDE_CODE_SUBAGENT_MODEL = "${ANTHROPIC_MODEL}"')
    if auth_token_var:
        lines.append(f'ANTHROPIC_AUTH_TOKEN = "${{{auth_token_var}}}"')
    lines.append("")

    USER_PROVIDERS_PATH.write_text(existing + "\n".join(lines), encoding="utf-8")
    print(f"{accent('Added')} provider '{name}' to {USER_PROVIDERS_PATH}")
    print(dimmed(f"Edit {USER_PROVIDERS_PATH} to customize further."))


def cmd_provider_remove(name: str) -> None:
    """Remove a user-defined provider from providers.toml."""
    if not USER_PROVIDERS_PATH.exists():
        raise ClaudeSwitchError("No user providers.toml found")

    import tomllib
    with open(USER_PROVIDERS_PATH, "rb") as f:
        data = tomllib.load(f)

    prods = data.get("provider", [])
    new_prods = [p for p in prods if p.get("name") != name]

    if len(new_prods) == len(prods):
        raise ClaudeSwitchError(f"Provider '{name}' not found in {USER_PROVIDERS_PATH}")

    # Rebuild the TOML manually
    out_lines = []
    for p in new_prods:
        out_lines.append("[[provider]]")
        out_lines.append(f'name = "{p["name"]}"')
        if p.get("aliases"):
            aliases_str = ", ".join(f'"{a}"' for a in p["aliases"])
            out_lines.append(f"aliases = [{aliases_str}]")
        if p.get("description"):
            out_lines.append(f'description = "{p["description"]}"')
        if p.get("category"):
            out_lines.append(f'category = "{p["category"]}"')
        out_lines.append("[provider.env]")
        for k, v in p.get("env", {}).items():
            out_lines.append(f'{k} = "{v}"')
        out_lines.append("")

    USER_PROVIDERS_PATH.write_text("\n".join(out_lines), encoding="utf-8")
    print(f"{accent('Removed')} provider '{name}' from {USER_PROVIDERS_PATH}")


def cmd_provider_use(name: str, variant: str | None, mode: str | None) -> None:
    """Switch to a provider."""
    mode = _detect_mode(mode)
    providers = load_providers()
    provider = resolve_provider(name, providers)
    env_vars = resolve_env(provider, variant)

    if mode == "eval":
        # stdout: export statements only (for eval capture)
        # stderr: human messages
        known = get_all_env_keys(providers)
        cleared = known - set(env_vars.keys())
        lines = [f"export {k}=" for k in sorted(cleared)]
        lines.append(format_exports(env_vars))
        print("\n".join(lines), file=sys.stdout)
        variant_str = f" ({variant})" if variant else ""
        print(f"# claude-switch: using provider '{provider.name}'{variant_str}", file=sys.stderr)
        print(f"# Run: eval \"$(claude-switch provider use {name})\"", file=sys.stderr)

    elif mode == "global":
        known = get_all_env_keys(providers)
        path = merge_into_user_settings(env_vars, source=provider.name, known_keys=known)
        print(f"Wrote {path} (provider: {accent(provider.name)})")
        # Unset env vars so settings.json takes effect
        for key in known:
            print(f"export {key}=")

    elif mode == "project":
        path = write_project_settings(env_vars, source=provider.name)
        print(f"Wrote {path} (provider: {accent(provider.name)})")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="claude-switch",
        description="Provider + account switcher for Claude Code",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command", title="commands")

    # --- provider ---
    p_prov = sub.add_parser("provider", help="Manage API providers")
    p_prov_sub = p_prov.add_subparsers(dest="action")

    p_prov_sub.add_parser("list", help="List all providers")

    p_add = p_prov_sub.add_parser("add", help="Add a custom provider")
    p_add.add_argument("name", help="Provider name")
    p_add.add_argument("--alias", action="append", default=None, help="Alias (repeatable)")
    p_add.add_argument("--base-url", help="Base URL for the Anthropic-compatible endpoint")
    p_add.add_argument("--model", help="Default model ID")
    p_add.add_argument("--auth-token-var", help="Env var name for API key (e.g. DEEPSEEK_API_KEY)")

    p_remove = p_prov_sub.add_parser("remove", help="Remove a custom provider")
    p_remove.add_argument("name", help="Provider name")

    p_use = p_prov_sub.add_parser("use", help="Switch to a provider")
    p_use.add_argument("name", help="Provider name or alias")
    p_use.add_argument("variant", nargs="?", default=None, help="Variant (e.g. china)")
    p_use.add_argument("--mode", choices=["eval", "global", "project"], default=None,
                        help="Switching mode (default: global in TTY, eval when piped)")

    # --- account ---
    p_acct = sub.add_parser("account", help="Manage Claude Pro accounts")
    p_acct_sub = p_acct.add_subparsers(dest="action")

    p_acct_sub.add_parser("list", help="List saved accounts")

    p_acct_add = p_acct_sub.add_parser("add", help="Save current credentials as an account")
    p_acct_add.add_argument("name", nargs="?", default=None, help="Label for this account")

    p_acct_switch = p_acct_sub.add_parser("switch", help="Switch to a saved account")
    p_acct_switch.add_argument("name", help="Account label or number")

    p_acct_remove = p_acct_sub.add_parser("remove", help="Remove a saved account")
    p_acct_remove.add_argument("name", help="Account label or number")

    # --- status ---
    sub.add_parser("status", help="Show current provider and account")

    # --- config ---
    p_cfg = sub.add_parser("config", help="Manage claude-switch config")
    p_cfg_sub = p_cfg.add_subparsers(dest="action")
    p_cfg_sub.add_parser("open", help="Open providers.toml in $EDITOR")
    p_cfg_sub.add_parser("show", help="Print current config (keys masked)")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "provider":
            if args.action == "list":
                cmd_provider_list()
            elif args.action == "add":
                cmd_provider_add(args.name, args.alias, args.base_url, args.model, args.auth_token_var)
            elif args.action == "remove":
                cmd_provider_remove(args.name)
            elif args.action == "use":
                cmd_provider_use(args.name, args.variant, args.mode)
            else:
                p_prov.print_help()
        elif args.command == "account":
            if args.action == "list":
                from claude_switch.account import cmd_account_list
                cmd_account_list()
            elif args.action == "add":
                from claude_switch.account import cmd_account_add
                cmd_account_add(args.name)
            elif args.action == "switch":
                from claude_switch.account import cmd_account_switch
                cmd_account_switch(args.name)
            elif args.action == "remove":
                from claude_switch.account import cmd_account_remove
                cmd_account_remove(args.name)
            else:
                p_acct.print_help()
        elif args.command == "status":
            from claude_switch.config import load_providers
            providers = load_providers()
            print("Providers:", ", ".join(p.name for p in providers))
            cfg = USER_PROVIDERS_PATH
            print(f"Config: {cfg if cfg.exists() else 'not created'}")
        elif args.command == "config":
            if args.action == "open":
                editor = os.environ.get("EDITOR", "vi")
                USER_PROVIDERS_PATH.parent.mkdir(parents=True, exist_ok=True)
                USER_PROVIDERS_PATH.touch(exist_ok=True)
                os.execvp(editor, [editor, str(USER_PROVIDERS_PATH)])
            elif args.action == "show":
                if USER_PROVIDERS_PATH.exists():
                    content = USER_PROVIDERS_PATH.read_text(encoding="utf-8")
                    print(content)
                else:
                    print(dimmed("# No user config. Using built-in presets only."))
            else:
                p_cfg.print_help()
    except ClaudeSwitchError as e:
        print(f"{error('Error:')} {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
