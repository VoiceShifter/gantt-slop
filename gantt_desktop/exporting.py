"""Snapshot-based diagram export: no window capture and no project mutations."""
from __future__ import annotations

import math
import os
import tempfile
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QByteArray, QDate, QMarginsF, QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QImageWriter,
    QPageLayout,
    QPageSize,
    QPainter,
    QPainterPath,
    QPdfWriter,
    QPen,
    QPolygonF,
)

from . import ganttpro_csv
from .critical_path import CriticalPath, analyze
from .domain import Baseline, Project
from .workload import workload_rows
from .xml_fields import export_fields

if TYPE_CHECKING:
    from .controller import Controller

SCALES = {"Дни подробно": 52, "Дни": 26, "Недели": 10, "Месяцы": 4, "Кварталы": 2, "Годы": 1}
PAPERS = {name: getattr(QPageSize.PageSizeId, name) for name in
          ("A4", "A3", "A2", "A1", "A0", "Letter", "Legal", "Tabloid", "Ledger")}
MONTHS = ("Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек")
STOCK_COLUMNS = {"wbs": ("№", 64), "name": ("Задача", 300), "assignee": ("Исполнитель", 120),
                 "start": ("Начало", 110), "startTime": ("Время начала", 90),
                 "end": ("Завершение", 110), "endTime": ("Время завершения", 90), "deadline": ("Крайний срок", 120),
                 "duration": ("Длительность", 100), "effort": ("Трудозатраты", 100),
                 "cost": ("Стоимость", 110), "progress": ("Прогресс", 90), "status": ("Статус", 120),
                 "priority": ("Приоритет", 130), "predecessors": ("Предшественники", 180), "notes": ("Описание", 260),
                 "baselineStart": ("Базовое начало", 160), "baselineEnd": ("Базовое завершение", 180),
                 "startVariance": ("Δ начала, кал. ч", 150), "endVariance": ("Δ завершения, кал. ч", 180)}


GANTTPRO_COLUMNS = ganttpro_csv.COLUMNS


class ExportError(ValueError):
    pass


@dataclass(frozen=True)
class ExportOptions:
    format: str = "pdf"
    scope: str = "all"
    columns: tuple[str, ...] = ("wbs", "name", "assignee", "effort", "cost")
    content: str = "both"
    pixels_per_day: float = 10
    start: date | None = None
    end: date | None = None
    paper: str = "Full"
    landscape: bool = True
    labels: str = "inside"
    links: bool = True
    today: bool = True
    workload: bool = False
    strike_closed: bool = True
    fade_closed: bool = True
    critical: bool = False
    baseline: bool = False
    site_import: bool = False
    table_headers: bool = True

    def validate(self) -> None:
        if self.format not in {"pdf", "png", "xlsx", "xml", "csv", "ganttpro_csv", "ganttpro_xlsx"} or self.scope not in {"all", "visible"}:
            raise ExportError("Некорректный формат или состав задач.")
        if self.content not in {"both", "table", "chart"} or self.labels not in {"inside", "right", "none"}:
            raise ExportError("Некорректные настройки отображения.")
        if self.paper != "Full" and self.paper not in PAPERS:
            raise ExportError("Неизвестный размер бумаги.")
        if not math.isfinite(self.pixels_per_day) or not 1 <= self.pixels_per_day <= 100:
            raise ExportError("Выберите масштаб от 1 до 100 пикселей на день.")
        if self.start and self.end and self.start > self.end:
            raise ExportError("Начало диапазона должно быть не позже завершения.")
        if self.content != "chart" and not self.columns:
            raise ExportError("Выберите хотя бы одно поле таблицы.")
        if len(set(self.columns)) != len(self.columns):
            raise ExportError("Поля экспорта не должны повторяться.")


