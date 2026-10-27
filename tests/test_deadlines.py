import csv
from copy import deepcopy
from datetime import date, datetime
from zipfile import ZipFile

import pytest
from conftest import wait_until
from dialog_helpers import click_native, required_widget
from PySide6.QtCore import QDate, QMetaObject, QObject, QPoint, Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QCalendarWidget
from test_custom_fields_ui import toggle_list
from test_exporting import generated_xml, pdf_document
from test_ui import drag, item, point

from gantt_desktop.controller import Controller
from gantt_desktop.domain import Project, ScheduleError, Task
from gantt_desktop.exporting import (
    ExportDocument,
    ExportOptions,
    ExportSource,
    export_file,
)
from gantt_desktop.interchange import MSP, SS


def without_deadlines(project):
    data = project.to_dict()
    for task in data["tasks"]:
        task.pop("deadline")
    return data


def open_inspector(c, window, task_id="sensor"):
    c.select(task_id)
    inspector = window.findChild(QObject, "taskInspector")
    assert inspector is not None and QMetaObject.invokeMethod(inspector, "open")
    wait_until(lambda: inspector.property("opened"))


@pytest.mark.parametrize("value", [None, date.min, date.max, date(2025, 12, 20)])
def test_deadline_round_trips_as_optional_iso_date_without_schedule_changes(value):
    p = Project(tasks={"a": Task("a", "A", datetime.fromisoformat("2025-12-01T09:00"))})
    before = without_deadlines(p)
    p.tasks["a"].deadline = value
    p.validate()
    data = p.to_dict()
    assert data["version"] == 9
    assert data["tasks"][0]["deadline"] == (value.isoformat() if value else None)
    restored = Project.from_dict(data)
    assert restored.tasks["a"].deadline == value and restored.to_dict() == data
    assert without_deadlines(p) == before


@pytest.mark.parametrize("value", ["2025-12-01", True, 0, datetime.fromisoformat("2025-12-01T09:00")])
def test_domain_rejects_non_date_deadlines(value):
    p = Project(tasks={"a": Task("a", "A", datetime.fromisoformat("2025-12-01T09:00"))})
    p.tasks["a"].deadline = value
    with pytest.raises(ScheduleError, match="Крайний срок"):
        p.validate()


@pytest.mark.parametrize("version", [1, 2, 3, 4])
def test_older_schemas_without_deadlines_remain_readable(qapp, version):
    data = Controller().project.to_dict()
    data["version"] = version
    for task in data["tasks"]:
        task.pop("deadline")
    restored = Project.from_dict(data)
    assert all(t.deadline is None for t in restored.tasks.values())
    assert restored.to_dict()["version"] == 9


@pytest.mark.parametrize("task_id", ["sensor", "controller", "components", "planning"])
def test_deadline_edit_is_independent_of_schedule_constraints_and_single_undo(qapp, task_id):
    c = Controller()
    before = c.project.to_dict()
    schedule = without_deadlines(c.project)
    assert c.editField(task_id, "deadline", "20.12.2025")
    assert c.project.tasks[task_id].deadline == date(2025, 12, 20)
    assert without_deadlines(c.project) == schedule
    after = c.project.to_dict()
    assert c.editField(task_id, "deadline", "2025-12-20")
    c.undo()
    assert c.project.to_dict() == before and not c.canUndo
    c.redo()
    assert c.project.to_dict() == after
    assert c.editField(task_id, "deadline", "")
    assert c.project.tasks[task_id].deadline is None
    c.undo()
    assert c.project.to_dict() == after


@pytest.mark.parametrize("value", ["2026-02-30", "31.02.2026", "2025-12-20T09:00", "tomorrow", None, 123])
def test_invalid_deadline_edit_rolls_back_without_history(qapp, value):
    c = Controller()
    before = c.project.to_dict()
    assert not c.editField("sensor", "deadline", value)
    assert c.project.to_dict() == before and not c.canUndo


