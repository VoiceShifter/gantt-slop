import csv
from copy import deepcopy
from datetime import datetime

import pytest
from PySide6.QtWidgets import QFileDialog

from gantt_desktop.controller import Controller
from gantt_desktop.domain import CustomField, Project, ScheduleError, Task

KINDS = ["text", "number", "date", "select", "checkbox", "color", "multi", "people", "labels"]


def field(kind, key="extra", name="Extra"):
    return CustomField(key, name, kind, ["Todo", "Done"] if kind in {"select", "multi"} else [],
                       "sum" if kind == "number" else "")


def project():
    p = Project()
    start = datetime.fromisoformat("2026-01-05T09:00")
    p.tasks = {"g": Task("g", "Group", start, 0, kind="group"),
               "a": Task("a", "A", start, parent="g"),
               "h": Task("h", "Nested", start, 0, parent="g", kind="group"),
               "b": Task("b", "B", start, parent="h"),
               "c": Task("c", "C", start)}
    p.ensure_resource("Alice")
    return p


def value_for(p, kind):
    return {"text": "Notes <plain>", "number": 0, "date": "2026-06-10", "select": "Done",
            "checkbox": False, "color": "#aBc123", "multi": ["Done", "Todo"],
            "people": [next(iter(p.resources))], "labels": ["One", "Two"]}[kind]


@pytest.mark.parametrize("kind", KINDS)
def test_typed_values_round_trip_and_clear_without_schedule_or_assignment_changes(kind):
    p = project()
    definition = field(kind)
    p.save_custom_field(definition)
    before = [(t.start, t.duration, t.effort, list(t.resource_ids)) for t in p.tasks.values()]
    value = value_for(p, kind)
    p.set_custom_value("a", "extra", value)
    p.validate()
    expected = value.lower() if kind == "color" else ["Todo", "Done"] if kind == "multi" else value
    assert p.custom_value("a", "extra") == expected
    data = p.to_dict()
    assert data["version"] == 4
    restored = Project.from_dict(data)
    assert restored.to_dict() == data
    assert [(t.start, t.duration, t.effort, t.resource_ids) for t in p.tasks.values()] == before
    p.set_custom_value("a", "extra", None)
    assert "extra" not in p.tasks["a"].custom_values


@pytest.mark.parametrize(("kind", "value"), [
    ("number", True), ("number", "1.5"), ("number", float("inf")), ("number", float("nan")), ("number", 10 ** 1000),
    ("checkbox", 0), ("checkbox", "false"), ("date", "2026-02-30"), ("date", "10.06.2026"),
    ("select", "missing"), ("multi", ["missing"]), ("multi", "Done"),
    ("people", ["unknown"]), ("labels", [""]), ("color", "red"), ("text", ["text"]),
])
def test_invalid_typed_values_are_rejected_without_mutation(kind, value):
    p = project()
    p.save_custom_field(field(kind))
    before = p.to_dict()
    with pytest.raises(ValueError):
        p.set_custom_value("a", "extra", value)
    assert p.to_dict() == before


def test_numeric_rollups_use_terminal_values_once_and_ignore_unset_not_zero():
    p = project()
    p.save_custom_field(field("number"))
    p.set_custom_value("a", "extra", 0)
    p.set_custom_value("b", "extra", 10)
    p.set_custom_value("c", "extra", 20)
    assert p.custom_value("h", "extra") == 10
    assert p.custom_value("g", "extra") == 10
    assert p.custom_value("", "extra") == 30
    p.save_custom_field(CustomField("extra", "Extra", "number", aggregate="average"))
    assert p.custom_value("g", "extra") == 5
    assert p.custom_value("", "extra") == 10
    with pytest.raises(ScheduleError, match="вычисляется"):
        p.set_custom_value("g", "extra", 123)
    p.relocate("b", "", "append")
    assert p.custom_value("g", "extra") == 0
    assert p.custom_value("", "extra") == 10


def test_definition_validation_and_used_options_are_not_silently_removed():
    p = project()
    with pytest.raises(ScheduleError):
        p.save_custom_field(CustomField("bad", "Bad", "select"))
    p.save_custom_field(field("select"))
    p.set_custom_value("a", "extra", "Done")
    before = p.to_dict()
    for definition in (CustomField("extra", "Extra", "select", ["Todo"]),
                       CustomField("extra", "Extra", "text"),
                       CustomField("other", "EXTRA"),
                       CustomField("bad", "Bad", "multi", ["A", "a"])):
        with pytest.raises(ScheduleError):
            p.save_custom_field(definition)
        assert p.to_dict() == before
    p.save_custom_field(CustomField("extra", "Renamed", "select", ["Todo", "Done", "Review"]))
    assert p.tasks["a"].custom_values["extra"] == "Done"
    p.remove_custom_field("extra")
    assert not p.custom_fields and not p.tasks["a"].custom_values


def test_snapshot_does_not_alias_values_or_definition_options():
    p = project()
    p.save_custom_field(field("multi"))
    p.set_custom_value("a", "extra", ["Done"])
    snapshot = p.to_dict()
    before = deepcopy(snapshot)
    restored = Project.from_dict(snapshot)
    values = restored.tasks["a"].custom_values["extra"]
    assert isinstance(values, list)
    values.append("Todo")
    restored.custom_fields["extra"].options.append("Review")
    assert snapshot == before
    assert p.to_dict() == before


