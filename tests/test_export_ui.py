import pytest
from conftest import wait_until
from dialog_helpers import native_dialog
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QScrollArea, QWidget
from test_ui import item, point

from gantt_desktop.domain import Project
from gantt_desktop.export_dialog import ExportDialog
from gantt_desktop.sample import sample_project


def open_export(window):
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(item(window, "exportButton")))
    dialog = native_dialog("exportDialog")
    assert isinstance(dialog, ExportDialog)
    wait_until(dialog.isVisible)
    wait_until(lambda: dialog.document is not None)
    return dialog


def choose(combo, value):
    combo.setCurrentIndex(combo.findData(value))


@pytest.mark.parametrize("dark", [False, True])
def test_native_export_has_real_preview_and_does_not_change_workspace_or_history(gui, qapp, dark):
    c, window = gui
    assert c.theme is not None
    c.theme.setDark(dark)
    c.toggleGroup("planning")
    before = c.project.to_dict()
    dialog = open_export(window)
    assert dialog.document is not None
    assert len(dialog.document.rows) == len(c.project.tasks)
    assert len(dialog.preview.scene_.items()) == 1
    assert dialog.style() is qapp.style()
    assert dialog.palette().color(QPalette.ColorRole.Window) == qapp.palette().color(QPalette.ColorRole.Window)
    for widget in [dialog, *dialog.findChildren(QWidget)]:
        assert not widget.styleSheet()
    settings = dialog.findChild(QScrollArea)
    assert settings is not None
    wait_until(lambda: settings.horizontalScrollBar().maximum() == 0)
    assert dialog.windowHandle().transientParent() is window
    assert c.dialogs.property("modalOpen")
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    wait_until(lambda: not c.dialogs.property("modalOpen"))
    assert "planning" in c._collapsed
    assert c.project.to_dict() == before and not c.canUndo and not c.dirty


@pytest.mark.parametrize("format_", ["pdf", "png", "xlsx", "xml", "csv"])
def test_native_configuration_exports_all_formats_to_chosen_local_path(gui, tmp_path, format_):
    c, window = gui
    before = c.project.to_dict()
    dialog = open_export(window)
    choose(dialog.format, format_)
    dialog.update_preview()
    path = tmp_path / ("native." + format_)
    assert dialog.export_to(path)
    assert path.stat().st_size > 100
    if format_ == "png":
        image = QImage(str(path))
        assert image.pixelColor(0, 0).name() == "#ffffff"
    assert c.project.to_dict() == before and not c.canUndo and not c.dirty
    dialog.reject()


def test_preview_options_fields_and_visible_filter_are_independent_of_workspace(gui):
    c, window = gui
    c.search("сенсора")
    before = c.project.to_dict()
    dialog = open_export(window)
    assert dialog.document is not None and len(dialog.document.rows) == len(c.project.tasks)
    choose(dialog.scope, "visible")
    item_ = next(dialog.fields.item(i) for i in range(dialog.fields.count())
                 if dialog.fields.item(i).data(Qt.ItemDataRole.UserRole) == "start")
    dialog.fields.setCurrentItem(item_)
    dialog.fields.setFocus()
    QTest.keyClick(dialog.fields, Qt.Key.Key_Space)
    choose(dialog.paper, "A4")
    choose(dialog.orientation, False)
    choose(dialog.labels, "right")
    dialog.workload.setChecked(True)
    dialog.update_preview()
    assert dialog.document is not None and dialog.source is not None
    assert len(dialog.document.rows) == len(dialog.source.visible_ids)
    assert "start" in dialog.document.options.columns
    assert dialog.document.options.labels == "right"
    assert dialog.document.resources
    assert dialog.orientation.isEnabled()
    assert not item(window, "ganttView").property("showStart")
    assert c._query == "сенсора" and c.project.to_dict() == before
    dialog.reject()