@dataclass
class ExportSource:
    project: Project
    rows: list[dict]
    visible_ids: frozenset[str]
    columns: dict[str, dict]
    default_columns: tuple[str, ...]
    today: date

    @classmethod
    def capture(cls, controller: Controller, context: dict | None = None) -> ExportSource:
        context = context or {}
        project = Project.from_dict(controller.project.to_dict())
        rows: list[dict] = []

        def visit(parent: str, level: int, prefix: str) -> None:
            for index, task in enumerate(project.children(parent), 1):
                outline = f"{prefix}.{index}" if prefix else str(index)
                row = deepcopy(controller.record(task.id))
                row.update(level=level, outline=outline, startValue=project.span(task.id)[0], endValue=project.span(task.id)[1])
                rows.append(row)
                if task.kind == "group":
                    visit(task.id, level + 1, outline)
        visit("", 0, "")
        visible = frozenset(r["taskId"] for r in controller._rows.records if r["rowKind"] == "task")
        columns = {key: {"key": key, "title": title, "width": width} for key, (title, width) in STOCK_COLUMNS.items()}
        for definition in project.custom_fields.values():
            key = "custom:" + definition.id
            columns[key] = {"key": key, "title": definition.name, "width": 160}
        defaults = ["wbs"]
        for item in context.get("columns", []):
            key = item.get("key")
            if key in columns and key not in defaults:
                defaults.append(key)
                width = item.get("width", columns[key]["width"])
                if isinstance(width, bool) or not isinstance(width, (int, float)) or not math.isfinite(width) or width <= 0:
                    raise ExportError("Некорректная ширина поля.")
                columns[key]["width"] = max(64, width - 64 if key == "name" else width)
        if len(defaults) == 1:
            defaults = ["wbs", "name", "assignee", "effort", "cost"]
        qdate = QDate.currentDate()
        return cls(project, rows, visible, columns, tuple(defaults), date(qdate.year(), qdate.month(), qdate.day()))

    def selected_rows(self, scope: str) -> list[dict]:
        return [r for r in self.rows if scope == "all" or r["taskId"] in self.visible_ids]

    def value(self, row: dict, key: str) -> object:
        if "ganttproValues" in row and key in ganttpro_csv.SITE_COLUMNS[:len(row["ganttproValues"])]:
            return row["ganttproValues"][ganttpro_csv.SITE_COLUMNS.index(key)]
        if key.startswith("custom:"):
            return row["customValues"].get(key[7:])
        if key == "wbs":
            return row.get("outline", "")
        if key in {"start", "end"}:
            value = row.get(key + "Value")
            return value.date() if isinstance(value, datetime) else None
        if key == "deadline":
            return self.project.tasks[row["taskId"]].deadline
        if key in {"baselineStart", "baselineEnd", "startVariance", "endVariance"}:
            baseline = self.project.baselines.get(self.project.active_baseline)
            entry = baseline.tasks.get(row["taskId"]) if baseline is not None else None
            if entry is None:
                return None
            if key == "baselineStart":
                return entry.start
            if key == "baselineEnd":
                return entry.end
            return (row["startValue"]-entry.start).total_seconds()/3600 if key == "startVariance" else (row["endValue"]-entry.end).total_seconds()/3600
        if key in {"duration", "effort", "cost"}:
            return row.get({"duration": "duration", "effort": "effortHours", "cost": "costValue"}[key])
        if key in {"status", "priority"}:
            return row.get(key + "Text", "")
        if key == "predecessors":
            outlines = {r["taskId"]: r["outline"] for r in self.rows}
            return ", ".join(outlines[d.source] + " " + d.kind + (f" {d.lag / 60:+g}ч" if d.lag else "")
                             for d in self.project.dependencies if d.target == row["taskId"])
        return row.get(key, "")

    def text(self, row: dict, key: str) -> str:
        value = self.value(row, key)
        if "ganttproValues" in row:
            return str(value)
        if key.startswith("custom:"):
            return self.project.custom_fields[key[7:]].display(value, self.project.resources)
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.strftime("%d.%m.%Y %H:%M")
        if isinstance(value, date):
            return f"{value.day:02}.{value.month:02}.{value.year:04}"
        if key in {"startVariance", "endVariance"}:
            return f"{value:+g}" if value else "0"
        if key == "cost":
            return f"{value:,.2f}"
        if key in {"duration", "effort"}:
            return f"{value:g}ч"
        if key == "progress":
            return f"{value:.0f}%"
        return str(value)


