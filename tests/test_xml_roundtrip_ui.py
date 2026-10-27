import json
from pathlib import Path

import pytest
from conftest import wait_until
from dialog_helpers import click_native, native_dialog
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from test_dependency_editing import _open_first_arrow
from test_export_ui import choose, open_export
from test_xml_import import DAY

from gantt_desktop.domain import CustomField
from gantt_desktop.ganttpro_csv import read_project_csv
from gantt_desktop.xml_dialog import XmlImportDialog
from gantt_desktop.xml_import import read_project_xml

FIXTURE = Path(__file__).parent / "fixtures" / "ganttpro-task-table.csv"


@pytest.mark.parametrize("dark", [False, True])
def test_native_xml_export_and_review_restore_the_editable_full_diagram(gui, tmp_path, dark):
    c, window = gui
    assert c.theme is not None
    c.theme.setDark(dark)
    project = read_project_csv(FIXTURE).project
    project.tasks["csv-task-1.2"].set_status("closed")
    c.load_project(project)
    before = c.project.to_dict()
    c.search("сенсора")
    dialog = open_export(window)
    choose(dialog.format, "xml")
    dialog.update_preview()
    assert dialog.document is not None and len(dialog.document.rows) == 20
    assert not dialog.scope.isEnabled() and not dialog.fields.isEnabled() and not dialog.range.isEnabled()
    assert dialog.transfer_warning.isVisible() and dialog.transfer_warning.parentWidget() is dialog
    assert "типизированные" in dialog.transfer_warning.text() and "GanttPRO не принимает XML" in dialog.transfer_warning.text()
    assert dialog.transfer_warning.geometry().bottom() <= dialog.height()
    path = tmp_path / "native.xml"
    assert dialog.export_to(path) and c.project.to_dict() == before
    dialog.reject()
    assert c.preview_xml(path)
    review = native_dialog("xmlImportDialog")
    assert isinstance(review, XmlImportDialog)
    assert "212 ч" in review.summary.text() and "38000" in review.summary.text()
    assert click_native("xmlImportSave")
    wait_until(lambda: len(c.links) == 14)
    assert len(c.project.custom_fields) == 4 and len(c.project.resources) == 3
    sensor = next(task for task in c.project.tasks.values() if task.name == "Выбор сенсора")
    assert sensor.status == "closed" and sensor.color == "#50c7d6" and sensor.effort == 8
    assert c.dirty and not c.canUndo and c._path is None
    link_editor = _open_first_arrow(c, window)
    QTest.keyClick(link_editor, Qt.Key.Key_Escape)
    wait_until(lambda: not c.dialogs.property("modalOpen"))
    imported = c.project.to_dict()
    assert c.editField(sensor.id, "name", "Edited imported XML")
    c.undo()
    assert c.project.to_dict() == imported
    native = tmp_path / "imported.gantt.json"
    assert c.save_path(native)
    assert json.loads(native.read_text())["version"] == 9
    assert c.load_path(native) and c.project.to_dict() == imported


def test_xml_field_limit_is_an_inline_preview_error_not_a_partial_file_write(gui, tmp_path):
    c, window = gui
    for index in range(27):
        key = str(index)
        c.project.custom_fields[key] = CustomField(key, "Text "+key)
    c.refresh()
    before = c.project.to_dict()
    dialog = open_export(window)
    choose(dialog.format, "xml")
    dialog.update_preview()
    assert dialog.document is None and not dialog.save_button.isEnabled()
    assert dialog.error.isVisible() and "лимит XML-полей" in dialog.error.text()
    path = tmp_path / "existing.xml"
    path.write_bytes(b"original")
    assert not dialog.export_to(path) and path.read_bytes() == b"original"
    assert c.project.to_dict() == before
    dialog.reject()


def test_xml_roundtrip_source_metadata_error_keeps_the_original_destination(gui, tmp_path):
    c, window = gui
    c.load_project(read_project_csv(FIXTURE).project)
    c.project.tasks["csv-task-1.2"].custom_values["ganttpro_actual_cost"] = "not a number"
    c.refresh()
    before = c.project.to_dict()
    dialog = open_export(window)
    choose(dialog.format, "xml")
    dialog.update_preview()
    path = tmp_path / "existing.xml"
    path.write_bytes(b"original")
    assert not dialog.export_to(path) and path.read_bytes() == b"original"
    assert c.project.to_dict() == before and dialog.error.isVisible()
    dialog.reject()
    # The invalid source metadata did not leak into any output project.
    assert not list(tmp_path.glob(".gantt-export-*"))
    with pytest.raises(ValueError):
        read_project_xml(path, DAY)
