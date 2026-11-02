"""Native, transactional calendar picker for scheduled task dates."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QCalendarWidget, QCheckBox, QDialogButtonBox, QLabel

from .dialogs import EditorDialog

if TYPE_CHECKING:
    from .controller import Controller


class TaskDateDialog(EditorDialog):
    def __init__(self, controller: Controller):
        is_en = controller.i18n.language == "en"
        super().__init__(controller, "taskDateDialog", "Task Date" if is_en else "Дата задачи")
        self.task_id = self.field = ""
        self.calendar = QCalendarWidget()
        self.calendar.setObjectName("taskDateCalendar")
        self.calendar.setDateRange(QDate(1, 1, 1), QDate(9999, 12, 31))
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.layout_root.addWidget(self.calendar)
        self.unset = QCheckBox("Remove deadline" if is_en else "Убрать крайний срок")
        self.unset.setObjectName("taskDeadlineUnset")
        self.unset.toggled.connect(self.calendar.setDisabled)
        self.layout_root.addWidget(self.unset)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.layout_root.addWidget(self.hint)
        self.layout_root.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        save.setText("Apply" if is_en else "Применить")
        save.setObjectName("taskDateSave")
        save.setDefault(True)
        cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel.setText("Cancel" if is_en else "Отмена")
        cancel.setObjectName("taskDateCancel")
        buttons.accepted.connect(self.apply)
        buttons.rejected.connect(self.reject)
        self.layout_root.addWidget(buttons)

    def prepare(self, task_id: str, field: str) -> None:
        self.task_id, self.field = task_id, field
        is_en = self.controller.i18n.language == "en"
        task = self.controller.project.tasks[task_id]
        start, end = self.controller.project.span(task_id)
        current = start if field == "start" else end
        if field == "deadline":
            current = task.deadline or end.date()
        self.unset.setChecked(False)
        self.unset.setVisible(field == "deadline")
        self.calendar.setEnabled(True)
        self.calendar.setSelectedDate(QDate(current.year, current.month, current.day))
        self.calendar.showSelectedDate()
        if is_en:
            self.hint.setText(
                "Deadline is inclusive until the end of the selected day. Schedule will not change."
                if field == "deadline"
                else "Time will be preserved. Non-working date will be aligned to the project calendar."
            )
            title = {"start": "Start", "end": "Finish", "deadline": "Deadline"}[field]
        else:
            self.hint.setText(
                "Срок включителен до конца выбранного дня. Расписание не изменится."
                if field == "deadline"
                else "Время сохранится. Нерабочая дата будет приведена к рабочему календарю проекта."
            )
            title = {"start": "Начало", "end": "Завершение", "deadline": "Крайний срок"}[field]
        self.setWindowTitle(title + " — " + self.controller.project.tasks[task_id].name)
        self.error.hide()

    def apply(self) -> None:
        value = "" if self.field == "deadline" and self.unset.isChecked() else self.calendar.selectedDate().toString(Qt.DateFormat.ISODate)
        if self.controller.editField(self.task_id, self.field, value):
            self.accept()
