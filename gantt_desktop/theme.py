"""One application-wide, optionally persisted palette for QML and QWidget editors."""
from PySide6.QtCore import Property, QObject, QSettings, Qt, Signal, Slot
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

LIGHT = {
    "surface": "#ffffff", "panel": "#f8f8f8", "raised": "#fafbfc", "input": "#ffffff",
    "text": "#30363b", "secondary": "#66727e", "muted": "#7b858e", "disabled": "#9b9b9b",
    "border": "#dfe4ea", "strongBorder": "#b9bec3", "grid": "#ededed",
    "hover": "#edf2f7", "selection": "#e3f2fc", "bulkSelection": "#f1f1f1",
    "selectionTint": "#18287dd1", "weekend": "#f3faff",
    "accent": "#1766cb", "accentPressed": "#1055b0", "link": "#1876dc",
    "brand": "#00564f", "summary": "#125360",
    "danger": "#b93d30", "warning": "#ad7a16", "success": "#129534",
    "loadFill": "rgba(80,199,134,0.14)", "overloadFill": "rgba(231,76,60,0.1)",
    "weekendFill": "rgba(244,184,61,0.14)",
}
DARK = {
    "surface": "#252a32", "panel": "#2d343e", "raised": "#303944", "input": "#1d232b",
    "text": "#e5e9f0", "secondary": "#b7c2d0", "muted": "#9aa8b9", "disabled": "#788596",
    "border": "#465262", "strongBorder": "#7f8c9f", "grid": "#39434f",
    "hover": "#343f4e", "selection": "#314b68", "bulkSelection": "#333c48",
    "selectionTint": "#403f8bdf", "weekend": "#26364a",
    "accent": "#3375c5", "accentPressed": "#245c9d", "link": "#8bbdff",
    "brand": "#84dcd1", "summary": "#8bd5df",
    "danger": "#ff9a91", "warning": "#e8c071", "success": "#76d79b",
    "loadFill": "rgba(80,199,134,0.18)", "overloadFill": "rgba(231,76,60,0.22)",
    "weekendFill": "rgba(244,184,61,0.2)",
}


class AppTheme(QObject):
    changed = Signal()

    def __init__(self, settings: QSettings | None = None):
        super().__init__()
        self._settings = settings
        self._dark = bool(settings.value("appearance/dark", False, type=bool)) if settings is not None else False
        self.apply_palette()

    dark = Property(bool, lambda self: self._dark, notify=changed)
    colors = Property(dict, lambda self: dict(DARK if self._dark else LIGHT), notify=changed)

    @Slot(bool)
    def setDark(self, dark: bool) -> None:
        if self._dark == dark:
            return
        self._dark = dark
        if self._settings is not None:
            self._settings.setValue("appearance/dark", dark)
            self._settings.sync()
        self.apply_palette()
        self.changed.emit()

    def apply_palette(self) -> None:
        app = QApplication.instance()
        assert isinstance(app, QApplication)
        app.styleHints().setColorScheme(Qt.ColorScheme.Dark if self._dark else Qt.ColorScheme.Light)
        colors = DARK if self._dark else LIGHT
        role = QPalette.ColorRole
        palette = QPalette()
        for key, value in {
            role.Window: colors["surface"], role.WindowText: colors["text"],
            role.Base: colors["input"], role.AlternateBase: colors["panel"], role.Text: colors["text"],
            role.Button: colors["panel"], role.ButtonText: colors["text"],
            role.Highlight: colors["accent"], role.HighlightedText: "#ffffff", role.Accent: colors["accent"],
            role.Link: colors["link"], role.LinkVisited: colors["link"],
            role.ToolTipBase: colors["raised"], role.ToolTipText: colors["text"],
            role.PlaceholderText: colors["muted"], role.BrightText: "#ffffff",
            role.Light: colors["raised"], role.Midlight: colors["panel"],
            role.Mid: colors["border"], role.Dark: colors["border"], role.Shadow: "#000000",
        }.items():
            palette.setColor(key, QColor(value))
        for key in (role.WindowText, role.Text, role.ButtonText, role.PlaceholderText):
            palette.setColor(QPalette.ColorGroup.Disabled, key, QColor(colors["disabled"]))
        app.setPalette(palette)
