"""Standard widget editors for project-local column definitions and typed values."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDateEdit,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .dialogs import EditorDialog
from .domain import FIELD_TYPES
from .i18n import FIELD_TYPES_EN

if TYPE_CHECKING:
    from .controller import Controller

BUILTIN_FIELDS = {"assignee": "Исполнитель", "effort": "Трудозатраты", "cost": "Стоимость",
                  "start": "Начало", "end": "Завершение", "duration": "Длительность",
                  "progress": "Прогресс", "status": "Статус", "priority": "Приоритет", "deadline": "Крайний срок",
                  "baselineStart": "Базовое начало", "baselineEnd": "Базовое завершение",
                  "startVariance": "Δ начала, кал. ч", "endVariance": "Δ завершения, кал. ч"}

BUILTIN_FIELDS_EN = {"assignee": "Assignee", "effort": "Effort", "cost": "Cost",
                     "start": "Start", "end": "Finish", "duration": "Duration",
                     "progress": "Progress", "status": "Status", "priority": "Priority", "deadline": "Deadline",
                     "baselineStart": "Baseline start", "baselineEnd": "Baseline finish",
                     "startVariance": "Start variance, cal. h", "endVariance": "Finish variance, cal. h"}


def editor_buttons(dialog: EditorDialog, apply, prefix: str) -> QDialogButtonBox:
    is_en = getattr(dialog, "controller", None) is not None and dialog.controller.i18n.language == "en"
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
    save = buttons.button(QDialogButtonBox.StandardButton.Save)
    save.setText("Save" if is_en else "Сохранить")
    save.setObjectName(prefix + "Save")
    save.setDefault(True)
    cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
    cancel.setText("Cancel" if is_en else "Отмена")
    cancel.setObjectName(prefix + "Cancel")
    buttons.accepted.connect(apply)
    buttons.rejected.connect(dialog.reject)
    dialog.layout_root.addWidget(buttons)
    return buttons


class FieldsDialog(EditorDialog):
    visibilityChanged = Signal(str, bool)
    editRequested = Signal(str)
    removeRequested = Signal(str)

    def __init__(self, controller: Controller):
        is_en = controller.i18n.language == "en"
        super().__init__(controller, "fieldsDialog", "Show/Hide Fields" if is_en else "Показать/скрыть поля")
        self.resize(540, 460)
        self.shown: dict[str, bool] = {}
        self.tabs = QTabWidget()
        self.standard = QListWidget()
        self.standard.setObjectName("standardFields")
        self.custom = QListWidget()
        self.custom.setObjectName("customFields")
        self.tabs.addTab(self.standard, "Standard" if is_en else "Стандартные")
        self.tabs.addTab(self.custom, "Custom" if is_en else "Пользовательские")
        self.tabs.setObjectName("fieldTabs")
        self.layout_root.addWidget(self.tabs)
        actions = QHBoxLayout()
        new = QPushButton("Create field…" if is_en else "Создать поле…")
        new.setObjectName("newCustomField")
        new.clicked.connect(lambda: self.editRequested.emit(""))
        self.rename = QPushButton("Edit…" if is_en else "Изменить…")
        self.rename.setObjectName("editCustomField")
        self.rename.clicked.connect(lambda: self.editRequested.emit(self.selected_id()))
        self.remove = QPushButton("Delete…" if is_en else "Удалить…")
        self.remove.setObjectName("removeCustomField")
        self.remove.clicked.connect(lambda: self.removeRequested.emit(self.selected_id()))
        for button in (new, self.rename, self.remove):
            button.setAutoDefault(False)
            actions.addWidget(button)
        self.layout_root.addLayout(actions)
        note = QLabel(
            "Hiding does not delete values. Custom fields and values are saved in the project."
            if is_en
            else "Скрытие не удаляет значения. Пользовательские поля и значения сохраняются в проекте."
        )
        note.setWordWrap(True)
        self.layout_root.addWidget(note)
        self.layout_root.addWidget(self.error)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.button(QDialogButtonBox.StandardButton.Close).setObjectName("closeFields")
        close.button(QDialogButtonBox.StandardButton.Close).setText("Close" if is_en else "Закрыть")
        close.rejected.connect(self.reject)
        self.layout_root.addWidget(close)
        self.standard.itemChanged.connect(self.changed_item)
        self.custom.itemChanged.connect(self.changed_item)
        self.custom.currentItemChanged.connect(self.update_actions)
        self.tabs.currentChanged.connect(self.update_actions)
        controller.viewChanged.connect(self.refresh)

    def selected_id(self) -> str:
        selected = self.custom.currentItem()
        return selected.data(Qt.ItemDataRole.UserRole)[7:] if selected is not None else ""

    def update_actions(self, *_args) -> None:
        selected = self.tabs.currentIndex() == 1 and bool(self.selected_id())
        self.rename.setEnabled(selected)
        self.remove.setEnabled(selected)

    def prepare(self, shown: dict) -> None:
        self.error.hide()
        self.shown = dict(shown)
        self.refresh()

    def refresh(self) -> None:
        selected = self.selected_id()
        is_en = self.controller.i18n.language == "en"
        types = FIELD_TYPES_EN if is_en else FIELD_TYPES
        builtin = BUILTIN_FIELDS_EN if is_en else BUILTIN_FIELDS
        definitions = self.controller.project.custom_fields.values()
        custom = {"custom:" + f.id: f.name + " · " + types[f.kind] for f in definitions}
        for widget, fields in ((self.standard, builtin), (self.custom, custom)):
            widget.blockSignals(True)
            widget.clear()
            for key, label in fields.items():
                item = QListWidgetItem(label, widget)
                item.setData(Qt.ItemDataRole.UserRole, key)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if self.shown.get(key, True) else Qt.CheckState.Unchecked)
                if key == "custom:" + selected:
                    widget.setCurrentItem(item)
            widget.blockSignals(False)
        if self.custom.currentItem() is None and self.custom.count():
            self.custom.setCurrentRow(0)
        self.update_actions()

    def changed_item(self, item: QListWidgetItem) -> None:
        key = item.data(Qt.ItemDataRole.UserRole)
        shown = item.checkState() == Qt.CheckState.Checked
        self.shown[key] = shown
        self.visibilityChanged.emit(key, shown)


class FieldDefinitionDialog(EditorDialog):
    def __init__(self, controller: Controller):
        is_en = controller.i18n.language == "en"
        super().__init__(controller, "fieldDefinitionDialog", "Custom Field" if is_en else "Пользовательское поле")
        self.field_id = ""
        self.resize(480, 380)
        self.form = QFormLayout()
        self.name = QLineEdit()
        self.name.setObjectName("customFieldName")
        self.kind = QComboBox()
        self.kind.setObjectName("customFieldType")
        for key, label in (FIELD_TYPES_EN if is_en else FIELD_TYPES).items():
            self.kind.addItem(label, key)
        self.options = QPlainTextEdit()
        self.options.setObjectName("customFieldOptions")
        self.options.setPlaceholderText("One option per line" if is_en else "Одна опция на строку")
        self.aggregate = QComboBox()
        self.aggregate.setObjectName("customFieldAggregate")
        self.aggregate.addItem("Sum" if is_en else "Сумма", "sum")
        self.aggregate.addItem("Average" if is_en else "Среднее", "average")
        self.form.addRow("Name" if is_en else "Название", self.name)
        self.form.addRow("Type" if is_en else "Тип", self.kind)
        self.form.addRow("Options" if is_en else "Опции", self.options)
        self.form.addRow("Aggregation" if is_en else "Агрегирование", self.aggregate)
        self.layout_root.addLayout(self.form)
        note = QLabel(
            "Type cannot be changed after creation. Options in use cannot be removed. "
            "People are project resources; labels are entered separately for each task."
            if is_en
            else "Тип после создания не меняется. Для списка нельзя удалить используемую опцию. "
            "Люди — ресурсы проекта; лейблы вводятся отдельно для каждой задачи."
        )
        note.setWordWrap(True)
        self.layout_root.addWidget(note)
        self.layout_root.addWidget(self.error)
        editor_buttons(self, self.apply, "customField")
        self.kind.currentIndexChanged.connect(self.update_type)

    def prepare(self, field_id: str) -> None:
        self.field_id = field_id
        definition = self.controller.project.custom_fields.get(field_id)
        self.error.hide()
        self.name.setText(definition.name if definition else "")
        self.kind.setEnabled(definition is None)
        self.kind.setCurrentIndex(self.kind.findData(definition.kind if definition else "text"))
        self.options.setPlainText("\n".join(definition.options) if definition else "")
        self.aggregate.setCurrentIndex(max(0, self.aggregate.findData(definition.aggregate if definition else "sum")))
        self.update_type()

    def update_type(self, *_args) -> None:
        self.form.setRowVisible(self.options, self.kind.currentData() in {"select", "multi"})
        self.form.setRowVisible(self.aggregate, self.kind.currentData() == "number")

    def apply(self) -> None:
        kind = self.kind.currentData()
        options = self.options.toPlainText().splitlines() if kind in {"select", "multi"} else []
        key = self.controller.saveCustomField(self.field_id, self.name.text(), kind, options, self.aggregate.currentData())
        if key:
            self.accept()


class FieldValueDialog(EditorDialog):
    def __init__(self, controller: Controller):
        is_en = controller.i18n.language == "en"
        super().__init__(controller, "fieldValueDialog", "Field Value" if is_en else "Значение поля")
        self.task_id = self.field_id = self.kind = ""
        self.resize(440, 330)
        self.unset = QCheckBox("Not set" if is_en else "Не задано")
        self.unset.setObjectName("customValueUnset")
        self.layout_root.addWidget(self.unset)
        self.stack = QStackedWidget()
        self.layout_root.addWidget(self.stack)
        self.text = QPlainTextEdit()
        self.text.setObjectName("customTextValue")
        self.number = QLineEdit()
        self.number.setObjectName("customNumberValue")
        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDateRange(QDate(1, 1, 1), QDate(9999, 12, 31))
        self.date.setDisplayFormat("dd.MM.yyyy")
        self.date.setObjectName("customDateValue")
        self.choice = QComboBox()
        self.choice.setObjectName("customChoiceValue")
        self.many = QListWidget()
        self.many.setObjectName("customManyValues")
        self.checkbox = QCheckBox("Yes" if is_en else "Да")
        self.checkbox.setObjectName("customCheckboxValue")
        self.color = QLineEdit()
        self.color.setObjectName("customColorValue")
        color_root = QWidget()
        color_layout = QHBoxLayout(color_root)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.addWidget(self.color)
        choose = QPushButton("Choose color…" if is_en else "Выбрать цвет…")
        choose.setObjectName("chooseCustomColor")
        choose.clicked.connect(self.choose_color)
        color_layout.addWidget(choose)
        self.widgets = {"text": self.text, "labels": self.text, "number": self.number, "date": self.date,
                        "select": self.choice, "multi": self.many, "people": self.many,
                        "checkbox": self.checkbox, "color": color_root}
        self.pages: dict[QWidget, QWidget] = {}
        for widget in dict.fromkeys(self.widgets.values()):
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(widget)
            if widget not in (self.text, self.many):
                layout.addStretch()
            self.pages[widget] = page
            self.stack.addWidget(page)
        self.unset.toggled.connect(lambda checked: self.stack.setEnabled(not checked))
        self.layout_root.addWidget(self.error)
        editor_buttons(self, self.apply, "customValue")

    def prepare(self, task_id: str, field_id: str) -> None:
        self.task_id, self.field_id = task_id, field_id
        is_en = self.controller.i18n.language == "en"
        definition = self.controller.project.custom_fields[field_id]
        self.kind = definition.kind
        value = self.controller.project.tasks[task_id].custom_values.get(field_id)
        self.setWindowTitle(definition.name + " — " + self.controller.project.tasks[task_id].name)
        self.error.hide()
        self.unset.setChecked(value is None)
        self.stack.setEnabled(value is not None)
        self.stack.setCurrentWidget(self.pages[self.widgets[self.kind]])
        if is_en:
            self.text.setPlaceholderText("One label per line" if self.kind == "labels" else "Text")
        else:
            self.text.setPlaceholderText("Один лейбл на строку" if self.kind == "labels" else "Текст")
        self.text.setPlainText("\n".join(value or []) if self.kind == "labels" else str(value or ""))
        self.number.setText(str(value) if value is not None else "")
        self.date.setDate(QDate.fromString(str(value), Qt.DateFormat.ISODate) if self.kind == "date" and value else QDate.currentDate())
        self.checkbox.setChecked(value is True)
        self.color.setText(str(value) if self.kind == "color" and value else "#50c7d6")
        self.choice.clear()
        self.choice.addItems(definition.options)
        self.choice.setCurrentIndex(max(0, self.choice.findText(str(value))))
        self.many.clear()
        choices = ({r.id: r.name for r in self.controller.project.resources.values()} if self.kind == "people"
                   else {s: s for s in definition.options})
        for key, label in choices.items():
            item = QListWidgetItem(label, self.many)
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if isinstance(value, list) and key in value else Qt.CheckState.Unchecked)

    def choose_color(self) -> None:
        is_en = self.controller.i18n.language == "en"
        color = QColorDialog.getColor(QColor(self.color.text()), self, "Value Color" if is_en else "Цвет значения")
        if color.isValid():
            self.color.setText(color.name())

    def apply(self) -> None:
        is_en = self.controller.i18n.language == "en"
        value: object = None
        if not self.unset.isChecked():
            if self.kind in {"text", "labels"}:
                text = self.text.toPlainText()
                value = [s.strip() for s in text.splitlines() if s.strip()] if self.kind == "labels" else text
            elif self.kind == "number":
                try:
                    value = float(self.number.text().replace(",", ".")) if self.number.text().strip() else None
                except ValueError:
                    self.report_error("Enter a number, e.g. 8 or 2.5." if is_en else "Введите число, например 8 или 2,5.")
                    return
            elif self.kind == "date":
                value = self.date.date().toString(Qt.DateFormat.ISODate)
            elif self.kind == "checkbox":
                value = self.checkbox.isChecked()
            elif self.kind == "select":
                value = self.choice.currentText()
            elif self.kind in {"multi", "people"}:
                value = [self.many.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.many.count())
                         if self.many.item(i).checkState() == Qt.CheckState.Checked]
            elif self.kind == "color":
                value = self.color.text()
        if self.controller.setCustomValue(self.task_id, self.field_id, value):
            self.accept()
