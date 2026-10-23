from conftest import wait_until
from PySide6.QtCore import QObject, QPoint, Qt
from PySide6.QtTest import QTest
from test_ui import drag, item, point


def test_genuine_double_click_opens_task_properties(gui):
    c, window = gui
    target = point(item(window, "taskbar-sensor"))
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, target)
    QTest.mouseDClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, target)
    QTest.mouseRelease(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, target)
    inspector = window.findChild(QObject, "taskInspector")
    assert inspector is not None
    wait_until(lambda: inspector.property("opened"))
    assert c.selectedId == "sensor"
    assert item(window, "inspectorEnd").property("text") == c.record("sensor")["end"]
    assert not c.canUndo


def test_empty_chart_panning_never_edits_schedule(gui):
    c, window = gui
    before = c.project.to_dict()
    view = item(window, "ganttView")
    start = QPoint(1800, 500)
    drag(window, start, start - QPoint(100, 0))
    wait_until(lambda: view.property("scrollX") >= 90)
    assert c.project.to_dict() == before and not c.canUndo


def test_native_search_clear_restores_hierarchy(gui):
    c, window = gui
    count = c.property("rowCount")
    search = item(window, "taskSearch")
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(search))
    for character in "nomatch":
        QTest.keyClick(window, Qt.Key(ord(character.upper())))
    wait_until(lambda: c.property("rowCount") == 1)
    QTest.keyClick(window, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(window, Qt.Key.Key_Backspace)
    wait_until(lambda: c.property("rowCount") == count)
