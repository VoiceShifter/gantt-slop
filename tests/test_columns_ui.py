import pytest
from conftest import wait_until
from PySide6.QtCore import QMetaObject, QPoint, QPointF, Qt
from PySide6.QtGui import QWindow
from PySide6.QtTest import QTest
from test_ui import drag, item, point

DEFAULT_KEYS = ["name", "assignee", "effort", "cost"]
OPTIONAL = {
    "start": "showStart", "end": "showEnd", "duration": "showDuration",
    "progress": "showProgress", "status": "showStatus", "priority": "showPriority",
}


def widths(window, keys=DEFAULT_KEYS):
    return {key: item(window, "column-header-" + key).width() for key in keys}


def resize_column(window, key, delta, release=True):
    start = point(item(window, "column-header-" + key), 1, 0.5)
    end = start + QPoint(delta, 0)
    drag(window, start, end, release=release)
    return end


def row_index(c, kind, parent=None):
    return next(i for i, row in enumerate(c._rows.records)
                if row["rowKind"] == kind and (parent is None or row.get("parentId") == parent))


def assert_add_row_contained(c, window):
    index = row_index(c, "add", "planning")
    cell = item(window, "add-cell-" + str(index))
    actions = item(window, "add-actions-" + str(index))
    header = item(window, "column-header-name")
    assert cell.clip()
    assert cell.width() == pytest.approx(header.width())
    assert actions.width() <= cell.width() - 8
    assert actions.x() == pytest.approx((cell.width() - actions.width()) / 2, abs=1)
    left = header.mapToScene(QPointF()).x()
    right = left + header.width()
    for prefix in ("inline-add-task-", "inline-add-milestone-"):
        button = item(window, prefix + str(index))
        assert button.mapToScene(QPointF()).x() >= left
        assert button.mapToScene(QPointF(button.width(), 0)).x() <= right


@pytest.mark.parametrize("width", [1000, 1366, 1920])
@pytest.mark.parametrize("dark", [False, True])
def test_add_actions_are_centered_inside_task_column_at_window_sizes(gui, width, dark):
    c, window = gui
    assert c.theme is not None
    c.theme.setDark(dark)
    before = c.project.to_dict()
    window.resize(width, 768)
    view = item(window, "ganttView")
    wait_until(lambda: view.width() == width - 260)
    assert_add_row_contained(c, window)
    assert c.project.to_dict() == before and not c.canUndo and not c.dirty


@pytest.mark.parametrize("key", [*DEFAULT_KEYS, *OPTIONAL])
def test_each_header_boundary_resizes_only_its_column_and_workload_split(gui, key):
    c, window = gui
    view = item(window, "ganttView")
    keys = DEFAULT_KEYS + ([key] if key in OPTIONAL else [])
    if key in OPTIONAL:
        view.setProperty(OPTIONAL[key], True)
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(item(window, "workloadToggle")))
    before = c.project.to_dict()
    original = widths(window, keys)
    grid = view.property("gridWidth")
    resize_column(window, key, 80)
    wait_until(lambda: abs(item(window, "column-header-" + key).width() - original[key] - 80) < 1)
    expected = dict(original, **{key: original[key] + 80})
    assert widths(window, keys) == pytest.approx(expected)
    assert view.property("gridWidth") == pytest.approx(grid + 80)
    assert item(window, "resourceWorkload").property("gridWidth") == pytest.approx(grid + 80)
    assert_add_row_contained(c, window)
    assert c.project.to_dict() == before and not c.canUndo and not c.dirty


@pytest.mark.parametrize(("key", "minimum"), [("name", 250), ("assignee", 64)])
def test_columns_stop_at_readable_minimum_without_text_leaking(gui, key, minimum):
    c, window = gui
    before = c.project.to_dict()
    resize_column(window, key, -1000)
    wait_until(lambda: item(window, "column-header-" + key).width() == minimum)
    assert_add_row_contained(c, window)
    sensor_row = next(i for i, row in enumerate(c._rows.records) if row.get("taskId") == "sensor")
    assert item(window, "column-cell-assignee-" + str(sensor_row)).clip()
    assert item(window, "task-name-sensor").parentItem().clip()
    assert c.project.to_dict() == before and not c.canUndo


