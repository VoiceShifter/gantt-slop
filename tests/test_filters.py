from copy import deepcopy
from datetime import date, datetime

import pytest

from gantt_desktop.controller import Controller
from gantt_desktop.domain import Dependency, Project, Resource, Task, TaskFilter
from gantt_desktop.exporting import ExportDocument, ExportOptions, ExportSource


def filter_project():
    def dt(day):
        return datetime.fromisoformat(f"2025-12-{day:02d}T09:00")
    project = Project(tasks={
        "g": Task("g", "Этап", dt(1), 0, kind="group"),
        "nested": Task("nested", "Вложенный", dt(1), 0, parent="g", kind="group"),
        "a": Task("a", "Альфа", dt(1), parent="nested", priority="high", color="#AABBCC", resource_ids=["r1"]),
        "b": Task("b", "Бета", dt(2), parent="nested", progress=50, status="in_progress", resource_ids=["r2"]),
        "m": Task("m", "Приёмка", dt(2), 0, parent="g", kind="milestone", progress=100,
                  status="closed", color="#aabbcc", resource_ids=["r1"]),
        "c": Task("c", "Гамма", dt(3), priority="high", notes="Примечание"),
        "empty": Task("empty", "Пусто", dt(1), 0, kind="group"),
    }, resources={"r1": Resource("r1", "Алексей"), "r2": Resource("r2", "Борис")},
        dependencies=[Dependency("ab", "a", "b")])
    project.validate()
    return project


def visible(c):
    return {row["taskId"] for row in c._rows.records if row["rowKind"] == "task"}


@pytest.mark.parametrize("values, expected", [
    ({"kinds": ["task"]}, {"a", "b", "c"}),
    ({"kinds": ["milestone"]}, {"m"}),
    ({"kinds": ["task", "milestone"]}, {"a", "b", "c", "m"}),
    ({"resources": ["r1"]}, {"a", "m"}),
    ({"resources": ["r1", "r2"]}, {"a", "b", "m"}),
    ({"unassigned": True}, {"c"}),
    ({"resources": ["r2"], "unassigned": True}, {"b", "c"}),
    ({"statuses": ["open"]}, {"a", "c"}),
    ({"statuses": ["in_progress", "closed"]}, {"b", "m"}),
    ({"priorities": ["high"]}, {"a", "c"}),
    ({"colors": ["#aAbBcC"]}, {"a", "m"}),
    ({"ranges": {"span": ["2025-12-01", "2025-12-02"]}}, {"a", "b", "m"}),
    ({"ranges": {"start": ["2025-12-02", "2025-12-02"]}}, {"b", "m"}),
    ({"ranges": {"end": ["2025-12-02", ""]}}, {"b", "m", "c"}),
    ({"ranges": {"end": ["", "2025-12-01"]}}, {"a"}),
    ({"resources": ["r1"], "kinds": ["milestone"], "statuses": ["closed"]}, {"m"}),
    ({"resources": ["r1"], "kinds": ["milestone"], "priorities": ["high"]}, set()),
])
def test_choice_or_field_and_and_inclusive_ranges(values, expected):
    project = filter_project()
    criteria = TaskFilter(**values)
    criteria.validate()
    assert {task.id for task in project.tasks.values() if criteria.matches(project, task)} == expected


def test_multiple_assignees_use_any_selected_resource():
    project = filter_project()
    project.assign_resources("b", ["r1", "r2"])
    assert TaskFilter(resources=["r1"]).matches(project, project.tasks["b"])
    assert not TaskFilter(unassigned=True).matches(project, project.tasks["b"])


def test_overlap_is_not_containment_and_date_conditions_combine():
    project = filter_project()
    project.tasks["a"].duration = 3 * 480
    assert TaskFilter(ranges={"span": ["2025-12-02", "2025-12-02"]}).matches(project, project.tasks["a"])
    assert not TaskFilter(ranges={"span": ["2025-12-02", "2025-12-02"],
                                  "start": ["2025-12-02", ""]}).matches(project, project.tasks["a"])
    assert TaskFilter(ranges={"span": ["0001-01-01", "9999-12-31"]}).matches(project, project.tasks["a"])


@pytest.mark.parametrize("values", [
    {"query": None}, {"quick": "unknown"}, {"unassigned": 1}, {"kinds": ["group"]},
    {"kinds": ["task", "task"]}, {"kinds": "task"}, {"resources": [""]}, {"resources": [False]},
    {"statuses": ["unknown"]}, {"priorities": ["urgent"]}, {"colors": ["red"]},
    {"ranges": []}, {"ranges": {"deadline": ["2025-12-01", ""]}}, {"ranges": {"start": ["", ""]}},
    {"ranges": {"start": ["2025-12-01"]}}, {"ranges": {"start": [None, "2025-12-01"]}},
    {"ranges": {"start": ["2025-12-03", "2025-12-01"]}},
    {"ranges": {"span": ["2025-02-30", ""]}}, {"ranges": {"span": ["20251201", ""]}},
])
def test_invalid_criteria_are_rejected(values):
    with pytest.raises(ValueError):
        TaskFilter(**values).validate()


def test_filtering_preserves_history_hierarchy_outlines_collapse_and_dates(qapp):
    c = Controller(filter_project())
    before = c.project.to_dict()
    c.expandAll(False)
    assert c.apply_filter(TaskFilter(resources=["r1"], kinds=["task"]))
    assert visible(c) == {"g", "nested", "a"}
    assert {r["taskId"]: r["outline"] for r in c._rows.records if r["rowKind"] == "task"} == {
        "g": "1", "nested": "1.1", "a": "1.1.1"}
    assert not any(r["rowKind"] == "add" for r in c._rows.records)
    assert c.links == []  # A hidden endpoint must not be redirected to its context group.
    assert c.project.to_dict() == before and not c.canUndo and not c.dirty
    c.clearFilters()
    assert not c.filterActive and visible(c) == {"g", "c", "empty"}
    assert c.project.to_dict() == before


