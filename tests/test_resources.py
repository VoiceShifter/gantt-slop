from datetime import date, datetime, time

import pytest

from gantt_desktop.domain import Project, Resource, ScheduleError, Task, WorkCalendar
from gantt_desktop.workload import workload_rows

MONDAY = date(2026, 1, 5)


def project_with_task(hours=8, duration=480, start=MONDAY):
    task = Task("a", "Task A", datetime.combine(start, time(9)), duration,
                assignee="Alice", effort=hours)
    return Project(tasks={task.id: task})


def test_legacy_constructor_creates_real_resource_and_ids():
    p = project_with_task()
    task = p.tasks["a"]
    assert len(p.resources) == 1
    assert p.resources[task.resource_ids[0]].name == "Alice"
    assert task.assignee == "Alice"
    p.validate()


def test_rename_preserves_identity_dates_and_assignment():
    p = project_with_task()
    task = p.tasks["a"]
    key = task.resource_ids[0]
    before = (task.start, task.duration, task.effort, list(task.resource_ids))
    p.update_resource(key, "Alice renamed", 8, set(range(5)))
    assert task.assignee == "Alice renamed"
    assert (task.start, task.duration, task.effort, task.resource_ids) == before
    assert workload_rows(p, MONDAY, 7)[0]["name"] == "Alice renamed"


def test_unassign_and_resource_delete_retain_task_effort():
    p = project_with_task()
    key = p.tasks["a"].resource_ids[0]
    p.remove_resource(key)
    assert not p.resources and not p.tasks["a"].resource_ids
    assert p.tasks["a"].effort == 8 and p.tasks["a"].assignee == ""
    p.validate()


def test_case_insensitive_names_share_one_entity():
    p = project_with_task()
    key = p.ensure_resource(" alice ").id
    assert key == p.tasks["a"].resource_ids[0] and len(p.resources) == 1


def test_equal_multi_assignment_and_explicit_effort_shares():
    p = project_with_task(hours=12)
    alice = p.tasks["a"].resource_ids[0]
    bob = p.ensure_resource("Bob").id
    p.assign_resources("a", [alice, bob])
    rows = workload_rows(p, MONDAY, 1)
    assert [r["hours"] for r in rows] == [6, 6]
    p.assign_resources("a", [alice, bob], [3, 9])
    assert p.tasks["a"].effort == 12
    assert [r["hours"] for r in workload_rows(p, MONDAY, 1)] == [3, 9]


def test_overlapping_tasks_sum_daily_hours():
    p = project_with_task()
    p.tasks["b"] = Task("b", "Task B", datetime.combine(MONDAY, time(9)), effort=4)
    p.assign_resources("b", p.tasks["a"].resource_ids)
    row = workload_rows(p, MONDAY, 7)[0]
    assert row["days"][0]["hours"] == 12
    assert row["days"][0]["overloaded"] and row["days"][0]["count"] == 2
    assert row["warningDays"] == 1


def test_effort_is_weighted_by_working_time_with_partial_days():
    p = project_with_task(hours=12, duration=720)
    days = workload_rows(p, MONDAY, 3)[0]["days"]
    assert [d["hours"] for d in days] == [8, 4, 0]
    assert not any(d["overloaded"] for d in days)


def test_daily_rounding_conserves_effort():
    p = project_with_task(hours=8, duration=1440)
    days = workload_rows(p, MONDAY, 3)[0]["days"]
    assert [d["hours"] for d in days] == pytest.approx([2.67, 2.67, 2.66])
    assert sum(d["hours"] for d in days) == pytest.approx(8)


def test_range_clipping_does_not_reallocate_offscreen_effort():
    p = project_with_task(hours=8, duration=960)
    assert workload_rows(p, date(2026, 1, 6), 1)[0]["hours"] == 4


def test_spanning_weekend_does_not_imply_weekend_work():
    p = project_with_task(hours=24, duration=1440, start=date(2026, 1, 9))
    days = workload_rows(p, date(2026, 1, 9), 5)[0]["days"]
    assert [d["hours"] for d in days] == [8, 0, 0, 8, 8]
    assert not any(d["weekendWork"] for d in days)


def test_scheduled_weekend_work_is_flagged_against_person_calendar():
    p = project_with_task(hours=8, start=date(2026, 1, 10))
    p.calendar = WorkCalendar(workdays=set(range(7)))
    cell = workload_rows(p, date(2026, 1, 10), 1)[0]["days"][0]
    assert cell["hours"] == 8 and cell["capacity"] == 0
    assert cell["weekendWork"] and cell["nonworking"] and cell["overloaded"]


def test_person_capacity_and_workdays_are_independent_of_project_days():
    p = project_with_task(hours=6)
    key = p.tasks["a"].resource_ids[0]
    p.update_resource(key, "Alice", 4, set(range(5)))
    assert workload_rows(p, MONDAY, 1)[0]["days"][0]["overloaded"]
    p.update_resource(key, "Alice", 8, {1, 2, 3, 4})
    assert workload_rows(p, MONDAY, 1)[0]["days"][0]["nonworking"]


def test_milestone_effort_is_reported_on_its_date():
    p = project_with_task()
    task = p.tasks["a"]
    task.kind, task.duration, task.effort = "milestone", 0, 3
    assert workload_rows(p, MONDAY, 1)[0]["hours"] == 3


def test_summaries_do_not_double_count_child_effort():
    p = project_with_task()
    p.tasks["g"] = Task("g", "Group", datetime.combine(MONDAY, time(9)), 0, kind="group")
    p.tasks["a"].parent = "g"
    assert workload_rows(p, MONDAY, 1)[0]["hours"] == 8


def test_resource_and_calendar_round_trip_current_schema():
    p = project_with_task()
    bob = p.ensure_resource("Bob").id
    p.assign_resources("a", [p.tasks["a"].resource_ids[0], bob], [2, 6])
    p.calendar.workdays = set(range(7))
    data = p.to_dict()
    assert data["version"] == 4 and "assignee" not in data["tasks"][0]
    assert Project.from_dict(data).to_dict() == data


@pytest.mark.parametrize("version", [1, 2])
def test_old_files_migrate_names_to_resource_entities(version):
    p = project_with_task()
    data = p.to_dict()
    data["version"] = version
    data.pop("resources")
    for task in data["tasks"]:
        task.pop("resource_ids")
        task.pop("resource_shares")
        task["assignee"] = "Alice"
    migrated = Project.from_dict(data)
    assert len(migrated.resources) == 1 and migrated.tasks["a"].resource_ids
    assert migrated.tasks["a"].assignee == "Alice"
    assert workload_rows(migrated, MONDAY, 1)[0]["hours"] == 8


def test_unknown_resource_reference_is_rejected():
    p = project_with_task()
    data = p.to_dict()
    data["tasks"][0]["resource_ids"] = ["missing"]
    with pytest.raises(ScheduleError, match="ресурс"):
        Project.from_dict(data)


@pytest.mark.parametrize("capacity", [-1, 25, float("nan"), float("inf")])
def test_invalid_person_capacity_is_rejected(capacity):
    with pytest.raises(ScheduleError):
        Resource("r", "Person", capacity).validate()


def test_project_requires_at_least_one_workday():
    p = project_with_task()
    with pytest.raises(ScheduleError):
        p.set_workdays(set())


def test_loading_does_not_share_mutable_assignment_lists_with_snapshot():
    p = project_with_task()
    data = p.to_dict()
    ids = list(data["tasks"][0]["resource_ids"])
    loaded = Project.from_dict(data)
    loaded.tasks["a"].resource_ids.clear()
    assert data["tasks"][0]["resource_ids"] == ids
