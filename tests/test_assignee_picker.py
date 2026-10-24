import pytest
from conftest import wait_until
from dialog_helpers import click_native, native_dialog, required_widget
from PySide6.QtCore import QMetaObject, QObject, QPoint, Qt
from PySide6.QtQml import QJSValue
from PySide6.QtTest import QTest
from test_bulk_ui import open_bulk
from test_ui import item, point

from gantt_desktop.controller import Controller


def click(window, name):
    def ready():
        try:
            return item(window, name).isVisible()
        except AssertionError:
            return False
    wait_until(ready)
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(item(window, name)))


def type_text(window, text):
    for character in text:
        QTest.keyClick(window, Qt.Key(ord(character.upper())))


def picker(window):
    result = window.findChild(QObject, "assigneePicker")
    assert result is not None
    return result


def ids(window):
    value = picker(window).property("selectedIds")
    return value.toVariant() if isinstance(value, QJSValue) else value


def open_picker(c, window, surface="table"):
    if surface == "table":
        click(window, "assignee-sensor")
    else:
        c.select("sensor")
        inspector = window.findChild(QObject, "taskInspector")
        assert inspector is not None and QMetaObject.invokeMethod(inspector, "open")
        wait_until(lambda: inspector.property("opened"))
        click(window, "inspectorAssignee")
    popup = picker(window)
    wait_until(lambda: popup.property("opened"))
    return popup


def close_picker(window):
    click(window, "cancelAssignees")
    wait_until(lambda: not picker(window).property("visible"))


@pytest.mark.parametrize("surface", ["table", "inspector"])
@pytest.mark.parametrize("dark", [False, True])
def test_roster_multi_selection_is_a_draft_and_applies_by_ids_once(gui, surface, dark):
    c, window = gui
    assert c.theme is not None
    c.theme.setDark(dark)
    before = c.project.to_dict()
    client = c.project.tasks["sensor"].resource_ids[0]
    artist = c.project.tasks["model"].resource_ids[0]
    popup = open_picker(c, window, surface)
    assert ids(window) == [client]
    click(window, "assignee-option-" + artist)
    assert set(ids(window)) == {client, artist}
    assert c.project.to_dict() == before and not c.canUndo
    click(window, "applyAssignees")
    wait_until(lambda: not popup.property("visible"))
    assert c.project.tasks["sensor"].resource_ids == [client, artist]
    assert c.project.tasks["sensor"].effort == 8
    assert not c.project.tasks["sensor"].resource_shares
    assert len(c.project.resources) == len(before["resources"])
    c.undo()
    assert c.project.to_dict() == before and not c.dirty


@pytest.mark.parametrize("method", ["escape", "outside", "cancel"])
def test_cancelled_selector_does_not_modify_task_or_catalog(gui, method):
    c, window = gui
    before = c.project.to_dict()
    popup = open_picker(c, window)
    artist = c.project.tasks["model"].resource_ids[0]
    click(window, "assignee-option-" + artist)
    if method == "escape":
        QTest.keyClick(window, Qt.Key.Key_Escape)
    elif method == "outside":
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(400, 58))
    else:
        click(window, "cancelAssignees")
    wait_until(lambda: not popup.property("visible"))
    assert c.project.to_dict() == before and not c.canUndo


def test_search_filters_roster_and_unknown_names_never_create_resources(gui):
    c, window = gui
    before = c.project.to_dict()
    popup = open_picker(c, window)
    search = item(window, "assigneeSearch")
    type_text(window, "nobody-new")
    wait_until(lambda: item(window, "assigneeList").property("count") == 0)
    QTest.keyClick(window, Qt.Key.Key_Return)
    assert popup.property("visible")
    assert c.project.to_dict() == before
    search.setProperty("text", "КЛИЕНТ")
    wait_until(lambda: item(window, "assigneeList").property("count") == 1)
    QTest.keyClick(window, Qt.Key.Key_Escape)
    wait_until(lambda: not popup.property("visible"))
    assert c.project.to_dict() == before and not c.dirty