@dataclass
class ExportDocument:
    source: ExportSource
    options: ExportOptions
    rows: list[dict] = field(init=False)
    columns: list[dict] = field(init=False)
    resources: list[dict] = field(init=False)
    start: date = field(init=False)
    end: date = field(init=False)
    dates: list[date] = field(init=False)
    left: float = field(init=False)
    width: float = field(init=False)
    height: float = field(init=False)
    body_rows: int = field(init=False)
    analysis: CriticalPath | None = field(init=False, default=None)
    reference: Baseline | None = field(init=False, default=None)
    header: int = 80
    row_height: int = 30

    def __post_init__(self) -> None:
        task_table = self.options.format in {"ganttpro_csv", "ganttpro_xlsx"}
        keys = ganttpro_csv.SITE_COLUMNS if self.options.site_import else GANTTPRO_COLUMNS
        if task_table:
            self.options = replace(self.options, scope="all", columns=keys, content="table", start=None, end=None,
                                   workload=False, critical=False, baseline=False,
                                   table_headers=self.options.table_headers if self.options.site_import else True)
        if self.options.format == "xml":
            self.options = replace(self.options, scope="all", content="table", start=None, end=None,
                                   workload=False, critical=False, baseline=False)
            try:
                export_fields(self.source.project)
            except ValueError as error:
                raise ExportError(str(error)) from error
        self.options.validate()
        if not task_table and any(key not in self.source.columns for key in self.options.columns):
            raise ExportError("Неизвестное поле экспорта.")
        self.rows = self.source.selected_rows(self.options.scope)
        if task_table:
            values = ganttpro_csv.table_rows(self.source.project, self.rows)
            if self.options.site_import:
                values = ganttpro_csv.site_rows(values)
            self.rows = [dict(row, ganttproValues=value) for row, value in zip(self.rows, values, strict=True)]
        if not self.rows:
            raise ExportError("Нет задач для экспорта. Проверьте фильтр.")
        if self.options.critical:
            self.analysis = analyze(self.source.project)
        self.reference = self.source.project.baselines.get(self.source.project.active_baseline)
        if self.options.baseline and self.reference is None:
            raise ExportError("Выберите базовый план перед экспортом сравнения.")
        if task_table:
            headers = ganttpro_csv.SITE_HEADERS if self.options.site_import else ganttpro_csv.HEADERS
            widths = ganttpro_csv.SITE_WIDTHS if self.options.site_import else ganttpro_csv.WIDTHS
            self.columns = [{"key": key, "title": title, "width": width}
                            for key, title, width in zip(keys, headers, widths, strict=True)]
        else:
            self.columns = [self.source.columns[key] for key in self.options.columns] if self.options.content != "chart" else []
        first = min(r["startValue"].date() for r in self.rows)
        last = max(r["endValue"].date() for r in self.rows)
        if self.options.baseline and self.reference is not None:
            entries = [self.reference.tasks[r["taskId"]] for r in self.rows if r["taskId"] in self.reference.tasks]
            first = min([first] + [entry.start.date() for entry in entries])
            last = max([last] + [entry.end.date() for entry in entries])
        self.start = self.options.start or (first - timedelta(days=1) if first > date.min else first)
        self.end = self.options.end or (last + timedelta(days=1) if last < date.max else last)
        if self.start > self.end:
            raise ExportError("Начало диапазона должно быть не позже завершения.")
        count = (self.end - self.start).days + 1
        if count > 36600:
            raise ExportError("Диапазон экспорта не должен превышать 100 лет.")
        self.dates = [self.start + timedelta(days=i) for i in range(count)]
        include_load = self.options.workload and self.options.content != "table"
        self.resources = workload_rows(self.source.project, self.start, count) if include_load else []
        self.left = sum(c["width"] for c in self.columns)
        if include_load:
            self.left = max(200, self.left)
        chart = count * self.options.pixels_per_day if self.options.content != "table" else 0
        self.width = max(240, self.left + chart + (180 if chart and self.options.labels == "right" else 0))
        self.body_rows = len(self.rows) + (1 + len(self.resources) if self.resources else 0)
        self.height = self.header + self.body_rows * self.row_height

    def _text(self, painter: QPainter, rect: QRectF, text: str, *, bold: bool = False,
              color: str = "#30363b", align=Qt.AlignmentFlag.AlignLeft, strike: bool = False) -> None:
        painter.save()
        painter.setClipRect(rect)
        font = QFont("Arial", 9)
        font.setBold(bold)
        font.setStrikeOut(strike)
        painter.setFont(font)
        painter.setPen(QColor(color))
        content = rect.adjusted(6, 0, -6, 0)
        label = painter.fontMetrics().elidedText(text.replace("\n", " "), Qt.TextElideMode.ElideRight, max(0, int(content.width())))
        painter.drawText(content, align | Qt.AlignmentFlag.AlignVCenter, label)
        painter.restore()

    def _periods(self, major: bool) -> list[tuple[int, int, str]]:
        ppd = self.options.pixels_per_day
        result: list[tuple[int, int, str]] = []
        previous = None
        for i, day in enumerate(self.dates):
            if major:
                key = (day.year, day.month) if ppd >= 6 else day.year
                label = f"{MONTHS[day.month-1]} {day.year}" if ppd >= 6 else str(day.year)
            elif ppd >= 18:
                key, label = day, f"{day.day:02}"
            elif ppd >= 6:
                key = day.isocalendar()[:2]
                label = f"{day.day:02} ({day.isocalendar().week}н)"
            elif ppd >= 3:
                key, label = (day.year, day.month), MONTHS[day.month-1]
            elif ppd >= 1.5:
                key, label = (day.year, (day.month-1)//3), f"{(day.month-1)//3+1} кв."
            else:
                key, label = day.year, str(day.year)
            if key != previous:
                result.append((i, 1, label))
                previous = key
            else:
                offset, length, old = result[-1]
                result[-1] = (offset, length + 1, old)
        return result

    def paint(self, painter: QPainter, first: int = 0, count: int | None = None, page: str = "") -> None:
        count = self.body_rows - first if count is None else count
        ppd = self.options.pixels_per_day
        body_height = count * self.row_height
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(QRectF(0, 0, self.width, self.header + body_height + 22), QColor("white"))
        title = self.source.project.name
        if self.reference is not None and (self.options.baseline or any(c["key"] in {"baselineStart", "baselineEnd", "startVariance", "endVariance"} for c in self.columns)):
            title += " · Базовый план: " + self.reference.name
        self._text(painter, QRectF(0, 0, self.width, 34), title +
                   f" · {self.start:%d.%m.%Y} — {self.end:%d.%m.%Y}", bold=True)
        x = 0.0
        for column in self.columns:
            rect = QRectF(x, 36, column["width"], 44)
            painter.fillRect(rect, QColor("#f8f8f8"))
            painter.setPen(QColor("#dfe4ea"))
            painter.drawRect(rect)
            self._text(painter, rect, column["title"], align=Qt.AlignmentFlag.AlignHCenter)
            x += column["width"]
        chart_width = len(self.dates) * ppd if self.options.content != "table" else 0
        if chart_width:
            for major, y, height in ((True, 36, 20), (False, 56, 24)):
                for offset, length, label in self._periods(major):
                    rect = QRectF(self.left + offset * ppd, y, length * ppd, height)
                    painter.fillRect(rect, QColor("#f8f8f8"))
                    painter.setPen(QColor("#dfe4ea"))
                    painter.drawRect(rect)
                    self._text(painter, rect, label, align=Qt.AlignmentFlag.AlignHCenter)
        painter.save()
        painter.setClipRect(QRectF(0, self.header, self.width, body_height))
        if chart_width:
            for i, day in enumerate(self.dates):
                if ppd >= 6 and not self.source.project.calendar.working_day(day):
                    painter.fillRect(QRectF(self.left + i * ppd, self.header, ppd, body_height), QColor("#f3faff"))
            painter.setPen(QColor("#ededed"))
            for offset, _length, _label in self._periods(False):
                x = self.left + offset * ppd
                painter.drawLine(QPointF(x, self.header), QPointF(x, self.header + body_height))
            if self.options.today and self.start <= self.source.today <= self.end:
                x = self.left + (self.source.today - self.start).days * ppd
                painter.setPen(QPen(QColor("#2486ed"), 1))
                painter.drawLine(QPointF(x, self.header), QPointF(x, self.header + body_height))
        if chart_width and self.options.links:
            self._links(painter, first)
        for index in range(first, min(first + count, len(self.rows))):
            row = self.rows[index]
            y = self.header + (index - first) * self.row_height
            closed = row["status"] == "closed"
            x = 0.0
            for column in self.columns:
                rect = QRectF(x, y, column["width"], self.row_height)
                if row["summary"]:
                    painter.fillRect(rect, QColor("#fafbfc"))
                inset = row["level"] * 14 if column["key"] == "name" else 0
                self._text(painter, rect.adjusted(inset, 0, 0, 0), self.source.text(row, column["key"]),
                           bold=row["summary"], color="#8b8b8b" if closed and self.options.fade_closed else "#30363b",
                           strike=closed and self.options.strike_closed,
                           align=Qt.AlignmentFlag.AlignRight if column["key"] in {"effort", "cost", "duration", "progress"} else Qt.AlignmentFlag.AlignLeft)
                painter.setPen(QColor("#e6e6e6"))
                painter.drawRect(rect)
                x += column["width"]
            if chart_width:
                self._bar(painter, row, y, chart_width)
            painter.setPen(QColor("#ededed"))
            painter.drawLine(QPointF(0, y + self.row_height), QPointF(self.width, y + self.row_height))
        if self.resources:
            self._workload(painter, first, count, chart_width)
        painter.restore()
        if page:
            self._text(painter, QRectF(0, self.header + body_height, self.width, 20), page,
                       color="#777777", align=Qt.AlignmentFlag.AlignRight)
        painter.restore()

    def _baseline(self, painter: QPainter, row: dict, y: float, chart_width: float) -> None:
        entry = self.reference.tasks.get(row["taskId"]) if self.reference is not None else None
        if not self.options.baseline or entry is None:
            return
        ppd = self.options.pixels_per_day
        x = self.left + (entry.start.date()-self.start).days*ppd
        end = self.left + ((entry.end.date()-self.start).days+1)*ppd
        painter.save()
        painter.setClipRect(QRectF(self.left, y, chart_width, self.row_height), Qt.ClipOperation.IntersectClip)
        color = QColor("#8493a3")
        if entry.kind == "milestone":
            x += ppd/2
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawPolygon(QPolygonF([QPointF(x, y+24), QPointF(x+3, y+27), QPointF(x, y+30), QPointF(x-3, y+27)]))
        else:
            painter.fillRect(QRectF(x, y+27, max(2, end-x), 2), color)
            if entry.kind == "group":
                painter.fillRect(QRectF(x, y+26, 1, 4), color)
                painter.fillRect(QRectF(end-1, y+26, 1, 4), color)
        painter.restore()

    def _bar(self, painter: QPainter, row: dict, y: float, chart_width: float) -> None:
        self._baseline(painter, row, y, chart_width)
        ppd = self.options.pixels_per_day
        x = self.left + (row["startValue"].date() - self.start).days * ppd
        end = self.left + ((row["endValue"].date() - self.start).days + 1) * ppd
        painter.save()
        painter.setClipRect(QRectF(self.left, y, self.width - self.left, self.row_height))
        if self.options.fade_closed and row["status"] == "closed":
            painter.setOpacity(0.45)
        critical = self.analysis is not None and self.analysis.total_float[row["taskId"]] == 0
        color = QColor("#c93b3b" if critical else row["color"])
        if row["milestone"]:
            center = x + ppd / 2
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawPolygon(QPolygonF([QPointF(center, y+5), QPointF(center+10, y+15), QPointF(center, y+25), QPointF(center-10, y+15)]))
            label_rect = QRectF(center+14, y, 180, 30)
        elif row["summary"]:
            painter.fillRect(QRectF(x, y+23, max(2, end-x), 5), color)
            label_rect = QRectF(x, y, max(180, end-x), 21)
        else:
            rect = QRectF(x, y+4, max(6, end-x), 22)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(rect, 2, 2)
            painter.fillRect(QRectF(x, y+4, rect.width()*row["progress"]/100, 22), QColor("#8e232b" if critical else "#289da9"))
            label_rect = QRectF(end+4, y, 176, 30) if self.options.labels == "right" else rect
        if self.options.labels != "none":
            self._text(painter, label_rect, row["name"], bold=row["summary"],
                       color=("#a82c2c" if critical else "#125360") if row["summary"] else "white" if self.options.labels == "inside" and not row["milestone"] else "#30363b",
                       strike=row["status"] == "closed" and self.options.strike_closed)
        deadline = self.source.project.tasks[row["taskId"]].deadline
        if deadline is not None and self.start <= deadline <= self.end:
            marker_x = self.left + ((deadline - self.start).days + 1) * ppd - 1
            marker_color = QColor("#b93d30" if row["deadlineMissed"] or row["deadlineOverdue"] else "#637c87")
            painter.setClipRect(QRectF(self.left, y, chart_width, self.row_height), Qt.ClipOperation.IntersectClip)
            painter.fillRect(QRectF(marker_x, y+3, 1, 24), marker_color)
            painter.fillRect(QRectF(marker_x, y+3, 6, 5), marker_color)
        painter.restore()

    def _links(self, painter: QPainter, first: int) -> None:
        indices = {r["taskId"]: i for i, r in enumerate(self.rows)}
        data = {r["taskId"]: r for r in self.rows}
        ppd = self.options.pixels_per_day
        painter.save()
        painter.setClipRect(QRectF(self.left, self.header, len(self.dates)*ppd, self.body_rows*self.row_height), Qt.ClipOperation.IntersectClip)
        for link in self.source.project.dependencies:
            if link.source not in indices or link.target not in indices:
                continue
            critical = self.analysis is not None and self.analysis.link_float[link.id] == 0
            color = QColor("#c93b3b" if critical else "#ffa726")
            painter.setPen(QPen(color, 2 if critical else 1.4))
            points = []
            for key, endpoint in ((link.source, link.kind[0]), (link.target, link.kind[1])):
                row = data[key]
                day = row["endValue"].date() if endpoint == "F" else row["startValue"].date()
                x = self.left + ((day-self.start).days + (endpoint == "F")) * ppd
                if row["milestone"]:
                    x = self.left + ((row["startValue"].date()-self.start).days+0.5)*ppd + (10 if endpoint == "F" else -10)
                y = self.header + (indices[key]-first+0.5)*self.row_height + (10 if row["summary"] else 0)
                points.append(QPointF(x, y))
            start, end = points
            stub_s = start.x() + (12 if link.kind[0] == "F" else -12)
            stub_t = end.x() + (12 if link.kind[1] == "F" else -12)
            middle = (stub_s+stub_t)/2
            route = [start, QPointF(middle, start.y()), QPointF(middle, end.y()), end]
            if not (link.kind == "FS" and stub_s <= stub_t):
                mid_y = start.y() + (15 if end.y() >= start.y() else -15)
                route = [start, QPointF(stub_s, start.y()), QPointF(stub_s, mid_y), QPointF(stub_t, mid_y), QPointF(stub_t, end.y()), end]
            path = QPainterPath(start)
            for point in route[1:]:
                path.lineTo(point)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            direction = -1 if link.kind[1] == "F" else 1
            painter.setBrush(color)
            painter.drawPolygon(QPolygonF([end, QPointF(end.x()-direction*5, end.y()-3), QPointF(end.x()-direction*5, end.y()+3)]))
        painter.restore()

    def _workload(self, painter: QPainter, first: int, count: int, chart_width: float) -> None:
        title_index = len(self.rows)
        if first <= title_index < first + count:
            y = self.header + (title_index-first)*self.row_height
            painter.fillRect(QRectF(0, y, self.width, 30), QColor("#f8f8f8"))
            self._text(painter, QRectF(0, y, self.width, 30), "Загрузка ресурсов · часы / доступность", bold=True)
        for i, resource in enumerate(self.resources):
            index = title_index + 1 + i
            if not first <= index < first + count:
                continue
            y = self.header + (index-first)*self.row_height
            self._text(painter, QRectF(0, y, self.left, 30), resource["name"])
            for offset, length, _label in self._periods(False):
                days = resource["days"][offset:offset+length]
                hours = sum(d["hours"] for d in days)
                capacity = sum(d["capacity"] for d in days)
                overloaded = any(d["overloaded"] for d in days)
                weekend = any(d["weekendWork"] for d in days)
                rect = QRectF(self.left+offset*self.options.pixels_per_day, y, length*self.options.pixels_per_day, 30)
                if hours:
                    painter.fillRect(rect, QColor("#fceae8" if overloaded else "#fff4d9" if weekend else "#e6f7ec"))
                self._text(painter, rect, f"{hours:g}/{capacity:g}", color="#b93d30" if overloaded else "#ad7a16" if weekend else "#129534",
                           align=Qt.AlignmentFlag.AlignHCenter)
            painter.setPen(QColor("#dfe4ea"))
            painter.drawRect(QRectF(0, y, self.left+chart_width, 30))

    def image(self, maximum: tuple[int, int] | None = None) -> QImage:
        scale = min(1.0, maximum[0]/self.width, maximum[1]/self.height) if maximum else 1.0
        width, height = math.ceil(self.width*scale), math.ceil(self.height*scale)
        if width > 32767 or height > 32767 or width*height > 80000000:
            raise ExportError("PNG слишком велик. Уменьшите масштаб или диапазон дат, либо выберите PDF с размером бумаги.")
        image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        if image.isNull():
            raise ExportError("Недостаточно памяти для изображения.")
        image.fill(QColor("white"))
        painter = QPainter(image)
        try:
            painter.scale(scale, scale)
            self.paint(painter)
        finally:
            painter.end()
        return image

    def pdf_layout(self) -> tuple[QPageSize, QPageLayout.Orientation, float, int]:
        if self.options.paper == "Full":
            if max(self.width, self.height) > 19000:
                raise ExportError("Полный лист PDF слишком велик. Выберите размер бумаги для разбивки на страницы.")
            size = QPageSize(QSizeF(self.width*25.4/96, self.height*25.4/96), QPageSize.Unit.Millimeter, "Full diagram")
            return size, QPageLayout.Orientation.Portrait, 1.0, self.body_rows
        orientation = QPageLayout.Orientation.Landscape if self.options.landscape else QPageLayout.Orientation.Portrait
        size = QPageSize(PAPERS[self.options.paper])
        layout = QPageLayout(size, orientation, QMarginsF(12, 12, 12, 12))
        rect = layout.paintRectPixels(96)
        scale = min(1.0, rect.width()/self.width)
        count = max(1, int((rect.height()/scale-self.header-22)//self.row_height))
        return size, orientation, scale, count

    def write_pdf(self, path: Path) -> None:
        size, orientation, scale, count = self.pdf_layout()
        writer = QPdfWriter(str(path))
        writer.setResolution(96)
        writer.setPageSize(size)
        writer.setPageOrientation(orientation)
        writer.setPageMargins(QMarginsF() if self.options.paper == "Full" else QMarginsF(12, 12, 12, 12))
        writer.setTitle(self.source.project.name)
        writer.setCreator("Gantt Desktop")
        painter = QPainter(writer)
        if not painter.isActive():
            raise ExportError("Не удалось открыть PDF для записи.")
        pages = math.ceil(self.body_rows/count)
        try:
            for page, first in enumerate(range(0, self.body_rows, count), 1):
                if page > 1 and not writer.newPage():
                    raise ExportError("Не удалось создать страницу PDF.")
                painter.save()
                painter.scale(scale, scale)
                self.paint(painter, first, min(count, self.body_rows-first), f"{page} / {pages}" if self.options.paper != "Full" else "")
                painter.restore()
        finally:
            painter.end()


def atomic_export(path: Path, write: Callable[[Path], None]) -> None:
    """Only replace the chosen destination once a complete export was written."""
    descriptor, temporary = tempfile.mkstemp(prefix=".gantt-export-", suffix=path.suffix, dir=path.parent)
    os.close(descriptor)
    temp_path = Path(temporary)
    try:
        write(temp_path)
        if not temp_path.stat().st_size:
            raise ExportError("Экспорт создал пустой файл.")
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def export_file(path: Path, document: ExportDocument) -> None:
    from .interchange import write_csv, write_project_xml, write_xlsx

    def write(target: Path) -> None:
        format_ = document.options.format
        if format_ == "png":
            writer = QImageWriter(str(target), QByteArray(b"png"))
            if not writer.write(document.image()):
                raise ExportError("Не удалось записать PNG: " + writer.errorString())
        elif format_ == "pdf":
            document.write_pdf(target)
        elif format_ in {"xlsx", "ganttpro_xlsx"}:
            write_xlsx(target, document)
        elif format_ == "xml":
            write_project_xml(target, document.source)
        elif format_ == "ganttpro_csv":
            from .interchange import write_ganttpro_csv
            write_ganttpro_csv(target, document)
        else:
            write_csv(target, document)
    atomic_export(Path(path), write)
