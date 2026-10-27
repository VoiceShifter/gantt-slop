import csv
from datetime import date
from io import StringIO
from pathlib import Path
from xml.etree.ElementTree import tostring
from xml.sax.saxutils import escape

import pytest
from defusedxml.ElementTree import fromstring
from test_xml_import import DAY, FIXTURE, dt, row, tiny_xml

from gantt_desktop.controller import Controller
from gantt_desktop.domain import (
    CalendarException,
    CustomField,
    Project,
    ResourceException,
    Task,
)
from gantt_desktop.exporting import (
    ExportDocument,
    ExportError,
    ExportOptions,
    ExportSource,
    export_file,
)
from gantt_desktop.ganttpro_csv import read_project_csv, table_rows
from gantt_desktop.xml_fields import FIELD_IDS, METADATA_FIELDS
from gantt_desktop.xml_import import XmlImportError, parse_project_xml, read_project_xml

NS = {"m": "http://schemas.microsoft.com/project"}
CSV_FIXTURE = Path(__file__).parent / "fixtures" / "ganttpro-task-table.csv"


def xml_roundtrip(project, tmp_path):
    controller = Controller(project)
    before = controller.project.to_dict()
    path = tmp_path / "plan.xml"
    export_file(path, ExportDocument(ExportSource.capture(controller), ExportOptions(format="xml")))
    assert controller.project.to_dict() == before
    return read_project_xml(path, DAY).project, fromstring(path.read_bytes())


def definition(uid="188743731", name="Text1", kind="7", alias="Extra", rollup=""):
    return (f"<ExtendedAttributes><ExtendedAttribute><FieldID>{uid}</FieldID><FieldName>{name}</FieldName>"
            f"<CFType>{kind}</CFType><Alias>{escape(alias)}</Alias>{rollup}</ExtendedAttribute></ExtendedAttributes>")


def attribute(value, uid="188743731"):
    return f"<ExtendedAttribute><FieldID>{uid}</FieldID><Value>{escape(value)}</Value></ExtendedAttribute>"


def closed(start="2026-01-05", end="2026-01-09", working=False):
    slots = ("<WorkingTimes><WorkingTime><FromTime>09:00:00</FromTime><ToTime>13:00:00</ToTime></WorkingTime>"
             "<WorkingTime><FromTime>14:00:00</FromTime><ToTime>18:00:00</ToTime></WorkingTime></WorkingTimes>") if working else ""
    return (f"<WeekDay><DayType>0</DayType><DayWorking>{int(working)}</DayWorking><TimePeriod>"
            f"<FromDate>{start}T00:00:00</FromDate><ToDate>{end}T23:59:59</ToDate></TimePeriod>{slots}</WeekDay>")


def calendar(uid, base="-1", days=""):
    return f"<Calendar><UID>{uid}</UID><BaseCalendarUID>{base}</BaseCalendarUID><WeekDays>{days}</WeekDays></Calendar>"


def test_ganttpro_work_fix_requires_the_known_exporter_signature():
    data = FIXTURE.read_bytes()
    for old, new in ((b"Export Tool v.2.1.0.0", b"Another exporter"), (b"<WorkFormat>2", b"<WorkFormat>3"),
                     (b"<SaveVersion>9", b"<SaveVersion>14")):
        changed = data.replace(old, new)
        report = parse_project_xml(changed, "unknown", DAY)
        sensor = next(task for task in report.project.tasks.values() if task.name == "Выбор сенсора")
        assert sensor.effort == pytest.approx(8/60)
        assert not any("Work ×60" in warning for warning in report.warnings)


def test_corrected_ganttpro_work_is_not_multiplied_again_on_desktop_reexport(qapp, tmp_path):
    original = read_project_xml(FIXTURE, DAY).project
    imported, root = xml_roundtrip(original, tmp_path)
    assert sum(task.effort for task in imported.tasks.values()) == 212
    assert root.findtext("m:SaveVersion", namespaces=NS) == "14"
    assert len(imported.dependencies) == 14
    assert {task.name: imported.span(task.id) for task in imported.tasks.values()} == {
        task.name: original.span(task.id) for task in original.tasks.values()}