def test_unchanged_or_reordered_choice_keeps_manual_effort_shares(gui):
    c, window = gui
    client = c.project.tasks["sensor"].resource_ids[0]
    artist = c.project.tasks["model"].resource_ids[0]
    assert c.assignResources("sensor", [client, artist], [1, 7])
    before = c.project.to_dict()
    index = c._history_index
    open_picker(c, window)
    click(window, "assignee-option-" + client)
    click(window, "assignee-option-" + client)
    click(window, "applyAssignees")
    wait_until(lambda: not picker(window).property("visible"))
    assert c.project.to_dict() == before and c._history_index == index
    assert c.project.tasks["sensor"].resource_shares == [0.125, 0.875]


def test_reset_unassigns_without_deleting_people_or_effort(gui):
    c, window = gui
    before = c.project.to_dict()
    open_picker(c, window)
    click(window, "resetAssignees")
    assert ids(window) == [] and c.project.to_dict() == before
    click(window, "applyAssignees")
    wait_until(lambda: not picker(window).property("visible"))
    assert c.project.tasks["sensor"].resource_ids == []
    assert c.project.tasks["sensor"].effort == 8
    assert len(c.project.resources) == len(before["resources"])
    c.undo()
    assert c.project.to_dict() == before


def test_explicit_add_opens_a_named_resource_draft_and_does_not_autoassign(gui):
    c, window = gui
    before = c.project.to_dict()
    original = list(c.project.tasks["sensor"].resource_ids)
    open_picker(c, window)
    type_text(window, "alex")
    click(window, "addAssigneeResource")
    manager = native_dialog("resourceManager")
    wait_until(manager.isVisible)
    assert required_widget("resourceName").property("text") == "alex"
    assert c.project.to_dict() == before
    assert click_native("saveResourceButton")
    created = next(r.id for r in c.project.resources.values() if r.name == "alex")
    assert c.project.tasks["sensor"].resource_ids == original
    assert click_native("closeResourcesButton")
    wait_until(lambda: not c.dialogs.property("modalOpen"))
    assert picker(window).property("visible")
    click(window, "assignee-option-" + created)
    click(window, "applyAssignees")
    wait_until(lambda: not picker(window).property("visible"))
    assert c.project.tasks["sensor"].resource_ids == original + [created]
    c.undo()
    assert c.project.tasks["sensor"].resource_ids == original and created in c.project.resources
    c.undo()
    assert c.project.to_dict() == before


def test_hours_action_keeps_native_allocation_editor_available(gui):
    c, window = gui
    before = c.project.to_dict()
    artist = c.project.tasks["model"].resource_ids[0]
    client = c.project.tasks["sensor"].resource_ids[0]
    open_picker(c, window)
    click(window, "assignee-option-" + artist)
    click(window, "assigneeHoursButton")
    native = native_dialog("resourcePicker")
    wait_until(native.isVisible)
    assert required_widget("assignmentHours-" + client).property("value") == 4
    assert required_widget("assignmentHours-" + artist).property("value") == 4
    assert c.project.to_dict() == before and not c.canUndo
    assert click_native("cancelResourceAssignment")
    wait_until(lambda: not picker(window).property("visible"))
    assert c.project.to_dict() == before and not c.canUndo
    open_picker(c, window)
    click(window, "assignee-option-" + artist)
    click(window, "assigneeHoursButton")
    assert required_widget("assignmentHours-" + client).setProperty("value", 1)
    assert required_widget("assignmentHours-" + artist).setProperty("value", 7)
    assert click_native("applyResourceAssignment")
    assert c.project.tasks["sensor"].resource_ids == [client, artist]
    assert c.project.tasks["sensor"].resource_shares == [0.125, 0.875]
    assert c._history_index == 1
    c.undo()
    assert c.project.to_dict() == before


