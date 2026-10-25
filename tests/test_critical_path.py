from datetime import datetime, timedelta
from itertools import product
from random import Random

import pytest

from gantt_desktop.critical_path import AnalysisError, analyze
from gantt_desktop.domain import (
    CalendarException,
    Dependency,
    Project,
    ResourceException,
    Task,
    WorkCalendar,
)

BASE = datetime.fromisoformat("2026-01-05T09:00")


def plan(items, links=()):
    calendar = WorkCalendar()
    p = Project(tasks={key: Task(key, key, calendar.normalize(calendar.add(BASE, start)), duration,
                                 kind="task" if duration else "milestone") for key, start, duration in items})
    p.dependencies = [Dependency(str(i), source, target, kind, lag) for i, (source, target, kind, lag) in enumerate(links)]
    p.validate()
    return p


def oracle(p):
    """Independent exhaustive schedules: no CPM passes or witness expansion."""
    members = {key: p.dependency_members(key) for key in p.tasks}
    nodes = [key for key in p.tasks if members[key] == {key}]
    actual = {key: p.calendar.between(BASE, p.tasks[key].start) for key in nodes}
    duration = {key: p.tasks[key].duration for key in nodes}
    horizon = max(actual[key] + duration[key] for key in nodes)
    best = dict.fromkeys(p.tasks, -1)
    link_best = dict.fromkeys((link.id for link in p.dependencies), -1)
    for values in product(*(range(actual[key], horizon-duration[key]+1) for key in nodes)):
        starts = dict(zip(nodes, values, strict=True))
        def endpoint(key, end, starts=starts):
            return max(starts[k] + duration[k] for k in members[key]) if end else min(starts[k] for k in members[key])
        margins = {link.id: endpoint(link.target, link.kind[1] == "F") - endpoint(link.source, link.kind[0] == "F") - link.lag
                   for link in p.dependencies}
        if any(value < 0 for value in margins.values()):
            continue
        for key, children in members.items():
            best[key] = max(best[key], min(starts[child] - actual[child] for child in children))
        for key, value in margins.items():
            link_best[key] = max(link_best[key], value)
    return best, link_best


def test_diamond_has_real_total_float_not_just_a_predecessor_chain():
    p = plan([("a", 0, 480), ("b", 480, 480), ("c", 480, 240), ("d", 960, 480)],
             [("a", "b", "FS", 0), ("a", "c", "FS", 0), ("b", "d", "FS", 0), ("c", "d", "FS", 0)])
    before = p.to_dict()
    result = analyze(p)
    assert result.total_float == {"a": 0, "b": 0, "c": 240, "d": 0}
    assert result.critical_tasks == {"a", "b", "d"}
    assert result.critical_links == {"0", "2"}
    assert result.finish == p.span("d")[1]
    assert p.to_dict() == before


def test_manual_gaps_are_floors_not_silently_compacted():
    p = plan([("a", 0, 480), ("b", 960, 480)], [("a", "b", "FS", 0)])
    result = analyze(p)
    assert result.total_float == {"a": 480, "b": 0}
    assert not result.critical_links


@pytest.mark.parametrize("kind", ["FS", "SS", "FF", "SF"])
@pytest.mark.parametrize("lag", [-2, 0, 2])
def test_all_endpoint_types_and_signed_lags_match_exhaustive_schedules(kind, lag):
    source = 3
    duration = 2
    target = source + (duration if kind[0] == "F" else 0) - (duration if kind[1] == "F" else 0) + lag
    p = plan([("a", source, duration), ("b", target, duration), ("z", 9, 1)], [("a", "b", kind, lag)])
    expected, links = oracle(p)
    result = analyze(p)
    assert result.total_float == expected and result.link_float == links


def test_tied_summary_starts_are_jointly_critical_without_false_critical_children():
    p = plan([("a", 0, 1), ("b", 0, 1), ("z", 0, 3)])
    p.tasks["g"] = Task("g", "Group", BASE, 0, kind="group")
    p.tasks["a"].parent = p.tasks["b"].parent = "g"
    p.dependencies = [Dependency("gz", "g", "z", "SS")]
    p.validate()
    result = analyze(p)
    assert result.total_float == {"a": 2, "b": 2, "z": 0, "g": 0}
    assert result.critical_tasks == {"g", "z"} and result.critical_links == {"gz"}


def test_summary_finish_uses_actual_member_envelope_without_double_counting():
    p = plan([("a", 0, 3), ("b", 0, 1), ("z", 3, 1)])
    p.tasks["g"] = Task("g", "Group", BASE, 0, kind="group")
    p.tasks["a"].parent = p.tasks["b"].parent = "g"
    p.dependencies = [Dependency("gz", "g", "z", "FS")]
    p.validate()
    result = analyze(p)
    assert result.total_float == {"a": 0, "b": 2, "z": 0, "g": 0}
    assert result.link_float == {"gz": 0}


