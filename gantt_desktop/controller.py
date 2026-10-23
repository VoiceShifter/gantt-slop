"""Qt-facing commands, visible rows, and file operations; scheduling stays in domain.py."""
from __future__ import annotations

import csv
import json
import math
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QDate,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtWidgets import QFileDialog, QMessageBox

from .domain import Project, ScheduleError, Task, new_id
from .sample import sample_project

MONTHS = ("Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
          "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь")


def local_today() -> date:
    today = QDate.currentDate()
    return date(today.year(), today.month(), today.day())


def parse_number(value: str) -> float:
    try:
        number = float(value.replace(",", ".").replace("ч", "").strip())
    except ValueError as error:
        raise ScheduleError("Введите число, например 8 или 2,5.") from error
    if not math.isfinite(number):
        raise ScheduleError("Нужно конечное число.")
    return number


class TaskRows(QAbstractListModel):
    ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent: QObject):
        super().__init__(parent)
        self.records: list[dict] = []

    def roleNames(self) -> dict[int, QByteArray]:
        return {self.ROLE: QByteArray(b"rowData")}

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex | None = None) -> int:
        return 0 if parent is not None and parent.isValid() else len(self.records)

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if index.isValid() and 0 <= index.row() < len(self.records) and role == self.ROLE:
            return self.records[index.row()]
        return None

    def replace(self, records: list[dict]) -> None:
        self.beginResetModel()
        self.records = records
        self.endResetModel()


