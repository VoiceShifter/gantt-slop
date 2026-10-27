import csv
import io
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from defusedxml.ElementTree import fromstring

from gantt_desktop.controller import Controller
from gantt_desktop.domain import Dependency
from gantt_desktop.exporting import (
    ExportDocument,
    ExportOptions,
    ExportSource,
    export_file,
)
from gantt_desktop.ganttpro_csv import SITE_HEADERS, read_project_csv, table_rows
from gantt_desktop.ganttpro_xlsx import (
    NS,
    XlsxImportError,
    parse_project_xlsx,
    read_project_xlsx,
)

FIXTURE = Path(__file__).parent / "fixtures" / "ganttpro-task-table.csv"
RETURN = FIXTURE.with_name("ganttpro-return-table.xlsx")
SHEET = "xl/worksheets/sheet1.xml"


def export_table(project, path, **options):
    controller = Controller(project)
    source = ExportSource.capture(controller)
    export_file(path, ExportDocument(source, ExportOptions(format="ganttpro_xlsx", **options)))
    return path.read_bytes()


def cells(project):
    source = ExportSource.capture(Controller(project))
    return table_rows(source.project, source.rows)


def rewrite(data, modify):
    with ZipFile(io.BytesIO(data)) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    modify(parts)
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for name, value in parts.items():
            archive.writestr(name, value)
    return buffer.getvalue()


def change_sheet(data, modify):
    def update(parts):
        sheet = fromstring(parts[SHEET])
        modify(sheet)
        parts[SHEET] = ET.tostring(sheet, encoding="utf-8")
    return rewrite(data, update)


def test_excel_23_column_roundtrip_preserves_all_reference_cells(qapp, tmp_path):
    project = read_project_csv(FIXTURE).project
    before = project.to_dict()
    data = export_table(project, tmp_path/"plan.xlsx", scope="visible", start=date(2030, 1, 1), end=date(2020, 1, 1),
                        critical=True, baseline=True, workload=True, table_headers=False)
    report = parse_project_xlsx(data)
    assert report.profile == "GanttPRO Excel · 23 поля"
    assert cells(report.project) == cells(project)
    assert len(report.project.dependencies) == 14
    assert project.to_dict() == before
    with ZipFile(io.BytesIO(data)) as archive:
        sheet = fromstring(archive.read(SHEET))
        assert len(sheet.findall("s:sheetData/s:row", NS)) == 21
        assert not sheet.findall(".//s:f", NS)
        wbs = sheet.find(".//s:c[@r='B4']", NS)
        assert wbs is not None and wbs.get("t") == "inlineStr"
        for address in ("F4", "G4", "I4", "J4", "K4", "Q4", "W4"):
            cell = sheet.find(f".//s:c[@r='{address}']", NS)
            assert cell is not None and cell.get("t") == "n"


def test_actual_site_return_retains_dates_totals_but_does_not_invent_lost_links_or_milestone_assignee(qapp):
    expected = read_project_csv(FIXTURE).project
    report = read_project_xlsx(RETURN)
    project = report.project
    assert len(project.tasks) == 20 and len(project.resources) == 3
    assert not project.dependencies and not project.tasks["csv-task-2.3"].resource_ids
    assert sum(t.effort for t in project.tasks.values()) == 212
    assert sum(t.cost for t in project.tasks.values()) == 38000
    for uid, task in project.tasks.items():
        source = expected.tasks[uid]
        assert (task.name, task.kind, task.parent, task.progress, task.priority) == (source.name, source.kind, source.parent, source.progress, source.priority)
        assert project.span(uid) == expected.span(uid)
    assert project.tasks["csv-task-1.2"].effort == 8
    assert "create" not in report.profile.lower()
    assert all("Человек Самолет" not in str(t.custom_values) for t in project.tasks.values())


@pytest.mark.parametrize("site", [False, True])
@pytest.mark.parametrize("value", ["=SUM(1,2)", "'=literal", "_x000D_", "a\r\nb", '  <>& \"hi\"  ', "Строка 😀"])
def test_excel_literal_text_never_becomes_a_formula_or_loses_whitespace(qapp, tmp_path, site, value):
    project = read_project_csv(FIXTURE).project
    task = project.tasks["csv-task-1.2"]
    task.name = value
    task.notes = value
    task.custom_values["ganttpro_creator"] = value
    other = parse_project_xlsx(export_table(project, tmp_path/"literal.xlsx", site_import=site)).project
    result = other.tasks[task.id]
    assert (result.name, result.notes, result.custom_values["ganttpro_creator"]) == (value, value, value)


