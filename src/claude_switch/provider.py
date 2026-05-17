"""Resolve a Provider to a dict of environment variable assignments."""
from __future__ import annotations

import os
import re

from claude_switch.config import Provider


def resolve_env(provider: Provider, variant: str | None = None) -> dict[str, str]:
    """Resolve a provider to a dict of env var name -> value.

    Applies variant overrides on top of base env, then performs
    ${VAR} substitution: first checks the resolved dict itself,
    then falls back to os.environ.
    """
    env = dict(provider.env)

    # Apply variant overrides
    if variant:
        if not provider.variants or variant not in provider.variants:
            raise ValueError(
                f"Provider '{provider.name}' has no variant '{variant}'. "
                f"Available: {list(provider.variants.keys()) if provider.variants else 'none'}"
            )
        env.update(provider.variants[variant])

    # ${VAR} substitution with chaining
    def _replacer(m: re.Match) -> str:
        var = m.group(1)
        return env.get(var, os.environ.get(var, ""))

    resolved = {}
    for key, value in env.items():
        resolved[key] = re.sub(r"\$\{(\w+)\}", _replacer, value)

    return resolved


def format_exports(env: dict[str, str]) -> str:
    """Format a resolved env dict as shell export statements."""
    lines = []
    for key, value in env.items():
        # Shell-escape single quotes in values
        escaped = value.replace("'", "'\\''")
        lines.append(f"export {key}='{escaped}'")
    return "\n".join(lines)
