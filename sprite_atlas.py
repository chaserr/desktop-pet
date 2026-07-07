from dataclasses import dataclass

from PyQt5.QtCore import QObject, QRect, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap

CELL_W = 192
CELL_H = 208
FRAME_MS = 100  # ~10 FPS, feels natural for chibi loops


@dataclass(frozen=True)
class State:
    id: str
    label: str
    row: int
    frames: int


STATES: tuple[State, ...] = (
    State("idle",          "Idle",       0, 6),
    State("running-right", "Run right",  1, 8),
    State("running-left",  "Run left",   2, 8),
    State("waving",        "Waving",     3, 4),
    State("jumping",       "Jumping",    4, 5),
    State("failed",        "Failed",     5, 8),
    State("waiting",       "Waiting",    6, 6),
    State("running",       "Running",    7, 6),
    State("review",        "Review",     8, 6),
)

STATES_BY_ID = {s.id: s for s in STATES}


class SpriteAnimator(QObject):
    """Slice a sprite atlas into per-state frame lists and emit them in order."""

    frame_ready = pyqtSignal(QPixmap)

    def __init__(self, parent: QObject | None = None, speed: int = 100):
        super().__init__(parent)
        self._atlas: QPixmap | None = None
        self._frames: list[QPixmap] = []
        self._idx = 0
        self._state = STATES[0]
        self._speed = max(10, min(400, int(speed)))
        self._timer = QTimer(self)
        self._timer.setInterval(self._current_interval())
        self._timer.timeout.connect(self._tick)

    def _current_interval(self) -> int:
        return max(16, int(FRAME_MS * 100 / self._speed))

    def set_speed(self, speed: int) -> None:
        self._speed = max(10, min(400, int(speed)))
        self._timer.setInterval(self._current_interval())

    def load(self, path: str) -> bool:
        pix = QPixmap(path)
        if pix.isNull():
            return False
        self._atlas = pix
        self.set_state(self._state.id)
        return True

    def set_state(self, state_id: str) -> None:
        state = STATES_BY_ID.get(state_id, STATES[0])
        self._state = state
        self._frames = self._slice(state) if self._atlas else []
        self._idx = 0
        if self._frames:
            self.frame_ready.emit(self._frames[0])

    def _slice(self, state: State) -> list[QPixmap]:
        assert self._atlas is not None
        y = state.row * CELL_H
        return [
            self._atlas.copy(QRect(i * CELL_W, y, CELL_W, CELL_H))
            for i in range(state.frames)
        ]

    def start(self) -> None:
        if self._frames and not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        if not self._frames:
            return
        self._idx = (self._idx + 1) % len(self._frames)
        self.frame_ready.emit(self._frames[self._idx])

    @property
    def state_id(self) -> str:
        return self._state.id