class Controller(QObject):
    viewChanged = Signal()
    selectionChanged = Signal()
    historyChanged = Signal()
    fileChanged = Signal()
    projectLoaded = Signal()
    toast = Signal(str)
    inspectRequested = Signal()
    focusRequested = Signal(float)
    imageRequested = Signal(str)

    def __init__(self, project: Project | None = None):
        super().__init__()
        self.project = project or sample_project()
        self._rows = TaskRows(self)
        self._selected = ""
        self._collapsed: set[str] = set()
        self._query = ""
        self._filter = "all"
        self._path: Path | None = None
        self._history: list[tuple[str, dict]] = [("", self.project.to_dict())]
        self._history_index = 0
        self._clean_index = 0
        self._origin = local_today()
        self._day_count = 180
        self.reset_range()
        self.refresh()

    model = Property(QObject, lambda self: self._rows, constant=True)
    selectedId = Property(str, lambda self: self._selected, notify=selectionChanged)
    projectName = Property(str, lambda self: self.project.name, notify=viewChanged)
    rowCount = Property(int, lambda self: len(self._rows.records), notify=viewChanged)
    dayCount = Property(int, lambda self: self._day_count, notify=viewChanged)
    canUndo = Property(bool, lambda self: self._history_index > 0, notify=historyChanged)
    canRedo = Property(bool, lambda self: self._history_index + 1 < len(self._history), notify=historyChanged)
    dirty = Property(bool, lambda self: self._history_index != self._clean_index, notify=historyChanged)
    fileName = Property(str, lambda self: self._path.name if self._path else "Без файла", notify=fileChanged)
    taskCount = Property(int, lambda self: sum(t.kind != "group" for t in self.project.tasks.values()), notify=viewChanged)

    def reset_range(self) -> None:
        start = min((self.project.span(t.id)[0].date() for t in self.project.tasks.values()), default=local_today())
        self._origin = start - timedelta(days=start.weekday() + 7)

    def refresh(self) -> None:
        project = self.project
        first = min((project.span(t.id)[0].date() for t in project.tasks.values()), default=self._origin)
        if first < self._origin:
            self._origin = first - timedelta(days=first.weekday() + 7)
        last = max((project.span(t.id)[1].date() for t in project.tasks.values()), default=self._origin)
        self._day_count = max(180, (last - self._origin).days + 60)
        matching = set()
        for task in project.tasks.values():
            text_match = self._query in f"{task.name} {task.assignee} {task.notes}".casefold()
            status_match = (self._filter == "all" or
                            (self._filter == "incomplete" and task.progress < 100) or
                            (self._filter == "complete" and task.progress >= 100) or
                            (self._filter == "overdue" and project.span(task.id)[1].date() < local_today() and task.progress < 100))
            if text_match and status_match:
                matching.add(task.id)
                if self._query and task.kind == "group":
                    matching.update(t.id for t in project.descendants(task.id))
        included = set(matching)
        for task_id in matching:
            parent = project.tasks[task_id].parent
            while parent:
                included.add(parent)
                parent = project.tasks[parent].parent
        active_filter = bool(self._query or self._filter != "all")
        records = []
        leaves = [t for t in project.tasks.values() if t.kind != "group"]
        if leaves:
            start = min(project.span(t.id)[0] for t in leaves)
            end = max(project.span(t.id)[1] for t in leaves)
            records.append({"taskId": "__total__", "rowKind": "total", "name": "",
                            "startDay": (start.date() - self._origin).days,
                            "endDay": (end.date() - self._origin).days + 1,
                            "effort": f"{sum(t.effort for t in leaves):g}ч",
                            "cost": f"{sum(t.cost for t in leaves):,.2f}"})

        def visit(parent: str, level: int, prefix: str) -> None:
            for number, task in enumerate(project.children(parent), 1):
                outline = f"{prefix}.{number}" if prefix else str(number)
                if task.id not in included:
                    continue
                record = self.record(task.id)
                record.update(level=level, outline=outline,
                              expanded=task.id not in self._collapsed or active_filter)
                records.append(record)
                if task.kind == "group" and record["expanded"]:
                    visit(task.id, level + 1, outline)
                    if not active_filter:
                        records.append({"taskId": "", "parentId": task.id, "rowKind": "add", "level": level + 1})
        visit("", 0, "")
        if not active_filter:
            records.append({"taskId": "", "parentId": "", "rowKind": "add", "level": 0})
        self._rows.replace(records)
        if self._selected not in project.tasks:
            self._selected = ""
        self.viewChanged.emit()
        self.selectionChanged.emit()

    def record(self, task_id: str) -> dict:
        task = self.project.tasks[task_id]
        start, end = self.project.span(task_id)
        leaves = self.project.leaves(task_id)
        summary = task.kind == "group"
        duration = self.project.calendar.between(start, end) if summary else task.duration
        effort = sum(t.effort for t in leaves) if summary else task.effort
        cost = sum(t.cost for t in leaves) if summary else task.cost
        weight = sum(t.duration for t in leaves)
        progress = (sum(t.progress * t.duration for t in leaves) / weight if weight else 0) if summary else task.progress
        moving = {t.id for t in leaves}
        locked = any(d.target in moving and d.source not in moving for d in self.project.dependencies)
        return {"taskId": task.id, "rowKind": "task", "parentId": task.parent, "name": task.name,
                "summary": summary, "milestone": task.kind == "milestone", "color": task.color,
                "startDay": (start.date() - self._origin).days,
                "endDay": (end.date() - self._origin).days + 1,
                "start": start.strftime("%d.%m.%Y"), "end": end.strftime("%d.%m.%Y"),
                "startTime": start.strftime("%H:%M"), "endTime": end.strftime("%H:%M"),
                "duration": duration / 60, "effortHours": effort, "costValue": cost,
                "effort": f"{effort:g}ч", "cost": f"{cost:,.2f}", "progress": progress,
                "assignee": task.assignee, "notes": task.notes, "canMove": not locked,
                "hasChildren": bool(self.project.children(task.id)), "kind": task.kind}

    @Property(dict, notify=selectionChanged)
    def selected(self):
        if self._selected not in self.project.tasks:
            return {}
        result = self.record(self._selected)
        result["dependencies"] = [{"id": d.id, "source": d.source, "target": d.target,
                                    "sourceName": self.project.tasks[d.source].name,
                                    "targetName": self.project.tasks[d.target].name,
                                    "kind": d.kind, "lag": d.lag / 60,
                                    "incoming": d.target == self._selected}
                                   for d in self.project.dependencies
                                   if self._selected in (d.source, d.target)]
        return result

    @Property(list, notify=viewChanged)
    def taskChoices(self):
        return [{"id": t.id, "name": t.name} for t in self.project.tasks.values() if t.kind != "group"]

    @Property(list, notify=viewChanged)
    def groupChoices(self):
        return [{"id": "", "name": "Без группы"}] + [
            {"id": t.id, "name": t.name} for t in self.project.tasks.values() if t.kind == "group"]

    @Property(list, notify=viewChanged)
    def days(self):
        return [{"offset": n, "number": day.day, "weekday": ("П", "В", "С", "Ч", "П", "С", "В")[day.weekday()],
                 "weekend": not self.project.calendar.working_day(day), "monday": day.weekday() == 0,
                 "week": day.isocalendar().week, "today": day == local_today(), "label": day.strftime("%d.%m.%Y")}
                for n in range(self._day_count) for day in [self._origin + timedelta(days=n)]]

    @Property(list, notify=viewChanged)
    def months(self):
        result = []
        day = self._origin
        while day < self._origin + timedelta(days=self._day_count):
            next_month = date(day.year + (day.month == 12), day.month % 12 + 1, 1)
            end = min(next_month, self._origin + timedelta(days=self._day_count))
            result.append({"offset": (day - self._origin).days, "length": (end - day).days,
                           "label": f"{MONTHS[day.month - 1]} {day.year}"})
            day = end
        return result

    @Property(list, notify=viewChanged)
    def links(self):
        rows = {r["taskId"]: (i, r) for i, r in enumerate(self._rows.records) if r["rowKind"] == "task"}

        def visible(task_id):
            while task_id not in rows and task_id in self.project.tasks:
                if self._query or self._filter != "all":
                    return ""
                task_id = self.project.tasks[task_id].parent
            return task_id if task_id in rows else ""

        result = []
        for link in self.project.dependencies:
            source, target = visible(link.source), visible(link.target)
            if not source or not target or source == target:
                continue
            si, sr = rows[source]
            ti, tr = rows[target]
            source_finish, target_finish = link.kind[0] == "F", link.kind[1] == "F"
            sx = sr["startDay"] + 0.5 if sr["milestone"] else sr["endDay"] if source_finish else sr["startDay"]
            tx = tr["startDay"] + 0.5 if tr["milestone"] else tr["endDay"] if target_finish else tr["startDay"]
            result.append({"id": link.id, "sx": sx, "tx": tx, "sourceRow": si, "targetRow": ti,
                           "sourceFinish": source_finish, "targetFinish": target_finish,
                           "label": f"{self.project.tasks[link.source].name} → {self.project.tasks[link.target].name} ({link.kind}, {link.lag / 60:g}ч)"})
        return result

    def restore(self, value: dict) -> None:
        self.project = Project.from_dict(value)
        self.refresh()

    def edit(self, label: str, action: Callable[[Project], None]) -> bool:
        before = self.project.to_dict()
        try:
            action(self.project)
            self.project.validate()
        except (ValueError, KeyError, TypeError, AttributeError, OverflowError) as error:
            self.project = Project.from_dict(before)
            self.toast.emit(str(error))
            self.selectionChanged.emit()
            return False
        after = self.project.to_dict()
        if before != after:
            if self._clean_index > self._history_index:
                self._clean_index = -1
            self._history = self._history[:self._history_index + 1] + [(label, after)]
            self._history_index += 1
            self.restore(after)
            self.historyChanged.emit()
        return True

    @Slot(str)
    def select(self, task_id):
        self._selected = task_id if task_id in self.project.tasks else ""
        self.selectionChanged.emit()

    @Slot(str)
    def toggleGroup(self, task_id):
        if task_id in self._collapsed:
            self._collapsed.remove(task_id)
        else:
            self._collapsed.add(task_id)
        self.refresh()

    @Slot(bool)
    def expandAll(self, expanded):
        self._collapsed = set() if expanded else {t.id for t in self.project.tasks.values() if t.kind == "group"}
        self.refresh()

    @Slot(str)
    def search(self, query):
        self._query = query.strip().casefold()
        self.refresh()

    @Slot(str)
    def setFilter(self, value):
        if value in {"all", "incomplete", "complete", "overdue"}:
            self._filter = value
            self.refresh()

    @Slot(str, int, result=bool)
    def moveTask(self, task_id, days):
        return self.edit("Перемещение задачи", lambda p: p.move(task_id, days))

    @Slot(str, str, int, result=bool)
    def resizeTask(self, task_id, edge, days):
        return self.edit("Изменение длительности", lambda p: p.resize(task_id, edge, days))

    @Slot(str, str, int, result="QVariantMap")
    def preview(self, task_id, mode, days):
        project = Project.from_dict(self.project.to_dict())
        try:
            if mode == "move":
                project.move(task_id, days)
            else:
                project.resize(task_id, mode, days)
            start, end = project.span(task_id)
            return {"valid": True, "startDay": (start.date() - self._origin).days,
                    "endDay": (end.date() - self._origin).days + 1,
                    "hint": f"{start:%d.%m.%Y} — {end:%d.%m.%Y}"}
        except ScheduleError as error:
            return {"valid": False, "hint": str(error)}

    @Slot(str, str, result=str)
    def addTask(self, parent, kind):
        task_id = new_id()
        start = self.project.span(parent)[0] if parent in self.project.tasks else datetime.combine(self._origin + timedelta(days=7), time(9))
        selected = self.project.tasks.get(self._selected)
        if selected and selected.parent == parent and selected.kind != "group":
            start = self.project.calendar.normalize(self.project.span(selected.id)[1])
        name = {"group": "Новая группа", "milestone": "Новая веха", "task": "Новая задача"}.get(kind, "Новая задача")

        def add(project):
            project.tasks[task_id] = Task(task_id, name, start, 480 if kind == "task" else 0,
                                          parent, kind, color="#d65ab1" if kind == "milestone" else "#50c7d6")
        if self.edit("Добавление задачи", add):
            self._collapsed.discard(parent)
            self.refresh()
            self.select(task_id)
            self.inspectRequested.emit()
            return task_id
        return ""

    @Slot(str, str, str, result=bool)
    def editField(self, task_id, field_name, value):
        def update(project):
            task = project.tasks[task_id]
            if field_name in {"name", "assignee", "notes", "color", "parent"}:
                if field_name == "parent" and value and value not in project.tasks:
                    raise ScheduleError("Неизвестная группа.")
                setattr(task, field_name, value)
            elif field_name in {"effort", "cost", "progress", "duration"}:
                number = parse_number(value)
                if task.kind == "group":
                    raise ScheduleError("Значение группы вычисляется из её задач.")
                if field_name == "duration":
                    if task.kind == "milestone" or number <= 0:
                        raise ScheduleError("Длительность обычной задачи должна быть больше нуля.")
                    task.duration = round(number * 60)
                    project.align(task_id)
                else:
                    setattr(task, field_name, number)
            elif field_name in {"start", "end", "startTime", "endTime"}:
                start, end = project.span(task_id)
                beginning = field_name.startswith("start")
                current = start if beginning else end
                if field_name.endswith("Time"):
                    parsed = time.fromisoformat(value)
                    changed = datetime.combine(current.date(), parsed)
                else:
                    parsed_date = date.fromisoformat(value if "-" in value else "-".join(reversed(value.split("."))))
                    changed = datetime.combine(parsed_date, current.time())
                if beginning:
                    if task.kind == "group":
                        if changed.time() != start.time():
                            raise ScheduleError("Начало группы изменяется по дате.")
                        project.move(task_id, (changed.date() - start.date()).days)
                        return
                    if project.incoming(task_id):
                        raise ScheduleError("Начало закреплено предшественником.")
                    task.start = project.calendar.normalize(changed)
                elif task.kind != "task":
                    raise ScheduleError("Завершение группы или вехи вычисляется.")
                else:
                    duration = project.calendar.between(start, project.calendar.normalize(changed, False))
                    if duration <= 0:
                        raise ScheduleError("Завершение должно быть позже начала.")
                    task.duration = duration
            else:
                raise ScheduleError("Неизвестное поле.")
            project.validate()
            if field_name in {"start", "end", "startTime", "endTime", "duration"}:
                project.propagate({task_id})
        return self.edit("Изменение задачи", update)

    @Slot(str)
    def deleteTask(self, task_id):
        if task_id in self.project.tasks:
            self.edit("Удаление задачи", lambda p: p.remove(task_id))

    @Slot(str, int)
    def reorder(self, task_id, direction):
        if task_id in self.project.tasks and direction in {-1, 1}:
            self.edit("Порядок задач", lambda p: p.reorder(task_id, direction))

    @Slot(str)
    def renameProject(self, name):
        self.edit("Название проекта", lambda p: setattr(p, "name", name))

    @Slot(str, str, str, str, result=bool)
    def addDependency(self, source, target, kind, lag):
        def add(project):
            minutes = round(parse_number(lag) * 60)
            project.add_link(source, target, kind, minutes)
        return self.edit("Создание зависимости", add)

    @Slot(str, str, str, str, str, result=bool)
    def updateDependency(self, link_id, source, target, kind, lag):
        def update(project):
            project.dependencies = [d for d in project.dependencies if d.id != link_id]
            project.add_link(source, target, kind, round(parse_number(lag) * 60))
        return self.edit("Изменение зависимости", update)

    @Slot(str)
    def removeDependency(self, link_id):
        self.edit("Удаление зависимости", lambda p: setattr(p, "dependencies", [d for d in p.dependencies if d.id != link_id]))

    @Slot(str, result="QVariantMap")
    def linkDetails(self, link_id):
        link = next((d for d in self.project.dependencies if d.id == link_id), None)
        return {"id": link.id, "source": link.source, "target": link.target, "kind": link.kind, "lag": link.lag / 60} if link else {}

    @Slot(str, str, float, int, result=bool)
    def linkAt(self, source, source_end, day, row):
        if not 0 <= row < len(self._rows.records):
            return False
        record = self._rows.records[row]
        if record["rowKind"] != "task" or record["summary"]:
            return False
        target_end = "F" if abs(day - record["endDay"]) < abs(day - record["startDay"]) else "S"
        return self.addDependency(source, record["taskId"], source_end + target_end, "0")

    @Slot()
    def undo(self):
        if self._history_index > 0:
            self._history_index -= 1
            self.restore(self._history[self._history_index][1])
            self.historyChanged.emit()

    @Slot()
    def redo(self):
        if self._history_index + 1 < len(self._history):
            self._history_index += 1
            self.restore(self._history[self._history_index][1])
            self.historyChanged.emit()

    @Slot(str)
    def focusTask(self, task_id):
        if task_id in self.project.tasks:
            self.focusRequested.emit(self.record(task_id)["startDay"])

    @Slot(int, result=str)
    def dateLabel(self, day):
        return (self._origin + timedelta(days=day)).strftime("%d.%m.%Y")

    def confirm_discard(self) -> bool:
        if self._history_index == self._clean_index:
            return True
        answer = QMessageBox.question(None, "Несохранённый проект", "Сохранить изменения перед закрытием?",
                                      QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Save:
            return self.save()
        return answer == QMessageBox.StandardButton.Discard

    @Slot(result=bool)
    def confirmClose(self):
        return self.confirm_discard()

    @Slot()
    def newProject(self):
        if self.confirm_discard():
            self.load_project(Project())

    @Slot()
    def loadExample(self):
        if self.confirm_discard():
            self.load_project(sample_project())

    def load_project(self, project: Project, path: Path | None = None) -> None:
        self.project = project
        self._path = path
        self._selected = ""
        self._collapsed.clear()
        self._query, self._filter = "", "all"
        self._history = [("", project.to_dict())]
        self._history_index = self._clean_index = 0
        self.historyChanged.emit()
        self.reset_range()
        self.refresh()
        self.fileChanged.emit()
        self.projectLoaded.emit()

    def load_path(self, path: Path) -> bool:
        try:
            project = Project.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as error:
            self.toast.emit(f"Не удалось открыть проект: {error}")
            return False
        self.load_project(project, path)
        return True

    @Slot()
    def openProject(self):
        if self.confirm_discard():
            path, _ = QFileDialog.getOpenFileName(None, "Открыть проект", "", "Проект Gantt (*.gantt.json *.json)")
            if path:
                self.load_path(Path(path))

    def save_path(self, path: Path) -> bool:
        temporary = path.with_name(path.name + ".tmp")
        try:
            temporary.write_text(json.dumps(self.project.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(path)
        except OSError as error:
            self.toast.emit(f"Не удалось сохранить проект: {error}")
            return False
        self._path = path
        self._clean_index = self._history_index
        self.historyChanged.emit()
        self.fileChanged.emit()
        self.toast.emit("Проект сохранён")
        return True

    @Slot(result=bool)
    def save(self):
        return self.save_path(self._path) if self._path else self.saveAs()

    @Slot(result=bool)
    def saveAs(self):
        path, _ = QFileDialog.getSaveFileName(None, "Сохранить проект", str(self._path or "project.gantt.json"), "Проект Gantt (*.gantt.json)")
        return self.save_path(Path(path)) if path else False

    @Slot()
    def exportCsv(self):
        path, _ = QFileDialog.getSaveFileName(None, "Экспорт задач", "tasks.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["Задача", "Начало", "Завершение", "Длительность (ч)", "Трудозатраты (ч)", "Стоимость", "Прогресс", "Исполнитель"])
                for task in self.project.tasks.values():
                    record = self.record(task.id)
                    writer.writerow([task.name, record["start"], record["end"], record["duration"], record["effortHours"], record["costValue"], record["progress"], task.assignee])
        except OSError as error:
            self.toast.emit(str(error))

    @Slot()
    def exportPng(self):
        path, _ = QFileDialog.getSaveFileName(None, "Экспорт текущего окна", "gantt.png", "PNG (*.png)")
        if path:
            self.imageRequested.emit(path)
