"""Task/calendar/dependency rules, independent of Qt and the presentation layer."""
from __future__ import annotations

import math
import re
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from uuid import uuid4


class ScheduleError(ValueError):
    """An edit would violate a task, hierarchy, or dependency constraint."""


STATUS_LABELS = {"open": "Открыт", "in_progress": "В работе", "completed": "Выполнено", "closed": "Закрыт"}
PRIORITY_LABELS = {"highest": "Самый высокий", "high": "Высокий", "medium": "Средний",
                   "low": "Низкий", "lowest": "Самый низкий"}


def status_for_progress(progress: float) -> str:
    return "completed" if progress >= 100 else "in_progress" if progress > 0 else "open"


@dataclass
class WorkCalendar:
    """Local project time: Monday–Friday, 09–13 and 14–18 (eight working hours)."""

    holidays: set[date] = field(default_factory=set)

    def working_day(self, day: date) -> bool:
        return day.weekday() < 5 and day not in self.holidays

    def segments(self, day: date) -> list[tuple[datetime, datetime]]:
        if not self.working_day(day):
            return []
        return [(datetime.combine(day, time(a)), datetime.combine(day, time(b)))
                for a, b in ((9, 13), (14, 18))]

    def normalize(self, value: datetime, forward: bool = True) -> datetime:
        while True:
            spans = self.segments(value.date())
            if forward:
                for start, end in spans:
                    if value < start:
                        return start
                    if start <= value < end:
                        return value
                value = datetime.combine(value.date() + timedelta(days=1), time(9))
            else:
                for start, end in reversed(spans):
                    if value > end:
                        return end
                    if start < value <= end:
                        return value
                value = datetime.combine(value.date() - timedelta(days=1), time(18))

    def add(self, value: datetime, minutes: int) -> datetime:
        if not minutes:
            return value
        forward = minutes > 0
        remaining = abs(minutes)
        current = self.normalize(value, forward)
        while remaining:
            spans = self.segments(current.date())
            for start, end in spans if forward else reversed(spans):
                if (start <= current < end) if forward else (start < current <= end):
                    available = int(((end - current) if forward else (current - start)).total_seconds() / 60)
                    if remaining <= available:
                        return current + timedelta(minutes=remaining if forward else -remaining)
                    remaining -= available
                    current = self.normalize(end if forward else start, forward)
                    break
        return current

    def between(self, start: datetime, end: datetime) -> int:
        if end < start:
            return -self.between(end, start)
        minutes = 0
        day = start.date()
        while day <= end.date():
            for a, b in self.segments(day):
                minutes += max(0, int((min(end, b) - max(start, a)).total_seconds() / 60))
            day += timedelta(days=1)
        return minutes

    def shift_date(self, value: datetime, days: int) -> datetime:
        if not days:
            return value
        result = value + timedelta(days=days)
        direction = 1 if days > 0 else -1
        while not self.working_day(result.date()):
            result += timedelta(days=direction)
        return result

    def shift_workdays(self, value: datetime, count: int) -> datetime:
        direction = 1 if count >= 0 else -1
        for _ in range(abs(count)):
            value += timedelta(days=direction)
            while not self.working_day(value.date()):
                value += timedelta(days=direction)
        return value

    def day_distance(self, start: date, end: date) -> int:
        direction = 1 if end >= start else -1
        count = 0
        while start != end:
            start += timedelta(days=direction)
            if self.working_day(start):
                count += direction
        return count


@dataclass
class Task:
    id: str
    name: str
    start: datetime
    duration: int = 480
    parent: str = ""
    kind: str = "task"
    progress: float = 0
    assignee: str = ""
    effort: float = 0
    cost: float = 0
    color: str = "#50c7d6"
    notes: str = ""
    status: str = "open"
    priority: str = "medium"

    def set_progress(self, value: float) -> None:
        if self.kind == "group":
            raise ScheduleError("Прогресс группы вычисляется из её задач.")
        if not math.isfinite(value) or not 0 <= value <= 100:
            raise ScheduleError("Прогресс должен быть от 0 до 100%.")
        if value == self.progress:
            return
        self.progress = value
        self.status = status_for_progress(value)

    def set_status(self, value: str) -> None:
        if self.kind == "group":
            raise ScheduleError("Статус группы вычисляется из её задач.")
        if value not in STATUS_LABELS:
            raise ScheduleError("Неизвестный статус задачи.")
        if value == self.status:
            return
        self.status = value
        self.progress = {"open": 0, "in_progress": 50, "completed": 100, "closed": 100}[value]


