from dataclasses import dataclass

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
