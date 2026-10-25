from datetime import datetime, timedelta

import pytest
from conftest import wait_until
from dialog_helpers import click_native, native_dialog, required_widget
from PySide6.QtCore import QDate, QMetaObject, QObject, Qt
from PySide6.QtGui import QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractItemView, QCalendarWidget, QLabel
from test_ui import item, point

from gantt_desktop.controller import Controller
from gantt_desktop.domain import Project, Task
from gantt_desktop.sample import sample_project


def calendar():
    widget = required_widget("taskDateCalendar")
    assert isinstance(widget, QCalendarWidget)
    return widget


@pytest.mark.parametrize("field", ["start", "end"])
def test_calendar_initial_date_cancel_and_unchanged_apply_are_noops(gui, field):
    c, window = gui
    before = c.project.to_dict()
    expected = c.project.span("sensor")[field == "end"].date()
    c.dialogs.showTaskDate("sensor", field)
    dialog = native_dialog("taskDateDialog")
    assert dialog.windowHandle().transientParent() is window
    assert calendar().selectedDate().toPython() == expected
    assert calendar().minimumDate() == QDate(1, 1, 1)
    assert calendar().maximumDate() == QDate(9999, 12, 31)
    calendar().setSelectedDate(calendar().selectedDate().addDays(7))
    assert click_native("taskDateCancel")
    assert c.project.to_dict() == before and not c.canUndo
    c.dialogs.showTaskDate("sensor", field)
    assert click_native("taskDateSave")
    assert c.project.to_dict() == before and not c.canUndo and not c.dirty


@pytest.mark.parametrize("field", ["start", "end"])
@pytest.mark.parametrize("width", [1000, 1920])
def test_inspector_calendar_button_real_key_selection_and_single_undo(gui, field, width):
    c, window = gui
    window.resize(width, 960)
    c.select("sensor")
    inspector = window.findChild(QObject, "taskInspector")
    assert inspector is not None
    assert QMetaObject.invokeMethod(inspector, "open")
    wait_until(lambda: inspector.property("opened"))
    button = item(window, "calendar-inspector" + field.title())
    assert button.isEnabled() and button.isVisible()
    before = c.project.to_dict()
    start, end = c.project.span("sensor")
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(button))
    wait_until(lambda: bool(c.dialogs.modalOpen))
    widget = calendar()
    original = widget.selectedDate()
    days = widget.findChild(QAbstractItemView)
    assert days is not None
    days.setFocus()
    QTest.keyClick(days, Qt.Key.Key_Right)
    wait_until(lambda: widget.selectedDate() == original.addDays(1))
    assert c.project.to_dict() == before
    assert click_native("taskDateSave")
    wait_until(lambda: not c.dialogs.modalOpen)
    updated_start, updated_end = c.project.span("sensor")
    if field == "start":
        assert updated_start == start + timedelta(days=1)
        assert c.project.tasks["sensor"].duration == 24 * 60
    else:
        assert updated_start == start
        assert updated_end == end + timedelta(days=1)
    assert c.project.tasks["sensor"].effort == 8
    after = c.project.to_dict()
    c.undo()
    assert c.project.to_dict() == before and not c.canUndo
    c.redo()
    assert c.project.to_dict() == after


@pytest.mark.parametrize("field", ["start", "end"])
def test_table_calendar_button_opens_the_correct_field(gui, field):
    c, window = gui
    view = item(window, "ganttView")
    for key in ("showAssignee", "showEffort", "showCost"):
        assert view.setProperty(key, False)
    assert view.setProperty("show" + field.title(), True)
    button = item(window, "calendar-task-" + field + "-sensor")
    wait_until(button.isVisible)
    before = c.project.to_dict()
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(button))
    wait_until(lambda: bool(c.dialogs.modalOpen))
    assert c.selectedId == "sensor"
    assert calendar().selectedDate().toPython() == c.project.span("sensor")[field == "end"].date()
    QTest.keyClick(native_dialog("taskDateDialog"), Qt.Key.Key_Escape)
    assert c.project.to_dict() == before and not c.canUndo


