"""Shared transactional XML/CSV/XLSX review. No live data changes before Apply."""
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
from .ganttpro_csv import CsvImport
from .xml_import import XmlImport

if TYPE_CHECKING:
    from .controller import Controller


class XmlImportDialog(EditorDialog):
    def __init__(self, controller: Controller, format_name: str = "XML"):
        prefix = format_name.lower()+"Import"
        super().__init__(controller, prefix+"Dialog", "Проверка импорта "+format_name)
        self.format_name = format_name
        self.report: XmlImport | CsvImport | None = None
        self.resize(1080, 680)
        self.summary = QLabel()
        self.summary.setObjectName(prefix+"Summary")
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.summary.setWordWrap(True)
        self.layout_root.addWidget(self.summary)
        self.name = QLineEdit()
        self.name.setObjectName(prefix+"Name")
        self.layout_root.addWidget(self.name)
        self.table = QTreeWidget()
        self.table.setObjectName(prefix+"Tasks")
        self.table.setHeaderLabels(["Элемент", "Тип", "Начало", "Завершение", "Длительность, ч"]+
                                   (["Трудозатраты, ч", "Стоимость"] if format_name in {"XML", "XLSX"} else []))
        self.table.setColumnWidth(0, 340)
        self.table.setColumnWidth(2, 170)
        self.table.setColumnWidth(3, 170)
        self.layout_root.addWidget(self.table, 1)
        self.warnings = QPlainTextEdit()
        self.warnings.setObjectName(prefix+"Warnings")
        self.warnings.setReadOnly(True)
        self.warnings.setMaximumHeight(150)
        self.layout_root.addWidget(self.warnings)
        note = QLabel("Импорт создаёт новый несохранённый проект. "+format_name+"-источник не перезаписывается; "
                      "сохраните результат как .gantt.json. Отмена оставляет текущий проект без изменений.")
        note.setWordWrap(True)
        self.layout_root.addWidget(note)
        self.layout_root.addWidget(self.error)
        buttons = editor_buttons(self, self.apply, prefix)
        save = buttons.button(buttons.StandardButton.Save)
        save.setText("Импортировать новым проектом")

    def prepare(self, report: XmlImport | CsvImport, source: Path) -> None:
        self.report = report
        self.error.hide()
        self.name.setText(report.project.name)
        self.summary.setText(f"{source.name} · {report.profile} · {len(report.project.tasks)} элементов · "
                             f"{len(report.project.dependencies)} связей · {len(report.project.resources)} ресурсов")
        if self.format_name in {"XML", "XLSX"}:
            leaves = [task for task in report.project.tasks.values() if task.kind != "group"]
            self.summary.setText(self.summary.text()+f" · {sum(task.effort for task in leaves):g} ч · стоимость {sum(task.cost for task in leaves):g}")
        self.warnings.setPlainText("\n".join("• "+text for text in report.warnings))
        self.table.clear()
        def visit(parent: str, owner: QTreeWidgetItem | None) -> None:
            for task in report.project.children(parent):
                start, end = report.project.span(task.id)
                values = [task.name, {"task": "Задача", "group": "Группа", "milestone": "Веха"}[task.kind],
                          start.strftime("%d.%m.%Y %H:%M"), end.strftime("%d.%m.%Y %H:%M"),
                          f"{report.project.calendar.between(start, end)/60:g}"]
                if self.format_name in {"XML", "XLSX"}:
                    members = list(report.project.descendants(task.id)) if task.kind == "group" else [task]
                    leaves = [member for member in members if member.kind != "group"]
                    values += [f"{sum(member.effort for member in leaves):g}", f"{sum(member.cost for member in leaves):g}"]
                item = QTreeWidgetItem(values)
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
        self.controller.load_imported_project(project, self.format_name)
