import json
from copy import deepcopy
from datetime import date, datetime

import pytest

from gantt_desktop.controller import Controller
from gantt_desktop.domain import (
    CalendarException,
    Dependency,
    Project,
    Resource,
    ResourceException,
    ScheduleError,
    Task,
    WorkCalendar,
)
from gantt_desktop.workload import workload_rows

MONDAY = date(2026, 1, 5)


def dt(value):
    return datetime.fromisoformat(value)


def exception(key="closed", start=MONDAY, end=None, periods=None):
    return CalendarException(key, start, end or start, "Exception", periods or [])


def project():
    p = Project(tasks={
        "g": Task("g", "Group", dt("2026-01-05T09:00"), 0, kind="group"),
        "a": Task("a", "A", dt("2026-01-05T09:00"), 960, parent="g", effort=12, assignee="Alice"),
        "b": Task("b", "B", dt("2026-01-07T09:00"), 480, parent="g", effort=3),
    }, dependencies=[Dependency("ab", "a", "b")])
    p.validate()
    return p


def save(c, resource="", key="", start="2026-01-06", end="2026-01-06", periods=None, capacity="0", holiday=""):
    return c.saveCalendarException(resource, key, "Exception", start, end, periods or [], capacity, holiday)


def test_closed_ranges_override_weekdays_and_working_ranges_override_holidays():
    day = date(2026, 1, 10)
    calendar = WorkCalendar(holidays={day}, exceptions=[exception(start=day, periods=[[420, 660]])])
    calendar.validate()
    assert calendar.working_day(day)
    assert calendar.segments(day) == [(dt("2026-01-10T07:00"), dt("2026-01-10T11:00"))]
    calendar.exceptions = [exception(start=MONDAY, end=date(2026, 1, 7))]
    assert not any(calendar.working_day(date(2026, 1, n)) for n in (5, 6, 7))
    assert calendar.working_day(date(2026, 1, 8))


def test_normalize_and_signed_arithmetic_use_early_and_late_exception_times():
    saturday = date(2026, 1, 10)
    calendar = WorkCalendar(exceptions=[exception(start=saturday, periods=[[420, 660], [1140, 1260]])])
    calendar.validate()
    assert calendar.normalize(dt("2026-01-09T18:00")) == dt("2026-01-10T07:00")
    assert calendar.normalize(dt("2026-01-12T08:00"), False) == dt("2026-01-10T21:00")
    assert calendar.add(dt("2026-01-09T17:00"), 120) == dt("2026-01-10T08:00")
    assert calendar.add(dt("2026-01-10T08:00"), -120) == dt("2026-01-09T17:00")
    assert calendar.between(dt("2026-01-10T07:00"), dt("2026-01-10T21:00")) == 360


def test_short_days_lunch_gaps_and_dragged_starts_use_actual_intervals():
    calendar = WorkCalendar(exceptions=[exception(periods=[[600, 720], [780, 840]])])
    assert calendar.normalize(dt("2026-01-05T12:30")) == dt("2026-01-05T13:00")
    assert calendar.add(dt("2026-01-05T10:00"), 240) == dt("2026-01-06T10:00")
    assert calendar.add(dt("2026-01-06T10:00"), -240) == dt("2026-01-05T10:00")
    assert calendar.shift_date(dt("2026-01-02T09:00"), 3) == dt("2026-01-05T09:00")
    assert calendar.shift_workdays(dt("2026-01-02T09:00"), 1) == dt("2026-01-05T10:00")


@pytest.mark.parametrize("periods", [
    [[600, 600]], [[660, 600]], [[540, 800], [780, 900]], [[840, 900], [540, 600]],
    [[0, 60], [120, 180], [240, 300]], [[-1, 60]], [[0, 1440]], [[True, 780]], [[540.0, 780]],
    [["09:00", "13:00"]], [[540]], None,
])
def test_invalid_project_intervals_are_rejected(periods):
    item = exception()
    item.periods = periods
    with pytest.raises(ScheduleError):
        WorkCalendar(exceptions=[item]).validate()


@pytest.mark.parametrize("capacity", [-1, 25, True, "8", None, float("nan"), float("inf"), 10**1000])
def test_invalid_exception_capacities_are_rejected(capacity):
    resource = Resource("r", "R", exceptions=[ResourceException("e", MONDAY, MONDAY, capacity=capacity)])
    with pytest.raises(ScheduleError):
        resource.validate()


