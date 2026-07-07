from copy import deepcopy

from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

import auth_detect
import llm_client


class _ProviderPanel(QGroupBox):
    def __init__(self, provider: str, settings: dict, parent: QWidget | None = None):
        super().__init__(provider, parent)
        self._provider = provider
        self._supports_cli = provider in ("claude", "codex")

        self._api_key = QLineEdit(settings.get("api_key", ""))
        self._api_key.setPlaceholderText("填入 API key")
        self._api_key.setEchoMode(QLineEdit.Password)
        self._model = QLineEdit(settings.get("model", ""))
        self._base_url = QLineEdit(settings.get("base_url", ""))

        form = QFormLayout(self)

        if self._supports_cli:
            probe = auth_detect.claude() if provider == "claude" else auth_detect.codex()
            status_bits = []
            status_bits.append("CLI 已安装" if probe.installed else "CLI 未安装")
            status_bits.append("已登录" if probe.logged_in else "未登录")
            color = "#2a9d3c" if probe.usable else "#a83232"
            status_label = QLabel(f"本机检测:{' / '.join(status_bits)}")
            status_label.setStyleSheet(f"color: {color}; font-size: 11px;")
            form.addRow(status_label)

            self._use_cli = QCheckBox("使用本机 CLI 登录 (免 api_key)")
            self._use_cli.setChecked(bool(settings.get("use_local_cli", False)))
            self._use_cli.setEnabled(probe.usable)
            if not probe.usable:
                self._use_cli.setToolTip(
                    "先在终端里跑 `claude login` / `codex login` 完成登录"
                    if not probe.logged_in
                    else "未在 PATH 找到该 CLI"
                )
            self._use_cli.stateChanged.connect(self._sync_api_key_state)
            form.addRow(self._use_cli)
        else:
            self._use_cli = None

        form.addRow("API key:", self._api_key)
        form.addRow("Model:", self._model)
        form.addRow("Base URL:", self._base_url)

        self._sync_api_key_state()

    def _sync_api_key_state(self) -> None:
        if self._use_cli is not None and self._use_cli.isChecked():
            self._api_key.setPlaceholderText("走本机 CLI 时可留空")
        else:
            self._api_key.setPlaceholderText("填入 API key")

    def to_dict(self) -> dict:
        out = {
            "api_key": self._api_key.text().strip(),
            "model": self._model.text().strip(),
            "base_url": self._base_url.text().strip(),
        }
        if self._use_cli is not None:
            out["use_local_cli"] = self._use_cli.isChecked()
        return out


class ChatSettingsDialog(QDialog):
    def __init__(self, cfg: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("LLM 配置")
        self.setMinimumWidth(460)
        self._cfg = cfg
        stored_settings = deepcopy(cfg.get("llm_settings") or {})

        root = QVBoxLayout(self)

        provider_form = QFormLayout()
        self._provider_combo = QComboBox()
        for p in llm_client.PROVIDERS:
            self._provider_combo.addItem(p)
        idx = self._provider_combo.findText(cfg.get("llm_provider", "claude"))
        if idx >= 0:
            self._provider_combo.setCurrentIndex(idx)
        provider_form.addRow("当前 provider:", self._provider_combo)
        root.addLayout(provider_form)

        self._panels: dict[str, _ProviderPanel] = {}
        for p in llm_client.PROVIDERS:
            panel = _ProviderPanel(p, stored_settings.get(p, {}))
            self._panels[p] = panel
            root.addWidget(panel)

        prompt_group = QGroupBox("System prompt (对宠物人设的定义)")
        prompt_layout = QVBoxLayout(prompt_group)
        self._prompt = QPlainTextEdit(cfg.get("chat_system_prompt", ""))
        self._prompt.setMinimumHeight(100)
        prompt_layout.addWidget(self._prompt)
        root.addWidget(prompt_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def provider(self) -> str:
        return self._provider_combo.currentText()

    def settings(self) -> dict:
        return {p: panel.to_dict() for p, panel in self._panels.items()}

    def system_prompt(self) -> str:
        return self._prompt.toPlainText().strip()
