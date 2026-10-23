from conftest import wait_until
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from test_ui import drag, item, point, undo


def _start(window, end="F"):
    QTest.mouseMove(window, point(item(window, "taskbar-scenario")))
    handle = item(window, f"link-{end}-scenario")
    wait_until(handle.isVisible)
    return point(handle)


def test_dependency_drag_scrolls_horizontally_then_connects(gui):
    c, window = gui
    before = c.project.to_dict()
    view = item(window, "ganttView")
    start = _start(window)
    drag(window, start, QPoint(window.width() - 8, start.y()), release=False)
    wait_until(lambda: view.property("scrollX") >= 48)
    end = point(item(window, "link-S-configure"))
    QTest.mouseMove(window, end)
    QTest.mouseRelease(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)
    wait_until(lambda: len(c.project.dependencies) == len(before["dependencies"]) + 1)
    link = c.project.dependencies[-1]
    assert (link.source, link.target, link.kind) == ("scenario", "configure", "FS")
    undo(window)
    wait_until(lambda: c.project.to_dict() == before)


def test_dependency_drag_scrolls_vertically_to_a_hidden_task(gui):
    c, window = gui
    window.resize(1920, 650)
    body = item(window, "bodyFlick")
    wait_until(lambda: body.height() < body.property("contentHeight"))
    before = c.project.to_dict()
    start = _start(window)
    bottom = body.mapToScene(QPointF(0, body.height())).toPoint().y()
    drag(window, start, QPoint(start.x() + 80, bottom - 8), release=False)
    wait_until(lambda: body.property("contentY") >= body.property("contentHeight") - body.height() - 1)
    end = point(item(window, "link-S-configure"))
    assert end.y() < bottom
    QTest.mouseMove(window, end)
    QTest.mouseRelease(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)
    wait_until(lambda: len(c.project.dependencies) == len(before["dependencies"]) + 1)
    assert c.project.dependencies[-1].target == "configure"
    undo(window)
    wait_until(lambda: c.project.to_dict() == before)


def test_dropping_on_the_table_after_panning_never_creates_a_link(gui):
    c, window = gui
    before = c.project.to_dict()
    view = item(window, "ganttView")
    start = _start(window)
    drag(window, start, QPoint(window.width() - 8, start.y()), release=False)
    wait_until(lambda: view.property("scrollX") >= 624)
    end = QPoint(600, point(item(window, "taskbar-controller")).y())
    QTest.mouseMove(window, end)
    QTest.mouseRelease(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)
    assert c.project.to_dict() == before and not c.canUndo
    assert not view.property("linkSource")


def test_click_pair_links_with_a_live_pointer_preview(gui):
    c, window = gui
    before = c.project.to_dict()
    start = _start(window, "S")
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    view = item(window, "ganttView")
    assert view.property("linkSource") == "scenario" and not view.property("linkDragging")
    target = item(window, "link-F-components")
    end = point(target)
    QTest.mouseMove(window, end)
    expected = target.mapToItem(view.property("sceneItem"), QPointF(target.width() / 2, target.height() / 2))
    wait_until(lambda: abs(view.property("linkMouseX") - expected.x()) < 2)
    assert c.project.to_dict() == before
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)
    wait_until(lambda: len(c.project.dependencies) == len(before["dependencies"]) + 1)
    link = c.project.dependencies[-1]
    assert (link.source, link.target, link.kind) == ("scenario", "components", "SF")
    undo(window)
    wait_until(lambda: c.project.to_dict() == before)


def test_zoom_cancels_a_pending_click_pair(gui):
    c, window = gui
    before = c.project.to_dict()
    start = _start(window)
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    zoom = item(window, "zoomSlider")
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(zoom, 0.2, 0.5))
    wait_until(lambda: not item(window, "ganttView").property("linkSource"))
    assert c.project.to_dict() == before and not c.canUndo
