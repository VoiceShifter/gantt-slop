"""Task/calendar/dependency rules, independent of Qt and the presentation layer."""
from __future__ import annotations

import math
import re
from collections import deque
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from itertools import pairwise
from uuid import uuid4


class ScheduleError(ValueError):
    """An edit would violate a task, hierarchy, or dependency constraint."""


STATUS_LABELS = {"open": "Открыт", "in_progress": "В работе", "completed": "Выполнено", "closed": "Закрыт"}
PRIORITY_LABELS = {"highest": "Самый высокий", "high": "Высокий", "medium": "Средний",
                   "low": "Низкий", "lowest": "Самый низкий"}


def status_for_progress(progress: float) -> str:
    return "completed" if progress >= 100 else "in_progress" if progress > 0 else "open"


@dataclass
class CalendarException:
    id: str
    start: date
    end: date
    name: str = ""
    periods: list[list[int]] = field(default_factory=list)


@dataclass
class ResourceException:
    id: str
    start: date
    end: date
    name: str = ""
    capacity: float = 0


def validate_exceptions(items, expected_type) -> None:
    if not isinstance(items, list) or any(type(item) is not expected_type for item in items):
        raise ScheduleError("Некорректный список исключений календаря.")
    ids = set()
    for item in items:
        if not isinstance(item.id, str) or not item.id or item.id in ids or not isinstance(item.name, str):
            raise ScheduleError("Некорректный или повторяющийся идентификатор исключения.")
        ids.add(item.id)
        if type(item.start) is not date or type(item.end) is not date or item.end < item.start:
            raise ScheduleError("Начало исключения должно быть не позже завершения.")
        if isinstance(item, ResourceException):
            if isinstance(item.capacity, bool) or not isinstance(item.capacity, (int, float)) or not 0 <= item.capacity <= 24 or not math.isfinite(item.capacity):
                raise ScheduleError("Доступность исключения должна быть от 0 до 24 часов в день.")
        else:
            if not isinstance(item.periods, list) or len(item.periods) > 2:
                raise ScheduleError("Задайте не более двух рабочих интервалов в пределах дня.")
            previous = -1
            for period in item.periods:
                if not isinstance(period, list) or len(period) != 2 or any(type(m) is not int for m in period):
                    raise ScheduleError("Рабочие интервалы задаются целыми минутами.")
                start, end = period
                if not 0 <= start < end < 1440 or start < previous:
                    raise ScheduleError("Рабочие интервалы должны идти по порядку, не пересекаться и не переходить через полночь.")
                previous = end
    ordered = sorted(items, key=lambda item: item.start)
    if any(a.end >= b.start for a, b in pairwise(ordered)):
        raise ScheduleError("Диапазоны исключений пересекаются. Измените существующее исключение.")


@dataclass
class WorkCalendar:
    """Local project time: Monday–Friday, 09–13 and 14–18 (eight working hours)."""

    holidays: set[date] = field(default_factory=set)
    workdays: set[int] = field(default_factory=lambda: set(range(5)))
    exceptions: list[CalendarException] = field(default_factory=list)
    weekly_periods: dict[int, list[list[int]]] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.workdays or any(type(day) is not int or not 0 <= day <= 6 for day in self.workdays):
            raise ScheduleError("Некорректные рабочие дни проекта.")
        if any(type(day) is not date for day in self.holidays):
            raise ScheduleError("Некорректная дата праздника.")
        validate_exceptions(self.exceptions, CalendarException)
        if not isinstance(self.weekly_periods, dict) or any(type(day) is not int or not 0 <= day <= 6 for day in self.weekly_periods):
            raise ScheduleError("Некорректные недельные интервалы проекта.")
        for day, periods in self.weekly_periods.items():
            validate_exceptions([CalendarException(str(day), date.min, date.min, periods=periods)], CalendarException)
        if not any(self.weekly_periods.get(day, [[540, 780], [840, 1080]]) for day in self.workdays):
            raise ScheduleError("У проекта должен быть регулярный рабочий интервал.")

    def working_day(self, day: date) -> bool:
        return bool(self.segments(day))

    def segments(self, day: date) -> list[tuple[datetime, datetime]]:
        override = next((item for item in self.exceptions if item.start <= day <= item.end), None)
        if override is not None:
            periods = override.periods
        elif day.weekday() in self.workdays and day not in self.holidays:
            periods = self.weekly_periods.get(day.weekday(), [[540, 780], [840, 1080]])
        else:
            periods = []
        midnight = datetime.combine(day, time())
        return [(midnight + timedelta(minutes=a), midnight + timedelta(minutes=b)) for a, b in periods]

    def normalize(self, value: datetime, forward: bool = True) -> datetime:
        day = value.date()
        while True:
            spans = self.segments(day)
            if forward:
                for start, end in spans:
                    if value < start:
                        return start
                    if start <= value < end:
                        return value
                day += timedelta(days=1)
            else:
                for start, end in reversed(spans):
                    if value > end:
                        return end
                    if start < value <= end:
                        return value
                day -= timedelta(days=1)

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
        return self.normalize(value)

    def day_distance(self, start: date, end: date) -> int:
        direction = 1 if end >= start else -1
        count = 0
        while start != end:
            start += timedelta(days=direction)
            if self.working_day(start):
                count += direction
        return count