@pytest.mark.parametrize("seed", range(30))
def test_summary_min_max_alternatives_match_independent_brute_force(seed):
    random = Random(seed)
    values = [(key, random.randrange(3), random.randrange(1, 4)) for key in "abcd"]
    p = plan(values)
    p.tasks["g"] = Task("g", "Source group", BASE, 0, kind="group")
    p.tasks["h"] = Task("h", "Target group", BASE, 0, kind="group")
    p.tasks["a"].parent = p.tasks["b"].parent = "g"
    p.tasks["c"].parent = p.tasks["d"].parent = "h"
    for index, (source, target) in enumerate((("g", "h"), ("a", "b"), ("a", "d"))):
        kind = random.choice(["FS", "SS", "FF", "SF"])
        source_time = p.calendar.between(BASE, p.span(source)[kind[0] == "F"])
        target_time = p.calendar.between(BASE, p.span(target)[kind[1] == "F"])
        p.dependencies.append(Dependency(str(index), source, target, kind, target_time-source_time-random.randrange(3)))
    p.validate()
    expected, links = oracle(p)
    result = analyze(p)
    assert result.total_float == expected
    assert result.link_float == links


def test_calendar_exceptions_holidays_and_lunch_use_working_minutes():
    p = plan([("a", 0, 480), ("b", 480, 240)])
    p.calendar.exceptions = [CalendarException("short", BASE.date(), BASE.date(), periods=[[540, 780]])]
    p.calendar.holidays.add((BASE+timedelta(days=1)).date())
    p.tasks["a"].start = BASE
    p.tasks["b"].start = p.calendar.normalize(p.span("a")[1])
    p.dependencies = [Dependency("ab", "a", "b")]
    p.validate()
    result = analyze(p)
    assert result.total_float == {"a": 0, "b": 0}
    assert result.finish == datetime.fromisoformat("2026-01-07T18:00")


def test_resource_availability_deadlines_effort_and_status_do_not_redefine_plan_float():
    p = plan([("a", 0, 4), ("b", 1, 1)])
    before = analyze(p)
    rid = p.ensure_resource("Person").id
    p.resources[rid].exceptions = [ResourceException("leave", BASE.date(), BASE.date())]
    p.assign_resources("a", [rid], [100])
    p.tasks["a"].deadline = (BASE-timedelta(days=10)).date()
    p.tasks["a"].set_status("closed")
    assert analyze(p) == before


def test_empty_groups_nested_groups_and_milestones_are_zero_duration_endpoints():
    p = plan([("a", 0, 2), ("m", 2, 0)], [("a", "m", "FS", 0)])
    p.tasks["g"] = Task("g", "Group", BASE, 0, kind="group")
    p.tasks["e"] = Task("e", "Empty", BASE+timedelta(minutes=1), 0, parent="g", kind="group")
    p.tasks["a"].parent = "g"
    p.validate()
    result = analyze(p)
    assert result.total_float == {"a": 0, "m": 0, "g": 0, "e": 1}
    assert result.critical_links == {"0"}


def test_budget_exhaustion_never_returns_partial_false_critical_results(monkeypatch):
    p = plan([("a", 0, 1), ("b", 0, 1), ("z", 0, 3)])
    p.tasks["g"] = Task("g", "Group", BASE, 0, kind="group")
    p.tasks["a"].parent = p.tasks["b"].parent = "g"
    p.dependencies = [Dependency("gz", "g", "z", "SS")]
    monkeypatch.setattr("gantt_desktop.critical_path._WORK_LIMIT", 3)
    before = p.to_dict()
    with pytest.raises(AnalysisError, match="альтернатив"):
        analyze(p)
    assert p.to_dict() == before


def test_invalid_plan_cycles_and_nonminute_dates_fail_explicitly():
    p = plan([("a", 0, 2), ("b", 0, 1)])
    p.dependencies = [Dependency("bad", "a", "b")]
    with pytest.raises(AnalysisError, match="bad"):
        analyze(p)
    p = plan([("a", 0, 0), ("b", 0, 0)])
    p.dependencies = [Dependency("ab", "a", "b"), Dependency("reverse", "b", "a")]
    with pytest.raises(AnalysisError, match="цикл"):
        analyze(p)
    p.dependencies.clear()
    p.tasks["a"].start += timedelta(seconds=1)
    with pytest.raises(AnalysisError, match="минутной"):
        analyze(p)
    assert not analyze(Project()).critical_tasks
