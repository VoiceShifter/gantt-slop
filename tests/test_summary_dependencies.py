from datetime import date, datetime, time

import pytest

from gantt_desktop.domain import Project, ScheduleError, Task


def at(day, hour=9):
    return datetime.combine(date(2025, 12, day), time(hour))


def grouped_project():
    tasks = [
        Task("a", "Source", at(1), 0, kind="group"),
        Task("a1", "First source", at(1), parent="a"),
        Task("a2", "Last source", at(3), parent="a"),
        Task("b", "Target", at(8), 0, kind="group"),
        Task("b1", "First target", at(8), parent="b", effort=3),
        Task("b2", "Last target", at(10), 960, parent="b", effort=7),
        Task("c", "Downstream", at(17)),
    ]
    return Project(tasks={t.id: t for t in tasks})


def test_summary_fs_shifts_children_without_stretching():
    p = grouped_project()
    p.add_link("a", "b")
    assert p.tasks["b1"].start == at(4)
    assert p.tasks["b2"].start == at(8)
    assert p.span("b") == (at(4), at(9, 18))
    assert [(p.tasks[k].duration, p.tasks[k].effort) for k in ("b1", "b2")] == [(480, 3), (960, 7)]
    assert Project.from_dict(p.to_dict()).to_dict() == p.to_dict()


@pytest.mark.parametrize("kind", ["FS", "SS", "FF", "SF"])
@pytest.mark.parametrize("lag", [-60, 60])
def test_summary_relationship_types_and_working_hour_lag(kind, lag):
    p = grouped_project()
    duration = p.calendar.between(*p.span("b"))
    p.add_link("a", "b", kind, lag)
    source = p.span("a")[kind[0] == "F"]
    target = p.span("b")[kind[1] == "F"]
    assert target == p.calendar.add(source, lag)
    assert p.calendar.between(*p.span("b")) == duration
    assert p.calendar.between(p.tasks["b1"].start, p.tasks["b2"].start) == 960


def test_group_child_changes_propagate_through_both_summaries():
    p = grouped_project()
    p.add_link("a", "b")
    p.add_link("b", "c")
    assert p.tasks["c"].start == at(10)
    p.resize("a2", "end", 1)
    assert p.tasks["b1"].start == at(5)
    assert p.tasks["b2"].start == at(9)
    assert p.tasks["c"].start == at(11)
    p.resize("a2", "end", -1)
    assert p.tasks["b1"].start == at(4)
    assert p.tasks["c"].start == at(10)


def test_internal_and_external_child_constraints_survive_group_alignment():
    p = grouped_project()
    p.add_link("b1", "b2")
    p.add_link("a", "b")
    assert p.tasks["b1"].start == at(4)
    assert p.tasks["b2"].start == at(5)
    p.tasks["c"].start = at(15)
    p.add_link("c", "b2")
    assert p.tasks["b1"].start == at(4)
    assert p.tasks["b2"].start == at(16)
    assert p.span("b")[0] == at(4)


def test_nested_group_constraint_cannot_pull_children_before_parent_anchor():
    p = grouped_project()
    p.tasks["outer"] = Task("outer", "Outer", at(8), 0, kind="group")
    p.tasks["b"].parent = "outer"
    p.add_link("a", "outer")
    p.add_link("a1", "b", "SS")
    assert p.span("outer")[0] == at(4)
    assert p.span("b")[0] == at(4)


@pytest.mark.parametrize("source,target", [("a", "a1"), ("a1", "a")])
def test_group_and_descendant_cannot_be_linked(source, target):
    p = grouped_project()
    before = p.to_dict()
    with pytest.raises(ScheduleError):
        p.add_link(source, target)
    assert p.to_dict() == before


def test_dependency_cycle_through_summary_members_is_rejected_atomically():
    p = grouped_project()
    p.add_link("a", "b")
    before = p.to_dict()
    with pytest.raises(ScheduleError, match="цикл"):
        p.add_link("b2", "a2")
    assert p.to_dict() == before


def test_linked_group_and_children_cannot_move_but_enclosing_group_can():
    p = grouped_project()
    p.add_link("a", "b")
    for task_id in ("b", "b1", "b2"):
        before = p.to_dict()
        with pytest.raises(ScheduleError, match="предшествен"):
            p.move(task_id, 7)
        assert p.to_dict() == before
    p.tasks["root"] = Task("root", "Enclosing", at(1), 0, kind="group")
    p.tasks["a"].parent = p.tasks["b"].parent = "root"
    p.move("root", 7)
    assert p.tasks["a1"].start == at(8)
    assert p.tasks["b1"].start == at(11)


def test_empty_group_is_a_schedulable_dependency_endpoint():
    p = grouped_project()
    p.tasks["empty"] = Task("empty", "Empty", at(1), 0, kind="group")
    p.add_link("a2", "empty")
    p.add_link("empty", "c")
    assert p.span("empty") == (at(4), at(4))
    assert p.tasks["c"].start == at(4)


@pytest.mark.parametrize("kind", ["FS", "FF"])
def test_external_child_predecessor_can_move_both_ways_without_group_drift(kind):
    p = grouped_project()
    p.add_link("a", "b", kind)
    p.add_link("c", "b2")
    before = p.to_dict()
    free_start = p.tasks["b1"].start
    for _ in range(3):
        p.move("c", 7)
        assert p.tasks["b1"].start == free_start
        p.move("c", -7)
        assert p.to_dict() == before
    p.resize("a2", "end", 1)
    p.resize("a2", "end", -1)
    assert p.to_dict() == before


def test_reparenting_into_a_linked_group_recalculates_its_schedule():
    p = grouped_project()
    p.add_link("a", "b")
    p.tasks["c"].start = at(1)
    p.relocate("c", "b", "inside")
    assert p.span("b")[0] == at(4)
    assert p.tasks["c"].start == at(4)


def test_reparenting_cannot_create_an_ancestor_dependency():
    p = grouped_project()
    p.add_link("a", "b")
    before = p.to_dict()
    with pytest.raises(ScheduleError):
        p.relocate("a", "b", "inside")
    assert p.to_dict() == before


def test_deleting_a_summary_source_child_updates_its_successor():
    p = grouped_project()
    p.add_link("a", "b", "SS")
    p.remove("a1")
    assert p.span("a")[0] == at(3)
    assert p.span("b")[0] == at(3)
