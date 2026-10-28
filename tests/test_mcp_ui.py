import json
import socket

import pytest
from conftest import wait_until
from dialog_helpers import click_native, native_dialog, replace_native
from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLineEdit
from test_audit_fixes import project
from test_mcp import connect, run_async
from test_ui import item, point, undo

from gantt_desktop.domain import Project
from gantt_desktop.mcp_dialog import McpDialog


def open_mcp(window):
    window.requestActivate()
    button = next(child for child in window.findChildren(QQuickItem) if child.property("text") == "Файл ⌄")
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(button))
    action = item(window, "mcpMenuItem")
    wait_until(action.isVisible)
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(action))
    dialog = native_dialog("mcpDialog")
    assert isinstance(dialog, McpDialog)
    wait_until(dialog.isVisible)
    return dialog


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("width", [1000, 1366, 1920])
def test_native_mcp_consent_copy_stop_and_palette(gui, dark, width, tmp_path):
    c, window = gui
    assert c.theme is not None
    c.theme.setDark(dark)
    window.resize(width, 960)
    before = c.project.to_dict()
    assert c.dialogs._mcp is None and not item(window, "mcpIndicator").isVisible()
    dialog = open_mcp(window)
    assert dialog.windowHandle().transientParent() is window and not dialog.styleSheet()
    assert not dialog.writes.isChecked() and not dialog.server.active and not dialog.url.text()
    assert dialog.token.echoMode() == QLineEdit.EchoMode.Password
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    assert not c.dialogs.modalOpen and not dialog.server.active
    dialog = open_mcp(window)
    assert replace_native("mcpPort", "0") and click_native("mcpStart")
    wait_until(lambda: dialog.copy_button.isEnabled())
    server = dialog.server
    assert server.running and not server.allow_writes
    assert not dialog.port.isEnabled() and not dialog.writes.isEnabled()
    assert item(window, "mcpIndicator").isVisible()
    assert click_native("mcpCopyConfig")
    clipboard = QGuiApplication.clipboard()
    config = json.loads(clipboard.text())["mcpServers"]["gantt-desktop"]
    assert config["url"] == server.url and config["headers"]["Authorization"] == f"Bearer {server.token}"
    clipboard.clear()  # Do not leave even a test token on the isolated display clipboard.
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    assert server.running and not c.dialogs.modalOpen
    path = tmp_path / "no-token.gantt.json"
    assert c.save_path(path)
    assert server.token not in path.read_text() and c.project.to_dict() == before and not c.canUndo
    open_mcp(window)
    assert click_native("mcpStop")
    assert not server.active and not dialog.url.text() and not dialog.token.text()
    assert not item(window, "mcpIndicator").isVisible() and dialog.start_button.isEnabled()


def test_real_mcp_change_updates_gui_and_desktop_undo_restores_clean_state(gui, tmp_path):
    c, window = gui
    path = tmp_path / "manual-save.gantt.json"
    assert c.save_path(path)
    source_bytes = path.read_bytes()
    before = c.project.to_dict()
    dialog = open_mcp(window)
    assert click_native("mcpAllowWrites") and replace_native("mcpPort", "0") and click_native("mcpStart")
    wait_until(lambda: dialog.server.running)
    server = dialog.server

    async def blocked(client):
        result = await client.call_tool("edit_task", {"expected_revision": server._revision,
                                                     "task_id": "scenario", "field": "name", "value": "Blocked"})
        assert result.is_error and any("busy" in getattr(content, "text", "") for content in result.content)
        assert not (await client.call_tool("get_project")).is_error
    run_async(lambda: connect(server, blocked))
    assert c.project.to_dict() == before
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    window.contentItem().forceActiveFocus()

    async def edit(client):
        snapshot = (await client.call_tool("get_project")).structured_content
        assert snapshot is not None
        result = await client.call_tool("edit_task", {"expected_revision": snapshot["revision"],
                                                     "task_id": "scenario", "field": "name", "value": "MCP verified"})
        assert not result.is_error
    run_async(lambda: connect(server, edit))
    assert c.project.tasks["scenario"].name == "MCP verified" and c.dirty
    assert any(row.get("name") == "MCP verified" for row in c._rows.records)
    assert path.read_bytes() == source_bytes  # No automatic persistence.
    window.requestActivate()
    undo(window)
    wait_until(lambda: c.project.to_dict() == before)
    assert not c.dirty and server.running
    c.load_project(Project(name="Other"))
    assert not server.active and not item(window, "mcpIndicator").isVisible()


def test_port_failure_is_visible_and_window_disposal_stops_listener(gui):
    c, window = gui
    dialog = open_mcp(window)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        assert replace_native("mcpPort", str(sock.getsockname()[1])) and click_native("mcpStart")
        assert dialog.error.isVisible() and not dialog.server.active
        assert dialog.start_button.isEnabled()
    assert replace_native("mcpPort", "0") and click_native("mcpStart")
    wait_until(lambda: dialog.server.running)
    server = dialog.server
    c.dialogs.dispose()
    assert not server.active and server._thread is None and not server.configuration()


def test_bulk_and_text_drafts_block_mcp_changes(gui):
    c, window = gui
    dialog = open_mcp(window)
    assert click_native("mcpAllowWrites") and replace_native("mcpPort", "0") and click_native("mcpStart")
    wait_until(lambda: dialog.server.running)
    server = dialog.server
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    before = c.project.to_dict()

    async def edit(client):
        assert (await client.call_tool("edit_task", {"expected_revision": server._revision, "task_id": "scenario",
                                                    "field": "name", "value": "Must not overwrite a draft"})).is_error
    c.setBulkMode(True)
    run_async(lambda: connect(server, edit))
    c.setBulkMode(False)
    drawer = window.findChild(QObject, "bulkEditor")
    assert drawer is not None
    wait_until(lambda: not drawer.property("visible"))
    window.requestActivate()
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(item(window, "taskSearch")))
    assert window.property("editingText")
    run_async(lambda: connect(server, edit))
    assert c.project.to_dict() == before and not c.dirty


def test_rejected_mcp_dates_leave_visible_chart_and_file_unchanged(gui, tmp_path):
    c, window = gui
    c.load_project(project())
    path = tmp_path / "audit.gantt.json"
    assert c.save_path(path)
    before = c.project.to_dict()
    source_bytes = path.read_bytes()
    dialog = open_mcp(window)
    assert click_native("mcpAllowWrites") and replace_native("mcpPort", "0") and click_native("mcpStart")
    wait_until(lambda: dialog.server.running)
    server = dialog.server
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    window.contentItem().forceActiveFocus()
    bar = item(window, "taskbar-a")
    geometry = (bar.x(), bar.width())
    rows = c._rows.records.copy()

    async def journey(client):
        snapshot = (await client.call_tool("get_project")).structured_content
        assert snapshot is not None
        for field, value in [("start", "9999-12-31"), ("startTime", "09:00:30")]:
            rejected = await client.call_tool("edit_task", {"expected_revision": snapshot["revision"],
                                                            "task_id": "a", "field": field, "value": value})
            assert rejected.is_error
            assert (await client.call_tool("get_project")).structured_content == snapshot

    run_async(lambda: connect(server, journey))
    assert c.project.to_dict() == before and c._rows.records == rows
    assert (bar.x(), bar.width()) == geometry and not c.dirty and not c.canUndo
    assert path.read_bytes() == source_bytes
    server.stop()
