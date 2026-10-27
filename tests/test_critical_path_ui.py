from copy import deepcopy

import pytest
from conftest import wait_until
from dialog_helpers import click_native, native_dialog, required_widget
from PySide6.QtCore import QMetaObject, QObject, QPoint, Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QCheckBox, QComboBox
from test_critical_path import BASE, plan
from test_ui import drag, item, point

from gantt_desktop.domain import Task


def diamond():
    return plan([("a", 0, 480), ("b", 480, 480), ("c", 480, 240), ("d", 960, 480)],
                [("a", "b", "FS", 0), ("a", "c", "FS", 0), ("b", "d", "FS", 0), ("c", "d", "FS", 0)])


def click(window, name):
    target = item(window, name)
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(target))


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("width", [1000, 1366, 1920])
def test_real_critical_toggle_restores_task_colors_without_history_or_dirty_state(gui, dark, width):
    c, window = gui
    c.load_project(diamond())
    assert c.theme is not None
    c.theme.setDark(dark)
    window.resize(width, 960)
    before = c.project.to_dict()
    button = item(window, "criticalPathButton")
    assert 0 <= point(button).x() < width
    click(window, "criticalPathButton")
    wait_until(lambda: bool(c.criticalPath))
    assert button.property("checked")
    assert item(window, "taskbar-a").property("displayColor") == QColor("#c93b3b")
    assert item(window, "taskbar-c").property("displayColor") == QColor(c.project.tasks["c"].color)
    assert c.record("c")["totalFloat"] == 240
    assert [link["critical"] for link in c.links] == [True, False, True, False]
    info = item(window, "criticalPathInfo")
    assert info.isVisible() and info.width() <= width - 260
    assert "всему" in info.property("text")
    click(window, "criticalPathButton")
    wait_until(lambda: not c.criticalPath)
    assert item(window, "taskbar-a").property("displayColor") == QColor(c.project.tasks["a"].color)
    assert c.project.to_dict() == before and not c.canUndo and not c.dirty


def test_schedule_edits_undo_and_redo_recompute_the_actual_bottleneck(gui):
    c, window = gui
    c.load_project(diamond())
    click(window, "criticalPathButton")
    assert c.record("c")["totalFloat"] == 240
    assert c.resizeTask("c", "end", 1)
    assert c.record("c")["totalFloat"] == 0 and c.record("b")["totalFloat"] > 0
    c.undo()
    assert c.record("c")["totalFloat"] == 240 and c.record("b")["totalFloat"] == 0
    c.redo()
    assert c.record("c")["totalFloat"] == 0


def test_filter_collapse_and_selection_never_redefine_the_project_critical_path(gui):
    c, _window = gui
    p = diamond()
    p.tasks["g"] = Task("g", "Group", BASE, 0, kind="group")
    for key in "abc":
        p.tasks[key].parent = "g"
    c.load_project(p)
    c.setCriticalPath(True)
    before = {key: c.record(key)["totalFloat"] for key in p.tasks}
    c.toggleGroup("g")
    assert c.record("g")["critical"]
    c.search("c")
    c.select("c")
    assert c.record("c")["totalFloat"] == 240
    assert {key: c.record(key)["totalFloat"] for key in p.tasks} == before
    assert not c.dirty and not c.canUndo


def test_inspector_reports_working_float_and_joint_group_criticality(gui):
    c, window = gui
    p = plan([("a", 0, 1), ("b", 0, 1), ("z", 0, 3)])
    p.tasks["g"] = Task("g", "Group", BASE, 0, kind="group")
    p.tasks["a"].parent = p.tasks["b"].parent = "g"
    from gantt_desktop.domain import Dependency
    p.dependencies = [Dependency("gz", "g", "z", "SS")]
    c.load_project(p)
    c.setCriticalPath(True)
    c.select("g")
    inspector = window.findChild(QObject, "taskInspector")
    assert inspector is not None and QMetaObject.invokeMethod(inspector, "open")
    wait_until(lambda: inspector.property("opened"))
    label = item(window, "inspectorTotalFloat")
    assert label.isVisible() and "Критическая группа" in label.property("text")
    c.select("a")
    assert "Критическая" not in label.property("text") and "рабочих" in label.property("text")
    assert c.record("a")["totalFloat"] == 2


