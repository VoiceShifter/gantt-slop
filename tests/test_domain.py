from datetime import date, datetime, timedelta

import pytest

from gantt_desktop.domain import Dependency, Project, ScheduleError, Task, WorkCalendar
from gantt_desktop.sample import sample_project


def dt(value):
    return datetime.fromisoformat(value)


def chain():
    p = Project(tasks={
        "a": Task("a", "A", dt("2026-06-05T09:00"), 480),
        "b": Task("b", "B", dt("2026-06-08T09:00"), 960),
        "c": Task("c", "C", dt("2026-06-10T09:00"), 480),
    })
    p.dependencies = [Dependency("ab", "a", "b"), Dependency("bc", "b", "c")]
    return p


@pytest.mark.parametrize("minutes,expected", [
    (0, "2026-06-05T09:00"), (240, "2026-06-05T13:00"),
    (300, "2026-06-05T15:00"), (480, "2026-06-05T18:00"),
    (540, "2026-06-08T10:00"), (960, "2026-06-08T18:00"),
    (-60, "2026-06-04T17:00"), (-480, "2026-06-04T09:00"),
])
def test_calendar(minutes, expected):
    assert WorkCalendar().add(dt("2026-06-05T09:00"), minutes) == dt(expected)


def test_holidays_and_signed_working_time():
    calendar = WorkCalendar({date(2026, 6, 8)})
    start = dt("2026-06-05T09:00")
    end = calendar.add(start, 960)
    assert end == dt("2026-06-09T18:00")
    assert calendar.between(start, end) == 960
    assert calendar.between(end, start) == -960
    assert calendar.add(end, -960) == start


def test_weekend_snap_is_directional():
    calendar = WorkCalendar()
    assert calendar.shift_date(dt("2026-06-05T09:00"), 1) == dt("2026-06-08T09:00")
    assert calendar.shift_date(dt("2026-06-08T09:00"), -1) == dt("2026-06-05T09:00")


def test_move_propagates_without_stretching():
    p = chain()
    p.move("a", 3)
    assert p.tasks["a"].start == dt("2026-06-08T09:00")
    assert p.tasks["b"].start == dt("2026-06-09T09:00")
    assert p.tasks["c"].start == dt("2026-06-11T09:00")
    assert [t.duration for t in p.tasks.values()] == [480, 960, 480]


def test_linked_body_and_start_resize_are_locked():
    p = chain()
    before = p.to_dict()
    with pytest.raises(ScheduleError, match="предшествен"):
        p.move("b", 3)
    with pytest.raises(ScheduleError, match="предшествен"):
        p.resize("b", "start", 1)
    assert p.to_dict() == before


def test_right_resize_keeps_start_progress_and_effort():
    p = chain()
    p.tasks["a"].progress = 35
    p.tasks["a"].effort = 2
    p.resize("a", "end", 3)
    assert p.tasks["a"].start == dt("2026-06-05T09:00")
    assert p.tasks["a"].duration == 960
    assert p.tasks["a"].progress == 35
    assert p.tasks["a"].effort == 2
    assert p.tasks["b"].start == dt("2026-06-09T09:00")


@pytest.mark.parametrize("kind,expected", [
    ("FS", "2026-06-08T09:00"), ("SS", "2026-06-05T09:00"),
    ("FF", "2026-06-05T09:00"), ("SF", "2026-06-04T09:00"),
])
def test_four_dependency_types(kind, expected):
    p = chain()
    p.dependencies.clear()
    p.tasks["b"].duration = 480
    p.add_link("a", "b", kind)
    assert p.tasks["b"].start == dt(expected)


def test_lag_and_multiple_predecessors():
    p = chain()
    p.dependencies.clear()
    p.add_link("a", "b", "FS", 480)
    assert p.tasks["b"].start == dt("2026-06-09T09:00")
    p.add_link("c", "b", "FS")
    assert p.tasks["b"].start == dt("2026-06-11T09:00")


def test_cycles_self_links_and_duplicates_are_atomic():
    p = chain()
    before = p.to_dict()
    for source, target in [("c", "a"), ("a", "a"), ("a", "b")]:
        with pytest.raises(ScheduleError):
            p.add_link(source, target)
        assert p.to_dict() == before


def test_group_moves_children_once_and_propagates():
    p = sample_project()
    starts = {key: task.start for key, task in p.tasks.items() if task.kind != "group"}
    durations = {key: task.duration for key, task in p.tasks.items()}
    p.move("planning", 7)
    for key, value in starts.items():
        assert p.tasks[key].start == value + timedelta(days=7)
    assert {key: task.duration for key, task in p.tasks.items()} == durations
    assert p.span("planning")[0] == dt("2025-12-08T09:00")


def test_milestone_has_no_duration_and_can_drive_successor():
    p = Project(tasks={
        "m": Task("m", "Milestone", dt("2026-06-05T09:00"), 0, kind="milestone"),
        "t": Task("t", "Task", dt("2026-06-08T09:00")),
    })
    p.add_link("m", "t")
    assert p.span("m")[0] == p.span("m")[1]
    assert p.tasks["t"].start == p.tasks["m"].start


def test_delete_group_removes_descendants_and_links():
    p = sample_project()
    descendants = {t.id for t in p.descendants("planning")}
    p.remove("planning")
    assert not descendants.intersection(p.tasks)
    assert not any(d.source in descendants or d.target in descendants for d in p.dependencies)
    p.validate()


def test_round_trip_and_invalid_hierarchy():
    p = sample_project()
    assert Project.from_dict(p.to_dict()).to_dict() == p.to_dict()
    p.tasks["planning"].parent = "planning"
    with pytest.raises(ScheduleError, match="иерархия"):
        p.validate()


def test_invalid_imports():
    data = sample_project().to_dict()
    data["tasks"].append(data["tasks"][0])
    with pytest.raises(ScheduleError, match="Повторяющийся"):
        Project.from_dict(data)


def test_noop_move_and_resize():
    p = sample_project()
    before = p.to_dict()
    p.move("sensor", 0)
    p.resize("sensor", "end", 0)
    assert p.to_dict() == before
