"""System-styled QWidget dialogs for the Qt Quick workspace."""
from __future__ import annotations

import weakref
from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import Property, QObject, Qt, Signal, Slot
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

if TYPE_CHECKING:
    from .controller import Controller
    from .mcp_server import McpServer

DAY_NAMES = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
RELATIONS = ("FS", "SS", "FF", "SF")


def day_controls(prefix: str) -> tuple[QWidget, list[QCheckBox]]:
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    boxes = []
    for i, name in enumerate(DAY_NAMES):
        box = QCheckBox(name)
        box.setObjectName(f"{prefix}-{i}")
        layout.addWidget(box)
        boxes.append(box)
    layout.addStretch()
    return widget, boxes


def checked_days(boxes: list[QCheckBox]) -> list[int]:
    return [i for i, box in enumerate(boxes) if box.isChecked()]


class EditorDialog(QDialog):
    def __init__(self, controller: Controller, name: str, title: str):
        super().__init__()
        self.controller = weakref.proxy(controller)
        self.setObjectName(name)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.layout_root = QVBoxLayout(self)
        self.error = QLabel()
        self.error.setObjectName("dialogError")
        self.error.setTextFormat(Qt.TextFormat.PlainText)
        self.error.setWordWrap(True)
        self.error.hide()
        controller.toast.connect(self.report_error)

    @Slot(str)
    def report_error(self, message: str) -> None:
        if self.isVisible():
            self.error.setText(message)
            self.error.show()


