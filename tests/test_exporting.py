import csv
import hashlib
from dataclasses import replace
from datetime import date, datetime
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from PySide6.QtPdf import QPdfDocument

from gantt_desktop.controller import Controller
from gantt_desktop.domain import Dependency, Project, Task
from gantt_desktop.exporting import (
    SCALES,
    ExportDocument,
    ExportError,
    ExportOptions,
    ExportSource,
    atomic_export,
    export_file,
)
from gantt_desktop.interchange import MSP, SS, column_name


def source(qapp):
    return ExportSource.capture(Controller())


def long_source(qapp, count=140):
    p = Project("Long project")
    start = datetime.fromisoformat("2026-01-05T09:00")
    p.tasks = {f"t{i}": Task(f"t{i}", f"Task {i}", start, duration=60) for i in range(count)}
    return ExportSource.capture(Controller(p))


def generated_xml(data):
    # Only our own writer output from temporary test files, never external XML.
    return ET.fromstring(data)


def pdf_document(path):
    pdf = QPdfDocument()
    assert pdf.load(str(path)) == QPdfDocument.Error.None_
    return pdf


@pytest.mark.parametrize("format_", ["pdf", "png", "xlsx", "xml", "csv"])
def test_all_formats_are_nonempty_and_leave_project_history_unchanged(qapp, tmp_path, format_):
    c = Controller()
    before = c.project.to_dict()
    doc = ExportDocument(ExportSource.capture(c), ExportOptions(format=format_, workload=True))
    path = tmp_path / ("diagram." + format_)
    export_file(path, doc)
    assert path.stat().st_size > 100
    if format_ == "pdf":
        pdf = pdf_document(path)
        assert pdf.pageCount() == 1
        assert "Планирование" in pdf.getAllText(0).text()
        pdf.close()
    elif format_ == "png":
        image = QImage(str(path))
        assert not image.isNull() and image.width() >= doc.width
    elif format_ == "xlsx":
        with ZipFile(path) as archive:
            assert "xl/worksheets/sheet2.xml" in archive.namelist()
            for name in archive.namelist():
                if name.endswith((".xml", ".rels")):
                    generated_xml(archive.read(name))
    elif format_ == "xml":
        assert generated_xml(path.read_bytes()).tag == "{" + MSP + "}Project"
    else:
        assert next(csv.reader(path.read_text(encoding="utf-8-sig").splitlines()))[1] == "Задача"
    assert c.project.to_dict() == before and not c.canUndo and not c.dirty
    assert not list(tmp_path.glob(".gantt-export-*"))


def test_snapshot_and_scope_preserve_hierarchy_not_add_rows_or_viewport(qapp):
    c = Controller()
    c.toggleGroup("planning")
    captured = ExportSource.capture(c)
    all_rows = ExportDocument(captured, ExportOptions()).rows
    visible = ExportDocument(captured, ExportOptions(scope="visible")).rows
    assert len(all_rows) == len(c.project.tasks) and len(visible) < len(all_rows)
    assert "sensor" not in {r["taskId"] for r in visible}
    assert all(r["rowKind"] == "task" and r["outline"] for r in all_rows)
    assert c.editField("sensor", "name", "Changed after snapshot")
    assert next(r for r in captured.rows if r["taskId"] == "sensor")["name"] == "Выбор сенсора"
    c.search("сенсора")
    filtered = ExportSource.capture(c)
    assert 0 < len(filtered.visible_ids) < len(filtered.rows)
    assert {r["taskId"] for r in ExportDocument(filtered, ExportOptions(scope="visible")).rows} == filtered.visible_ids


@pytest.mark.parametrize("change", [
    {"format": "wrong"}, {"scope": "wrong"}, {"paper": "wrong"}, {"labels": "wrong"},
    {"content": "wrong"}, {"pixels_per_day": 0}, {"pixels_per_day": float("nan")},
    {"columns": ()}, {"columns": ("missing",)}, {"columns": ("name", "name")},
    {"start": date(2026, 2, 1), "end": date(2026, 1, 1)},
])
def test_invalid_options_are_rejected(qapp, change):
    with pytest.raises(ExportError):
        ExportDocument(source(qapp), replace(ExportOptions(), **change))


@pytest.mark.parametrize("scale", SCALES.values())
def test_time_scale_and_single_day_range_control_whole_document_width(qapp, scale):
    doc = ExportDocument(source(qapp), ExportOptions(pixels_per_day=scale,
                                                   start=date(2026, 1, 5), end=date(2026, 1, 5)))
    assert len(doc.dates) == 1
    assert doc.width == doc.left + scale
    assert not doc.image().isNull()


