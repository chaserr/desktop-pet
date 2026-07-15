from dataclasses import dataclass
from datetime import date, datetime

from PyQt5.QtCore import QObject, QTimer, pyqtSignal


@dataclass(frozen=True)
class Reminder:
    id: str
    label: str
    interval_ms: int
    messages: tuple[str, ...]
    first_delay_ms: int = 0  # 0 means "same as interval"
    state_hint: str = "waving"


DEFAULT_DICTS: list[dict] = [
    {
        "id": "stand-up",
        "label": "起立走动",
        "enabled": True,
        "interval_min": 60,
        "first_delay_min": 45,
        "state_hint": "waving",
        "messages": [
            "该起来走走啦!伸个懒腰~ 🧘",
            "坐太久了,站起来活动一下!",
            "起立时间到,拉伸拉伸腰背~",
            "走两步!眼睛也歇一会儿。",
        ],
    },
    {
        "id": "drink-water",
        "label": "喝水",
        "enabled": True,
        "interval_min": 60,
        "first_delay_min": 15,
        "state_hint": "waving",
        "messages": [
            "记得喝水哦 💧",
            "该补水啦,抿一口水~",
            "身体缺水啦,拿起水杯!",
            "喝水时间,咕咚咕咚~ 🫗",
        ],
    },
]


def default_reminders_dicts() -> list[dict]:
    """Fresh copy of the built-in reminder configs (so callers can mutate freely)."""
    return [dict(d, messages=list(d["messages"])) for d in DEFAULT_DICTS]


def from_dicts(items: list[dict]) -> tuple[Reminder, ...]:
    """Turn a list of dicts (from config) into Reminder objects, skipping disabled ones."""
    out: list[Reminder] = []
    for it in items:
        if not it.get("enabled", True):
            continue
        msgs = tuple(m for m in it.get("messages", []) if str(m).strip())
        if not msgs:
            continue
        out.append(
            Reminder(
                id=str(it["id"]),
                label=str(it.get("label", it["id"])),
                interval_ms=max(1, int(it.get("interval_min", 60))) * 60_000,
                messages=msgs,
                first_delay_ms=max(0, int(it.get("first_delay_min", 0))) * 60_000,
                state_hint=str(it.get("state_hint", "waving")),
            )
        )
    return tuple(out)


DEFAULT_REMINDERS: tuple[Reminder, ...] = from_dicts(DEFAULT_DICTS)


