from copy import deepcopy

import pytest
from conftest import wait_until
from dialog_helpers import click_native, native_dialog, replace_native, required_widget
from PySide6.QtCore import QMetaObject, QObject, QPoint, Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QTreeWidget, QWidget
from test_custom_fields_ui import toggle_list
from test_ui import drag, item, point

from gantt_desktop.domain import Project
from gantt_desktop.sample import sample_project
from gantt_desktop.theme import DARK, LIGHT


def click(window, name):
    target = item(window, name)
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(target))


def open_manager(window):
    click(window, "baselinesButton")
    dialog = native_dialog("baselineDialog")
    wait_until(dialog.isVisible)
    return dialog


def choose(key):
    table = required_widget("baselineList")
    assert isinstance(table, QTreeWidget)
    for index in range(table.topLevelItemCount()):
        candidate = table.topLevelItem(index)
        if candidate is not None and candidate.data(0, Qt.ItemDataRole.UserRole) == key:
            table.setCurrentItem(candidate)
            return
    raise AssertionError(key)


def delete_confirmation(accept):
    box = next(widget for widget in QApplication.topLevelWidgets()
               if isinstance(widget, QMessageBox) and widget.isVisible() and widget.objectName() == "deleteBaselineDialog")
    button = box.button(QMessageBox.StandardButton.Ok if accept else QMessageBox.StandardButton.Cancel)
    assert button is not None
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("width", [1000, 1366, 1920])
def test_native_capture_from_header_keeps_tasks_and_renders_baseline_undo(gui, dark, width):
    c, window = gui
    assert c.theme is not None
    c.theme.setDark(dark)
    window.resize(width, 960)
    before = c.project.to_dict()
    button = item(window, "baselinesButton")
    assert 0 <= point(button).x() < width
    manager = open_manager(window)
    assert manager.windowHandle().transientParent() is window
    assert replace_native("baselineName", "Initial") and click_native("createBaseline")
    key = c.project.active_baseline
    assert key and len(c.project.baselines[key].tasks) == len(c.project.tasks)
    assert c.project.to_dict()["tasks"] == before["tasks"]
    assert click_native("closeBaselines")
    assert item(window, "baselineInfo").isVisible()
    assert item(window, "baseline-bar-sensor").isVisible()
    assert c.dirty and c.canUndo
    c.undo()
    assert c.project.to_dict() == before and not item(window, "baseline-bar-sensor").isVisible()
    c.redo()
    assert c.project.active_baseline == key and item(window, "baseline-bar-sensor").isVisible()


def test_enter_captures_only_explicit_name_draft_and_close_without_capture_is_noop(gui):
    c, window = gui
    before = c.project.to_dict()
    manager = open_manager(window)
    assert replace_native("baselineName", "Draft") and click_native("closeBaselines")
    assert c.project.to_dict() == before and not c.canUndo
    manager = open_manager(window)
    assert replace_native("baselineName", "Keyboard")
    QTest.keyClick(required_widget("baselineName"), Qt.Key.Key_Return)
    wait_until(lambda: bool(c.project.baselines))
    assert manager.isVisible() and len(c.project.baselines) == 1
    assert c.project.baselines[c.project.active_baseline].name == "Keyboard"
    assert click_native("createBaseline")
    table = required_widget("baselineList")
    assert isinstance(table, QTreeWidget)
    selected = table.currentItem()
    assert selected is not None and selected.data(0, Qt.ItemDataRole.UserRole) == c.project.active_baseline


def test_select_hide_delete_cancel_and_delete_undo_do_not_restore_task_dates(gui):
    c, window = gui
    first = c.createBaseline("First")
    assert c.moveTask("sensor", 7)
    second = c.createBaseline("Second")
    tasks = deepcopy(c.project.to_dict()["tasks"])
    open_manager(window)
    choose(first)
    assert click_native("useBaseline")
    assert c.project.active_baseline == first and c.project.to_dict()["tasks"] == tasks
    assert click_native("hideBaseline")
    assert c.project.active_baseline == "" and c.project.to_dict()["tasks"] == tasks
    choose(second)
    assert click_native("useBaseline") and click_native("removeBaseline")
    delete_confirmation(False)
    assert second in c.project.baselines and c.project.active_baseline == second
    assert click_native("removeBaseline")
    delete_confirmation(True)
    assert second not in c.project.baselines and c.project.active_baseline == ""
    c.undo()
    assert second in c.project.baselines and c.project.active_baseline == second
    assert c.project.to_dict()["tasks"] == tasks


@pytest.mark.parametrize("name", ["", "INITIAL"])
def test_invalid_snapshot_name_keeps_draft_and_does_not_create_a_partial_record(gui, name):
    c, window = gui
    assert c.createBaseline("Initial")
    before = c.project.to_dict()
    manager = open_manager(window)
    assert replace_native("baselineName", name)
    if not name:
        QTest.keyClick(required_widget("baselineName"), Qt.Key.Key_Backspace)
    assert click_native("createBaseline")
    error = manager.findChild(QLabel, "dialogError")
    assert error is not None and error.isVisible()
    assert c.project.to_dict() == before


