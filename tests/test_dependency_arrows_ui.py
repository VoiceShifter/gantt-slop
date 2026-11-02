import pytest
from conftest import wait_until
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest
from test_ui import drag, item, point, undo


@pytest.mark.parametrize("end", ["S", "F"])
def test_handles_survive_walking_across_the_gap(gui, end):
    c, window = gui
    bar = item(window, "taskbar-scenario")
    QTest.mouseMove(window, point(bar))
    handle = item(window, f"link-{end}-scenario")
    wait_until(handle.isVisible)
    xs = range(1, -12, -1) if end == "S" else range(int(bar.width()) - 1, int(bar.width()) + 12)
    for x in xs:
        QTest.mouseMove(window, bar.mapToScene(QPointF(x, 11)).toPoint())
        QTest.qWait(1)
        assert handle.isVisible(), f"Handle disappeared at x={x}"
    assert not c.canUndo


def test_releasing_in_empty_space_does_not_link_the_row(gui):
    c, window = gui
    before = c.project.to_dict()
    source = item(window, "taskbar-scenario")
    QTest.mouseMove(window, point(source))
    handle = item(window, "link-F-scenario")
    wait_until(handle.isVisible)
    target = item(window, "taskbar-sensor")
    end = target.mapToScene(QPointF(target.width() + 160, 11)).toPoint()
    drag(window, point(handle), end)
    assert c.project.to_dict() == before and not c.canUndo


@pytest.mark.parametrize("kind", ["FS", "SS", "FF", "SF"])
def test_drag_to_both_milestone_endpoints(gui, kind):
    c, window = gui
    before = c.project.to_dict()
    count = len(c.project.dependencies)
    QTest.mouseMove(window, point(item(window, "taskbar-scenario")))
    source = item(window, f"link-{kind[0]}-scenario")
    wait_until(source.isVisible)
    target = item(window, f"link-{kind[1]}-components")
    drag(window, point(source), point(target))
    wait_until(lambda: len(c.project.dependencies) == count + 1)
    link = c.project.dependencies[-1]
    assert (link.source, link.target, link.kind) == ("scenario", "components", kind)
    undo(window)
    wait_until(lambda: c.project.to_dict() == before)


def test_real_summary_to_summary_arrow(gui):
    c, window = gui
    before = c.project.to_dict()
    count = len(c.project.dependencies)
    QTest.mouseMove(window, point(item(window, "taskbar-planning")))
    source = item(window, "link-F-planning")
    wait_until(source.isVisible)
    target = item(window, "link-S-preparation")
    drag(window, point(source), point(target))
    wait_until(lambda: len(c.project.dependencies) == count + 1)
    link = c.project.dependencies[-1]
    assert (link.source, link.target, link.kind) == ("planning", "preparation", "FS")
    assert not c.record("preparation")["canMove"]
    undo(window)
    wait_until(lambda: c.project.to_dict() == before)


def test_escape_cancels_a_dependency_drag(gui):
    c, window = gui
    before = c.project.to_dict()
    QTest.mouseMove(window, point(item(window, "taskbar-scenario")))
    source = item(window, "link-F-scenario")
    wait_until(source.isVisible)
    end = point(item(window, "taskbar-sensor"), 0, 0.5)
    drag(window, point(source), end, release=False)
    QTest.keyClick(window, Qt.Key.Key_Escape)
    QTest.mouseRelease(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)
    assert not item(window, "ganttView").property("linkSource")
    assert c.project.to_dict() == before and not c.canUndo


def test_releasing_between_rows_does_not_create_an_arrow(gui):
    c, window = gui
    before = c.project.to_dict()
    QTest.mouseMove(window, point(item(window, "taskbar-scenario")))
    source = item(window, "link-F-scenario")
    wait_until(source.isVisible)
    target = item(window, "taskbar-sensor")
    end = target.mapToScene(QPointF(target.width() / 2, -3)).toPoint()
    drag(window, point(source), end)
    assert c.project.to_dict() == before and not c.canUndo


def test_fs_arrow_between_adjacent_blocks_has_three_straight_lines(gui):
    _c, window = gui
    canvas = item(window, "chartCanvas")

    def paths():
        value = canvas.property("paths")
        return value.toVariant() if hasattr(value, "toVariant") else value

    # In sample_project, link-4 connects supplier (end 40) to supplier-control (start 42).
    # Even when scale is small (gap < 24 px), it should use 3 straight lines (4 points).
    wait_until(lambda: any(p["id"] == "link-4" for p in paths()))
    path = next(p for p in paths() if p["id"] == "link-4")
    # 4 points = 3 straight lines (start -> middle -> middle,ty -> end)
    assert len(path["points"]) == 4
    # Line 1: horizontal out of source
    assert abs(path["points"][0][1] - path["points"][1][1]) < 0.001
    # Line 2: vertical straight down/up
    assert abs(path["points"][1][0] - path["points"][2][0]) < 0.001
    # Line 3: horizontal into target
    assert abs(path["points"][2][1] - path["points"][3][1]) < 0.001