def test_escape_restores_column_widths_viewport_and_scroll_before_release(gui):
    c, window = gui
    view = item(window, "ganttView")
    original = widths(window)
    grid = view.property("gridWidth")
    before = c.project.to_dict()
    end = resize_column(window, "name", 100, release=False)
    assert widths(window)["name"] == pytest.approx(original["name"] + 100)
    QTest.keyClick(window, Qt.Key.Key_Escape)
    QTest.mouseRelease(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)
    assert widths(window) == pytest.approx(original)
    assert view.property("gridWidth") == pytest.approx(grid)
    assert view.property("gridScroll") == 0
    assert c.project.to_dict() == before and not c.canUndo


def test_scrolled_resize_keeps_headers_cells_and_scroll_aligned_and_hidden_widths(gui):
    c, window = gui
    view = item(window, "ganttView")
    for prop in OPTIONAL.values():
        view.setProperty(prop, True)
    view.setProperty("gridScroll", 250)
    resize_column(window, "duration", 80)
    assert item(window, "column-header-duration").width() == pytest.approx(180)
    assert view.property("gridScroll") == pytest.approx(250)
    resize_column(window, "duration", -50)
    assert item(window, "column-header-duration").width() == pytest.approx(130)
    assert view.property("gridScroll") == pytest.approx(250)
    sensor_row = next(i for i, row in enumerate(c._rows.records) if row.get("taskId") == "sensor")
    header = item(window, "column-header-duration")
    cell = item(window, "column-cell-duration-" + str(sensor_row))
    assert header.mapToScene(QPointF()).x() == pytest.approx(cell.mapToScene(QPointF()).x())
    for prop in ["showAssignee", "showEffort", "showCost", *OPTIONAL.values()]:
        view.setProperty(prop, False)
    wait_until(lambda: view.property("gridScroll") == 0)
    view.setProperty("showDuration", True)
    assert item(window, "column-header-duration").width() == pytest.approx(130)
    assert not c.canUndo and not c.dirty


def test_reset_table_widths_restores_defaults_without_project_history(gui):
    c, window = gui
    view = item(window, "ganttView")
    before = c.project.to_dict()
    resize_column(window, "name", 120)
    resize_column(window, "assignee", 70)
    assert QMetaObject.invokeMethod(view, "resetColumnWidths")
    assert widths(window) == pytest.approx({"name": 370, "assignee": 100, "effort": 100, "cost": 100})
    assert view.property("gridWidth") == 716 and view.property("gridScroll") == 0
    assert c.project.to_dict() == before and not c.canUndo and not c.dirty


def test_custom_widths_survive_small_window_and_fullscreen_layout(gui):
    c, window = gui
    view = item(window, "ganttView")
    before = c.project.to_dict()
    resize_column(window, "name", 300)
    original = widths(window)
    window.resize(1000, 768)
    wait_until(lambda: view.width() == 740)
    wait_until(lambda: view.property("gridWidth") <= view.width() - 180)
    assert widths(window) == pytest.approx(original)
    assert view.property("gridContentWidth") > view.property("gridWidth")
    window.showFullScreen()
    wait_until(lambda: window.visibility() == QWindow.Visibility.FullScreen)
    wait_until(lambda: window.width() == window.screen().geometry().width())
    wait_until(lambda: view.width() == window.width() - 260)
    wait_until(lambda: view.property("gridWidth") <= max(180, view.width() - 180))
    assert widths(window) == pytest.approx(original)
    assert_add_row_contained(c, window)
    window.showNormal()
    assert c.project.to_dict() == before and not c.canUndo


@pytest.mark.parametrize(("prefix", "milestone"), [("inline-add-task-", False), ("inline-add-milestone-", True)])
def test_centered_creation_buttons_still_create_in_the_correct_group(gui, prefix, milestone):
    c, window = gui
    view = item(window, "ganttView")
    resize_column(window, "name", -1000)
    index = row_index(c, "add", "planning")
    before = c.project.to_dict()
    count = c.taskCount
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(item(window, prefix + str(index))))
    wait_until(lambda: c.taskCount == count + 1)
    selected = c.property("selected")
    assert selected["parentId"] == "planning" and selected["milestone"] == milestone
    c.undo()
    assert c.project.to_dict() == before
    assert view.property("gridScroll") == 0


def test_clicking_boundary_without_drag_keeps_default_responsive_width(gui):
    c, window = gui
    view = item(window, "ganttView")
    window.resize(1000, 768)
    wait_until(lambda: view.width() == 740)
    resize_column(window, "name", 0)
    window.resize(1920, 960)
    wait_until(lambda: item(window, "column-header-name").width() == 370)
    assert view.property("gridWidth") == 716
    assert not c.canUndo and not c.dirty