@dataclass
class Resource:
    id: str
    name: str
    capacity: float = 8
    workdays: set[int] = field(default_factory=lambda: set(range(5)))
    color: str = "#2683ed"
    exceptions: list[ResourceException] = field(default_factory=list)

    def available(self, day: date) -> float:
        override = next((item for item in self.exceptions if item.start <= day <= item.end), None)
        return override.capacity if override is not None else self.capacity if day.weekday() in self.workdays else 0

    def validate(self) -> None:
        if not self.id or not isinstance(self.name, str) or not self.name.strip():
            raise ScheduleError("Укажите имя ресурса.")
        if not math.isfinite(self.capacity) or not 0 <= self.capacity <= 24:
            raise ScheduleError("Доступность ресурса должна быть от 0 до 24 часов в день.")
        if any(type(day) is not int or not 0 <= day <= 6 for day in self.workdays):
            raise ScheduleError("Некорректные рабочие дни ресурса.")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", self.color):
            raise ScheduleError("Цвет должен иметь формат #RRGGBB.")
        validate_exceptions(self.exceptions, ResourceException)


FIELD_TYPES = {"text": "Текст", "number": "Число", "date": "Дата", "select": "Список",
               "checkbox": "Флажок", "color": "Цвет", "multi": "Мультиселект",
               "people": "Люди", "labels": "Лейблы"}


@dataclass
class CustomField:
    id: str
    name: str
    kind: str = "text"
    options: list[str] = field(default_factory=list)
    aggregate: str = ""

    def validate(self) -> None:
        if not isinstance(self.id, str) or not self.id or not isinstance(self.name, str) or not self.name.strip():
            raise ScheduleError("Укажите название поля.")
        if self.kind not in FIELD_TYPES:
            raise ScheduleError("Неизвестный тип поля.")
        if not isinstance(self.options, list) or any(not isinstance(s, str) or not s.strip() for s in self.options):
            raise ScheduleError("Опции должны иметь непустые названия.")
        if len({s.casefold() for s in self.options}) != len(self.options):
            raise ScheduleError("Названия опций не должны повторяться.")
        if self.kind in {"select", "multi"}:
            if not self.options:
                raise ScheduleError("Добавьте хотя бы одну опцию.")
        elif self.options:
            raise ScheduleError("Опции поддерживаются только списком и мультиселектом.")
        if (self.kind == "number" and self.aggregate not in {"sum", "average"}) or (self.kind != "number" and self.aggregate):
            raise ScheduleError("Выберите сумму или среднее для числового поля.")

    def normalize(self, value: object, resources: dict[str, Resource]) -> object:
        if value is None:
            return None
        if self.kind == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ScheduleError("Значение поля должно быть конечным числом.")
            try:
                number = float(value)
            except OverflowError as error:
                raise ScheduleError("Значение поля выходит за допустимый диапазон.") from error
            if not math.isfinite(number):
                raise ScheduleError("Значение поля должно быть конечным числом.")
            return number
        if self.kind == "checkbox":
            if type(value) is not bool:
                raise ScheduleError("Значение флажка должно быть Да или Нет.")
            return value
        if self.kind in {"multi", "people", "labels"}:
            if not isinstance(value, list) or any(not isinstance(s, str) or not s.strip() for s in value):
                raise ScheduleError("Ожидается список непустых значений.")
            result = list(dict.fromkeys(value))
            if self.kind == "multi":
                if any(s not in self.options for s in result):
                    raise ScheduleError("Выберите значения из опций поля.")
                result = [s for s in self.options if s in result]
            if self.kind == "people" and any(s not in resources for s in result):
                raise ScheduleError("Поле ссылается на неизвестный ресурс.")
            return result or None
        if not isinstance(value, str):
            raise ScheduleError("Ожидается текстовое значение поля.")
        if not value.strip():
            return None
        if self.kind == "select" and value not in self.options:
            raise ScheduleError("Выберите значение из опций поля.")
        if self.kind == "date":
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ScheduleError("Дата поля должна иметь формат ГГГГ-ММ-ДД.")
            return date.fromisoformat(value).isoformat()
        if self.kind == "color":
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                raise ScheduleError("Цвет должен иметь формат #RRGGBB.")
            return value.lower()
        return value

    def display(self, value: object, resources: dict[str, Resource]) -> str:
        if value is None:
            return ""
        if self.kind == "number":
            return f"{value:g}"
        if self.kind == "checkbox":
            return "Да" if value else "Нет"
        if self.kind == "date":
            return date.fromisoformat(str(value)).strftime("%d.%m.%Y")
        if isinstance(value, list):
            return ", ".join(resources[s].name if self.kind == "people" else s for s in value)
        return str(value)


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
    resource_ids: list[str] = field(default_factory=list)
    resource_shares: list[float] = field(default_factory=list)
    custom_values: dict[str, object] = field(default_factory=dict)
    deadline: date | None = None
    # assignee is a legacy-constructor/display cache; JSON stores resource IDs.

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
class TaskFilter:
    query: str = ""
    quick: str = "all"
    kinds: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)
    unassigned: bool = False
    statuses: list[str] = field(default_factory=list)
    priorities: list[str] = field(default_factory=list)
    colors: list[str] = field(default_factory=list)
    ranges: dict[str, list[str]] = field(default_factory=dict)

    @property
    def extra_active(self) -> bool:
        return bool(self.kinds or self.resources or self.unassigned or self.statuses or
                    self.priorities or self.colors or self.ranges)

    def validate(self) -> None:
        if not isinstance(self.query, str) or self.quick not in ("all", "incomplete", "complete", "overdue"):
            raise ScheduleError("Некорректный поиск или быстрый фильтр.")
        if type(self.unassigned) is not bool:
            raise ScheduleError("Некорректный фильтр неназначенных задач.")
        for values, allowed in ((self.kinds, {"task", "milestone"}), (self.resources, None),
                                (self.statuses, STATUS_LABELS), (self.priorities, PRIORITY_LABELS),
                                (self.colors, None)):
            if (not isinstance(values, list) or any(not isinstance(v, str) or not v for v in values)
                    or len(set(values)) != len(values) or allowed is not None and any(v not in allowed for v in values)):
                raise ScheduleError("Некорректные значения фильтра.")
        if any(not re.fullmatch(r"#[0-9a-fA-F]{6}", value) for value in self.colors):
            raise ScheduleError("Цвет фильтра должен иметь формат #RRGGBB.")
        if not isinstance(self.ranges, dict):
            raise ScheduleError("Некорректные диапазоны фильтра.")
        for key, bounds in self.ranges.items():
            if (key not in {"span", "start", "end"} or not isinstance(bounds, list) or len(bounds) != 2
                    or any(not isinstance(v, str) for v in bounds) or not any(bounds)):
                raise ScheduleError("Некорректный диапазон фильтра.")
            for value in bounds:
                if value and date.fromisoformat(value).isoformat() != value:
                    raise ScheduleError("Дата фильтра должна иметь формат ГГГГ-ММ-ДД.")
            if all(bounds) and bounds[0] > bounds[1]:
                raise ScheduleError("Начало диапазона фильтра должно быть не позже завершения.")

    def matches(self, project: Project, task: Task) -> bool:
        if not self.extra_active:
            return True
        if task.kind == "group":
            return False  # Summary rows are included as context for matching descendants.
        if self.kinds and task.kind not in self.kinds:
            return False
        if (self.resources or self.unassigned) and not (
                set(self.resources).intersection(task.resource_ids) or self.unassigned and not task.resource_ids):
            return False
        if self.statuses and task.status not in self.statuses or self.priorities and task.priority not in self.priorities:
            return False
        if self.colors and task.color.casefold() not in {v.casefold() for v in self.colors}:
            return False
        if self.ranges:
            start, end = (value.date().isoformat() for value in project.span(task.id))
            for key, (lower, upper) in self.ranges.items():
                first, last = (start, end) if key == "span" else (start, start) if key == "start" else (end, end)
                if lower and last < lower or upper and first > upper:
                    return False
        return True


