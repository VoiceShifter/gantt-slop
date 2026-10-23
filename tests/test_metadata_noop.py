from gantt_desktop.controller import Controller


def test_unchanged_completion_does_not_reopen_closed_task(qapp):
    c = Controller()
    assert c.editField("sensor", "status", "closed")
    before = c.project.to_dict()
    assert c.editField("sensor", "progress", "100")
    assert c.project.to_dict() == before
    c.undo()
    assert c.project.tasks["sensor"].status == "open" and not c.canUndo


def test_unchanged_status_preserves_partial_progress_in_single_and_bulk_edits(qapp):
    c = Controller()
    assert c.editField("sensor", "progress", "25")
    before = c.project.to_dict()
    assert c.editField("sensor", "status", "in_progress")
    c.setBulkMode(True)
    c.toggleChecked("sensor")
    assert c.applyBulk({"status": "in_progress"})
    assert c.project.to_dict() == before
    c.undo()
    assert c.project.tasks["sensor"].progress == 0 and not c.canUndo
