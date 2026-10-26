import csv
import io
from collections import Counter
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path

import pytest

from gantt_desktop.domain import Project
from gantt_desktop.ganttpro_csv import (
    HEADERS,
    CsvImportError,
    parse_project_csv,
    read_project_csv,
)
from gantt_desktop.xml_import import read_project_xml

FIXTURE = Path(__file__).parent / "fixtures" / "ganttpro-task-table.csv"


def basic(wbs="1", name="A"):
    return ["#50c7d6", wbs, "", name, "Alice", "2026-01-05 09:00:00", "2026-01-05 18:00:00", "", "0", "8", "8", "0",
            "Открыт", "Средний", "Описание, с запятой\nи новой строкой", "", "120.5", "3.5", "2026-01-01 10:11:12", "Автор", "задача", "CSV test", "1"]


def encoded(rows, delimiter=",", encoding="utf-8-sig", headers=HEADERS):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=delimiter)
    writer.writerow(headers)
    writer.writerows(rows)
    return stream.getvalue().encode(encoding)


def test_supplied_table_retains_all_twenty_elements_fourteen_links_colors_effort_cost_and_metadata():
    report = read_project_csv(FIXTURE)
    p = report.project
    assert len(p.tasks) == 20 and len(p.dependencies) == 14 and len(p.resources) == 3
    assert Counter(t.kind for t in p.tasks.values()) == {"group": 4, "task": 15, "milestone": 1}
    assert sum(t.effort for t in p.tasks.values() if t.kind != "group") == 212
    assert sum(t.cost for t in p.tasks.values() if t.kind != "group") == 38000
    assert p.span("csv-task-1.2") == (datetime.fromisoformat("2025-12-11T09:00"), datetime.fromisoformat("2025-12-15T18:00"))
    assert p.tasks["csv-task-2.3"].color == "#d860bb" and p.tasks["csv-task-1.2"].color == "#50c7d6"
    assert len(p.custom_fields) == 4
    assert p.custom_value("csv-task-1", "ganttpro_creator") == "Автор примера"
    assert p.custom_value("csv-task-1.2", "ganttpro_spent_minutes") == "0"
    assert p.custom_value("csv-task-1.2", "ganttpro_actual_cost") == "0"
    other = read_project_xml(FIXTURE.with_name("ganttpro-device-plan.xml"), date(2026, 10, 26)).project
    by_name = {task.name: task for task in other.tasks.values()}
    for task in p.tasks.values():
        assert p.span(task.id) == other.span(by_name[task.name].id)
    def links(q):
        return {(q.tasks[d.source].name, q.tasks[d.target].name, d.kind, d.lag) for d in q.dependencies}
    assert links(p) == links(other)


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "cp1251"])
@pytest.mark.parametrize("delimiter", [",", ";", "\t"])
def test_common_excel_csv_encodings_and_delimiters(encoding, delimiter):
    p = parse_project_csv(encoded([basic()], delimiter, encoding)).project
    assert p.name == "CSV test" and p.tasks["csv-task-1"].effort == 8
    assert p.tasks["csv-task-1"].notes == basic()[14]


@pytest.mark.parametrize("kind", ["FS", "SS", "FF", "SF"])
@pytest.mark.parametrize("lag", [-7, 0, 7])
def test_explicit_endpoint_types_and_whole_working_minute_lags_are_read_without_rescheduling(kind, lag):
    first, second = basic(), basic("2", "B")
    second[15] = "1 "+kind+(f" {lag:+d}m" if lag else "")
    p = parse_project_csv(encoded([first, second])).project
    assert len(p.dependencies) == 1
    assert p.dependencies[0].kind == kind and p.dependencies[0].lag == lag
    assert p.tasks["csv-task-2"].start == datetime.fromisoformat("2026-01-05T09:00")


def test_plain_predecessors_default_to_fs_zero_and_inconsistent_source_dates_are_reported():
    a, b = basic(), basic("2", "B")
    b[15] = "1"
    report = parse_project_csv(encoded([a, b]))
    assert report.project.dependencies[0].kind == "FS" and report.project.dependencies[0].lag == 0
    assert any("Несогласованных" in warning for warning in report.warnings)
    assert report.project.span("csv-task-2")[0] == datetime.fromisoformat("2026-01-05T09:00")


def test_named_roster_and_quoted_names_are_entities_not_an_assignment_string():
    row = basic()
    row[4] = '"Doe, Jane",Second'
    p = parse_project_csv(encoded([row])).project
    task = p.tasks["csv-task-1"]
    assert [p.resources[rid].name for rid in task.resource_ids] == ["Doe, Jane", "Second"]
    assert task.effort == 8 and task.resource_shares == []