@dataclass(frozen=True)
class BaselineEntry:
    task_id: str
    name: str
    kind: str
    start: datetime
    end: datetime


@dataclass(frozen=True)
class Baseline:
    id: str
    name: str
    created: date
    tasks: dict[str, BaselineEntry] = field(default_factory=dict)

    def validate(self) -> None:
        if not isinstance(self.id, str) or not self.id or not isinstance(self.name, str) or not self.name.strip():
            raise ScheduleError("Укажите название базового плана.")
        if type(self.created) is not date or not isinstance(self.tasks, dict):
            raise ScheduleError("Некорректный базовый план.")
        for key, entry in self.tasks.items():
            if not isinstance(entry, BaselineEntry) or not isinstance(key, str) or not key or key != entry.task_id:
                raise ScheduleError("Некорректный идентификатор элемента базового плана.")
            if not isinstance(entry.name, str) or not entry.name.strip() or entry.kind not in {"task", "group", "milestone"}:
                raise ScheduleError("Некорректный элемент базового плана.")
            if not isinstance(entry.start, datetime) or not isinstance(entry.end, datetime) or entry.start.tzinfo is not None or entry.end.tzinfo is not None:
                raise ScheduleError("Даты базового плана должны быть в локальном времени.")
            if entry.end < entry.start or entry.kind == "milestone" and entry.start != entry.end:
                raise ScheduleError("Некорректный диапазон дат базового плана.")


@dataclass
class Dependency:
    id: str
    source: str
    target: str
    kind: str = "FS"
    lag: int = 0


def new_id() -> str:
    return uuid4().hex[:12]


GroupAnchors = dict[str, tuple[datetime, datetime]]


