import json
from hashlib import sha256
from pathlib import Path

import pytest
from conftest import wait_until
from dialog_helpers import click_native, native_dialog, replace_native
from PySide6.QtCore import QMetaObject, QObject, Qt
from PySide6.QtGui import QPalette
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QFileDialog, QWidget
from test_dependency_editing import _open_first_arrow

from gantt_desktop.xml_dialog import XmlImportDialog

FIXTURE = Path(__file__).parent / "fixtures" / "ganttpro-task-table.csv"


@pytest.mark.parametrize("dark", [False, True])
def test_real_csv_file_menu_opens_transactional_native_review(gui, qapp, monkeypatch, dark):
    c, window = gui
    assert c.theme is not None
    c.theme.setDark(dark)
    before = c.project.to_dict()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(FIXTURE), ""))
    action = window.findChild(QObject, "importCsvMenuItem")
    assert action is not None and QMetaObject.invokeMethod(action, "triggered")
    dialog = native_dialog("csvImportDialog")
    assert isinstance(dialog, XmlImportDialog)
    wait_until(dialog.isVisible)
    assert "20 элементов" in dialog.summary.text() and "14 связей" in dialog.summary.text() and "3 ресурсов" in dialog.summary.text()
    assert "создание и автор" in dialog.warnings.toPlainText()
    assert dialog.table.topLevelItemCount() == 4
    assert dialog.windowHandle().transientParent() is window
    assert dialog.palette().color(QPalette.ColorRole.Window) == qapp.palette().color(QPalette.ColorRole.Window)
    assert all(not widget.styleSheet() for widget in [dialog, *dialog.findChildren(QWidget)])
    assert c.dialogs.property("modalOpen") and c.project.to_dict() == before
    assert click_native("csvImportCancel")
    wait_until(lambda: not c.dialogs.property("modalOpen"))
    assert not c.dirty and not c.canUndo and c.project.to_dict() == before


def test_accept_creates_editable_diagram_with_arrows_metadata_history_and_safe_native_save(gui, tmp_path):
    c, window = gui
    digest = sha256(FIXTURE.read_bytes()).hexdigest()
    assert c.preview_csv(FIXTURE)
    assert replace_native("csvImportName", "Imported CSV")
    assert click_native("csvImportSave")
    wait_until(lambda: len(c.project.tasks) == 20)
    assert c.project.name == "Imported CSV" and c.dirty and not c.canUndo and c._path is None
    assert len(c.project.dependencies) == 14 and len(c.project.resources) == 3 and len(c.project.custom_fields) == 4
    assert c.record("csv-task-1.2")["effortHours"] == 8
    assert c.record("csv-task-1.2")["start"] == "11.12.2025" and c.record("csv-task-1.2")["end"] == "15.12.2025"
    assert c.record("csv-task-2.3")["color"] == "#d860bb"
    before = c.project.to_dict()
    assert c.editField("csv-task-1.2", "name", "Edited sensor") and c.canUndo
    c.undo()
    assert c.project.to_dict() == before
    c.redo()
    assert c.project.tasks["csv-task-1.2"].name == "Edited sensor"
    native = tmp_path / "imported.gantt.json"
    assert c.save_path(native) and not c.dirty
    expected = c.project.to_dict()
    assert json.loads(native.read_text())["version"] == 9
    assert c.load_path(native) and c.project.to_dict() == expected and not c.canUndo
    assert sha256(FIXTURE.read_bytes()).hexdigest() == digest and window.isVisible()


def test_imported_csv_arrow_is_rendered_and_opens_real_dependency_editor(gui):
    c, window = gui
    assert c.preview_csv(FIXTURE) and click_native("csvImportSave")
    wait_until(lambda: len(c.links) == 14)
    before = c.project.to_dict()
    dialog = _open_first_arrow(c, window)
    assert dialog.isVisible() and c.dialogs.activeLinkId == c.project.dependencies[0].id
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    wait_until(lambda: not c.dialogs.property("modalOpen"))
    assert c.project.to_dict() == before and not c.canUndo


def test_csv_review_does_not_discard_dirty_work_without_existing_confirmation(gui, monkeypatch):
    c, _window = gui
    assert c.editField("sensor", "name", "Uncommitted")
    before = c.project.to_dict()
    assert c.preview_csv(FIXTURE)
    monkeypatch.setattr(c, "confirm_discard", lambda: False)
    assert click_native("csvImportSave")
    dialog = native_dialog("csvImportDialog")
    assert dialog.isVisible() and c.project.to_dict() == before and c.dirty and c.canUndo
    assert click_native("csvImportCancel") and c.project.to_dict() == before


def test_invalid_csv_and_missing_file_report_errors_before_replacing_project(gui, tmp_path):
    c, _window = gui
    before = c.project.to_dict()
    errors = QSignalSpy(c.toast)
    malformed = tmp_path / "bad.csv"
    malformed.write_text('wrong,headers\n1,2\n', encoding="utf-8")
    for path in (malformed, tmp_path / "missing.csv"):
        assert not c.preview_csv(path)
        assert c.project.to_dict() == before and not c.dirty and not c.dialogs.property("modalOpen")
    assert errors.count() == 2


def test_csv_review_escape_and_window_lifecycle_leave_project_untouched(gui):
    c, window = gui
    before = c.project.to_dict()
    assert c.preview_csv(FIXTURE)
    dialog = native_dialog("csvImportDialog")
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    wait_until(lambda: not c.dialogs.property("modalOpen"))
    assert c.project.to_dict() == before
    assert c.preview_csv(FIXTURE)
    window.hide()
    wait_until(lambda: not dialog.isVisible())
    assert not c.dialogs.property("modalOpen") and c.project.to_dict() == before
