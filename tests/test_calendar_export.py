from datetime import date
from zipfile import ZipFile

import pytest
from test_calendar_exceptions import project, save
from test_exporting import generated_xml

from gantt_desktop.controller import Controller
from gantt_desktop.exporting import (
    ExportDocument,
    ExportOptions,
    ExportSource,
    export_file,
)
from gantt_desktop.interchange import MSP, SS


@pytest.mark.parametrize("format_", ["pdf", "png", "xlsx", "xml", "csv"])
def test_calendar_exception_exports_use_frozen_schedules_and_availability(qapp, tmp_path, format_):
    c = Controller(project())
    rid = next(iter(c.project.resources))
    assert save(c, start="2026-01-06", end="2026-01-06")
    assert save(c, rid, start="2026-01-05", end="2026-01-05", capacity="2.5")
    before = c.project.to_dict()
    source = ExportSource.capture(c)
    doc = ExportDocument(source, ExportOptions(format=format_, workload=True, columns=("name", "start", "end")))
    path = tmp_path / ("calendar." + format_)
    export_file(path, doc)
    assert path.stat().st_size > 100
    if format_ == "xml":
        assert not doc.resources and not doc.options.workload
    else:
        monday = next(day for day in doc.resources[0]["days"] if day["date"] == "2026-01-05")
        assert monday["capacity"] == 2.5 and monday["overloaded"]
    assert source.project.span("a")[1].date() == date(2026, 1, 7)
    assert c.project.to_dict() == before
    assert c.removeCalendarException("", c.project.calendar.exceptions[0].id)
    assert not source.project.calendar.working_day(date(2026, 1, 6))


def test_excel_workload_sheet_has_exception_capacity_and_warning(qapp, tmp_path):
    c = Controller(project())
    rid = next(iter(c.project.resources))
    assert save(c, rid, start="2026-01-05", end="2026-01-05", capacity="2.5")
    doc = ExportDocument(ExportSource.capture(c), ExportOptions(format="xlsx", workload=True))
    path = tmp_path / "workload.xlsx"
    export_file(path, doc)
    with ZipFile(path) as archive:
        sheet = generated_xml(archive.read("xl/worksheets/sheet2.xml"))
    ns = {"s": SS}
    serial = str((date(2026, 1, 5)-date(1899, 12, 30)).days)
    monday = next(row for row in sheet.findall("s:sheetData/s:row", ns)
                  if any(cell.get("r", "").startswith("B") and cell.findtext("s:v", namespaces=ns) == serial
                         for cell in row.findall("s:c", ns)))
    cells = {cell.get("r", "")[0]: cell for cell in monday.findall("s:c", ns)}
    assert cells["D"].findtext("s:v", namespaces=ns) == "2.5"
    assert cells["E"].get("t") == "b" and cells["E"].findtext("s:v", namespaces=ns) == "1"


def test_xml_calendars_encode_ranges_working_times_and_resource_availability_gaps(qapp, tmp_path):
    c = Controller(project())
    rid = next(iter(c.project.resources))
    c.project.calendar.holidays.update({date(2026, 1, 6), date(2026, 1, 9)})
    assert save(c, periods=[[420, 660], [1140, 1260]])
    assert save(c, rid, start="2026-01-07", end="2026-01-08")
    assert save(c, rid, start="2026-01-10", end="2026-01-10", capacity="6")
    doc = ExportDocument(ExportSource.capture(c), ExportOptions(format="xml"))
    path = tmp_path / "calendars.xml"
    export_file(path, doc)
    root = generated_xml(path.read_bytes())
    ns = {"m": MSP}
    calendars = root.findall("m:Calendars/m:Calendar", ns)
    base = next(item for item in calendars if item.findtext("m:UID", namespaces=ns) == "1")
    dated = [day for day in base.findall("m:WeekDays/m:WeekDay", ns) if day.findtext("m:DayType", namespaces=ns) == "0"]
    assert len(dated) == 2  # Jan 6 overrides its old holiday; Jan 9 remains closed.
    working = next(day for day in dated if day.findtext("m:DayWorking", namespaces=ns) == "1")
    assert working.findtext("m:TimePeriod/m:FromDate", namespaces=ns) == "2026-01-06T00:00:00"
    assert working.findtext("m:TimePeriod/m:ToDate", namespaces=ns) == "2026-01-06T23:59:59"
    assert [node.text for node in working.findall("m:WorkingTimes/m:WorkingTime/m:FromTime", ns)] == ["07:00:00", "19:00:00"]
    resource = root.find("m:Resources/m:Resource", ns)
    assert resource is not None
    periods = resource.findall("m:AvailabilityPeriods/m:AvailabilityPeriod", ns)
    assert [item.findtext("m:AvailableUnits", namespaces=ns) for item in periods] == ["1.0", "0.0", "1.0", "0.75", "1.0"]
    assert periods[0].find("m:AvailableFrom", ns) is None
    assert periods[-1].find("m:AvailableTo", ns) is None
    assert periods[2].findtext("m:AvailableFrom", namespaces=ns) == "2026-01-09T00:00:00"
    person = next(item for item in calendars if item.findtext("m:BaseCalendarUID", namespaces=ns) == "1")
    dated = [day for day in person.findall("m:WeekDays/m:WeekDay", ns) if day.findtext("m:DayType", namespaces=ns) == "0"]
    assert [day.findtext("m:DayWorking", namespaces=ns) for day in dated] == ["0", "1"]