class ResourceDialog(EditorDialog):
    def __init__(self, controller: Controller):
        super().__init__(controller, "resourceManager", "Люди и доступность ресурсов")
        self.resource_id = ""
        self.capacity_hours = 8.0
        self.resize(760, 540)
        description = QLabel("Локальные ресурсы проекта. Без приглашений и учётных записей.")
        description.setWordWrap(True)
        self.layout_root.addWidget(description)
        body = QHBoxLayout()
        left = QVBoxLayout()
        self.people = QListWidget()
        self.people.setObjectName("resourceList")
        self.people.currentItemChanged.connect(self.select_person)
        left.addWidget(self.people)
        add = QPushButton("Добавить человека")
        add.setObjectName("newResourceButton")
        add.setAutoDefault(False)
        add.clicked.connect(lambda: self.load_resource(""))
        left.addWidget(add)
        body.addLayout(left, 1)
        group = QGroupBox("Календарь ресурса")
        form = QFormLayout(group)
        self.name = QLineEdit()
        self.name.setObjectName("resourceName")
        self.capacity = QDoubleSpinBox()
        self.capacity.setObjectName("resourceCapacity")
        self.capacity.setRange(0, 24)
        self.capacity.setDecimals(2)
        self.capacity.setSuffix(" ч")
        self.capacity.valueChanged.connect(self.capacity_changed)
        days_widget, self.days = day_controls("resourceDay")
        form.addRow("Имя", self.name)
        form.addRow("Доступно часов в день", self.capacity)
        form.addRow("Рабочие дни", days_widget)
        self.exceptions_button = QPushButton("Отпуска и исключения…")
        self.exceptions_button.setObjectName("resourceExceptionsButton")
        self.exceptions_button.setAutoDefault(False)
        self.exceptions_button.clicked.connect(lambda: self.controller.dialogs.showCalendar(self.resource_id))
        form.addRow(self.exceptions_button)
        note = QLabel("Доступность влияет на предупреждения, а не переносит задачи.")
        note.setWordWrap(True)
        form.addRow(note)
        actions = QHBoxLayout()
        self.remove = QPushButton("Удалить")
        self.remove.setObjectName("removeResourceButton")
        self.remove.clicked.connect(self.confirm_remove)
        save = QPushButton("Сохранить ресурс")
        save.setObjectName("saveResourceButton")
        self.save_button = save
        save.clicked.connect(self.save_resource)
        actions.addWidget(self.remove)
        actions.addStretch()
        actions.addWidget(save)
        form.addRow(actions)
        body.addWidget(group, 2)
        self.layout_root.addLayout(body, 1)
        project = QGroupBox("Рабочие дни проекта · планирование задач")
        project_layout = QVBoxLayout(project)
        project_days, self.project_days = day_controls("projectDay")
        project_layout.addWidget(project_days)
        exceptions = QPushButton("Праздники и исключения…")
        exceptions.setObjectName("projectExceptionsButton")
        exceptions.setAutoDefault(False)
        exceptions.clicked.connect(lambda: self.controller.dialogs.showCalendar(""))
        project_layout.addWidget(exceptions, 0, Qt.AlignmentFlag.AlignLeft)
        note = QLabel("Изменение календаря проекта пересчитывает сроки одной отменяемой операцией. "
                      "Календарь человека остаётся независимым.")
        note.setWordWrap(True)
        project_layout.addWidget(note)
        apply_calendar = QPushButton("Применить календарь")
        apply_calendar.setObjectName("applyProjectCalendar")
        apply_calendar.clicked.connect(self.apply_calendar)
        project_layout.addWidget(apply_calendar, 0, Qt.AlignmentFlag.AlignRight)
        self.layout_root.addWidget(project)
        self.layout_root.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setObjectName("closeResourcesButton")
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Закрыть")
        buttons.rejected.connect(self.reject)
        self.layout_root.addWidget(buttons)
        controller.viewChanged.connect(self.refresh_catalog)

    def prepare(self, resource_id: str) -> None:
        self.error.hide()
        self.refresh_catalog()
        self.load_resource(resource_id or next(iter(self.controller.project.resources), ""))
        for i, box in enumerate(self.project_days):
            box.setChecked(i in self.controller.project.calendar.workdays)

    @Slot()
    def refresh_catalog(self) -> None:
        self.people.blockSignals(True)
        self.people.clear()
        for resource in self.controller.project.resources.values():
            item = QListWidgetItem(resource.name)
            item.setData(Qt.ItemDataRole.UserRole, resource.id)
            self.people.addItem(item)
            if resource.id == self.resource_id:
                self.people.setCurrentItem(item)
        self.people.blockSignals(False)

    def select_person(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is not None:
            self.load_resource(current.data(Qt.ItemDataRole.UserRole))

    def load_resource(self, resource_id: str) -> None:
        resource = self.controller.project.resources.get(resource_id)
        self.resource_id = resource.id if resource else ""
        self.name.setText(resource.name if resource else "")
        self.capacity_hours = resource.capacity if resource else 8
        self.capacity.blockSignals(True)
        self.capacity.setValue(self.capacity_hours)
        self.capacity.blockSignals(False)
        for i, box in enumerate(self.days):
            box.setChecked(i in (resource.workdays if resource else range(5)))
        self.remove.setEnabled(resource is not None)
        self.exceptions_button.setEnabled(resource is not None)
        if resource is None:
            self.people.blockSignals(True)
            self.people.setCurrentRow(-1)
            self.people.blockSignals(False)
            self.name.setFocus()
        self.save_button.setDefault(True)

    @Slot(float)
    def capacity_changed(self, value: float) -> None:
        self.capacity_hours = value

    @Slot()
    def save_resource(self) -> None:
        self.error.hide()
        key = self.controller.saveResource(self.resource_id, self.name.text(),
                                           str(self.capacity_hours), checked_days(self.days))
        if key:
            self.resource_id = key
            self.refresh_catalog()
            self.load_resource(key)

    @Slot()
    def apply_calendar(self) -> None:
        self.error.hide()
        self.controller.setProjectWorkdays(checked_days(self.project_days))

    @Slot()
    def confirm_remove(self) -> None:
        key = self.resource_id
        box = QMessageBox(QMessageBox.Icon.Question, "Удалить ресурс?",
                          "Назначения ресурса будут сняты. Задачи и общие трудозатраты сохранятся. "
                          "Действие можно отменить.",
                          QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel, self)
        box.setObjectName("deleteResourceDialog")
        box.button(QMessageBox.StandardButton.Cancel).setText("Отмена")
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        def confirmed(result: int) -> None:
            if result == QMessageBox.StandardButton.Ok and self.controller.removeResource(key):
                self.refresh_catalog()
                self.load_resource(next(iter(self.controller.project.resources), ""))
        box.finished.connect(confirmed)
        box.open()


class AssignmentDialog(EditorDialog):
    manageRequested = Signal()

    def __init__(self, controller: Controller):
        super().__init__(controller, "resourcePicker", "Исполнители и трудозатраты")
        self.task_id = ""
        self.chosen: list[str] = []
        self.hours: dict[str, float] = {}
        self.spins: dict[str, QDoubleSpinBox] = {}
        self.total = 0.0
        self.resize(540, 360)
        self.caption = QLabel()
        self.caption.setTextFormat(Qt.TextFormat.PlainText)
        self.layout_root.addWidget(self.caption)
        note = QLabel("Выберите людей. По умолчанию трудозатраты делятся поровну.")
        note.setWordWrap(True)
        self.layout_root.addWidget(note)
        self.table = QTableWidget(0, 3)
        self.table.setObjectName("assignmentTable")
        self.table.setHorizontalHeaderLabels(["", "Ресурс", "Всего часов"])
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.layout_root.addWidget(self.table)
        self.layout_root.addWidget(self.error)
        actions = QHBoxLayout()
        manage = QPushButton("Ресурсы…")
        manage.clicked.connect(self.manage)
        actions.addWidget(manage)
        actions.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Применить")
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("applyResourceAssignment")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("cancelResourceAssignment")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        buttons.accepted.connect(self.apply)
        buttons.rejected.connect(self.reject)
        actions.addWidget(buttons)
        self.layout_root.addLayout(actions)

    def prepare(self, task_id: str, ids: list[str] | None = None) -> None:
        task = self.controller.project.tasks[task_id]
        self.task_id, self.total = task_id, task.effort
        self.chosen = list(task.resource_ids if ids is None else ids)
        self.hours = {key: task.effort * (task.resource_shares[i] if task.resource_shares else 1 / len(task.resource_ids))
                      for i, key in enumerate(task.resource_ids)}
        if len(self.chosen) != len(task.resource_ids) or set(self.chosen) != set(task.resource_ids):
            self.hours = {key: task.effort / len(self.chosen) for key in self.chosen}
        self.caption.setText(task.name)
        self.error.hide()
        self.spins.clear()
        self.table.setRowCount(0)
        for resource in self.controller.project.resources.values():
            row = self.table.rowCount()
            self.table.insertRow(row)
            check = QCheckBox()
            check.setObjectName("assign-resource-" + resource.id)
            check.setChecked(resource.id in self.chosen)
            check.clicked.connect(lambda checked, key=resource.id: self.toggle(key, checked))
            self.table.setCellWidget(row, 0, check)
            name = QTableWidgetItem(resource.name)
            name.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 1, name)
            spin = QDoubleSpinBox()
            spin.setObjectName("assignmentHours-" + resource.id)
            spin.setRange(0, 1e9)
            spin.setDecimals(2)
            spin.setValue(self.hours.get(resource.id, 0))
            spin.setEnabled(resource.id in self.chosen)
            spin.valueChanged.connect(lambda value, key=resource.id: self.hours.update({key: value}))
            self.table.setCellWidget(row, 2, spin)
            self.spins[resource.id] = spin
        self.table.resizeRowsToContents()

    def toggle(self, key: str, checked: bool) -> None:
        if checked and key not in self.chosen:
            self.chosen.append(key)
        elif not checked and key in self.chosen:
            self.chosen.remove(key)
        self.hours = {key: self.total / len(self.chosen) for key in self.chosen}
        for resource_id, spin in self.spins.items():
            spin.blockSignals(True)
            spin.setEnabled(resource_id in self.chosen)
            spin.setValue(self.hours.get(resource_id, 0))
            spin.blockSignals(False)

    @Slot()
    def apply(self) -> None:
        self.error.hide()
        if self.controller.assignResources(self.task_id, self.chosen, [self.hours[key] for key in self.chosen]):
            self.accept()

    @Slot()
    def manage(self) -> None:
        self.reject()
        self.manageRequested.emit()