@dataclass
class Project:
    name: str = "Новый проект"
    tasks: dict[str, Task] = field(default_factory=dict)
    dependencies: list[Dependency] = field(default_factory=list)
    calendar: WorkCalendar = field(default_factory=WorkCalendar)
    resources: dict[str, Resource] = field(default_factory=dict)
    custom_fields: dict[str, CustomField] = field(default_factory=dict)
    baselines: dict[str, Baseline] = field(default_factory=dict)
    active_baseline: str = ""
    saved_filters: dict[str, TaskFilter] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for task in self.tasks.values():
            if not task.resource_ids and task.assignee.strip():
                task.resource_ids = [self.ensure_resource(task.assignee).id]
            if task.resource_ids and len(task.resource_shares) == len(task.resource_ids) and all(
                    math.isclose(s, 1 / len(task.resource_ids)) for s in task.resource_shares):
                task.resource_shares = []
        self.sync_resource_names()

    def capture_baseline(self, name: str, created: date) -> str:
        name = name.strip()
        if not name or any(item.name.casefold() == name.casefold() for item in self.baselines.values()):
            raise ScheduleError("Укажите уникальное название базового плана.")
        key = new_id()
        entries = {task.id: BaselineEntry(task.id, task.name, task.kind, *self.span(task.id)) for task in self.tasks.values()}
        snapshot = Baseline(key, name, created, entries)
        snapshot.validate()
        self.baselines[key] = snapshot
        self.active_baseline = key
        return key

    def select_baseline(self, baseline_id: str) -> None:
        if baseline_id and baseline_id not in self.baselines:
            raise ScheduleError("Базовый план уже удалён.")
        self.active_baseline = baseline_id

    def remove_baseline(self, baseline_id: str) -> None:
        if baseline_id not in self.baselines:
            raise ScheduleError("Базовый план уже удалён.")
        del self.baselines[baseline_id]
        if self.active_baseline == baseline_id:
            self.active_baseline = ""

    def sync_resource_names(self) -> None:
        for task in self.tasks.values():
            task.assignee = ", ".join(self.resources[key].name for key in task.resource_ids if key in self.resources)

    def ensure_resource(self, name: str) -> Resource:
        name = name.strip()
        existing = next((r for r in self.resources.values() if r.name.casefold() == name.casefold()), None)
        if existing is not None:
            return existing
        resource = Resource(new_id(), name, color="#2683ed" if not self.resources else "#829da7")
        resource.validate()
        self.resources[resource.id] = resource
        return resource

    def assign_resources(self, task_id: str, ids: list[str], hours: list[float] | None = None) -> None:
        task = self.tasks[task_id]
        if task.kind == "group":
            raise ScheduleError("Назначайте ресурсы задачам, а не сводной группе.")
        if len(set(ids)) != len(ids) or any(key not in self.resources for key in ids):
            raise ScheduleError("Некорректное назначение ресурсов.")
        if hours is not None and (len(hours) != len(ids) or any(not math.isfinite(h) or h < 0 for h in hours)):
            raise ScheduleError("Трудозатраты назначений должны быть неотрицательными числами.")
        task.resource_ids = list(ids)
        task.resource_shares = []
        if hours is not None and ids:
            task.effort = sum(hours)
            if task.effort:
                shares = [h / task.effort for h in hours]
                task.resource_shares = [] if all(math.isclose(s, 1 / len(ids)) for s in shares) else shares
        self.sync_resource_names()

    def assign_name(self, task_id: str, name: str) -> None:
        task = self.tasks[task_id]
        if name == task.assignee:
            return
        self.assign_resources(task_id, [self.ensure_resource(name).id] if name.strip() else [])

    def update_resource(self, resource_id: str, name: str, capacity: float, workdays: set[int]) -> None:
        resource = self.resources[resource_id]
        candidate = Resource(resource_id, name.strip(), capacity, workdays, resource.color)
        candidate.validate()
        if any(r.id != resource_id and r.name.casefold() == candidate.name.casefold() for r in self.resources.values()):
            raise ScheduleError("Ресурс с таким именем уже существует.")
        self.resources[resource_id] = candidate
        self.sync_resource_names()

    def remove_resource(self, resource_id: str) -> None:
        del self.resources[resource_id]
        for task in self.tasks.values():
            if resource_id in task.resource_ids:
                index = task.resource_ids.index(resource_id)
                task.resource_ids.pop(index)
                if task.resource_shares:
                    task.resource_shares.pop(index)
                    total = sum(task.resource_shares)
                    shares = [s / total for s in task.resource_shares] if total else []
                    task.resource_shares = [] if shares and all(math.isclose(s, 1 / len(shares)) for s in shares) else shares
            for definition in self.custom_fields.values():
                selected = task.custom_values.get(definition.id)
                if definition.kind == "people" and isinstance(selected, list) and resource_id in selected:
                    remaining = [key for key in selected if key != resource_id]
                    if remaining:
                        task.custom_values[definition.id] = remaining
                    else:
                        task.custom_values.pop(definition.id)
        self.sync_resource_names()

    def save_custom_field(self, definition: CustomField) -> None:
        definition.validate()
        previous = self.custom_fields.get(definition.id)
        if previous is not None and previous.kind != definition.kind:
            raise ScheduleError("Тип существующего поля нельзя изменить.")
        if any(f.id != definition.id and f.name.casefold() == definition.name.casefold() for f in self.custom_fields.values()):
            raise ScheduleError("Поле с таким названием уже существует.")
        updates = {task.id: definition.normalize(task.custom_values[definition.id], self.resources)
                   for task in self.tasks.values() if definition.id in task.custom_values}
        self.custom_fields[definition.id] = definition
        for task_id, value in updates.items():
            if value is None:
                self.tasks[task_id].custom_values.pop(definition.id, None)
            else:
                self.tasks[task_id].custom_values[definition.id] = value

    def remove_custom_field(self, field_id: str) -> None:
        del self.custom_fields[field_id]
        for task in self.tasks.values():
            task.custom_values.pop(field_id, None)

    def set_custom_value(self, task_id: str, field_id: str, value: object) -> None:
        task, definition = self.tasks[task_id], self.custom_fields[field_id]
        if task.kind == "group" and definition.kind == "number":
            raise ScheduleError("Числовое значение группы вычисляется из её задач.")
        value = definition.normalize(value, self.resources)
        if value is None:
            task.custom_values.pop(field_id, None)
        else:
            task.custom_values[field_id] = value

    def custom_value(self, task_id: str, field_id: str) -> object:
        definition = self.custom_fields[field_id]
        task = self.tasks.get(task_id)
        if definition.kind != "number" or (task is not None and task.kind != "group"):
            return task.custom_values.get(field_id) if task is not None else None
        members = self.descendants(task_id) if task is not None else self.tasks.values()
        numbers = [value for t in members if t.kind != "group"
                   and isinstance(value := t.custom_values.get(field_id), (int, float))]
        if not numbers:
            return None
        divisor = len(numbers) if definition.aggregate == "average" else 1
        try:
            return math.fsum(number / divisor for number in numbers)
        except OverflowError as error:
            raise ScheduleError("Числовой итог выходит за допустимый диапазон.") from error

    def set_workdays(self, days: set[int]) -> None:
        if not days or any(type(day) is not int or not 0 <= day <= 6 for day in days):
            raise ScheduleError("Выберите хотя бы один рабочий день проекта.")
        calendar = deepcopy(self.calendar)
        calendar.workdays = days
        self.set_calendar(calendar)

    def set_calendar(self, calendar: WorkCalendar) -> None:
        calendar.validate()
        if calendar == self.calendar:
            return
        previous = self.calendar
        self.calendar = deepcopy(calendar)
        if (calendar.workdays == previous.workdays and calendar.holidays == previous.holidays and calendar.weekly_periods == previous.weekly_periods and
                [(item.start, item.end, item.periods) for item in calendar.exceptions] ==
                [(item.start, item.end, item.periods) for item in previous.exceptions]):
            return
        for task in self.tasks.values():
            if task.kind != "group" or not self.children(task.id):
                task.start = self.calendar.normalize(task.start)
        self.propagate(set(self.tasks), {}, align_changed=True)

    def children(self, task_id: str = "") -> list[Task]:
        return [task for task in self.tasks.values() if task.parent == task_id]

    def descendants(self, task_id: str) -> list[Task]:
        result: list[Task] = []
        for child in self.children(task_id):
            result.append(child)
            result.extend(self.descendants(child.id))
        return result

    def ancestors(self, task_id: str) -> set[str]:
        result = set()
        parent = self.tasks[task_id].parent
        while parent:
            result.add(parent)
            parent = self.tasks[parent].parent
        return result

    def leaves(self, task_id: str) -> list[Task]:
        task = self.tasks[task_id]
        if task.kind != "group":
            return [task]
        return [t for t in self.descendants(task_id) if t.kind != "group"]

    def dependency_members(self, task_id: str) -> set[str]:
        """Terminal tasks, including empty groups, represented by an endpoint."""
        children = self.children(task_id)
        if not children:
            return {task_id}
        return set().union(*(self.dependency_members(t.id) for t in children))

    def can_move(self, task_id: str) -> bool:
        moving = self.dependency_members(task_id)
        return not any(self.dependency_members(d.target) & moving
                       and not self.dependency_members(d.source) <= moving
                       for d in self.dependencies)

    def span(self, task_id: str) -> tuple[datetime, datetime]:
        task = self.tasks[task_id]
        children = self.children(task_id)
        if task.kind == "group" and children:
            spans = [self.span(child.id) for child in children]
            return min(a for a, _ in spans), max(b for _, b in spans)
        return task.start, self.calendar.add(task.start, task.duration)

    def incoming(self, task_id: str) -> list[Dependency]:
        return [link for link in self.dependencies if link.target == task_id]

    def endpoint_locked(self, task_id: str, end: str) -> bool:
        return any(d.kind[1] == end for d in self.incoming(task_id))

    def topological(self) -> list[str]:
        degree = dict.fromkeys(self.tasks, 0)
        outgoing: dict[str, set[str]] = {key: set() for key in self.tasks}
        # Project summary edges onto their members so hierarchy-induced cycles
        # are rejected too (e.g. Group A → Group B → a child of Group A).
        for link in self.dependencies:
            for source in self.dependency_members(link.source):
                for target in self.dependency_members(link.target):
                    if target not in outgoing[source]:
                        outgoing[source].add(target)
                        degree[target] += 1
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
        self.calendar.validate()
        filter_names = set()
        if not isinstance(self.saved_filters, dict):
            raise ScheduleError("Некорректные сохранённые фильтры.")
        for name, criteria in self.saved_filters.items():
            if (not isinstance(name, str) or not name.strip() or name != name.strip()
                    or name.casefold() in filter_names or not isinstance(criteria, TaskFilter)):
                raise ScheduleError("Укажите уникальное название фильтра.")
            criteria.validate()
            filter_names.add(name.casefold())
        baseline_names = set()
        for key, baseline in self.baselines.items():
            baseline.validate()
            if key != baseline.id or baseline.name.casefold() in baseline_names:
                raise ScheduleError("Повторяющийся идентификатор или название базового плана.")
            baseline_names.add(baseline.name.casefold())
        if not isinstance(self.active_baseline, str) or self.active_baseline and self.active_baseline not in self.baselines:
            raise ScheduleError("Неизвестный выбранный базовый план.")
        names = set()
        for resource in self.resources.values():
            resource.validate()
            if resource.name.casefold() in names:
                raise ScheduleError("Ресурс с таким именем уже существует.")
            names.add(resource.name.casefold())
        field_names = set()
        for key, definition in self.custom_fields.items():
            definition.validate()
            if key != definition.id or definition.name.casefold() in field_names:
                raise ScheduleError("Повторяющийся идентификатор или название поля.")
            field_names.add(definition.name.casefold())
        for task in self.tasks.values():
            if not isinstance(task.custom_values, dict) or any(key not in self.custom_fields for key in task.custom_values):
                raise ScheduleError("Значение ссылается на неизвестное поле.")
            for key, value in task.custom_values.items():
                definition = self.custom_fields[key]
                definition.normalize(value, self.resources)
                if task.kind == "group" and definition.kind == "number" and value is not None:
                    raise ScheduleError("Числовое значение группы вычисляется из её задач.")
            if len(set(task.resource_ids)) != len(task.resource_ids) or any(key not in self.resources for key in task.resource_ids):
                raise ScheduleError("Назначение ссылается на неизвестный ресурс.")
            if task.resource_shares and (len(task.resource_shares) != len(task.resource_ids)
                                        or any(not math.isfinite(s) or s < 0 for s in task.resource_shares)
                                        or not math.isclose(sum(task.resource_shares), 1, abs_tol=1e-9)):
                raise ScheduleError("Некорректное распределение трудозатрат.")
            if not task.id or not task.name.strip():
                raise ScheduleError("Укажите название задачи.")
            if task.kind not in {"task", "group", "milestone"}:
                raise ScheduleError("Неизвестный тип задачи.")
            if task.start.tzinfo is not None:
                raise ScheduleError("Даты проекта должны быть в локальном времени, без часового пояса.")
            if task.deadline is not None and type(task.deadline) is not date:
                raise ScheduleError("Крайний срок должен быть календарной датой.")
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
            if self.dependency_members(link.source) & self.dependency_members(link.target):
                raise ScheduleError("Нельзя связать группу с её подзадачей.")
            if (link.source, link.target) in pairs:
                raise ScheduleError("Эти задачи уже связаны.")
            pairs.add((link.source, link.target))
            if not isinstance(link.lag, int):
                raise ScheduleError("Лаг задаётся в рабочих минутах.")
        self.topological()
        for definition in self.custom_fields.values():
            if definition.kind == "number":
                self.custom_value("", definition.id)
                for task in self.tasks.values():
                    if task.kind == "group":
                        self.custom_value(task.id, definition.id)

    def required_start(self, task_id: str) -> datetime | None:
        target = self.tasks[task_id]
        duration = self.calendar.between(*self.span(task_id)) if target.kind == "group" else target.duration
        starts = []
        for link in self.incoming(task_id):
            source_span = self.span(link.source)
            anchor = source_span[1 if link.kind[0] == "F" else 0]
            anchor = self.calendar.add(anchor, link.lag)
            if link.kind[1] == "F":
                starts.append(self.calendar.add(anchor, -duration))
            else:
                starts.append(self.calendar.normalize(anchor))
        return max(starts) if starts else None

    def group_anchors(self) -> GroupAnchors:
        """Capture actual/constrained summary starts before a scheduling edit."""
        result = {}
        for task in self.tasks.values():
            required = self.required_start(task.id) if task.kind == "group" else None
            if required is not None:
                result[task.id] = self.span(task.id)[0], required
        return result

    def align(self, task_id: str, floors: dict[str, datetime] | None = None,
              previous: GroupAnchors | None = None) -> None:
        required = self.required_start(task_id)
        if required is None:
            return
        target = self.tasks[task_id]
        floors = floors if floors is not None else {}
        if target.kind != "group" or not self.children(task_id):
            target.start = max(required, floors[task_id]) if task_id in floors else required
            return
        members = self.dependency_members(task_id)
        start = self.span(task_id)[0]
        shift = self.calendar.between(start, required)
        if previous is not None and task_id in previous:
            old_start, old_required = previous[task_id]
            desired = self.calendar.add(old_start, self.calendar.between(old_required, required))
            # Preserve slack caused by other child constraints, without applying
            # a containing group's manual/automatic translation a second time.
            shift = max(shift, self.calendar.between(start, desired))
        # A nested group must not undo the containing group's translation.
        for key in members & floors.keys():
            shift = max(shift, self.calendar.between(self.tasks[key].start, floors[key]))
        for key in members:
            task = self.tasks[key]
            if shift:
                task.start = self.calendar.add(task.start, shift)
                if task.duration:
                    task.start = self.calendar.normalize(task.start)
        last = max(sorted(members), key=lambda key: self.span(key)[1])
        for link in self.incoming(task_id):
            anchor = self.calendar.add(self.span(link.source)[link.kind[0] == "F"], link.lag)
            bound = self.calendar.add(anchor, -self.tasks[last].duration) if link.kind[1] == "F" else self.calendar.normalize(anchor)
            # Start constraints apply to every child; a finish constraint needs
            # one terminal child to reach that finish. Other children may follow
            # their own predecessors in either direction on later edits.
            for key in ({last} if link.kind[1] == "F" else members):
                floors[key] = max(floors[key], bound) if key in floors else bound

    def propagate(self, changed: set[str], previous: GroupAnchors | None = None,
                  *, align_changed: bool = False) -> None:
        previous = self.group_anchors() if previous is None else previous
        members = {key: self.dependency_members(key) for key in self.tasks}
        affected = set().union(*(members[key] for key in changed))
        while True:
            before = len(affected)
            for link in self.dependencies:
                # A constrained summary moves as a block, so include siblings
                # when one member changes, as well as ordinary successors.
                if members[link.source] & affected or (self.tasks[link.target].kind == "group"
                                                       and members[link.target] & affected):
                    affected.update(members[link.target])
            if len(affected) == before:
                break
        order = {key: i for i, key in enumerate(self.topological())}

        def rank(task_id):
            depth, parent = 0, self.tasks[task_id].parent
            while parent:
                depth += 1
                parent = self.tasks[parent].parent
            return min(order[key] for key in members[task_id]), depth

        targets = {d.target for d in self.dependencies if members[d.target] & affected}
        floors: dict[str, datetime] = {}
        for task_id in sorted(targets, key=rank):
            if align_changed or task_id not in changed or self.tasks[task_id].kind == "group":
                self.align(task_id, floors, previous)

    def move(self, task_id: str, days: int) -> None:
        if not days:
            return
        moving = self.dependency_members(task_id)
        if not self.can_move(task_id):
            raise ScheduleError("Нельзя переместить: даты закреплены предшественником. Измените связь или лаг.")
        previous = self.group_anchors()
        start, _ = self.span(task_id)
        new_start = self.calendar.shift_date(start, days)
        count = self.calendar.day_distance(start.date(), new_start.date())
        for key in moving:
            task = self.tasks[key]
            task.start = self.calendar.shift_workdays(task.start, count)
        self.propagate(moving, previous)

    def resize(self, task_id: str, edge: str, days: int) -> None:
        if not days:
            return
        task = self.tasks[task_id]
        if task.kind != "task":
            raise ScheduleError("Размер меняется только у обычной задачи.")
        previous = self.group_anchors()
        start, end = self.span(task_id)
        if edge == "start":
            if self.endpoint_locked(task_id, "S"):
                raise ScheduleError("Начало закреплено предшественником.")
            start = self.calendar.shift_date(start, days)
        elif edge == "end":
            if self.endpoint_locked(task_id, "F"):
                raise ScheduleError("Завершение закреплено предшественником.")
            end = self.calendar.shift_date(end, days)
        else:
            raise ScheduleError("Неизвестная граница задачи.")
        duration = self.calendar.between(start, end)
        if duration <= 0:
            raise ScheduleError("Начало должно быть раньше завершения.")
        task.start, task.duration = start, duration
        self.propagate({task_id}, previous)

    def add_link(self, source: str, target: str, kind: str = "FS", lag: int = 0) -> str:
        previous = self.group_anchors()
        link = Dependency(new_id(), source, target, kind, lag)
        self.dependencies.append(link)
        try:
            self.validate()
        except (ValueError, KeyError):
            self.dependencies.pop()
            raise
        self.propagate({target}, previous, align_changed=True)
        return link.id

    def hierarchy_changed(self, groups: set[str], previous: GroupAnchors) -> None:
        linked_groups = {key for d in self.dependencies for key in (d.source, d.target)
                         if self.tasks[key].kind == "group"}
        changed = groups & linked_groups
        if changed:
            self.validate()
            self.propagate(changed, previous)

    def remove(self, task_id: str) -> None:
        previous, groups = self.group_anchors(), self.ancestors(task_id)
        deleting = {task_id, *(task.id for task in self.descendants(task_id))}
        self.tasks = {key: task for key, task in self.tasks.items() if key not in deleting}
        self.dependencies = [link for link in self.dependencies
                             if link.source not in deleting and link.target not in deleting]
        self.hierarchy_changed(groups, previous)

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
        """Reparent/reorder a subtree; reschedule only affected summary dependencies."""
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
        previous, groups = self.group_anchors(), self.ancestors(task_id)
        old_tasks, old_parent = self.tasks, self.tasks[task_id].parent
        self.tasks[task_id].parent = parent
        self.tasks = {key: self.tasks[key] for key in order}
        if old_parent != parent:
            try:
                self.hierarchy_changed(groups | self.ancestors(task_id), previous)
            except ScheduleError:
                self.tasks[task_id].parent = old_parent
                self.tasks = old_tasks
                raise

    def to_dict(self) -> dict:
        def exceptions(items):
            return [{**asdict(item), "start": item.start.isoformat(), "end": item.end.isoformat()} for item in items]
        tasks = []
        for task in self.tasks.values():
            item = asdict(task)
            item["start"] = task.start.isoformat(timespec="minutes")
            item["deadline"] = task.deadline.isoformat() if task.deadline is not None else None
            item.pop("assignee")
            tasks.append(item)
        resources = [{**asdict(r), "workdays": sorted(r.workdays), "exceptions": exceptions(r.exceptions)} for r in self.resources.values()]
        baselines = [{"id": item.id, "name": item.name, "created": item.created.isoformat(),
                      "tasks": [{**asdict(entry), "start": entry.start.isoformat(), "end": entry.end.isoformat()}
                                for entry in item.tasks.values()]} for item in self.baselines.values()]
        return {"version": 9, "name": self.name, "tasks": tasks, "resources": resources,
                "saved_filters": {name: asdict(criteria) for name, criteria in self.saved_filters.items()},
                "weekly_periods": deepcopy(self.calendar.weekly_periods),
                "baselines": baselines, "active_baseline": self.active_baseline,
                "calendar_exceptions": exceptions(self.calendar.exceptions),
                "custom_fields": [asdict(f) for f in self.custom_fields.values()],
                "dependencies": [asdict(link) for link in self.dependencies],
                "workdays": sorted(self.calendar.workdays),
                "holidays": sorted(day.isoformat() for day in self.calendar.holidays)}

    @classmethod
    def from_dict(cls, value: dict) -> Project:
        if value.get("version") not in (1, 2, 3, 4, 5, 6, 7, 8, 9):
            raise ScheduleError("Неподдерживаемая версия файла проекта.")
        def exceptions(items, kind):
            return [kind(**{**deepcopy(item), "start": date.fromisoformat(item["start"]), "end": date.fromisoformat(item["end"])})
                    for item in items]
        tasks = {}
        for item in value["tasks"]:
            record = {**item, "resource_ids": list(item.get("resource_ids", [])),
                      "resource_shares": list(item.get("resource_shares", [])),
                      "custom_values": deepcopy(item.get("custom_values", {}))}
            record.setdefault("status", status_for_progress(record.get("progress", 0)))
            task = Task(**{**record, "start": datetime.fromisoformat(item["start"]),
                           "deadline": date.fromisoformat(item["deadline"]) if item.get("deadline") is not None else None})
            if task.id in tasks:
                raise ScheduleError("Повторяющийся идентификатор задачи.")
            tasks[task.id] = task
        resources = {}
        for item in value.get("resources", []):
            resource = Resource(**{**item, "workdays": set(item.get("workdays", range(5))),
                                   "exceptions": exceptions(item.get("exceptions", []), ResourceException)})
            if resource.id in resources:
                raise ScheduleError("Повторяющийся идентификатор ресурса.")
            resources[resource.id] = resource
        custom_fields = {}
        for item in value.get("custom_fields", []):
            definition = CustomField(**deepcopy(item))
            if definition.id in custom_fields:
                raise ScheduleError("Повторяющийся идентификатор поля.")
            custom_fields[definition.id] = definition
        baselines = {}
        for item in value.get("baselines", []):
            entries = {}
            for entry in item["tasks"]:
                record = BaselineEntry(**{**entry, "start": datetime.fromisoformat(entry["start"]),
                                          "end": datetime.fromisoformat(entry["end"])})
                if record.task_id in entries:
                    raise ScheduleError("Повторяющийся элемент базового плана.")
                entries[record.task_id] = record
            snapshot = Baseline(item["id"], item["name"], date.fromisoformat(item["created"]), entries)
            if snapshot.id in baselines:
                raise ScheduleError("Повторяющийся идентификатор базового плана.")
            baselines[snapshot.id] = snapshot
        project = cls(value["name"], tasks,
                      [Dependency(**item) for item in value["dependencies"]],
                      WorkCalendar({date.fromisoformat(day) for day in value.get("holidays", [])},
                                   set(value.get("workdays", range(5))),
                                   exceptions(value.get("calendar_exceptions", []), CalendarException),
                                   {int(day): deepcopy(periods) for day, periods in value.get("weekly_periods", {}).items()}), resources, custom_fields,
                      baselines, value.get("active_baseline", ""),
                      {name: TaskFilter(**deepcopy(criteria)) for name, criteria in value.get("saved_filters", {}).items()})
        project.validate()
        return project
