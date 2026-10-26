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

from gantt_desktop.domain import Project
from gantt_desktop.xml_dialog import XmlImportDialog

FIXTURE = Path(__file__).parent / "fixtures" / "ganttpro-device-plan.xml"


@pytest.mark.parametrize("dark", [False, True])
def test_real_file_menu_previews_actual_xml_without_changing_current_project(gui, qapp, monkeypatch, dark):
    c, window = gui
    assert c.theme is not None
    c.theme.setDark(dark)
    before = c.project.to_dict()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(FIXTURE), ""))
    action = window.findChild(QObject, "importXmlMenuItem")
    assert action is not None
    assert QMetaObject.invokeMethod(action, "triggered")
    dialog = native_dialog("xmlImportDialog")
    assert isinstance(dialog, XmlImportDialog)
    wait_until(dialog.isVisible)
    assert "20 элементов" in dialog.summary.text() and "14 связей" in dialog.summary.text()
    assert "буквально" in dialog.warnings.toPlainText() and "не содержит ресурсов" in dialog.warnings.toPlainText()
    assert dialog.table.topLevelItemCount() > 1
    assert dialog.windowHandle().transientParent() is window
    assert dialog.palette().color(QPalette.ColorRole.Window) == qapp.palette().color(QPalette.ColorRole.Window)
    assert all(not widget.styleSheet() for widget in [dialog, *dialog.findChildren(QWidget)])
    assert c.dialogs.property("modalOpen") and c.project.to_dict() == before and not c.dirty
    assert click_native("xmlImportCancel")
    wait_until(lambda: not c.dialogs.property("modalOpen"))
    assert c.project.to_dict() == before and not c.canUndo


def test_accept_creates_dirty_new_project_without_overwriting_xml_then_saves_native(gui, tmp_path):
    c, window = gui
    digest = sha256(FIXTURE.read_bytes()).hexdigest()
    assert c.preview_xml(FIXTURE)
    assert replace_native("xmlImportName", "Imported diagram")
    assert click_native("xmlImportSave")
    wait_until(lambda: len(c.project.tasks) == 20)
    assert c.project.name == "Imported diagram" and c.dirty and not c.canUndo and c._path is None
    assert not c.dialogs.property("modalOpen")
    native = tmp_path / "imported.gantt.json"
    assert c.save_path(native) and not c.dirty
    expected = c.project.to_dict()
    assert Project.from_dict(json.loads(native.read_text())).to_dict() == expected
    assert c.load_path(native) and c.project.to_dict() == expected and not c.canUndo
    assert sha256(FIXTURE.read_bytes()).hexdigest() == digest
    assert window.isVisible()


def test_declining_discard_keeps_dirty_project_and_import_draft_open(gui, monkeypatch):
    c, _window = gui
    assert c.editField("sensor", "name", "Uncommitted current work")
    before = c.project.to_dict()
    assert c.preview_xml(FIXTURE)
    monkeypatch.setattr(c, "confirm_discard", lambda: False)
    assert click_native("xmlImportSave")
    dialog = native_dialog("xmlImportDialog")
    assert dialog.isVisible() and c.project.to_dict() == before and c.canUndo and c.dirty
    assert click_native("xmlImportCancel")
    assert c.project.to_dict() == before


def test_malformed_or_unsafe_xml_never_changes_or_replaces_current_project(gui, tmp_path):
    c, _window = gui
    before = c.project.to_dict()
    spy = QSignalSpy(c.toast)
    for data in (b'<Project>', b'<!DOCTYPE Project SYSTEM "file:///etc/passwd"><Project/>'):
        path = tmp_path / "unsafe.xml"
        path.write_bytes(data)
        assert not c.preview_xml(path)
        assert c.project.to_dict() == before and not c.dirty and not c.dialogs.property("modalOpen")
    assert spy.count() == 2


def test_import_review_closes_with_window_and_escape_is_noop(gui):
    c, window = gui
    before = c.project.to_dict()
    assert c.preview_xml(FIXTURE)
    dialog = native_dialog("xmlImportDialog")
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    wait_until(lambda: not c.dialogs.property("modalOpen"))
    assert c.project.to_dict() == before
    assert c.preview_xml(FIXTURE)
    window.hide()
    wait_until(lambda: not dialog.isVisible())
    assert not c.dialogs.property("modalOpen") and c.project.to_dict() == before
