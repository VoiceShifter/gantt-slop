from datetime import datetime, time

from test_resources import MONDAY, project_with_task

from gantt_desktop.controller import Controller
from gantt_desktop.domain import Task


def test_resource_save_is_atomic_and_undoable(qapp):
    c = Controller()
    before = c.project.to_dict()
    key = c.saveResource("", "Alex", "4", [0, 1, 2, 3, 4, 5])
    assert key and c.project.resources[key].capacity == 4
    assert c.project.resources[key].workdays == set(range(6))
    c.undo()
    assert c.project.to_dict() == before and not c.canUndo


def test_rename_changes_all_labels_without_reassigning_or_rescheduling(qapp):
    c = Controller()
    task = c.project.tasks["sensor"]
    key = task.resource_ids[0]
    before = c.project.to_dict()
    dates = [(t.start, t.duration, t.effort) for t in c.project.tasks.values()]
    assert c.updateResource(key, "Customer", "8", [0, 1, 2, 3, 4])
    assert c.project.tasks["sensor"].resource_ids == [key]
    assert c.record("sensor")["assignee"] == "Customer"
    assert c.project.tasks["scenario"].assignee == "Customer"
    assert [(t.start, t.duration, t.effort) for t in c.project.tasks.values()] == dates
    c.undo()
    assert c.project.to_dict() == before


def test_invalid_resource_changes_leave_no_partial_entities(qapp):
    c = Controller()
    before = c.project.to_dict()
    assert not c.saveResource("", "New", "bad", [0])
    assert not c.createResource("Клиент")
    assert not c.assignResources("sensor", ["missing"], [8])
    assert not c.assignResources("sensor", c.project.tasks["sensor"].resource_ids, ["NaN"])
    assert not c.setProjectWorkdays([])
    assert c.project.to_dict() == before and not c.canUndo


def test_resource_deletion_and_assignments_undo_together(qapp):
    c = Controller()
    before = c.project.to_dict()
    key = c.project.tasks["sensor"].resource_ids[0]
    assert c.removeResource(key)
    assert c.project.tasks["sensor"].assignee == ""
    assert c.project.tasks["sensor"].effort == 8
    c.undo()
    assert c.project.to_dict() == before


def test_assignment_shares_save_as_one_transaction(qapp):
    c = Controller()
    ids = [c.project.tasks["sensor"].resource_ids[0], c.project.tasks["model"].resource_ids[0]]
    before = c.project.to_dict()
    assert c.assignResources("sensor", ids, [2, 6])
    assert c.project.tasks["sensor"].resource_shares == [0.25, 0.75]
    assert c.project.tasks["sensor"].effort == 8
    c.undo()
    assert c.project.to_dict() == before


def test_unchanged_assignment_save_has_no_history(qapp):
    c = Controller()
    task = c.project.tasks["sensor"]
    before = c.project.to_dict()
    assert c.assignResources("sensor", task.resource_ids, [task.effort])
    assert c.project.to_dict() == before and not c.canUndo


def test_workload_ignores_task_search_and_capacity_changes_preserve_dates(qapp):
    p = project_with_task()
    p.tasks["b"] = Task("b", "Other", datetime.combine(MONDAY, time(9)), effort=8)
    p.assign_resources("b", p.tasks["a"].resource_ids)
    c = Controller(p)
    c.search("Task A")
    assert max(d["hours"] for d in c.property("workloadRows")[0]["days"]) == 16
    before = c.project.to_dict()
    key = p.tasks["a"].resource_ids[0]
    assert c.updateResource(key, "Alice", "16", [0, 1, 2, 3, 4])
    assert not c.property("workloadRows")[0]["warningDays"]
    c.undo()
    assert c.project.to_dict() == before


def test_project_calendar_change_and_dates_undo_together(qapp):
    c = Controller()
    before = c.project.to_dict()
    assert c.setProjectWorkdays([0, 1, 2, 3, 4, 5, 6])
    assert c.project.calendar.workdays == set(range(7))
    c.project.validate()
    c.undo()
    assert c.project.to_dict() == before


def test_resources_and_calendar_survive_file_load(qapp, tmp_path):
    c = Controller()
    key = c.project.tasks["sensor"].resource_ids[0]
    assert c.updateResource(key, "Renamed", "6", [0, 1, 2, 3])
    path = tmp_path / "resources.json"
    assert c.save_path(path)
    loaded = Controller()
    assert loaded.load_path(path)
    assert loaded.project.to_dict() == c.project.to_dict()
    assert loaded.resourceCatalog == c.resourceCatalog


def test_deleting_one_shared_resource_has_canonical_redo_state(qapp):
    c = Controller()
    client = c.project.tasks["sensor"].resource_ids[0]
    artist = c.project.tasks["model"].resource_ids[0]
    assert c.assignResources("sensor", [client, artist], [2, 6])
    assert c.removeResource(artist)
    after = c.project.to_dict()
    assert c.project.tasks["sensor"].resource_shares == []
    assert c.project.tasks["sensor"].effort == 8
    c.undo()
    c.redo()
    assert c.project.to_dict() == after