def test_supplied_table_cells_survive_csv_to_xml_to_csv(qapp, tmp_path):
    original = read_project_csv(CSV_FIXTURE).project
    imported, root = xml_roundtrip(original, tmp_path)
    controller = Controller(imported)
    expected = list(csv.reader(StringIO(CSV_FIXTURE.read_text(encoding="utf-8-sig"))))[1:]
    assert table_rows(imported, ExportSource.capture(controller).rows) == expected
    assert len(imported.resources) == 3 and len(imported.dependencies) == 14
    assert sum(task.cost for task in imported.tasks.values()) == 38000
    assert any(resource.name.endswith(" ") for resource in imported.resources.values())
    assert root.findall("m:Tasks/m:Task/m:ActualCost", NS)
    assert root.findall("m:Tasks/m:Task/m:CreateDate", NS)


@pytest.mark.parametrize("progress,status", [(0, "open"), (12.345, "in_progress"), (99.9, "in_progress"),
                                            (100, "completed"), (100, "closed")])
def test_colors_exact_progress_status_and_notes_do_not_degrade_or_grow(qapp, tmp_path, progress, status):
    notes = "  Original & <literal>\r\nСтатус: user text\nБазовый план: user text  \n"
    task = Task("a", " Name & <literal> ", dt("2026-01-05T09:00"), 480,
                color="#123AbC", progress=progress, status=status, notes=notes, cost=0.0000000000123)
    project = Project(" Project ", {"a": task})
    for _ in range(3):
        project, _root = xml_roundtrip(project, tmp_path)
        other = next(iter(project.tasks.values()))
        assert (other.color, other.progress, other.status, other.notes, other.cost) == (task.color, progress, status, notes, task.cost)
        assert other.name == task.name and project.name == " Project "


@pytest.mark.parametrize("kind,value", [("text", " =1+1 & <literal>\n "), ("number", 0), ("number", -12.25),
                                      ("checkbox", False), ("checkbox", True), ("date", "2026-02-28")])
def test_typed_extended_attributes_roundtrip_without_notes(qapp, tmp_path, kind, value):
    field = CustomField("field", "Example", kind, aggregate="average" if kind == "number" else "")
    project = Project(tasks={"a": Task("a", "A", dt("2026-01-05T09:00"), 480)}, custom_fields={field.id: field})
    project.set_custom_value("a", field.id, value)
    imported, _root = xml_roundtrip(project, tmp_path)
    other_field = next(iter(imported.custom_fields.values()))
    other = next(iter(imported.tasks.values()))
    assert (other_field.name, other_field.kind, other_field.aggregate) == (field.name, kind, field.aggregate)
    assert other.custom_values[other_field.id] == value and not other.notes


@pytest.mark.parametrize("aggregate,total", [("sum", 4), ("average", 2)])
def test_numeric_group_rollups_keep_their_meaning(qapp, tmp_path, aggregate, total):
    field = CustomField("n", "Number", "number", aggregate=aggregate)
    project = Project(tasks={"g": Task("g", "Group", dt("2026-01-05T09:00"), 0, kind="group"),
                             "a": Task("a", "A", dt("2026-01-05T09:00"), 480, parent="g"),
                             "b": Task("b", "B", dt("2026-01-05T09:00"), 480, parent="g")}, custom_fields={"n": field})
    project.set_custom_value("a", "n", 0)
    project.set_custom_value("b", "n", 4)
    imported, _root = xml_roundtrip(project, tmp_path)
    assert imported.custom_value("xml-task-1", "xml-field-188743767") == total


