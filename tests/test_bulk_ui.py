from conftest import wait_until
from PySide6.QtCore import QObject, QPoint, Qt
from PySide6.QtTest import QTest
from test_ui import drag, item, point, undo


def click(window, name):
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(item(window, name)))


def open_bulk(controller, window):
    click(window, "bulkModeButton")
    drawer = window.findChild(QObject, "bulkEditor")
    assert drawer is not None
    wait_until(lambda: drawer.property("opened"))
    assert controller.property("bulkMode")
    return drawer


def choose(window, name, index):
    control = item(window, name)
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(control))
    QTest.keyClick(window, Qt.Key.Key_Home)
    for _ in range(index):
        QTest.keyClick(window, Qt.Key.Key_Down)
    QTest.keyClick(window, Qt.Key.Key_Return)
    wait_until(lambda: control.property("currentIndex") == index)


def visible_button(window, labels):
    pending = [window.contentItem()]
    while pending:
        candidate = pending.pop()
        text = candidate.property("text")
        if (isinstance(text, str) and text.replace("&", "") in labels
                and candidate.property("down") is not None and candidate.isVisible()):
            return candidate
        pending.extend(candidate.childItems())
    raise AssertionError(f"No visible button in {labels}")


def test_real_group_check_partial_state_select_all_and_cancel(gui):
    c, window = gui
    before = c.project.to_dict()
    open_bulk(c, window)
    click(window, "bulk-check-planning")
    wait_until(lambda: c.property("checkedCount") == 6)
    click(window, "bulk-check-scenario")
    wait_until(lambda: c.property("checkedCount") == 5)
    assert item(window, "bulk-check-planning").property("checkState") == Qt.CheckState.PartiallyChecked
    QTest.keyClick(window, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    wait_until(lambda: c.property("checkedCount") == 20)
    assert item(window, "bulk-check-__total__").property("checked")
    QTest.keyClick(window, Qt.Key.Key_Escape)
    wait_until(lambda: not c.property("bulkMode"))
    assert c.property("checkedCount") == 0
    assert c.project.to_dict() == before and not c.canUndo


def test_real_bulk_status_priority_apply_and_single_undo(gui):
    c, window = gui
    before = c.project.to_dict()
    open_bulk(c, window)
    click(window, "bulk-check-scenario")
    click(window, "bulk-check-sensor")
    choose(window, "bulkStatus", 3)  # Completed; index zero means no change.
    choose(window, "bulkPriority", 5)  # Lowest.
    assert c.project.to_dict() == before and not c.canUndo
    click(window, "applyBulkButton")
    wait_until(lambda: c.project.tasks["sensor"].status == "completed")
    assert c.project.tasks["scenario"].progress == 100
    assert c.project.tasks["sensor"].priority == "lowest"
    assert c.property("checkedCount") == 2 and c.property("bulkMode")
    undo(window)
    wait_until(lambda: c.project.to_dict() == before)
    assert not c.canUndo


def test_real_bulk_draft_cancel_does_not_commit(gui):
    c, window = gui
    before = c.project.to_dict()
    open_bulk(c, window)
    click(window, "bulk-check-sensor")
    choose(window, "bulkStatus", 4)  # Closed, but Apply is not clicked.
    QTest.keyClick(window, Qt.Key.Key_Escape)
    wait_until(lambda: not c.property("bulkMode"))
    assert c.project.to_dict() == before and not c.dirty


def test_bar_drag_in_bulk_mode_toggles_check_not_dates(gui):
    c, window = gui
    before = c.project.to_dict()
    open_bulk(c, window)
    click(window, "bulk-check-scenario")
    click(window, "bulk-check-sensor")
    start = point(item(window, "taskbar-scenario"))
    drag(window, start, start + QPoint(70, 0))
    wait_until(lambda: c.property("checkedCount") == 1)
    assert c.property("checkedIds") == ["sensor"]
    assert c.project.to_dict() == before and not c.canUndo


def test_bulk_delete_confirmation_preserves_unchecked_child(gui):
    c, window = gui
    before = c.project.to_dict()
    open_bulk(c, window)
    click(window, "bulk-check-planning")
    click(window, "bulk-check-scenario")
    assert c.property("bulkDeleteCount") == 4
    click(window, "deleteBulkButton")
    dialog = window.findChild(QObject, "deleteDialog")
    assert dialog is not None
    wait_until(lambda: dialog.property("opened"))
    assert "4" in dialog.property("title")
    accept = visible_button(window, {"OK", "ОК"})
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(accept))
    wait_until(lambda: "sensor" not in c.project.tasks)
    assert "scenario" in c.project.tasks and "planning" in c.project.tasks
    assert c.property("bulkDeleteCount") == 0
    undo(window)
    wait_until(lambda: c.project.to_dict() == before)


def test_real_inspector_status_and_manual_progress_stay_synchronized(gui):
    c, window = gui
    c.select("sensor")
    start = point(item(window, "taskbar-sensor"))
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    QTest.mouseDClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    QTest.mouseRelease(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    drawer = window.findChild(QObject, "taskInspector")
    assert drawer is not None
    wait_until(lambda: drawer.property("opened"))
    choose(window, "inspectorStatus", 3)  # Closed, no placeholder in the single-task editor.
    wait_until(lambda: c.project.tasks["sensor"].status == "closed")
    assert c.project.tasks["sensor"].progress == 100
    choose(window, "inspectorStatus", 1)
    wait_until(lambda: c.project.tasks["sensor"].progress == 50)
    assert c.project.tasks["sensor"].status == "in_progress"
    progress = item(window, "inspectorProgressValue")
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(progress))
    QTest.keyClick(window, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(window, Qt.Key.Key_2)
    QTest.keyClick(window, Qt.Key.Key_5)
    QTest.keyClick(window, Qt.Key.Key_Tab)
    wait_until(lambda: c.project.tasks["sensor"].progress == 25)
    assert c.project.tasks["sensor"].status == "in_progress"
