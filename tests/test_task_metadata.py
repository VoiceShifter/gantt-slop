from datetime import datetime

import pytest

from gantt_desktop.domain import Project, ScheduleError, Task
from gantt_desktop.sample import sample_project

START = datetime.fromisoformat("2026-06-01T09:00")


@pytest.mark.parametrize("status,progress", [("open", 0), ("in_progress", 50), ("completed", 100), ("closed", 100)])
def test_explicit_status_sets_reference_progress(status, progress):
    task = Task("a", "A", START, duration=960, effort=3)
    before = (task.start, task.duration, task.effort, task.cost, task.color)
    task.set_status(status)
    assert task.status == status and task.progress == progress
    assert (task.start, task.duration, task.effort, task.cost, task.color) == before


@pytest.mark.parametrize("value,status", [(0, "open"), (1, "in_progress"), (25, "in_progress"), (99, "in_progress"), (100, "completed")])
def test_manual_progress_updates_status_without_rounding(value, status):
    task = Task("a", "A", START)
    task.set_progress(value)
    assert (task.status, task.progress) == (status, value)


def test_summary_metadata_is_derived():
    task = Task("g", "Group", START, duration=0, kind="group")
    with pytest.raises(ScheduleError):
        task.set_status("completed")
    with pytest.raises(ScheduleError):
        task.set_progress(25)
    assert task.progress == 0 and task.status == "open"


def test_invalid_status_and_progress_are_atomic():
    task = Task("a", "A", START)
    with pytest.raises(ScheduleError):
        task.set_status("unknown")
    with pytest.raises(ScheduleError):
        task.set_progress(101)
    assert task.progress == 0 and task.status == "open"


def test_old_files_derive_missing_status_and_default_priority():
    data = sample_project().to_dict()
    data["version"] = 1
    for record in data["tasks"]:
        del record["status"]
        del record["priority"]
        if record["id"] == "sensor":
            record["progress"] = 25
    project = Project.from_dict(data)
    assert project.tasks["sensor"].status == "in_progress"
    assert project.tasks["sensor"].progress == 25
    assert project.tasks["sensor"].priority == "medium"


def test_metadata_round_trip_preserves_explicit_values():
    project = sample_project()
    project.tasks["sensor"].set_status("closed")
    project.tasks["sensor"].priority = "highest"
    data = project.to_dict()
    assert Project.from_dict(data).to_dict() == data
