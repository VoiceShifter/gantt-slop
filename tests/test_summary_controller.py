from test_summary_dependencies import at, grouped_project

from gantt_desktop.controller import Controller
from gantt_desktop.domain import Task


def test_adding_a_source_child_reschedules_and_undoes_as_one_edit(qapp):
    c = Controller(grouped_project())
    assert c.addDependency("a", "b", "FS", "0")
    c.select("a2")
    before = c.project.to_dict()
    task_id = c.addTask("a", "task")
    assert task_id
    assert c.project.tasks[task_id].start == at(4)
    assert c.project.span("b")[0] == at(5)
    c.undo()
    assert c.project.to_dict() == before


def test_adding_first_child_to_an_empty_source_updates_its_arrow(qapp):
    p = grouped_project()
    p.tasks["empty"] = Task("empty", "Empty", at(1), 0, kind="group")
    p.add_link("empty", "c")
    c = Controller(p)
    c.select("empty")
    before = c.project.to_dict()
    assert c.addTask("empty", "task")
    assert c.project.tasks["c"].start == at(2)
    c.undo()
    assert c.project.to_dict() == before


def test_parent_field_reschedules_summary_anchors_atomically(qapp):
    c = Controller(grouped_project())
    assert c.addDependency("a", "b", "SS", "0")
    before = c.project.to_dict()
    assert c.editField("a1", "parent", "")
    assert c.project.tasks["a1"].start == at(1)
    assert c.project.span("a")[0] == at(3)
    assert c.project.span("b")[0] == at(3)
    c.undo()
    assert c.project.to_dict() == before