def test_people_fields_follow_resource_renames_and_cleanup_not_workload():
    p = project()
    p.save_custom_field(field("people"))
    key = next(iter(p.resources))
    p.set_custom_value("a", "extra", [key])
    assert p.tasks["a"].resource_ids == [] and p.tasks["a"].effort == 0
    p.update_resource(key, "Renamed", 4, {0, 1})
    assert p.custom_fields["extra"].display(p.custom_value("a", "extra"), p.resources) == "Renamed"
    p.remove_resource(key)
    assert "extra" not in p.tasks["a"].custom_values
    p.validate()


@pytest.mark.parametrize("version", [1, 2, 3])
def test_existing_schemas_without_custom_data_remain_importable(version):
    data = project().to_dict()
    data["version"] = version
    data.pop("custom_fields")
    for task in data["tasks"]:
        task.pop("custom_values")
    restored = Project.from_dict(data)
    assert not restored.custom_fields
    assert restored.to_dict()["version"] == 4


@pytest.mark.parametrize("damage", ["unknown-field", "duplicate-field", "invalid-value"])
def test_invalid_schema_four_data_is_rejected(damage):
    p = project()
    p.save_custom_field(field("checkbox"))
    data = p.to_dict()
    if damage == "unknown-field":
        data["tasks"][1]["custom_values"] = {"missing": True}
    elif damage == "duplicate-field":
        data["custom_fields"].append(deepcopy(data["custom_fields"][0]))
    else:
        data["tasks"][1]["custom_values"] = {"extra": "false"}
    with pytest.raises(ScheduleError):
        Project.from_dict(data)


def test_controller_history_noops_delete_restore_and_resource_cleanup(qapp):
    c = Controller(project())
    before = c.project.to_dict()
    key = c.saveCustomField("", "Extra", "people", [], "")
    assert key and c.dirty
    resource = next(iter(c.project.resources))
    assert c.setCustomValue("a", key, [resource])
    saved = c.project.to_dict()
    index = c._history_index
    assert c.setCustomValue("a", key, [resource]) and c._history_index == index
    assert c.saveCustomField(key, "Extra", "people", [], "") == key and c._history_index == index
    assert c.removeResource(resource)
    assert key not in c.project.tasks["a"].custom_values
    c.undo()
    assert c.project.to_dict() == saved
    assert c.removeCustomField(key)
    c.undo()
    assert c.project.to_dict() == saved
    c.undo()
    c.undo()
    assert c.project.to_dict() == before and not c.dirty
    c.redo()
    assert key in c.project.custom_fields


def test_custom_fields_persist_export_and_rejected_edits_keep_history(qapp, tmp_path, monkeypatch):
    c = Controller(project())
    number = c.saveCustomField("", "Budget", "number", [], "sum")
    flag = c.saveCustomField("", "Approved", "checkbox", [], "")
    assert c.setCustomValue("a", number, 0)
    assert c.setCustomValue("b", number, 7.5)
    assert c.setCustomValue("a", flag, False)
    before = c.project.to_dict()
    index = c._history_index
    assert not c.setCustomValue("a", number, "bad")
    assert c.project.to_dict() == before and c._history_index == index
    path = tmp_path / "fields.gantt.json"
    assert c.save_path(path)
    restored = Controller()
    assert restored.load_path(path) and restored.project.to_dict() == before
    assert not restored.dirty
    assert restored.record("g")["customValues"][number] == 7.5
    assert restored.record("a")["customTexts"][flag] == "Нет"
    csv_path = tmp_path / "fields.csv"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(csv_path), ""))
    c.exportCsv()
    rows = list(csv.reader(csv_path.read_text(encoding="utf-8-sig").splitlines()))
    assert rows[0][-2:] == ["Budget", "Approved"]
    assert next(row for row in rows if row[0] == "Group")[-2] == "7.5"
    assert next(row for row in rows if row[0] == "A")[-2:] == ["0", "Нет"]


def test_multi_option_order_is_canonical_and_reordering_definition_is_atomic():
    p = project()
    p.save_custom_field(field("multi"))
    p.set_custom_value("a", "extra", ["Done", "Todo", "Done"])
    assert p.tasks["a"].custom_values["extra"] == ["Todo", "Done"]
    p.save_custom_field(CustomField("extra", "Extra", "multi", ["Done", "Todo"]))
    assert p.tasks["a"].custom_values["extra"] == ["Done", "Todo"]


def test_nonfinite_numeric_rollups_are_rejected_on_import():
    p = project()
    p.save_custom_field(field("number"))
    p.set_custom_value("a", "extra", 1e308)
    p.set_custom_value("b", "extra", 1e308)
    with pytest.raises(ScheduleError, match="итог"):
        Project.from_dict(p.to_dict())
    p.custom_fields["extra"].aggregate = "average"
    p.validate()
    assert p.custom_value("g", "extra") == 1e308
