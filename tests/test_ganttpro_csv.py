import csv
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path

import pytest
from test_export_ui import choose, open_export

from gantt_desktop.controller import Controller
from gantt_desktop.domain import Dependency, Project, Resource, Task
from gantt_desktop.exporting import (
    GANTTPRO_COLUMNS,
    ExportDocument,
    ExportOptions,
    ExportSource,
    export_file,
)
from gantt_desktop.ganttpro_csv import HEADERS, read_project_csv

FIXTURE = Path(__file__).parent / "fixtures" / "ganttpro-task-table.csv"


def test_ganttpro_preset_matches_supplied_23_column_table_and_keeps_real_predecessors(qapp, tmp_path):
    imported = read_project_csv(FIXTURE)
    c = Controller(imported.project)
    c.search("сенсора")
    source = ExportSource.capture(c)
    before = deepcopy(source.rows)
    document = ExportDocument(source, ExportOptions(format="ganttpro_csv", scope="visible", content="chart",
                              start=date(2030, 1, 1), end=date(2020, 1, 1), critical=True, baseline=True, workload=True))
    assert document.options.columns == GANTTPRO_COLUMNS and document.options.scope == "all"
    assert document.options.content == "table" and document.analysis is None and not document.options.baseline
    assert len(document.rows) == len(c.project.tasks)
    path = tmp_path / "ganttpro.csv"
    export_file(path, document)
    assert path.read_bytes().startswith(b'\xef\xbb\xbf')
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.reader(stream))
    with FIXTURE.open(encoding="utf-8-sig", newline="") as stream:
        expected = list(csv.reader(stream))
    assert rows == expected
    assert tuple(rows[0]) == HEADERS and rows[0][2] == ""
    assert len(rows) == 21 and all(len(row) == 23 for row in rows)
    sensor = next(row for row in rows[1:] if row[3] == "Выбор сенсора")
    assert sensor[1] == "1.2" and sensor[5:7] == ["2025-12-11 09:00:00", "2025-12-15 18:00:00"]
    assert sensor[15] == "1.1" and sensor[14] == "" and sensor[20:] == ["задача", "Новый проект / Планирование", "2"]
    assert sum(bool(row[15]) for row in rows[1:]) == 14
    assert source.rows == before
    assert read_project_csv(path).project.to_dict() == imported.project.to_dict()


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "  =", "'", "'=literal"])
def test_ganttpro_csv_formula_escaping_is_literal_and_reversible(qapp, tmp_path, prefix):
    c = Controller()
    c.project.tasks["sensor"].name = prefix+"User text"
    c.project.tasks["sensor"].notes = prefix+"Notes"
    document = ExportDocument(ExportSource.capture(c), ExportOptions(format="ganttpro_csv"))
    path = tmp_path / "literal.csv"
    export_file(path, document)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        sensor = next(row for row in csv.reader(stream) if row[3].endswith("User text"))
    assert sensor[3].startswith("'") and sensor[14].startswith("'")
    restored = read_project_csv(path).project.tasks["csv-task-1.2"]
    assert restored.name == prefix+"User text" and restored.notes == prefix+"Notes"


@pytest.mark.parametrize("kind", ["FS", "SS", "FF", "SF"])
@pytest.mark.parametrize("lag", [-7, 0, 7])
def test_csv_roundtrip_retains_link_endpoint_types_signed_lags_and_minute_duration(qapp, tmp_path, kind, lag):
    p = Project("Minute plan", tasks={"a": Task("a", "A", datetime.fromisoformat("2026-01-05T09:00"), 1),
                                      "b": Task("b", "B", datetime.fromisoformat("2026-01-05T09:00"), 1)},
                dependencies=[Dependency("ab", "a", "b", kind, lag)])
    document = ExportDocument(ExportSource.capture(Controller(p)), ExportOptions(format="ganttpro_csv"))
    path = tmp_path / "typed-links.csv"
    export_file(path, document)
    other = read_project_csv(path).project
    assert other.dependencies[0].kind == kind and other.dependencies[0].lag == lag
    assert other.tasks["csv-task-1"].duration == other.tasks["csv-task-2"].duration == 1
    assert other.span("csv-task-2") == p.span("b")


def test_csv_roundtrip_preserves_quoted_comma_newline_names_and_status(qapp, tmp_path):
    names = ['Doe, Jane', 'Line\nPerson', "'=literal person"]
    p = Project("Names", tasks={"a": Task("a", "A", datetime.fromisoformat("2026-01-05T09:00"), 480, progress=100, status="closed", effort=9,
                                          resource_ids=["r0", "r1", "r2"])},
                resources={f"r{i}": Resource(f"r{i}", name) for i, name in enumerate(names)})
    path = tmp_path / "names.csv"
    export_file(path, ExportDocument(ExportSource.capture(Controller(p)), ExportOptions(format="ganttpro_csv")))
    other = read_project_csv(path).project
    task = other.tasks["csv-task-1"]
    assert [other.resources[rid].name for rid in task.resource_ids] == names
    assert task.status == "closed" and task.progress == 100 and task.effort == 9


@pytest.mark.parametrize(("field", "value"), [("ganttpro_spent_minutes", "bad"), ("ganttpro_actual_cost", "-1"),
                                               ("ganttpro_created", "not a date")])
def test_invalid_edited_source_metadata_is_rejected_before_csv_export(qapp, field, value):
    p = read_project_csv(FIXTURE).project
    p.tasks["csv-task-1.2"].custom_values[field] = value
    with pytest.raises(ValueError):
        ExportDocument(ExportSource.capture(Controller(p)), ExportOptions(format="ganttpro_csv"))


def test_native_ganttpro_preset_has_fixed_fields_and_visible_loss_warning(gui, tmp_path):
    c, window = gui
    c.search("сенсора")
    before = c.project.to_dict()
    dialog = open_export(window)
    choose(dialog.scope, "visible")
    dialog.range.setChecked(True)
    dialog.start.setDate(dialog.end.date().addDays(10))
    choose(dialog.format, "ganttpro_csv")
    dialog.update_preview()
    assert dialog.document is not None and len(dialog.document.rows) == len(c.project.tasks)
    assert tuple(column["key"] for column in dialog.document.columns) == GANTTPRO_COLUMNS
    assert tuple(column["title"] for column in dialog.document.columns) == HEADERS
    assert not dialog.scope.isEnabled() and not dialog.fields.isEnabled() and not dialog.range.isEnabled()
    assert "Предшественник" in dialog.note.text() and "23 поля" in dialog.info.text()
    assert dialog.transfer_warning.isVisible() and "не входят в схему" in dialog.transfer_warning.text()
    assert dialog.transfer_warning.parentWidget() is dialog
    assert dialog.transfer_warning.geometry().bottom() <= dialog.height()
    assert dialog.export_to(tmp_path / "native.csv")
    assert c.project.to_dict() == before and not c.dirty
    dialog.reject()
