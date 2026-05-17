"""Load and merge provider configurations from built-in presets and user TOML."""
from __future__ import annotations

import importlib.resources
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
    """Load all providers: built-in presets merged with user overrides.

    Returns a list of Provider objects. User-defined providers with the
    same name as a built-in override it. User-defined providers with new
    names are appended.
    """
    # Load built-in presets from package data
    try:
        presets_bytes = importlib.resources.files("claude_switch").joinpath("builtin_presets.toml").read_bytes()
    except Exception as e:
        raise ConfigError(f"Failed to load built-in presets: {e}") from e

    builtin_raw = tomllib.loads(presets_bytes.decode("utf-8")).get("provider", [])

    # Build a dict keyed by provider name
    provider_map: dict[str, Provider] = {}
    for raw in builtin_raw:
        p = _dict_to_provider(raw)
        provider_map[p.name] = p

    # Load user overrides
    user_raw = _load_toml_providers(USER_PROVIDERS_PATH)
    for raw in user_raw:
        p = _dict_to_provider(raw)
        provider_map[p.name] = p  # override or append

    return list(provider_map.values())


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