@pytest.mark.parametrize("resource", [False, True])
def test_exception_identity_ranges_overlap_and_context_are_validated(resource):
    if resource:
        owner = Resource("r", "R", exceptions=[ResourceException("a", MONDAY, date(2026, 1, 7)),
                                               ResourceException("b", date(2026, 1, 7), date(2026, 1, 8))])
    else:
        owner = WorkCalendar(exceptions=[CalendarException("a", MONDAY, date(2026, 1, 7)),
                                         CalendarException("b", date(2026, 1, 7), date(2026, 1, 8))])
    values = owner.exceptions
    with pytest.raises(ScheduleError, match="пересекаются"):
        owner.validate()
    values[1].start = date(2026, 1, 8)
    owner.validate()
    values[1].id = "a"
    with pytest.raises(ScheduleError, match="идентификатор"):
        owner.validate()
    values[1].id = "b"
    values[1].end = MONDAY
    with pytest.raises(ScheduleError, match="Начало"):
        owner.validate()
    vars(owner)["exceptions"] = [exception()] if resource else [ResourceException("r", MONDAY, MONDAY)]
    with pytest.raises(ScheduleError, match="список"):
        owner.validate()


def test_resource_exceptions_override_weekdays_and_zero_capacity_without_changing_dates():
    resource = Resource("r", "R", capacity=8, exceptions=[ResourceException("leave", MONDAY, date(2026, 1, 7)),
                                                        ResourceException("sat", date(2026, 1, 10), date(2026, 1, 10), capacity=6)])
    resource.validate()
    assert resource.available(MONDAY) == 0
    assert resource.available(date(2026, 1, 8)) == 8
    assert resource.available(date(2026, 1, 10)) == 6


def test_project_exception_recalculates_dependencies_groups_and_milestones_atomically(qapp):
    p = project()
    p.tasks["m"] = Task("m", "Milestone", dt("2026-01-06T12:00"), 0, kind="milestone")
    p.tasks["e"] = Task("e", "Empty group", dt("2026-01-06T15:00"), 0, kind="group")
    c = Controller(p)
    before = c.project.to_dict()
    assert save(c)
    assert c.project.span("a")[1] == dt("2026-01-07T18:00")
    assert c.project.tasks["b"].start == dt("2026-01-08T09:00")
    assert c.project.tasks["m"].start == dt("2026-01-07T09:00")
    assert c.project.tasks["e"].start == dt("2026-01-07T09:00")
    assert c.project.span("g")[1] == c.project.span("b")[1]
    assert c.project.tasks["a"].duration == 960 and c.project.tasks["a"].effort == 12
    after = c.project.to_dict()
    c.undo()
    assert c.project.to_dict() == before and not c.canUndo
    c.redo()
    assert c.project.to_dict() == after


@pytest.mark.parametrize("kind", ["FS", "SS", "FF", "SF"])
@pytest.mark.parametrize("lag", [-60, 60])
def test_calendar_recalculation_retains_dependency_types_and_signed_lags(qapp, kind, lag):
    p = project()
    p.dependencies[0].kind, p.dependencies[0].lag = kind, lag
    p.align("b")
    c = Controller(p)
    assert save(c)
    assert c.project.tasks["b"].start == c.project.required_start("b")
    assert c.project.dependencies[0].kind == kind and c.project.dependencies[0].lag == lag


def test_resource_exception_crud_and_noops_do_not_move_or_modify_tasks(qapp):
    c = Controller(project())
    rid = next(iter(c.project.resources))
    before = c.project.to_dict()
    assert save(c, rid, capacity="4")
    key = c.project.resources[rid].exceptions[0].id
    assert c.project.to_dict()["tasks"] == before["tasks"]
    after = c.project.to_dict()
    assert save(c, rid, key, capacity="4")
    c.undo()
    assert c.project.to_dict() == before and not c.canUndo
    c.redo()
    assert c.project.to_dict() == after
    assert c.removeCalendarException(rid, key)
    assert not c.project.resources[rid].exceptions
    c.undo()
    assert c.project.to_dict() == after


def test_invalid_overlap_stale_ids_and_ranges_roll_back_everything(qapp):
    c = Controller(project())
    assert save(c)
    before = c.project.to_dict()
    for changes in ({}, {"key": "missing"}, {"start": "2026-02-01", "end": "2026-01-01"}, {"resource": "missing"}):
        assert not save(c, **changes)
        assert c.project.to_dict() == before
    assert not c.removeCalendarException("", "missing")
    assert c.project.to_dict() == before


def test_workload_uses_resource_leave_and_extra_weekend_availability(qapp):
    c = Controller(project())
    rid = next(iter(c.project.resources))
    assert save(c, rid, start="2026-01-05", end="2026-01-05")
    cell = workload_rows(c.project, MONDAY, 1)[0]["days"][0]
    assert cell["hours"] == 6 and cell["capacity"] == 0 and cell["nonworking"] and cell["overloaded"]
    assert save(c, start="2026-01-10", end="2026-01-10", periods=[[540, 780]])
    assert save(c, rid, start="2026-01-10", end="2026-01-10", capacity="6")
    cell = workload_rows(c.project, date(2026, 1, 10), 1)[0]["days"][0]
    assert cell["capacity"] == 6
    assert c.project.calendar.working_day(date(2026, 1, 10))


