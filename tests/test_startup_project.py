from datetime import datetime
import json
from pathlib import Path
from PySide6.QtCore import QObject, QSettings

from gantt_desktop.controller import Controller
from gantt_desktop.domain import Project, Task


def test_default_startup_project_is_empty_when_setting_is_off(qapp, tmp_path):
    ini_path = str(tmp_path / "test_settings.ini")
    settings = QSettings(ini_path, QSettings.Format.IniFormat)
    c = Controller(settings=settings)
    assert not c.open_last_file

    c.apply_startup_project()
    assert len(c.project.tasks) == 0
    assert c.project.name == "Новый проект"
    assert c._path is None


def test_startup_project_opens_last_edited_file_when_setting_is_on(qapp, tmp_path):
    ini_path = str(tmp_path / "test_settings.ini")
    settings = QSettings(ini_path, QSettings.Format.IniFormat)

    # Create and save a project file
    project_file = tmp_path / "my_project.gantt.json"
    p = Project(name="My Saved Work")
    p.tasks["t1"] = Task(id="t1", name="Custom Task", start=datetime(2026, 11, 2, 9, 0))
    project_file.write_text(json.dumps(p.to_dict()), encoding="utf-8")

    # Configure settings
    settings.setValue("general/open_last_file", True)
    settings.setValue("general/last_edited_file", str(project_file))
    settings.sync()

    c = Controller(settings=settings)
    assert c.open_last_file
    assert c.last_edited_file == str(project_file)

    c.apply_startup_project()
    assert c.project.name == "My Saved Work"
    assert "t1" in c.project.tasks
    assert c.project.tasks["t1"].name == "Custom Task"
    assert c._path == project_file


def test_startup_project_falls_back_to_empty_when_last_file_missing(qapp, tmp_path):
    ini_path = str(tmp_path / "test_settings.ini")
    settings = QSettings(ini_path, QSettings.Format.IniFormat)
    settings.setValue("general/open_last_file", True)
    settings.setValue("general/last_edited_file", str(tmp_path / "does_not_exist.gantt.json"))
    settings.sync()

    c = Controller(settings=settings)
    c.apply_startup_project()
    assert len(c.project.tasks) == 0
    assert c.project.name == "Новый проект"
    assert c._path is None


def test_record_last_edited_file_on_save_and_load(qapp, tmp_path):
    ini_path = str(tmp_path / "test_settings.ini")
    settings = QSettings(ini_path, QSettings.Format.IniFormat)
    c = Controller(settings=settings)

    file1 = tmp_path / "first.gantt.json"
    assert c.save_path(file1)
    assert c.last_edited_file == str(file1.resolve())
    assert settings.value("general/last_edited_file") == str(file1.resolve())

    # Create second file and load it
    file2 = tmp_path / "second.gantt.json"
    p = Project(name="Second File")
    file2.write_text(json.dumps(p.to_dict()), encoding="utf-8")

    assert c.load_path(file2)
    assert c.last_edited_file == str(file2.resolve())
    assert settings.value("general/last_edited_file") == str(file2.resolve())


def test_toggle_open_last_file_setting(qapp, tmp_path):
    ini_path = str(tmp_path / "test_settings.ini")
    settings = QSettings(ini_path, QSettings.Format.IniFormat)
    c = Controller(settings=settings)

    signals = []
    c.openLastFileChanged.connect(lambda: signals.append(True))

    assert not c.openLastFile
    c.set_open_last_file(True)
    assert c.openLastFile
    assert len(signals) == 1
    assert settings.value("general/open_last_file", type=bool) is True

    # Same value - no duplicate signal
    c.set_open_last_file(True)
    assert len(signals) == 1

    c.set_open_last_file(False)
    assert not c.openLastFile
    assert len(signals) == 2
    assert settings.value("general/open_last_file", type=bool) is False


from conftest import wait_until
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from test_ui import item, point


def test_open_last_file_switch_in_settings_ui(gui, qapp, tmp_path):
    controller, window = gui
    ini_path = str(tmp_path / "ui_settings.ini")
    settings = QSettings(ini_path, QSettings.Format.IniFormat)
    controller.settings = settings

    # Open settings drawer
    settings_btn = window.findChild(QObject, "settingsButton")
    assert settings_btn is not None
    settings_btn.clicked.emit()
    qapp.processEvents()

    drawer = window.findChild(QObject, "settingsDrawer")
    assert drawer is not None
    wait_until(lambda: drawer.property("opened"))

    switch_item = item(window, "openLastFileSwitch")
    assert switch_item is not None
    assert switch_item.property("checked") is False

    # Click switch to toggle ON
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(switch_item))
    qapp.processEvents()

    wait_until(lambda: controller.open_last_file is True)
    assert switch_item.property("checked") is True
    assert settings.value("general/open_last_file", type=bool) is True

    # Click switch to toggle OFF
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(switch_item))
    qapp.processEvents()

    wait_until(lambda: controller.open_last_file is False)
    assert switch_item.property("checked") is False
    assert settings.value("general/open_last_file", type=bool) is False


def test_empty_project_text_placed_on_left_side(gui, qapp):
    controller, window = gui
    controller.load_project(Project())
    qapp.processEvents()

    hint = item(window, "emptyStateHint")
    assert hint is not None
    assert hint.property("visible") is True
    assert controller.i18n.t("empty_start_hint") in hint.property("text")

    gantt_view = item(window, "ganttView")
    grid_width = gantt_view.property("gridWidth")

    # The hint must be strictly bounded to the left-hand table side
    assert hint.property("x") == 0
    assert hint.property("width") == grid_width


def test_ctrl_q_shortcut_closes_window(gui, qapp):
    controller, window = gui
    shortcut = window.findChild(QObject, "quitShortcut")
    assert shortcut is not None
    assert shortcut.property("enabled") is True

    menu_item = window.findChild(QObject, "quitMenuItem")
    assert menu_item is not None
    assert menu_item.property("text") == controller.i18n.t("menu_quit")

    calls = []
    window.setProperty("allowClose", False)
    # Return False to prevent actual window closure during test
    controller.confirmClose = lambda: (calls.append(True) or False)

    # 1. Trigger via keyboard event (Ctrl+Q)
    QTest.keyClick(window, Qt.Key.Key_Q, Qt.KeyboardModifier.ControlModifier)
    qapp.processEvents()
    assert len(calls) == 1

    # 2. Trigger via file menu item
    menu_item.triggered.emit()
    qapp.processEvents()
    assert len(calls) == 2






