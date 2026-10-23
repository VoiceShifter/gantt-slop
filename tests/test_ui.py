from datetime import timedelta

from conftest import wait_until
from PySide6.QtCore import QObject, QPoint, QPointF, Qt
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest


def item(window, name):
    result = window.findChild(QQuickItem, name)
    if result is not None:
        return result
    # Repeater delegates have visual parents outside the QObject ownership tree.
    pending = [window.contentItem()]
    while pending:
        candidate = pending.pop()
        if candidate.objectName() == name:
            return candidate
        pending.extend(candidate.childItems())
    raise AssertionError(f"Missing native item {name}")


def point(target, x=0.5, y=0.5):
    return target.mapToScene(QPointF(target.width() * x, target.height() * y)).toPoint()


def drag(window, start, end, release=True):
    QTest.mouseMove(window, start)
    QTest.mousePress(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    for step in range(1, 9):
        pos = start + (end - start) * (step / 8)
        QTest.mouseMove(window, pos)
    if release:
        QTest.mouseRelease(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)


def undo(window):
    button = item(window, "undoButton")
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(button))


def test_real_body_drag_undo_redo(gui):
    c, window = gui
    before = c.project.to_dict()
    original = c.project.tasks["sensor"].start
    bar = item(window, "taskbar-sensor")
    start = point(bar)
    drag(window, start, start + QPoint(70, 0))
    wait_until(lambda: c.project.tasks["sensor"].start == original + timedelta(days=7))
    assert c.project.tasks["configure"].start == original.replace(year=2026, month=2, day=5)
    after = c.project.to_dict()
    undo(window)
    wait_until(lambda: c.project.to_dict() == before)
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(item(window, "redoButton")))
    wait_until(lambda: c.project.to_dict() == after)


def test_rapid_select_then_drag_does_not_open_inspector(gui):
    c, window = gui
    start = point(item(window, "taskbar-sensor"))
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    drag(window, start, start + QPoint(70, 0))
    wait_until(lambda: c.canUndo)
    inspector = window.findChild(QObject, "taskInspector")
    assert inspector is not None and not inspector.property("visible")


def test_linked_body_drag_is_a_visible_noop(gui):
    c, window = gui
    messages = []
    c.toast.connect(messages.append)
    before = c.project.to_dict()
    start = point(item(window, "taskbar-configure"))
    drag(window, start, start + QPoint(50, 0))
    wait_until(lambda: bool(messages))
    assert "предшествен" in messages[-1]
    assert c.project.to_dict() == before and not c.canUndo


def test_real_resize_preserves_start_and_effort(gui):
    c, window = gui
    before = c.project.to_dict()
    original = c.project.tasks["sensor"].start
    end_handle = item(window, "resize-end-sensor")
    start = point(end_handle)
    drag(window, start, start + QPoint(20, 0))
    wait_until(lambda: c.project.tasks["sensor"].duration == 40 * 60)
    assert c.project.tasks["sensor"].start == original
    assert c.project.tasks["sensor"].effort == 8
    undo(window)
    wait_until(lambda: c.project.to_dict() == before)


def test_real_group_drag_moves_children_and_dependents(gui):
    c, window = gui
    before = c.project.to_dict()
    last_start = c.project.tasks["configure"].start
    start = point(item(window, "taskbar-planning"), 0.5, 0.9)
    drag(window, start, start + QPoint(70, 0))
    wait_until(lambda: c.project.tasks["configure"].start == last_start + timedelta(days=7))
    assert c.project.tasks["scenario"].start.day == 8
    undo(window)
    wait_until(lambda: c.project.to_dict() == before)


def test_escape_cancels_preview_before_release(gui):
    c, window = gui
    before = c.project.to_dict()
    start = point(item(window, "taskbar-sensor"))
    end = start + QPoint(70, 0)
    drag(window, start, end, release=False)
    assert c.project.to_dict() == before
    QTest.keyClick(window, Qt.Key.Key_Escape)
    QTest.mouseRelease(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)
    assert c.project.to_dict() == before and not c.canUndo


def test_real_progress_handle_and_undo(gui):
    c, window = gui
    bar = item(window, "taskbar-scenario")
    QTest.mouseMove(window, point(bar))
    handle = item(window, "progress-scenario")
    wait_until(lambda: handle.isVisible())
    start = point(handle)
    end = bar.mapToScene(QPointF(bar.width() * 0.75, 23)).toPoint()
    drag(window, start, end)
    wait_until(lambda: c.project.tasks["scenario"].progress >= 70)
    assert c.project.tasks["scenario"].progress <= 80
    undo(window)
    wait_until(lambda: c.project.tasks["scenario"].progress == 0)


def test_real_dependency_handle_drag(gui):
    c, window = gui
    before = c.project.to_dict()
    source = item(window, "taskbar-scenario")
    QTest.mouseMove(window, point(source))
    handle = item(window, "link-F-scenario")
    wait_until(lambda: handle.isVisible())
    target = item(window, "taskbar-sensor")
    start = point(handle)
    end = target.mapToScene(QPointF(0, target.height() / 2)).toPoint()
    drag(window, start, end)
    wait_until(lambda: len(c.project.dependencies) == 16)
    link = c.project.dependencies[-1]
    assert (link.source, link.target, link.kind) == ("scenario", "sensor", "FS")
    undo(window)
    wait_until(lambda: c.project.to_dict() == before)


def test_create_task_and_edit_native_inspector(gui):
    c, window = gui
    count = c.taskCount
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(item(window, "addTaskButton")))
    wait_until(lambda: c.taskCount == count + 1)
    inspector = window.findChild(QObject, "taskInspector")
    assert inspector is not None
    wait_until(lambda: inspector.property("opened"))
    target = item(window, "inspectorName")
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(target))
    wait_until(lambda: target.property("activeFocus"))
    QTest.keyClick(window, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    for character in "native edited task":
        QTest.keyClick(window, Qt.Key(ord(character.upper())))
    QTest.keyClick(window, Qt.Key.Key_Tab)
    wait_until(lambda: c.project.tasks[c.selectedId].name == "native edited task")


def test_real_zoom_and_resizable_split(gui):
    _c, window = gui
    view = item(window, "ganttView")
    zoom = item(window, "zoomSlider")
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(zoom, 0.2, 0.5))
    wait_until(lambda: view.property("pixelsPerDay") > 10)
    assert view.property("scrollX") >= 0
    previous_width = view.property("gridWidth")
    divider = item(window, "gridDivider")
    start = point(divider, 0.5, 0.15)
    drag(window, start, start - QPoint(100, 0))
    wait_until(lambda: abs(view.property("gridWidth") - previous_width + 100) < 2)
