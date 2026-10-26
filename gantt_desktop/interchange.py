"""Local spreadsheet and MS Project XML writers, using only the standard library."""
from __future__ import annotations

import csv
import math
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from .exporting import ExportError
from .workload import workload_rows

if TYPE_CHECKING:
    from .exporting import ExportDocument, ExportSource

SS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
MSP = "http://schemas.microsoft.com/project"


def text(value: object) -> str:
    result = str(value)
    if any(ord(c) < 32 and c not in "\t\r\n" or 0xD800 <= ord(c) <= 0xDFFF for c in result):
        raise ExportError("Текст содержит недопустимые XML-символы.")
    return result


def element(parent: ET.Element, tag: str, value: object | None = None, **attributes: str) -> ET.Element:
    child = ET.SubElement(parent, tag, attributes)
    if value is not None:
        child.text = text(value)
    return child


def xml_bytes(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def tabular_value(document: ExportDocument, row: dict, key: str) -> object:
    value = document.source.value(row, key)
    if key.startswith("custom:"):
        definition = document.source.project.custom_fields[key[7:]]
        if definition.kind == "date" and value:
            return date.fromisoformat(str(value))
        if isinstance(value, list):
            return definition.display(value, document.source.project.resources)
    return value


def write_csv(path: Path, document: ExportDocument) -> None:
    keys = document.options.columns
    if not keys:
        raise ExportError("Выберите поля таблицы.")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow([document.source.columns[key]["title"] for key in keys])
        for row in document.rows:
            values = []
            for key in keys:
                value = tabular_value(document, row, key)
                if isinstance(value, bool):
                    value = "Да" if value else "Нет"
                elif isinstance(value, (date, datetime)):
                    value = value.isoformat()
                elif isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                    value = "'" + value
                values.append(value)
            writer.writerow(values)


def write_ganttpro_csv(path: Path, document: ExportDocument) -> None:
    """The supplied GanttPRO task table, with a real predecessor column."""
    from .ganttpro_csv import write_rows

    write_rows(path, [row["ganttproValues"] for row in document.rows])


def worksheet(headers: list[str], rows: list[tuple[list[object], bool, int]], widths: list[float]) -> bytes:
    if len(headers) > 16384 or len(rows) + 1 > 1048576:
        raise ExportError("Превышен предел строк или столбцов Excel.")
    root = ET.Element("worksheet", {"xmlns": SS})
    sheet_pr = element(root, "sheetPr")
    element(sheet_pr, "outlinePr", summaryBelow="0")
    element(root, "dimension", ref=f"A1:{column_name(len(headers))}{len(rows)+1}")
    views = element(root, "sheetViews")
    view = element(views, "sheetView", workbookViewId="0")
    element(view, "pane", xSplit="1", ySplit="1", topLeftCell="B2", activePane="bottomRight", state="frozen")
    columns = element(root, "cols")
    for index, width in enumerate(widths, 1):
        element(columns, "col", min=str(index), max=str(index), width=f"{max(8,min(100,width/7)):g}", customWidth="1")
    data = element(root, "sheetData")

    def add_row(index: int, values: list[object], style: int, level: int) -> None:
        record = element(data, "row", r=str(index), outlineLevel=str(min(7, level)))
        for col, value in enumerate(values, 1):
            if value is None:
                continue
            attrs = {"r": column_name(col) + str(index), "s": str(style)}
            if isinstance(value, bool):
                cell = element(record, "c", t="b", **attrs)
                element(cell, "v", "1" if value else "0")
            elif isinstance(value, (int, float)):
                if not math.isfinite(value):
                    raise ExportError("Excel не поддерживает бесконечные числовые значения.")
                cell = element(record, "c", t="n", **attrs)
                element(cell, "v", f"{value:.15g}")
            elif isinstance(value, date) and (value.date() if isinstance(value, datetime) else value) >= date(1900, 1, 1):
                day = value.date() if isinstance(value, datetime) else value
                serial = (day - date(1899, 12, 30)).days
                if serial <= 60:
                    serial -= 1
                if isinstance(value, datetime):
                    serial += (value.hour*3600 + value.minute*60 + value.second + value.microsecond/1e6)/86400
                attrs["s"] = "4" if isinstance(value, datetime) else "2"
                cell = element(record, "c", t="n", **attrs)
                element(cell, "v", f"{serial:.15g}")
            else:
                cell = element(record, "c", t="inlineStr", **attrs)
                string = element(cell, "is")
                entry = element(string, "t", value.isoformat() if isinstance(value, date) else value)
                entry.set("xml:space", "preserve")
    add_row(1, list(headers), 1, 0)
    for index, (values, summary, level) in enumerate(rows, 2):
        add_row(index, values, 3 if summary else 0, level)
    element(root, "autoFilter", ref=f"A1:{column_name(len(headers))}{len(rows)+1}")
    return xml_bytes(root)


def styles() -> bytes:
    root = ET.Element("styleSheet", {"xmlns": SS})
    fonts = element(root, "fonts", count="2")
    for bold in (False, True):
        font = element(fonts, "font")
        element(font, "sz", val="11")
        element(font, "name", val="Calibri")
        if bold:
            element(font, "b")
    fills = element(root, "fills", count="3")
    for pattern in ("none", "gray125", "solid"):
        fill = element(fills, "fill")
        pattern_fill = element(fill, "patternFill", patternType=pattern)
        if pattern == "solid":
            element(pattern_fill, "fgColor", rgb="FFF2F2F2")
    borders = element(root, "borders", count="1")
    element(borders, "border")
    base = element(root, "cellStyleXfs", count="1")
    element(base, "xf", numFmtId="0", fontId="0", fillId="0", borderId="0")
    formats = element(root, "cellXfs", count="5")
    for font, fill, number in ((0, 0, 0), (1, 2, 0), (0, 0, 14), (1, 0, 0), (0, 0, 22)):
        element(formats, "xf", numFmtId=str(number), fontId=str(font), fillId=str(fill), borderId="0", xfId="0")
    names = element(root, "cellStyles", count="1")
    element(names, "cellStyle", name="Normal", xfId="0", builtinId="0")
    return xml_bytes(root)


def write_xlsx(path: Path, document: ExportDocument) -> None:
    keys = document.options.columns
    if not keys:
        raise ExportError("Выберите поля таблицы.")
    sheets = [("Задачи", worksheet(
        [document.source.columns[key]["title"] for key in keys],
        [([tabular_value(document, row, key) for key in keys], row["summary"], row["level"]) for row in document.rows],
        [document.source.columns[key]["width"] for key in keys]))]
    if document.options.workload:
        resources = document.resources or workload_rows(document.source.project, document.start, len(document.dates))
        rows = []
        for resource in resources:
            for day in resource["days"]:
                rows.append(([resource["name"], date.fromisoformat(day["date"]), day["hours"], day["capacity"],
                              day["overloaded"], day["weekendWork"]], False, 0))
        sheets.append(("Загрузка ресурсов", worksheet(["Ресурс", "Дата", "Часы", "Доступно", "Перегрузка", "Выходной"],
                                                    rows, [200, 100, 100, 100, 100, 100])))
    types = ET.Element("Types", {"xmlns": "http://schemas.openxmlformats.org/package/2006/content-types"})
    element(types, "Default", Extension="rels", ContentType="application/vnd.openxmlformats-package.relationships+xml")
    element(types, "Default", Extension="xml", ContentType="application/xml")
    for name, content_type in [("/xl/workbook.xml", "spreadsheetml.sheet.main"), ("/xl/styles.xml", "spreadsheetml.styles")]:
        element(types, "Override", PartName=name, ContentType="application/vnd.openxmlformats-officedocument." + content_type + "+xml")
    for i in range(1, len(sheets)+1):
        element(types, "Override", PartName=f"/xl/worksheets/sheet{i}.xml",
                ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml")
    package_rels = ET.Element("Relationships", {"xmlns": PKG_REL})
    element(package_rels, "Relationship", Id="rId1", Type=REL + "/officeDocument", Target="xl/workbook.xml")
    workbook = ET.Element("workbook", {"xmlns": SS, "xmlns:r": REL})
    sheet_list = element(workbook, "sheets")
    relationships = ET.Element("Relationships", {"xmlns": PKG_REL})
    for i, (name, _data) in enumerate(sheets, 1):
        element(sheet_list, "sheet", name=name, sheetId=str(i), **{"r:id": f"rId{i}"})
        element(relationships, "Relationship", Id=f"rId{i}", Type=REL + "/worksheet", Target=f"worksheets/sheet{i}.xml")
    element(relationships, "Relationship", Id=f"rId{len(sheets)+1}", Type=REL + "/styles", Target="styles.xml")
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, data in [("[Content_Types].xml", xml_bytes(types)), ("_rels/.rels", xml_bytes(package_rels)),
                           ("xl/workbook.xml", xml_bytes(workbook)), ("xl/_rels/workbook.xml.rels", xml_bytes(relationships)),
                           ("xl/styles.xml", styles())]:
            archive.writestr(name, data)
        for i, (_name, data) in enumerate(sheets, 1):
            archive.writestr(f"xl/worksheets/sheet{i}.xml", data)


def duration(minutes: float) -> str:
    seconds = minutes * 60
    if not math.isfinite(seconds) or seconds < 0:
        raise ExportError("Длительность или работа выходит за диапазон XML.")
    hours = int(seconds // 3600)
    minute = int((seconds % 3600) // 60)
    second = round(seconds % 60, 6)
    return f"PT{hours}H{minute}M{second:g}S"


def write_project_xml(path: Path, source: ExportSource) -> None:
    """MSPDI interchange; custom values are retained as named entries in Notes."""
    project = source.project
    root = ET.Element("Project", {"xmlns": MSP})
    for key, value in (("SaveVersion", 14), ("Name", project.name), ("Title", project.name),
                       ("ScheduleFromStart", 1), ("CalendarUID", 1), ("MinutesPerDay", 480),
                       ("MinutesPerWeek", len(project.calendar.workdays)*480), ("DaysPerMonth", 20)):
        element(root, key, value)
    if source.rows:
        element(root, "StartDate", min(r["startValue"] for r in source.rows).isoformat(timespec="seconds"))
        element(root, "FinishDate", max(r["endValue"] for r in source.rows).isoformat(timespec="seconds"))
    calendars = element(root, "Calendars")

    def working_times(day, periods) -> None:
        times = element(day, "WorkingTimes")
        for a, b in periods:
            period = element(times, "WorkingTime")
            element(period, "FromTime", f"{a//60:02}:{a%60:02}:00")
            element(period, "ToTime", f"{b//60:02}:{b%60:02}:00")

    def calendar(uid: int, name: str, days: set[int], base: bool, exceptions) -> None:
        record = element(calendars, "Calendar")
        element(record, "UID", uid)
        element(record, "Name", name)
        element(record, "IsBaseCalendar", int(base))
        element(record, "BaseCalendarUID", -1 if base else 1)
        weekdays = element(record, "WeekDays")
        for day_type in range(1, 8):
            day = element(weekdays, "WeekDay")
            element(day, "DayType", day_type)
            working = (day_type+5) % 7 in days
            element(day, "DayWorking", int(working))
            if working:
                working_times(day, project.calendar.weekly_periods.get((day_type+5) % 7, [[540, 780], [840, 1080]]) if base else [[540, 780], [840, 1080]])
        ranges = [(item.start, item.end, item.periods if base else [[540, 780], [840, 1080]] if item.capacity else [])
                  for item in exceptions]
        if base:
            ranges += [(holiday, holiday, []) for holiday in sorted(project.calendar.holidays)
                       if not any(item.start <= holiday <= item.end for item in exceptions)]
        for start, end, periods in sorted(ranges):
            day = element(weekdays, "WeekDay")
            element(day, "DayType", 0)
            element(day, "DayWorking", int(bool(periods)))
            period = element(day, "TimePeriod")
            element(period, "FromDate", start.isoformat() + "T00:00:00")
            element(period, "ToDate", end.isoformat() + "T23:59:59")
            if periods:
                working_times(day, periods)
    calendar(1, "Календарь проекта", project.calendar.workdays, True, project.calendar.exceptions)
    resource_uids = {key: index for index, key in enumerate(project.resources, 1)}
    for key, resource in project.resources.items():
        calendar(resource_uids[key]+1, resource.name, resource.workdays, False, resource.exceptions)
    resources = element(root, "Resources")
    for key, resource in project.resources.items():
        record = element(resources, "Resource")
        for name, value in (("UID", resource_uids[key]), ("ID", resource_uids[key]), ("Name", resource.name),
                            ("Type", 1), ("MaxUnits", resource.capacity/8), ("CalendarUID", resource_uids[key]+1)):
            element(record, name, value)
        if resource.exceptions:
            availability = element(record, "AvailabilityPeriods")
            def available(start: date | None, end: date | None, hours: float, parent=availability) -> None:
                period = element(parent, "AvailabilityPeriod")
                if start is not None:
                    element(period, "AvailableFrom", start.isoformat() + "T00:00:00")
                if end is not None:
                    element(period, "AvailableTo", end.isoformat() + "T23:59:59")
                element(period, "AvailableUnits", hours/8)
            previous = None
            for exception in sorted(resource.exceptions, key=lambda item: item.start):
                first = previous + timedelta(days=1) if previous is not None else None
                if exception.start > date.min and (first is None or first < exception.start):
                    available(first, exception.start - timedelta(days=1), resource.capacity)
                available(exception.start, exception.end, exception.capacity)
                previous = exception.end
            if previous is not None and previous < date.max:
                available(previous + timedelta(days=1), None, resource.capacity)
    task_uids = {row["taskId"]: index for index, row in enumerate(source.rows, 1)}
    tasks = element(root, "Tasks")
    for row in source.rows:
        task = project.tasks[row["taskId"]]
        record = element(tasks, "Task")
        values = (("UID", task_uids[task.id]), ("ID", task_uids[task.id]), ("Name", task.name), ("Type", 1),
                  ("WBS", row["outline"]), ("OutlineNumber", row["outline"]), ("OutlineLevel", row["level"]+1),
                  ("Priority", {"highest": 1000, "high": 750, "medium": 500, "low": 250, "lowest": 0}[task.priority]),
                  ("Start", row["startValue"].isoformat(timespec="seconds")),
                  ("Finish", row["endValue"].isoformat(timespec="seconds")), ("Duration", duration(row["duration"]*60)),
                  ("DurationFormat", 7), ("Work", duration(row["effortHours"]*60)),
                  ("EffortDriven", 0), ("Milestone", int(row["milestone"])), ("Summary", int(row["summary"])),
                  ("FixedCost", f"{row['costValue']:.10f}"), ("PercentComplete", round(row["progress"])),
                  ("Cost", f"{row['costValue']:.10f}"), ("CalendarUID", 1), ("Manual", 1),
                  ("ManualStart", row["startValue"].isoformat(timespec="seconds")),
                  ("ManualFinish", row["endValue"].isoformat(timespec="seconds")),
                  ("ManualDuration", duration(row["duration"]*60)))
        for name, value in values:
            element(record, name, value)
        if task.deadline is not None:
            element(record, "Deadline", task.deadline.isoformat() + "T23:59:59")
        notes = [task.notes, "Статус: " + row["statusText"]]
        baseline = project.baselines.get(project.active_baseline)
        saved = baseline.tasks.get(task.id) if baseline is not None else None
        if baseline is not None and saved is not None:
            baseline_node = element(record, "Baseline")
            element(baseline_node, "Number", 0)
            element(baseline_node, "Start", saved.start.isoformat())
            element(baseline_node, "Finish", saved.end.isoformat())
            notes.append("Базовый план: " + baseline.name)
        notes.extend(f.name + ": " + source.text(row, "custom:" + f.id) for f in project.custom_fields.values()
                     if source.value(row, "custom:" + f.id) is not None)
        element(record, "Notes", "\n".join(part for part in notes if part))
        for link in project.dependencies:
            if link.target == task.id:
                predecessor = element(record, "PredecessorLink")
                element(predecessor, "PredecessorUID", task_uids[link.source])
                element(predecessor, "Type", {"FF": 0, "FS": 1, "SF": 2, "SS": 3}[link.kind])
                element(predecessor, "CrossProject", 0)
                element(predecessor, "LinkLag", link.lag*10)
                element(predecessor, "LagFormat", 7)
    assignments = element(root, "Assignments")
    uid = 0
    for task in project.tasks.values():
        if task.kind == "group":
            continue
        start, end = project.span(task.id)
        for index, key in enumerate(task.resource_ids):
            uid += 1
            hours = task.effort * (task.resource_shares[index] if task.resource_shares else 1/len(task.resource_ids))
            record = element(assignments, "Assignment")
            for name, value in (("UID", uid), ("TaskUID", task_uids[task.id]), ("ResourceUID", resource_uids[key]),
                                ("Units", hours/(task.duration/60) if task.duration else 1),
                                ("Work", duration(hours*60)), ("Start", start.isoformat(timespec="seconds")),
                                ("Finish", end.isoformat(timespec="seconds"))):
                element(record, name, value)
    path.write_bytes(xml_bytes(root))
