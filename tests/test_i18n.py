from PySide6.QtCore import QObject, QSettings

from gantt_desktop.controller import Controller
from gantt_desktop.i18n import I18n


def test_i18n_unit_default_and_switching():
    i18n = I18n()
    assert i18n.language == "ru"
    assert len(i18n.languages) == 2
    assert i18n.languages[0]["code"] == "ru"
    assert i18n.languages[1]["code"] == "en"

    # Default Russian messages and collections
    assert i18n.t("settings") == "Настройки"
    assert i18n.t("unknown_key_xyz") == "unknown_key_xyz"
    assert i18n.months[0] == "Январь"
    assert i18n.dayNames[0] == "Пн"
    assert i18n.statuses["open"] == "Открыт"
    assert i18n.priorities["medium"] == "Средний"

    # Switch to English
    signals = []
    i18n.changed.connect(lambda: signals.append(True))
    i18n.setLanguage("en")

    assert len(signals) == 1
    assert i18n.language == "en"
    assert i18n.t("settings") == "Settings"
    assert i18n.months[0] == "January"
    assert i18n.dayNames[0] == "Mon"
    assert i18n.statuses["open"] == "Open"
    assert i18n.priorities["medium"] == "Normal"

    # Invalid language ignored
    i18n.setLanguage("fr")
    assert i18n.language == "en"
    assert len(signals) == 1

    # Switch back to Russian
    i18n.setLanguage("ru")
    assert len(signals) == 2
    assert i18n.language == "ru"
    assert i18n.t("settings") == "Настройки"


def test_i18n_qsettings_persistence(tmp_path):
    ini_file = str(tmp_path / "test_settings.ini")
    settings = QSettings(ini_file, QSettings.Format.IniFormat)

    i18n1 = I18n(settings=settings)
    assert i18n1.language == "ru"

    i18n1.setLanguage("en")
    assert settings.value("general/language") == "en"

    # Second instance reading same settings
    settings2 = QSettings(ini_file, QSettings.Format.IniFormat)
    i18n2 = I18n(settings=settings2)
    assert i18n2.language == "en"
    assert i18n2.t("settings") == "Settings"


def test_controller_language_reactivity():
    c = Controller()
    assert c.i18n.language == "ru"
    assert c.fileName == "Без файла"
    assert "Открыт" in [choice["label"] for choice in c.statusChoices]
    assert "Средний" in [choice["label"] for choice in c.priorityChoices]

    c.i18n.setLanguage("en")
    assert c.fileName == "No file"
    assert "Open" in [choice["label"] for choice in c.statusChoices]
    assert "Normal" in [choice["label"] for choice in c.priorityChoices]

    c.i18n.setLanguage("ru")
    assert c.fileName == "Без файла"
    assert "Открыт" in [choice["label"] for choice in c.statusChoices]


def test_native_dialogs_language_switch(qapp):
    c = Controller()
    c.dialogs.showExport({})
    export_dialog = c.dialogs._editors.get("export")
    assert export_dialog is not None
    assert "Экспорт" in export_dialog.windowTitle()
    export_dialog.close()

    c.i18n.setLanguage("en")
    c.dialogs.showExport({})
    export_dialog_en = c.dialogs._editors.get("export")
    assert export_dialog_en is not None
    assert "Export" in export_dialog_en.windowTitle()
    export_dialog_en.close()

    c.dialogs.showBaselines()
    baseline_dialog_en = c.dialogs._editors.get("baselines")
    assert baseline_dialog_en is not None
    assert "Baselines" in baseline_dialog_en.windowTitle()
    baseline_dialog_en.close()

    c.i18n.setLanguage("ru")
    c.dialogs.showExport({})
    export_dialog_ru = c.dialogs._editors.get("export")
    assert export_dialog_ru is not None
    assert "Экспорт" in export_dialog_ru.windowTitle()
    export_dialog_ru.close()


def test_qml_language_switch_in_settings(gui, qapp):
    controller, window = gui

    settings_btn = window.findChild(QObject, "settingsButton")
    assert settings_btn is not None
    assert settings_btn.property("text") == "⚙ Настройки"

    # Open settings drawer
    settings_drawer = window.findChild(QObject, "settingsDrawer")
    assert settings_drawer is not None
    settings_btn.clicked.emit()
    qapp.processEvents()

    lang_combo = window.findChild(QObject, "languageCombo")
    assert lang_combo is not None
    assert lang_combo.property("currentIndex") == 0

    # Switch to English
    lang_combo.setProperty("currentIndex", 1)
    lang_combo.activated.emit(1)
    qapp.processEvents()

    assert controller.i18n.language == "en"
    assert settings_btn.property("text") == "⚙ Settings"

    # Verify main window toolbar elements
    search = window.findChild(QObject, "taskSearch")
    assert search is not None
    assert search.property("placeholderText") == "Search tasks by name"

    undo_btn = window.findChild(QObject, "undoButton")
    assert undo_btn is not None
    assert undo_btn.property("hint") == "Undo · Ctrl+Z"

    # Switch back to Russian
    lang_combo.setProperty("currentIndex", 0)
    lang_combo.activated.emit(0)
    qapp.processEvents()

    assert controller.i18n.language == "ru"
    assert settings_btn.property("text") == "⚙ Настройки"
    assert search.property("placeholderText") == "Поиск по имени задачи"
    assert undo_btn.property("hint") == "Отменить · Ctrl+Z"