def test_invalid_range_disables_export_and_preserves_destination_and_draft(gui, tmp_path):
    c, window = gui
    before = c.project.to_dict()
    dialog = open_export(window)
    dialog.range.setChecked(True)
    dialog.start.setDate(dialog.end.date().addDays(10))
    dialog.update_preview()
    assert dialog.document is None and not dialog.save_button.isEnabled()
    assert dialog.error.isVisible() and "Начало" in dialog.error.text()
    assert not dialog.preview.scene_.items()
    path = tmp_path / "unchanged.pdf"
    path.write_bytes(b"original")
    assert not dialog.export_to(path)
    assert path.read_bytes() == b"original"
    assert c.project.to_dict() == before and not c.dirty
    dialog.reject()


def test_xml_is_whole_project_and_table_formats_do_not_offer_fake_graph_options(gui):
    c, window = gui
    c.search("сенсора")
    dialog = open_export(window)
    choose(dialog.scope, "visible")
    choose(dialog.format, "xml")
    dialog.update_preview()
    assert dialog.document is not None
    assert dialog.scope.currentData() == "all" and not dialog.scope.isEnabled()
    assert dialog.document.options.scope == "all"
    assert len(dialog.document.rows) == len(c.project.tasks)
    assert dialog.content.currentData() == "table" and not dialog.content.isEnabled()
    assert not dialog.fields.isEnabled() and not dialog.paper.isEnabled()
    choose(dialog.format, "xlsx")
    dialog.update_preview()
    assert dialog.fields.isEnabled() and dialog.workload.isEnabled()
    assert not dialog.scale.isEnabled() and not dialog.orientation.isEnabled()
    dialog.reject()


def test_save_dialog_cancel_wrong_extension_and_file_error_do_not_dirty_project(gui, tmp_path, monkeypatch):
    c, window = gui
    before = c.project.to_dict()
    dialog = open_export(window)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: ("", ""))
    dialog.apply()
    assert dialog.isVisible() and not list(tmp_path.iterdir())
    wrong = tmp_path / "wrong.png"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(wrong), ""))
    dialog.apply()
    assert dialog.error.isVisible() and not wrong.exists()
    assert not dialog.export_to(tmp_path / "missing" / "file.pdf")
    assert dialog.error.isVisible()
    assert c.project.to_dict() == before and not c.canUndo
    dialog.reject()


def test_confirmed_export_closes_modal_without_saving_the_project(gui, tmp_path, monkeypatch):
    c, window = gui
    assert c.editField("sensor", "name", "Exported task")
    before = c.project.to_dict()
    index = c._history_index
    dialog = open_export(window)
    path = tmp_path / "confirmed.pdf"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(path), ""))
    dialog.apply()
    wait_until(lambda: not c.dialogs.property("modalOpen"))
    assert path.read_bytes().startswith(b"%PDF")
    assert c.project.to_dict() == before and c._history_index == index and c.dirty


def test_project_load_and_main_window_close_dispose_export_previews(gui):
    c, window = gui
    dialog = open_export(window)
    dialog.timer.start()
    c.load_project(sample_project())
    assert not dialog.isVisible() and not c.dialogs.property("modalOpen")
    dialog = open_export(window)
    window.close()
    wait_until(lambda: not c.dialogs.property("modalOpen"))
    assert not dialog.isVisible()


def test_empty_project_reports_no_tasks_without_an_old_preview_or_output(gui, tmp_path):
    c, window = gui
    dialog = open_export(window)
    dialog.reject()
    c.load_project(Project())
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(item(window, "exportButton")))
    dialog = native_dialog("exportDialog")
    assert isinstance(dialog, ExportDialog)
    wait_until(dialog.isVisible)
    assert dialog.document is None and dialog.error.isVisible()
    assert "Нет задач" in dialog.error.text()
    assert not dialog.save_button.isEnabled() and not dialog.preview.scene_.items()
    assert not dialog.export_to(tmp_path / "empty.pdf")
    assert not (tmp_path / "empty.pdf").exists()
    dialog.reject()


def test_legacy_png_entry_now_opens_full_diagram_export_not_window_capture(gui):
    c, _window = gui
    before = c.project.to_dict()
    c.exportPng()
    dialog = native_dialog("exportDialog")
    assert isinstance(dialog, ExportDialog)
    wait_until(dialog.isVisible)
    assert dialog.format.currentData() == "png" and dialog.document is not None
    assert c.project.to_dict() == before and not c.canUndo
    dialog.reject()
