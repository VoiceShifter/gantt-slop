"""Native calendar exception lists and atomic range editors."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QDate, Qt, QTime
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTimeEdit,
    QTreeWidget,
    QTreeWidgetItem,
)

from .dialogs import EditorDialog
from .field_dialogs import editor_buttons

if TYPE_CHECKING:
    from .controller import Controller


def day_text(day) -> str:
    return f"{day.day:02}.{day.month:02}.{day.year:04}"


def minute_text(value: int) -> str:
    return f"{value // 60:02}:{value % 60:02}"


class CalendarDialog(EditorDialog):
    def __init__(self, controller: Controller):
        is_en = controller.i18n.language == "en"
        super().__init__(controller, "calendarDialog", "Calendar Exceptions" if is_en else "Исключения календаря")
        self.resource_id = ""
        self.resize(720, 440)
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.layout_root.addWidget(self.description)
        self.table = QTreeWidget()
        self.table.setObjectName("calendarExceptions")
        self.table.setHeaderLabels(
            ["Name", "Start", "Finish", "Availability / intervals"]
            if is_en
            else ["Название", "Начало", "Завершение", "Доступность / интервалы"]
        )
        self.table.setRootIsDecorated(False)
        self.table.setColumnWidth(0, 180)
        self.table.setColumnWidth(1, 110)
        self.table.setColumnWidth(2, 110)
        self.table.currentItemChanged.connect(self.update_actions)
        self.table.itemDoubleClicked.connect(lambda *_args: self.edit())
        self.layout_root.addWidget(self.table)
        actions = QHBoxLayout()
        for name, label, callback in (
            ("newCalendarException", "Add…" if is_en else "Добавить…", lambda: self.edit(True)),
            ("editCalendarException", "Edit…" if is_en else "Изменить…", self.edit),
            ("removeCalendarException", "Delete…" if is_en else "Удалить…", self.remove),
        ):
            button = QPushButton(label)
            button.setObjectName(name)
            button.setAutoDefault(False)
            button.clicked.connect(callback)
            actions.addWidget(button)
            if name == "editCalendarException":
                self.edit_button = button
            elif name == "removeCalendarException":
                self.remove_button = button
        actions.addStretch()
        self.layout_root.addLayout(actions)
        self.layout_root.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setObjectName("closeCalendar")
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Close" if is_en else "Закрыть")
        buttons.rejected.connect(self.reject)
        self.layout_root.addWidget(buttons)
        controller.viewChanged.connect(self.refresh)

    def prepare(self, resource_id: str) -> None:
        self.resource_id = resource_id
        self.error.hide()
        self.refresh()

    def selected(self) -> tuple[str, str] | None:
        item = self.table.currentItem()
        return tuple(item.data(0, Qt.ItemDataRole.UserRole)) if item is not None else None

    def update_actions(self, *_args) -> None:
        selected = self.selected() is not None
        self.edit_button.setEnabled(selected)
        self.remove_button.setEnabled(selected)

    def refresh(self) -> None:
        project = self.controller.project
        if self.resource_id and self.resource_id not in project.resources:
            self.reject()
            return
        is_en = self.controller.i18n.language == "en"
        resource = project.resources.get(self.resource_id)
        title = resource.name if resource else ("Project calendar" if is_en else "Календарь проекта")
        self.setWindowTitle(("Exceptions — " if is_en else "Исключения — ") + title)
        if resource:
            self.description.setText(
                "Availability on specified dates overrides weekly norm. 0 hours — vacation/non-working days. Tasks are not shifted."
                if is_en
                else "Доступность на указанные даты заменяет недельную норму. 0 часов — отпуск/нерабочие дни. Задачи не переносятся."
            )
        else:
            self.description.setText(
                "Exceptions override weekly schedule and standard holidays. Saving recalculates schedule in a single Undo step."
                if is_en
                else "Исключения заменяют недельный график и старые праздники. Сохранение пересчитывает расписание одной операцией Undo."
            )
        selected = self.selected()
        entries = []
        for exception in (resource.exceptions if resource else project.calendar.exceptions):
            if resource:
                detail = f"{exception.capacity:g} h/day" if is_en else f"{exception.capacity:g} ч/день"
            else:
                default_nonworking = "Non-working days" if is_en else "Нерабочие дни"
                detail = "; ".join(minute_text(a) + "–" + minute_text(b) for a, b in exception.periods) or default_nonworking
            entries.append((exception.start, exception.end, exception.name, detail, (exception.id, "")))
        if not resource:
            for day in project.calendar.holidays:
                overridden = any(item.start <= day <= item.end for item in project.calendar.exceptions)
                holiday_name = "Holiday" if is_en else "Праздник"
                if is_en:
                    holiday_detail = "Overridden by exception" if overridden else "Non-working day"
                else:
                    holiday_detail = "Переопределён исключением" if overridden else "Нерабочий день"
                entries.append((day, day, holiday_name, holiday_detail, ("", day.isoformat())))
        self.table.blockSignals(True)
        self.table.clear()
        for start, end, name, detail, key in sorted(entries, key=lambda entry: (entry[0], entry[1], entry[4])):
            item = QTreeWidgetItem([name, day_text(start), day_text(end), detail])
            item.setData(0, Qt.ItemDataRole.UserRole, key)
            self.table.addTopLevelItem(item)
            if key == selected:
                self.table.setCurrentItem(item)
        if self.table.currentItem() is None and self.table.topLevelItemCount():
            first = self.table.topLevelItem(0)
            assert first is not None
            self.table.setCurrentItem(first)
        self.table.blockSignals(False)
        self.update_actions()

    def edit(self, new: bool = False) -> None:
        selected = ("", "") if new else self.selected()
        if selected is not None:
            self.controller.dialogs.showCalendarException(self.resource_id, *selected)

    def remove(self) -> None:
        selected = self.selected()
        if selected is not None:
            self.controller.dialogs.confirmCalendarException(self.resource_id, *selected)


class CalendarExceptionDialog(EditorDialog):
    def __init__(self, controller: Controller):
        is_en = controller.i18n.language == "en"
        super().__init__(controller, "calendarExceptionDialog", "Calendar Exception" if is_en else "Исключение календаря")
        self.resource_id = self.exception_id = self.holiday = ""
        self.capacity_hours = 0.0
        self.form = QFormLayout()
        self.form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.name = QLineEdit()
        self.name.setObjectName("exceptionName")
        self.name.setPlaceholderText("Holiday, vacation, short day…" if is_en else "Праздник, отпуск, сокращённый день…")
        self.form.addRow("Name" if is_en else "Название", self.name)
        self.start = QDateEdit()
        self.end = QDateEdit()
        for name, widget in (("exceptionStart", self.start), ("exceptionEnd", self.end)):
            widget.setObjectName(name)
            widget.setCalendarPopup(True)
            widget.setDateRange(QDate(1, 1, 1), QDate(9999, 12, 31))
            widget.setDisplayFormat("dd.MM.yyyy")
        self.form.addRow("From date (inclusive)" if is_en else "С даты (включительно)", self.start)
        self.form.addRow("To date (inclusive)" if is_en else "По дату (включительно)", self.end)
        self.mode = QComboBox()
        self.mode.setObjectName("exceptionMode")
        self.mode.addItems(["Non-working days", "Working intervals"] if is_en else ["Нерабочие дни", "Рабочие интервалы"])
        self.form.addRow("Type" if is_en else "Тип", self.mode)
        self.capacity = QDoubleSpinBox()
        self.capacity.setObjectName("exceptionCapacity")
        self.capacity.setRange(0, 24)
        self.capacity.setDecimals(2)
        self.capacity.setSuffix(" h/day" if is_en else " ч/день")
        self.capacity.valueChanged.connect(self.capacity_changed)
        self.form.addRow("Availability" if is_en else "Доступность", self.capacity)
        self.layout_root.addLayout(self.form)
        self.period_group = QGroupBox("Working intervals within day" if is_en else "Рабочие интервалы в пределах дня")
        periods = QFormLayout(self.period_group)
        self.times: list[tuple[QTimeEdit, QTimeEdit]] = []
        self.second = QCheckBox("Second interval" if is_en else "Второй интервал")
        self.second.setObjectName("exceptionSecondPeriod")
        for number in (1, 2):
            row = QHBoxLayout()
            a, b = QTimeEdit(), QTimeEdit()
            for suffix, widget in (("Start", a), ("End", b)):
                widget.setDisplayFormat("HH:mm")
                widget.setObjectName(f"exception{suffix}Time{number}")
                row.addWidget(widget)
            periods.addRow(("First interval" if is_en else "Первый интервал") if number == 1 else self.second, row)
            self.times.append((a, b))
        self.mode.currentIndexChanged.connect(self.update_periods)
        self.second.toggled.connect(self.update_periods)
        self.layout_root.addWidget(self.period_group)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.layout_root.addWidget(self.note)
        self.layout_root.addWidget(self.error)
        editor_buttons(self, self.apply, "calendarException")

    def update_periods(self, *_args) -> None:
        self.period_group.setEnabled(self.mode.currentIndex() == 1)
        for widget in self.times[1]:
            widget.setEnabled(self.second.isChecked())

    def capacity_changed(self, value: float) -> None:
        self.capacity_hours = value

    def prepare(self, resource_id: str, exception_id: str, holiday: str) -> bool:
        project = self.controller.project
        resource = project.resources.get(resource_id)
        if resource_id and resource is None:
            return False
        items = resource.exceptions if resource else project.calendar.exceptions
        exception = next((item for item in items if item.id == exception_id), None)
        old_holiday = next((day for day in project.calendar.holidays if day.isoformat() == holiday), None)
        if exception_id and exception is None or holiday and (resource or exception_id or old_holiday is None):
            return False
        self.resource_id, self.exception_id, self.holiday = resource_id, exception_id, holiday
        self.error.hide()
        is_en = self.controller.i18n.language == "en"
        title = resource.name if resource else ("Project calendar" if is_en else "Календарь проекта")
        self.setWindowTitle(("Exception — " if is_en else "Исключение — ") + title)
        default = QDate.currentDate()
        for widget, value in ((self.start, exception.start if exception else old_holiday), (self.end, exception.end if exception else old_holiday)):
            widget.setDate(QDate(value.year, value.month, value.day) if value is not None else default)
        default_holiday = "Holiday" if is_en else "Праздник"
        self.name.setText(exception.name if exception else default_holiday if holiday else "")
        self.form.setRowVisible(self.mode, resource is None)
        self.form.setRowVisible(self.capacity, resource is not None)
        self.period_group.setVisible(resource is None)
        self.capacity_hours = exception.capacity if resource and exception is not None else 0
        self.capacity.blockSignals(True)
        self.capacity.setValue(self.capacity_hours)
        self.capacity.blockSignals(False)
        values = exception.periods if exception is not None and not resource else []
        self.mode.setCurrentIndex(1 if values else 0)
        self.second.setChecked(len(values) == 2 if values else True)
        for (a, b), (start, end) in zip(self.times, values + [[540, 780], [840, 1080]][len(values):], strict=True):
            a.setTime(QTime(start // 60, start % 60))
            b.setTime(QTime(end // 60, end % 60))
        self.update_periods()
        if resource:
            self.note.setText(
                "Availability is set for each day of the range, including weekends. Tasks and planned effort do not change."
                if is_en
                else "Доступность задаётся на каждый день диапазона, включая выходные. Задачи и плановые трудозатраты не меняются."
            )
        else:
            self.note.setText(
                "Range includes both dates. Up to two intervals, no crossing midnight. Applying recalculates dates while preserving task working duration."
                if is_en
                else "Диапазон включает обе даты. Не более двух интервалов, без перехода через полночь. Применение пересчитывает сроки, сохраняя рабочую длительность задач."
            )
        return True

    def apply(self) -> None:
        periods = []
        if not self.resource_id and self.mode.currentIndex() == 1:
            for a, b in self.times[:2 if self.second.isChecked() else 1]:
                periods.append([a.time().hour()*60+a.time().minute(), b.time().hour()*60+b.time().minute()])
        if self.controller.saveCalendarException(self.resource_id, self.exception_id, self.name.text(),
                                                 self.start.date().toString(Qt.DateFormat.ISODate),
                                                 self.end.date().toString(Qt.DateFormat.ISODate),
                                                 periods, str(self.capacity_hours), self.holiday):
            self.accept()
