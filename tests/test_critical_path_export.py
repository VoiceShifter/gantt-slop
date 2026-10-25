from dataclasses import replace

import pytest
from conftest import wait_until
from dialog_helpers import click_native, native_dialog, required_widget
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QPushButton
from test_critical_path_ui import diamond

from gantt_desktop.controller import Controller
from gantt_desktop.exporting import (
    ExportDocument,
    ExportOptions,
    ExportSource,
    export_file,
)


def bar_pixel(document, key):
    row = next(i for i, value in enumerate(document.rows) if value["taskId"] == key)
    record = document.rows[row]
    x = int(document.left + (record["startValue"].date()-document.start).days*document.options.pixels_per_day+5)
    return document.image().pixelColor(x, document.header+row*document.row_height+6)


def test_export_critical_option_is_independent_and_preserves_original_colors(qapp):
    c = Controller(diamond())
    assert c.editField("a", "color", "#2255aa")
    c.setCriticalPath(True)
    before = c.project.to_dict()
    source = ExportSource.capture(c)
    options = ExportOptions(content="chart", pixels_per_day=52, labels="none", links=False)
    normal = ExportDocument(source, options)
    critical = ExportDocument(source, replace(options, critical=True))
    assert bar_pixel(normal, "a") == QColor("#2255aa")
    assert bar_pixel(critical, "a") == QColor("#c93b3b")
    assert bar_pixel(critical, "c") == QColor(c.project.tasks["c"].color)
    assert critical.analysis is not None and critical.analysis.total_float["c"] == 240
    assert c.project.to_dict() == before


def test_visible_scope_does_not_invent_a_filtered_critical_path(qapp):
    c = Controller(diamond())
    c.search("c")
    source = ExportSource.capture(c)
    document = ExportDocument(source, ExportOptions(scope="visible", content="chart", critical=True,
                                                   pixels_per_day=52, labels="none", links=False))
    assert [row["taskId"] for row in document.rows] == ["c"]
    assert document.analysis is not None and document.analysis.total_float["c"] == 240
    assert bar_pixel(document, "c") == QColor(c.project.tasks["c"].color)


@pytest.mark.parametrize("format_", ["png", "pdf"])
def test_critical_output_uses_a_frozen_project_and_does_not_modify_history(qapp, tmp_path, format_):
    c = Controller(diamond())
    source = ExportSource.capture(c)
    document = ExportDocument(source, ExportOptions(format=format_, critical=True, paper="A4"))
    before = c.project.to_dict()
    path = tmp_path / ("critical."+format_)
    export_file(path, document)
    assert path.stat().st_size > 100 and c.project.to_dict() == before and not c.canUndo
    assert c.resizeTask("c", "end", 1)
    assert document.analysis is not None and document.analysis.total_float["c"] == 240


def test_export_budget_error_disables_save_and_can_be_cleared_without_project_changes(gui, monkeypatch):
    c, _window = gui
    c.load_project(diamond())
    before = c.project.to_dict()
    monkeypatch.setattr("gantt_desktop.critical_path._WORK_LIMIT", 1)
    c.dialogs.showExport({"critical": True})
    dialog = native_dialog("exportDialog")
    error = dialog.findChild(QLabel, "dialogError")
    button = required_widget("saveExport")
    assert isinstance(button, QPushButton)
    assert error is not None and error.isVisible() and "альтернатив" in error.text()
    assert not button.isEnabled()
    assert click_native("exportCritical")
    wait_until(button.isEnabled)
    assert c.project.to_dict() == before and not c.dirty