@pytest.mark.parametrize("paper", ["A4", "A3", "Letter"])
@pytest.mark.parametrize("landscape", [True, False])
def test_pdf_pages_repeat_headers_and_include_the_last_offscreen_task(qapp, tmp_path, paper, landscape):
    doc = ExportDocument(long_source(qapp), ExportOptions(paper=paper, landscape=landscape))
    path = tmp_path / "pages.pdf"
    export_file(path, doc)
    pdf = pdf_document(path)
    assert pdf.pageCount() > 1
    first = pdf.getAllText(0).text()
    last = pdf.getAllText(pdf.pageCount()-1).text()
    assert "Long project" in first and "Task 0" in first
    assert "Long project" in last and "Task 139" in last
    size = pdf.pagePointSize(0)
    assert (size.width() > size.height()) == landscape
    assert not pdf.render(pdf.pageCount()-1, QSize(800, 600)).isNull()
    pdf.close()


def test_full_pdf_and_png_are_full_model_not_a_screen_capture(qapp, tmp_path):
    doc = ExportDocument(long_source(qapp, 80), ExportOptions(pixels_per_day=26))
    png = tmp_path / "all.png"
    pdf_path = tmp_path / "all.pdf"
    export_file(png, replace(doc, options=replace(doc.options, format="png")))
    image = QImage(str(png))
    assert image.height() == 80 + 80*30 and image.height() > 960
    export_file(pdf_path, doc)
    pdf = pdf_document(pdf_path)
    assert pdf.pageCount() == 1
    assert pdf.pagePointSize(0).height() == pytest.approx(doc.height*72/96, abs=1)
    assert "Task 79" in pdf.getAllText(0).text()
    pdf.close()


def test_png_limits_and_partial_failures_never_replace_an_existing_file(qapp, tmp_path):
    path = tmp_path / "existing.png"
    path.write_bytes(b"original user file")
    doc = ExportDocument(source(qapp), ExportOptions(format="png", pixels_per_day=52,
                                                   start=date(2020, 1, 1), end=date(2026, 1, 1)))
    with pytest.raises(ExportError, match="PNG"):
        export_file(path, doc)
    assert path.read_bytes() == b"original user file"

    def fail(target):
        target.write_bytes(b"partial")
        raise ExportError("deliberate write failure")
    with pytest.raises(ExportError):
        atomic_export(path, fail)
    assert path.read_bytes() == b"original user file"
    assert list(tmp_path.iterdir()) == [path]


def test_oversized_full_pdf_requires_a_paged_paper(qapp):
    doc = ExportDocument(source(qapp), ExportOptions(pixels_per_day=52,
                                                   start=date(2020, 1, 1), end=date(2026, 1, 1)))
    with pytest.raises(ExportError, match="PDF"):
        doc.pdf_layout()
    assert ExportDocument(doc.source, replace(doc.options, paper="A4")).pdf_layout()[3] > 0


def test_excel_has_real_types_hierarchy_custom_fields_and_no_executable_formula(qapp, tmp_path):
    c = Controller()
    number = c.saveCustomField("", "Number", "number", [], "sum")
    flag = c.saveCustomField("", "Flag", "checkbox", [], "")
    day = c.saveCustomField("", "Day", "date", [], "")
    formula = c.saveCustomField("", "Text", "text", [], "")
    for key, value in ((number, 0), (flag, False), (day, "2026-01-05"), (formula, "=1+1")):
        assert c.setCustomValue("sensor", key, value)
    keys = ("name", "start", "custom:"+number, "custom:"+flag, "custom:"+day, "custom:"+formula)
    doc = ExportDocument(ExportSource.capture(c), ExportOptions(format="xlsx", columns=keys, content="table", workload=True))
    path = tmp_path / "typed.xlsx"
    export_file(path, doc)
    ns = {"s": SS}
    with ZipFile(path) as archive:
        sheet = generated_xml(archive.read("xl/worksheets/sheet1.xml"))
        sensor_index = next(i+2 for i, row in enumerate(doc.rows) if row["taskId"] == "sensor")
        cells = {cell.attrib["r"]: cell for cell in sheet.findall(".//s:c", ns)}
        assert cells[f"C{sensor_index}"].findtext("s:v", namespaces=ns) == "0"
        assert cells[f"D{sensor_index}"].attrib["t"] == "b"
        assert cells[f"D{sensor_index}"].findtext("s:v", namespaces=ns) == "0"
        assert cells[f"E{sensor_index}"].attrib["s"] == "2"
        assert cells[f"F{sensor_index}"].attrib["t"] == "inlineStr"
        assert cells[f"F{sensor_index}"].findtext("s:is/s:t", namespaces=ns) == "=1+1"
        assert not sheet.findall(".//s:f", ns)
        assert sheet.find("s:autoFilter", ns) is not None
        assert any(int(row.attrib["outlineLevel"]) > 0 for row in sheet.findall("s:sheetData/s:row", ns))
        assert "xl/worksheets/sheet2.xml" in archive.namelist()
        load = generated_xml(archive.read("xl/worksheets/sheet2.xml"))
        assert len(load.findall("s:sheetData/s:row", ns)) == 1 + len(c.project.resources)*len(doc.dates)
    assert column_name(1) == "A" and column_name(27) == "AA" and column_name(16384) == "XFD"