def test_bulk_uses_same_roster_and_applies_to_checked_leaves_once(gui):
    c, window = gui
    before = c.project.to_dict()
    client = c.project.tasks["sensor"].resource_ids[0]
    artist = c.project.tasks["model"].resource_ids[0]
    open_bulk(c, window)
    click(window, "bulk-check-planning")
    click(window, "bulkAssignEnabled")
    click(window, "bulkAssignee")
    wait_until(lambda: picker(window).property("opened"))
    click(window, "assignee-option-" + client)
    click(window, "assignee-option-" + artist)
    click(window, "applyAssignees")
    wait_until(lambda: not picker(window).property("visible"))
    assert c.project.to_dict() == before and not c.canUndo
    click(window, "applyBulkButton")
    for task in c.project.tasks.values():
        if task.parent == "planning":
            assert task.resource_ids == [client, artist]
    assert c.project.tasks["planning"].resource_ids == []
    c.undo()
    assert c.project.to_dict() == before


def test_bulk_selector_escape_keeps_bulk_draft_and_selection_unapplied(gui):
    c, window = gui
    before = c.project.to_dict()
    open_bulk(c, window)
    click(window, "bulk-check-sensor")
    click(window, "bulkAssignEnabled")
    click(window, "bulkAssignee")
    wait_until(lambda: picker(window).property("opened"))
    click(window, "assignee-option-" + c.project.tasks["model"].resource_ids[0])
    QTest.keyClick(window, Qt.Key.Key_Escape)
    wait_until(lambda: not picker(window).property("visible"))
    assert c.bulkMode and c.checkedCount == 1
    assert c.project.to_dict() == before and not c.canUndo
    QTest.keyClick(window, Qt.Key.Key_Escape)
    wait_until(lambda: not c.bulkMode)
    assert c.project.to_dict() == before


@pytest.mark.parametrize("width", [1000, 1366, 1920])
def test_dropdown_fits_window_and_scrolls_a_large_catalog(gui, width):
    c, window = gui
    for i in range(12):
        assert c.createResource("Person " + str(i))
    window.resize(width, 768)
    wait_until(lambda: item(window, "ganttView").width() == width - 260)
    popup = open_picker(c, window)
    assert popup.property("x") >= 0 and popup.property("y") >= 0
    assert popup.property("x") + popup.property("width") <= width
    assert popup.property("y") + popup.property("height") <= window.height()
    view = item(window, "assigneeList")
    assert view.property("contentHeight") > view.height()
    view.setProperty("contentY", view.property("contentHeight") - view.height())
    close_picker(window)


def test_selection_api_is_id_based_validated_and_bulk_keeps_shares(qapp):
    c = Controller()
    before = c.project.to_dict()
    client = c.project.tasks["sensor"].resource_ids[0]
    artist = c.project.tasks["model"].resource_ids[0]
    assert not c.chooseTaskResources("sensor", ["New name"])
    assert not c.chooseTaskResources("sensor", [client, client])
    assert not c.chooseTaskResources("planning", [])
    assert c.project.to_dict() == before and not c.canUndo
    assert c.assignResources("sensor", [client, artist], [1, 7])
    snapshot = c.project.to_dict()
    index = c._history_index
    assert c.chooseTaskResources("sensor", [artist, client])
    assert c.project.to_dict() == snapshot and c._history_index == index
    c.setBulkMode(True)
    c.toggleChecked("sensor")
    assert c.applyBulk({"resourceIds": [client, artist]})
    assert c.project.to_dict() == snapshot and c._history_index == index
    assert not c.applyBulk({"resourceIds": ["unknown"]})
    assert c.project.to_dict() == snapshot


def test_deleted_people_are_removed_from_an_open_selection_draft(gui):
    c, window = gui
    client = c.project.tasks["sensor"].resource_ids[0]
    artist = c.project.tasks["model"].resource_ids[0]
    open_picker(c, window)
    click(window, "assignee-option-" + artist)
    assert set(ids(window)) == {client, artist}
    assert c.removeResource(artist)
    wait_until(lambda: ids(window) == [client])
    assert picker(window).property("visible")
    close_picker(window)
    c.undo()
    assert artist in c.project.resources
