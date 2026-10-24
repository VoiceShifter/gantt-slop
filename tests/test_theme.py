import pytest
from conftest import wait_until
from dialog_helpers import native_dialog
from PySide6.QtCore import (
    QCoreApplication,
    QEvent,
    QMetaObject,
    QObject,
    QPointF,
    QSettings,
    Qt,
)
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QWidget
from test_ui import item, point

from gantt_desktop.app import create_window
from gantt_desktop.controller import Controller
from gantt_desktop.theme import DARK, LIGHT, AppTheme


def click(window, name):
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(item(window, name)))


def open_settings(window):
    click(window, "settingsButton")
    drawer = window.findChild(QObject, "settingsDrawer")
    assert drawer is not None
    wait_until(lambda: drawer.property("opened"))
    return drawer


def canvas_pixel(window, name):
    position = item(window, name).mapToScene(QPointF(17, 10)).toPoint()
    image = window.grabWindow()
    assert not image.isNull()
    return image.pixelColor(position * image.devicePixelRatio())


def test_theme_settings_round_trip_and_noop(qapp, tmp_path):
    path = str(tmp_path / "preferences.ini")
    settings = QSettings(path, QSettings.Format.IniFormat)
    settings.setValue("unrelated", "keep")
    theme = AppTheme(settings)
    changed = QSignalSpy(theme.changed)
    assert not theme.property("dark")
    theme.setDark(True)
    theme.setDark(True)
    assert changed.count() == 1
    loaded = AppTheme(QSettings(path, QSettings.Format.IniFormat))
    assert loaded.property("dark")
    loaded.setDark(False)
    saved = QSettings(path, QSettings.Format.IniFormat)
    assert not saved.value("appearance/dark", True, type=bool)
    assert saved.value("unrelated") == "keep"


def test_default_is_consistently_light_even_after_a_dark_application_palette(qapp):
    AppTheme().setDark(True)
    assert qapp.palette().color(QPalette.ColorRole.Window) == QColor(DARK["surface"])
    theme = AppTheme()
    assert not theme.property("dark")
    assert qapp.palette().color(QPalette.ColorRole.Window) == QColor(LIGHT["surface"])


@pytest.mark.parametrize("dark", [False, True])
def test_native_palette_and_qml_tokens_agree(qapp, dark):
    theme = AppTheme()
    theme.setDark(dark)
    colors = DARK if dark else LIGHT
    assert LIGHT.keys() == DARK.keys()
    assert theme.property("colors") == colors
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        for role, key in ((QPalette.ColorRole.Window, "surface"), (QPalette.ColorRole.Base, "input"),
                          (QPalette.ColorRole.Text, "text"), (QPalette.ColorRole.Button, "panel"),
                          (QPalette.ColorRole.ToolTipText, "text"), (QPalette.ColorRole.Highlight, "accent")):
            assert qapp.palette().color(group, role) == QColor(colors[key])
    assert qapp.palette().color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text) == QColor(colors["disabled"])


def test_real_settings_switch_repaints_both_canvases_and_supports_keyboard(gui):
    c, window = gui
    assert c.theme is not None
    before = c.project.to_dict()
    click(window, "workloadToggle")
    wait_until(lambda: canvas_pixel(window, "workloadCanvas") == QColor(LIGHT["surface"]))
    assert canvas_pixel(window, "chartCanvas") == QColor(LIGHT["surface"])
    drawer = open_settings(window)
    click(window, "themeSwitch")
    assert c.theme.property("dark")
    assert item(window, "themeSwitch").property("checked")
    track = item(window, "themeSwitchTrack")
    thumb = item(window, "themeSwitchThumb")
    assert track.property("color") == QColor(DARK["accent"])
    assert thumb.x() == pytest.approx(track.width() - thumb.width() - 2)
    QTest.keyClick(window, Qt.Key.Key_Escape)
    wait_until(lambda: not drawer.property("visible"))
    wait_until(lambda: canvas_pixel(window, "chartCanvas") == QColor(DARK["surface"]))
    wait_until(lambda: canvas_pixel(window, "workloadCanvas") == QColor(DARK["surface"]))
    assert window.color() == QColor(DARK["surface"])
    assert item(window, "task-name-sensor").property("color") == QColor(DARK["text"])
    drawer = open_settings(window)
    item(window, "themeSwitch").forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_Space)
    assert not c.theme.property("dark")
    assert item(window, "themeSwitchThumb").x() == pytest.approx(2)
    click(window, "closeSettingsButton")
    wait_until(lambda: not drawer.property("visible"))
    wait_until(lambda: canvas_pixel(window, "chartCanvas") == QColor(LIGHT["surface"]))
    wait_until(lambda: canvas_pixel(window, "workloadCanvas") == QColor(LIGHT["surface"]))
    assert c.project.to_dict() == before
    assert not c.canUndo and not c.dirty