def test_budget_failure_shows_persistent_error_and_never_partial_red_bars(gui, monkeypatch):
    c, window = gui
    c.load_project(diamond())
    before = c.project.to_dict()
    monkeypatch.setattr("gantt_desktop.critical_path._WORK_LIMIT", 1)
    click(window, "criticalPathButton")
    wait_until(lambda: bool(c.criticalPathError))
    assert "не рассчитан" in item(window, "criticalPathInfo").property("text")
    assert all(not c.record(key)["critical"] and c.record(key)["totalFloat"] is None for key in c.project.tasks)
    assert all(not link["critical"] for link in c.links)
    assert c.project.to_dict() == before and not c.dirty
    monkeypatch.setattr("gantt_desktop.critical_path._WORK_LIMIT", 100_000)
    c.refresh()
    assert not c.criticalPathError and c.record("a")["critical"]


def test_project_load_recomputes_enabled_analysis_and_empty_projects_are_safe(gui):
    c, _window = gui
    c.load_project(diamond())
    c.setCriticalPath(True)
    c.load_project(plan([("only", 0, 480)]))
    assert c.criticalPath and c.record("only")["totalFloat"] == 0
    from gantt_desktop.domain import Project
    c.load_project(Project())
    assert "Нет элементов" in c.criticalPathInfo and not c.criticalPathError
    assert not c.dirty and not c.canUndo


def test_analysis_is_once_per_refresh_not_recomputed_for_every_row_or_link(gui, monkeypatch):
    c, _window = gui
    c.load_project(diamond())
    from gantt_desktop.critical_path import analyze
    calls = []
    def count(project):
        calls.append(project)
        return analyze(project)
    monkeypatch.setattr("gantt_desktop.controller.analyze", count)
    c.setCriticalPath(True)
    for _ in range(10):
        for key in c.project.tasks:
            c.record(key)
        assert c.links
    assert len(calls) == 1


def test_export_critical_checkbox_inherits_view_then_is_independent_and_format_aware(gui):
    c, window = gui
    c.load_project(diamond())
    click(window, "criticalPathButton")
    before = deepcopy(c.project.to_dict())
    click(window, "exportButton")
    dialog = native_dialog("exportDialog")
    wait_until(dialog.isVisible)
    critical = required_widget("exportCritical")
    assert isinstance(critical, QCheckBox) and critical.isChecked()
    assert click_native("exportCritical")
    assert c.criticalPath
    format_ = required_widget("exportFormat")
    assert isinstance(format_, QComboBox)
    format_.setCurrentIndex(format_.findData("xml"))
    wait_until(lambda: not critical.isEnabled())
    assert c.project.to_dict() == before and not c.dirty
    assert click_native("closeExport")


def test_real_resize_with_critical_overlay_recomputes_and_undo_keeps_view_enabled(gui):
    c, window = gui
    c.load_project(diamond())
    click(window, "criticalPathButton")
    before = c.project.to_dict()
    handle = item(window, "resize-end-c")
    start = point(handle)
    drag(window, start, start+QPoint(10, 0))
    wait_until(lambda: c.record("c")["critical"])
    assert c.criticalPath and c.canUndo
    c.undo()
    assert c.project.to_dict() == before and c.criticalPath and c.record("c")["totalFloat"] == 240


def test_analysis_flag_and_results_are_not_serialized_or_a_schema_change(qapp, tmp_path):
    from gantt_desktop.controller import Controller
    c = Controller(diamond())
    c.setCriticalPath(True)
    before = c.project.to_dict()
    assert before["version"] == 9
    assert "critical" not in before and all("critical" not in row for row in before["tasks"])
    path = tmp_path / "critical.json"
    assert c.save_path(path)
    reopened = Controller()
    assert reopened.load_path(path)
    assert reopened.project.to_dict() == before and not reopened.criticalPath
