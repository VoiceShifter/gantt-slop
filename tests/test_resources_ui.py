from datetime import date, datetime, time

from conftest import wait_until
from dialog_helpers import click_native, native_dialog, replace_native, required_widget
from PySide6.QtCore import QObject, QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDoubleSpinBox
from test_resources import MONDAY, project_with_task
from test_ui import drag, item, point, undo

from gantt_desktop.domain import Task


def click(window, name):
    if click_native(name):
        return
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(item(window, name)))


def replace(window, name, value):
    if replace_native(name, value):
        return
    click(window, name)
    QTest.keyClick(window, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    for character in value:
        QTest.keyClick(window, Qt.Key(ord(character.upper())))


def test_workload_toggle_zoom_pan_and_divider_stay_synchronized(gui):
    c, window = gui
    before = c.project.to_dict()
    click(window, "workloadToggle")
    panel = item(window, "resourceWorkload")
    wait_until(panel.isVisible)
    view = item(window, "ganttView")
    assert panel.property("gridWidth") == view.property("gridWidth")
    drag(window, QPoint(1800, 450), QPoint(1700, 450))
    wait_until(lambda: view.property("scrollX") >= 90)
    assert panel.property("scrollX") == view.property("scrollX")
    start = point(item(window, "gridDivider"), 0.5, 0.2)
    drag(window, start, start - QPoint(70, 0))
    wait_until(lambda: panel.property("gridWidth") == view.property("gridWidth"))
    zoom = item(window, "zoomSlider")
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(zoom, 0.2, 0.5))
    wait_until(lambda: view.property("pixelsPerDay") > 10)
    assert panel.property("pixelsPerDay") == view.property("pixelsPerDay")
    click(window, "workloadPercentMode")
    assert panel.property("mode") == 1
    click(window, "workloadTasksMode")
    assert panel.property("mode") == 2
    click(window, "workloadToggle")
    assert not panel.isVisible()
    assert c.project.to_dict() == before and not c.canUndo


def test_create_person_with_capacity_and_workdays_is_one_native_edit(gui):
    c, window = gui
    before = c.project.to_dict()
    click(window, "resourcesButton")
    manager = native_dialog("resourceManager")
    wait_until(manager.isVisible)
    click(window, "newResourceButton")
    replace(window, "resourceName", "alex")
    replace(window, "resourceCapacity", "4")
    click(window, "resourceDay-5")
    click(window, "saveResourceButton")
    wait_until(lambda: any(r.name == "alex" for r in c.project.resources.values()))
    resource = next(r for r in c.project.resources.values() if r.name == "alex")
    assert resource.capacity == 4 and resource.workdays == set(range(6))
    click(window, "closeResourcesButton")
    wait_until(lambda: not manager.property("visible"))
    undo(window)
    wait_until(lambda: c.project.to_dict() == before)


def test_calendar_button_renames_the_entity_everywhere(gui):
    c, window = gui
    before = c.project.to_dict()
    key = c.project.tasks["sensor"].resource_ids[0]
    click(window, "workloadToggle")
    click(window, "resource-calendar-" + key)
    manager = native_dialog("resourceManager")
    wait_until(manager.isVisible)
    assert required_widget("resourceName").property("text") == "Клиент"
    replace(window, "resourceName", "customer")
    click(window, "saveResourceButton")
    wait_until(lambda: c.project.resources[key].name == "customer")
    assert c.project.tasks["sensor"].assignee == "customer"
    assert c.project.tasks["scenario"].resource_ids == [key]
    click(window, "closeResourcesButton")
    wait_until(lambda: not manager.property("visible"))
    undo(window)
    wait_until(lambda: c.project.to_dict() == before)


def open_assignments(window):
    target = point(item(window, "taskbar-sensor"))
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, target)
    QTest.mouseDClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, target)
    QTest.mouseRelease(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, target)
    inspector = window.findChild(QObject, "taskInspector")
    wait_until(lambda: inspector.property("opened"))
    click(window, "chooseResourcesButton")
    picker = native_dialog("resourcePicker")
    wait_until(picker.isVisible)
    return picker


