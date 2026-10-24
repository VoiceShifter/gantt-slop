import pytest
from conftest import wait_until
from dialog_helpers import click_native, native_dialog, replace_native, required_widget
from PySide6.QtCore import QDate, QMetaObject, QPoint, QPointF, Qt
from PySide6.QtGui import QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QTabWidget,
)
from test_custom_fields import KINDS, value_for
from test_ui import drag, item, point

from gantt_desktop.sample import sample_project


def click(window, name):
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(item(window, name)))


def toggle_list(widget, key):
    assert isinstance(widget, QListWidget)
    selected = next(widget.item(i) for i in range(widget.count())
                    if widget.item(i).data(Qt.ItemDataRole.UserRole) == key)
    widget.setCurrentItem(selected)
    widget.setFocus()
    QTest.keyClick(widget, Qt.Key.Key_Space)


def open_fields(window):
    click(window, "fieldsButton")
    dialog = native_dialog("fieldsDialog")
    wait_until(dialog.isVisible)
    return dialog


def create_field_ui(c, window, kind):
    open_fields(window)
    assert click_native("newCustomField")
    editor = native_dialog("fieldDefinitionDialog")
    wait_until(editor.isVisible)
    assert replace_native("customFieldName", "Extra " + kind)
    combo = required_widget("customFieldType")
    assert isinstance(combo, QComboBox)
    combo.setCurrentIndex(combo.findData(kind))
    if kind in {"select", "multi"}:
        options = required_widget("customFieldOptions")
        assert isinstance(options, QPlainTextEdit)
        options.setPlainText("Todo\nDone")
    assert click_native("customFieldSave")
    wait_until(lambda: not editor.isVisible())
    key = next(f.id for f in c.project.custom_fields.values() if f.name == "Extra " + kind)
    assert click_native("closeFields")
    wait_until(lambda: not c.dialogs.property("modalOpen"))
    wait_until(lambda: point(item(window, "column-header-custom:" + key), 1, 0.5).x()
               <= point(item(window, "addColumnButton"), 0, 0.5).x() - 5)
    return key


def edit_value_ui(c, window, key, kind):
    click(window, "custom-value-" + key + "-sensor")
    editor = native_dialog("fieldValueDialog")
    wait_until(editor.isVisible)
    assert click_native("customValueUnset")
    value = value_for(c.project, kind)
    if kind == "text":
        assert replace_native("customTextValue", value)
    elif kind == "number":
        assert replace_native("customNumberValue", "0")
    elif kind == "date":
        date = required_widget("customDateValue")
        assert isinstance(date, QDateEdit)
        date.setDate(QDate.fromString(value, Qt.DateFormat.ISODate))
    elif kind == "select":
        choice = required_widget("customChoiceValue")
        assert isinstance(choice, QComboBox)
        choice.setCurrentIndex(choice.findText(value))
    elif kind == "color":
        assert replace_native("customColorValue", value)
    elif kind in {"multi", "people"}:
        for key_value in value:
            toggle_list(required_widget("customManyValues"), key_value)
    elif kind == "labels":
        text = required_widget("customTextValue")
        assert isinstance(text, QPlainTextEdit)
        text.setPlainText("\n".join(value))
    compact = {"number": "customNumberValue", "date": "customDateValue", "select": "customChoiceValue",
               "checkbox": "customCheckboxValue", "color": "customColorValue"}
    if kind in compact:
        widget = required_widget(compact[kind])
        assert widget.height() <= widget.sizeHint().height() + 2
    assert click_native("customValueSave")
    wait_until(lambda: not editor.isVisible())
    return value.lower() if kind == "color" else ["Todo", "Done"] if kind == "multi" else value


