"""Regression coverage for the five 0.19 audit findings."""
import json
import tempfile
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from gantt_desktop.controller import Controller
from gantt_desktop.domain import (
    Project,
    Resource,
    ScheduleError,
    Task,
    TaskFilter,
    WorkCalendar,
)

START = datetime.fromisoformat("2025-12-01T09:00")


def project():
    return Project("Audit", {"a": Task("a", "Original", START, 960)})


@pytest.fixture
def editor(qapp):
    c = Controller(project())
    yield c
    c.dialogs.dispose()


def state(c):
    return deepcopy({
        "project": c.project.to_dict(), "history": c._history,
        "history_index": c._history_index, "clean_index": c._clean_index, "path": c._path,
        "rows": c._rows.records, "origin": c._origin, "day_count": c._day_count,
        "selected": c.selectedId, "bulk": c.bulkMode, "checked": c._checked, "collapsed": c._collapsed,
        "filter": c.filter_state(), "critical": c._critical, "critical_error": c._critical_error,
        "baseline_range": (c._baseline_range_id, c._baseline_range_warning),
    })


def prepare_history_and_view(c, tmp_path):
    assert c.save_path(tmp_path / "original.gantt.json")
    assert c.editField("a", "name", "First")
    assert c.editField("a", "name", "Second")
    c.undo()
    c.select("a")
    c.setBulkMode(True)
    c.toggleChecked("a")
    c.setCriticalPath(True)
    assert c.dirty and c.canRedo


def test_overflow_edit_preserves_history_view_and_revision_signals(editor, tmp_path):
    c = editor
    prepare_history_and_view(c, tmp_path)
    before = state(c)
    history_events = []
    c.historyChanged.connect(lambda: history_events.append(True))
    assert not c.editField("a", "start", "9999-12-31")
    assert state(c) == before and not history_events
    assert c.project.span("a") == (START, datetime.fromisoformat("2025-12-02T18:00"))
    assert c.editField("a", "name", "Recovered")
    c.undo()
    assert c.project.to_dict() == before["project"]


@pytest.mark.parametrize("field", ["startTime", "endTime"])
@pytest.mark.parametrize("value", ["09:00:30", "09:00:00.5", "08:00:30", "18:00:30", "09:00+03:00"])
def test_subminute_edits_are_rejected_before_normalization(editor, field, value):
    before = state(editor)
    assert not editor.editField("a", field, value)
    assert state(editor) == before


@pytest.mark.parametrize("kind,minutes", [("task", 480), ("group", 0), ("milestone", 0)])
@pytest.mark.parametrize("start", ["2025-12-01T09:00:30", "2025-12-01T09:00:00.5"])
def test_domain_and_native_load_reject_subminute_starts(kind, minutes, start):
    p = Project("Audit", {"a": Task("a", "Original", datetime.fromisoformat(start), minutes, kind=kind)})
    with pytest.raises(ScheduleError, match="минут"):
        p.validate()
    payload = p.to_dict()
    payload["tasks"][0]["start"] = start
    with pytest.raises(ScheduleError, match="минут"):
        Project.from_dict(payload)


@pytest.mark.parametrize("day", ["0001-01-01", "9999-12-31"])
def test_valid_calendar_boundaries_remain_renderable(qapp, day):
    start = datetime.fromisoformat(day + "T09:00")
    end = datetime.fromisoformat(day + "T18:00")
    p = Project("Boundary", {"g": Task("g", "Group", start, 0, kind="group"),
                             "a": Task("a", "Task", start, 480, parent="g")})
    p.validate()
    assert WorkCalendar().between(start, end) == 480
    c = Controller(p)
    assert c.project.span("g") == (start, end) and c.record("g")["duration"] == 8
    c.dialogs.dispose()


@pytest.mark.parametrize("operation", ["edit", "load"])
@pytest.mark.parametrize("stage", ["record", "_selection_scope"])
def test_view_preparation_failure_restores_document_and_view(editor, tmp_path, monkeypatch, operation, stage):
    c = editor
    prepare_history_and_view(c, tmp_path)
    before = state(c)
    original = getattr(c, stage)
    events = []
    c.historyChanged.connect(lambda: events.append("history"))
    c.fileChanged.connect(lambda: events.append("file"))
    c.projectLoaded.connect(lambda: events.append("load"))

    def fail_candidate(*args):
        if c.project.name == "Rejected":
            raise OverflowError("simulated derived-view failure")
        return original(*args)

    monkeypatch.setattr(c, stage, fail_candidate)
    if operation == "edit":
        def update(draft):
            draft.name = "Rejected"
            draft.tasks["a"].start = datetime.fromisoformat("2024-01-01T09:00")
        assert not c.edit("Rejected edit", update)
    else:
        payload = project().to_dict()
        payload["name"] = "Rejected"
        path = tmp_path / "rejected.gantt.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        assert not c.load_path(path)
    assert state(c) == before and not events


@pytest.mark.parametrize("start", ["9999-12-31T09:00", "2025-12-01T09:00:30", "2025-12-01T09:00:00.5"])
def test_invalid_native_schedule_preserves_open_document(editor, tmp_path, start):
    c = editor
    prepare_history_and_view(c, tmp_path)
    c.search("First")
    before = state(c)
    payload = project().to_dict()
    payload["tasks"][0]["start"] = start
    path = tmp_path / "bad.gantt.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert not c.load_path(path)
    assert state(c) == before


