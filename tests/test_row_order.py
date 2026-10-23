import pytest

from gantt_desktop.domain import ScheduleError, Task
from gantt_desktop.sample import sample_project


def leaf_values(project):
    return {key: (task.start, task.duration, task.progress, task.effort, task.cost, task.assignee, task.color)
            for key, task in project.tasks.items() if task.kind != "group"}


def test_sibling_drop_changes_order_not_dates_or_links():
    project = sample_project()
    before = leaf_values(project)
    links = list(project.dependencies)
    project.relocate("scenario", "sensor", "after")
    assert [t.id for t in project.children("planning")][:2] == ["sensor", "scenario"]
    assert leaf_values(project) == before and project.dependencies == links
    project.relocate("scenario", "sensor", "before")
    assert [t.id for t in project.children("planning")][:2] == ["scenario", "sensor"]


def test_drop_into_group_inserts_first_and_updates_derived_totals():
    project = sample_project()
    before = leaf_values(project)
    project.relocate("scenario", "preparation", "inside")
    assert project.children("preparation")[0].id == "scenario"
    assert project.tasks["scenario"].parent == "preparation"
    assert sum(t.effort for t in project.leaves("planning")) == 48
    assert sum(t.effort for t in project.leaves("preparation")) == 72
    assert project.span("preparation")[0].date().isoformat() == "2025-12-01"
    assert leaf_values(project) == before
    project.validate()


def test_append_supports_group_end_and_root():
    project = sample_project()
    project.relocate("scenario", "preparation", "append")
    assert project.children("preparation")[-1].id == "scenario"
    project.relocate("scenario", "", "append")
    assert project.children()[-1].id == "scenario"
    assert project.tasks["scenario"].parent == ""


def test_moving_summary_keeps_its_subtree():
    project = sample_project()
    before = leaf_values(project)
    children = [t.id for t in project.descendants("case")]
    project.relocate("case", "planning", "inside")
    assert project.children("planning")[0].id == "case"
    assert [t.id for t in project.descendants("case")] == children
    assert leaf_values(project) == before
    project.validate()


@pytest.mark.parametrize("source,target,mode", [
    ("planning", "sensor", "after"), ("planning", "planning", "inside"),
    ("scenario", "sensor", "inside"), ("scenario", "", "inside"),
    ("unknown", "sensor", "before"), ("scenario", "unknown", "after"),
    ("scenario", "sensor", "unknown"),
])
def test_invalid_drops_are_atomic(source, target, mode):
    project = sample_project()
    before = project.to_dict()
    with pytest.raises(ScheduleError):
        project.relocate(source, target, mode)
    assert project.to_dict() == before


def test_semantic_noop_preserves_raw_order_even_for_new_groups():
    project = sample_project()
    project.tasks["new-group"] = Task("new-group", "New", project.tasks["scenario"].start, duration=0, kind="group")
    before = project.to_dict()
    project.relocate("new-group", "", "append")
    assert project.to_dict() == before
    project.relocate("scenario", "planning", "inside")
    assert project.to_dict() == before
    project.relocate("scenario", "scenario", "after")
    assert project.to_dict() == before