@pytest.mark.parametrize("kind", ["text", "number", "date", "checkbox"])
def test_real_field_slots_are_unique_at_capacity_and_overflow_is_rejected(qapp, tmp_path, kind):
    project = Project(tasks={"a": Task("a", "A", dt("2026-01-05T09:00"), 480)})
    for index in range(len(FIELD_IDS[kind])):
        key = str(index)
        project.custom_fields[key] = CustomField(key, "Field "+key, kind, aggregate="sum" if kind == "number" else "")
    imported, root = xml_roundtrip(project, tmp_path)
    assert len(imported.custom_fields) == len(FIELD_IDS[kind])
    definitions = root.findall("m:ExtendedAttributes/m:ExtendedAttribute", NS)
    ids = [field.findtext("m:FieldID", namespaces=NS) for field in definitions]
    assert len(set(ids)) == len(ids)
    assert {str(uid) for _key, uid, _name, _alias, _type in METADATA_FIELDS}.issubset(ids)
    project.custom_fields["overflow"] = CustomField("overflow", "Overflow", kind, aggregate="sum" if kind == "number" else "")
    path = tmp_path / "plan.xml"
    before = path.read_bytes()
    with pytest.raises(ExportError, match="лимит XML-полей"):
        export_file(path, ExportDocument(ExportSource.capture(Controller(project)), ExportOptions(format="xml")))
    assert path.read_bytes() == before


@pytest.mark.parametrize("kind,value", [("1", "2026-01-05T12:00:00"), ("4", "yes"), ("5", "NaN"), ("5", "inf")])
def test_unrepresentable_typed_values_fail_before_live_replacement(kind, value):
    data = tiny_xml(row(extra=attribute(value)), extra=definition(kind=kind))
    with pytest.raises(ValueError):
        parse_project_xml(data, "invalid", DAY)


def test_unsupported_field_is_preserved_once_in_notes_and_named_in_report(qapp, tmp_path):
    report = parse_project_xml(tiny_xml(row(extra=attribute("PT8H")), extra=definition(kind="2", alias="Estimate")), "unknown", DAY)
    assert not report.project.custom_fields
    assert next(iter(report.project.tasks.values())).notes == "Estimate: PT8H"
    assert any("Estimate" in message for message in report.warnings)
    imported, _root = xml_roundtrip(report.project, tmp_path)
    assert next(iter(imported.tasks.values())).notes == "Estimate: PT8H"


@pytest.mark.parametrize("which", ["definition", "value"])
def test_duplicate_field_definitions_or_values_are_rejected(which):
    defs = definition()
    values = attribute("one")
    if which == "definition":
        defs = defs.replace("</ExtendedAttributes>", defs.removeprefix("<ExtendedAttributes>"))
    else:
        values += attribute("two")
    with pytest.raises(XmlImportError, match="Повторяющ"):
        parse_project_xml(tiny_xml(row(extra=values), extra=defs), "duplicate", DAY)


def test_standard_actuals_are_metadata_not_a_time_journal(qapp, tmp_path):
    data = tiny_xml(row(extra="<ActualWork>PT1H30M</ActualWork><ActualCost>123.450</ActualCost>"
                             "<CreateDate>2026-01-01T12:34:56</CreateDate><FixedCost>20</FixedCost><Cost>100</Cost>"))
    project = parse_project_xml(data, "actuals", DAY).project
    task = next(iter(project.tasks.values()))
    assert task.cost == 100
    assert task.custom_values == {"ganttpro_spent_minutes": "90", "ganttpro_actual_cost": "123.450", "ganttpro_created": "2026-01-01 12:34:56"}
    imported, root = xml_roundtrip(project, tmp_path)
    assert next(iter(imported.tasks.values())).custom_values == task.custom_values
    assert root.findtext("m:Tasks/m:Task/m:ActualWork", namespaces=NS) == "PT1H30M0S"


def test_selected_baseline_name_and_creation_date_survive_without_polluting_notes(qapp, tmp_path):
    project = Project(tasks={"a": Task("a", "A", dt("2026-01-05T09:00"), 480, notes="Original note")})
    saved = project.capture_baseline("Original & <saved>", date(2026, 1, 1))
    project.capture_baseline("Not selected", date(2026, 1, 2))
    project.select_baseline(saved)
    project.move("a", 7)
    imported, _root = xml_roundtrip(project, tmp_path)
    baseline = imported.baselines[imported.active_baseline]
    assert len(imported.baselines) == 1 and baseline.name == "Original & <saved>" and baseline.created == date(2026, 1, 1)
    assert baseline.tasks["xml-task-1"].start == dt("2026-01-05T09:00")
    assert imported.tasks["xml-task-1"].notes == "Original note"


