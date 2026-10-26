"""The 23-column task table observed in the supplied GanttPRO workbook."""
from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .domain import (
    PRIORITY_LABELS,
    STATUS_LABELS,
    CustomField,
    Dependency,
    Project,
    Resource,
    Task,
    status_for_progress,
)

HEADERS = ("Цвет", "Структура задач", "", "Наименование задач", "Исполнитель", "Дата начала", "Дата окончания",
           "Крайний срок", "Прогресс (%)", "Длительность (часы)", "Трудозатраты в часах", "Затраченное время (минуты)",
           "Статус", "Приоритет", "Описание задачи", "Предшественник", "Стоимость", "Фактическая стоимость",
           "Создан", "Создатель", "Тип", "Проект", "Уровень")
COLUMNS = ("color", "wbs", "groupName", "name", "assignee", "start", "end", "deadline", "progress", "duration", "effort",
           "csvSpent", "status", "priority", "notes", "predecessors", "cost", "csvActual", "csvCreated", "csvCreator",
           "kind", "projectPath", "level")
WIDTHS = (100, 80, 210, 300, 180, 180, 180, 130, 100, 130, 140, 160, 120, 120, 260, 210, 110, 150, 180, 180, 100, 260, 80)
# Text fields deliberately preserve source summary values without numeric rollups.
METADATA = ((11, "ganttpro_spent_minutes"), (17, "ganttpro_actual_cost"),
            (18, "ganttpro_created"), (19, "ganttpro_creator"))
KINDS = {"проект": "group", "задача": "task", "веха": "milestone"}
MAX_BYTES = 16*1024*1024
MAX_TASKS = 2000
MAX_LINKS = 10000
_WBS = re.compile(r"[1-9]\d*(?:\.[1-9]\d*)*")
_LINK = re.compile(r"([1-9]\d*(?:\.[1-9]\d*)*)(?:\s+(FS|SS|FF|SF)(?:\s+([+-]\d+)m)?)?")


class CsvImportError(ValueError):
    pass


@dataclass(frozen=True)
class CsvImport:
    project: Project
    warnings: tuple[str, ...]
    profile: str = "GanttPRO CSV · 23 поля"


def literal(value: str) -> str:
    """Reversible spreadsheet-formula protection, including literal apostrophes."""
    return "'"+value if value.startswith("'") or value.lstrip().startswith(("=", "+", "-", "@")) else value


def unliteral(value: str) -> str:
    if value.startswith("'") and (value[1:].startswith("'") or value[1:].lstrip().startswith(("=", "+", "-", "@"))):
        return value[1:]
    return value


def number(value: str) -> float:
    try:
        result = float(value.strip().replace("\u00a0", "").replace(" ", "").replace(",", "."))
    except ValueError as error:
        raise CsvImportError("Некорректное число CSV.") from error
    if not math.isfinite(result) or result < 0:
        raise CsvImportError("Число должно быть конечным и неотрицательным.")
    return result


def hours_minutes(value: str) -> int:
    hours = number(value)
    if hours > 876000:
        raise CsvImportError("Слишком большая длительность CSV.")
    try:
        minutes = Decimal(value.strip().replace(",", "."))*60
    except InvalidOperation as error:
        raise CsvImportError("Некорректная длительность CSV.") from error
    rounded = minutes.to_integral_value()
    if abs(minutes-rounded) > Decimal("0.000001"):
        raise CsvImportError("Длительность задачи должна иметь минутную точность.")
    return int(rounded)


def timestamp(value: str, finish: bool = False, minute_precision: bool = True) -> datetime:
    text = value.strip()
    try:
        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            serial = Decimal(text)
            if not 61 <= serial <= 2958465:
                raise CsvImportError("Дата Excel вне поддержанного диапазона.")
            result = datetime.fromisoformat("1899-12-30")+timedelta(seconds=round(serial*86400))
        else:
            try:
                result = datetime.fromisoformat(text)
            except ValueError:
                match = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})(?: (\d{2}):(\d{2})(?::(\d{2}))?)?", text)
                if match is None:
                    raise CsvImportError("Ожидается ISO-дата/время или ДД.ММ.ГГГГ [ЧЧ:ММ].") from None
                result = datetime.fromisoformat(f"{match[3]}-{match[2]}-{match[1]}T{match[4] or '00'}:{match[5] or '00'}:{match[6] or '00'}")
            if len(text) == 10:
                result = datetime.combine(result.date(), time(18 if finish else 9))
    except (ValueError, OverflowError) as error:
        raise CsvImportError("Некорректная дата CSV: " + text) from error
    if result.tzinfo is not None or minute_precision and (result.second or result.microsecond):
        raise CsvImportError("Даты задач должны быть локальными, с минутной точностью.")
    return result