def test_workload_distributes_effort_over_short_days_and_clips_after_distribution():
    p = project()
    p.calendar.exceptions = [exception(periods=[[540, 780]])]
    cells = workload_rows(p, MONDAY, 3)[0]["days"]
    assert [cell["hours"] for cell in cells] == [3, 6, 3]
    assert workload_rows(p, date(2026, 1, 6), 1)[0]["hours"] == 6
    p.calendar.exceptions = [exception()]
    assert workload_rows(p, MONDAY, 1)[0]["days"][0]["capacity"] == 0


def test_legacy_holiday_edit_noop_change_delete_and_undo(qapp):
    p = project()
    holiday = date(2026, 1, 6)
    p.calendar.holidays.add(holiday)
    c = Controller(p)
    before = c.project.to_dict()
    assert c.saveCalendarException("", "", "Праздник", holiday.isoformat(), holiday.isoformat(), [], "0", holiday.isoformat())
    assert c.project.to_dict() == before and not c.canUndo
    assert save(c, start="2026-01-06", end="2026-01-07", holiday=holiday.isoformat())
    assert not c.project.calendar.holidays and len(c.project.calendar.exceptions) == 1
    c.undo()
    assert c.project.to_dict() == before
    assert c.removeCalendarException("", "", holiday.isoformat())
    assert not c.project.calendar.holidays
    c.undo()
    assert c.project.to_dict() == before


def test_weekday_changes_preserve_overrides_and_snapshots_do_not_alias(qapp):
    c = Controller(project())
    assert save(c, periods=[[600, 720]])
    snapshot = c.project.to_dict()
    original = deepcopy(snapshot)
    restored = Project.from_dict(snapshot)
    restored.calendar.exceptions[0].periods[0][0] = 660
    assert snapshot == original
    assert c.setProjectWorkdays([0, 1, 2, 3])
    assert c.project.calendar.exceptions[0].periods == [[600, 720]]
    c.undo()
    assert c.project.to_dict() == original


@pytest.mark.parametrize("version", [1, 2, 3, 4, 5])
def test_schema_migration_keeps_old_holidays_and_empty_exception_lists(version):
    p = project()
    p.calendar.holidays.add(date(2026, 1, 1))
    data = p.to_dict()
    data["version"] = version
    data.pop("calendar_exceptions")
    for resource in data["resources"]:
        resource.pop("exceptions")
    restored = Project.from_dict(data)
    assert restored.calendar.holidays == p.calendar.holidays
    assert not restored.calendar.exceptions and all(not r.exceptions for r in restored.resources.values())
    assert restored.to_dict()["version"] == 8


def test_schema_six_roundtrip_history_and_file_save(qapp, tmp_path):
    c = Controller(project())
    rid = next(iter(c.project.resources))
    assert save(c, periods=[[600, 780], [840, 960]])
    assert save(c, rid, start="2026-01-07", end="2026-01-09", capacity="2.001")
    data = c.project.to_dict()
    assert data["version"] == 8 and Project.from_dict(json.loads(json.dumps(data))).to_dict() == data
    path = tmp_path / "calendar.json"
    assert c.save_path(path)
    other = Controller()
    assert other.load_path(path) and other.project.to_dict() == data
    invalid = deepcopy(data)
    invalid["calendar_exceptions"][0]["periods"] = [[840, 600]]
    with pytest.raises(ScheduleError):
        Project.from_dict(invalid)


@pytest.mark.parametrize("kind", ["FS", "SS", "FF", "SF"])
def test_calendar_changes_keep_summary_dependency_endpoints_consistent(qapp, kind):
    p = project()
    p.tasks["source"] = Task("source", "Source", dt("2026-01-07T09:00"), 480)
    c = Controller(p)
    assert c.addDependency("source", "g", kind, "0")
    before = c.project.to_dict()
    assert save(c)
    for link in c.project.dependencies:
        anchor = c.project.calendar.add(c.project.span(link.source)[link.kind[0] == "F"], link.lag)
        actual = c.project.span(link.target)[link.kind[1] == "F"]
        # Finish/start sides of a closed interval are zero working minutes apart.
        assert c.project.calendar.between(anchor, actual) >= 0
        if link.kind[1] == "S":
            assert actual >= anchor
    assert c.project.tasks["a"].duration == 960 and c.project.tasks["b"].duration == 480
    c.undo()
    assert c.project.to_dict() == before


def test_renaming_project_exception_does_not_reschedule_manual_slack(qapp):
    p = project()
    p.calendar.exceptions = [exception(start=date(2026, 1, 10))]
    p.tasks["b"].start = dt("2026-01-09T09:00")
    c = Controller(p)
    before = c.project.to_dict()
    assert c.saveCalendarException("", "closed", "Renamed", "2026-01-10", "2026-01-10", [], "0")
    assert c.project.to_dict()["tasks"] == before["tasks"]
    assert c.project.calendar.exceptions[0].name == "Renamed"
    c.undo()
    assert c.project.to_dict() == before