class DependencyDialog(EditorDialog):
    def __init__(self, controller: Controller):
        super().__init__(controller, "dependencyDialog", "Зависимость")
        self.link_id = ""
        self.resize(540, 290)
        form = QFormLayout()
        self.source = QComboBox()
        self.source.setObjectName("dependencySource")
        self.target = QComboBox()
        self.target.setObjectName("dependencyTarget")
        self.kind = QComboBox()
        self.kind.setObjectName("dependencyKind")
        self.kind.addItems(["FS · Окончание → Начало", "SS · Начало → Начало",
                            "FF · Окончание → Окончание", "SF · Начало → Окончание"])
        self.lag = QDoubleSpinBox()
        self.lag.setObjectName("dependencyLag")
        self.lag.setRange(-1e9, 1e9)
        self.lag.setDecimals(2)
        self.lag.setSuffix(" ч")
        form.addRow("Предшественник", self.source)
        form.addRow("Последователь", self.target)
        form.addRow("Тип связи", self.kind)
        form.addRow("Лаг, рабочие часы", self.lag)
        self.layout_root.addLayout(form)
        note = QLabel("Отрицательный лаг разрешён. Циклические связи не допускаются.")
        note.setWordWrap(True)
        self.layout_root.addWidget(note)
        self.layout_root.addWidget(self.error)
        actions = QHBoxLayout()
        self.remove = QPushButton("Удалить связь")
        self.remove.setObjectName("deleteDependency")
        self.remove.clicked.connect(self.delete)
        actions.addWidget(self.remove)
        actions.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.save = buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save.setObjectName("saveDependency")
        self.save.setText("Сохранить")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("cancelDependency")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        buttons.accepted.connect(self.apply)
        buttons.rejected.connect(self.reject)
        actions.addWidget(buttons)
        self.layout_root.addLayout(actions)
        self.source.currentIndexChanged.connect(self.update_save)
        self.target.currentIndexChanged.connect(self.update_save)

    def prepare(self, source: str, target: str, kind: str, link_id: str) -> None:
        self.link_id = link_id
        detail = self.controller.linkDetails(link_id) if link_id else {}
        self.error.hide()
        self.setWindowTitle("Изменить зависимость" if link_id else "Добавить зависимость")
        for combo, selected in ((self.source, source), (self.target, target)):
            combo.clear()
            combo.addItem("Выберите задачу", "")
            for task in self.controller.project.tasks.values():
                combo.addItem(task.name, task.id)
            combo.setCurrentIndex(max(0, combo.findData(selected)))
        self.kind.setCurrentIndex(RELATIONS.index(kind))
        self.lag.setValue(detail.get("lag", 0))
        self.remove.setVisible(bool(link_id))
        self.update_save()

    @Slot()
    def update_save(self) -> None:
        source, target = self.source.currentData(), self.target.currentData()
        self.save.setEnabled(bool(source and target and source != target))

    @Slot()
    def apply(self) -> None:
        self.error.hide()
        args = (self.source.currentData(), self.target.currentData(),
                RELATIONS[self.kind.currentIndex()], str(self.lag.value()))
        ok = self.controller.updateDependency(self.link_id, *args) if self.link_id else self.controller.addDependency(*args)
        if ok:
            self.accept()

    @Slot()
    def delete(self) -> None:
        self.controller.removeDependency(self.link_id)
        self.accept()