def _names(value: str) -> list[str]:
    if not value.strip():
        return []
    try:
        result = next(csv.reader([value], strict=True))
    except csv.Error as error:
        raise CsvImportError("Некорректный список исполнителей.") from error
    if any(not name.strip() for name in result) or len({name.casefold() for name in result}) != len(result):
        raise CsvImportError("Повторяющийся или пустой исполнитель.")
    return result


def read_project_csv(path: Path) -> CsvImport:
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES+1)
    return parse_project_csv(data, path.stem)


def parse_project_csv(data: bytes, fallback_name: str = "Импорт CSV") -> CsvImport:
    if len(data) > MAX_BYTES:
        raise CsvImportError("CSV превышает допустимые 16 MiB.")
    try:
        if data.startswith((b'\xff\xfe', b'\xfe\xff')):
            text = data.decode("utf-16")
        else:
            try:
                text = data.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = data.decode("cp1251")
    except UnicodeError as error:
        raise CsvImportError("Не удалось прочитать кодировку CSV.") from error
    if "\x00" in text:
        raise CsvImportError("CSV содержит нулевые байты.")
    try:
        delimiter = next((d for d in (",", ";", "\t") if tuple(next(csv.reader(io.StringIO(text), delimiter=d), ())) == HEADERS), None)
    except csv.Error as error:
        raise CsvImportError("Повреждённая строка заголовков CSV.") from error
    if delimiter is None:
        raise CsvImportError("Ожидается таблица GanttPRO из 23 столбцов с исходной строкой заголовков, включая пустой третий заголовок.")
    records = {}
    try:
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
        next(reader)
        for row in reader:
            if not any(row):
                continue
            line = reader.line_num
            if len(row) != len(HEADERS):
                raise CsvImportError(f"Строка {line}: требуется 23 столбца.")
            row = [unliteral(value) for value in row]
            wbs = row[1].strip()
            if not _WBS.fullmatch(wbs) or len(wbs) > 256 or wbs in records or wbs.count(".") >= 64:
                raise CsvImportError(f"Строка {line}: некорректная или повторяющаяся структура задач.")
            if row[22].strip() != str(wbs.count(".")+1):
                raise CsvImportError(f"Строка {line}: уровень не соответствует структуре {wbs}.")
            records[wbs] = row
            if len(records) > MAX_TASKS:
                raise CsvImportError("В CSV больше 2000 элементов.")
    except csv.Error as error:
        raise CsvImportError("Повреждённая строка или слишком большое поле CSV.") from error
    if not records:
        raise CsvImportError("В CSV нет элементов.")
    ordered = sorted(records, key=lambda key: tuple(int(part) for part in key.split(".")))
    root_rows = [records[key] for key in ordered if "." not in key]
    project = Project(root_rows[0][21].strip() or fallback_name)
    warnings = ["CSV не содержит рабочих календарей и ёмкости ресурсов: применены Пн–Пт 09–13/14–18 и 8 ч/день.",
                "Простые предшественники означают FS с нулевым лагом. Типы/лаги, отсутствующие в файле, не восстанавливаются по догадке.",
                "Базовые планы и определения пользовательских полей не входят в эту таблицу. Сохраните исходники отдельно."]
    ends = {}
    resources = {}
    paths = {}
    for wbs in ordered:
        row = records[wbs]
        try:
            kind = KINDS[row[20].strip().lower()]
            parent_wbs = wbs.rpartition(".")[0]
            if parent_wbs and (parent_wbs not in records or project.tasks["csv-task-"+parent_wbs].kind != "group"):
                raise CsvImportError("Родитель отсутствует или не является группой.")
            name = row[2] or row[3] if kind == "group" else row[3]
            if not name.strip() or kind != "group" and row[2] or row[2] and row[3] and row[2] != row[3]:
                raise CsvImportError("Некорректное имя/размещение группы и задачи.")
            path = paths[parent_wbs]+" / "+project.tasks["csv-task-"+parent_wbs].name if parent_wbs else project.name
            if row[21] and row[21] != path:
                raise CsvImportError("Путь проекта не соответствует структуре задач.")
            paths[wbs] = path
            start = timestamp(row[5])
            end = timestamp(row[6], finish=kind != "milestone")
            if end < start or (end-start).days > 36600:
                raise CsvImportError("Некорректный или превышающий 100 лет диапазон задачи.")
            duration = hours_minutes(row[9])
            if kind == "milestone" and (duration or end != start):
                raise CsvImportError("У вехи должны совпадать даты при нулевой длительности.")
            if kind == "task" and (duration > (end-start).total_seconds()/60 or project.calendar.add(start, duration) != end):
                raise CsvImportError("Начало/окончание и рабочая длительность не совпадают. Сохраните время в датах и проверьте календарь.")
            progress = number(row[8])
            if progress > 100:
                raise CsvImportError("Прогресс должен быть от 0 до 100.")
            status = next((key for key, label in STATUS_LABELS.items() if row[12] in {key, label}), status_for_progress(progress))
            if row[12] and row[12] not in {*STATUS_LABELS, *STATUS_LABELS.values()}:
                raise CsvImportError("Неизвестный статус.")
            if status in {"completed", "closed"} and progress != 100 or status == "open" and progress != 0 or status == "in_progress" and not 0 < progress < 100:
                raise CsvImportError("Статус противоречит прогрессу.")
            priority = next((key for key, label in PRIORITY_LABELS.items() if row[13] in {key, label}), "medium")
            if row[13] and row[13] not in {*PRIORITY_LABELS, *PRIORITY_LABELS.values()}:
                raise CsvImportError("Неизвестный приоритет.")
            if kind == "group" and (row[12] or row[13]):
                raise CsvImportError("Статус и приоритет сводной группы должны оставаться пустыми, как в исходной таблице.")
            color = row[0] or ("#d860bb" if kind == "milestone" else "#50c7d6")
            if not row[0]:
                warnings.append("Пустые цвета заменены стандартными: CSV не хранит заливки Excel.")
            task = Task("csv-task-"+wbs, name, start, duration if kind == "task" else 0,
                        "csv-task-"+parent_wbs if parent_wbs else "", kind, progress=progress,
                        effort=number(row[10]) if kind != "group" else 0, cost=number(row[16]) if kind != "group" else 0,
                        color=color, notes=row[14], status=status, priority=priority)
            if row[7]:
                deadline = timestamp(row[7], minute_precision=False)
                date_only = re.fullmatch(r"\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4}|\d+", row[7].strip())
                if not date_only and deadline.time() not in {time(), time(23, 59, 59)}:
                    raise CsvImportError("Поддержана дата дедлайна, а не время внутри дня.")
                task.deadline = deadline.date()
            for index, field_id in METADATA:
                value = row[index]
                if value:
                    if index in {11, 17}:
                        number(value)
                    elif index == 18:
                        timestamp(value, minute_precision=False)
                    if field_id not in project.custom_fields:
                        project.save_custom_field(CustomField(field_id, HEADERS[index], "text"))
                    task.custom_values[field_id] = value
            names = _names(row[4])
            if kind == "group" and names:
                raise CsvImportError("Назначения на сводную группу не поддержаны.")
            for name_ in names:
                folded = name_.casefold()
                if folded not in resources:
                    if len(resources) >= MAX_TASKS:
                        raise CsvImportError("Слишком много ресурсов CSV.")
                    resource = Resource("csv-resource-"+str(len(resources)+1), name_)
                    project.resources[resource.id] = resource
                    resources[folded] = resource.id
                task.resource_ids.append(resources[folded])
            project.tasks[task.id] = task
            ends[task.id] = end
        except (ValueError, KeyError, OverflowError) as error:
            raise CsvImportError(f"Элемент {wbs}: {error}") from error
    project.sync_resource_names()
    for wbs in ordered:
        target = "csv-task-"+wbs
        for value in re.split(r"[,;]", records[wbs][15]):
            if not value.strip():
                continue
            match = _LINK.fullmatch(value.strip())
            if match is None or match[1] not in records:
                raise CsvImportError(f"Элемент {wbs}: неизвестный предшественник или синтаксис связи.")
            lag = int(match[3] or "0")
            if abs(lag) > 52560000:
                raise CsvImportError("Слишком большой лаг CSV.")
            project.dependencies.append(Dependency("csv-link-"+str(len(project.dependencies)+1), "csv-task-"+match[1], target, match[2] or "FS", lag))
            if len(project.dependencies) > MAX_LINKS:
                raise CsvImportError("Слишком много связей CSV.")
    project.validate()
    for task_id, expected in ends.items():
        start, end = project.span(task_id)
        if end != expected or project.tasks[task_id].kind == "group" and start != project.tasks[task_id].start:
            raise CsvImportError("Границы группы/элемента не совпадают с его дочерними задачами: " + project.tasks[task_id].name)
    if (max(ends.values())-min(task.start for task in project.tasks.values())).days > 36600:
        raise CsvImportError("Диапазон CSV превышает 100 лет.")
    if project.custom_fields:
        warnings.append("Затраченное время, фактическая стоимость, создание и автор сохранены текстовыми пользовательскими полями без подмены плановых значений.")
    for wbs in ordered:
        task = project.tasks["csv-task-"+wbs]
        if task.kind != "group":
            continue
        leaves = project.leaves(task.id)
        weight = sum(t.duration for t in leaves)
        progress = sum(t.progress*t.duration for t in leaves)/weight if weight else 0
        duration = project.calendar.between(*project.span(task.id))/60
        for index, total in ((8, progress), (9, duration), (10, sum(t.effort for t in leaves)), (16, sum(t.cost for t in leaves))):
            if not math.isclose(number(records[wbs][index]), total, abs_tol=1e-8):
                warnings.append("Итоги группы вычислены по дочерним задачам: " + wbs)
    inconsistent = sum(project.calendar.between(project.span(d.source)[d.kind[0] == "F"], project.span(d.target)[d.kind[1] == "F"]) < d.lag for d in project.dependencies)
    if inconsistent:
        warnings.append(f"Несогласованных по датам связей: {inconsistent}. Даты сохранены без перепланирования.")
    return CsvImport(project, tuple(dict.fromkeys(warnings)))


