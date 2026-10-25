from datetime import date

import pytest
from conftest import wait_until
from dialog_helpers import click_native, native_dialog, replace_native, required_widget
from PySide6.QtCore import QDate, Qt, QTime
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QLabel,
    QMessageBox,
    QTimeEdit,
    QTreeWidget,
    QWidget,
)
from test_calendar_exceptions import exception, project, save

from gantt_desktop.theme import DARK, LIGHT


def set_range(start, end):
    for name, value in (("exceptionStart", start), ("exceptionEnd", end)):
        widget = required_widget(name)
        assert isinstance(widget, QDateEdit)
        widget.setDate(QDate.fromString(value, Qt.DateFormat.ISODate))


def set_time(name, hours, minutes=0):
    widget = required_widget(name)
    assert isinstance(widget, QTimeEdit)
    widget.setTime(QTime(hours, minutes))


def table():
    widget = required_widget("calendarExceptions")
    assert isinstance(widget, QTreeWidget)
    return widget


def open_new(c, resource=""):
    c.dialogs.showCalendar(resource)
    assert click_native("newCalendarException")
    dialog = native_dialog("calendarExceptionDialog")
    wait_until(dialog.isVisible)
    return dialog


def accept_delete():
    box = next(widget for widget in QApplication.topLevelWidgets()
               if isinstance(widget, QMessageBox) and widget.isVisible() and widget.objectName() == "deleteCalendarExceptionDialog")
    button = box.button(QMessageBox.StandardButton.Ok)
    assert button is not None
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)


@pytest.mark.parametrize("resource", [False, True])
def test_resource_manager_buttons_open_real_calendar_lists_and_cancel_is_noop(gui, resource):
    c, window = gui
    rid = c.project.tasks["sensor"].resource_ids[0]
    before = c.project.to_dict()
    c.dialogs.showResources(rid)
    assert click_native("resourceExceptionsButton" if resource else "projectExceptionsButton")
    listing = native_dialog("calendarDialog")
    assert listing.windowHandle().transientParent() is window
    assert click_native("newCalendarException")
    editor = native_dialog("calendarExceptionDialog")
    set_range("2026-01-05", "2026-01-09")
    assert replace_native("exceptionName", "Draft")
    assert c.project.to_dict() == before
    assert click_native("calendarExceptionCancel")
    assert not editor.isVisible() and table().topLevelItemCount() == 0
    assert click_native("closeCalendar")
    assert not listing.isVisible()
    assert c.project.to_dict() == before and not c.canUndo


def test_project_holiday_apply_and_list_edit_delete_cancel_and_undo(gui):
    c, _window = gui
    c.load_project(project())
    before = c.project.to_dict()
    editor = open_new(c)
    set_range("2026-01-06", "2026-01-06")
    assert replace_native("exceptionName", "Holiday")
    assert click_native("calendarExceptionSave")
    wait_until(lambda: not editor.isVisible())
    assert table().topLevelItemCount() == 1
    assert c.project.tasks["b"].start.day == 8
    after = c.project.to_dict()
    assert click_native("editCalendarException")
    assert click_native("calendarExceptionSave")
    assert c.project.to_dict() == after
    assert click_native("removeCalendarException")
    QTest.keyClick(native_dialog("deleteCalendarExceptionDialog"), Qt.Key.Key_Escape)
    assert c.project.to_dict() == after
    assert click_native("removeCalendarException")
    accept_delete()
    assert table().topLevelItemCount() == 0
    c.undo()
    assert c.project.to_dict() == after
    c.undo()
    assert c.project.to_dict() == before and not c.canUndo


def test_resource_leave_and_fractional_capacity_are_atomic_native_edits(gui):
    c, _window = gui
    c.load_project(project())
    rid = next(iter(c.project.resources))
    before = c.project.to_dict()
    editor = open_new(c, rid)
    set_range("2026-01-05", "2026-01-06")
    assert replace_native("exceptionCapacity", "2.5")
    assert click_native("calendarExceptionSave")
    wait_until(lambda: not editor.isVisible())
    saved = c.project.resources[rid].exceptions[0]
    assert saved.capacity == 2.5 and saved.start == date(2026, 1, 5) and saved.end == date(2026, 1, 6)
    assert c.project.to_dict()["tasks"] == before["tasks"]
    assert click_native("editCalendarException")
    assert replace_native("exceptionCapacity", "0")
    assert click_native("calendarExceptionSave")
    assert c.project.resources[rid].available(saved.start) == 0
    c.undo()
    assert c.project.resources[rid].available(saved.start) == 2.5


def test_working_exception_controls_validate_intervals_without_losing_draft(gui):
    c, _window = gui
    before = c.project.to_dict()
    editor = open_new(c)
    set_range("2026-01-10", "2026-01-10")
    combo = required_widget("exceptionMode")
    assert isinstance(combo, QComboBox)
    combo.setCurrentIndex(1)
    set_time("exceptionStartTime1", 7)
    set_time("exceptionEndTime1", 16)
    set_time("exceptionStartTime2", 14)
    assert click_native("calendarExceptionSave")
    error = editor.findChild(QLabel, "dialogError")
    assert editor.isVisible() and error is not None and error.isVisible() and error.text()
    assert c.project.to_dict() == before and not c.canUndo
    set_time("exceptionEndTime1", 11)
    assert click_native("calendarExceptionSave")
    assert c.project.calendar.exceptions[0].periods == [[420, 660], [840, 1080]]
    assert c.project.calendar.working_day(date(2026, 1, 10))