@pytest.mark.parametrize("width", [1000, 1366, 1920])
def test_plus_opens_real_field_picker_and_standard_fields_have_existing_logic(gui, width):
    c, window = gui
    window.resize(width, 768)
    view = item(window, "ganttView")
    wait_until(lambda: view.width() == width - 260)
    plus = item(window, "addColumnButton")
    assert plus.mapToScene(QPointF(plus.width(), 0)).x() <= width
    before = c.project.to_dict()
    click(window, "addColumnButton")
    dialog = native_dialog("fieldsDialog")
    wait_until(dialog.isVisible)
    assert isinstance(dialog, QDialog)
    standard = required_widget("standardFields")
    toggle_list(standard, "start")
    assert item(window, "ganttView").property("showStart")
    assert item(window, "column-header-start").isVisible()
    toggle_list(standard, "effort")
    assert not item(window, "ganttView").property("showEffort")
    assert c.project.to_dict() == before and not c.canUndo and not c.dirty
    assert click_native("closeFields")
    c.dialogs.showFields({"start": True, "effort": False})
    standard = required_widget("standardFields")
    assert isinstance(standard, QListWidget)
    effort = next(standard.item(i) for i in range(standard.count())
                  if standard.item(i).data(Qt.ItemDataRole.UserRole) == "effort")
    assert effort.checkState() == Qt.CheckState.Unchecked
    c.dialogs.closeAll()


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("kind", KINDS)
def test_all_custom_types_create_edit_save_reload_and_keep_native_theme(gui, qapp, tmp_path, dark, kind):
    c, window = gui
    assert c.theme is not None
    c.theme.setDark(dark)
    schedule = [(t.start, t.duration, t.effort, list(t.resource_ids)) for t in c.project.tasks.values()]
    key = create_field_ui(c, window, kind)
    assert c.project.custom_fields[key].kind == kind
    value = edit_value_ui(c, window, key, kind)
    assert c.project.tasks["sensor"].custom_values[key] == value
    editor = native_dialog("fieldValueDialog")
    assert editor.style() is qapp.style() and not editor.styleSheet()
    assert editor.palette().color(QPalette.ColorRole.Window) == qapp.palette().color(QPalette.ColorRole.Window)
    assert [(t.start, t.duration, t.effort, t.resource_ids) for t in c.project.tasks.values()] == schedule
    saved = c.project.to_dict()
    path = tmp_path / (kind + ".gantt.json")
    assert c.save_path(path) and c.load_path(path)
    assert c.project.to_dict() == saved
    assert not c.dirty
    assert c.record("sensor")["customTexts"][key]
    if kind == "number":
        assert c.record("planning")["customValues"][key] == 0
    if kind == "checkbox":
        click(window, "custom-check-" + key + "-sensor")
        wait_until(lambda: c.project.tasks["sensor"].custom_values[key] is True)
        c.undo()
        assert c.project.to_dict() == saved


def test_create_cancel_and_validation_keep_the_definition_draft_without_history(gui):
    c, window = gui
    before = c.project.to_dict()
    open_fields(window)
    assert click_native("newCustomField")
    assert replace_native("customFieldName", "Draft")
    combo = required_widget("customFieldType")
    assert isinstance(combo, QComboBox)
    combo.setCurrentIndex(combo.findData("select"))
    assert click_native("customFieldSave")
    assert native_dialog("fieldDefinitionDialog").isVisible()
    assert required_widget("customFieldName").property("text") == "Draft"
    assert required_widget("dialogError").isVisible()
    assert c.project.to_dict() == before and not c.canUndo
    assert click_native("customFieldCancel")
    assert click_native("closeFields")
    assert c.project.to_dict() == before and not c.dirty


def test_hidden_custom_values_rename_and_confirmed_delete_are_not_lost(gui, tmp_path):
    c, window = gui
    key = create_field_ui(c, window, "text")
    edit_value_ui(c, window, key, "text")
    assert c.save_path(tmp_path / "saved.json")
    before = c.project.to_dict()
    dialog = open_fields(window)
    tabs = required_widget("fieldTabs")
    assert isinstance(tabs, QTabWidget)
    assert not required_widget("editCustomField").isEnabled()
    assert not required_widget("removeCustomField").isEnabled()
    tabs.setCurrentIndex(1)
    assert required_widget("editCustomField").isEnabled()
    toggle_list(required_widget("customFields"), "custom:" + key)
    assert key in item(window, "ganttView").property("hiddenCustomFields").toVariant()
    assert c.project.to_dict() == before and not c.dirty
    assert click_native("editCustomField")
    assert not required_widget("customFieldType").isEnabled()
    assert replace_native("customFieldName", "Renamed")
    assert click_native("customFieldSave")
    assert c.project.custom_fields[key].name == "Renamed"
    assert c.project.tasks["sensor"].custom_values[key]
    assert click_native("removeCustomField")
    box = native_dialog("deleteCustomFieldDialog")
    assert isinstance(box, QMessageBox)
    button = box.button(QMessageBox.StandardButton.Ok)
    assert button is not None
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    wait_until(lambda: key not in c.project.custom_fields)
    assert all(key not in t.custom_values for t in c.project.tasks.values())
    c.undo()
    assert c.project.custom_fields[key].name == "Renamed"
    assert c.project.tasks["sensor"].custom_values[key]
    assert dialog.isVisible()
    c.dialogs.closeAll()