def test_deadline_is_inclusive_and_past_unfinished_deadlines_are_overdue(qapp, monkeypatch):
    monkeypatch.setattr("gantt_desktop.controller.local_today", lambda: date(2025, 12, 17))
    c = Controller()
    assert c.editField("sensor", "deadline", "2025-12-17")
    assert not c.record("sensor")["deadlineMissed"] and not c.record("sensor")["deadlineOverdue"]
    assert c.editField("sensor", "deadline", "2025-12-16")
    assert c.record("sensor")["deadlineMissed"] and c.record("sensor")["deadlineOverdue"]
    assert c.editField("sensor", "progress", "100")
    assert c.record("sensor")["deadlineMissed"] and not c.record("sensor")["deadlineOverdue"]
    assert c.editField("planning", "deadline", "2025-12-19")
    assert c.record("planning")["deadlineMissed"]


def test_overdue_filter_includes_expired_deadline_before_a_future_planned_finish(qapp, monkeypatch):
    monkeypatch.setattr("gantt_desktop.controller.local_today", lambda: date(2025, 12, 2))
    c = Controller()
    assert c.editField("sensor", "deadline", "2025-12-01")
    c.setFilter("overdue")
    ids = {r["taskId"] for r in c._rows.records if r["rowKind"] == "task"}
    assert "sensor" in ids and "controller" not in ids


def test_deadlines_save_reopen_and_invalid_file_preserves_current_project(qapp, tmp_path):
    c = Controller()
    assert c.editField("sensor", "deadline", "2025-12-20")
    path = tmp_path / "project.json"
    assert c.save_path(path)
    other = Controller()
    assert other.load_path(path) and other.project.to_dict() == c.project.to_dict()
    invalid = deepcopy(other.project.to_dict())
    invalid["tasks"][0]["deadline"] = "2025-02-30"
    with pytest.raises(ValueError):
        Project.from_dict(invalid)
    assert other.project.to_dict() == c.project.to_dict()


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("width", [1000, 1920])
def test_inspector_sets_cancels_warns_and_clears_deadline_with_real_controls(gui, dark, width):
    c, window = gui
    assert c.theme is not None
    c.theme.setDark(dark)
    window.resize(width, 960)
    open_inspector(c, window, "controller")
    before = c.project.to_dict()
    button = item(window, "calendar-inspectorDeadline")
    assert button.isEnabled()
    assert point(button).x() <= width - 32
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(button))
    wait_until(lambda: bool(c.dialogs.modalOpen))
    widget = required_widget("taskDateCalendar")
    assert isinstance(widget, QCalendarWidget)
    widget.setSelectedDate(QDate(2025, 12, 1))
    assert click_native("taskDateCancel")
    assert c.project.to_dict() == before and not c.canUndo
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(button))
    wait_until(lambda: bool(c.dialogs.modalOpen))
    widget.setSelectedDate(QDate(2025, 12, 1))
    assert click_native("taskDateSave")
    wait_until(lambda: c.selected["deadline"] == "01.12.2025")
    assert item(window, "deadlineWarning").isVisible()
    clear = item(window, "clearDeadline")
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(clear))
    wait_until(lambda: c.project.tasks["controller"].deadline is None)
    c.undo()
    assert c.project.tasks["controller"].deadline == date(2025, 12, 1)


def test_deadline_standard_column_picker_and_calendar_clear_are_real(gui):
    c, window = gui
    view = item(window, "ganttView")
    for key in ("showAssignee", "showEffort", "showCost"):
        view.setProperty(key, False)
    c.dialogs.showFields({"deadline": False})
    toggle_list(required_widget("standardFields"), "deadline")
    assert click_native("closeFields")
    wait_until(lambda: bool(view.property("showDeadline")))
    button = item(window, "calendar-task-deadline-sensor")
    wait_until(button.isVisible)
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(button))
    wait_until(lambda: bool(c.dialogs.modalOpen))
    assert click_native("taskDateSave")
    assert c.project.tasks["sensor"].deadline == c.project.span("sensor")[1].date()
    c.dialogs.showTaskDate("sensor", "deadline")
    assert click_native("taskDeadlineUnset") and click_native("taskDateSave")
    assert c.project.tasks["sensor"].deadline is None


