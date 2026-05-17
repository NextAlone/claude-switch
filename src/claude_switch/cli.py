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


def _provider_names(include_builtin: bool = False) -> list[str]:
    providers = load_providers()
    if not include_builtin and USER_PROVIDERS_PATH.exists():
        import tomllib
        data = tomllib.loads(USER_PROVIDERS_PATH.read_text(encoding="utf-8"))
        return sorted({p.get("name", "") for p in data.get("provider", []) if p.get("name")})
    return sorted({p.name for p in providers})


def _provider_variant_names(provider_name: str) -> list[str]:
    for p in load_providers():
        if p.name == provider_name and p.variants:
            return sorted(p.variants)
    return []


def _account_names() -> list[str]:
    try:
        from claude_switch.account import _read_seq, _sequence_file
        if not _sequence_file().exists():
            return []
        data = _read_seq()
        names: list[str] = []
        for slot in data.get("order", []):
            info = data.get("accounts", {}).get(slot, {})
            names.append(slot)
            if info.get("name"):
                names.append(info["name"])
        return sorted(set(names))
    except Exception:
        return []


def _account_commands() -> list[str]:
    return ["list", "add", "switch", "remove"]


def _provider_commands() -> list[str]:
    return ["list", "add", "remove", "use"]


def _root_commands() -> list[str]:
    return ["provider", "account", "status", "config", "completion"]


def _print_fish_completion() -> None:
    print("complete -c claude-switch -f")
    print("complete -c claude-switch -n '__fish_use_subcommand' -a 'provider account status config completion'")
    print("complete -c claude-switch -n '__fish_seen_subcommand_from provider; and not __fish_seen_subcommand_from list add remove use' -a 'list add remove use'")
    print("complete -c claude-switch -n '__fish_seen_subcommand_from provider; and __fish_seen_subcommand_from add' -l alias")
    print("complete -c claude-switch -n '__fish_seen_subcommand_from provider; and __fish_seen_subcommand_from add' -l base-url")
    print("complete -c claude-switch -n '__fish_seen_subcommand_from provider; and __fish_seen_subcommand_from add' -l model")
    print("complete -c claude-switch -n '__fish_seen_subcommand_from provider; and __fish_seen_subcommand_from add' -l auth-token-var")
    print("complete -c claude-switch -n '__fish_seen_subcommand_from provider; and __fish_seen_subcommand_from remove; and test (count (commandline -opc)) -eq 3' -a '(claude-switch __complete providers)'")
    print("complete -c claude-switch -n '__fish_seen_subcommand_from provider; and __fish_seen_subcommand_from use; and test (count (commandline -opc)) -eq 3' -a '(claude-switch __complete providers)'")
    print("complete -c claude-switch -n '__fish_seen_subcommand_from provider; and __fish_seen_subcommand_from use; and test (count (commandline -opc)) -eq 4' -a '(claude-switch __complete variants (commandline -opc)[4])'")
    print("complete -c claude-switch -n '__fish_seen_subcommand_from provider; and __fish_seen_subcommand_from use' -l mode -a 'eval global project'")
    print("complete -c claude-switch -n '__fish_seen_argument -l mode' -a 'eval global project'")
    print("complete -c claude-switch -n '__fish_seen_subcommand_from account; and not __fish_seen_subcommand_from list add switch remove' -a 'list add switch remove'")
    print("complete -c claude-switch -n '__fish_seen_subcommand_from account; and __fish_seen_subcommand_from switch remove' -a '(claude-switch __complete accounts)'")
    print("complete -c claude-switch -n '__fish_seen_subcommand_from config; and not __fish_seen_subcommand_from open show' -a 'open show'")
    print("complete -c claude-switch -n '__fish_seen_subcommand_from completion; and not __fish_seen_subcommand_from fish zsh bash' -a 'fish zsh bash'")


