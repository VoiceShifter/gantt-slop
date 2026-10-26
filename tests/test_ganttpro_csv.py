import csv
from copy import deepcopy
from datetime import date

import pytest
from test_export_ui import choose, open_export

from gantt_desktop.controller import Controller
from gantt_desktop.exporting import (
    GANTTPRO_COLUMNS,
    ExportDocument,
    ExportOptions,
    ExportSource,
    export_file,
)


def test_ganttpro_preset_uses_whole_hierarchy_dates_times_hours_and_manual_link_notes(qapp, tmp_path):
    c = Controller()
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
    assert not path.read_bytes().startswith(b'\xef\xbb\xbf')
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.reader(stream))
    assert len(rows) == len(c.project.tasks) and all(len(row) == 8 for row in rows)
    assert rows[0][0] == "1" and rows[0][1] == "Планирование"
    sensor = next(row for row in rows if row[1] == "Выбор сенсора")
    assert sensor[0] == "1.2" and sensor[2:6] == ["15.12.2025", "17.12.2025", "09:00", "18:00"]
    assert float(sensor[6]) == 24
    linked = next(row for row in source.rows if source.value(row, "predecessors"))
    exported = next(row for row in rows if row[1] == linked["name"])
    assert "Связи (создать вручную): " + str(source.value(linked, "predecessors")) in exported[7]
    milestone = next(row for row in rows if row[1] == "Приобретение компонентов")
    assert float(milestone[6]) == 0 and milestone[2] == milestone[3]
    assert source.rows == before


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "  ="])
def test_ganttpro_csv_keeps_formula_like_user_text_literal(qapp, tmp_path, prefix):
    c = Controller()
    c.project.tasks["sensor"].name = prefix+"User text"
    c.project.tasks["sensor"].notes = prefix+"Notes"
    document = ExportDocument(ExportSource.capture(c), ExportOptions(format="ganttpro_csv"))
    path = tmp_path / "literal.csv"
    export_file(path, document)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        sensor = next(row for row in csv.reader(stream) if row[1].endswith("User text"))
    assert sensor[1].startswith("'") and sensor[7].startswith("'")


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
    assert not dialog.scope.isEnabled() and not dialog.fields.isEnabled() and not dialog.range.isEnabled()
    assert "НЕ импортируются" in dialog.note.text() and "вручную" in dialog.info.text()
    assert dialog.transfer_warning.isVisible() and "без заголовков" in dialog.transfer_warning.text()
    assert dialog.transfer_warning.parentWidget() is dialog
    assert dialog.transfer_warning.geometry().bottom() <= dialog.height()
    assert dialog.export_to(tmp_path / "native.csv")
    assert c.project.to_dict() == before and not c.dirty
    dialog.reject()
