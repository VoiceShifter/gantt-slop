from datetime import date, datetime
from pathlib import Path

import pytest

from gantt_desktop.controller import Controller
from gantt_desktop.domain import (
    CalendarException,
    Project,
    ResourceException,
    Task,
)
from gantt_desktop.exporting import (
    ExportDocument,
    ExportOptions,
    ExportSource,
    export_file,
)
from gantt_desktop.xml_import import XmlImportError, parse_project_xml, read_project_xml

DAY = date(2026, 10, 26)
FIXTURE = Path(__file__).parent / "fixtures" / "ganttpro-device-plan.xml"


def dt(text):
    return datetime.fromisoformat(text)


def tiny_xml(task="", calendars="", extra=""):
    return (f'<Project xmlns="http://schemas.microsoft.com/project"><Name>Test</Name>{calendars}<Tasks>{task}</Tasks>{extra}</Project>').encode()


def row(uid="1", name="A", start="2026-01-05T09:00:00", duration="PT8H", finish="", extra="", level=1):
    return (f'<Task><UID>{uid}</UID><Name>{name}</Name><OutlineLevel>{level}</OutlineLevel><Start>{start}</Start>'
            f'<Duration>{duration}</Duration>'+ (f'<Finish>{finish}</Finish>' if finish else '') +extra+'</Task>')


def signature(project):
    tasks = {task.name: (project.tasks[task.parent].name if task.parent else "", task.kind, project.span(task.id), task.duration)
             for task in project.tasks.values()}
    links = sorted((project.tasks[link.source].name, project.tasks[link.target].name, link.kind, link.lag) for link in project.dependencies)
    return tasks, links


def test_real_sanitized_ganttpro_xml_preserves_dates_hierarchy_and_fourteen_links():
    report = read_project_xml(FIXTURE, DAY)
    p = report.project
    assert report.profile == "GanttPRO XML" and len(p.tasks) == 20 and len(p.dependencies) == 14
    sensor = next(task for task in p.tasks.values() if task.name == "Выбор сенсора")
    assert p.span(sensor.id) == (dt("2025-12-11T09:00"), dt("2025-12-15T18:00"))
    assert sensor.duration == 24*60 and sensor.effort == 8
    assert sum(task.effort for task in p.tasks.values()) == 212
    assert p.tasks[sensor.parent].name == "Планирование"
    group = next(task for task in p.tasks.values() if task.name == "Планирование")
    assert p.span(group.id) == (dt("2025-12-01T09:00"), dt("2025-12-26T18:00"))
    checkpoint = next(task for task in p.tasks.values() if task.name == "Приобретение компонентов")
    assert checkpoint.kind == "milestone" and p.span(checkpoint.id)[0] == p.span(checkpoint.id)[1]
    assert not p.resources and any("не содержит ресурсов" in message for message in report.warnings)
    assert any("Work ×60" in message for message in report.warnings)
    assert any("нет стоимости" in message for message in report.warnings)
    assert not any(task.name == "Total estimate" for task in p.tasks.values())


def test_desktop_xml_roundtrip_core_diagram_resources_and_selected_baseline(qapp, tmp_path):
    c = Controller()
    c.project.tasks["sensor"].deadline = date(2025, 12, 31)
    assert c.createBaseline("Original")
    assert c.moveTask("sensor", 7)
    before = c.project.to_dict()
    path = tmp_path / "roundtrip.xml"
    export_file(path, ExportDocument(ExportSource.capture(c), ExportOptions(format="xml")))
    report = read_project_xml(path, DAY)
    assert signature(report.project) == signature(c.project)
    assert {resource.name for resource in report.project.resources.values()} == {resource.name for resource in c.project.resources.values()}
    for task in c.project.tasks.values():
        other = next(item for item in report.project.tasks.values() if item.name == task.name)
        assert other.effort == task.effort and other.cost == task.cost and other.deadline == task.deadline
        assert [report.project.resources[rid].name for rid in other.resource_ids] == [c.project.resources[rid].name for rid in task.resource_ids]
    assert len(report.project.baselines) == 1
    baseline = report.project.baselines[report.project.active_baseline]
    sensor = next(task for task in report.project.tasks.values() if task.name == "Выбор сенсора")
    assert baseline.tasks[sensor.id].start == dt("2025-12-15T09:00")
    assert c.project.to_dict() == before


@pytest.mark.parametrize("kind", ["FS", "SS", "FF", "SF"])
@pytest.mark.parametrize("lag", [-60, 0, 60])
def test_signed_lags_and_all_endpoint_types_roundtrip(qapp, tmp_path, kind, lag):
    p = Project(tasks={"a": Task("a", "A", dt("2026-01-07T10:00"), 480),
                       "b": Task("b", "B", dt("2026-01-08T10:00"), 480)})
    p.add_link("a", "b", kind, lag)
    path = tmp_path / "links.xml"
    export_file(path, ExportDocument(ExportSource.capture(Controller(p)), ExportOptions(format="xml")))
    assert signature(read_project_xml(path, DAY).project) == signature(p)


