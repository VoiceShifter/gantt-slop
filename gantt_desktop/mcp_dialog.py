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
        super().__init__(controller, "mcpDialog", "MCP-сервер · доступ LLM")
        self.server = server
        self.resize(660, 420)
        explanation = QLabel(
            "Только этот компьютер (127.0.0.1). Клиент с токеном получает весь открытый проект, "
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
        self.port.setValue(8765)
        form.addRow("Порт (0 — свободный)", self.port)
        self.writes = QCheckBox("Разрешить изменения проекта и Отмену/Повтор")
        self.writes.setObjectName("mcpAllowWrites")
        form.addRow(self.writes)
        self.status = QLabel()
        self.status.setObjectName("mcpStatus")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        form.addRow("Состояние", self.status)
        self.url = QLineEdit()
        self.url.setObjectName("mcpUrl")
        self.url.setReadOnly(True)
        form.addRow("Streamable HTTP", self.url)
        self.token = QLineEdit()
        self.token.setObjectName("mcpToken")
        self.token.setReadOnly(True)
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Токен доступа", self.token)
        self.layout_root.addLayout(form)
        buttons = QHBoxLayout()
        self.start_button = QPushButton("Включить")
        self.start_button.setObjectName("mcpStart")
        self.start_button.clicked.connect(self.start)
        self.stop_button = QPushButton("Выключить")
        self.stop_button.setObjectName("mcpStop")
        self.stop_button.clicked.connect(server.stop)
        self.copy_button = QPushButton("Копировать конфигурацию")
        self.copy_button.setObjectName("mcpCopyConfig")
        self.copy_button.clicked.connect(self.copy_configuration)
        for button in (self.start_button, self.stop_button, self.copy_button):
            buttons.addWidget(button)
        self.layout_root.addLayout(buttons)
        warning = QLabel("Не публикуйте конфигурацию: она содержит токен. При каждом включении токен меняется. "
                         "Открытие другого проекта и выход отключают сервер. Закрытие этого окна — нет.")
        warning.setWordWrap(True)
        self.layout_root.addWidget(warning)
        self.layout_root.addWidget(self.error)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        self.layout_root.addWidget(close)
        server.changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        self.status.setText(self.server.status)
        self.url.setText(self.server.url)
        self.token.setText(self.server.token)
        stopped = self.server._thread is None
        self.start_button.setEnabled(stopped)
        self.stop_button.setEnabled(not stopped)
        self.port.setEnabled(stopped)
        self.writes.setEnabled(stopped)
        self.copy_button.setEnabled(self.server.running)

    def start(self):
        self.error.hide()
        try:
            self.server.start(self.port.value(), self.writes.isChecked())
        except (ImportError, OSError, ValueError) as error:
            self.report_error(f"Не удалось включить MCP: {error}")

    def copy_configuration(self):
        from PySide6.QtGui import QGuiApplication

        config = self.server.configuration()
        if config:
            QGuiApplication.clipboard().setText(config)