def test_deadline_marker_tracks_zoom_and_does_not_steal_bar_resize(gui):
    c, window = gui
    assert c.editField("sensor", "deadline", c.project.span("sensor")[1].date().isoformat())
    view = item(window, "ganttView")
    marker = item(window, "deadline-marker-sensor")
    wait_until(marker.isVisible)
    for scale in (26, 10):
        view.setProperty("pixelsPerDay", scale)
        wait_until(lambda scale=scale: marker.x() == pytest.approx((c.record("sensor")["deadlineDay"] + 1)*scale-1))
    original = c.project.tasks["sensor"].duration
    handle = item(window, "resize-end-sensor")
    start = point(handle)
    drag(window, start, start + QPoint(20, 0))
    wait_until(lambda: c.project.tasks["sensor"].duration > original)
    assert c.project.tasks["sensor"].deadline == date(2025, 12, 17)


@pytest.mark.parametrize("format_", ["csv", "xlsx", "pdf", "xml"])
def test_deadline_exports_as_date_or_native_xml_deadline(qapp, tmp_path, format_):
    c = Controller()
    assert c.editField("sensor", "deadline", "2025-12-19")
    source = ExportSource.capture(c)
    row = next(r for r in source.rows if r["taskId"] == "sensor")
    assert source.value(row, "deadline") == date(2025, 12, 19)
    assert source.text(row, "deadline") == "19.12.2025"
    before = c.project.to_dict()
    doc = ExportDocument(source, ExportOptions(format=format_, content="table", columns=("name", "deadline")))
    path = tmp_path / ("deadline." + format_)
    export_file(path, doc)
    if format_ == "csv":
        rows = list(csv.reader(path.read_text(encoding="utf-8-sig").splitlines()))
        assert rows[0] == ["Задача", "Крайний срок"]
        assert next(r for r in rows if r[0] == "Выбор сенсора")[1] == "2025-12-19"
    elif format_ == "xlsx":
        with ZipFile(path) as archive:
            sheet = generated_xml(archive.read("xl/worksheets/sheet1.xml"))
        cells = sheet.findall(f".//{{{SS}}}c")
        serial = str((date(2025, 12, 19)-date(1899, 12, 30)).days)
        assert any(cell.get("s") == "2" and cell.findtext(f"{{{SS}}}v") == serial for cell in cells)
    elif format_ == "xml":
        root = generated_xml(path.read_bytes())
        ns = {"p": MSP}
        tasks = root.findall("p:Tasks/p:Task", ns)
        sensor = next(t for t in tasks if t.findtext("p:Name", namespaces=ns) == "Выбор сенсора")
        assert sensor.findtext("p:Deadline", namespaces=ns) == "2025-12-19T23:59:59"
        assert sum(t.find("p:Deadline", ns) is not None for t in tasks) == 1
    else:
        pdf = pdf_document(path)
        assert "19.12.2025" in pdf.getAllText(0).text()
        pdf.close()
    assert c.project.to_dict() == before


def test_export_deadline_snapshot_marker_and_range_clipping(qapp):
    c = Controller()
    assert c.editField("sensor", "deadline", "2025-12-16")
    source = ExportSource.capture(c)
    doc = ExportDocument(source, ExportOptions(content="chart", pixels_per_day=26))
    row_index = next(i for i, r in enumerate(doc.rows) if r["taskId"] == "sensor")
    x = ((date(2025, 12, 16)-doc.start).days+1)*26
    y = doc.header + row_index*doc.row_height + 4
    image = doc.image()
    assert image.pixelColor(x, y) == QColor("#b93d30")
    assert c.editField("sensor", "deadline", "9999-12-31")
    assert source.project.tasks["sensor"].deadline == date(2025, 12, 16)
    clipped = ExportDocument(ExportSource.capture(c), ExportOptions(content="chart"))
    assert not clipped.image().isNull()