def test_imported_weekly_hours_and_dated_calendars_survive_native_and_xml_roundtrip(qapp, tmp_path):
    p = Project(tasks={"a": Task("a", "A", dt("2026-01-05T08:00"), 960)})
    p.calendar.weekly_periods = {day: [[480, 720], [780, 1020]] for day in range(5)}
    p.calendar.exceptions = [CalendarException("closed", date(2026, 1, 6), date(2026, 1, 6))]
    p.validate()
    path = tmp_path / "clock.xml"
    export_file(path, ExportDocument(ExportSource.capture(Controller(p)), ExportOptions(format="xml")))
    imported = read_project_xml(path, DAY).project
    assert imported.span("xml-task-1") == p.span("a")
    assert imported.calendar.weekly_periods == p.calendar.weekly_periods
    assert Project.from_dict(imported.to_dict()).to_dict() == imported.to_dict()
    assert imported.to_dict()["version"] == 9


def test_resource_vacation_and_extra_capacity_roundtrip(qapp, tmp_path):
    p = Project(tasks={"a": Task("a", "A", dt("2026-01-05T09:00"), 480, effort=8, assignee="Alice")})
    rid = p.tasks["a"].resource_ids[0]
    p.resources[rid].exceptions = [ResourceException("leave", date(2026, 1, 6), date(2026, 1, 7)),
                                   ResourceException("extra", date(2026, 1, 10), date(2026, 1, 10), capacity=6)]
    path = tmp_path / "availability.xml"
    export_file(path, ExportDocument(ExportSource.capture(Controller(p)), ExportOptions(format="xml")))
    imported = read_project_xml(path, DAY).project
    resource = next(iter(imported.resources.values()))
    assert resource.available(date(2026, 1, 6)) == 0 and resource.available(date(2026, 1, 10)) == 6
    assert resource.available(date(2026, 1, 5)) == 8


def test_explicit_finish_has_priority_with_visible_duration_warning():
    report = parse_project_xml(tiny_xml(row(finish="2026-01-05T17:00:00")), "test", DAY)
    task = next(iter(report.project.tasks.values()))
    assert task.duration == 420 and report.project.span(task.id)[1] == dt("2026-01-05T17:00")
    assert any("Duration уточнён" in warning for warning in report.warnings)


@pytest.mark.parametrize("payload", [
    b'<!DOCTYPE Project [<!ENTITY x "expanded">]><Project><Name>&x;</Name></Project>',
    b'<!DOCTYPE Project SYSTEM "file:///etc/passwd"><Project/>',
    b'<!DOCTYPE Project [<!ENTITY x SYSTEM "https://example.com/private">]><Project><Name>&x;</Name></Project>',
])
@pytest.mark.parametrize("encoding", ["utf-8", "utf-16"])
def test_dtd_entities_and_external_resolution_are_forbidden(payload, encoding):
    data = payload.decode().encode(encoding)
    with pytest.raises(XmlImportError, match="небезопасный"):
        parse_project_xml(data, "unsafe", DAY)


@pytest.mark.parametrize("damage", ["root", "duplicate", "level", "uid", "cycle", "lag", "timezone", "seconds", "negative-duration", "bad-duration", "finish", "calendar"])
def test_invalid_diagram_data_is_rejected_without_partial_project(damage):
    a = row()
    b = row("2", "B", "2026-01-06T09:00:00")
    extra = calendars = ""
    if damage == "root":
        data = b'<NotProject/>'
    else:
        if damage == "duplicate":
            b = row()
        elif damage == "level":
            b = row("2", level=4)
        elif damage == "uid":
            b = row("", "B")
        elif damage == "cycle":
            a = row(extra='<PredecessorLink><PredecessorUID>2</PredecessorUID><Type>3</Type></PredecessorLink>')
            b = row("2", "B", extra='<PredecessorLink><PredecessorUID>1</PredecessorUID><Type>3</Type></PredecessorLink>')
        elif damage == "lag":
            b = row("2", extra='<PredecessorLink><PredecessorUID>1</PredecessorUID><LinkLag>1</LinkLag></PredecessorLink>')
        elif damage == "timezone":
            a = row(start="2026-01-05T09:00:00Z")
        elif damage == "seconds":
            a = row(start="2026-01-05T09:00:01")
        elif damage == "negative-duration":
            a = row(duration="-PT8H")
        elif damage == "bad-duration":
            a = row(duration="P1M")
        elif damage == "finish":
            a = row(finish="2026-01-06T09:00:00")
        else:
            calendars = '<CalendarUID>3</CalendarUID><Calendars><Calendar><UID>1</UID></Calendar></Calendars>'
        data = tiny_xml(a+b, calendars, extra)
    with pytest.raises(ValueError):
        parse_project_xml(data, "bad", DAY)


