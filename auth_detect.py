"""Detect whether Claude Code / Codex CLIs are installed and logged in locally.
When available, we can call them via subprocess and reuse the user's existing
session — no API key needed in the app config."""
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CliProbe:
    installed: bool
    logged_in: bool
    binary: str | None
    home_dir: Path | None

    @property
    def usable(self) -> bool:
        return self.installed and self.logged_in


def _probe(binary_name: str, home_dirname: str) -> CliProbe:
    binary = shutil.which(binary_name)
    home = Path.home() / home_dirname
    logged_in = home.is_dir() and any(home.iterdir())
    return CliProbe(
        installed=bool(binary),
        logged_in=logged_in,
        binary=binary,
        home_dir=home if home.exists() else None,
    )


def claude() -> CliProbe:
    return _probe("claude", ".claude")


def codex() -> CliProbe:
    return _probe("codex", ".codex")


def summary() -> dict[str, CliProbe]:
    return {"claude": claude(), "codex": codex()}
