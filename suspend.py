"""Persistent suspension marker. Writes an ISO date to data/suspended_until.txt.
Anyone in the codebase that shouldn't fire during suspension checks
`is_suspended()` — including launch_or_remind, the pet's reminder scheduler,
and the encouragement timer."""
from datetime import date, timedelta

from config import CONFIG_DIR, ensure_dirs

SUSPEND_FILE = CONFIG_DIR / "suspended_until.txt"


def suspended_until() -> date | None:
    if not SUSPEND_FILE.exists():
        return None
    try:
        return date.fromisoformat(SUSPEND_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def is_suspended(today: date | None = None) -> bool:
    today = today or date.today()
    until = suspended_until()
    return until is not None and today <= until


def suspend_for_days(days: int) -> date:
    """Suspend for `days` calendar days starting today. days=1 means today only."""
    days = max(1, int(days))
    ensure_dirs()
    target = date.today() + timedelta(days=days - 1)
    SUSPEND_FILE.write_text(target.isoformat(), encoding="utf-8")
    return target


def resume() -> bool:
    """Remove the suspension marker. Returns True if we actually removed one."""
    if not SUSPEND_FILE.exists():
        return False
    try:
        SUSPEND_FILE.unlink()
        return True
    except OSError:
        return False
