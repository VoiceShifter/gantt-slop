import gc
import os
import sys
import time

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, qInstallMessageHandler
from PySide6.QtGui import QFont
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from gantt_desktop.app import create_window
from gantt_desktop.controller import Controller


@pytest.fixture(scope="session")
def qapp():
    os.environ.setdefault("QT_QUICK_BACKEND", "software")
    if not os.environ.get("DISPLAY") and os.name != "nt" and sys.platform != "darwin":
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance()
    if instance is None:
        app = QApplication([])
    else:
        assert isinstance(instance, QApplication)
        app = instance
    app.setFont(QFont("Arial", 9))
    QQuickStyle.setStyle("Basic")
    yield app
    # QML wrapper cycles must be collected before QApplication is destroyed.
    gc.collect()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    gc.collect()


def wait_until(condition, timeout=3):
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("Qt condition did not become true before timeout")
        QTest.qWait(10)


@pytest.fixture
def gui(qapp):
    messages = []
    previous = qInstallMessageHandler(lambda _kind, _context, message: messages.append(message))
    controller = Controller()
    engine, window = create_window(controller)
    window.resize(1920, 960)
    window.setProperty("allowClose", True)
    assert QTest.qWaitForWindowExposed(window, 3000)
    window.requestActivate()
    qapp.processEvents()
    yield controller, window
    window.close()
    engine.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()
    qInstallMessageHandler(previous)
    errors = [m for m in messages if any(word in m for word in (
        "TypeError", "ReferenceError", "Binding loop", "Unable to assign", "is not a function", "Cannot anchor"))]
    assert not errors, "\n".join(dict.fromkeys(errors))
