from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QMovie, QPixmap

from config import CONFIG_DIR, ensure_dirs
from sprite_atlas import STATES

GIF_PETS_DIR = CONFIG_DIR / "gif-pets"
EXTS = ("gif", "webp", "apng", "png")


class GifPet(QObject):
    """A folder containing per-state animation files (idle.gif, waving.gif, ...)."""

    frame_ready = pyqtSignal(QPixmap)

    def __init__(self, folder: str, parent: QObject | None = None, speed: int = 100):
        super().__init__(parent)
        self._folder = Path(folder)
        self._movies: dict[str, QMovie] = {}
        self._current: QMovie | None = None
        self._state_id = "idle"
        self._speed = max(10, min(400, int(speed)))
        self._load_movies()
        if self._movies:
            self.set_state("idle" if "idle" in self._movies else next(iter(self._movies)))

    def _load_movies(self) -> None:
        for state in STATES:
            for ext in EXTS:
                p = self._folder / f"{state.id}.{ext}"
                if p.is_file():
                    m = QMovie(str(p))
                    m.setSpeed(self._speed)
                    m.frameChanged.connect(self._relay)
                    self._movies[state.id] = m
                    break

    def set_speed(self, speed: int) -> None:
        self._speed = max(10, min(400, int(speed)))
        for m in self._movies.values():
            m.setSpeed(self._speed)

    def has_state(self, state_id: str) -> bool:
        return state_id in self._movies

    @property
    def state_id(self) -> str:
        return self._state_id

    def available_states(self) -> list[str]:
        return list(self._movies.keys())

    def set_state(self, state_id: str) -> None:
        if state_id not in self._movies:
            state_id = "idle" if "idle" in self._movies else next(iter(self._movies))
        if self._current is not None:
            self._current.stop()
        movie = self._movies[state_id]
        self._current = movie
        self._state_id = state_id
        movie.jumpToFrame(0)
        movie.start()
        self.frame_ready.emit(movie.currentPixmap())

    def start(self) -> None:
        if self._current is not None:
            self._current.start()

    def stop(self) -> None:
        if self._current is not None:
            self._current.stop()

    def _relay(self, _frame_idx: int) -> None:
        if self._current is not None:
            self.frame_ready.emit(self._current.currentPixmap())


def list_local() -> list[Path]:
    ensure_dirs()
    if not GIF_PETS_DIR.exists():
        return []
    return sorted(
        d for d in GIF_PETS_DIR.iterdir()
        if d.is_dir() and any((d / f"idle.{e}").is_file() for e in EXTS)
    )
