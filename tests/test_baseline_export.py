import csv
from datetime import date, datetime
from zipfile import ZipFile

import pytest
from conftest import wait_until
from dialog_helpers import click_native, native_dialog, required_widget
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QCheckBox, QComboBox
from test_baselines import dt, project
from test_exporting import generated_xml, pdf_document

from gantt_desktop.controller import Controller
from gantt_desktop.domain import Project
from gantt_desktop.exporting import (
    ExportDocument,
    ExportError,
    ExportOptions,
    ExportSource,
    export_file,
)
from gantt_desktop.interchange import MSP, SS, worksheet


@pytest.mark.parametrize("format_", ["pdf", "png", "xlsx", "xml", "csv"])
def test_baseline_exports_use_frozen_selected_snapshot_and_do_not_mutate_project(qapp, tmp_path, format_):
    c = Controller(project())
    first = c.createBaseline("Original")
    assert c.moveTask("a", 7)
    assert c.createBaseline("Later")
    assert c.selectBaseline(first)
    before = c.project.to_dict()
    source = ExportSource.capture(c)
    document = ExportDocument(source, ExportOptions(format=format_, baseline=format_ in {"pdf", "png"},
                                                   columns=("name", "baselineStart", "baselineEnd", "startVariance", "endVariance")))
    row = next(row for row in source.rows if row["taskId"] == "a")
    assert source.value(row, "baselineStart") == dt("2026-01-05T09:00")
    assert source.value(row, "startVariance") == 168
    path = tmp_path / ("baseline."+format_)
    export_file(path, document)
    assert path.stat().st_size > 100
    if format_ == "csv":
        rows = list(csv.reader(path.read_text(encoding="utf-8-sig").splitlines()))
        saved = next(row for row in rows if row[0] == "A")
        assert saved[1] == "2026-01-05T09:00:00" and float(saved[3]) == 168
    elif format_ == "xlsx":
        with ZipFile(path) as archive:
            sheet = generated_xml(archive.read("xl/worksheets/sheet1.xml"))
            styles = generated_xml(archive.read("xl/styles.xml"))
        ns = {"s": SS}
        serial = (date(2026, 1, 5)-date(1899, 12, 30)).days+9/24
        cells = sheet.findall(".//s:c", ns)
        assert any(cell.get("s") == "4" and float(cell.findtext("s:v", namespaces=ns) or 0) == pytest.approx(serial) for cell in cells)
        assert styles.findall("s:cellXfs/s:xf", ns)[4].get("numFmtId") == "22"
    elif format_ == "xml":
        root = generated_xml(path.read_bytes())
        ns = {"m": MSP}
        tasks = root.findall("m:Tasks/m:Task", ns)
        task = next(task for task in tasks if task.findtext("m:Name", namespaces=ns) == "A")
        assert task.findtext("m:Baseline/m:Number", namespaces=ns) == "0"
        assert task.findtext("m:Baseline/m:Start", namespaces=ns) == "2026-01-05T09:00:00"
        field = next(item for item in root.findall("m:ExtendedAttributes/m:ExtendedAttribute", ns)
                     if item.findtext("m:Alias", namespaces=ns) == "Gantt Desktop · Базовый план")
        values = {item.findtext("m:FieldID", namespaces=ns): item.findtext("m:Value", namespaces=ns)
                  for item in task.findall("m:ExtendedAttribute", ns)}
        assert values[field.findtext("m:FieldID", namespaces=ns)] == "Original"
    elif format_ == "pdf":
        pdf = pdf_document(path)
        assert "Original" in pdf.getAllText(0).text()
        pdf.close()
    assert c.project.to_dict() == before
    assert c.removeBaseline(first)
    assert source.project.active_baseline == first and first in source.project.baselines