@pytest.mark.parametrize("invalid", ["range", "overlap"])
def test_invalid_ranges_are_visible_errors_with_no_silent_replacement(gui, invalid):
    c, _window = gui
    if invalid == "overlap":
        assert save(c, start="2026-01-05", end="2026-01-08")
    before = c.project.to_dict()
    editor = open_new(c)
    set_range("2026-01-07", "2026-01-06" if invalid == "range" else "2026-01-10")
    assert click_native("calendarExceptionSave")
    error = editor.findChild(QLabel, "dialogError")
    assert error is not None and error.isVisible() and editor.isVisible()
    assert c.project.to_dict() == before


def test_native_legacy_holiday_can_be_edited_without_a_spurious_noop_history(gui):
    c, _window = gui
    p = project()
    p.calendar.holidays.add(date(2026, 1, 6))
    c.load_project(p)
    before = c.project.to_dict()
    c.dialogs.showCalendar("")
    assert table().topLevelItemCount() == 1
    assert click_native("editCalendarException") and click_native("calendarExceptionSave")
    assert c.project.to_dict() == before and not c.canUndo
    assert click_native("removeCalendarException")
    accept_delete()
    assert not c.project.calendar.holidays
    c.undo()
    assert c.project.to_dict() == before


def test_unchanged_capacity_draft_preserves_precision_beyond_spinbox_display(gui):
    c, _window = gui
    rid = c.project.tasks["sensor"].resource_ids[0]
    assert save(c, rid, capacity="2.001")
    before = c.project.to_dict()
    c.dialogs.showCalendar(rid)
    assert click_native("editCalendarException")
    spinbox = required_widget("exceptionCapacity")
    assert isinstance(spinbox, QDoubleSpinBox) and spinbox.value() == 2.0
    assert click_native("calendarExceptionSave")
    assert c.project.to_dict() == before


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("resource", [False, True])
def test_exception_editors_use_native_style_shared_palette_and_large_font(gui, qapp, dark, resource):
    c, window = gui
    assert c.theme is not None
    c.theme.setDark(dark)
    previous = QFont(qapp.font())
    font = QFont(previous)
    font.setPointSize(14)
    try:
        qapp.setFont(font)
        rid = c.project.tasks["sensor"].resource_ids[0] if resource else ""
        editor = open_new(c, rid)
        qapp.processEvents()
        assert editor.windowHandle().transientParent() is window
        assert editor.width() >= editor.minimumSizeHint().width() and editor.height() >= editor.minimumSizeHint().height()
        for value in (dark, not dark, dark):
            c.theme.setDark(value)
            expected = QColor((DARK if value else LIGHT)["surface"])
            wait_until(lambda expected=expected: editor.palette().color(QPalette.ColorRole.Window) == expected)
            assert editor.palette().color(QPalette.ColorRole.Window) == qapp.palette().color(QPalette.ColorRole.Window)
        assert editor.font().pointSize() == 14
        for widget in [editor, *editor.findChildren(QWidget)]:
            assert widget.style() is qapp.style() and not widget.styleSheet()
    finally:
        c.dialogs.closeAll()
        qapp.setFont(previous)


@pytest.mark.parametrize("action", ["load", "hide", "close"])
def test_calendar_stack_and_pending_delete_close_without_mutation(gui, action):
    c, window = gui
    p = project()
    p.calendar.exceptions = [exception()]
    c.load_project(p)
    before = c.project.to_dict()
    c.dialogs.showCalendar("")
    assert click_native("removeCalendarException")
    if action == "load":
        c.load_project(project())
    elif action == "hide":
        window.hide()
    else:
        window.close()
    wait_until(lambda: not c.dialogs.modalOpen)
    if action != "load":
        assert c.project.to_dict() == before


def test_stale_exception_edit_fails_without_recreating_deleted_item(gui):
    c, _window = gui
    assert save(c)
    key = c.project.calendar.exceptions[0].id
    c.dialogs.showCalendarException("", key, "")
    assert c.removeCalendarException("", key)
    before = c.project.to_dict()
    assert click_native("calendarExceptionSave")
    editor = native_dialog("calendarExceptionDialog")
    assert editor.isVisible() and c.project.to_dict() == before


def test_new_resource_requires_explicit_save_before_editing_its_calendar(gui):
    c, _window = gui
    before = c.project.to_dict()
    c.dialogs.showNewResource("Draft")
    button = required_widget("resourceExceptionsButton")
    assert not button.isEnabled()
    assert c.project.to_dict() == before and not c.canUndo


@pytest.mark.parametrize("resource", [False, True])
def test_enter_saves_only_the_focused_exception_draft(gui, resource):
    c, _window = gui
    rid = c.project.tasks["sensor"].resource_ids[0] if resource else ""
    before = c.project.to_dict()
    editor = open_new(c, rid)
    set_range("2026-01-10", "2026-01-10")
    assert replace_native("exceptionName", "Keyboard")
    QTest.keyClick(required_widget("exceptionName"), Qt.Key.Key_Return)
    wait_until(lambda: not editor.isVisible())
    items = c.project.resources[rid].exceptions if resource else c.project.calendar.exceptions
    assert len(items) == 1 and items[0].name == "Keyboard"
    if resource:
        assert c.project.to_dict()["tasks"] == before["tasks"]
    c.undo()
    assert c.project.to_dict() == before