@pytest.mark.parametrize("key", ["baselineStart", "baselineEnd", "startVariance", "endVariance"])
def test_comparison_columns_are_real_resizable_read_only_fields(gui, key):
    c, window = gui
    assert c.createBaseline("Initial")
    assert c.moveTask("sensor", 7)
    view = item(window, "ganttView")
    for flag in ("showAssignee", "showEffort", "showCost"):
        view.setProperty(flag, False)
    c.dialogs.showFields({key: False})
    toggle_list(required_widget("standardFields"), key)
    assert click_native("closeFields")
    field = item(window, "task-"+key+"-sensor")
    wait_until(field.isVisible)
    assert field.property("readOnly") and field.property("text") == c.record("sensor")[key]
    before = c.project.to_dict()
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(field))
    QTest.keyClick(window, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(window, Qt.Key.Key_Backspace)
    assert c.project.to_dict() == before
    header = item(window, "column-header-"+key)
    width = header.width()
    start = point(header, 1, 0.5)
    drag(window, start, start+QPoint(30, 0))
    wait_until(lambda: item(window, "column-header-"+key).width() == pytest.approx(width+30))
    assert c.project.to_dict() == before


def test_baseline_geometry_stays_frozen_tracks_zoom_and_does_not_steal_resize(gui):
    c, window = gui
    assert c.createBaseline("Initial")
    baseline = item(window, "baseline-bar-sensor")
    original = baseline.x()
    assert c.moveTask("sensor", 7)
    wait_until(lambda: item(window, "baseline-bar-sensor").x() == original)
    assert item(window, "taskbar-sensor").x() > original
    view = item(window, "ganttView")
    view.setProperty("pixelsPerDay", 26)
    wait_until(lambda: item(window, "baseline-bar-sensor").x() == c.record("sensor")["baselineStartDay"]*26)
    duration = c.project.tasks["sensor"].duration
    frame = QSignalSpy(window.frameSwapped)
    c.focusTask("sensor")
    assert frame.wait(3000)
    wait_until(lambda: point(item(window, "resize-end-sensor")).x() > point(item(window, "gridDivider")).x()+20)
    handle = item(window, "resize-end-sensor")
    start = point(handle)
    drag(window, start, start+QPoint(26, 0))
    wait_until(lambda: c.project.tasks["sensor"].duration > duration)
    assert c.project.baselines[c.project.active_baseline].tasks["sensor"].start.day == 15
    assert item(window, "baseline-bar-components").property("point")


def test_inspector_shows_snapshot_times_and_handles_new_tasks_without_zero_dates(gui):
    c, window = gui
    assert c.createBaseline("Initial")
    assert c.moveTask("sensor", 7)
    c.select("sensor")
    inspector = window.findChild(QObject, "taskInspector")
    assert inspector is not None and QMetaObject.invokeMethod(inspector, "open")
    wait_until(lambda: inspector.property("opened"))
    label = item(window, "inspectorBaseline")
    assert label.isVisible() and "15.12.2025 09:00" in label.property("text")
    assert "+168" in label.property("text")
    c.addTask("", "task")
    wait_until(lambda: "Элемента нет" in label.property("text"))


@pytest.mark.parametrize("dark", [False, True])
def test_baseline_manager_uses_live_shared_theme_native_style_and_large_font(gui, qapp, dark):
    c, window = gui
    assert c.theme is not None
    previous = QFont(qapp.font())
    font = QFont(previous)
    font.setPointSize(14)
    try:
        qapp.setFont(font)
        manager = open_manager(window)
        for value in (dark, not dark, dark):
            c.theme.setDark(value)
            expected = QColor((DARK if value else LIGHT)["surface"])
            wait_until(lambda expected=expected: manager.palette().color(QPalette.ColorRole.Window) == expected)
        assert manager.width() >= manager.minimumSizeHint().width() and manager.height() >= manager.minimumSizeHint().height()
        for widget in [manager, *manager.findChildren(QWidget)]:
            assert widget.style() is qapp.style() and not widget.styleSheet()
    finally:
        c.dialogs.closeAll()
        qapp.setFont(previous)


@pytest.mark.parametrize("action", ["load", "hide", "close"])
def test_baseline_manager_and_pending_confirmation_close_without_deleting_on_lifecycle(gui, action):
    c, window = gui
    key = c.createBaseline("Initial")
    before = c.project.to_dict()
    open_manager(window)
    choose(key)
    assert click_native("removeBaseline")
    if action == "load":
        c.load_project(sample_project())
    elif action == "hide":
        window.hide()
    else:
        window.close()
    wait_until(lambda: not c.dialogs.modalOpen)
    if action != "load":
        assert c.project.to_dict() == before


def test_empty_baseline_is_a_real_persistable_snapshot_without_fake_rows(gui):
    c, _window = gui
    c.load_project(Project())
    assert c.createBaseline("Empty")
    assert "совпадает: 0" in c.property("baselineInfo")
    assert not c.project.baselines[c.project.active_baseline].tasks