@dataclass
class Dependency:
    id: str
    source: str
    target: str
    kind: str = "FS"
    lag: int = 0


def new_id() -> str:
    return uuid4().hex[:12]


@dataclass
class Project:
    name: str = "Новый проект"
    tasks: dict[str, Task] = field(default_factory=dict)
    dependencies: list[Dependency] = field(default_factory=list)
    calendar: WorkCalendar = field(default_factory=WorkCalendar)

    def children(self, task_id: str = "") -> list[Task]:
        return [task for task in self.tasks.values() if task.parent == task_id]

    def descendants(self, task_id: str) -> list[Task]:
        result: list[Task] = []
        for child in self.children(task_id):
            result.append(child)
            result.extend(self.descendants(child.id))
        return result

    def leaves(self, task_id: str) -> list[Task]:
        task = self.tasks[task_id]
        if task.kind != "group":
            return [task]
        return [t for t in self.descendants(task_id) if t.kind != "group"]

    def span(self, task_id: str) -> tuple[datetime, datetime]:
        task = self.tasks[task_id]
        children = self.children(task_id)
        if task.kind == "group" and children:
            spans = [self.span(child.id) for child in children]
            return min(a for a, _ in spans), max(b for _, b in spans)
        return task.start, self.calendar.add(task.start, task.duration)

    def incoming(self, task_id: str) -> list[Dependency]:
        return [link for link in self.dependencies if link.target == task_id]

    def topological(self) -> list[str]:
        degree = dict.fromkeys(self.tasks, 0)
        outgoing: dict[str, list[str]] = {key: [] for key in self.tasks}
        for link in self.dependencies:
            degree[link.target] += 1
            outgoing[link.source].append(link.target)
        queue = deque(key for key, value in degree.items() if not value)
        result = []
        while queue:
            source = queue.popleft()
            result.append(source)
            for target in outgoing[source]:
                degree[target] -= 1
                if not degree[target]:
                    queue.append(target)
        if len(result) != len(self.tasks):
            raise ScheduleError("Зависимость создаёт цикл.")
        return result

    def validate(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ScheduleError("Укажите название проекта.")
        for task in self.tasks.values():
            if not task.id or not task.name.strip():
                raise ScheduleError("Укажите название задачи.")
            if task.kind not in {"task", "group", "milestone"}:
                raise ScheduleError("Неизвестный тип задачи.")
            if task.start.tzinfo is not None:
                raise ScheduleError("Даты проекта должны быть в локальном времени, без часового пояса.")
            if not isinstance(task.duration, int) or task.duration < 0:
                raise ScheduleError("Длительность должна быть неотрицательным числом минут.")
            if task.kind == "task" and task.duration == 0:
                raise ScheduleError("У задачи должна быть длительность; для нулевой используйте веху.")
            if task.kind in {"group", "milestone"} and task.duration:
                raise ScheduleError("Длительность группы вычисляется, а длительность вехи равна нулю.")
            if not math.isfinite(task.progress) or not 0 <= task.progress <= 100:
                raise ScheduleError("Прогресс должен быть от 0 до 100%.")
            if task.status not in STATUS_LABELS or task.priority not in PRIORITY_LABELS:
                raise ScheduleError("Неизвестный статус или приоритет задачи.")
            if not all(math.isfinite(x) and x >= 0 for x in (task.effort, task.cost)):
                raise ScheduleError("Трудозатраты и стоимость должны быть неотрицательными числами.")
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", task.color):
                raise ScheduleError("Цвет должен иметь формат #RRGGBB.")
            seen = {task.id}
            parent = task.parent
            while parent:
                if parent in seen or parent not in self.tasks:
                    raise ScheduleError("Некорректная иерархия задач.")
                seen.add(parent)
                if self.tasks[parent].kind != "group":
                    raise ScheduleError("Родителем задачи должна быть группа.")
                parent = self.tasks[parent].parent
        pairs = set()
        link_ids = set()
        for link in self.dependencies:
            if link.id in link_ids:
                raise ScheduleError("Повторяющийся идентификатор зависимости.")
            link_ids.add(link.id)
            if link.source not in self.tasks or link.target not in self.tasks:
                raise ScheduleError("Зависимость ссылается на неизвестную задачу.")
            if link.source == link.target or link.kind not in {"FS", "SS", "FF", "SF"}:
                raise ScheduleError("Некорректный тип или конец зависимости.")
            if any(self.tasks[key].kind == "group" for key in (link.source, link.target)):
                raise ScheduleError("В этой версии связываются задачи и вехи, не группы.")
            if (link.source, link.target) in pairs:
                raise ScheduleError("Эти задачи уже связаны.")
            pairs.add((link.source, link.target))
            if not isinstance(link.lag, int):
                raise ScheduleError("Лаг задаётся в рабочих минутах.")
        self.topological()

    def align(self, task_id: str) -> None:
        target = self.tasks[task_id]
        starts = []
        for link in self.incoming(task_id):
            source_span = self.span(link.source)
            anchor = source_span[1 if link.kind[0] == "F" else 0]
            anchor = self.calendar.add(anchor, link.lag)
            if link.kind[1] == "F":
                starts.append(self.calendar.add(anchor, -target.duration))
            else:
                starts.append(self.calendar.normalize(anchor))
        if starts:
            target.start = max(starts)

    def propagate(self, changed: set[str]) -> None:
        affected = set(changed)
        queue = deque(changed)
        while queue:
            source = queue.popleft()
            for link in self.dependencies:
                if link.source == source and link.target not in affected:
                    affected.add(link.target)
                    queue.append(link.target)
        for task_id in self.topological():
            if task_id in affected and task_id not in changed:
                self.align(task_id)

    def move(self, task_id: str, days: int) -> None:
        if not days:
            return
        task = self.tasks[task_id]
        leaves = self.leaves(task_id)
        moving = {t.id for t in leaves}
        if any(link.target in moving and link.source not in moving for link in self.dependencies):
            raise ScheduleError("Нельзя переместить: начало закреплено предшественником. Измените связь или лаг.")
        start, _ = self.span(task_id)
        new_start = self.calendar.shift_date(start, days)
        count = self.calendar.day_distance(start.date(), new_start.date())
        if leaves:
            for leaf in leaves:
                leaf.start = self.calendar.shift_workdays(leaf.start, count)
        else:
            task.start = new_start
        self.propagate(moving)

    def resize(self, task_id: str, edge: str, days: int) -> None:
        if not days:
            return
        task = self.tasks[task_id]
        if task.kind != "task":
            raise ScheduleError("Размер меняется только у обычной задачи.")
        start, end = self.span(task_id)
        if edge == "start":
            if self.incoming(task_id):
                raise ScheduleError("Начало закреплено предшественником.")
            start = self.calendar.shift_date(start, days)
        elif edge == "end":
            end = self.calendar.shift_date(end, days)
        else:
            raise ScheduleError("Неизвестная граница задачи.")
        duration = self.calendar.between(start, end)
        if duration <= 0:
            raise ScheduleError("Начало должно быть раньше завершения.")
        task.start, task.duration = start, duration
        self.propagate({task_id})

    def add_link(self, source: str, target: str, kind: str = "FS", lag: int = 0) -> str:
        link = Dependency(new_id(), source, target, kind, lag)
        self.dependencies.append(link)
        try:
            self.validate()
        except (ValueError, KeyError):
            self.dependencies.pop()
            raise
        self.align(target)
        self.propagate({target})
        return link.id

    def remove(self, task_id: str) -> None:
        deleting = {task_id, *(task.id for task in self.descendants(task_id))}
        self.tasks = {key: task for key, task in self.tasks.items() if key not in deleting}
        self.dependencies = [link for link in self.dependencies
                             if link.source not in deleting and link.target not in deleting]

    def reorder(self, task_id: str, direction: int) -> None:
        siblings = self.children(self.tasks[task_id].parent)
        index = next(i for i, task in enumerate(siblings) if task.id == task_id)
        other = index + direction
        if not 0 <= other < len(siblings):
            return
        keys = list(self.tasks)
        a, b = keys.index(task_id), keys.index(siblings[other].id)
        keys[a], keys[b] = keys[b], keys[a]
        self.tasks = {key: self.tasks[key] for key in keys}

    def relocate(self, task_id: str, target_id: str, placement: str) -> None:
        """Reorder/reparent one subtree without modifying any leaf's schedule or links."""
        if task_id not in self.tasks or (target_id and target_id not in self.tasks):
            raise ScheduleError("Неизвестная задача для перемещения.")
        if placement not in {"before", "after", "inside", "append"}:
            raise ScheduleError("Неизвестное положение строки.")
        if task_id == target_id and placement in {"before", "after"}:
            return
        target = self.tasks.get(target_id)
        if placement in {"inside", "append"}:
            if target is not None and target.kind != "group":
                raise ScheduleError("Вложить задачу можно только в группу.")
            if target is None and placement == "inside":
                raise ScheduleError("Выберите группу для вложения.")
            parent = target_id
        else:
            if target is None:
                raise ScheduleError("Выберите строку назначения.")
            parent = target.parent
        subtree = {task_id, *(t.id for t in self.descendants(task_id))}
        if parent in subtree or target_id in subtree:
            raise ScheduleError("Нельзя переместить группу в неё саму или в её подзадачу.")
        current_siblings = [t.id for t in self.children(parent)]
        siblings = [key for key in current_siblings if key != task_id]
        sibling_index = siblings.index(target_id) + (placement == "after") if placement in {"before", "after"} else 0 if placement == "inside" else len(siblings)
        desired_siblings = siblings[:sibling_index] + [task_id] + siblings[sibling_index:]
        if self.tasks[task_id].parent == parent and desired_siblings == current_siblings:
            return
        order = [key for key in self.tasks if key != task_id]
        if placement in {"before", "after"}:
            index = order.index(target_id) + (placement == "after")
        elif placement == "inside":
            index = order.index(siblings[0]) if siblings else order.index(parent) + 1
        elif siblings:
            index = order.index(siblings[-1]) + 1
        else:
            index = order.index(parent) + 1 if parent else len(order)
        order.insert(index, task_id)
        self.tasks[task_id].parent = parent
        self.tasks = {key: self.tasks[key] for key in order}

    def to_dict(self) -> dict:
        tasks = []
        for task in self.tasks.values():
            item = asdict(task)
            item["start"] = task.start.isoformat(timespec="minutes")
            tasks.append(item)
        return {"version": 2, "name": self.name, "tasks": tasks,
                "dependencies": [asdict(link) for link in self.dependencies],
                "holidays": sorted(day.isoformat() for day in self.calendar.holidays)}

    @classmethod
    def from_dict(cls, value: dict) -> Project:
        if value.get("version") not in (1, 2):
            raise ScheduleError("Неподдерживаемая версия файла проекта.")
        tasks = {}
        for item in value["tasks"]:
            record = {**item}
            record.setdefault("status", status_for_progress(record.get("progress", 0)))
            task = Task(**{**record, "start": datetime.fromisoformat(item["start"])})
            if task.id in tasks:
                raise ScheduleError("Повторяющийся идентификатор задачи.")
            tasks[task.id] = task
        project = cls(value["name"], tasks,
                      [Dependency(**item) for item in value["dependencies"]],
                      WorkCalendar({date.fromisoformat(day) for day in value.get("holidays", [])}))
        project.validate()
        return project
