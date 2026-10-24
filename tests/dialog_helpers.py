"""Native QWidget dialog locators/input, alongside the QML workspace helpers."""
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QStyle,
    QStyleOptionButton,
    QWidget,
)


def native_dialog(name: str) -> QDialog:
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QDialog) and widget.objectName() == name:
            return widget
    raise AssertionError(f"Missing native dialog {name}")


def native_widget(name: str) -> QWidget | None:
    for dialog in QApplication.topLevelWidgets():
        if dialog.isVisible():
            widget = dialog.findChild(QWidget, name)
            if widget is not None and widget.isVisible():
                return widget
    return None


def required_widget(name: str) -> QWidget:
    widget = native_widget(name)
    assert widget is not None, f"Missing native widget {name}"
    return widget


def click_native(name: str) -> bool:
    widget = native_widget(name)
    if widget is None:
        return False
    position = widget.rect().center()
    if isinstance(widget, QCheckBox):
        option = QStyleOptionButton()
        option.initFrom(widget)
        option.text = widget.text()
        position = widget.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, widget).center()
    QTest.mouseClick(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, position)
    return True


def replace_native(name: str, text: str) -> bool:
    widget = native_widget(name)
    if widget is None:
        return False
    QTest.mouseClick(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, widget.rect().center())
    QTest.keyClick(widget, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    if isinstance(widget, QDoubleSpinBox):
        text = text.replace(".", widget.locale().decimalPoint())
    QTest.keyClicks(widget, text)
    return True
