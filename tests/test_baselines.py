import json
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta

import pytest

from gantt_desktop.controller import Controller
from gantt_desktop.domain import (
    Baseline,
    BaselineEntry,
    Dependency,
    Project,
    ScheduleError,
    Task,
)

DAY = date(2026, 1, 5)


def dt(value):
    return datetime.fromisoformat(value)


def project():
    return Project(tasks={
        "g": Task("g", "Group", dt("2026-01-05T09:00"), 0, kind="group"),
        "a": Task("a", "A", dt("2026-01-05T09:00"), 480, parent="g"),
        "b": Task("b", "B", dt("2026-01-06T09:00"), 480, parent="g"),
        "m": Task("m", "Milestone", dt("2026-01-07T09:00"), 0, kind="milestone"),
        "e": Task("e", "Empty", dt("2026-01-08T09:00"), 0, kind="group"),
    }, dependencies=[Dependency("ab", "a", "b")])


def test_capture_freezes_all_dates_kinds_and_names_without_changing_tasks():
    p = project()
    before = deepcopy(p.to_dict()["tasks"])
    key = p.capture_baseline("Initial", DAY)
    snapshot = p.baselines[key]
    assert snapshot.created == DAY and p.active_baseline == key
    assert set(snapshot.tasks) == set(p.tasks)
    assert snapshot.tasks["g"].end == p.span("b")[1]
    assert snapshot.tasks["m"].kind == "milestone" and snapshot.tasks["m"].start == snapshot.tasks["m"].end
    assert p.to_dict()["tasks"] == before
    with pytest.raises(FrozenInstanceError):
        snapshot.tasks["a"].__setattr__("start", dt("2026-02-01T09:00"))
    p.move("a", 7)
    p.tasks["a"].name = "Renamed"
    assert snapshot.tasks["a"].name == "A" and snapshot.tasks["a"].start == dt("2026-01-05T09:00")


def test_multiple_snapshots_select_remove_and_deleted_task_archives():
    p = project()
    first = p.capture_baseline("First", DAY)
    p.move("a", 7)
    second = p.capture_baseline("Second", DAY)
    assert p.baselines[first].tasks["a"].start != p.baselines[second].tasks["a"].start
    current = p.to_dict()["tasks"]
    p.select_baseline(first)
    assert p.to_dict()["tasks"] == current
    p.remove("a")
    assert "a" in p.baselines[first].tasks and "a" not in p.tasks
    p.remove_baseline(second)
    assert p.active_baseline == first
    p.remove_baseline(first)
    assert not p.baselines and p.active_baseline == ""
    p.validate()


@pytest.mark.parametrize("name", ["", "  ", "INITIAL", " Initial "])
def test_empty_or_duplicate_names_reject_without_partial_capture(name):
    p = project()
    p.capture_baseline("Initial", DAY)
    before = p.to_dict()
    with pytest.raises(ScheduleError):
        p.capture_baseline(name, DAY)
    assert p.to_dict() == before


def test_history_is_independent_of_baseline_storage_and_active_selection(qapp, tmp_path):
    c = Controller(project())
    first = c.createBaseline("First")
    assert first
    assert c.moveTask("a", 7)
    second = c.createBaseline("Second")
    assert c.selectBaseline(first)
    before = c.project.to_dict()
    assert c.selectBaseline(first) and c.project.to_dict() == before
    path = tmp_path / "baseline.json"
    assert c.save_path(path)
    restored = Controller()
    assert restored.load_path(path) and not restored.canUndo
    assert restored.project.active_baseline == first and set(restored.project.baselines) == {first, second}
    assert restored.project.to_dict() == before
    assert restored.removeBaseline(first)
    assert restored.project.active_baseline == ""
    restored.undo()
    assert restored.project.to_dict() == before and restored.project.active_baseline == first
    assert restored.selectBaseline(second)
    restored.undo()
    assert restored.project.active_baseline == first


def test_capture_and_delete_are_single_undo_steps_and_selection_never_moves_tasks(qapp):
    c = Controller(project())
    before = c.project.to_dict()
    key = c.createBaseline("Initial")
    after = c.project.to_dict()
    assert key and c.canUndo and c.dirty
    c.undo()
    assert c.project.to_dict() == before and not c.canUndo
    c.redo()
    assert c.project.to_dict() == after
    assert c.selectBaseline("")
    assert c.project.to_dict()["tasks"] == before["tasks"]
    assert not c.record("a")["hasBaseline"]
    c.undo()
    assert c.record("a")["hasBaseline"]
    assert c.removeBaseline(key)
    c.undo()
    assert c.project.to_dict() == after


def test_new_deleted_and_renamed_tasks_match_only_stable_ids(qapp):
    c = Controller(project())
    key = c.createBaseline("Initial")
    assert c.editField("a", "name", "Renamed")
    assert c.record("a")["hasBaseline"] and c.project.baselines[key].tasks["a"].name == "A"
    c.deleteTask("m")
    assert "m" not in c.project.tasks
    c.addTask("", "task")
    created = c.property("selectedId")
    assert isinstance(created, str)
    assert not c.record(created)["hasBaseline"]
    assert c.record(created)["startVarianceHours"] is None and c.record(created)["startVariance"] == ""
    assert "m" in c.project.baselines[key].tasks
    assert "новых: 1" in c.property("baselineInfo") and "удалённых: 1" in c.property("baselineInfo")


