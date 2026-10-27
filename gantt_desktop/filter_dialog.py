"""Native, transactional task filters and project-local named presets."""
from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .dialogs import EditorDialog
from .domain import PRIORITY_LABELS, STATUS_LABELS, ScheduleError, TaskFilter


class FilterDialog(EditorDialog):
    def __init__(self, controller):
        super().__init__(controller, "filterDialog", "Фильтры задач")
        self.resize(820, 740)
        self.saved: dict[str, TaskFilter] = {}
        note = QLabel("Между полями — И; внутри списка — ИЛИ. Пустой список означает все значения. "
                      "Группы остаются как контекст, их итоги относятся ко всем подзадачам. "
                      "Изменения вида и наборов вступят в силу только после «Применить».")
        note.setWordWrap(True)
        self.layout_root.addWidget(note)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        layout = QVBoxLayout(body)
        self.presets = QComboBox()
        self.presets.setObjectName("filterPresets")
        self.presets.activated.connect(self.load_preset)
        layout.addWidget(self.presets)
        names = QHBoxLayout()
        self.name = QLineEdit()
        self.name.setObjectName("filterPresetName")
        self.name.setPlaceholderText("Название нового набора · сохраняется в .gantt.json")
        names.addWidget(self.name, 1)
        for title, key, action in (("Добавить набор", "filterAddPreset", self.add_preset),
                                   ("Удалить набор", "filterDeletePreset", self.delete_preset)):
            button = QPushButton(title)
            button.setObjectName(key)
            button.setAutoDefault(False)
            button.clicked.connect(action)
            names.addWidget(button)
        layout.addLayout(names)
        form = QFormLayout()
        self.query = QLineEdit()
        self.query.setObjectName("filterQuery")
        form.addRow("Поиск в имени, исполнителе и описании", self.query)
        self.quick = QComboBox()
        self.quick.setObjectName("filterQuick")
        for key, label in (("all", "Все задачи"), ("incomplete", "Незавершённые"),
                           ("complete", "Завершённые"), ("overdue", "Просроченные")):
            self.quick.addItem(label, key)
        form.addRow("Быстрый фильтр", self.quick)
        layout.addLayout(form)
        grid = QGridLayout()
        self.choices: dict[str, QListWidget] = {}
        for i, (key, title) in enumerate((("kinds", "Тип"), ("resources", "Исполнитель"),
                                         ("statuses", "Статус"), ("priorities", "Приоритет"), ("colors", "Цвет"))):
            group = QGroupBox(title)
            box = QVBoxLayout(group)
            choices = QListWidget()
            choices.setObjectName("filter-" + key)
            choices.setMinimumHeight(100)
            choices.setMaximumHeight(120)
            box.addWidget(choices)
            self.choices[key] = choices
            grid.addWidget(group, i // 3, i % 3)
        layout.addLayout(grid)
        dates = QGroupBox("Даты · включительно; диапазон — пересечение с задачей")
        date_grid = QGridLayout(dates)
        self.bounds: dict[str, list[tuple[QCheckBox, QDateEdit]]] = {}
        for row, (key, label) in enumerate((("span", "Диапазон"), ("start", "Начало"), ("end", "Завершение"))):
            date_grid.addWidget(QLabel(label), row, 0)
            self.bounds[key] = []
            for col, title in enumerate(("С", "По")):
                enabled = QCheckBox(title)
                enabled.setObjectName(f"filter-{key}-{col}-enabled")
                value = QDateEdit()
                value.setObjectName(f"filter-{key}-{col}")
                value.setCalendarPopup(True)
                value.setDisplayFormat("dd.MM.yyyy")
                value.setDateRange(QDate(1, 1, 1), QDate(9999, 12, 31))
                enabled.toggled.connect(value.setEnabled)
                date_grid.addWidget(enabled, row, 1 + col * 2)
                date_grid.addWidget(value, row, 2 + col * 2)
                self.bounds[key].append((enabled, value))
        layout.addWidget(dates)
        scroll.setWidget(body)
        self.layout_root.addWidget(scroll, 1)
        self.layout_root.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel)
        apply = buttons.button(QDialogButtonBox.StandardButton.Apply)
        apply.setObjectName("filterApply")
        apply.setText("Применить")
        apply.clicked.connect(self.apply)
        cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel.setObjectName("filterCancel")
        cancel.setText("Отмена")
        cancel.clicked.connect(self.reject)
        clear = buttons.addButton("Очистить условия", QDialogButtonBox.ButtonRole.ResetRole)
        clear.setObjectName("filterClear")
        clear.clicked.connect(lambda: self.populate(TaskFilter()))
        self.layout_root.addWidget(buttons)

    def prepare(self) -> None:
        self.saved = deepcopy(self.controller.project.saved_filters)
        self.refresh_presets()
        self.name.clear()
        self.populate(self.controller.filter_state())

    def refresh_presets(self, selected: str = "") -> None:
        self.presets.clear()
        self.presets.addItem("Выбрать сохранённый набор…", "")
        for name in self.saved:
            self.presets.addItem(name, name)
        self.presets.setCurrentIndex(max(0, self.presets.findData(selected)))

    def populate(self, criteria: TaskFilter) -> None:
        self.error.hide()
        self.query.setText(criteria.query)
        self.quick.setCurrentIndex(self.quick.findData(criteria.quick))
        project = self.controller.project
        resources = {"": "Не назначен", **{key: value.name for key, value in project.resources.items()}}
        for key in criteria.resources:
            resources.setdefault(key, f"Удалённый ресурс · {key}")
        colors = sorted({t.color.casefold() for t in project.tasks.values()} | {c.casefold() for c in criteria.colors})
        options = {"kinds": {"task": "Задача", "milestone": "Веха"}, "resources": resources,
                   "statuses": STATUS_LABELS, "priorities": PRIORITY_LABELS, "colors": {c: c for c in colors}}
        for key, choices in self.choices.items():
            choices.clear()
            selected = list(getattr(criteria, key))
            if key == "resources" and criteria.unassigned:
                selected.append("")
            if key == "colors":
                selected = [c.casefold() for c in selected]
            for value, label in options[key].items():
                item = QListWidgetItem(label, choices)
                item.setData(Qt.ItemDataRole.UserRole, value)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if value in selected else Qt.CheckState.Unchecked)
                if key == "colors":
                    swatch = QPixmap(16, 16)
                    swatch.fill(QColor(value))
                    item.setIcon(QIcon(swatch))
        for key, controls in self.bounds.items():
            for (enabled, value), bound in zip(controls, criteria.ranges.get(key, ["", ""]), strict=True):
                enabled.setChecked(bool(bound))
                value.setEnabled(bool(bound))
                value.setDate(QDate.fromString(bound, Qt.DateFormat.ISODate) if bound else QDate.currentDate())

    def criteria(self) -> TaskFilter:
        values = {key: [choices.item(i).data(Qt.ItemDataRole.UserRole) for i in range(choices.count())
                        if choices.item(i).checkState() == Qt.CheckState.Checked] for key, choices in self.choices.items()}
        ranges = {key: [value.date().toString(Qt.DateFormat.ISODate) if enabled.isChecked() else ""
                        for enabled, value in controls] for key, controls in self.bounds.items()}
        result = TaskFilter(query=self.query.text().strip(), quick=self.quick.currentData(),
                            kinds=values["kinds"], resources=[key for key in values["resources"] if key],
                            unassigned="" in values["resources"], statuses=values["statuses"],
                            priorities=values["priorities"], colors=values["colors"],
                            ranges={key: bounds for key, bounds in ranges.items() if any(bounds)})
        result.validate()
        return result

    def load_preset(self) -> None:
        name = self.presets.currentData()
        if name in self.saved:
            self.populate(self.saved[name])

    def add_preset(self) -> None:
        try:
            name = self.name.text().strip()
            if not name or name.casefold() in {key.casefold() for key in self.saved}:
                raise ScheduleError("Укажите уникальное название фильтра.")
            self.saved[name] = self.criteria()
            self.refresh_presets(name)
            self.name.clear()
            self.error.hide()
        except ValueError as error:
            self.report_error(str(error))

    def delete_preset(self) -> None:
        name = self.presets.currentData()
        if name in self.saved:
            del self.saved[name]
            self.refresh_presets()

    def apply(self) -> None:
        try:
            criteria = self.criteria()
        except ValueError as error:
            self.report_error(str(error))
            return
        if self.controller.apply_filter(criteria, self.saved):
            self.accept()