def test_native_multi_assignment_and_cancelled_draft(gui):
    c, window = gui
    before = c.project.to_dict()
    artist = c.project.tasks["model"].resource_ids[0]
    client = c.project.tasks["sensor"].resource_ids[0]
    picker = open_assignments(window)
    click(window, "assign-resource-" + artist)
    assert c.project.to_dict() == before
    assert required_widget("assignmentHours-" + artist).property("value") == 4
    click(window, "cancelResourceAssignment")
    wait_until(lambda: not picker.property("visible"))
    assert c.project.to_dict() == before and not c.canUndo
    click(window, "chooseResourcesButton")
    wait_until(picker.isVisible)
    click(window, "assign-resource-" + artist)
    click(window, "applyResourceAssignment")
    wait_until(lambda: c.project.tasks["sensor"].resource_ids == [client, artist])
    assert c.project.tasks["sensor"].effort == 8
    wait_until(lambda: not picker.property("visible"))
    c.undo()
    assert c.project.to_dict() == before


def test_project_working_saturday_produces_a_weekend_warning_and_undo(gui):
    c, window = gui
    p = project_with_task(hours=16, duration=960, start=date(2026, 1, 9))
    c.load_project(p)
    before = c.project.to_dict()
    click(window, "resourcesButton")
    manager = native_dialog("resourceManager")
    wait_until(manager.isVisible)
    click(window, "projectDay-5")
    click(window, "applyProjectCalendar")
    wait_until(lambda: 5 in c.project.calendar.workdays)
    row = c.property("workloadRows")[0]
    saturday = next(d for d in row["days"] if d["date"] == "2026-01-10")
    assert saturday["hours"] == 8 and saturday["capacity"] == 0
    assert saturday["weekendWork"] and saturday["overloaded"]
    click(window, "closeResourcesButton")
    wait_until(lambda: not manager.property("visible"))
    click(window, "workloadToggle")
    assert item(window, "resourceWorkload").isVisible()
    undo(window)
    wait_until(lambda: c.project.to_dict() == before)


def test_expanded_resource_task_bar_opens_real_task_properties(gui):
    c, window = gui
    key = c.project.tasks["sensor"].resource_ids[0]
    click(window, "workloadToggle")
    click(window, "resource-row-" + key)
    wait_until(lambda: item(window, "resource-row-" + key).height() > 30)
    click(window, "workload-task-" + key + "-sensor")
    inspector = window.findChild(QObject, "taskInspector")
    wait_until(lambda: inspector.property("opened"))
    assert c.selectedId == "sensor" and not c.canUndo


def test_overload_cell_details_show_both_contributing_tasks(gui):
    c, window = gui
    p = project_with_task()
    p.tasks["b"] = Task("b", "Task B", datetime.combine(MONDAY, time(9)), effort=8)
    p.assign_resources("b", p.tasks["a"].resource_ids)
    c.load_project(p)
    click(window, "workloadToggle")
    canvas = item(window, "workloadCanvas")
    panel = item(window, "resourceWorkload")
    days = c.property("days")
    offset = next(d["offset"] for d in days if d["number"] == 5 and d["monday"])
    x = (offset + 3.5) * panel.property("pixelsPerDay")
    target = canvas.mapToScene(QPointF(x, 15)).toPoint()
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, target)
    detail = window.findChild(QObject, "workloadDetail")
    wait_until(lambda: detail.property("visible"))
    text = item(window, "workloadDetailText").property("text")
    assert "16ч" in text and "Перегрузка" in text and "Task A" in text and "Task B" in text
    assert not c.canUndo


def test_assignment_spinbox_rejects_invalid_text(gui):
    c, window = gui
    before = c.project.to_dict()
    client = c.project.tasks["sensor"].resource_ids[0]
    picker = open_assignments(window)
    spin = required_widget("assignmentHours-" + client)
    assert isinstance(spin, QDoubleSpinBox)
    replace(window, "assignmentHours-" + client, "bad")
    spin.interpretText()
    assert spin.value() == 8 and picker.isVisible()
    assert c.project.to_dict() == before and not c.canUndo
    click(window, "cancelResourceAssignment")
