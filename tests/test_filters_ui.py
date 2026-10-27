import pytest
from conftest import wait_until
from dialog_helpers import click_native, native_dialog, replace_native
from PySide6.QtCore import QDate, QObject, QPoint, Qt
from PySide6.QtTest import QTest
from test_custom_fields_ui import toggle_list
from test_filters import filter_project, visible
from test_ui import item, point

from gantt_desktop.domain import TaskFilter
from gantt_desktop.filter_dialog import FilterDialog


def open_filters(window):
    window.requestActivate()
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(item(window, "filterButton")))
    action = item(window, "advancedFiltersMenuItem")
    wait_until(action.isVisible)
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(action))
    dialog = native_dialog("filterDialog")
    assert isinstance(dialog, FilterDialog)
    wait_until(dialog.isVisible)
    return dialog


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("width", [1000, 1366, 1920])
def test_toolbar_native_filter_apply_cancel_theme_and_hierarchy(gui, dark, width):
    c, window = gui
    c.load_project(filter_project())
    assert c.theme is not None
    c.theme.setDark(dark)
    window.resize(width, 960)
    before = c.project.to_dict()
    dialog = open_filters(window)
    assert dialog.windowHandle().transientParent() is window
    assert c.dialogs.modalOpen and not dialog.styleSheet()
    toggle_list(dialog.choices["kinds"], "milestone")
    toggle_list(dialog.choices["resources"], "r1")
    assert not c.filterActive and c.project.to_dict() == before
    assert click_native("filterApply")
    wait_until(lambda: not c.dialogs.modalOpen)
    assert visible(c) == {"g", "m"} and item(window, "filterButton").property("checked")
    assert item(window, "taskbar-m").isVisible()
    assert not c.canUndo and not c.dirty and c.project.to_dict() == before
    dialog = open_filters(window)
    assert dialog.criteria().kinds == ["milestone"]
    assert click_native("filterClear")
    assert not dialog.criteria().extra_active and c.filterActive
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    wait_until(lambda: not c.dialogs.modalOpen)
    assert visible(c) == {"g", "m"}
    open_filters(window)
    assert click_native("filterClear") and click_native("filterApply")
    assert not c.filterActive and visible(c) == set(c.project.tasks)
    assert c.project.to_dict() == before


def test_preset_drafts_apply_load_delete_cancel_and_undo(gui, tmp_path):
    c, window = gui
    c.load_project(filter_project())
    before = c.project.to_dict()
    dialog = open_filters(window)
    toggle_list(dialog.choices["kinds"], "milestone")
    assert replace_native("filterPresetName", "Milestones") and click_native("filterAddPreset")
    assert "Milestones" in dialog.saved and c.project.to_dict() == before
    assert click_native("filterCancel")
    dialog = open_filters(window)
    assert dialog.saved == {} and not dialog.criteria().extra_active
    toggle_list(dialog.choices["resources"], "r1")
    assert replace_native("filterPresetName", "People") and click_native("filterAddPreset")
    assert click_native("filterApply")
    assert c.project.saved_filters["People"].resources == ["r1"] and c.canUndo
    saved = c.project.to_dict()
    c.clearFilters()
    dialog = open_filters(window)
    dialog.presets.setFocus()
    QTest.keyClick(dialog.presets, Qt.Key.Key_Down)
    assert dialog.criteria().resources == ["r1"]
    assert not c.filterActive
    assert click_native("filterApply") and visible(c) == {"g", "nested", "a", "m"}
    assert c.project.to_dict() == saved
    path = tmp_path / "presets.gantt.json"
    assert c.save_path(path) and c.load_path(path)
    assert c.project.to_dict() == saved and not c.filterActive
    dialog = open_filters(window)
    dialog.presets.setFocus()
    QTest.keyClick(dialog.presets, Qt.Key.Key_Down)
    assert click_native("filterDeletePreset") and not dialog.saved
    assert click_native("filterCancel") and c.project.to_dict() == saved
    dialog = open_filters(window)
    dialog.presets.setFocus()
    QTest.keyClick(dialog.presets, Qt.Key.Key_Down)
    assert click_native("filterDeletePreset") and click_native("filterApply")
    assert not c.project.saved_filters and c.dirty
    c.undo()
    assert c.project.to_dict() == saved and not c.dirty


def test_invalid_dates_keep_draft_open_and_calendar_is_native(gui):
    c, window = gui
    c.load_project(filter_project())
    before = c.project.to_dict()
    dialog = open_filters(window)
    lower, upper = dialog.bounds["span"]
    assert click_native("filter-span-0-enabled") and click_native("filter-span-1-enabled")
    lower[1].setDate(QDate(2025, 12, 3))
    upper[1].setDate(QDate(2025, 12, 1))
    assert click_native("filterApply")
    assert dialog.isVisible() and dialog.error.isVisible() and "Начало диапазона" in dialog.error.text()
    assert c.project.to_dict() == before and not c.filterActive
    upper[1].setFocus()
    QTest.mouseClick(upper[1], Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     QPoint(upper[1].width() - 8, upper[1].height() // 2))
    calendar = upper[1].calendarWidget()
    wait_until(calendar.isVisible)
    QTest.keyClick(calendar, Qt.Key.Key_Escape)
    upper[1].setDate(QDate(2025, 12, 3))
    assert click_native("filterApply") and visible(c) == {"c"}
    assert c.project.to_dict() == before


def test_search_quick_filters_and_reset_stay_synchronized_with_toolbar(gui):
    c, window = gui
    c.load_project(filter_project())
    dialog = open_filters(window)
    dialog.query.setText("ПРИ")
    dialog.quick.setCurrentIndex(dialog.quick.findData("complete"))
    assert click_native("filterApply")
    assert visible(c) == {"g", "m"}
    assert item(window, "taskSearch").property("text") == "при"
    assert window.property("filterCode") == "complete"
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(item(window, "filterButton")))
    action = item(window, "clearFiltersMenuItem")
    wait_until(action.isVisible)
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(action))
    assert not c.filterActive and item(window, "taskSearch").property("text") == ""
    assert window.property("filterCode") == "all"


def test_duplicate_names_and_missing_resource_presets_are_not_silently_changed(gui):
    c, window = gui
    c.load_project(filter_project())
    assert c.apply_filter(TaskFilter(resources=["missing"]), {"Saved": TaskFilter(resources=["missing"])})
    before = c.project.to_dict()
    dialog = open_filters(window)
    assert dialog.criteria().resources == ["missing"]
    assert any("Удалённый ресурс" in dialog.choices["resources"].item(i).text()
               for i in range(dialog.choices["resources"].count()))
    assert replace_native("filterPresetName", "sAvEd") and click_native("filterAddPreset")
    assert dialog.error.isVisible() and list(dialog.saved) == ["Saved"]
    assert click_native("filterCancel") and c.project.to_dict() == before


@pytest.mark.parametrize("action", ["hide", "load"])
def test_project_and_window_lifecycle_discard_filter_drafts(gui, action):
    c, window = gui
    before = c.project.to_dict()
    dialog = open_filters(window)
    toggle_list(dialog.choices["kinds"], "milestone")
    assert replace_native("filterPresetName", "Draft") and click_native("filterAddPreset")
    if action == "hide":
        window.hide()
    else:
        c.load_project(filter_project())
    wait_until(lambda: not dialog.isVisible())
    assert not c.dialogs.modalOpen and not c.project.saved_filters and not c.filterActive
    if action == "hide":
        assert c.project.to_dict() == before
    inspector = window.findChild(QObject, "taskInspector")
    assert inspector is not None and not inspector.property("visible")