@pytest.mark.parametrize("value", ["2026-01-05", "05.01.2026", "2026-01-05T23:59:59", "2026-01-05 00:00:00"])
def test_date_only_deadlines_are_not_schedule_constraints(value):
    row = basic()
    row[7] = value
    p = parse_project_csv(encoded([row])).project
    assert p.tasks["csv-task-1"].deadline == date(2026, 1, 5)
    assert p.span("csv-task-1")[1] == datetime.fromisoformat("2026-01-05T18:00")


def test_russian_datetime_and_raw_excel_date_serials_preserve_clock_times():
    row = basic()
    row[5:7] = ["46027.375", "05.01.2026 18:00"]
    p = parse_project_csv(encoded([row])).project
    assert p.span("csv-task-1") == (datetime.fromisoformat("2026-01-05T09:00"), datetime.fromisoformat("2026-01-05T18:00"))


def test_empty_group_and_milestone_remain_distinct_and_snapshot_values_do_not_alias():
    group, milestone = basic(), basic("2", "Point")
    group[2:5] = ["Empty group", "", ""]
    group[6] = group[5]
    group[9:11] = ["0", "0"]
    group[12:14] = ["", ""]
    group[16] = "0"
    group[20] = "проект"
    milestone[6] = milestone[5]
    milestone[9] = "0"
    milestone[20] = "веха"
    p = parse_project_csv(encoded([group, milestone])).project
    assert p.tasks["csv-task-1"].kind == "group" and p.tasks["csv-task-2"].kind == "milestone"
    original = deepcopy(p.to_dict())
    restored = Project.from_dict(original)
    restored.tasks["csv-task-1"].custom_values["ganttpro_creator"] = "Changed"
    assert p.to_dict() == original


@pytest.mark.parametrize(("index", "value"), [
    (0, "red"), (1, "1..2"), (1, "0"), (1, "1.01"), (3, ""), (5, "2026-01-05T09:00:01"),
    (5, "2026-01-05T09:00:00Z"), (6, "2026-01-04 18:00"), (6, "9999-12-31 18:00"),
    (7, "2026-01-05T12:00:00"), (7, "2026-01-05 12:00"), (8, "101"), (8, "-1"),
    (9, "0.0001"), (9, "9"), (10, "NaN"), (11, "-1"), (12, "Unknown"), (12, "Выполнено"),
    (13, "Unknown"), (15, "99"), (15, "1 FS +0.5m"), (16, "inf"), (17, "-1"),
    (18, "not a date"), (20, "unknown"), (22, "2"),
])
def test_invalid_or_unrepresentable_cells_reject_the_complete_import(index, value):
    row = basic()
    row[index] = value
    with pytest.raises(ValueError):
        parse_project_csv(encoded([row]))


@pytest.mark.parametrize("damage", ["duplicate", "missing-parent", "task-parent", "cycle", "duplicate-link", "short-row", "header", "no-data", "project-path"])
def test_invalid_structure_references_headers_and_row_shapes_are_rejected(damage):
    a, b = basic(), basic("2", "B")
    rows = [a, b]
    headers = HEADERS
    if damage == "duplicate":
        b[1] = "1"
    elif damage == "missing-parent":
        b[1], b[22] = "3.1", "2"
    elif damage == "task-parent":
        b[1], b[22] = "1.1", "2"
    elif damage == "cycle":
        a[15], b[15] = "2 SS", "1 SS"
    elif damage == "duplicate-link":
        b[15] = "1, 1"
    elif damage == "short-row":
        b.pop()
    elif damage == "header":
        headers = (*HEADERS[:2], "invented", *HEADERS[3:])
    elif damage == "project-path":
        b[21] = "Other project"
    else:
        rows = []
    with pytest.raises(ValueError):
        parse_project_csv(encoded(rows, headers=headers))


def test_import_limits_and_binary_input_are_bounded(monkeypatch):
    monkeypatch.setattr('gantt_desktop.ganttpro_csv.MAX_BYTES', 32)
    with pytest.raises(CsvImportError, match="16 MiB"):
        parse_project_csv(b' '*33)
    monkeypatch.setattr('gantt_desktop.ganttpro_csv.MAX_BYTES', 100000)
    monkeypatch.setattr('gantt_desktop.ganttpro_csv.MAX_TASKS', 0)
    with pytest.raises(CsvImportError, match="2000"):
        parse_project_csv(encoded([basic()]))
    with pytest.raises(CsvImportError, match="нулевые"):
        parse_project_csv(b'bad\x00input')