@pytest.mark.parametrize("kind", ["FS", "SS", "FF", "SF"])
@pytest.mark.parametrize("lag", [-7, 0, 7])
def test_excel_retains_real_local_dependency_types_and_lags(qapp, tmp_path, kind, lag):
    p = read_project_csv(FIXTURE).project
    p.dependencies = [Dependency("link", "csv-task-1.1", "csv-task-1.2", kind, lag)]
    other = parse_project_xlsx(export_table(p, tmp_path/"links.xlsx")).project
    assert [(d.kind, d.lag) for d in other.dependencies] == [(kind, lag)]


@pytest.mark.parametrize("format_", ["ganttpro_csv", "ganttpro_xlsx"])
@pytest.mark.parametrize("headers", [True, False])
def test_website_layout_is_separate_and_reversible_with_headers(qapp, tmp_path, format_, headers):
    p = read_project_csv(FIXTURE).project
    source = ExportSource.capture(Controller(p))
    before = p.to_dict()
    doc = ExportDocument(source, ExportOptions(format=format_, site_import=True, table_headers=headers))
    assert tuple(c["title"] for c in doc.columns) == SITE_HEADERS
    assert doc.rows[0]["ganttproValues"][2] == doc.rows[0]["ganttproValues"][3]
    sensor = doc.rows[2]["ganttproValues"]
    assert sensor[5:7] == ["11.12.2025", "15.12.2025"] and sensor[23:] == ["09:00", "18:00"]
    path = tmp_path/("site.csv" if format_ == "ganttpro_csv" else "site.xlsx")
    export_file(path, doc)
    if format_ == "ganttpro_csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        assert len(rows) == 20+int(headers)
        parser = read_project_csv
    else:
        with ZipFile(path) as archive:
            sheet = fromstring(archive.read(SHEET))
            assert len(sheet.findall("s:sheetData/s:row", NS)) == 20+int(headers)
            assert (sheet.find("s:autoFilter", NS) is not None) == headers
        parser = read_project_xlsx
    if headers:
        assert cells(parser(path).project) == cells(p)
    else:
        with pytest.raises(ValueError):
            parser(path)
    assert p.to_dict() == before


def test_excel_1904_epoch_is_respected(qapp, tmp_path):
    p = read_project_csv(FIXTURE).project
    data = export_table(p, tmp_path/"epoch.xlsx")
    def convert(parts):
        workbook = fromstring(parts["xl/workbook.xml"])
        ET.SubElement(workbook, "{"+NS['s']+"}workbookPr", date1904="1")
        parts["xl/workbook.xml"] = ET.tostring(workbook)
        sheet = fromstring(parts[SHEET])
        for cell in sheet.findall(".//s:c", NS):
            if cell.get("t") == "n" and cell.get("r", "")[0] in {"F", "G"}:
                value = cell.find("s:v", NS)
                assert value is not None and value.text is not None
                value.text = str(float(value.text)-1462)
        parts[SHEET] = ET.tostring(sheet)
    assert cells(parse_project_xlsx(rewrite(data, convert)).project) == cells(p)


@pytest.mark.parametrize(("old", "new"), [(b'46002.375', b'60'), (b'46002.375', b'NaN'), (b'46002.375', b'1e100'),
                                             (b'46002.375', b'46002.3750001')])
def test_invalid_or_subsecond_excel_dates_are_rejected(old, new):
    data = rewrite(RETURN.read_bytes(), lambda parts: parts.update({SHEET: parts[SHEET].replace(old, new)}))
    with pytest.raises(XlsxImportError):
        parse_project_xlsx(data)


@pytest.mark.parametrize("attack", ["formula", "duplicate-cell", "duplicate-row", "bad-string", "bad-fill", "error-cell", "extra-column", "extra-footer"])
def test_malformed_cells_are_rejected_without_a_partial_project(attack):
    def modify(sheet):
        data = sheet.find("s:sheetData", NS)
        assert data is not None
        row = data.find("s:row[@r='7']", NS)
        assert row is not None
        cell = row.find("s:c[@r='B7']", NS)
        assert cell is not None
        if attack == "formula":
            ET.SubElement(cell, "{"+NS['s']+"}f").text = "1+1"
        elif attack == "duplicate-cell":
            row.append(cell)
        elif attack == "duplicate-row":
            data.append(row)
        elif attack == "bad-string":
            cell.find("s:v", NS).text = "99999999"
        elif attack == "bad-fill":
            row.find("s:c[@r='A7']", NS).set("s", "99999999")
        elif attack == "error-cell":
            cell.set("t", "e")
        elif attack == "extra-column":
            extra = ET.SubElement(row, "{"+NS['s']+"}c", r="Z7", t="n")
            ET.SubElement(extra, "{"+NS['s']+"}v").text = "1"
        else:
            row.set("r", "28")
            for child in row:
                child.set("r", child.get("r", "").replace("7", "28"))
            data.append(row)
    with pytest.raises(XlsxImportError):
        parse_project_xlsx(change_sheet(RETURN.read_bytes(), modify))


