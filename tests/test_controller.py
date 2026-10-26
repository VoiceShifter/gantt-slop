import json

import pytest

from gantt_desktop.controller import Controller


def test_history_snapshots_whole_schedule(qapp):
    c = Controller()
    before = c.project.to_dict()
    assert c.moveTask("sensor", 7)
    after = c.project.to_dict()
    assert c.canUndo and c.dirty
    c.undo()
    assert c.project.to_dict() == before
    assert not c.canUndo and not c.dirty and c.canRedo
    c.redo()
    assert c.project.to_dict() == after


def test_noop_and_failed_edits_do_not_create_history(qapp):
    c = Controller()
    before = c.project.to_dict()
    assert c.moveTask("sensor", 0)
    assert not c.canUndo
    assert not c.moveTask("configure", 7)
    assert c.project.to_dict() == before and not c.canUndo


@pytest.mark.parametrize("value", ["not a number", "NaN", "inf", "-1"])
def test_invalid_number_is_atomic(qapp, value):
    c = Controller()
    before = c.project.to_dict()
    assert not c.editField("sensor", "duration", value)
    assert not c.addDependency("scenario", "sensor", "FS", value if value != "-1" else "NaN")
    assert c.project.to_dict() == before
    assert not c.canUndo


def test_hierarchy_cycles_roll_back(qapp):
    c = Controller()
    before = c.project.to_dict()
    assert not c.editField("planning", "parent", "planning")
    assert not c.editField("planning", "parent", "sensor")
    assert c.project.to_dict() == before


def test_create_edit_delete_and_undo(qapp):
    c = Controller()
    count = c.property("taskCount")
    task_id = c.addTask("planning", "task")
    assert c.property("taskCount") == count + 1 and c.selectedId == task_id
    assert c.editField(task_id, "name", "A new task")
    assert c.editField(task_id, "duration", "2,5")
    assert c.project.tasks[task_id].duration == 150
    c.deleteTask(task_id)
    assert c.taskCount == count
    c.undo()
    assert c.project.tasks[task_id].name == "A new task"


def test_progress_color_and_effort_survive_move(qapp):
    c = Controller()
    c.editField("sensor", "progress", "75")
    c.editField("sensor", "color", "#dd44aa")
    c.editField("sensor", "effort", "3.5")
    c.moveTask("sensor", 7)
    task = c.project.tasks["sensor"]
    assert (task.progress, task.color, task.effort) == (75, "#dd44aa", 3.5)


def test_collapsing_filtering_and_links(qapp):
    c = Controller()
    original = c.property("rowCount")
    c.toggleGroup("planning")
    assert c.property("rowCount") < original
    assert all(link["sourceRow"] < c.property("rowCount") and link["targetRow"] < c.property("rowCount") for link in c.property("links"))
    c.search("сенсор")
    visible = [r["taskId"] for r in c._rows.records if r["rowKind"] == "task"]
    assert "sensor" in visible and "supplier" in visible and "planning" in visible
    assert "configure" not in visible
    c.search("no such task")
    assert not any(r["rowKind"] == "task" for r in c._rows.records)
    c.search("")
    c.expandAll(True)
    assert c.rowCount == original


def test_dependency_edit_and_delete_undo(qapp):
    c = Controller()
    before = c.project.to_dict()
    assert c.addDependency("scenario", "sensor", "FS", "0")
    new_link = c.project.dependencies[-1]
    assert c.updateDependency(new_link.id, "scenario", "sensor", "SS", "8")
    updated = c.project.dependencies[-1]
    assert updated.kind == "SS" and updated.lag == 480
    c.removeDependency(updated.id)
    assert not c.project.incoming("sensor")
    for _ in range(3):
        c.undo()
    assert c.project.to_dict() == before


def test_save_reopen_and_dirty_marker(qapp, tmp_path):
    c = Controller()
    c.moveTask("sensor", 7)
    path = tmp_path / "test.gantt.json"
    assert c.save_path(path)
    assert not c.dirty
    saved = c.project.to_dict()
    c.editField("sensor", "name", "Changed")
    assert c.dirty
    c.undo()
    assert not c.dirty
    reopened = Controller()
    assert reopened.load_path(path)
    assert reopened.project.to_dict() == saved
    assert json.loads(path.read_text())["version"] == 8


def test_invalid_file_keeps_open_project(qapp, tmp_path):
    c = Controller()
    before = c.project.to_dict()
    path = tmp_path / "bad.json"
    path.write_text('{"version": 9}', encoding="utf-8")
    assert not c.load_path(path)
    assert c.project.to_dict() == before


def test_preview_does_not_change_model_or_history(qapp):
    c = Controller()
    before = c.project.to_dict()
    preview = c.preview("sensor", "move", 7)
    assert preview["valid"]
    assert c.project.to_dict() == before
    assert not c.canUndo
    assert not c.preview("configure", "move", 7)["valid"]
