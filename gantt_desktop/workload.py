"""Effort allocation and availability reporting, independent of Qt."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from .domain import Project


def workload_rows(project: Project, origin: date, count: int) -> list[dict]:
    dates = [origin + timedelta(days=i) for i in range(count)]
    rows = {}
    for resource in project.resources.values():
        rows[resource.id] = {
            "id": resource.id, "name": resource.name, "color": resource.color,
            "capacity": resource.capacity, "workdays": sorted(resource.workdays),
            "tasks": [], "days": [
                {"date": day.isoformat(), "offset": i, "hours": 0.0,
                 "capacity": resource.available(day) if day not in project.calendar.holidays else 0,
                 "weekend": day.weekday() >= 5, "tasks": []}
                for i, day in enumerate(dates)],
        }
    for task in project.tasks.values():
        if task.kind == "group" or not task.resource_ids:
            continue
        start, end = project.span(task.id)
        portions = []
        day = start.date()
        while day <= end.date():
            minutes = project.calendar.between(max(start, datetime.combine(day, time())),
                                               min(end, datetime.combine(day + timedelta(days=1), time())))
            if minutes > 0 or task.kind == "milestone":
                portions.append((day, minutes))
            day += timedelta(days=1)
        total = sum(minutes for _, minutes in portions)
        for index, resource_id in enumerate(task.resource_ids):
            row = rows[resource_id]
            row["tasks"].append({"id": task.id, "name": task.name, "color": task.color,
                                 "startDay": (start.date() - origin).days,
                                 "endDay": (end.date() - origin).days + 1,
                                 "milestone": task.kind == "milestone", "progress": task.progress})
            share = task.resource_shares[index] if task.resource_shares else 1 / len(task.resource_ids)
            effort = task.effort * share
            remaining = effort
            for i, (day, minutes) in enumerate(portions):
                hours = remaining if i == len(portions) - 1 else min(remaining, round(effort * minutes / total, 2))
                remaining = max(0, remaining - hours)
                offset = (day - origin).days
                if 0 <= offset < count:
                    cell = row["days"][offset]
                    cell["hours"] += hours
                    cell["tasks"].append({"id": task.id, "name": task.name, "hours": hours})
    for row in rows.values():
        for cell in row["days"]:
            cell["count"] = len(cell["tasks"])
            cell["overloaded"] = cell["hours"] > cell["capacity"] + 1e-8
            cell["weekendWork"] = cell["weekend"] and cell["hours"] > 1e-8
            cell["nonworking"] = cell["capacity"] == 0 and cell["hours"] > 1e-8
        row["hours"] = sum(d["hours"] for d in row["days"])
        row["warningDays"] = sum(d["overloaded"] or d["weekendWork"] for d in row["days"])
    return list(rows.values())