def table_rows(project: Project, records: list[dict]) -> list[list[str]]:
    outlines = {row["taskId"]: row["outline"] for row in records}
    result = []
    def numeric(value):
        return str(int(value)) if float(value).is_integer() else repr(value)
    for row in records:
        task = project.tasks[row["taskId"]]
        summary = task.kind == "group"
        path = []
        parent = task.parent
        while parent:
            path.append(project.tasks[parent].name)
            parent = project.tasks[parent].parent
        assignees = io.StringIO()
        csv.writer(assignees).writerow([project.resources[rid].name for rid in task.resource_ids])
        links = []
        for link in project.dependencies:
            if link.target == task.id:
                label = outlines[link.source]
                if link.kind != "FS" or link.lag:
                    label += " "+link.kind+(f" {link.lag:+d}m" if link.lag else "")
                links.append(label)
        values = [task.color, row["outline"], task.name if summary else "", "" if summary else task.name, assignees.getvalue()[:-2],
                  row["startValue"].isoformat(sep=" ", timespec="seconds"), row["endValue"].isoformat(sep=" ", timespec="seconds"),
                  task.deadline.isoformat() if task.deadline else "", numeric(row["progress"]), numeric(row["duration"]), numeric(row["effortHours"]), "",
                  "" if summary else STATUS_LABELS[task.status], "" if summary else PRIORITY_LABELS[task.priority], task.notes, ", ".join(links),
                  numeric(row["costValue"]), "", "", "", next(label for label, kind in KINDS.items() if kind == task.kind),
                  " / ".join([project.name, *reversed(path)]), str(row["level"]+1)]
        for index, field_id in METADATA:
            if field_id in project.custom_fields:
                values[index] = str(project.custom_value(task.id, field_id) or "")
                if values[index] and index in {11, 17}:
                    number(values[index])
                elif values[index] and index == 18:
                    timestamp(values[index], minute_precision=False)
        result.append(values)
    return result


def write_rows(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(HEADERS)
        writer.writerows([[literal(value) for value in row] for row in rows])
