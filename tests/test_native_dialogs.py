import pytest
from conftest import wait_until
from dialog_helpers import click_native, native_dialog, required_widget
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QWidget,
)


@pytest.mark.parametrize("dark", [False, True])
def test_resource_dialog_uses_application_palette_font_and_standard_controls(gui, qapp, dark):
    c, window = gui
    previous = QPalette(qapp.palette())
    palette = QPalette(previous)
    palette.setColor(QPalette.ColorRole.Window, QColor("#242424" if dark else "#f3f3f3"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#181818" if dark else "#ffffff"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#eeeeee" if dark else "#202020"))
    palette.setColor(QPalette.ColorRole.Text, palette.color(QPalette.ColorRole.WindowText))
    palette.setColor(QPalette.ColorRole.Button, palette.color(QPalette.ColorRole.Window))
    palette.setColor(QPalette.ColorRole.ButtonText, palette.color(QPalette.ColorRole.WindowText))
    try:
        qapp.setPalette(palette)
        c.dialogs.showResources("")
        dialog = native_dialog("resourceManager")
        assert isinstance(dialog, QDialog)
        assert dialog.style() is qapp.style()
        assert dialog.palette().color(QPalette.ColorRole.Window) == palette.color(QPalette.ColorRole.Window)
        assert dialog.font().family() == qapp.font().family()
        assert isinstance(required_widget("resourceName"), QLineEdit)
        assert isinstance(required_widget("resourceCapacity"), QDoubleSpinBox)
        assert isinstance(required_widget("resourceList"), QListWidget)
        assert isinstance(required_widget("resourceDay-0"), QCheckBox)
        for widget in [dialog, *dialog.findChildren(QWidget)]:
            assert not widget.styleSheet()
        assert required_widget("resourceName").palette().color(QPalette.ColorRole.Base) == palette.color(QPalette.ColorRole.Base)
        for label in dialog.findChildren(QLabel):
            assert label.palette().color(QPalette.ColorRole.WindowText) == palette.color(QPalette.ColorRole.WindowText)
        assert dialog.windowHandle().transientParent() is window
        assert dialog.windowModality() == Qt.WindowModality.WindowModal
        assert not dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    finally:
        c.dialogs.closeAll()
        qapp.setPalette(previous)


def test_editors_and_help_are_real_native_dialog_windows(gui):
    c, window = gui
    link = c.project.dependencies[0]
    cases = [
        ("resourceManager", lambda: c.dialogs.showResources("")),
        ("resourcePicker", lambda: c.dialogs.showAssignments("sensor")),
        ("dependencyDialog", lambda: c.dialogs.showDependency(link.source, link.target, link.kind, link.id)),
        ("helpDialog", c.dialogs.showHelp),
    ]
    for name, show in cases:
        show()
        dialog = native_dialog(name)
        assert isinstance(dialog, QDialog) and dialog.isWindow()
        assert dialog.windowHandle().transientParent() is window
        assert c.dialogs.property("modalOpen")
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        wait_until(lambda: not c.dialogs.property("modalOpen"))


def test_project_load_closes_native_editors(gui):
    c, _window = gui
    c.dialogs.showResources("")
    dialog = native_dialog("resourceManager")
    assert dialog.isVisible()
    c.loadExample()
    assert not dialog.isVisible() and not c.dialogs.property("modalOpen")


def test_main_window_close_also_closes_nested_native_confirmation(gui):
    c, window = gui
    before = c.project.to_dict()
    c.dialogs.showResources(c.project.tasks["sensor"].resource_ids[0])
    assert click_native("removeResourceButton")
    confirmation = native_dialog("deleteResourceDialog")
    assert isinstance(confirmation, QMessageBox)
    window.close()
    wait_until(lambda: not c.dialogs.property("modalOpen"))
    assert c.project.to_dict() == before


def test_native_resource_delete_confirmation_is_undoable(gui):
    c, _window = gui
    before = c.project.to_dict()
    key = c.project.tasks["sensor"].resource_ids[0]
    c.dialogs.showResources(key)
    assert click_native("removeResourceButton")
    box = native_dialog("deleteResourceDialog")
    assert isinstance(box, QMessageBox)
    button = box.button(QMessageBox.StandardButton.Ok)
    assert button is not None
    QTest.mouseClick(button, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, button.rect().center())
    assert key not in c.project.resources
    c.dialogs.closeAll()
    c.undo()
    assert c.project.to_dict() == before


def test_invalid_dependency_shows_inline_native_error_without_losing_draft(gui):
    c, _window = gui
    before = c.project.to_dict()
    link = c.project.dependencies[0]
    c.dialogs.showDependency(link.source, link.target, link.kind, link.id)
    dialog = native_dialog("dependencyDialog")
    source = required_widget("dependencySource")
    assert isinstance(source, QComboBox)
    source.setCurrentIndex(source.findData("planning"))
    assert click_native("saveDependency")
    assert dialog.isVisible() and c.project.to_dict() == before
    error = dialog.findChild(QLabel, "dialogError")
    assert error is not None and error.isVisible() and error.text()
    assert not c.canUndo


def test_unchanged_native_forms_preserve_sub_display_precision(gui):
    c, _window = gui
    key = c.project.tasks["sensor"].resource_ids[0]
    assert c.updateResource(key, "Клиент", "8.001", [0, 1, 2, 3, 4])
    assert c.editField("sensor", "effort", "8.001")
    before = c.project.to_dict()
    c.dialogs.showResources(key)
    assert click_native("saveResourceButton")
    assert c.project.to_dict() == before
    c.dialogs.closeAll()
    c.dialogs.showAssignments("sensor")
    assert click_native("applyResourceAssignment")
    assert c.project.to_dict() == before


def test_native_form_layout_adapts_to_larger_system_font(gui, qapp):
    c, _window = gui
    previous = QFont(qapp.font())
    larger = QFont(previous)
    larger.setPointSize(14)
    try:
        qapp.setFont(larger)
        c.dialogs.showResources("")
        dialog = native_dialog("resourceManager")
        qapp.processEvents()
        assert dialog.font().pointSize() == 14
        assert dialog.height() >= dialog.minimumSizeHint().height()
        assert dialog.width() >= dialog.minimumSizeHint().width()
    finally:
        c.dialogs.closeAll()
        qapp.setFont(previous)


def test_enter_uses_the_native_resource_save_default(gui):
    c, _window = gui
    c.dialogs.showResources("")
    assert click_native("newResourceButton")
    name = required_widget("resourceName")
    QTest.mouseClick(name, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, name.rect().center())
    wait_until(name.hasFocus)
    QTest.keyClicks(name, "newperson")
    QTest.keyClick(name, Qt.Key.Key_Return)
    assert any(r.name == "newperson" for r in c.project.resources.values())
