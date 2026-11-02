"""Desktop entry point; GUI automation uses the same launcher on an isolated display."""
import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt, QTimer, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from .controller import Controller
from .i18n import I18n, set_i18n
from .theme import AppTheme


def create_window(
    controller: Controller,
    theme: AppTheme | None = None,
    i18n: I18n | None = None,
    settings: QSettings | None = None,
) -> tuple[QQmlApplicationEngine, QQuickWindow]:
    if settings is not None:
        controller.settings = settings
    controller.theme = theme if theme is not None else AppTheme(settings)
    controller.theme.setParent(controller)
    controller.i18n = i18n if i18n is not None else I18n(settings)
    controller.i18n.setParent(controller)
    set_i18n(controller.i18n)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("controller", controller)
    engine.rootContext().setContextProperty("nativeDialogs", controller.dialogs)
    engine.rootContext().setContextProperty("appTheme", controller.theme)
    engine.rootContext().setContextProperty("i18n", controller.i18n)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parent / "qml" / "Main.qml")))
    objects = engine.rootObjects()
    if not objects or not isinstance(objects[0], QQuickWindow):
        raise RuntimeError("Could not load the Gantt desktop interface; see Qt diagnostics above.")
    controller.dialogs.attach(objects[0])
    engine.destroyed.connect(controller.dialogs.dispose)
    app = QCoreApplication.instance()
    if app is not None:
        app.aboutToQuit.connect(controller.dialogs.dispose)
    return engine, objects[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Gantt Desktop — independent Python/Qt task editor")
    parser.add_argument("project", nargs="?", type=Path, help="Open a .gantt.json project")
    parser.add_argument("--screenshot", type=Path, help="Capture the native window after rendering, then exit")
    parser.add_argument("--size", default="1600x960", help="Initial client size, e.g. 1366x768")
    args = parser.parse_args()
    try:
        width, height = (int(part) for part in args.size.lower().split("x"))
        if width < 1000 or height < 650:
            raise ValueError
    except ValueError:
        parser.error("--size must be WIDTHxHEIGHT, at least 1000x650")
    app = QApplication([sys.argv[0]])
    app.setApplicationName("Gantt Desktop")
    app.setOrganizationName("GanttDesktop")
    QQuickStyle.setStyle("Basic")
    settings = QSettings()
    controller = Controller(settings=settings)
    if args.project:
        if not controller.load_path(args.project):
            print(f"Could not open {args.project}", file=sys.stderr)
            return 2
    else:
        controller.apply_startup_project()
    try:
        engine, window = create_window(controller, AppTheme(settings), I18n(settings), settings)
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    window.resize(width, height)

    if args.screenshot:
        captured = False

        def capture() -> None:
            nonlocal captured
            if captured:
                return
            captured = True
            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            saved = window.grabWindow().save(str(args.screenshot))
            print(f"Native screenshot: {args.screenshot}" if saved else "Screenshot failed")
            window.setProperty("allowClose", True)
            app.exit(0 if saved else 2)

        window.frameSwapped.connect(capture, Qt.ConnectionType.QueuedConnection)
        QTimer.singleShot(15000, lambda: app.exit(3))
        window.update()
    result = app.exec()
    # Destroy QML objects while their Python context object is still alive.
    controller.dialogs.dispose()
    engine.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    return result
