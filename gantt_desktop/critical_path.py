"""Read-only total-float analysis of the current plan in working minutes.

Summary starts/finishes are min/max events, not extra duration-bearing tasks.
Disjunctive summary endpoints are solved as a bounded union of DAG networks;
partial results are never returned when the exact search exceeds its budget.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, time
from itertools import product

from .domain import Project

_WORK_LIMIT = 100_000
Arc = tuple[str, str, int, str]


class AnalysisError(ValueError):
    """The plan cannot be analysed exactly within the supported limits."""


@dataclass(frozen=True)
class CriticalPath:
    total_float: dict[str, int]
    link_float: dict[str, int]
    finish: datetime | None

    @property
    def critical_tasks(self) -> frozenset[str]:
        return frozenset(key for key, value in self.total_float.items() if value == 0)

    @property
    def critical_links(self) -> frozenset[str]:
        return frozenset(key for key, value in self.link_float.items() if value == 0)


def analyze(project: Project) -> CriticalPath:
    if not project.tasks:
        return CriticalPath({}, {}, None)
    members = {key: sorted(project.dependency_members(key)) for key in project.tasks}
    nodes = {key: task for key, task in project.tasks.items() if members[key] == [key]}
    spans = {key: project.span(key) for key in project.tasks}
    points = sorted({point for span in spans.values() for point in span})
    if any(point.second or point.microsecond for point in points):
        raise AnalysisError("Критический путь требует дат с минутной точностью.")
    positions = {}
    previous = datetime.combine(points[0].date(), time())
    elapsed = 0
    for point in points:
        midnight = datetime.combine(point.date(), time())
        elapsed += project.calendar.between(previous, midnight)
        positions[point] = elapsed + project.calendar.between(midnight, point)
        previous = midnight
    actual = {key: positions[spans[key][0]] for key in nodes}
    duration = {key: task.duration for key, task in nodes.items()}
    finish = max(spans[key][1] for key in nodes)
    horizon = positions[finish]
    remaining = _WORK_LIMIT

    def charge(amount: int) -> None:
        nonlocal remaining
        remaining -= amount
        if remaining < 0:
            raise AnalysisError("Превышен лимит точного расчёта графика и альтернатив сводных связей. Подсветка не применяется.")

    base: list[Arc] = []
    choices: list[list[tuple[Arc, ...]]] = []
    union = {key: set() for key in nodes}
    for link in project.dependencies:
        source_time = positions[spans[link.source][link.kind[0] == "F"]]
        target_time = positions[spans[link.target][link.kind[1] == "F"]]
        if target_time < source_time + link.lag:
            raise AnalysisError(f"Текущий план нарушает зависимость {link.id}. Сначала исправьте её даты или лаг.")
        sources = [members[link.source]] if link.kind[0] == "F" else [[key] for key in members[link.source]]
        targets = [members[link.target]] if link.kind[1] == "S" else [[key] for key in members[link.target]]
        variants = []
        for source_set, target_set in product(sources, targets):
            arcs = []
            for source, target in product(source_set, target_set):
                charge(1)
                weight = link.lag + (duration[source] if link.kind[0] == "F" else 0) - (duration[target] if link.kind[1] == "F" else 0)
                arcs.append((source, target, weight, link.id))
                union[source].add(target)
            variants.append(tuple(arcs))
        if len(variants) == 1:
            base.extend(variants[0])
        else:
            choices.append(variants)
    degree = dict.fromkeys(nodes, 0)
    for targets in union.values():
        for key in targets:
            degree[key] += 1
    queue = deque(key for key in nodes if not degree[key])
    order = []
    while queue:
        key = queue.popleft()
        order.append(key)
        for target in union[key]:
            degree[target] -= 1
            if not degree[target]:
                queue.append(target)
    if len(order) != len(nodes):
        raise AnalysisError("Зависимости создают цикл; критический путь не рассчитан.")
    best = dict.fromkeys(project.tasks, -1)
    link_best = dict.fromkeys((link.id for link in project.dependencies), -1)
    # Iterators keep the exact search bounded without recursive depth limits.
    stack: list[tuple[int, Iterator[tuple[Arc, ...]], tuple[Arc, ...]]] = [(0, iter([tuple(base)]), ())]
    while stack:
        depth, variants, previous_arcs = stack[-1]
        try:
            arcs = previous_arcs + next(variants)
        except StopIteration:
            stack.pop()
            continue
        charge(len(nodes) + len(arcs))
        outgoing = {key: [] for key in nodes}
        for source, target, weight, _link_id in arcs:
            outgoing[source].append((target, weight))
        latest = {key: horizon - duration[key] for key in nodes}
        for source in reversed(order):
            for target, weight in outgoing[source]:
                latest[source] = min(latest[source], latest[target] - weight)
        if any(latest[key] < actual[key] for key in nodes):
            continue
        if depth < len(choices):
            stack.append((depth + 1, iter(choices[depth]), arcs))
            continue
        earliest = dict(actual)
        for source in order:
            for target, weight in outgoing[source]:
                earliest[target] = max(earliest[target], earliest[source] + weight)
        for key, children in members.items():
            best[key] = max(best[key], min(latest[child] - actual[child] for child in children))
        margins = {}
        for source, target, weight, link_id in arcs:
            margin = latest[target] - earliest[source] - weight
            margins[link_id] = min(margins[link_id], margin) if link_id in margins else margin
        for key, value in margins.items():
            link_best[key] = max(link_best[key], value)
    if any(value < 0 for value in best.values()):
        raise AnalysisError("Не найден допустимый вариант текущего плана; подсветка не применяется.")
    return CriticalPath(best, link_best, finish)