def test_size_and_depth_limits_fail_before_gui_load(monkeypatch):
    monkeypatch.setattr('gantt_desktop.xml_import.MAX_XML_BYTES', 32)
    with pytest.raises(XmlImportError, match="16 MiB"):
        parse_project_xml(b' '*33, "big", DAY)
    monkeypatch.setattr('gantt_desktop.xml_import.MAX_XML_BYTES', 10000)
    with pytest.raises(XmlImportError, match="глубокий"):
        parse_project_xml(b'<Project>'+b'<x>'*65+b'</x>'*65+b'</Project>', "deep", DAY)


def test_no_namespace_xml_and_real_user_summary_named_total_estimate_are_not_misdetected():
    data = tiny_xml(row(name="Total estimate", finish="2026-01-05T18:00:00")).replace(b' xmlns="http://schemas.microsoft.com/project"', b'')
    report = parse_project_xml(data, "Plain", DAY)
    assert report.profile == "MS Project XML" and next(iter(report.project.tasks.values())).name == "Total estimate"


def test_weekly_interval_validation_and_calendar_edit_preserve_imported_clock():
    p = Project(tasks={"a": Task("a", "A", dt("2026-01-05T09:00"), 480)})
    p.calendar.weekly_periods = {0: [[600, 840]]}
    p.set_workdays({0, 1, 2, 3, 4})
    assert p.calendar.weekly_periods[0] == [[600, 840]]
    p.calendar.weekly_periods = {0: [[720, 600]]}
    with pytest.raises(ValueError):
        p.validate()


@pytest.mark.parametrize("version", range(1, 8))
def test_native_schemas_one_through_seven_keep_default_clock(version):
    p = Project(tasks={"a": Task("a", "A", dt("2026-01-05T09:00"), 480)})
    data = p.to_dict()
    data["version"] = version
    data.pop("weekly_periods")
    restored = Project.from_dict(data)
    assert not restored.calendar.weekly_periods
    assert restored.span("a") == p.span("a") and restored.to_dict()["version"] == 9


@pytest.mark.parametrize("periods", [{7: [[600, 840]]}, {True: [[600, 840]]}, {0: []},
                                      {0: [[600, 840], [780, 900]]}, {0: [[0, 10], [20, 30], [40, 50]]}])
def test_invalid_weekly_intervals_cannot_enter_native_project(periods):
    p = Project()
    p.calendar.workdays = {0}
    p.calendar.weekly_periods = periods
    with pytest.raises(ValueError):
        p.validate()


def test_weekly_interval_snapshots_do_not_alias_native_json():
    p = Project()
    p.calendar.weekly_periods = {0: [[600, 840]]}
    data = p.to_dict()
    restored = Project.from_dict(data)
    restored.calendar.weekly_periods[0][0][0] = 660
    assert p.calendar.weekly_periods[0][0][0] == 600 and data["weekly_periods"][0][0][0] == 600


def test_self_referential_calendar_is_rejected():
    calendar = '<Calendars><Calendar><UID>1</UID><BaseCalendarUID>1</BaseCalendarUID></Calendar></Calendars>'
    with pytest.raises(XmlImportError, match="циклический"):
        parse_project_xml(tiny_xml(row(), calendar), "Cycle", DAY)


@pytest.mark.parametrize("type_", ["0", "2"])
def test_material_and_cost_resources_are_not_silently_reinterpreted_as_people(type_):
    extra = f'<Resources><Resource><UID>1</UID><Name>Alice</Name><Type>{type_}</Type></Resource></Resources>'
    with pytest.raises(XmlImportError, match="Материальные"):
        parse_project_xml(tiny_xml(row(), extra=extra), "Unsupported", DAY)


def test_unknown_assignment_is_fatal_and_mismatched_work_is_reported():
    assignments = '<Assignments><Assignment><TaskUID>1</TaskUID><ResourceUID>1</ResourceUID><Work>PT4H</Work></Assignment></Assignments>'
    with pytest.raises(XmlImportError, match="Назначение"):
        parse_project_xml(tiny_xml(row(), extra=assignments), "Bad", DAY)
    resources = '<Resources><Resource><UID>1</UID><Name>Alice</Name><Type>1</Type></Resource></Resources>'
    report = parse_project_xml(tiny_xml(row(extra='<Work>PT8H</Work>'), extra=resources+assignments), "Work", DAY)
    task = next(iter(report.project.tasks.values()))
    assert task.effort == 8 and len(task.resource_ids) == 1
    assert any("пропорционально" in warning for warning in report.warnings)


@pytest.mark.parametrize("finish", ["2026-01-04T18:00:00", "9999-12-31T18:00:00"])
def test_reversed_or_huge_explicit_finish_rejects_before_working_day_iteration(finish):
    with pytest.raises(XmlImportError, match="диапазон"):
        parse_project_xml(tiny_xml(row(finish=finish)), "Bounded", DAY)
