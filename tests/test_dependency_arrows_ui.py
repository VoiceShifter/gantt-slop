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


def test_fs_arrow_targeting_milestone_default_enters_left(gui):
    _c, window = gui
    canvas = item(window, "chartCanvas")

    def paths():
        value = canvas.property("paths")
        return value.toVariant() if hasattr(value, "toVariant") else value

    # By default (settings off), link-5 enters from the left vertex at (mx - 14, ty).
    wait_until(lambda: any(p["id"] == "link-5" for p in paths()))
    path = next(p for p in paths() if p["id"] == "link-5")
    # Enters left vertex at row center ty (not top vertex at ty - 14)
    end_point = path["points"][-1]
    # In sample_project, components row center is at ty = 345
    assert end_point[1] == 345.0
    # Left vertex is shifted 14px left of milestone center (445 - 14 = 431)
    assert end_point[0] == 431.0


def test_fs_arrow_targeting_milestone_drops_vertically_into_top_vertex(gui):
    c, window = gui
    canvas = item(window, "chartCanvas")

    def paths():
        value = canvas.property("paths")
        return value.toVariant() if hasattr(value, "toVariant") else value

    c.set_milestone_enter_top(True)
    wait_until(lambda: any(p["id"] == "link-5" and len(p["points"]) == 3 for p in paths()))
    path = next(p for p in paths() if p["id"] == "link-5")
    assert len(path["points"]) == 3
    # Horizontal line from source to mx
    assert abs(path["points"][0][1] - path["points"][1][1]) < 0.001
    assert path["points"][1][0] > path["points"][0][0]
    # Vertical drop directly into top vertex (ty - 14 = 345 - 14 = 331)
    assert abs(path["points"][1][0] - path["points"][2][0]) < 0.001
    assert path["points"][2][1] == 331.0


def test_fs_arrow_milestone_multi_link_deconfliction(gui):
    c, window = gui
    canvas = item(window, "chartCanvas")

    def paths():
        value = canvas.property("paths")
        return value.toVariant() if hasattr(value, "toVariant") else value

    c.set_milestone_enter_top(True)
    # Add an earlier link to components (router is on row 5, supplier-control on row 8, components on row 9)
    from gantt_desktop.domain import Dependency
    c.project.dependencies.append(Dependency("link-router-comp", "router", "components", "FS", 0))
    c.viewChanged.emit()

    wait_until(lambda: any(p["id"] == "link-router-comp" for p in paths()))
    p_router = next(p for p in paths() if p["id"] == "link-router-comp")
    p_supplier = next(p for p in paths() if p["id"] == "link-5")

    # The predecessor further above (router) enters from the top vertex (drops into top vertex at y=331)
    assert len(p_router["points"]) == 3
    assert abs(p_router["points"][1][0] - p_router["points"][2][0]) < 0.001
    assert p_router["points"][2][1] == 331.0

    # The closest predecessor (supplier-control) enters from the left vertex (at y=345, x=431)
    assert p_supplier["points"][-1] == [431.0, 345.0]
    # They do NOT merge into the same path!
    assert p_router["points"][-1] != p_supplier["points"][-1]


def test_fs_arrow_exiting_milestone_from_bottom_vertex(gui):
    c, window = gui
    canvas = item(window, "chartCanvas")

    def paths():
        value = canvas.property("paths")
        return value.toVariant() if hasattr(value, "toVariant") else value

    # In sample_project, link-6 connects milestone components (row 9, sy=345, smx=445) to prototype (row 10).
    c.set_milestone_exit_bottom(True)
    wait_until(lambda: any(p["id"] == "link-6" and p["points"][0][1] == 359.0 for p in paths()))
    path = next(p for p in paths() if p["id"] == "link-6")
    # link-6 exits from bottom vertex of components (smx, sy + 14 = 445, 345 + 14 = 359):
    assert path["points"][0] == [445.0, 359.0]
    # First step drops straight vertically down from bottom vertex:
    assert path["points"][1][0] == 445.0
    assert path["points"][1][1] > 359.0



