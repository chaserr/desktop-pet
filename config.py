import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = PROJECT_ROOT / "data"
CONFIG_FILE = CONFIG_DIR / "config.json"
ASSETS_DIR = CONFIG_DIR / "assets"

# Fields containing filesystem paths — stored relative to PROJECT_ROOT when
# possible so config.json stays portable and doesn't leak the user's home dir.
PATH_FIELDS = ("gif_path", "pet_path")


def _to_portable(path: str) -> str:
    if not path:
        return path
    try:
        p = Path(path).resolve()
        return str(p.relative_to(PROJECT_ROOT))
    except (ValueError, OSError):
        return path


def _from_portable(path: str) -> str:
    if not path:
        return path
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return str(p)

DEFAULTS = {
    "gif_path": "",
    "pet_path": "",
    "state": "idle",
    "pos": [200, 200],
    "size": 160,
    "follow_mouse": False,
    "follow_speed": 6,
    "always_on_top": True,
    "playback_speed": 50,  # percent; 100 = original GIF timing
    "reminders_enabled": True,
    "encouragement_enabled": True,
    "encouragement_interval_seconds": 750,  # ~12.5 min average, ±20% jitter
    "bubble_auto_hide": False,   # bubble stays until user closes it
    "bubble_duration_ms": 7000,  # only honored when bubble_auto_hide is True
    "reminders": [],  # filled at load-time via _default_reminders()
    "llm_provider": "claude",
    "llm_settings": {},  # filled at load-time via _default_llm_settings()
    "chat_system_prompt": "",  # filled at load-time
}


def _default_reminders() -> list[dict]:
    # Deferred import so this module stays PyQt5-free at import time
    # (used by the launchd bootstrap script).
    import reminders as _reminders
    return _reminders.default_reminders_dicts()


def _default_llm_settings() -> dict:
    import auth_detect
    import llm_client
    # Deep copy so callers can mutate freely without touching the module default.
    settings = {k: dict(v) for k, v in llm_client.DEFAULT_SETTINGS.items()}
    if auth_detect.claude().usable:
        settings["claude"]["use_local_cli"] = True
    if auth_detect.codex().usable:
        settings["codex"]["use_local_cli"] = True
    return settings


def _default_system_prompt() -> str:
    import llm_client
    return llm_client.DEFAULT_SYSTEM_PROMPT


def ensure_dirs():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def load() -> dict:
    ensure_dirs()
    merged = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            merged.update({k: v for k, v in data.items() if k in DEFAULTS})
        except (OSError, json.JSONDecodeError):
            pass
    if not merged.get("reminders"):
        merged["reminders"] = _default_reminders()
    llm_defaults = _default_llm_settings()
    stored = merged.get("llm_settings") or {}
    for provider, defaults in llm_defaults.items():
        cur = dict(defaults)
        cur.update({k: v for k, v in (stored.get(provider) or {}).items() if k in defaults})
        llm_defaults[provider] = cur
    merged["llm_settings"] = llm_defaults
    if not merged.get("chat_system_prompt"):
        merged["chat_system_prompt"] = _default_system_prompt()
    for field in PATH_FIELDS:
        merged[field] = _from_portable(merged.get(field, ""))
    return merged


def save(cfg: dict) -> None:
    ensure_dirs()
    payload = {k: cfg.get(k, DEFAULTS[k]) for k in DEFAULTS}
    for field in PATH_FIELDS:
        payload[field] = _to_portable(payload.get(field, ""))
    CONFIG_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
