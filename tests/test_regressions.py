from datetime import timedelta

from gantt_desktop.controller import Controller


def test_branching_after_undo_does_not_reuse_saved_clean_index(qapp, tmp_path):
    c = Controller()
    c.moveTask("sensor", 7)
    assert c.save_path(tmp_path / "saved.gantt.json")
    c.undo()
    assert c.dirty
    c.moveTask("sensor", 1)
    assert c.dirty and not c.canRedo
    c.undo()
    assert c.dirty


def test_earlier_dates_extend_the_timeline(qapp):
    c = Controller()
    assert c.editField("scenario", "start", "17.11.2025")
    assert c.record("scenario")["startDay"] >= 0
    assert c.record("scenario")["start"] == "17.11.2025"


def test_metadata_edit_never_reschedules_a_loaded_gap(qapp):
    c = Controller()
    c.project.tasks["controller"].start += timedelta(days=7)
    dates = {key: task.start for key, task in c.project.tasks.items()}
    assert c.editField("sensor", "notes", "Only a note, not a scheduling command")
    assert {key: task.start for key, task in c.project.tasks.items()} == dates