def test_child_calendar_overrides_and_splits_inherited_ranges():
    calendars = "<CalendarUID>2</CalendarUID><Calendars>"+calendar("1", days=closed())+calendar("2", "1", closed("2026-01-07", "2026-01-07", True))+"</Calendars>"
    report = parse_project_xml(tiny_xml(row(start="2026-01-07T09:00:00"), calendars), "override", DAY)
    cal = report.project.calendar
    assert len(cal.exceptions) == 3
    assert not cal.working_day(date(2026, 1, 6)) and cal.working_day(date(2026, 1, 7)) and not cal.working_day(date(2026, 1, 8))
    assert report.project.span("xml-task-1")[1] == dt("2026-01-07T18:00")


def test_overlapping_project_and_resource_exceptions_roundtrip_independently(qapp, tmp_path):
    project = Project(tasks={"a": Task("a", "A", dt("2026-01-12T09:00"), 480, effort=8, assignee="Alice ")})
    project.calendar.exceptions = [CalendarException("off", date(2026, 1, 5), date(2026, 1, 9))]
    resource = next(iter(project.resources.values()))
    resource.exceptions = [ResourceException("half", date(2026, 1, 7), date(2026, 1, 7), capacity=4)]
    imported, _root = xml_roundtrip(project, tmp_path)
    other = next(iter(imported.resources.values()))
    assert other.available(date(2026, 1, 6)) == 8 and other.available(date(2026, 1, 7)) == 4
    assert not imported.calendar.working_day(date(2026, 1, 7))


def test_resource_inherits_its_own_base_and_availability_overrides_part_of_it():
    calendars = "<CalendarUID>1</CalendarUID><Calendars>"+calendar("1")+calendar("2", days=closed())+calendar("3", "2")+"</Calendars>"
    resource = ("<Resources><Resource><UID>1</UID><Name>Alice</Name><CalendarUID>3</CalendarUID>"
                "<AvailabilityPeriods><AvailabilityPeriod><AvailableFrom>2026-01-07T00:00:00</AvailableFrom>"
                "<AvailableTo>2026-01-07T23:59:59</AvailableTo><AvailableUnits>0.5</AvailableUnits>"
                "</AvailabilityPeriod></AvailabilityPeriods></Resource></Resources>")
    report = parse_project_xml(tiny_xml(row(), calendars, resource), "availability", DAY)
    other = next(iter(report.project.resources.values()))
    assert other.available(date(2026, 1, 6)) == 0 and other.available(date(2026, 1, 7)) == 4 and other.available(date(2026, 1, 8)) == 0


@pytest.mark.parametrize("ranges", [closed()+closed(), closed("2026-01-09", "2026-01-05"), closed("1900-01-01", "2101-01-01")])
def test_invalid_or_overlarge_calendar_ranges_are_rejected(ranges):
    with pytest.raises(ValueError):
        parse_project_xml(tiny_xml(row(), "<Calendars>"+calendar("1", days=ranges)+"</Calendars>"), "ranges", DAY)


def test_negative_assignment_units_are_not_normalized_to_positive_shares():
    extra = ("<Resources><Resource><UID>1</UID><Name>Alice</Name></Resource></Resources>"
             "<Assignments><Assignment><TaskUID>1</TaskUID><ResourceUID>1</ResourceUID><Units>-1</Units></Assignment></Assignments>")
    with pytest.raises(XmlImportError, match="Отрицательная"):
        parse_project_xml(tiny_xml(row(), extra=extra), "units", DAY)


def test_xml_preview_always_matches_the_whole_written_tree_without_graphical_analysis(qapp, tmp_path):
    controller = Controller()
    controller.search("Выбор сенсора")
    source = ExportSource.capture(controller)
    doc = ExportDocument(source, ExportOptions(format="xml", scope="visible", start=date(2030, 1, 1),
                                               end=date(2030, 1, 2), content="chart", workload=True, critical=True, baseline=True))
    assert len(doc.rows) == len(controller.project.tasks) and doc.options.content == "table"
    assert not doc.options.workload and not doc.options.critical and not doc.options.baseline
    assert doc.start.year == 2025 and not doc.resources and doc.analysis is None


