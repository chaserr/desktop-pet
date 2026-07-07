#!/usr/bin/env python3
"""Called by launchd on the reminder schedule. Ensures the pet is running during
work hours and queues a reminder via a file-based IPC marker."""
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

# Re-exec through the project venv so imports (holidays, etc.) resolve.
_VENV_PY = SCRIPT_DIR / ".venv" / "bin" / "python"
if _VENV_PY.exists() and Path(sys.executable).resolve() != _VENV_PY.resolve():
    os.execv(str(_VENV_PY), [str(_VENV_PY), *sys.argv])

sys.path.insert(0, str(SCRIPT_DIR))

from config import CONFIG_DIR, ensure_dirs
from holidays_check import is_lunch_hour, now_is_work_time

PENDING_FILE = CONFIG_DIR / "pending_reminder.txt"
VENV_PY = SCRIPT_DIR / ".venv" / "bin" / "python"
PET_MAIN = SCRIPT_DIR / "pet.py"


def is_pet_running() -> bool:
    try:
        subprocess.check_output(["pgrep", "-f", str(PET_MAIN)])
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def choose_reminder(now: datetime) -> str:
    """Alternate between drink-water (even hours) and stand-up (odd hours)."""
    return "drink-water" if now.hour % 2 == 0 else "stand-up"


def launch_pet_detached() -> None:
    if not VENV_PY.exists():
        return
    subprocess.Popen(
        [str(VENV_PY), str(PET_MAIN)],
        cwd=str(SCRIPT_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def main() -> int:
    now = datetime.now()
    if not now_is_work_time(now):
        return 0
    if is_lunch_hour(now):
        return 0
    ensure_dirs()
    PENDING_FILE.write_text(choose_reminder(now), encoding="utf-8")
    if not is_pet_running():
        launch_pet_detached()
    return 0


if __name__ == "__main__":
    sys.exit(main())
