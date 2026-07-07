from pathlib import Path
from typing import Protocol

from PyQt5.QtCore import QFileSystemWatcher, QPoint, QSize, Qt, QTimer, pyqtBoundSignal
from PyQt5.QtGui import QCursor, QMovie, QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QActionGroup,
    QApplication,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QWidget,
)

import codex_fetcher
import config
import gif_manager
import gif_pet
import reminders as reminders_mod
from bubble import SpeechBubble
from chat_settings_dialog import ChatSettingsDialog
from chat_window import ChatWindow
from gif_pet import GifPet
from reminders import ReminderScheduler
from reminders_dialog import RemindersDialog
from sprite_atlas import STATES, SpriteAnimator


class MultiStatePet(Protocol):
    frame_ready: pyqtBoundSignal
    state_id: str
    def set_state(self, state_id: str) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...


class PetWindow(QWidget):
    def __init__(self, cfg: dict) -> None:
        super().__init__()
        self.cfg = cfg
        self._drag_offset: QPoint | None = None
        self._movie: QMovie | None = None
        self._pet: MultiStatePet | None = None
        self._resume_follow_after_drag = False

        self._build_window()
        self._build_label()
        self._build_follow_timer()
        self._build_bubble_and_reminders()

        pet_path = self.cfg.get("pet_path") or self.cfg.get("gif_path") or self._pick_default_pet()
        if pet_path:
            self.load_pet(pet_path)

        x, y = self.cfg.get("pos", [200, 200])
        self.move(int(x), int(y))
        size = int(self.cfg["size"])
        self.resize(size, size)
        self.label.setGeometry(0, 0, size, size)
        self.show()
        self.raise_()
        self.activateWindow()

    # ---------- setup ----------

    def _build_window(self) -> None:
        flags = (
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.NoDropShadowWindowHint
        )
        if not self.cfg.get("always_on_top", True):
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)

    def _build_label(self) -> None:
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("background: transparent;")
        self.label.setAttribute(Qt.WA_TranslucentBackground, True)

    def _build_follow_timer(self) -> None:
        self._follow_timer = QTimer(self)
        self._follow_timer.setInterval(16)
        self._follow_timer.timeout.connect(self._step_follow)
        if self.cfg.get("follow_mouse"):
            self._follow_timer.start()

    def _build_bubble_and_reminders(self) -> None:
        self._bubble = SpeechBubble()
        self._bubble.set_reply_callback(self._open_chat)
        self._bubble.closed.connect(self._restore_state_after_reminder)
        self._chat_window: ChatWindow | None = None
        reminders = reminders_mod.from_dicts(
            self.cfg.get("reminders") or reminders_mod.default_reminders_dicts()
        )
        self._scheduler = ReminderScheduler(reminders=reminders, parent=self)
        self._scheduler.remind.connect(self._on_reminder)
        self._prev_state_before_reminder: str | None = None
        if self.cfg.get("reminders_enabled", True):
            self._scheduler.start()
        self._build_pending_reminder_watcher()

    def _build_pending_reminder_watcher(self) -> None:
        self._pending_reminder_path = str(config.CONFIG_DIR / "pending_reminder.txt")
        Path(self._pending_reminder_path).parent.mkdir(parents=True, exist_ok=True)
        if not Path(self._pending_reminder_path).exists():
            Path(self._pending_reminder_path).write_text("", encoding="utf-8")
        self._file_watcher = QFileSystemWatcher([self._pending_reminder_path], self)
        self._file_watcher.fileChanged.connect(self._on_pending_reminder_changed)
        QTimer.singleShot(400, self._consume_pending_reminder)

    def _consume_pending_reminder(self) -> None:
        p = Path(self._pending_reminder_path)
        if not p.exists():
            return
        try:
            rid = p.read_text(encoding="utf-8").strip()
        except OSError:
            return
        if not rid:
            return
        try:
            p.write_text("", encoding="utf-8")
        except OSError:
            pass
        self._fire_reminder_now(rid)

    def _on_pending_reminder_changed(self, path: str) -> None:
        # Some writers replace the file, which removes it from the watcher; re-add.
        if path not in self._file_watcher.files():
            self._file_watcher.addPath(path)
        self._consume_pending_reminder()

    def _pick_default_pet(self) -> str | None:
        for d in gif_pet.list_local():
            return str(d)
        for p in codex_fetcher.list_local():
            return p
        for p in gif_manager.list_local():
            return p
        return None

    # ---------- anchor points (used by bubble/chat for head/mouth alignment) ----------

    # Sprite anatomy ratios for a 192x208 chibi cell (Suisei-style codex pets):
    # head center around y=50/208 ≈ 0.24, mouth around y=80/208 ≈ 0.38.
    HEAD_Y_RATIO = 0.24
    MOUTH_Y_RATIO = 0.40

    def head_point(self) -> QPoint:
        """Global center point of the pet's head."""
        size = self.cfg["size"]
        return self.mapToGlobal(QPoint(size // 2, int(size * self.HEAD_Y_RATIO)))

    def mouth_point(self) -> QPoint:
        """Global center point of the pet's mouth."""
        size = self.cfg["size"]
        return self.mapToGlobal(QPoint(size // 2, int(size * self.MOUTH_Y_RATIO)))

    # ---------- pet loading ----------

    @staticmethod
    def _is_sprite_atlas(path: str) -> bool:
        p = Path(path)
        return p.is_file() and p.suffix.lower() == ".webp" and p.parent.name != "assets"

    def load_pet(self, path: str) -> None:
        p = Path(path)
        if not p.exists():
            fallback = self._pick_default_pet()
            if not fallback or fallback == path:
                QMessageBox.warning(self, "Desktop Pet", f"Not found:\n{path}")
                return
            p = Path(fallback)

        if p.is_dir():
            self._load_gif_pet(str(p))
        elif self._is_sprite_atlas(str(p)):
            self._load_atlas(str(p))
        else:
            self._load_single_gif(str(p))

        self.cfg["pet_path"] = str(p)
        self.cfg["gif_path"] = str(p)  # legacy
        config.save(self.cfg)

    def _load_single_gif(self, path: str) -> None:
        self._detach_pet()
        if self._movie is not None:
            self._movie.stop()
        movie = QMovie(path)
        movie.setSpeed(int(self.cfg.get("playback_speed", 100)))
        size = self.cfg["size"]
        movie.setScaledSize(QSize(size, size))
        self.label.setMovie(movie)
        movie.start()
        self._movie = movie

    def _load_atlas(self, path: str) -> None:
        self._detach_movie()
        animator = SpriteAnimator(self, speed=int(self.cfg.get("playback_speed", 100)))
        if not animator.load(path):
            QMessageBox.warning(self, "Desktop Pet", f"Invalid sprite atlas:\n{path}")
            return
        self._attach_pet(animator, initial_state=self.cfg.get("state", "idle"))

    def _load_gif_pet(self, folder: str) -> None:
        self._detach_movie()
        pet = GifPet(folder, self, speed=int(self.cfg.get("playback_speed", 100)))
        if not pet.available_states():
            QMessageBox.warning(self, "Desktop Pet", f"No pet frames in:\n{folder}")
            return
        self._attach_pet(pet, initial_state=self.cfg.get("state", "idle"))

    def _attach_pet(self, pet: MultiStatePet, initial_state: str) -> None:
        self._detach_pet()
        pet.frame_ready.connect(self._on_frame)
        self._pet = pet
        pet.set_state(initial_state)
        pet.start()

    def _detach_pet(self) -> None:
        if self._pet is not None:
            self._pet.stop()
            try:
                self._pet.frame_ready.disconnect(self._on_frame)
            except TypeError:
                pass
            self._pet = None

    def _detach_movie(self) -> None:
        if self._movie is not None:
            self._movie.stop()
            self.label.setMovie(None)
            self._movie = None

    def _on_frame(self, pix: QPixmap) -> None:
        size = self.cfg["size"]
        scaled = pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.label.setPixmap(scaled)

    def set_size(self, size: int) -> None:
        size = max(48, min(600, int(size)))
        self.cfg["size"] = size
        self.resize(size, size)
        self.label.setGeometry(0, 0, size, size)
        if self._movie is not None:
            self._movie.setScaledSize(QSize(size, size))
        if self._pet is not None:
            self._pet.set_state(self._pet.state_id)  # re-emit at new size
        config.save(self.cfg)

    def set_state(self, state_id: str) -> None:
        self.cfg["state"] = state_id
        if self._pet is not None:
            self._pet.set_state(state_id)
        config.save(self.cfg)

    def set_playback_speed(self, percent: int) -> None:
        percent = max(10, min(400, int(percent)))
        self.cfg["playback_speed"] = percent
        if self._movie is not None:
            self._movie.setSpeed(percent)
        if self._pet is not None and hasattr(self._pet, "set_speed"):
            self._pet.set_speed(percent)  # type: ignore[attr-defined]
        config.save(self.cfg)

    # ---------- interactions ----------

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        if getattr(self, "_bubble", None) is not None and self._bubble.isVisible():
            self._bubble.reposition()
        if getattr(self, "_chat_window", None) is not None and self._chat_window.isVisible():
            self._chat_window.follow_target()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
            self._resume_follow_after_drag = self._follow_timer.isActive()
            self._follow_timer.stop()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._drag_offset is not None:
            self._drag_offset = None
            self.cfg["pos"] = [self.x(), self.y()]
            config.save(self.cfg)
            if self._resume_follow_after_drag:
                self._follow_timer.start()
            event.accept()

    def _step_follow(self) -> None:
        target = QCursor.pos()
        size = self.cfg["size"]
        desired = QPoint(target.x() - size // 2 + 24, target.y() - size // 2 + 24)
        cur = self.pos()
        speed = max(1, int(self.cfg.get("follow_speed", 6)))
        dx = (desired.x() - cur.x()) / speed
        dy = (desired.y() - cur.y()) / speed
        if abs(dx) < 0.5 and abs(dy) < 0.5:
            new_pos = desired
        else:
            new_pos = QPoint(cur.x() + int(dx), cur.y() + int(dy))
        self.move(new_pos)
        self._maybe_switch_run_state(new_pos.x() - cur.x())

    # ---------- reminders ----------

    def _on_reminder(self, _rid: str, message: str, state_hint: str) -> None:
        # Reminder bubble never auto-hides — user must dismiss it. Pet state is
        # restored via the bubble.closed signal.
        auto_hide = bool(self.cfg.get("bubble_auto_hide", False))
        duration = int(self.cfg.get("bubble_duration_ms", 0)) if auto_hide else 0
        self._bubble.blow_out_from(self, message, duration)
        if self._pet is not None and state_hint:
            if self._prev_state_before_reminder is None:
                self._prev_state_before_reminder = self._pet.state_id
            self._pet.set_state(state_hint)

    def _restore_state_after_reminder(self) -> None:
        if self._prev_state_before_reminder and self._pet is not None:
            self._pet.set_state(self._prev_state_before_reminder)
        self._prev_state_before_reminder = None

    def _toggle_reminders(self, checked: bool) -> None:
        self.cfg["reminders_enabled"] = bool(checked)
        if checked:
            self._scheduler.start()
        else:
            self._scheduler.stop()
            self._bubble.hide()
        config.save(self.cfg)

    def _fire_reminder_now(self, rid: str) -> None:
        self._scheduler.fire_now(rid)

    def _open_chat(self, seed_pet_message: str = "") -> None:
        if self._chat_window is None:
            self._chat_window = ChatWindow(self.cfg)
        # If the bubble is still on-screen (or was just clicked), animate the
        # chat window growing out of the bubble's last rect for continuity.
        bubble = getattr(self, "_bubble", None)
        if bubble is not None and bubble.geometry().isValid():
            self._chat_window.open_from_rect(self, bubble.geometry(), seed_pet_message)
        else:
            self._chat_window.open_next_to(self, seed_pet_message)

    def _open_chat_settings(self) -> None:
        dlg = ChatSettingsDialog(self.cfg, parent=self)
        if dlg.exec_() != dlg.Accepted:
            return
        self.cfg["llm_provider"] = dlg.provider()
        self.cfg["llm_settings"] = dlg.settings()
        self.cfg["chat_system_prompt"] = dlg.system_prompt()
        config.save(self.cfg)
        if self._chat_window is not None:
            self._chat_window.cfg = self.cfg

    def _open_reminders_config(self) -> None:
        dlg = RemindersDialog(self.cfg, parent=self)
        if dlg.exec_() != dlg.Accepted:
            return
        self.cfg["reminders"] = dlg.result_reminders()
        self.cfg["reminders_enabled"] = dlg.global_enabled_flag()
        self.cfg["bubble_duration_ms"] = dlg.bubble_duration_ms()
        self.cfg["bubble_auto_hide"] = dlg.bubble_auto_hide()
        self._scheduler.reload(reminders_mod.from_dicts(self.cfg["reminders"]))
        if self.cfg["reminders_enabled"] and not self._scheduler.is_running():
            self._scheduler.start()
        elif not self.cfg["reminders_enabled"]:
            self._scheduler.stop()
            self._bubble.hide()
        config.save(self.cfg)

    def _maybe_switch_run_state(self, dx: int) -> None:
        if self._pet is None:
            return
        if abs(dx) < 1:
            desired = "idle"
        elif dx > 0:
            desired = "running-right"
        else:
            desired = "running-left"
        if self._pet.state_id != desired:
            self._pet.set_state(desired)

    # ---------- menu ----------

    def _show_menu(self, pos) -> None:
        menu = QMenu(self)

        menu.addAction("Load local GIF/WebP…").triggered.connect(self._action_load_local)
        menu.addAction("Load from URL…").triggered.connect(self._action_load_url)
        menu.addAction("Load Codex Pet (slug)…").triggered.connect(self._action_load_codex)

        gif_pets = gif_pet.list_local()
        codex_local = codex_fetcher.list_local()
        gif_local = gif_manager.list_local()
        if gif_pets or codex_local or gif_local:
            sub = menu.addMenu("Recent")
            for d in gif_pets:
                sub.addAction(f"{d.name} (multi-gif)").triggered.connect(
                    lambda _=False, path=str(d): self.load_pet(path)
                )
            for p in codex_local:
                sub.addAction(f"{Path(p).parent.name} (codex)").triggered.connect(
                    lambda _=False, path=p: self.load_pet(path)
                )
            for p in gif_local[:15]:
                sub.addAction(Path(p).name).triggered.connect(
                    lambda _=False, path=p: self.load_pet(path)
                )

        menu.addSeparator()

        if self._pet is not None:
            state_menu = menu.addMenu("State")
            grp = QActionGroup(state_menu)
            grp.setExclusive(True)
            available = (
                set(self._pet.available_states())  # type: ignore[attr-defined]
                if isinstance(self._pet, GifPet)
                else {s.id for s in STATES}
            )
            current = self._pet.state_id
            for s in STATES:
                a = QAction(s.label, state_menu, checkable=True)
                a.setChecked(s.id == current)
                a.setEnabled(s.id in available)
                a.triggered.connect(lambda _=False, sid=s.id: self.set_state(sid))
                grp.addAction(a)
                state_menu.addAction(a)

        size_menu = menu.addMenu("Size")
        sgrp = QActionGroup(size_menu)
        sgrp.setExclusive(True)
        for s in (96, 128, 160, 200, 256, 320):
            a = QAction(f"{s}px", size_menu, checkable=True)
            a.setChecked(self.cfg["size"] == s)
            a.triggered.connect(lambda _=False, v=s: self.set_size(v))
            sgrp.addAction(a)
            size_menu.addAction(a)

        speed_menu = menu.addMenu("Playback speed")
        pgrp = QActionGroup(speed_menu)
        pgrp.setExclusive(True)
        current_speed = int(self.cfg.get("playback_speed", 100))
        for pct in (25, 50, 75, 100, 150, 200):
            a = QAction(f"{pct}%", speed_menu, checkable=True)
            a.setChecked(current_speed == pct)
            a.triggered.connect(lambda _=False, v=pct: self.set_playback_speed(v))
            pgrp.addAction(a)
            speed_menu.addAction(a)

        follow_action = menu.addAction("Follow mouse")
        follow_action.setCheckable(True)
        follow_action.setChecked(self._follow_timer.isActive())
        follow_action.triggered.connect(self._toggle_follow)

        reminders_menu = menu.addMenu("Reminders")
        rem_enabled = reminders_menu.addAction("Enabled")
        rem_enabled.setCheckable(True)
        rem_enabled.setChecked(self._scheduler.is_running())
        rem_enabled.triggered.connect(self._toggle_reminders)
        reminders_menu.addAction("Configure…").triggered.connect(self._open_reminders_config)
        reminders_menu.addSeparator()
        for r in self._scheduler.reminders:
            act = reminders_menu.addAction(f"Show now: {r.label}")
            act.triggered.connect(lambda _=False, rid=r.id: self._fire_reminder_now(rid))

        chat_menu = menu.addMenu("Chat")
        chat_menu.addAction("Open chat…").triggered.connect(lambda: self._open_chat(""))
        chat_menu.addAction("LLM settings…").triggered.connect(self._open_chat_settings)

        top_action = menu.addAction("Always on top")
        top_action.setCheckable(True)
        top_action.setChecked(self.cfg.get("always_on_top", True))
        top_action.triggered.connect(self._toggle_on_top)

        menu.addSeparator()
        menu.addAction("Quit").triggered.connect(QApplication.instance().quit)
        menu.exec_(self.mapToGlobal(pos))

    def _action_load_local(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose pet image",
            str(Path.home()),
            "Animations (*.gif *.webp *.apng *.png)",
        )
        if not path:
            return
        try:
            stored = gif_manager.import_local(path)
        except OSError as exc:
            QMessageBox.warning(self, "Desktop Pet", f"Failed to import: {exc}")
            return
        self.load_pet(stored)

    def _action_load_url(self) -> None:
        url, ok = QInputDialog.getText(self, "Load from URL", "GIF/WebP URL:")
        if not ok or not url.strip():
            return
        try:
            path = gif_manager.download(url.strip())
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Desktop Pet", f"Download failed: {exc}")
            return
        self.load_pet(path)

    def _action_load_codex(self) -> None:
        slug, ok = QInputDialog.getText(
            self,
            "Load Codex Pet",
            "Pet slug (e.g. hoshimachi-suisei):",
            text="hoshimachi-suisei",
        )
        if not ok or not slug.strip():
            return
        try:
            path = codex_fetcher.fetch(slug.strip())
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Desktop Pet", f"Fetch failed: {exc}")
            return
        self.load_pet(str(path))

    def _toggle_follow(self, checked: bool) -> None:
        self.cfg["follow_mouse"] = bool(checked)
        if checked:
            self._follow_timer.start()
        else:
            self._follow_timer.stop()
            if self._pet is not None:
                self._pet.set_state("idle")
        config.save(self.cfg)

    def _toggle_on_top(self, checked: bool) -> None:
        self.cfg["always_on_top"] = bool(checked)
        flags = self.windowFlags()
        if checked:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()
        if checked:
            # Re-apply Cocoa-level tweaks; setWindowFlags rebuilds the NSWindow.
            import macos_bridge
            macos_bridge.float_over_everything(self)
        config.save(self.cfg)
