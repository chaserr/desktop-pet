from PyQt5.QtCore import QObject, QSize, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import llm_client

USER_BG = "#dcf5ff"
PET_BG = "#ffffff"
SYSTEM_BG = "#fff2cc"
WINDOW_MIN = QSize(340, 420)


class _ChatWorker(QThread):
    reply_ready = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(
        self,
        provider: str,
        api_key: str,
        model: str,
        base_url: str,
        messages: list[dict],
        system_prompt: str,
        use_local_cli: bool = False,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._provider = provider
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._messages = list(messages)
        self._system_prompt = system_prompt
        self._use_local_cli = use_local_cli

    def run(self) -> None:
        try:
            text = llm_client.chat(
                self._provider,
                self._api_key,
                self._model,
                self._base_url,
                self._messages,
                self._system_prompt,
                use_local_cli=self._use_local_cli,
            )
        except llm_client.LlmError as exc:
            self.error.emit(str(exc))
            return
        except Exception as exc:  # noqa: BLE001 — surface any unexpected failure
            self.error.emit(f"未预期错误: {exc}")
            return
        self.reply_ready.emit(text)


class _MessageRow(QFrame):
    def __init__(self, sender: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        bg = {"user": USER_BG, "pet": PET_BG, "system": SYSTEM_BG}.get(sender, PET_BG)
        align = Qt.AlignRight if sender == "user" else Qt.AlignLeft
        self.setStyleSheet(
            f"QFrame {{ background: {bg}; border-radius: 10px; padding: 6px 10px; }}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setFont(QFont("PingFang SC", 12))
        label.setStyleSheet("background: transparent;")
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout.addWidget(label, 0, align)


class ChatWindow(QWidget):
    def __init__(self, cfg: dict, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool,
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.cfg = cfg
        self._target: QWidget | None = None
        self._history: list[dict] = []
        self._worker: _ChatWorker | None = None
        self._pending_row: _MessageRow | None = None

        self.setMinimumSize(WINDOW_MIN)
        self.resize(WINDOW_MIN)
        self._build_ui()

    # ---------- ui ----------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        card = QFrame(self)
        card.setObjectName("card")
        card.setStyleSheet(
            """
            #card {
                background: rgba(255, 255, 255, 245);
                border: 1px solid rgba(0, 0, 0, 40);
                border-radius: 14px;
            }
            """
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 12)
        card_layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("苏酱 · 对话")
        title.setFont(QFont("PingFang SC", 13, QFont.Bold))
        header.addWidget(title, 1)
        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            "QPushButton { border: none; font-size: 16px; }"
            "QPushButton:hover { color: #d33; }"
        )
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)
        card_layout.addLayout(header)

        provider = self.cfg.get("llm_provider", "claude")
        info = QLabel(f"provider: {provider}  ·  点右下齿轮改配置")
        info.setStyleSheet("color: #888; font-size: 11px;")
        card_layout.addWidget(info)
        self._provider_label = info

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setStyleSheet("background: transparent;")
        self._messages_holder = QWidget()
        self._messages_layout = QVBoxLayout(self._messages_holder)
        self._messages_layout.setContentsMargins(0, 0, 0, 0)
        self._messages_layout.setSpacing(6)
        self._messages_layout.addStretch(1)
        self._scroll.setWidget(self._messages_holder)
        card_layout.addWidget(self._scroll, 1)

        input_row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("输入消息…回车发送")
        self._input.returnPressed.connect(self._on_send)
        input_row.addWidget(self._input, 1)
        self._send_btn = QPushButton("发送")
        self._send_btn.clicked.connect(self._on_send)
        input_row.addWidget(self._send_btn)
        self._settings_btn = QPushButton("⚙")
        self._settings_btn.setFixedWidth(30)
        self._settings_btn.clicked.connect(self._open_settings)
        input_row.addWidget(self._settings_btn)
        card_layout.addLayout(input_row)

        root.addWidget(card)

    # ---------- lifecycle ----------

    def open_next_to(self, target: QWidget, seed_pet_message: str = "") -> None:
        self._target = target
        self._reposition_for(target)
        if seed_pet_message and not self._history:
            self._append_row("pet", seed_pet_message)
            self._history.append({"role": "assistant", "content": seed_pet_message})
        self.show()
        self.raise_()
        self.activateWindow()
        self._input.setFocus()

    def follow_target(self) -> None:
        if self._target is not None and self.isVisible():
            self._reposition_for(self._target)

    def _reposition_for(self, target: QWidget) -> None:
        geom = target.frameGeometry()
        screen = QApplication.primaryScreen().availableGeometry()
        right_x = geom.right() + 8
        left_x = geom.left() - self.width() - 8
        if right_x + self.width() <= screen.right():
            x = right_x
        elif left_x >= screen.left():
            x = left_x
        else:
            x = max(screen.left(), min(right_x, screen.right() - self.width()))
        y = geom.center().y() - self.height() // 2
        y = max(screen.top(), min(y, screen.bottom() - self.height()))
        self.move(x, y)

    # ---------- chat ----------

    def _on_send(self) -> None:
        text = self._input.text().strip()
        if not text or self._worker is not None:
            return
        self._input.clear()
        self._append_row("user", text)
        self._history.append({"role": "user", "content": text})
        self._start_worker()

    def _start_worker(self) -> None:
        provider = self.cfg.get("llm_provider", "claude")
        settings = (self.cfg.get("llm_settings") or {}).get(provider, {})
        api_key = settings.get("api_key", "")
        use_cli = bool(settings.get("use_local_cli", False))
        if not use_cli and not api_key:
            self._append_row(
                "system",
                f"未配置 {provider} 的 API key,点右下 ⚙ 打开设置。",
            )
            self._history.pop()
            return
        self._pending_row = self._append_row("pet", "…")
        self._send_btn.setEnabled(False)
        self._input.setEnabled(False)
        worker = _ChatWorker(
            provider=provider,
            api_key=api_key,
            model=settings.get("model", ""),
            base_url=settings.get("base_url", ""),
            messages=self._history,
            system_prompt=self.cfg.get("chat_system_prompt", ""),
            use_local_cli=use_cli,
            parent=self,
        )
        worker.reply_ready.connect(self._on_reply_ready)
        worker.error.connect(self._on_worker_error)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _on_reply_ready(self, text: str) -> None:
        if self._pending_row is not None:
            self._replace_pending_text(text)
        else:
            self._append_row("pet", text)
        self._history.append({"role": "assistant", "content": text})
        self._finish_worker()

    def _on_worker_error(self, msg: str) -> None:
        if self._pending_row is not None:
            self._replace_pending_text(f"[错误] {msg}")
        else:
            self._append_row("system", f"[错误] {msg}")
        # remove the last user turn so retrying doesn't re-post it
        if self._history and self._history[-1]["role"] == "user":
            pass  # keep it; user may want to retry manually
        self._finish_worker()

    def _finish_worker(self) -> None:
        self._pending_row = None
        self._worker = None
        self._send_btn.setEnabled(True)
        self._input.setEnabled(True)
        self._input.setFocus()

    # ---------- misc ----------

    def _append_row(self, sender: str, text: str) -> _MessageRow:
        row = _MessageRow(sender, text)
        # Insert before the stretch (last item).
        idx = max(0, self._messages_layout.count() - 1)
        self._messages_layout.insertWidget(idx, row)
        self._scroll_to_bottom()
        return row

    def _replace_pending_text(self, text: str) -> None:
        # Rebuild the row so the styled QLabel picks up the new text.
        if self._pending_row is None:
            return
        idx = self._messages_layout.indexOf(self._pending_row)
        self._messages_layout.removeWidget(self._pending_row)
        self._pending_row.deleteLater()
        new_row = _MessageRow("pet", text)
        self._messages_layout.insertWidget(idx, new_row)
        self._pending_row = new_row
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _open_settings(self) -> None:
        # Lazy import to avoid a circular dependency with pet_window.
        from chat_settings_dialog import ChatSettingsDialog
        dlg = ChatSettingsDialog(self.cfg, parent=self)
        if dlg.exec_() != dlg.Accepted:
            return
        self.cfg["llm_provider"] = dlg.provider()
        self.cfg["llm_settings"] = dlg.settings()
        self.cfg["chat_system_prompt"] = dlg.system_prompt()
        import config
        config.save(self.cfg)
        self._provider_label.setText(
            f"provider: {self.cfg['llm_provider']}  ·  点右下齿轮改配置"
        )