def _print_zsh_completion() -> None:
    print("#compdef claude-switch")
    print("_claude_switch() {")
    print("  local -a commands providers accounts modes variants")
    print("  commands=(provider account status config completion)")
    print("  providers=(${(f)\"$(claude-switch __complete providers)\"})")
    print("  accounts=(${(f)\"$(claude-switch __complete accounts)\"})")
    print("  modes=(eval global project)")
    print("  _arguments \\")
    print("    '--alias[Provider alias]:alias:' \\")
    print("    '--base-url[Provider base URL]:url:' \\")
    print("    '--model[Default model]:model:' \\")
    print("    '--auth-token-var[Environment variable for API key]:env var:' \\")
    print("    '--mode[Switching mode]:mode:(eval global project)' \\")
    print("    '1:command:->cmd' \\")
    print("    '2:subcommand:->subcmd' \\")
    print("    '3:provider:->provider' \\")
    print("    '4:variant:->variant' \\")
    print("    '*::arg:->args'")
    print("  case $state in")
    print("    cmd) _describe 'command' commands ;;")
    print("    subcmd)")
    print("      case $words[2] in")
    print("        provider) _values 'provider command' list add remove use ;;")
    print("        account) _values 'account command' list add switch remove ;;")
    print("        config) _values 'config command' open show ;;")
    print("        completion) _values 'shell' fish zsh bash ;;")
    print("      esac ;;")
    print("    provider)")
    print("      if [[ $words[2] == provider && $words[3] == use ]]; then _describe 'provider' providers; fi")
    print("      if [[ $words[2] == provider && $words[3] == remove ]]; then _describe 'provider' providers; fi")
    print("      if [[ $words[2] == account && ( $words[3] == switch || $words[3] == remove ) ]]; then _describe 'account' accounts; fi ;;")
    print("    variant)")
    print("      if [[ $words[2] == provider && $words[3] == use ]]; then")
    print("        variants=(${(f)\"$(claude-switch __complete variants $words[4])\"})")
    print("        _describe 'variant' variants")
    print("      fi ;;")
    print("  esac")
    print("}")
    print("compdef _claude_switch claude-switch")


def _print_bash_completion() -> None:
    print("_claude_switch() {")
    print("  local cur prev words cword")
    print("  _init_completion || return")
    print("  case $prev in")
    print("    --mode) COMPREPLY=( $(compgen -W 'eval global project' -- \"$cur\") ); return ;;")
    print("    --alias|--base-url|--model|--auth-token-var) return ;;")
    print("  esac")
    print("  case $cword in")
    print("    1) COMPREPLY=( $(compgen -W 'provider account status config completion' -- \"$cur\") ) ;;")
    print("    2)")
    print("      case ${words[1]} in")
    print("        provider) COMPREPLY=( $(compgen -W 'list add remove use' -- \"$cur\") ) ;;")
    print("        account) COMPREPLY=( $(compgen -W 'list add switch remove' -- \"$cur\") ) ;;")
    print("        config) COMPREPLY=( $(compgen -W 'open show' -- \"$cur\") ) ;;")
    print("        completion) COMPREPLY=( $(compgen -W 'fish zsh bash' -- \"$cur\") ) ;;")
    print("      esac ;;")
    print("    3)")
    print("      [[ ${words[1]} == provider && ${words[2]} == use ]] && COMPREPLY=( $(compgen -W \"$(claude-switch __complete providers) --mode\" -- \"$cur\") )")
    print("      [[ ${words[1]} == provider && ${words[2]} == remove ]] && COMPREPLY=( $(compgen -W \"$(claude-switch __complete providers)\" -- \"$cur\") )")
    print("      [[ ${words[1]} == provider && ${words[2]} == add ]] && COMPREPLY=( $(compgen -W '--alias --base-url --model --auth-token-var' -- \"$cur\") )")
    print("      [[ ${words[1]} == account && ( ${words[2]} == switch || ${words[2]} == remove ) ]] && COMPREPLY=( $(compgen -W \"$(claude-switch __complete accounts)\" -- \"$cur\") ) ;;")
    print("    4)")
    print("      if [[ ${words[1]} == provider && ${words[2]} == use ]]; then")
    print("        COMPREPLY=( $(compgen -W \"$(claude-switch __complete variants ${words[3]})\" -- \"$cur\") )")
    print("      fi ;;")
    print("  esac")
    print("}")
    print("complete -F _claude_switch claude-switch")


def cmd_complete(kind: str, provider_name: str | None = None) -> None:
    if kind == "providers":
        print("\n".join(_provider_names()))
    elif kind == "variants":
        if provider_name:
            print("\n".join(_provider_variant_names(provider_name)))
    elif kind == "accounts":
        print("\n".join(_account_names()))
    else:
        raise ClaudeSwitchError(f"Unsupported completion kind '{kind}'")


def cmd_completion(shell: str) -> None:
    if shell == "fish":
        _print_fish_completion()
    elif shell == "zsh":
        _print_zsh_completion()
    elif shell == "bash":
        _print_bash_completion()
    else:
        raise ClaudeSwitchError(f"Unsupported shell '{shell}'")


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

    # --- internal completion ---
    p_internal = sub.add_parser("__complete", help=argparse.SUPPRESS)
    p_internal.add_argument("kind", choices=["providers", "variants", "accounts"])
    p_internal.add_argument("provider", nargs="?", default=None)

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

    # --- completion ---
    p_comp = sub.add_parser("completion", help="Generate shell completions")
    p_comp.add_argument("shell", choices=["fish", "zsh", "bash"], help="Shell to generate completion for")

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
        if args.command == "__complete":
            cmd_complete(args.kind, args.provider)
        elif args.command == "provider":
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
        elif args.command == "completion":
            cmd_completion(args.shell)
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
