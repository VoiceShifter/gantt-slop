from hashlib import sha256

import pytest
from conftest import wait_until
from dialog_helpers import click_native, native_dialog
from PySide6.QtCore import QMetaObject, QObject, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QFileDialog
from test_dependency_editing import _open_first_arrow
from test_export_ui import choose, open_export
from test_ganttpro_xlsx import FIXTURE, RETURN, cells, export_table

from gantt_desktop.ganttpro_csv import read_project_csv
from gantt_desktop.ganttpro_xlsx import read_project_xlsx
from gantt_desktop.xml_dialog import XmlImportDialog


@pytest.mark.parametrize("dark", [False, True])
def test_real_excel_menu_opens_native_review_without_mutating_project(gui, monkeypatch, dark):
    c, window = gui
    assert c.theme is not None
    c.theme.setDark(dark)
    before = c.project.to_dict()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(RETURN), ""))
    action = window.findChild(QObject, "importXlsxMenuItem")
    assert action is not None and QMetaObject.invokeMethod(action, "triggered")
    dialog = native_dialog("xlsxImportDialog")
    assert isinstance(dialog, XmlImportDialog)
    wait_until(dialog.isVisible)
    assert "20 элементов" in dialog.summary.text() and "0 связей" in dialog.summary.text()
    assert "212 ч" in dialog.summary.text() and "38000" in dialog.summary.text()
    assert dialog.table.columnCount() == 7 and dialog.table.topLevelItemCount() == 4
    assert dialog.windowHandle().transientParent() is window
    assert c.project.to_dict() == before and not c.dirty
    assert click_native("xlsxImportCancel")
    wait_until(lambda: not c.dialogs.property("modalOpen"))
    assert c.project.to_dict() == before and not c.canUndo


def test_excel_review_accept_arrow_edit_history_save_reopen_and_source_preservation(gui, tmp_path):
    c, window = gui
    source = tmp_path/"source.xlsx"
    export_table(read_project_csv(FIXTURE).project, source)
    digest = sha256(source.read_bytes()).hexdigest()
    assert c.preview_xlsx(source) and click_native("xlsxImportSave")
    wait_until(lambda: len(c.links) == 14)
    assert c.dirty and not c.canUndo and c._path is None
    before = c.project.to_dict()
    dialog = _open_first_arrow(c, window)
    assert dialog.isVisible() and c.dialogs.activeLinkId
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    wait_until(lambda: not c.dialogs.property("modalOpen"))
    assert c.editField("csv-task-1.2", "name", "Changed") and c.canUndo
    c.undo()
    assert c.project.to_dict() == before
    native = tmp_path/"plan.gantt.json"
    assert c.save_path(native) and c.load_path(native)
    assert c.project.to_dict() == before and not c.dirty and not c.canUndo
    assert sha256(source.read_bytes()).hexdigest() == digest


def test_excel_dirty_cancel_malformed_and_window_lifecycle(gui, monkeypatch, tmp_path):
    c, window = gui
    assert c.editField("sensor", "name", "Dirty")
    before = c.project.to_dict()
    assert c.preview_xlsx(RETURN)
    monkeypatch.setattr(c, "confirm_discard", lambda: False)
    assert click_native("xlsxImportSave")
    dialog = native_dialog("xlsxImportDialog")
    assert dialog.isVisible() and c.project.to_dict() == before and c.canUndo
    window.hide()
    wait_until(lambda: not dialog.isVisible())
    assert not c.dialogs.property("modalOpen")
    errors = QSignalSpy(c.toast)
    invalid = tmp_path/"bad.xlsx"
    invalid.write_bytes(b'bad zip')
    for path in (invalid, tmp_path/"missing.xlsx"):
        assert not c.preview_xlsx(path)
    assert errors.count() == 2 and c.project.to_dict() == before


def test_excel_export_mode_preview_headerless_and_extension_use_real_controls(gui, monkeypatch, tmp_path):
    c, window = gui
    c.load_project(read_project_csv(FIXTURE).project)
    before = c.project.to_dict()
    dialog = open_export(window)
    choose(dialog.format, "ganttpro_xlsx")
    dialog.update_preview()
    assert dialog.document is not None and len(dialog.document.columns) == 23
    assert not dialog.scope.isEnabled() and not dialog.fields.isEnabled()
    assert dialog.site_import.isVisible() and not dialog.table_headers.isEnabled()
    assert "стрелки не восстановились" in dialog.transfer_warning.text()
    assert dialog.transfer_warning.geometry().bottom() <= dialog.height()
    assert dialog.export_to(tmp_path/"reviewed.xlsx")
    assert cells(read_project_xlsx(tmp_path/"reviewed.xlsx").project) == cells(c.project)
    assert click_native("exportSiteImport")
    dialog.update_preview()
    assert dialog.document is not None and len(dialog.document.columns) == 25 and dialog.table_headers.isEnabled()
    assert click_native("exportTableHeaders")
    dialog.update_preview()
    assert dialog.document is not None and not dialog.document.options.table_headers and "без заголовков" in dialog.info.text()
    requests = []
    def destination(*args):
        requests.append(args)
        return str(tmp_path/"site.xlsx"), ""
    monkeypatch.setattr(QFileDialog, "getSaveFileName", destination)
    assert click_native("saveExport")
    assert (tmp_path/"site.xlsx").exists() and requests[0][2].endswith('.xlsx')
    assert c.project.to_dict() == before and not c.dirty