def test_graphical_baseline_line_uses_original_dates_and_expands_default_range(qapp):
    c = Controller(project())
    assert c.createBaseline("Initial")
    assert c.moveTask("a", 30)
    source = ExportSource.capture(c)
    options = ExportOptions(content="chart", baseline=True, pixels_per_day=26, labels="none", links=False, today=False)
    document = ExportDocument(source, options)
    row = next(i for i, row in enumerate(document.rows) if row["taskId"] == "a")
    x = int((date(2026, 1, 5)-document.start).days*26+5)
    y = document.header+row*document.row_height+28
    assert document.start < date(2026, 1, 5)
    assert document.image().pixelColor(x, y) == QColor("#8493a3")
    assert document.reference is not None and document.reference.tasks["m"].kind == "milestone"
    clipped = ExportDocument(source, ExportOptions(content="chart", baseline=True,
                                                   start=date(2026, 2, 1), end=date(2026, 2, 10)))
    assert not clipped.image().isNull()


def test_absent_snapshot_data_is_blank_not_zero_and_deleted_entries_do_not_create_rows(qapp):
    c = Controller(project())
    assert c.createBaseline("Initial")
    c.deleteTask("m")
    c.addTask("", "task")
    key = c.property("selectedId")
    source = ExportSource.capture(c)
    row = next(row for row in source.rows if row["taskId"] == key)
    assert source.value(row, "baselineStart") is None and source.value(row, "endVariance") is None
    document = ExportDocument(source, ExportOptions(baseline=True))
    assert "m" not in {row["taskId"] for row in document.rows}
    assert document.reference is not None and "m" in document.reference.tasks


@pytest.mark.parametrize(("value", "expected", "style"), [
    ("1900-01-01T12:00", 1.5, "4"), ("1900-02-28T12:00", 59.5, "4"),
    ("1900-03-01T12:00", 61.5, "4"), ("1899-12-31T09:00", None, "0"),
])
def test_excel_datetime_preserves_time_and_epoch_quirk(value, expected, style):
    sheet = generated_xml(worksheet(["Date"], [([datetime.fromisoformat(value)], False, 0)], [160]))
    ns = {"s": SS}
    cell = sheet.find("s:sheetData/s:row[@r='2']/s:c", ns)
    assert cell is not None and cell.get("s") == style
    if expected is None:
        assert cell.get("t") == "inlineStr" and cell.findtext("s:is/s:t", namespaces=ns) == datetime.fromisoformat(value).isoformat()
    else:
        assert float(cell.findtext("s:v", namespaces=ns) or 0) == expected


def test_native_export_baseline_option_is_independent_and_missing_reference_disables_it(gui):
    c, _window = gui
    before = c.project.to_dict()
    c.dialogs.showExport({})
    option = required_widget("exportBaseline")
    assert isinstance(option, QCheckBox) and not option.isEnabled() and not option.isChecked()
    assert click_native("closeExport")
    assert c.createBaseline("Initial")
    selected = c.project.active_baseline
    c.dialogs.showExport({})
    option = required_widget("exportBaseline")
    assert isinstance(option, QCheckBox) and option.isEnabled() and option.isChecked()
    assert click_native("exportBaseline")
    assert c.project.active_baseline == selected
    content = required_widget("exportContent")
    assert isinstance(content, QComboBox)
    content.setCurrentIndex(content.findData("table"))
    wait_until(lambda: not option.isEnabled())
    assert c.project.to_dict()["tasks"] == before["tasks"]
    assert native_dialog("exportDialog").isVisible()


def test_baseline_export_requires_active_reference_and_enforces_range_limit(qapp):
    c = Controller(project())
    with pytest.raises(ExportError, match="Выберите базовый"):
        ExportDocument(ExportSource.capture(c), ExportOptions(baseline=True))
    assert c.createBaseline("Initial")
    data = c.project.to_dict()
    old = next(row for row in data["baselines"][0]["tasks"] if row["task_id"] == "a")
    old.update(start="1500-01-01T09:00", end="1500-01-02T18:00")
    c.load_project(Project.from_dict(data))
    with pytest.raises(ExportError, match="100 лет"):
        ExportDocument(ExportSource.capture(c), ExportOptions(baseline=True))
    assert not ExportDocument(ExportSource.capture(c), ExportOptions()).image().isNull()