@pytest.mark.parametrize("tag,order", [
    ("Project", "SaveVersion Name Title ScheduleFromStart StartDate FinishDate CalendarUID MinutesPerDay MinutesPerWeek DaysPerMonth ExtendedAttributes Calendars Tasks Resources Assignments"),
    ("Task", "UID ID Name Type CreateDate WBS OutlineNumber OutlineLevel Priority Start Finish Duration DurationFormat Work EffortDriven Milestone Summary FixedCost PercentComplete Cost ActualCost ActualWork CalendarUID Deadline Notes PredecessorLink ExtendedAttribute Baseline Manual ManualStart ManualFinish ManualDuration"),
    ("Assignment", "UID TaskUID ResourceUID Finish Start Units Work"),
])
def test_published_mspdi_sequence_order_is_not_just_accepted_by_our_own_reader(qapp, tmp_path, tag, order):
    # Ordering comes from Microsoft's published Project/Tasks/Assignments XSDs.
    project = read_project_csv(CSV_FIXTURE).project
    project.capture_baseline("Original", date(2026, 1, 1))
    _imported, root = xml_roundtrip(project, tmp_path)
    nodes = [root] if tag == "Project" else root.findall(".//m:"+tag, NS)
    assert nodes
    sequence = order.split()
    for node in nodes:
        positions = [sequence.index(child.tag.split("}")[-1]) for child in node]
        assert positions == sorted(positions)


@pytest.mark.parametrize("kind,value,options", [("select", "One", ["One", "Two"]), ("multi", ["One", "Two"], ["One", "Two"]),
                                               ("color", "#123abc", []), ("labels", ["One", "Two"], []), ("people", ["r"], [])])
def test_complex_fields_have_the_documented_literal_text_boundary(qapp, tmp_path, kind, value, options):
    project = Project(tasks={"a": Task("a", "A", dt("2026-01-05T09:00"), 480, assignee="Alice")})
    resource = next(iter(project.resources.values()))
    if kind == "people":
        value = [resource.id]
    field = CustomField("field", "Example", kind, options)
    project.save_custom_field(field)
    project.set_custom_value("a", "field", value)
    expected = field.display(value, project.resources)
    imported, _root = xml_roundtrip(project, tmp_path)
    other_field = next(iter(imported.custom_fields.values()))
    assert other_field.kind == "text"
    assert imported.tasks["xml-task-1"].custom_values[other_field.id] == expected
    assert not imported.tasks["xml-task-1"].notes


@pytest.mark.parametrize("capacity", [0, 8, 24])
def test_resources_without_weekly_workdays_remain_valid_resources_not_project_calendars(qapp, tmp_path, capacity):
    project = Project(tasks={"a": Task("a", "A", dt("2026-01-05T09:00"), 480, assignee="Alice")})
    resource = next(iter(project.resources.values()))
    resource.workdays = set()
    resource.capacity = capacity
    imported, _root = xml_roundtrip(project, tmp_path)
    other = next(iter(imported.resources.values()))
    assert not other.workdays and other.capacity == capacity and other.available(date(2026, 1, 5)) == 0
    assert imported.calendar.workdays == {0, 1, 2, 3, 4}


@pytest.mark.parametrize("key,bad", [("color", "#bad"), ("status", "closed"), ("progress", "99")])
def test_invalid_or_stale_named_metadata_fails_instead_of_overriding_visible_standard_data(qapp, tmp_path, key, bad):
    project = Project(tasks={"a": Task("a", "A", dt("2026-01-05T09:00"), 480)})
    _imported, root = xml_roundtrip(project, tmp_path)
    uid = next(str(uid) for key_, uid, _name, _alias, _type in METADATA_FIELDS if key_ == key)
    item = next(item for item in root.findall("m:Tasks/m:Task/m:ExtendedAttribute", NS) if item.findtext("m:FieldID", namespaces=NS) == uid)
    value = item.find("m:Value", NS)
    assert value is not None
    value.text = bad
    with pytest.raises(ValueError):
        parse_project_xml(tostring(root), "invalid", DAY)
