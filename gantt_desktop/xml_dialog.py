"""Transactional, native XML import review. No live data changes before Apply."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
)

from .dialogs import EditorDialog
from .domain import Project
from .field_dialogs import editor_buttons
from .xml_import import XmlImport

if TYPE_CHECKING:
    from .controller import Controller


class XmlImportDialog(EditorDialog):
    def __init__(self, controller: Controller):
        super().__init__(controller, "xmlImportDialog", "Проверка импорта XML")
        self.report: XmlImport | None = None
        self.resize(1080, 680)
        self.summary = QLabel()
        self.summary.setObjectName("xmlImportSummary")
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.summary.setWordWrap(True)
        self.layout_root.addWidget(self.summary)
        self.name = QLineEdit()
        self.name.setObjectName("xmlImportName")
        self.layout_root.addWidget(self.name)
        self.table = QTreeWidget()
        self.table.setObjectName("xmlImportTasks")
        self.table.setHeaderLabels(["Элемент", "Тип", "Начало", "Завершение", "Длительность, ч"])
        self.table.setColumnWidth(0, 340)
        self.table.setColumnWidth(2, 170)
        self.table.setColumnWidth(3, 170)
        self.layout_root.addWidget(self.table, 1)
        self.warnings = QPlainTextEdit()
        self.warnings.setObjectName("xmlImportWarnings")
        self.warnings.setReadOnly(True)
        self.warnings.setMaximumHeight(150)
        self.layout_root.addWidget(self.warnings)
        note = QLabel("Импорт создаёт новый несохранённый проект. XML-источник не перезаписывается; "
                      "сохраните результат как .gantt.json. Отмена оставляет текущий проект без изменений.")
        note.setWordWrap(True)
        self.layout_root.addWidget(note)
        self.layout_root.addWidget(self.error)
        buttons = editor_buttons(self, self.apply, "xmlImport")
        save = buttons.button(buttons.StandardButton.Save)
        save.setText("Импортировать новым проектом")

    def prepare(self, report: XmlImport, source: Path) -> None:
        self.report = report
        self.error.hide()
        self.name.setText(report.project.name)
        self.summary.setText(f"{source.name} · {report.profile} · {len(report.project.tasks)} элементов · "
                             f"{len(report.project.dependencies)} связей · {len(report.project.resources)} ресурсов")
        self.warnings.setPlainText("\n".join("• "+text for text in report.warnings))
        self.table.clear()
        def visit(parent: str, owner: QTreeWidgetItem | None) -> None:
            for task in report.project.children(parent):
                start, end = report.project.span(task.id)
                item = QTreeWidgetItem([task.name, {"task": "Задача", "group": "Группа", "milestone": "Веха"}[task.kind],
                                        start.strftime("%d.%m.%Y %H:%M"), end.strftime("%d.%m.%Y %H:%M"),
                                        f"{report.project.calendar.between(start, end)/60:g}"])
                if owner is None:
                    self.table.addTopLevelItem(item)
                else:
                    owner.addChild(item)
                visit(task.id, item)
        visit("", None)
        self.table.expandAll()

    def apply(self) -> None:
        if self.report is None:
            return
        project = Project.from_dict(self.report.project.to_dict())
        project.name = self.name.text().strip()
        try:
            project.validate()
        except ValueError as error:
            self.report_error(str(error))
            return
        if not self.controller.confirm_discard():
            return
        self.accept()
        self.controller.load_imported_project(project)