def test_settings_blocks_background_project_shortcuts_and_keeps_history(gui):
    c, window = gui
    assert c.editField("sensor", "name", "Renamed sensor")
    c.select("sensor")
    before = c.project.to_dict()
    drawer = open_settings(window)
    QTest.keyClick(window, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(window, Qt.Key.Key_Delete)
    assert c.project.to_dict() == before and c.canUndo and c.dirty
    click(window, "themeSwitch")
    QTest.keyClick(window, Qt.Key.Key_Escape)
    wait_until(lambda: not drawer.property("visible"))
    assert c.project.to_dict() == before and c.canUndo and c.dirty
    c.undo()
    assert not c.dirty


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("kind", ["resources", "assignments", "dependency", "help", "delete"])
def test_existing_and_open_native_dialogs_follow_selected_theme(gui, qapp, dark, kind):
    c, window = gui
    assert c.theme is not None
    before = c.project.to_dict()
    c.theme.setDark(dark)
    if kind == "resources":
        c.dialogs.showResources("")
        name = "resourceManager"
    elif kind == "assignments":
        c.dialogs.showAssignments("sensor")
        name = "resourcePicker"
    elif kind == "dependency":
        link = c.project.dependencies[0]
        c.dialogs.showDependency(link.source, link.target, link.kind, link.id)
        name = "dependencyDialog"
    elif kind == "help":
        c.dialogs.showHelp()
        name = "helpDialog"
    else:
        c.dialogs.confirmDelete("sensor", False)
        name = "deleteDialog"
    dialog = native_dialog(name)
    for value in (dark, not dark, dark):
        c.theme.setDark(value)
        colors = DARK if value else LIGHT
        wait_until(lambda colors=colors: dialog.palette().color(QPalette.ColorRole.Window) == QColor(colors["surface"]))
        assert window.color() == QColor(colors["surface"])
        for widget in [dialog, *dialog.findChildren(QWidget)]:
            assert not widget.styleSheet()
            assert widget.palette().color(QPalette.ColorGroup.Active, QPalette.ColorRole.Text) == QColor(colors["text"])
        assert dialog.style() is qapp.style()
        assert dialog.font().family() == qapp.font().family()
    c.dialogs.closeAll()
    assert c.project.to_dict() == before and not c.canUndo and not c.dirty


@pytest.mark.parametrize("width", [1000, 1366, 1920])
def test_settings_button_and_switch_fit_supported_window_sizes(gui, width):
    _c, window = gui
    window.resize(width, 768)
    wait_until(lambda: item(window, "settingsButton").mapToScene(QPointF()).x() < width)
    button = item(window, "settingsButton")
    assert button.mapToScene(QPointF()).x() >= 0
    assert button.mapToScene(QPointF(button.width(), 0)).x() <= width
    drawer = open_settings(window)
    switch = item(window, "themeSwitch")
    assert switch.mapToScene(QPointF()).x() >= width - drawer.property("width") + 20
    assert switch.mapToScene(QPointF(switch.width(), 0)).x() <= width - 20
    QTest.keyClick(window, Qt.Key.Key_Escape)
    wait_until(lambda: not drawer.property("visible"))


@pytest.mark.parametrize("dark", [False, True])
def test_side_drawers_and_combo_popup_share_the_theme(gui, dark):
    c, window = gui
    assert c.theme is not None
    c.theme.setDark(dark)
    colors = DARK if dark else LIGHT
    c.select("sensor")
    inspector = window.findChild(QObject, "taskInspector")
    assert inspector is not None and QMetaObject.invokeMethod(inspector, "open")
    wait_until(lambda: inspector.property("opened"))
    assert inspector.property("background").property("color") == QColor(colors["surface"])
    status = item(window, "inspectorStatus")
    assert status.property("background").property("color") == QColor(colors["panel"])
    popup = next(child for child in status.findChildren(QObject) if child.inherits("QQuickPopup"))
    assert QMetaObject.invokeMethod(popup, "open")
    wait_until(lambda: popup.property("visible"))
    assert popup.property("background").property("color") == QColor(colors["surface"])
    assert QMetaObject.invokeMethod(popup, "close")
    c.setBulkMode(True)
    bulk = window.findChild(QObject, "bulkEditor")
    assert bulk is not None
    wait_until(lambda: bulk.property("opened"))
    assert bulk.property("background").property("color") == QColor(colors["surface"])
    assert item(window, "bulkAssignEnabled").property("indicator").property("color") == QColor(colors["input"])
    drawer = open_settings(window)
    assert drawer.property("background").property("color") == QColor(colors["surface"])
    QTest.keyClick(window, Qt.Key.Key_Escape)
    wait_until(lambda: not drawer.property("visible"))
    assert c.bulkMode
    c.setBulkMode(False)
    assert not c.canUndo and not c.dirty


def test_clicked_preference_is_restored_in_a_new_window(qapp, tmp_path):
    path = str(tmp_path / "preferences.ini")
    windows = []
    try:
        for expected_dark in (False, True):
            c = Controller()
            theme = AppTheme(QSettings(path, QSettings.Format.IniFormat))
            engine, window = create_window(c, theme)
            windows.append((c, engine, window))
            window.setProperty("allowClose", True)
            assert QTest.qWaitForWindowExposed(window, 3000)
            window.requestActivate()
            drawer = open_settings(window)
            assert item(window, "themeSwitch").property("checked") == expected_dark
            assert window.color() == QColor((DARK if expected_dark else LIGHT)["surface"])
            if not expected_dark:
                click(window, "themeSwitch")
            QTest.keyClick(window, Qt.Key.Key_Escape)
            wait_until(lambda drawer=drawer: not drawer.property("visible"))
            window.close()
        assert QSettings(path, QSettings.Format.IniFormat).value("appearance/dark", False, type=bool)
    finally:
        for c, engine, window in windows:
            window.close()
            c.dialogs.dispose()
            engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qapp.processEvents()
