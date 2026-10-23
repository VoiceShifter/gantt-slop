from conftest import wait_until
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from test_ui import drag, item, point, undo

from gantt_desktop.domain import Task
from gantt_desktop.sample import sample_project


def test_real_sibling_row_drag_updates_outline_not_schedule(gui):
    c, window = gui
    before = c.project.to_dict()
    source = point(item(window, "row-grip-scenario"))
    target_row = item(window, "task-row-sensor")
    target = target_row.mapToScene(QPointF(16, target_row.height() - 2)).toPoint()
    drag(window, source, target)
    wait_until(lambda: c.project.children("planning")[0].id == "sensor")
    assert c.project.tasks["scenario"].start == sample_project().tasks["scenario"].start
    assert next(r for r in c._rows.records if r["taskId"] == "scenario")["outline"] == "1.2"
    undo(window)
    wait_until(lambda: c.project.to_dict() == before)


def test_real_cross_group_row_drop_inserts_first_and_undo(gui):
    c, window = gui
    before = c.project.to_dict()
    source = point(item(window, "row-grip-scenario"))
    target = item(window, "task-row-preparation").mapToScene(QPointF(170, 15)).toPoint()
    drag(window, source, target)
    wait_until(lambda: c.project.tasks["scenario"].parent == "preparation")
    assert c.project.children("preparation")[0].id == "scenario"
    assert c.record("planning")["effortHours"] == 48
    assert c.record("preparation")["effortHours"] == 72
    assert next(r for r in c._rows.records if r["taskId"] == "scenario")["outline"] == "2.1"
    undo(window)
    wait_until(lambda: c.project.to_dict() == before)


def test_cycle_row_drop_is_rejected_without_history(gui):
    c, window = gui
    before = c.project.to_dict()
    messages = []
    c.toast.connect(messages.append)
    source = point(item(window, "row-grip-planning"))
    target = item(window, "task-row-sensor").mapToScene(QPointF(170, 15)).toPoint()
    drag(window, source, target)
    wait_until(lambda: bool(messages))
    assert "Нельзя" in messages[-1]
    assert c.project.to_dict() == before and not c.canUndo


def test_escape_cancels_row_drop_preview(gui):
    c, window = gui
    before = c.project.to_dict()
    source = point(item(window, "row-grip-scenario"))
    target = item(window, "task-row-preparation").mapToScene(QPointF(170, 15)).toPoint()
    drag(window, source, target, release=False)
    assert c.project.to_dict() == before
    assert item(window, "rowDragGhost").isVisible()
    QTest.keyClick(window, Qt.Key.Key_Escape)
    QTest.mouseRelease(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, target)
    assert c.project.to_dict() == before and not c.canUndo


def test_small_grip_motion_is_not_an_edit(gui):
    c, window = gui
    before = c.project.to_dict()
    source = point(item(window, "row-grip-scenario"))
    drag(window, source, source + QPoint(0, 2))
    assert c.project.to_dict() == before and not c.canUndo


def test_row_drag_autoscroll_and_cancel(gui):
    c, window = gui
    project = sample_project()
    for i in range(25):
        project.tasks[f"extra-{i}"] = Task(f"extra-{i}", f"Extra {i}", project.tasks["sensor"].start, parent="planning")
    c.load_project(project)
    before = c.project.to_dict()
    body = item(window, "bodyFlick")
    source = point(item(window, "row-grip-scenario"))
    target = body.mapToScene(QPointF(170, body.height() - 5)).toPoint()
    drag(window, source, target, release=False)
    wait_until(lambda: body.property("contentY") >= 12)
    QTest.keyClick(window, Qt.Key.Key_Escape)
    QTest.mouseRelease(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, target)
    assert c.project.to_dict() == before and not c.canUndo