@pytest.mark.parametrize(("task_id", "field"), [("controller", "start"), ("planning", "end"), ("components", "end"), ("missing", "start"), ("sensor", "notes")])
def test_calendar_does_not_open_for_locked_or_invalid_dates(gui, task_id, field):
    c, _window = gui
    c.dialogs.showTaskDate(task_id, field)
    assert not c.dialogs.modalOpen and not c.canUndo


def test_calendar_preserves_time_precision_and_updates_successors(gui):
    c, _window = gui
    assert c.editField("sensor", "startTime", "10:17:23")
    before = c.project.to_dict()
    start = c.project.tasks["sensor"].start
    successor_start = c.project.tasks["controller"].start
    c.dialogs.showTaskDate("sensor", "start")
    calendar().setSelectedDate(calendar().selectedDate().addDays(7))
    assert click_native("taskDateSave")
    assert c.project.tasks["sensor"].start == start + timedelta(days=7)
    assert c.project.tasks["controller"].start > successor_start
    c.undo()
    assert c.project.to_dict() == before


def test_calendar_invalid_finish_keeps_draft_and_reports_error(gui):
    c, _window = gui
    before = c.project.to_dict()
    c.dialogs.showTaskDate("sensor", "end")
    selected = QDate(2025, 12, 1)
    calendar().setSelectedDate(selected)
    assert click_native("taskDateSave")
    dialog = native_dialog("taskDateDialog")
    error = dialog.findChild(QLabel, "dialogError")
    assert dialog.isVisible() and error is not None and error.isVisible() and error.text()
    assert calendar().selectedDate() == selected
    assert c.project.to_dict() == before and not c.canUndo


def test_calendar_rechecks_dependencies_when_applying_a_stale_draft(gui):
    c, _window = gui
    c.dialogs.showTaskDate("sensor", "start")
    calendar().setSelectedDate(calendar().selectedDate().addDays(7))
    assert c.addDependency("scenario", "sensor", "FS", "0")
    before = c.project.to_dict()
    assert click_native("taskDateSave")
    assert native_dialog("taskDateDialog").isVisible()
    assert c.project.to_dict() == before


@pytest.mark.parametrize(("field", "day", "expected"), [
    ("start", QDate(2025, 12, 6), "2025-12-08T09:00"),
    ("end", QDate(2025, 12, 14), "2025-12-12T18:00"),
])
def test_calendar_uses_existing_working_day_normalization(qapp, field, day, expected):
    project = Project(tasks={"a": Task("a", "A", datetime.fromisoformat("2025-12-01T09:00"), 40 * 60)})
    c = Controller(project)
    try:
        c.dialogs.showTaskDate("a", field)
        calendar().setSelectedDate(day)
        assert click_native("taskDateSave")
        assert c.project.span("a")[field == "end"] == datetime.fromisoformat(expected)
    finally:
        c.dialogs.dispose()


@pytest.mark.parametrize("dark", [False, True])
def test_calendar_uses_the_shared_theme_and_system_style(gui, qapp, dark):
    c, _window = gui
    assert c.theme is not None
    c.theme.setDark(dark)
    c.dialogs.showTaskDate("sensor", "start")
    widget = calendar()
    assert widget.style() is qapp.style() and not widget.styleSheet()
    assert widget.palette().color(QPalette.ColorRole.Window) == qapp.palette().color(QPalette.ColorRole.Window)
    assert widget.font().family() == qapp.font().family()


@pytest.mark.parametrize("action", ["load", "hide"])
def test_calendar_closes_with_project_or_window(gui, action):
    c, window = gui
    c.dialogs.showTaskDate("sensor", "start")
    dialog = native_dialog("taskDateDialog")
    if action == "load":
        c.load_project(sample_project())
    else:
        window.hide()
    wait_until(lambda: not dialog.isVisible() and not c.dialogs.modalOpen)