@pytest.mark.parametrize("location", [("name",), ("tasks", 0, "name"), ("tasks", 0, "notes"),
                                      ("resources", 0, "name"), ("saved_filters", "Keep", "query"),
                                      ("baselines", 0, "tasks", 0, "name")])
@pytest.mark.parametrize("codepoint", [0xD800, 0xDFFF])
def test_native_validation_rejects_unpaired_surrogates(editor, tmp_path, location, codepoint):
    text = chr(codepoint)
    p = project()
    p.resources["r"] = Resource("r", "Person")
    p.saved_filters["Keep"] = TaskFilter(query="Original")
    p.capture_baseline("Initial", date.fromisoformat("2025-12-01"))
    payload = p.to_dict()
    target = payload
    for key in location[:-1]:
        target = target[key]
    target[location[-1]] = text
    path = tmp_path / "bad-text.gantt.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    before = state(editor)
    with pytest.raises((UnicodeError, ScheduleError)):
        Project.from_dict(payload)
    assert not editor.load_path(path)
    assert state(editor) == before


def test_text_edits_cannot_introduce_unsavable_unicode(editor):
    before = state(editor)
    assert not editor.editField("a", "notes", "\ud800")
    assert state(editor) == before


def test_valid_non_bmp_text_roundtrips_without_replacement(editor, tmp_path):
    text = "🛰️ План — 中文 😀"
    assert editor.editField("a", "notes", text)
    path = tmp_path / "unicode.gantt.json"
    assert editor.save_path(path)
    assert text in path.read_text(encoding="utf-8")
    payload = json.loads(path.read_text(encoding="utf-8"))
    # The JSON decoder also accepts correctly paired UTF-16 escapes.
    path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
    assert editor.load_path(path) and editor.project.tasks["a"].notes == text
    assert not editor.dirty


def test_save_does_not_overwrite_a_temporary_sibling(editor, tmp_path):
    path = tmp_path / "project.gantt.json"
    sibling = path.with_name(path.name + ".tmp")
    sibling.write_bytes(b"UNRELATED SENTINEL")
    assert editor.save_path(path)
    assert sibling.read_bytes() == b"UNRELATED SENTINEL"
    assert set(tmp_path.iterdir()) == {path, sibling}
    assert json.loads(path.read_text(encoding="utf-8")) == editor.project.to_dict()


@pytest.mark.parametrize("failure", ["create", "write", "replace", "encode"])
@pytest.mark.parametrize("existing", [False, True])
def test_failed_save_preserves_files_dirty_state_and_cleans_temporary(editor, tmp_path, monkeypatch, failure, existing):
    c = editor
    original = tmp_path / "original.gantt.json"
    assert c.save_path(original)
    assert c.editField("a", "name", "Unsaved")
    destination = tmp_path / "other.gantt.json"
    if existing:
        destination.write_bytes(b"KEEP EXISTING DESTINATION")
    before_files = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    before = state(c)
    messages = []
    c.toast.connect(messages.append)

    def denied(*_args, **_kwargs):
        raise OSError("simulated filesystem failure")

    if failure == "create":
        monkeypatch.setattr(tempfile, "NamedTemporaryFile", denied)
    elif failure == "write":
        create = tempfile.NamedTemporaryFile

        def partial_file(*args, **kwargs):
            stream = create(*args, **kwargs)
            write = stream.write

            def partial_write(text):
                write(text[:8])
                stream.flush()
                raise OSError("simulated partial write")

            monkeypatch.setattr(stream, "write", partial_write)
            return stream

        monkeypatch.setattr(tempfile, "NamedTemporaryFile", partial_file)
    elif failure == "replace":
        monkeypatch.setattr(Path, "replace", denied)
    else:
        # Defensive save handling even if a caller bypasses normal validation.
        c.project.tasks["a"].notes = "\ud800"
        before = state(c)
    assert not c.save_path(destination)
    assert state(c) == before
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before_files
    assert messages and messages[-1].startswith("Не удалось сохранить проект:")


def test_save_failure_does_not_allow_discard_or_close(editor, tmp_path, monkeypatch):
    c = editor
    assert c.save_path(tmp_path / "project.gantt.json")
    assert c.editField("a", "name", "Unsaved")
    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_kw: QMessageBox.StandardButton.Save)

    def denied(*_args, **_kwargs):
        raise PermissionError("Cannot replace")

    monkeypatch.setattr(Path, "replace", denied)
    assert not c.confirmClose() and c.dirty


def test_direct_load_does_not_truncate_invalid_time(editor):
    candidate = project()
    candidate.tasks["a"].start = START.replace(second=30)
    before = state(editor)
    with pytest.raises(ScheduleError, match="минут"):
        editor.load_project(candidate)
    assert state(editor) == before


@pytest.mark.parametrize("operation,target", [("undo", "Original"), ("redo", "Second")])
def test_failed_history_view_does_not_move_history_index(editor, tmp_path, monkeypatch, operation, target):
    c = editor
    prepare_history_and_view(c, tmp_path)
    before = state(c)
    record = c.record

    def fail_candidate(task_id):
        if c.project.tasks["a"].name == target:
            raise OverflowError("simulated view failure")
        return record(task_id)

    monkeypatch.setattr(c, "record", fail_candidate)
    with pytest.raises(OverflowError):
        getattr(c, operation)()
    assert state(c) == before