class NativeDialogs(QObject):
    modalChanged = Signal()
    columnVisibilityChanged = Signal(str, bool)
    mcpChanged = Signal()

    def __init__(self, controller: Controller):
        super().__init__(controller)
        self._controller_ref = weakref.ref(controller)
        self.window: QWindow | None = None
        self._editors: dict[str, QDialog] = {}
        self._active: set[QDialog] = set()
        self._actions: dict[QMessageBox, Callable[[], object]] = {}
        self._link_id = ""
        self._mcp: McpServer | None = None
        controller.projectLoaded.connect(self.closeAll)

    @property
    def controller(self) -> Controller:
        controller = self._controller_ref()
        assert controller is not None
        return controller

    @Property(bool, notify=modalChanged)
    def modalOpen(self):
        return bool(self._active)

    @Property(str, notify=mcpChanged)
    def mcpStatus(self):
        return self._mcp.label if self._mcp is not None else ""

    @Property(str, notify=modalChanged)
    def activeLinkId(self):
        return self._link_id

    def attach(self, window: QWindow) -> None:
        self.window = window
        window.visibleChanged.connect(self.visibility_changed)

    @Slot(bool)
    def visibility_changed(self, visible: bool) -> None:
        if not visible:
            self.closeAll()

    def present(self, dialog: QDialog) -> None:
        dialog.winId()
        handle = dialog.windowHandle()
        if handle is not None and self.window is not None:
            handle.setTransientParent(self.window)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._active.add(dialog)
        dialog.finished.connect(self.finished, Qt.ConnectionType.UniqueConnection)
        self.modalChanged.emit()
        dialog.open()
        dialog.raise_()
        dialog.activateWindow()

    @Slot(int)
    def finished(self, result: int) -> None:
        dialog = self.sender()
        if isinstance(dialog, QDialog):
            self._active.discard(dialog)
            if dialog.objectName() == "dependencyDialog":
                self._link_id = ""
        if isinstance(dialog, QMessageBox):
            action = self._actions.pop(dialog, None)
            if result == QMessageBox.StandardButton.Ok and action is not None:
                action()
            dialog.deleteLater()
        self.modalChanged.emit()

    @Slot(dict)
    def showExport(self, context: dict) -> None:
        from .export_dialog import ExportDialog

        dialog = self._editors.get("export")
        if not isinstance(dialog, ExportDialog):
            dialog = ExportDialog(self.controller)
            self._editors["export"] = dialog
        dialog.prepare(context)
        self.present(dialog)

    def showXmlImport(self, report, source) -> None:
        from .xml_dialog import XmlImportDialog

        dialog = self._editors.get("xmlImport")
        if not isinstance(dialog, XmlImportDialog):
            dialog = XmlImportDialog(self.controller)
            self._editors["xmlImport"] = dialog
        dialog.prepare(report, source)
        self.present(dialog)

    def showXlsxImport(self, report, source) -> None:
        from .xml_dialog import XmlImportDialog

        dialog = self._editors.get("xlsxImport")
        if not isinstance(dialog, XmlImportDialog):
            dialog = XmlImportDialog(self.controller, "XLSX")
            self._editors["xlsxImport"] = dialog
        dialog.prepare(report, source)
        self.present(dialog)

    def showCsvImport(self, report, source) -> None:
        from .xml_dialog import XmlImportDialog

        dialog = self._editors.get("csvImport")
        if not isinstance(dialog, XmlImportDialog):
            dialog = XmlImportDialog(self.controller, "CSV")
            self._editors["csvImport"] = dialog
        dialog.prepare(report, source)
        self.present(dialog)

    @Slot()
    def showMcp(self) -> None:
        from .mcp_dialog import McpDialog
        from .mcp_server import McpServer

        if self._mcp is None:
            self._mcp = McpServer(self.controller)
            self._mcp.changed.connect(self.mcpChanged)
        dialog = self._editors.get("mcp")
        if not isinstance(dialog, McpDialog):
            dialog = McpDialog(self.controller, self._mcp)
            self._editors["mcp"] = dialog
        dialog.error.hide()
        dialog.refresh()
        self.present(dialog)

    @Slot()
    def showFilters(self) -> None:
        from .filter_dialog import FilterDialog

        dialog = self._editors.get("filters")
        if not isinstance(dialog, FilterDialog):
            dialog = FilterDialog(self.controller)
            self._editors["filters"] = dialog
        dialog.prepare()
        self.present(dialog)

    @Slot(dict)
    def showFields(self, shown: dict) -> None:
        from .field_dialogs import FieldsDialog

        dialog = self._editors.get("fields")
        if not isinstance(dialog, FieldsDialog):
            dialog = FieldsDialog(self.controller)
            dialog.visibilityChanged.connect(self.columnVisibilityChanged.emit)
            dialog.editRequested.connect(self.showCustomField)
            dialog.removeRequested.connect(self.confirmCustomFieldDelete)
            self._editors["fields"] = dialog
        dialog.prepare(shown)
        self.present(dialog)

    @Slot(str)
    def showCustomField(self, field_id: str) -> None:
        from .field_dialogs import FieldDefinitionDialog

        if field_id and field_id not in self.controller.project.custom_fields:
            return
        dialog = self._editors.get("fieldDefinition")
        if not isinstance(dialog, FieldDefinitionDialog):
            dialog = FieldDefinitionDialog(self.controller)
            self._editors["fieldDefinition"] = dialog
        dialog.prepare(field_id)
        self.present(dialog)

    @Slot(str, str)
    def showTaskDate(self, task_id: str, field: str) -> None:
        from .date_dialog import TaskDateDialog

        if task_id not in self.controller.project.tasks or field not in {"start", "end", "deadline"}:
            return
        record = self.controller.record(task_id)
        if field != "deadline" and not record["canMove" if field == "start" else "canResizeEnd"]:
            return
        dialog = self._editors.get("taskDate")
        if not isinstance(dialog, TaskDateDialog):
            dialog = TaskDateDialog(self.controller)
            self._editors["taskDate"] = dialog
        dialog.prepare(task_id, field)
        self.present(dialog)

    @Slot(str, str)
    def showFieldValue(self, task_id: str, field_id: str) -> None:
        from .field_dialogs import FieldValueDialog

        task = self.controller.project.tasks.get(task_id)
        definition = self.controller.project.custom_fields.get(field_id)
        if task is None or definition is None or (task.kind == "group" and definition.kind == "number"):
            return
        dialog = self._editors.get("fieldValue")
        if not isinstance(dialog, FieldValueDialog):
            dialog = FieldValueDialog(self.controller)
            self._editors["fieldValue"] = dialog
        dialog.prepare(task_id, field_id)
        self.present(dialog)

    @Slot(str)
    def confirmCustomFieldDelete(self, field_id: str) -> None:
        if field_id not in self.controller.project.custom_fields:
            return
        name = self.controller.project.custom_fields[field_id].name
        box = QMessageBox(QMessageBox.Icon.Question, "Удалить поле?",
                          f"Поле «{name}» и его значения во всех задачах будут удалены. Действие можно отменить.",
                          QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        box.setObjectName("deleteCustomFieldDialog")
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.button(QMessageBox.StandardButton.Cancel).setText("Отмена")
        self._actions[box] = lambda: self.controller.removeCustomField(field_id)
        self.present(box)

    @Slot()
    def showBaselines(self) -> None:
        from .baseline_dialog import BaselineDialog

        dialog = self._editors.get("baselines")
        if not isinstance(dialog, BaselineDialog):
            dialog = BaselineDialog(self.controller)
            self._editors["baselines"] = dialog
        dialog.prepare()
        self.present(dialog)

    @Slot(str)
    def confirmBaselineDelete(self, baseline_id: str) -> None:
        if baseline_id not in self.controller.project.baselines:
            return
        box = QMessageBox(QMessageBox.Icon.Question, "Удалить базовый план?",
                          "Снимок будет удалён. Текущие задачи не изменятся. Действие можно отменить.",
                          QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        box.setObjectName("deleteBaselineDialog")
        box.button(QMessageBox.StandardButton.Ok).setText("Удалить")
        box.button(QMessageBox.StandardButton.Cancel).setText("Отмена")
        self._actions[box] = lambda: self.controller.removeBaseline(baseline_id)
        self.present(box)

    @Slot(str)
    def showResources(self, resource_id: str) -> None:
        dialog = self._editors.get("resources")
        if not isinstance(dialog, ResourceDialog):
            dialog = ResourceDialog(self.controller)
            self._editors["resources"] = dialog
        dialog.prepare(resource_id)
        self.present(dialog)

    @Slot(str)
    def showCalendar(self, resource_id: str) -> None:
        from .calendar_dialog import CalendarDialog

        if resource_id and resource_id not in self.controller.project.resources:
            return
        dialog = self._editors.get("calendar")
        if not isinstance(dialog, CalendarDialog):
            dialog = CalendarDialog(self.controller)
            self._editors["calendar"] = dialog
        dialog.prepare(resource_id)
        self.present(dialog)

    @Slot(str, str, str)
    def showCalendarException(self, resource_id: str, exception_id: str, holiday: str) -> None:
        from .calendar_dialog import CalendarExceptionDialog

        dialog = self._editors.get("calendarException")
        if not isinstance(dialog, CalendarExceptionDialog):
            dialog = CalendarExceptionDialog(self.controller)
            self._editors["calendarException"] = dialog
        if dialog.prepare(resource_id, exception_id, holiday):
            self.present(dialog)

    @Slot(str, str, str)
    def confirmCalendarException(self, resource_id: str, exception_id: str, holiday: str) -> None:
        box = QMessageBox(QMessageBox.Icon.Question, "Удалить исключение?",
                          "Вернётся базовый график. Изменение можно отменить. Для календаря проекта сроки пересчитаются.",
                          QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        box.setObjectName("deleteCalendarExceptionDialog")
        box.button(QMessageBox.StandardButton.Ok).setText("Удалить")
        box.button(QMessageBox.StandardButton.Cancel).setText("Отмена")
        self._actions[box] = lambda: self.controller.removeCalendarException(resource_id, exception_id, holiday)
        self.present(box)

    @Slot(str)
    def showNewResource(self, name: str) -> None:
        dialog = self._editors.get("resources")
        if not isinstance(dialog, ResourceDialog):
            dialog = ResourceDialog(self.controller)
            self._editors["resources"] = dialog
        dialog.prepare("")
        dialog.load_resource("")
        dialog.name.setText(name.strip())
        self.present(dialog)

    @Slot(str)
    @Slot(str, list)
    def showAssignments(self, task_id: str, ids: list[str] | None = None) -> None:
        dialog = self._editors.get("assignments")
        if not isinstance(dialog, AssignmentDialog):
            dialog = AssignmentDialog(self.controller)
            dialog.manageRequested.connect(lambda: self.showResources(""))
            self._editors["assignments"] = dialog
        dialog.prepare(task_id, ids)
        self.present(dialog)

    @Slot(str, str, str, str)
    def showDependency(self, source: str, target: str, kind: str, link_id: str) -> None:
        dialog = self._editors.get("dependency")
        if not isinstance(dialog, DependencyDialog):
            dialog = DependencyDialog(self.controller)
            self._editors["dependency"] = dialog
        dialog.prepare(source, target, kind, link_id)
        self._link_id = link_id
        self.present(dialog)

    @Slot(str, bool)
    def confirmDelete(self, task_id: str, bulk: bool) -> None:
        title = f"Удалить задач: {self.controller.bulkDeleteCount}?" if bulk else "Удалить задачу?"
        text = ("Удалятся только полностью выбранные задачи и группы. Снятые отметки сохраняются."
                if bulk else "Задача, её подзадачи и связанные зависимости будут удалены.")
        box = QMessageBox(QMessageBox.Icon.Question, title, text + " Действие можно отменить.",
                          QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        box.setObjectName("deleteDialog")
        box.button(QMessageBox.StandardButton.Cancel).setText("Отмена")
        self._actions[box] = self.controller.deleteChecked if bulk else lambda: self.controller.deleteTask(task_id)
        self.present(box)

    @Slot()
    def showHelp(self) -> None:
        box = QMessageBox(QMessageBox.Icon.Information, "Работа с диаграммой",
                          "• Перетаскивайте свободную задачу или группу за тело блока.\n"
                          "• Задача с предшественником закреплена: измените связь или лаг.\n"
                          "• Тяните края задачи для изменения начала или завершения.\n"
                          "• Круги по бокам создают связи: перетащите круг на другую задачу.\n"
                          "• Маленький ромб под блоком меняет прогресс.\n"
                          "• Двойной щелчок открывает свойства; название редактируется в таблице.\n"
                          "• Пустую область диаграммы можно перетаскивать.\n"
                          "• Загрузка ресурсов и Люди… находятся в нижней панели.\n"
                          "• Ctrl+колесо — масштаб; Shift+колесо — горизонтальная прокрутка.\n"
                          "• Ctrl+Z / Ctrl+Shift+Z — отмена и повтор; Ctrl+S — сохранить.\n\n"
                          "По умолчанию: Пн–Пт, 09:00–13:00 и 14:00–18:00.\n"
                          "Длительность и трудозатраты — разные величины.",
                          QMessageBox.StandardButton.Close)
        box.setObjectName("helpDialog")
        box.button(QMessageBox.StandardButton.Close).setText("Закрыть")
        self.present(box)

    @Slot()
    def closeAll(self) -> None:
        for dialog in tuple(self._active):
            if isValid(dialog):
                for child in dialog.findChildren(QDialog):
                    child.reject()
                dialog.reject()
            else:
                self._active.discard(dialog)

    @Slot()
    def dispose(self) -> None:
        if self._mcp is not None:
            self._mcp.stop()
        self.closeAll()
        for dialog in self._editors.values():
            if isValid(dialog):
                dialog.deleteLater()
        self._editors.clear()
        self.window = None