def test_variance_uses_signed_civil_hours_not_working_time(qapp):
    p = Project(tasks={"a": Task("a", "A", dt("2026-01-09T09:00"), 480)})
    c = Controller(p)
    assert c.createBaseline("Friday")
    assert c.editField("a", "start", "2026-01-12")
    row = c.record("a")
    assert row["startVarianceHours"] == 72 and row["endVarianceHours"] == 72
    assert row["startVariance"] == "+72"
    assert c.editField("a", "start", "2026-01-07")
    assert c.record("a")["startVarianceHours"] == -48
    c.undo()
    assert c.record("a")["startVarianceHours"] == 72


def test_snapshot_dates_do_not_recompute_with_calendar_hierarchy_or_critical_path(qapp):
    c = Controller(project())
    key = c.createBaseline("Initial")
    saved = deepcopy(c.project.to_dict()["baselines"])
    assert c.setProjectWorkdays([1, 2, 3, 4])
    c.setCriticalPath(True)
    assert c.project.to_dict()["baselines"] == saved
    assert c.project.baselines[key].tasks["g"].start == dt("2026-01-05T09:00")


def test_snapshot_json_deep_copy_and_full_datetime_precision():
    p = project()
    p.tasks["a"].start += timedelta(seconds=12)
    key = p.capture_baseline("Precise", DAY)
    data = p.to_dict()
    assert data["version"] == 8
    original = deepcopy(data)
    restored = Project.from_dict(json.loads(json.dumps(data)))
    assert restored.baselines[key].tasks["a"].start.second == 12
    restored.baselines[key].tasks.clear()
    assert data == original and len(p.baselines[key].tasks) == 5


@pytest.mark.parametrize("version", [1, 2, 3, 4, 5, 6])
def test_old_schemas_load_without_baselines(version):
    data = project().to_dict()
    data["version"] = version
    data.pop("baselines")
    data.pop("active_baseline")
    restored = Project.from_dict(data)
    assert restored.baselines == {} and restored.active_baseline == ""
    assert restored.to_dict()["version"] == 8


@pytest.mark.parametrize("damage", ["duplicate-baseline", "duplicate-entry", "duplicate-name", "bad-id", "bad-name", "bad-kind", "bad-dates", "timezone", "active", "created"])
def test_invalid_snapshot_files_are_rejected(damage):
    p = project()
    p.capture_baseline("Initial", DAY)
    data = p.to_dict()
    baseline = data["baselines"][0]
    entry = baseline["tasks"][0]
    if damage == "duplicate-baseline":
        data["baselines"].append(deepcopy(baseline))
    elif damage == "duplicate-entry":
        baseline["tasks"].append(deepcopy(entry))
    elif damage == "duplicate-name":
        other = deepcopy(baseline)
        other["id"] = "other"
        other["name"] = "INITIAL"
        data["baselines"].append(other)
    elif damage == "bad-id":
        entry["task_id"] = ""
    elif damage == "bad-name":
        baseline["name"] = ""
    elif damage == "bad-kind":
        entry["kind"] = "unknown"
    elif damage == "bad-dates":
        entry["end"] = "2020-01-01T09:00"
    elif damage == "timezone":
        entry["start"] += "+00:00"
    elif damage == "active":
        data["active_baseline"] = "missing"
    else:
        baseline["created"] = "2026-02-30"
    with pytest.raises(ValueError):
        Project.from_dict(data)


def test_invalid_commands_roll_back_and_empty_snapshots_are_safe(qapp):
    c = Controller(project())
    before = c.project.to_dict()
    assert not c.selectBaseline("missing") and not c.removeBaseline("missing")
    assert c.project.to_dict() == before and not c.canUndo
    empty = Controller(Project())
    key = empty.createBaseline("Empty")
    assert key and not empty.project.baselines[key].tasks and empty.baselineName == "Empty"
    assert empty.removeBaseline(key)


def test_active_reference_extends_timeline_and_far_dates_do_not_allocate_centuries(qapp):
    c = Controller(project())
    key = c.createBaseline("Initial")
    assert c.moveTask("a", 90)
    reopened = Controller(Project.from_dict(c.project.to_dict()))
    assert reopened._origin <= reopened.project.baselines[key].tasks["a"].start.date()
    assert reopened.record("a")["baselineStartDay"] >= 0
    p = project()
    entry = BaselineEntry("a", "A", "task", dt("1500-01-01T09:00"), dt("1500-01-02T18:00"))
    p.baselines = {"far": Baseline("far", "Far", DAY, {"a": entry})}
    p.active_baseline = "far"
    p.validate()
    far = Controller(p)
    assert far.property("dayCount") < 36600 and "100 лет" in far.property("baselineInfo")
    assert far.record("a")["hasBaseline"]


def test_milestone_snapshot_validation_and_unknown_deleted_entry_are_independent():
    entry = BaselineEntry("deleted", "Old", "milestone", dt("2026-01-05T09:00"), dt("2026-01-05T09:00"))
    p = project()
    p.baselines = {"b": Baseline("b", "B", DAY, {"deleted": entry})}
    p.active_baseline = "b"
    p.validate()
    p.baselines["b"] = replace(p.baselines["b"], tasks={"deleted": replace(entry, end=entry.end+timedelta(minutes=1))})
    with pytest.raises(ScheduleError):
        p.validate()