@pytest.mark.parametrize("attack", ["dtd", "entity", "deep", "macro", "external", "path", "two-tables", "missing", "bad-xml"])
def test_untrusted_workbook_packages_are_bounded_offline_and_unambiguous(attack):
    def modify(parts):
        if attack in {"dtd", "entity"}:
            parts[SHEET] = (b'<!DOCTYPE worksheet [<!ENTITY evil SYSTEM "file:///etc/passwd">]>' if attack == "entity" else b'<!DOCTYPE worksheet>')+b'<worksheet>&evil;</worksheet>'
        elif attack == "deep":
            parts[SHEET] = b'<a>'*65+b'</a>'*65
        elif attack == "macro":
            parts['xl/vbaProject.bin'] = b'not executed'
        elif attack == "external":
            parts['xl/_rels/workbook.xml.rels'] = parts['xl/_rels/workbook.xml.rels'].replace(b'Target="styles.xml"', b'TargetMode="External" Target="https://example.invalid/file"')
        elif attack == "path":
            parts['../outside'] = b'never extracted'
        elif attack == "two-tables":
            parts['xl/workbook.xml'] = parts['xl/workbook.xml'].replace(b'</sheets>', b'<sheet name="Second" sheetId="2" r:id="r1"/></sheets>')
        elif attack == "missing":
            del parts[SHEET]
        else:
            parts[SHEET] = b'<broken>'
    with pytest.raises(XlsxImportError):
        parse_project_xlsx(rewrite(RETURN.read_bytes(), modify))


def test_zip_limits_and_corruption_are_reported(monkeypatch):
    import gantt_desktop.ganttpro_xlsx as reader

    with pytest.raises(XlsxImportError):
        parse_project_xlsx(b'not a zip')
    monkeypatch.setattr(reader, 'MAX_UNPACKED', 100)
    with pytest.raises(XlsxImportError, match="большой"):
        parse_project_xlsx(RETURN.read_bytes())
    monkeypatch.setattr(reader, 'MAX_BYTES', 100)
    with pytest.raises(XlsxImportError, match="16 MiB"):
        parse_project_xlsx(RETURN.read_bytes())


@pytest.mark.parametrize("value", ["_xD83D__xDE00_", "_xD83D_", "_xDE00_"])
def test_excel_utf16_escapes_decode_pairs_and_reject_unpaired_surrogates(qapp, tmp_path, value):
    project = read_project_csv(FIXTURE).project
    project.tasks["csv-task-1.2"].notes = "ESCAPED_EMOJI"
    data = export_table(project, tmp_path/"unicode.xlsx")
    data = rewrite(data, lambda parts: parts.update({SHEET: parts[SHEET].replace(b"ESCAPED_EMOJI", value.encode())}))
    if value == "_xD83D__xDE00_":
        assert parse_project_xlsx(data).project.tasks["csv-task-1.2"].notes == "😀"
    else:
        with pytest.raises(XlsxImportError):
            parse_project_xlsx(data)


def test_reused_shared_strings_cannot_amplify_the_table_without_limit(monkeypatch):
    import gantt_desktop.ganttpro_xlsx as reader

    def amplify(parts):
        name = "xl/sharedStrings.xml"
        parts[name] = parts[name].replace("Автор примера".encode(), b"x"*5000)
    data = rewrite(RETURN.read_bytes(), amplify)
    with ZipFile(io.BytesIO(data)) as archive:
        limit = max(len(data), *(part.file_size for part in archive.infolist()))+1
    monkeypatch.setattr(reader, "MAX_BYTES", limit)
    with pytest.raises(XlsxImportError, match="Текст таблицы"):
        parse_project_xlsx(data)


def test_repeated_relationship_target_is_rejected_before_reparsing():
    def modify(parts):
        name = "xl/_rels/workbook.xml.rels"
        root = fromstring(parts[name])
        repeated = fromstring(ET.tostring(root[0]))
        repeated.set("Id", "duplicate-target")
        root.append(repeated)
        parts[name] = ET.tostring(root)
    with pytest.raises(XlsxImportError, match="Повторная/внешняя"):
        parse_project_xlsx(rewrite(RETURN.read_bytes(), modify))


def test_failed_export_preserves_existing_destination(qapp, tmp_path):
    p = read_project_csv(FIXTURE).project
    p.tasks['csv-task-1.2'].notes = 'bad\x00text'
    path = tmp_path/'protected.xlsx'
    path.write_bytes(b'existing destination')
    with pytest.raises(ValueError):
        export_table(p, path)
    assert path.read_bytes() == b'existing destination'
    assert not list(tmp_path.glob('.gantt-export-*'))
