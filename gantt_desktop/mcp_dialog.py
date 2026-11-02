"""Native, explicit consent and connection details for the local MCP server."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
)

from .dialogs import EditorDialog
from .mcp_server import McpServer


class McpDialog(EditorDialog):
    def __init__(self, controller, server: McpServer):
        is_en = controller.i18n.language == "en"
        super().__init__(controller, "mcpDialog", "MCP Server · LLM Access" if is_en else "MCP-сервер · доступ LLM")
        self.server = server
        self.resize(660, 460)
        explanation = QLabel(
            "Local machine only (127.0.0.1). A client with the token receives the entire open project, "
            "including hidden tasks, notes, resources, and baselines. Connect only trusted LLM clients: "
            "they may transmit data to their provider.\n\n"
            "Read-only access by default. Permitted edits are reflected on the chart, "
            "support Undo/Redo, and are not automatically saved to file. "
            "To apply edits, close this dialog and complete editing."
            if is_en
            else "Только этот компьютер (127.0.0.1). Клиент с токеном получает весь открытый проект, "
                 "включая скрытые задачи, заметки, ресурсы и базовые планы. Подключайте только доверенный LLM-клиент: "
                 "он может передать данные своему провайдеру.\n\n"
                 "По умолчанию доступ только для чтения. Разрешённые изменения видны на диаграмме, "
                 "поддерживают Отмену/Повтор и не сохраняются в файл автоматически. "
                 "Для изменений закройте это окно и завершите редактирование."
        )
        explanation.setWordWrap(True)
        self.layout_root.addWidget(explanation)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.port = QSpinBox()
        self.port.setObjectName("mcpPort")
        self.port.setRange(0, 65535)
        saved_port = 8765
        if self.server.settings is not None:
            saved_port = int(self.server.settings.value("mcp/port", 8765))
        self.port.setValue(saved_port)
        form.addRow("Port (0 for auto)" if is_en else "Порт (0 — свободный)", self.port)
        self.writes = QCheckBox(
            "Allow project edits and Undo/Redo"
            if is_en
            else "Разрешить изменения проекта и Отмену/Повтор"
        )
        self.writes.setObjectName("mcpAllowWrites")
        if self.server.settings is not None:
            self.writes.setChecked(bool(self.server.settings.value("mcp/allow_writes", False, type=bool)))
        form.addRow(self.writes)
        self.persistent_token = QCheckBox(
            "Persistent token across sessions"
            if is_en
            else "Постоянный токен (сохраняется между сессиями)"
        )
        self.persistent_token.setObjectName("mcpPersistentToken")
        self.persistent_token.setChecked(self.server.persistent_token_enabled)
        self.persistent_token.toggled.connect(self._on_persistent_toggled)
        form.addRow(self.persistent_token)
        self.status = QLabel()
        self.status.setObjectName("mcpStatus")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        form.addRow("Status" if is_en else "Состояние", self.status)
        self.url = QLineEdit()
        self.url.setObjectName("mcpUrl")
        self.url.setReadOnly(True)
        form.addRow("Streamable HTTP", self.url)
        self.token = QLineEdit()
        self.token.setObjectName("mcpToken")
        self.token.setReadOnly(True)
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        self.token.textChanged.connect(self._on_token_edited)
        self.regen_button = QPushButton("Regenerate" if is_en else "Сгенерировать")
        self.regen_button.setObjectName("mcpRegenerateToken")
        self.regen_button.clicked.connect(self._on_regenerate_token)
        token_row = QHBoxLayout()
        token_row.addWidget(self.token)
        token_row.addWidget(self.regen_button)
        form.addRow("Access token" if is_en else "Токен доступа", token_row)
        self.layout_root.addLayout(form)
        buttons = QHBoxLayout()
        self.start_button = QPushButton("Start" if is_en else "Включить")
        self.start_button.setObjectName("mcpStart")
        self.start_button.clicked.connect(self.start)
        self.stop_button = QPushButton("Stop" if is_en else "Выключить")
        self.stop_button.setObjectName("mcpStop")
        self.stop_button.clicked.connect(server.stop)
        self.copy_button = QPushButton("Copy configuration" if is_en else "Копировать конфигурацию")
        self.copy_button.setObjectName("mcpCopyConfig")
        self.copy_button.clicked.connect(self.copy_configuration)
        for button in (self.start_button, self.stop_button, self.copy_button):
            buttons.addWidget(button)
        self.layout_root.addLayout(buttons)
        self.warning = QLabel()
        self.warning.setWordWrap(True)
        self.layout_root.addWidget(self.warning)
        self.layout_root.addWidget(self.error)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.button(QDialogButtonBox.StandardButton.Close).setText("Close" if is_en else "Закрыть")
        close.rejected.connect(self.reject)
        self.layout_root.addWidget(close)
        server.changed.connect(self.refresh)
        self.refresh()

    def _on_persistent_toggled(self, checked: bool):
        self.server.set_persistent_token_enabled(checked)
        self.refresh()

    def _on_regenerate_token(self):
        token = self.server.regenerate_persistent_token()
        self.token.setText(token)

    def _on_token_edited(self, text: str):
        if self.server._thread is None and self.persistent_token.isChecked() and text.strip():
            self.server.set_persistent_token(text.strip())

    def refresh(self):
        is_en = self.controller.i18n.language == "en"
        self.status.setText(self.server.status)
        self.url.setText(self.server.url)
        stopped = self.server._thread is None
        if self.server.running:
            self.token.setText(self.server.token)
            self.token.setReadOnly(True)
        elif self.persistent_token.isChecked():
            self.token.setText(self.server.persistent_token)
            self.token.setReadOnly(False)
        else:
            self.token.setText("")
            self.token.setReadOnly(True)
        self.start_button.setEnabled(stopped)
        self.stop_button.setEnabled(not stopped)
        self.port.setEnabled(stopped)
        self.writes.setEnabled(stopped)
        self.persistent_token.setEnabled(stopped)
        self.regen_button.setEnabled(stopped and self.persistent_token.isChecked())
        self.copy_button.setEnabled(self.server.running or (self.persistent_token.isChecked() and bool(self.server.persistent_token)))
        if self.persistent_token.isChecked():
            self.warning.setText(
                "Persistent token is enabled: the token is saved across sessions and remains active when opening "
                "other projects. Update your LLM client configuration (e.g. Gemini CLI) once."
                if is_en
                else "Постоянный токен включён: токен сохраняется между сессиями и остаётся активным "
                     "при открытии других проектов. Настройте конфигурацию LLM-клиента (например, Gemini CLI) один раз."
            )
        else:
            self.warning.setText(
                "Do not publish configuration: it contains an access token. The token changes each time the server starts. "
                "Opening another project or exiting stops the server. Closing this window does not."
                if is_en
                else "Не публикуйте конфигурацию: она содержит токен. При каждом включении токен меняется. "
                     "Открытие другого проекта и выход отключают сервер. Закрытие этого окна — нет."
            )

    def start(self):
        self.error.hide()
        is_en = self.controller.i18n.language == "en"
        port = self.port.value()
        writes = self.writes.isChecked()
        use_persistent = self.persistent_token.isChecked()
        settings = self.server.settings
        if settings is not None:
            settings.setValue("mcp/port", port)
            settings.setValue("mcp/allow_writes", writes)
            settings.setValue("mcp/persistent_token", use_persistent)
            settings.sync()
        try:
            token = self.server.get_persistent_token() if use_persistent else None
            self.server.start(port, writes, token=token)
        except (ImportError, OSError, ValueError) as error:
            self.report_error(f"Failed to start MCP: {error}" if is_en else f"Не удалось включить MCP: {error}")

    def copy_configuration(self):
        import json
        from PySide6.QtGui import QGuiApplication

        config = self.server.configuration()
        if not config and self.persistent_token.isChecked() and self.server.persistent_token:
            port = self.port.value() or 8765
            url = f"http://127.0.0.1:{port}/mcp"
            config = json.dumps({"mcpServers": {"gantt-desktop": {
                "type": "http",
                "url": url,
                "httpUrl": url,
                "headers": {"Authorization": f"Bearer {self.server.persistent_token}"},
            }}}, indent=2)
        if config:
            QGuiApplication.clipboard().setText(config)
