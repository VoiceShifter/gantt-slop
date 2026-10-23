import json

from gantt_desktop.controller import Controller


def schedule_values(controller):
    return {key: (task.start, task.duration, task.effort, task.cost)
            for key, task in controller.project.tasks.items() if task.kind != "group"}


def test_selection_is_view_state_with_group_tristate(qapp):
    c = Controller()
    before = c.project.to_dict()
    c.setBulkMode(True)
    c.toggleChecked("planning")
    assert c.property("checkedCount") == 6
    assert c.property("checkStates")["planning"] == 2
    c.toggleChecked("scenario")
    assert c.property("checkedCount") == 5
    assert c.property("checkStates")["planning"] == 1
    c.toggleChecked("planning")
    assert c.property("checkedCount") == 6
    c.setBulkMode(False)
    assert c.property("checkedCount") == 0
    assert c.project.to_dict() == before and not c.canUndo and not c.dirty


def test_bulk_patch_is_one_history_transaction(qapp):
    c = Controller()
    before = c.project.to_dict()
    dates = schedule_values(c)
    c.setBulkMode(True)
    c.toggleChecked("scenario")
    c.toggleChecked("sensor")
    assert c.applyBulk({"assignee": "Test", "status": "completed", "priority": "highest", "color": "#aabbcc"})
    for key in ("scenario", "sensor"):
        task = c.project.tasks[key]
        assert (task.assignee, task.status, task.progress, task.priority, task.color) == ("Test", "completed", 100, "highest", "#aabbcc")
    assert schedule_values(c) == dates
    assert c.property("checkedCount") == 2
    c.undo()
    assert c.project.to_dict() == before and not c.canUndo
    c.redo()
    assert c.project.tasks["sensor"].status == "completed"


def test_bulk_clear_assignee_and_noop(qapp):
    c = Controller()
    c.setBulkMode(True)
    c.toggleChecked("sensor")
    assert c.applyBulk({"status": "open"}) and not c.canUndo
    assert c.applyBulk({"assignee": ""})
    assert c.project.tasks["sensor"].assignee == ""
    c.undo()
    assert c.project.tasks["sensor"].assignee == "Клиент"


def test_invalid_bulk_patch_rolls_everything_back(qapp):
    c = Controller()
    before = c.project.to_dict()
    c.setBulkMode(True)
    c.toggleChecked("planning")
    assert not c.applyBulk({"assignee": "Changed", "priority": "invalid"})
    assert not c.applyBulk({"color": "invalid"})
    assert not c.applyBulk({"duration": "8"})
    assert c.project.to_dict() == before and not c.canUndo


def test_deselected_children_are_not_edited_or_deleted(qapp):
    c = Controller()
    before = c.project.to_dict()
    c.setBulkMode(True)
    c.toggleChecked("planning")
    c.toggleChecked("scenario")
    assert c.property("bulkDeleteCount") == 4
    assert c.applyBulk({"status": "closed", "color": "#eeeeee"})
    assert c.project.tasks["scenario"].status == "open"
    assert c.project.tasks["scenario"].color == "#50c7d6"
    assert c.project.tasks["planning"].color == "#eeeeee"
    assert c.deleteChecked()
    assert "planning" in c.project.tasks and "scenario" in c.project.tasks
    assert len(c.project.children("planning")) == 1
    c.undo()
    c.undo()
    assert c.project.to_dict() == before


def test_full_group_delete_is_atomic(qapp):
    c = Controller()
    before = c.project.to_dict()
    c.setBulkMode(True)
    c.toggleChecked("planning")
    assert c.property("bulkDeleteCount") == 6
    assert c.deleteChecked()
    assert "planning" not in c.project.tasks and "sensor" not in c.project.tasks
    c.project.validate()
    c.undo()
    assert c.project.to_dict() == before


def test_select_all_includes_collapsed_children_and_respects_filters(qapp):
    c = Controller()
    c.expandAll(False)
    c.setBulkMode(True)
    c.setAllChecked(True)
    assert c.property("checkedCount") == 20
    c.search("сенсор")
    assert c.property("checkedCount") == 0
    c.setAllChecked(True)
    assert set(c.property("checkedIds")) == {"planning", "sensor", "preparation", "supplier"}
    c.setAllChecked(False)
    c.toggleChecked("planning")
    assert set(c.property("checkedIds")) == {"planning", "sensor"}
    c.search("")
    assert c.property("checkedCount") == 0


def test_completion_filter_drops_hidden_selections(qapp):
    c = Controller()
    c.setFilter("incomplete")
    c.setBulkMode(True)
    c.toggleChecked("sensor")
    assert c.applyBulk({"status": "completed"})
    assert c.property("checkedCount") == 0


def test_bulk_mode_guards_date_edits_and_new_task_creation(qapp):
    c = Controller()
    before = c.project.to_dict()
    c.setBulkMode(True)
    assert not c.moveTask("sensor", 7)
    assert not c.resizeTask("sensor", "end", 7)
    assert c.addTask("", "task") == ""
    assert c.project.to_dict() == before and not c.canUndo


def test_metadata_persists_and_project_load_clears_selection(qapp, tmp_path):
    c = Controller()
    c.editField("sensor", "status", "closed")
    c.editField("sensor", "priority", "high")
    path = tmp_path / "metadata.gantt.json"
    assert c.save_path(path)
    c.setBulkMode(True)
    c.toggleChecked("planning")
    assert c.load_path(path)
    assert not c.property("bulkMode") and c.property("checkedCount") == 0
    assert c.project.tasks["sensor"].progress == 100
    assert c.project.tasks["sensor"].priority == "high"
    data = json.loads(path.read_text())
    assert next(task for task in data["tasks"] if task["id"] == "sensor")["status"] == "closed"


def test_row_preview_and_relocation_preserve_date_values(qapp):
    c = Controller()
    before = c.project.to_dict()
    dates = schedule_values(c)
    row = next(i for i, r in enumerate(c._rows.records) if r["taskId"] == "preparation")
    preview = c.rowDropPreview("scenario", row, 0.5, True)
    assert preview["valid"] and preview["placement"] == "inside"
    assert c.project.to_dict() == before and not c.canUndo
    assert c.relocateRow("scenario", preview["target"], preview["placement"])
    assert schedule_values(c) == dates
    assert c.record("preparation")["effortHours"] == 72
    assert c._rows.records[next(i for i, r in enumerate(c._rows.records) if r["taskId"] == "scenario")]["outline"] == "2.1"
    c.undo()
    assert c.project.to_dict() == before


def test_invalid_and_noop_row_drops_do_not_create_history(qapp):
    c = Controller()
    before = c.project.to_dict()
    row = next(i for i, r in enumerate(c._rows.records) if r["taskId"] == "sensor")
    assert not c.rowDropPreview("planning", row, 0.5, True)["valid"]
    assert not c.relocateRow("planning", "sensor", "inside")
    assert c.relocateRow("scenario", "planning", "inside")
    assert c.project.to_dict() == before and not c.canUndo