def test_numeric_group_and_total_are_readonly_and_unset_false_zero_stay_distinct(gui):
    c, window = gui
    key = create_field_ui(c, window, "number")
    assert c.setCustomValue("sensor", key, 10)
    assert c.setCustomValue("scenario", key, 0)
    group = item(window, "custom-value-" + key + "-planning")
    assert c.record("planning")["customValues"][key] == 10
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(group))
    assert not c.dialogs.property("modalOpen")
    c.dialogs.showFieldValue("planning", key)
    assert not c.dialogs.property("modalOpen")
    c.dialogs.showFieldValue("sensor", key)
    assert click_native("customValueUnset")
    assert click_native("customValueSave")
    assert key not in c.project.tasks["sensor"].custom_values
    assert c.record("planning")["customValues"][key] == 0


def test_value_noop_precision_and_early_dates_preserved_and_load_closes_editors(gui):
    c, window = gui
    key = create_field_ui(c, window, "number")
    assert c.setCustomValue("sensor", key, 0.123456789012345)
    before = c.project.to_dict()
    index = c._history_index
    c.dialogs.showFieldValue("sensor", key)
    assert click_native("customValueSave")
    assert c.project.to_dict() == before and c._history_index == index
    date = c.saveCustomField("", "Date", "date", [], "")
    assert c.setCustomValue("sensor", date, "0001-01-01")
    c.dialogs.showFieldValue("sensor", date)
    value = required_widget("customDateValue")
    assert isinstance(value, QDateEdit) and value.date() == QDate(1, 1, 1)
    assert click_native("customValueSave")
    assert c.project.tasks["sensor"].custom_values[date] == "0001-01-01"
    c.dialogs.showFieldValue("sensor", date)
    c.load_project(sample_project())
    assert not c.dialogs.property("modalOpen")
    assert not c.project.custom_fields
    assert QMetaObject.invokeMethod(item(window, "ganttView"), "resetColumnWidths")


def test_custom_column_resizes_without_changing_field_or_values(gui):
    c, window = gui
    key = create_field_ui(c, window, "text")
    before = c.project.to_dict()
    index = c._history_index
    header = item(window, "column-header-custom:" + key)
    start = point(header, 1, 0.5)
    drag(window, start, start + QPoint(80, 0))
    assert item(window, "column-header-custom:" + key).width() == 240
    assert c.project.to_dict() == before and c._history_index == index


def test_invalid_numeric_value_stays_in_native_editor_with_inline_error(gui):
    c, window = gui
    key = create_field_ui(c, window, "number")
    before = c.project.to_dict()
    index = c._history_index
    c.dialogs.showFieldValue("sensor", key)
    assert click_native("customValueUnset")
    assert replace_native("customNumberValue", "nan")
    assert click_native("customValueSave")
    dialog = native_dialog("fieldValueDialog")
    error = dialog.findChild(QLabel, "dialogError")
    assert dialog.isVisible() and error is not None and error.isVisible()
    assert required_widget("customNumberValue").property("text") == "nan"
    assert c.project.to_dict() == before and c._history_index == index
    c.dialogs.closeAll()


def test_window_close_also_closes_field_picker_and_definition_draft(gui):
    c, window = gui
    before = c.project.to_dict()
    open_fields(window)
    assert click_native("newCustomField")
    window.close()
    wait_until(lambda: not c.dialogs.property("modalOpen"))
    assert c.project.to_dict() == before and not c.canUndo
