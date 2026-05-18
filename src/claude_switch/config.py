"""Load provider configurations from user TOML."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from claude_switch.exceptions import ConfigError, ProviderNotFoundError


@dataclass
class Provider:
    name: str
    aliases: list[str] = field(default_factory=list)
    description: str = ""
    category: str = "api"
    env: dict[str, str] = field(default_factory=dict)
    variants: dict[str, dict[str, str]] | None = None  # variant_name -> env overrides


def _config_dir() -> Path:
    return Path.home() / ".config" / "claude-switch"


USER_CONFIG_DIR = _config_dir()
USER_PROVIDERS_PATH = USER_CONFIG_DIR / "providers.toml"


def _load_toml_providers(path: Path) -> list[dict]:
    """Parse a TOML file and return the list of provider dicts."""
    if not path.exists():
        return []
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        raise ConfigError(f"Failed to parse {path}: {e}") from e

    raw = data.get("provider", [])
    if not isinstance(raw, list):
        raise ConfigError(f"{path}: [[provider]] section must be a TOML array of tables")
    return raw


def _dict_to_provider(raw: dict) -> Provider:
    """Convert a raw provider dict (from TOML) to a Provider dataclass."""
    variants = None
    if "variants" in raw:
        variants_data = raw["variants"]
        if isinstance(variants_data, dict):
            variants = {}
            for vname, vdata in variants_data.items():
                if isinstance(vdata, dict):
                    variants[vname] = vdata.get("env", {})
                else:
                    variants[vname] = {}

    return Provider(
        name=raw["name"],
        aliases=raw.get("aliases", []),
        description=raw.get("description", ""),
        category=raw.get("category", "api"),
        env=raw.get("env", {}),
        variants=variants,
    )


def load_providers() -> list[Provider]:
    """Load all providers from user config."""
    user_raw = _load_toml_providers(USER_PROVIDERS_PATH)
    return [_dict_to_provider(raw) for raw in user_raw]


def get_all_env_keys(providers: list[Provider]) -> set[str]:
    """Collect all possible env var keys from all providers and their variants."""
    keys: set[str] = set()
    for p in providers:
        keys.update(p.env.keys())
        if p.variants:
            for v_env in p.variants.values():
                keys.update(v_env.keys())
    return keys


def resolve_provider(name: str, providers: list[Provider]) -> Provider:
    """Find a provider by name or alias. Raises ProviderNotFoundError."""
    for p in providers:
        if p.name == name or name in p.aliases:
            return p
    raise ProviderNotFoundError(f"Provider '{name}' not found. Available: "
        f"{', '.join(sorted(set(p.name for p in providers)))}")