def test_xml_retains_structure_calendar_dependencies_assignments_and_metadata(qapp, tmp_path):
    c = Controller()
    p = c.project
    p.calendar.holidays.add(date(2026, 1, 7))
    key = c.saveCustomField("", "Risk", "text", [], "")
    assert c.setCustomValue("sensor", key, "Low & <safe>")
    artist = p.tasks["model"].resource_ids[0]
    client = p.tasks["sensor"].resource_ids[0]
    assert c.assignResources("sensor", [client, artist], [1, 7])
    source_ = ExportSource.capture(c)
    doc = ExportDocument(source_, ExportOptions(format="xml", scope="visible"))
    path = tmp_path / "project.xml"
    export_file(path, doc)
    ns = {"m": MSP}
    root = generated_xml(path.read_bytes())
    tasks = root.findall("m:Tasks/m:Task", ns)
    assert len(tasks) == len(c.project.tasks)
    sensor = next(t for t in tasks if t.findtext("m:Name", namespaces=ns) == "Выбор сенсора")
    assert "Risk: Low & <safe>" in (sensor.findtext("m:Notes", namespaces=ns) or "")
    assert sensor.findtext("m:Duration", namespaces=ns) == "PT24H0M0S"
    assert sensor.findtext("m:Work", namespaces=ns) == "PT8H0M0S"
    assert root.findall(".//m:TimePeriod/m:FromDate", ns)
    uid = sensor.findtext("m:UID", namespaces=ns)
    assignments = [a for a in root.findall("m:Assignments/m:Assignment", ns) if a.findtext("m:TaskUID", namespaces=ns) == uid]
    assert {a.findtext("m:Work", namespaces=ns) for a in assignments} == {"PT1H0M0S", "PT7H0M0S"}
    assert len(root.findall(".//m:PredecessorLink", ns)) == len(c.project.dependencies)
    assert any(t.findtext("m:Summary", namespaces=ns) == "1" for t in tasks)
    assert any(t.findtext("m:Milestone", namespaces=ns) == "1" for t in tasks)


def test_visual_settings_change_rendered_pixels_without_touching_data(qapp):
    c = Controller()
    assert c.editField("sensor", "status", "closed")
    source_ = ExportSource.capture(c)
    before = c.project.to_dict()
    options = ExportOptions()
    document = ExportDocument(source_, options)
    source_.today = document.start + (document.end-document.start)//2

    def digest(change):
        image = ExportDocument(source_, replace(options, **change)).image()
        return hashlib.sha256(image.constBits()).hexdigest()
    normal = digest({})
    for change in ({"links": False}, {"labels": "none"}, {"labels": "right"}, {"strike_closed": False},
                   {"fade_closed": False}, {"today": False}, {"workload": True}):
        assert digest(change) != normal
    assert c.project.to_dict() == before


def test_empty_filtered_scope_bad_context_and_invalid_xml_text_fail_cleanly(qapp, tmp_path):
    c = Controller()
    c.search("no matching task")
    with pytest.raises(ExportError, match="Нет задач"):
        ExportDocument(ExportSource.capture(c), ExportOptions(scope="visible"))
    with pytest.raises(ExportError, match="ширина"):
        ExportSource.capture(c, {"columns": [{"key": "name", "width": "bad"}]})
    c.search("")
    assert c.editField("sensor", "notes", "Invalid\x01text")
    document = ExportDocument(ExportSource.capture(c), ExportOptions(format="xml"))
    path = tmp_path / "bad.xml"
    with pytest.raises(ExportError, match="XML"):
        export_file(path, document)
    assert not path.exists()


def test_dependency_paths_are_strokes_not_filled_open_polygons(qapp):
    p = Project()
    p.tasks = {"a": Task("a", "A", datetime.fromisoformat("2026-01-05T09:00")),
               "b": Task("b", "B", datetime.fromisoformat("2026-01-08T09:00"))}
    p.dependencies = [Dependency("ab", "a", "b", "FS")]
    doc = ExportDocument(ExportSource.capture(Controller(p)), ExportOptions(columns=("name",), pixels_per_day=26))
    image = doc.image()
    # Inside the orthogonal route, away from the actual line/bar/grid: it must remain white.
    assert image.pixelColor(round(doc.left + 70), 105).name() == "#ffffff"
