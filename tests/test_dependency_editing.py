import pytest
from conftest import wait_until
from dialog_helpers import click_native, native_dialog, replace_native, required_widget
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from test_ui import drag, item, point, undo

from gantt_desktop.controller import Controller


def test_unchanged_dependency_save_is_not_an_edit(qapp):
    c = Controller()
    before = c.project.to_dict()
    link = c.project.dependencies[0]
    assert c.updateDependency(link.id, link.source, link.target, link.kind, "0.0")
    assert c.project.to_dict() == before and not c.canUndo and not c.dirty


def test_dependency_identity_survives_edit_undo_and_redo(qapp):
    c = Controller()
    before = c.project.to_dict()
    link = c.project.dependencies[0]
    assert c.updateDependency(link.id, link.source, link.target, "FF", "-1.5")
    assert c.project.dependencies[0].id == link.id
    assert c.project.dependencies[0].lag == -90
    after = c.project.to_dict()
    c.undo()
    assert c.project.to_dict() == before
    c.redo()
    assert c.project.to_dict() == after


def test_invalid_or_stale_dependency_edits_are_atomic(qapp):
    c = Controller()
    before = c.project.to_dict()
    link = c.project.dependencies[0]
    assert not c.updateDependency(link.id, "planning", "sensor", "FS", "0")
    assert not c.updateDependency("missing", "scenario", "sensor", "FS", "0")
    assert c.project.to_dict() == before and not c.canUndo


@pytest.mark.parametrize("kind", ["FS", "SS", "FF", "SF"])
def test_relationship_locks_only_its_target_endpoint(qapp, kind):
    c = Controller()
    assert c.addDependency("scenario", "sensor", kind, "1")
    anchored_finish = kind[1] == "F"
    record = c.record("sensor")
    assert record["canResizeStart"] == anchored_finish
    assert record["canResizeEnd"] != anchored_finish
    locked = "end" if anchored_finish else "start"
    before = c.project.to_dict()
    assert not c.resizeTask("sensor", locked, 1)
    assert c.project.to_dict() == before
    if anchored_finish:
        assert not c.editField("sensor", "end", "2026-01-30")
        assert not c.editField("sensor", "endTime", "17:00")
        assert c.project.to_dict() == before
        finish = c.project.span("sensor")[1]
        assert c.resizeTask("sensor", "start", 1)
        assert c.project.span("sensor")[1] == finish


def _open_first_arrow(c, window):
    canvas = item(window, "chartCanvas")

    def paths():
        value = canvas.property("paths")
        return value.toVariant() if hasattr(value, "toVariant") else value

    link_id = c.project.dependencies[0].id
    logical = next(d for d in c.links if d["id"] == link_id)
    scale = item(window, "ganttView").property("pixelsPerDay")
    expected_x, expected_target = logical["sx"] * scale, logical["tx"] * scale
    wait_until(lambda: any(p["id"] == link_id and abs(p["points"][0][0] - expected_x) < 0.1
                           and abs(p["points"][-1][0] - expected_target) < 0.1 for p in paths()))
    path = next(p for p in paths() if p["id"] == link_id)
    a, b = path["points"][2:4]
    assert a[1] == b[1]
    location = canvas.mapToScene(QPointF((a[0] + b[0]) / 2, a[1])).toPoint()
    QTest.mouseMove(window, QPoint(1850, 900))
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, location)
    dialog = native_dialog("dependencyDialog")
    wait_until(dialog.isVisible)
    return dialog


def _click(window, name):
    if click_native(name):
        return
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point(item(window, name)))


def _replace_text(window, name, text):
    if replace_native(name, text):
        return
    _click(window, name)
    QTest.keyClick(window, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    for character in text:
        QTest.keyClick(window, Qt.Key(ord(character.upper())))


def test_real_arrow_click_edits_type_lag_and_can_be_deleted(gui):
    c, window = gui
    before = c.project.to_dict()
    original_id = c.project.dependencies[0].id
    dialog = _open_first_arrow(c, window)
    assert item(window, "ganttView").property("activeLinkId") == original_id
    kind = required_widget("dependencyKind")
    kind.setFocus()
    QTest.keyClick(kind, Qt.Key.Key_Home)
    QTest.keyClick(kind, Qt.Key.Key_Down)
    QTest.keyClick(kind, Qt.Key.Key_Down)
    _replace_text(window, "dependencyLag", "1.5")
    assert c.project.to_dict() == before
    _click(window, "saveDependency")
    wait_until(lambda: not dialog.property("visible"))
    link = c.project.dependencies[0]
    assert (link.id, link.kind, link.lag) == (original_id, "FF", 90)
    after_edit = c.project.to_dict()
    _open_first_arrow(c, window)
    _click(window, "deleteDependency")
    wait_until(lambda: all(d.id != original_id for d in c.project.dependencies))
    undo(window)
    wait_until(lambda: c.project.to_dict() == after_edit)
    undo(window)
    wait_until(lambda: c.project.to_dict() == before)


def test_cancelling_arrow_editor_discards_draft(gui):
    c, window = gui
    before = c.project.to_dict()
    dialog = _open_first_arrow(c, window)
    _replace_text(window, "dependencyLag", "-2")
    _click(window, "cancelDependency")
    wait_until(lambda: not dialog.property("visible"))
    assert not item(window, "ganttView").property("activeLinkId")
    assert c.project.to_dict() == before and not c.canUndo


def test_finish_anchored_task_resizes_from_its_start_in_the_real_ui(gui):
    c, window = gui
    assert c.addDependency("scenario", "sensor", "FF", "1")
    finish = c.project.span("sensor")[1]
    before = c.project.to_dict()
    handle = item(window, "resize-start-sensor")
    start = point(handle)
    drag(window, start, start + QPoint(10, 0))
    wait_until(lambda: c.project.to_dict() != before)
    assert c.project.span("sensor")[1] == finish
    assert c.project.tasks["sensor"].duration < 1440
    undo(window)
    wait_until(lambda: c.project.to_dict() == before)


def test_escape_discards_the_arrow_editor_draft(gui):
    c, window = gui
    before = c.project.to_dict()
    dialog = _open_first_arrow(c, window)
    _replace_text(window, "dependencyLag", "-2")
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    wait_until(lambda: not dialog.property("visible"))
    assert c.project.to_dict() == before and not c.canUndo


def test_arrow_editor_blocks_background_undo_and_task_delete(gui):
    c, window = gui
    assert c.moveTask("sensor", 7)
    c.select("sensor")
    before = c.project.to_dict()
    dialog = _open_first_arrow(c, window)
    _click(window, "dependencyKind")
    popup = QApplication.activePopupWidget()
    if popup is not None:
        QTest.keyClick(popup, Qt.Key.Key_Escape)
    assert dialog.isVisible()
    QTest.keyClick(window, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(window, Qt.Key.Key_Delete)
    QTest.qWait(20)
    assert c.project.to_dict() == before
    assert not any(w.objectName() == "deleteDialog" and w.isVisible() for w in QApplication.topLevelWidgets())
    _click(window, "cancelDependency")