def test_group_search_does_not_bypass_other_conditions_or_quick_filter(qapp):
    c = Controller(filter_project())
    assert c.apply_filter(TaskFilter(query="ЭТАП", kinds=["task"], statuses=["open"]))
    assert visible(c) == {"g", "nested", "a"}
    assert c.apply_filter(TaskFilter(query="Этап", quick="complete"))
    assert visible(c) == {"g", "m"}
    c.search("примечание")
    c.setFilter("all")
    assert visible(c) == {"c"}


def test_overdue_uses_current_day_and_deadline_with_other_criteria(qapp, monkeypatch):
    monkeypatch.setattr("gantt_desktop.controller.local_today", lambda: date(2025, 12, 2))
    c = Controller(filter_project())
    c.project.tasks["c"].deadline = date(2025, 12, 1)
    assert c.apply_filter(TaskFilter(quick="overdue", priorities=["high"]))
    assert visible(c) == {"g", "nested", "a", "c"}
    assert c.apply_filter(TaskFilter(quick="overdue", resources=["r2"]))
    assert visible(c) == set()


def test_bulk_selection_and_deletion_cannot_touch_hidden_descendants(qapp):
    c = Controller(filter_project())
    c.setBulkMode(True)
    c.setAllChecked(True)
    assert c.apply_filter(TaskFilter(resources=["r1"], kinds=["task"]))
    assert not c.checkedIds
    c.toggleChecked("g")
    assert set(c.checkedIds) == {"g", "nested", "a"}
    assert c.bulkDeleteCount == 1
    assert c.deleteChecked()
    assert set(c.project.tasks) == {"g", "nested", "b", "m", "c", "empty"}
    c.undo()
    assert visible(c) == {"g", "nested", "a"}


def test_named_presets_are_deep_copied_atomic_undoable_and_persisted(qapp, tmp_path):
    c = Controller(filter_project())
    before = c.project.to_dict()
    criteria = TaskFilter(resources=["r1"])
    presets = {"Клиент": criteria}
    assert c.apply_filter(criteria, presets)
    after = c.project.to_dict()
    assert after["version"] == 9 and c.canUndo and c.dirty
    criteria.resources.append("r2")
    presets.clear()
    assert c.filter_state().resources == ["r1"] and c.project.to_dict() == after
    c.undo()
    assert c.project.to_dict() == before and c.filterActive  # Undo is document history, not view history.
    c.redo()
    assert c.project.to_dict() == after
    path = tmp_path / "filters.gantt.json"
    assert c.save_path(path) and c.load_path(path)
    assert c.project.to_dict() == after and not c.filterActive
    assert c.apply_filter(c.project.saved_filters["Клиент"])
    assert not c.dirty and c.filter_state().resources == ["r1"]
    state = c.filter_state()
    state.resources.clear()
    assert c.filter_state().resources == ["r1"]
    assert c.apply_filter(TaskFilter(), {})
    assert not c.project.saved_filters and c.canUndo
    c.undo()
    assert c.project.saved_filters


@pytest.mark.parametrize("name", ["", " ", " padded ", None])
def test_bad_preset_names_reject_atomically(qapp, name):
    c = Controller(filter_project())
    before = c.project.to_dict()
    assert not c.apply_filter(TaskFilter(kinds=["milestone"]), {name: TaskFilter()})
    assert c.project.to_dict() == before and not c.filterActive and not c.canUndo


def test_invalid_apply_never_saves_presets_or_changes_view(qapp):
    c = Controller(filter_project())
    assert c.apply_filter(TaskFilter(kinds=["milestone"]))
    state, before = c.filter_state(), c.project.to_dict()
    assert not c.apply_filter(TaskFilter(colors=["bad"]), {"Preset": TaskFilter()})
    assert not c.apply_filter(TaskFilter(), {"Name": TaskFilter(), "name": TaskFilter()})
    assert c.filter_state() == state and c.project.to_dict() == before


def test_missing_resources_stay_selected_instead_of_broadening_saved_filters(qapp):
    c = Controller(filter_project())
    criteria = TaskFilter(resources=["r1"])
    assert c.apply_filter(criteria, {"Only r1": criteria})
    assert c.edit("Remove", lambda p: p.remove_resource("r1"))
    assert c.project.saved_filters["Only r1"].resources == ["r1"]
    assert visible(c) == set() and c.filterActive
    c.undo()
    assert visible(c) == {"g", "nested", "a", "m"}


@pytest.mark.parametrize("version", range(1, 10))
def test_older_schemas_default_to_no_saved_filters(version):
    data = filter_project().to_dict()
    data["version"] = version
    del data["saved_filters"]
    restored = Project.from_dict(data)
    assert restored.saved_filters == {} and restored.to_dict()["version"] == 9


def test_visible_export_freezes_filtered_rows_but_whole_tree_keeps_everything(qapp):
    c = Controller(filter_project())
    c.apply_filter(TaskFilter(kinds=["milestone"]))
    source = ExportSource.capture(c)
    assert source.visible_ids == {"g", "m"}
    document = ExportDocument(source, ExportOptions(scope="visible"))
    assert {row["taskId"] for row in document.rows} == {"g", "m"}
    saved = deepcopy(source.project.to_dict())
    c.clearFilters()
    assert source.visible_ids == {"g", "m"} and source.project.to_dict() == saved
    full = ExportDocument(source, ExportOptions(scope="all"))
    assert {row["taskId"] for row in full.rows} == set(c.project.tasks)
