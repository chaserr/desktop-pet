from copy import deepcopy

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import reminders as reminders_mod


class _ReminderEditor(QGroupBox):
    """Edits a single reminder in-place."""

    def __init__(self, item: dict, parent: QWidget | None = None):
        super().__init__(item.get("label", item.get("id", "reminder")), parent)
        self._item = item

        self.enabled = QCheckBox("启用")
        self.enabled.setChecked(bool(item.get("enabled", True)))

        self.label_edit = QLineEdit(str(item.get("label", "")))
        self.label_edit.setPlaceholderText("显示名称")

        self.interval = QSpinBox()
        self.interval.setRange(1, 720)
        self.interval.setSuffix(" 分钟")
        self.interval.setValue(int(item.get("interval_min", 60)))

        self.first_delay = QSpinBox()
        self.first_delay.setRange(0, 720)
        self.first_delay.setSuffix(" 分钟 (0 = 与间隔相同)")
        self.first_delay.setValue(int(item.get("first_delay_min", 0)))

        self.state_hint = QLineEdit(str(item.get("state_hint", "waving")))
        self.state_hint.setPlaceholderText("waving / jumping / idle …")

        self.messages = QPlainTextEdit("\n".join(item.get("messages", [])))
        self.messages.setPlaceholderText("每行一条,提醒时随机轮换")
        self.messages.setMinimumHeight(110)

        form = QFormLayout()
        form.addRow(self.enabled)
        form.addRow("名称:", self.label_edit)
        form.addRow("间隔:", self.interval)
        form.addRow("首次:", self.first_delay)
        form.addRow("动作:", self.state_hint)
        form.addRow("文案:", self.messages)
        self.setLayout(form)

    def to_dict(self) -> dict:
        messages = [
            line.strip()
            for line in self.messages.toPlainText().splitlines()
            if line.strip()
        ]
        return {
            "id": self._item["id"],
            "label": self.label_edit.text().strip() or self._item["id"],
            "enabled": self.enabled.isChecked(),
            "interval_min": self.interval.value(),
            "first_delay_min": self.first_delay.value(),
            "state_hint": self.state_hint.text().strip() or "waving",
            "messages": messages,
        }


class RemindersDialog(QDialog):
    def __init__(self, cfg: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Reminder 配置")
        self.setMinimumSize(460, 560)
        self._cfg = cfg
        self._working = deepcopy(cfg.get("reminders") or reminders_mod.default_reminders_dicts())

        root = QVBoxLayout(self)

        # global switches
        self.global_enabled = QCheckBox("总开关 (Reminders enabled)")
        self.global_enabled.setChecked(bool(cfg.get("reminders_enabled", True)))
        root.addWidget(self.global_enabled)

        self.auto_hide = QCheckBox("气泡自动隐藏 (关掉后需手动点 × 关闭)")
        self.auto_hide.setChecked(bool(cfg.get("bubble_auto_hide", False)))
        root.addWidget(self.auto_hide)

        duration_row = QHBoxLayout()
        duration_row.addWidget(QLabel("自动隐藏时长:"))
        self.duration = QSpinBox()
        self.duration.setRange(2, 60)
        self.duration.setSuffix(" 秒")
        self.duration.setValue(int(cfg.get("bubble_duration_ms", 7000) / 1000))
        self.duration.setEnabled(self.auto_hide.isChecked())
        self.auto_hide.stateChanged.connect(lambda s: self.duration.setEnabled(bool(s)))
        duration_row.addWidget(self.duration)
        duration_row.addStretch(1)
        root.addLayout(duration_row)

        # per-reminder editors
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self._editors_layout = QVBoxLayout(container)
        self._editors: list[_ReminderEditor] = []
        for item in self._working:
            editor = _ReminderEditor(item)
            self._editors.append(editor)
            self._editors_layout.addWidget(editor)
        self._editors_layout.addStretch(1)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        # buttons
        buttons = QDialogButtonBox()
        reset = buttons.addButton("恢复默认", QDialogButtonBox.ResetRole)
        buttons.addButton(QDialogButtonBox.Cancel)
        buttons.addButton(QDialogButtonBox.Save)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        reset.clicked.connect(self._on_reset)
        root.addWidget(buttons)

    def _on_reset(self) -> None:
        confirm = QMessageBox.question(
            self, "恢复默认", "会覆盖当前所有 reminder 编辑,继续吗?"
        )
        if confirm != QMessageBox.Yes:
            return
        self._working = reminders_mod.default_reminders_dicts()
        for editor in self._editors:
            self._editors_layout.removeWidget(editor)
            editor.deleteLater()
        self._editors.clear()
        for item in self._working:
            editor = _ReminderEditor(item)
            self._editors.append(editor)
            self._editors_layout.insertWidget(self._editors_layout.count() - 1, editor)

    def _on_save(self) -> None:
        self._working = [ed.to_dict() for ed in self._editors]
        self.accept()

    def result_reminders(self) -> list[dict]:
        return self._working

    def global_enabled_flag(self) -> bool:
        return self.global_enabled.isChecked()

    def bubble_duration_ms(self) -> int:
        return self.duration.value() * 1000

    def bubble_auto_hide(self) -> bool:
        return self.auto_hide.isChecked()