class ReminderScheduler(QObject):
    """Fires per-reminder timers and emits (reminder_id, message, state_hint)."""

    remind = pyqtSignal(str, str, str)

    def __init__(
        self,
        reminders: tuple[Reminder, ...] = DEFAULT_REMINDERS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._reminders = reminders
        self._msg_idx: dict[str, int] = {r.id: 0 for r in reminders}
        self._timers: list[QTimer] = []
        self._running = False

    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        for r in self._reminders:
            first = r.first_delay_ms if r.first_delay_ms > 0 else r.interval_ms
            QTimer.singleShot(first, lambda rid=r.id: self._fire_and_reschedule(rid))

    def reload(self, reminders: tuple[Reminder, ...]) -> None:
        """Replace the reminder list; if running, restart with the new schedule."""
        was_running = self._running
        self.stop()
        self._reminders = reminders
        self._msg_idx = {r.id: 0 for r in reminders}
        if was_running:
            self.start()

    def stop(self) -> None:
        self._running = False
        for t in self._timers:
            t.stop()
        self._timers.clear()

    def fire_now(self, reminder_id: str) -> None:
        r = self._by_id(reminder_id)
        if r is not None:
            self._emit(r)

    def _fire_and_reschedule(self, reminder_id: str) -> None:
        if not self._running:
            return
        r = self._by_id(reminder_id)
        if r is None:
            return
        self._emit(r)
        t = QTimer(self)
        t.setInterval(r.interval_ms)
        t.timeout.connect(lambda rid=r.id: self._emit_by_id(rid))
        t.start()
        self._timers.append(t)

    def _emit_by_id(self, reminder_id: str) -> None:
        if not self._running:
            return
        r = self._by_id(reminder_id)
        if r is not None:
            self._emit(r)

    def _emit(self, r: Reminder) -> None:
        idx = self._msg_idx[r.id] % len(r.messages)
        self._msg_idx[r.id] += 1
        self.remind.emit(r.id, r.messages[idx], r.state_hint)

    def _by_id(self, rid: str) -> Reminder | None:
        return next((r for r in self._reminders if r.id == rid), None)

    @property
    def reminders(self) -> tuple[Reminder, ...]:
        return self._reminders


# ---------- Time-of-day reminders (女仆干饭 / 下班催促) ----------


@dataclass(frozen=True)
class TimeReminder:
    """Fires at a specific (hour, minute) on given weekdays."""
    id: str
    label: str
    hour: int
    minute: int
    weekdays: tuple[int, ...]  # 0=Mon .. 6=Sun
    respect_holidays: bool
    grace_min: int             # catch-up grace: fire if pet was started late
    messages: tuple[str, ...]
    state_hint: str


DEFAULT_TIME_DICTS: list[dict] = [
    {
        "id": "lunch-heads-up",
        "label": "干饭预告",
        "hour": 11, "minute": 40,
        "weekdays": [0, 1, 2, 3, 4],
        "respect_holidays": True,
        "grace_min": 30,
        "state_hint": "waving",
        "messages": [
            "主人~ 快到干饭时间啦!今天想吃什么? 🍚",
            "快 12 点啦,主人先收个尾去吃饭吧~ ✨",
            "主人,记得吃饭哦!人家可不希望主人饿肚子 🥺",
            "肚子有没有咕咕叫呀?人家已经想帮主人端饭啦 🍜",
        ],
    },
    {
        "id": "lunch-urgent",
        "label": "催饭",
        "hour": 11, "minute": 50,
        "weekdays": [0, 1, 2, 3, 4],
        "respect_holidays": True,
        "grace_min": 30,
        "state_hint": "jumping",
        "messages": [
            "主人!赶紧去干饭啦!不然人家要生气咯~ 😤",
            "干饭!干饭!主人别再拖啦~ 🍚💨",
            "咕噜咕噜~ 主人再不吃,人家就替主人吃啦!🥢",
            "喂喂,主人的午饭时间到咯,快去快去 🍱",
        ],
    },
    {
        "id": "leave-heads-up",
        "label": "下班预告",
        "hour": 18, "minute": 40,
        "weekdays": [0, 1, 2, 3, 4],
        "respect_holidays": True,
        "grace_min": 30,
        "state_hint": "waving",
        "messages": [
            "主人~ 快下班啦,可以开始收东西咯 👜",
            "还有 20 分钟下班,主人加油完成手头的活~ ⏰",
            "今天也辛苦啦,准备准备回家吧~ 🏠",
            "主人,提前告诉您:马上要下班咯~ ✨",
        ],
    },
    {
        "id": "leave-now",
        "label": "催下班",
        "hour": 18, "minute": 50,
        "weekdays": [0, 1, 2, 3, 4],
        "respect_holidays": True,
        "grace_min": 30,
        "state_hint": "jumping",
        "messages": [
            "下班啦!主人!快关电脑走人~ 🎉",
            "主人!不许加班~ 人家等您回家呢!💗",
            "下班咯~ 主人今天也超棒的,回家吧~ ✨",
            "叮咚!下班时间到,主人立刻起身~ 🔔",
        ],
    },
]


def default_time_reminders_dicts() -> list[dict]:
    return [
        dict(d, messages=list(d["messages"]), weekdays=list(d["weekdays"]))
        for d in DEFAULT_TIME_DICTS
    ]


def time_reminders_from_dicts(items: list[dict]) -> tuple[TimeReminder, ...]:
    out: list[TimeReminder] = []
    for it in items:
        msgs = tuple(m for m in it.get("messages", []) if str(m).strip())
        if not msgs:
            continue
        out.append(
            TimeReminder(
                id=str(it["id"]),
                label=str(it.get("label", it["id"])),
                hour=int(it["hour"]),
                minute=int(it["minute"]),
                weekdays=tuple(int(x) for x in it.get("weekdays", (0, 1, 2, 3, 4))),
                respect_holidays=bool(it.get("respect_holidays", True)),
                grace_min=int(it.get("grace_min", 30)),
                state_hint=str(it.get("state_hint", "waving")),
                messages=msgs,
            )
        )
    return tuple(out)


class TimeReminderScheduler(QObject):
    """Wakes up every 30s, fires any time-of-day reminder that (a) hasn't fired
    today and (b) is within grace_min of its scheduled time. State persists to
    data/time_reminders_state.json so restarts don't re-fire the same reminder."""

    remind = pyqtSignal(str, str, str)  # id, message, state_hint

    def __init__(
        self,
        reminders: tuple[TimeReminder, ...],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._reminders = reminders
        self._msg_idx: dict[str, int] = {r.id: 0 for r in reminders}
        self._last_fired: dict[str, date] = {}
        self._timer = QTimer(self)
        self._timer.setInterval(30_000)
        self._timer.timeout.connect(self._check)
        self._running = False
        # First check runs right after start() — use a tight window there so
        # opening the app well past a scheduled time doesn't retroactively
        # nag. Subsequent polls use the per-reminder grace_min.
        self._first_check_pending = True

    STARTUP_CATCHUP_S = 60

    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._load_state()
        self._running = True
        self._timer.start()
        # Immediate initial check so catch-up fires without waiting 30s.
        QTimer.singleShot(400, self._check)

    def stop(self) -> None:
        self._running = False
        self._timer.stop()

    @property
    def reminders(self) -> tuple[TimeReminder, ...]:
        return self._reminders

    def fire_now(self, reminder_id: str) -> None:
        r = self._by_id(reminder_id)
        if r is not None:
            self._emit(r, date.today())

    def _by_id(self, rid: str) -> TimeReminder | None:
        return next((r for r in self._reminders if r.id == rid), None)

    def _check(self) -> None:
        if not self._running:
            return
        # Suspend / holidays imported lazily so this module stays cheap.
        try:
            import suspend as _suspend
            if _suspend.is_suspended():
                return
        except ImportError:
            pass
        try:
            from holidays_check import is_public_holiday
        except ImportError:
            is_public_holiday = None  # type: ignore

        now = datetime.now()
        today = now.date()
        is_startup = self._first_check_pending
        self._first_check_pending = False
        for r in self._reminders:
            if now.weekday() not in r.weekdays:
                continue
            if r.respect_holidays and is_public_holiday is not None and is_public_holiday(today):
                continue
            if self._last_fired.get(r.id) == today:
                continue
            target = now.replace(hour=r.hour, minute=r.minute, second=0, microsecond=0)
            delta = (now - target).total_seconds()
            # Startup: tight window so we don't retroactively fire something the
            # user missed hours ago. Runtime polling every 30s catches on-time.
            grace_s = self.STARTUP_CATCHUP_S if is_startup else r.grace_min * 60
            if 0 <= delta <= grace_s:
                self._emit(r, today)

    def _emit(self, r: TimeReminder, today: date) -> None:
        idx = self._msg_idx[r.id] % len(r.messages)
        self._msg_idx[r.id] += 1
        self._last_fired[r.id] = today
        self._save_state()
        self.remind.emit(r.id, r.messages[idx], r.state_hint)

    def _state_file(self):
        from config import CONFIG_DIR
        return CONFIG_DIR / "time_reminders_state.json"

    def _load_state(self) -> None:
        import json
        f = self._state_file()
        if not f.exists():
            return
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            self._last_fired = {
                str(k): date.fromisoformat(str(v)) for k, v in data.items()
            }
        except (OSError, ValueError, KeyError, TypeError):
            self._last_fired = {}

    def _save_state(self) -> None:
        import json
        from config import ensure_dirs
        ensure_dirs()
        try:
            data = {k: v.isoformat() for k, v in self._last_fired.items()}
            self._state_file().write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass
