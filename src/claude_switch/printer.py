"""ANSI terminal output helpers. Respects NO_COLOR env var."""
import os
import sys

_NO_COLOR = bool(os.environ.get("NO_COLOR", "")) or not sys.stderr.isatty()


def _style(code: str, text: str) -> str:
    if _NO_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def accent(text: str) -> str:
    return _style("1;36", text)  # bold cyan


def bolded(text: str) -> str:
    return _style("1", text)


def dimmed(text: str) -> str:
    return _style("2", text)


def error(text: str) -> str:
    return _style("1;31", text)  # bold red


def warning(text: str) -> str:
    return _style("1;33", text)  # bold yellow


def muted(text: str) -> str:
    return _style("2;37", text)  # dim white
