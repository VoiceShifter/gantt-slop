"""Bounded, offline MSPDI/GanttPRO XML import with explicit fidelity warnings."""
from __future__ import annotations

import math
import re
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import iterparse

from .domain import (
    STATUS_LABELS,
    Baseline,
    BaselineEntry,
    CalendarException,
    CustomField,
    Dependency,
    Project,
    Resource,
    ResourceException,
    Task,
    WorkCalendar,
    status_for_progress,
    validate_exceptions,
)
from .ganttpro_csv import HEADERS, METADATA
from .xml_fields import METADATA_FIELDS

MSP = "http://schemas.microsoft.com/project"
MAX_XML_BYTES = 16 * 1024 * 1024
MAX_TASKS = 2000
MAX_LINKS = 10000
_DURATION = re.compile(r"PT(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?")


class XmlImportError(ValueError):
    """The XML cannot be represented safely without changing diagram data."""


@dataclass(frozen=True)
class XmlImport:
    project: Project
    warnings: tuple[str, ...]
    profile: str


def duration_minutes(value: str) -> Decimal:
    match = _DURATION.fullmatch(value)
    if not match or not any(match.groups()) or len(value) > 120:
        raise XmlImportError("Длительность должна иметь формат PT…H…M…S без месяцев/календарных дней.")
    hours, minutes, seconds = (Decimal(part or "0") for part in match.groups())
    result = hours*60 + minutes + seconds/60
    if result > 52_560_000:
        raise XmlImportError("Слишком большая длительность XML.")
    return result


def local_datetime(value: str, *, minute_precision: bool = True) -> datetime:
    try:
        result = datetime.fromisoformat(value)
    except ValueError as error:
        raise XmlImportError("Некорректная ISO-дата XML.") from error
    if result.tzinfo is not None or minute_precision and (result.second or result.microsecond):
        raise XmlImportError("Даты задач должны быть локальными, с минутной точностью, без часового пояса.")
    return result


def read_project_xml(path: Path, imported_on: date) -> XmlImport:
    with path.open("rb") as stream:
        data = stream.read(MAX_XML_BYTES+1)
    return parse_project_xml(data, path.stem, imported_on)


def _overlay(entries, override):
    """A child calendar/availability range overrides, rather than overlaps, its base."""
    result = []
    for item in entries:
        if item.end < override.start or item.start > override.end:
            result.append(item)
            continue
        if item.start < override.start:
            result.append(replace(deepcopy(item), id=item.id+"-left-"+override.id, end=override.start-timedelta(days=1)))
        if item.end > override.end:
            result.append(replace(deepcopy(item), id=item.id+"-right-"+override.id, start=override.end+timedelta(days=1)))
    return sorted([*result, override], key=lambda item: item.start)


def parse_project_xml(data: bytes, fallback_name: str, imported_on: date) -> XmlImport:
    if len(data) > MAX_XML_BYTES:
        raise XmlImportError("XML превышает допустимые 16 MiB.")
    try:
        reader = iterparse(BytesIO(data), events=("start", "end"), forbid_dtd=True, forbid_entities=True, forbid_external=True)
        depth = count = 0
        root = None
        for event, _node in reader:
            if event == "start":
                depth += 1
                count += 1
                if depth == 1:
                    root = _node
                if depth > 64 or count > 100_000:
                    raise XmlImportError("Слишком глубокий или большой XML проекта.")
            else:
                depth -= 1
        if root is None:
            raise XmlImportError("Пустой XML проекта.")
    except (ET.ParseError, DefusedXmlException) as error:
        raise XmlImportError("Повреждённый или небезопасный XML проекта (DTD/сущности запрещены).") from error
    if root.tag not in {"Project", "{"+MSP+"}Project"}:
        raise XmlImportError("Поддерживается Microsoft Project XML (MSPDI), не произвольный XML.")
    namespace = "{"+MSP+"}" if root.tag.startswith("{") else ""
    def elements(node, path):
        return node.findall("/".join(namespace+part for part in path.split("/")))
    def value(node, name, default="", *, strip=True):
        found = node.find(namespace+name)
        if found is None or found.text is None:
            return default
        return found.text.strip() if strip else found.text
    def flag(node, name, default=False):
        text = value(node, name, "1" if default else "0").lower()
        if text not in {"0", "1", "true", "false"}:
            raise XmlImportError("Некорректный флаг XML: " + name)
        return text in {"1", "true"}
    def integer(text):
        if not re.fullmatch(r"-?\d{1,12}", text):
            raise XmlImportError("Некорректное целое значение XML.")
        return int(text)
    def number(text):
        try:
            result = float(text)
        except ValueError as error:
            raise XmlImportError("Некорректное число XML.") from error
        if not math.isfinite(result):
            raise XmlImportError("XML содержит бесконечное числовое значение.")
        return result
    def periods(node):
        result = []
        for item in elements(node, "WorkingTimes/WorkingTime"):
            pair = []
            for key in ("FromTime", "ToTime"):
                parsed = time.fromisoformat(value(item, key))
                if parsed.tzinfo is not None or parsed.second or parsed.microsecond:
                    raise XmlImportError("Рабочие интервалы XML должны иметь минутную точность.")
                pair.append(parsed.hour*60+parsed.minute)
            result.append(pair)
        return result

    warnings: list[str] = []
    calendar_nodes = {}
    for node in elements(root, "Calendars/Calendar"):
        uid = value(node, "UID")
        if not uid or uid in calendar_nodes:
            raise XmlImportError("Повторяющийся/пустой UID календаря.")
        calendar_nodes[uid] = node
    resolved: dict[str, WorkCalendar] = {}
    def calendar(uid, trail=()):
        if uid in resolved:
            return resolved[uid]
        if uid not in calendar_nodes or uid in trail or len(trail) > 64:
            raise XmlImportError("Неизвестный или циклический календарь XML.")
        node = calendar_nodes[uid]
        parent = value(node, "BaseCalendarUID", "-1")
        result = deepcopy(calendar(parent, (*trail, uid))) if parent not in {"-1", ""} else WorkCalendar()
        own_ranges = []
        for item in elements(node, "WeekDays/WeekDay"):
            kind = integer(value(item, "DayType"))
            working = flag(item, "DayWorking")
            slots = periods(item) if working else []
            if kind == 0:
                period = elements(item, "TimePeriod")
                if len(period) != 1:
                    raise XmlImportError("У датированного календаря нет диапазона.")
                start = local_datetime(value(period[0], "FromDate"), minute_precision=False).date()
                end = local_datetime(value(period[0], "ToDate"), minute_precision=False).date()
                if end < start or (end-start).days > 36600:
                    raise XmlImportError("Диапазон исключения XML некорректен или превышает 100 лет.")
                if any(a <= end and start <= b for a, b in own_ranges):
                    raise XmlImportError("Пересекающиеся исключения одного календаря XML.")
                own_ranges.append((start, end))
                result.exceptions = _overlay(result.exceptions, CalendarException(f"xml-{uid}-{len(own_ranges)}", start, end, "Из XML", slots))
            elif 1 <= kind <= 7:
                day = (kind+5) % 7
                if working:
                    result.workdays.add(day)
                    if slots != [[540, 780], [840, 1080]]:
                        result.weekly_periods[day] = slots
                    else:
                        result.weekly_periods.pop(day, None)
                else:
                    result.workdays.discard(day)
                    result.weekly_periods.pop(day, None)
            else:
                raise XmlImportError("Неподдерживаемый тип дня XML.")
        if elements(node, "Exceptions/Exception"):
            raise XmlImportError("Повторяющиеся/расширенные календарные Exception не поддержаны; используйте датированные WeekDay/TimePeriod.")
        if result.workdays:
            result.validate()
        else:
            # A resource can have no regular workdays; a scheduling calendar cannot.
            validate_exceptions(result.exceptions, CalendarException)
        resolved[uid] = result
        return result
    selected_calendar = value(root, "CalendarUID", next(iter(calendar_nodes), "1"))
    project_calendar = deepcopy(calendar(selected_calendar)) if calendar_nodes else WorkCalendar()
    project_calendar.validate()
    if not calendar_nodes:
        warnings.append("В XML нет календаря: используются Пн–Пт, 09–13/14–18. Проверьте даты.")
    def calendar_signature(item):
        return (item.workdays, item.weekly_periods, item.holidays,
                [(entry.start, entry.end, entry.periods) for entry in item.exceptions])

    records = elements(root, "Tasks/Task")
    if len(records) > MAX_TASKS:
        raise XmlImportError("В XML больше 2000 элементов.")
    ganttpro = bool(records and value(records[0], "Name") == "Total estimate" and
                   flag(records[0], "Summary") and value(root, "SaveVersion") == "9" and not value(records[0], "Finish"))
    skipped = set()
    if records and (ganttpro or value(records[0], "UID") == "0" and flag(records[0], "Summary") and value(records[0], "OutlineLevel") == "0"):
        skipped.add(value(records[0], "UID"))
        records = records[1:]
        warnings.append("Служебная сводка проекта исключена; пользовательская иерархия сохранена.")
    if ganttpro:
        warnings += ["Профиль GanttPRO: при отсутствии Finish окончания вычисляются из Start/Duration и календаря.",
                     "GanttPRO XML не гарантирует сохранение цветов/веб-метаданных."]
        if not elements(root, "Resources/Resource") and not elements(root, "Assignments/Assignment"):
            warnings.append("GanttPRO XML не содержит ресурсов/назначений: они не восстановлены.")
    # Correct only the identified GanttPRO Export Tool v2 minute/hour defect.
    # Ordinary MSPDI and unrecognized exporters always retain literal ISO Work.
    work_scale = 60 if (ganttpro and value(root, "Author") == "Export Tool v.2.1.0.0" and
                        value(root, "WorkFormat") == "2" and
                        not elements(root, "Resources/Resource") and not elements(root, "Assignments/Assignment")) else 1
    if work_scale == 60:
        warnings.append("Исправлен известный профиль Export Tool v.2.1.0.0: Work ×60; записанные минуты означают часы GanttPRO. Проверьте трудозатраты в таблице.")
    elif ganttpro:
        warnings.append("Work импортируется буквально по ISO XML; неизвестный профиль экспортёра не пересчитывается.")
    if ganttpro and not any(value(record, "Cost") or value(record, "FixedCost") for record in records):
        warnings.append("В GanttPRO XML нет стоимости: сохранено 0, значения из других файлов не подставляются.")
    custom_fields = {}
    field_map = {}
    metadata_map = {}
    field_names = {}
    source_metadata = {HEADERS[column]: key for column, key in METADATA}
    for definition in elements(root, "ExtendedAttributes/ExtendedAttribute"):
        uid = value(definition, "FieldID")
        if not uid:
            warnings.append("Определение XML-поля без FieldID не поддержано; значения останутся в описании.")
            continue
        if uid in field_names:
            raise XmlImportError("Повторяющийся FieldID пользовательского поля XML.")
        name = value(definition, "Alias", value(definition, "FieldName", "XML поле "+uid), strip=False)
        field_names[uid] = name
        cf_type = value(definition, "CFType")
        native = next((key for key, slot, _label, alias, type_ in METADATA_FIELDS
                       if uid == str(slot) and name == alias and cf_type == str(type_)), "")
        if native:
            metadata_map[uid] = native
            continue
        kind = {"0": "number", "1": "date", "4": "checkbox", "5": "number", "7": "text"}.get(cf_type)
        if not kind:
            kind = next((kind_ for label, kind_ in (("Text", "text"), ("Number", "number"), ("Date", "date"), ("Flag", "checkbox"))
                         if re.fullmatch(label+r"\d+", value(definition, "FieldName")) and not cf_type), None)
        rollup = value(definition, "RollupType", "3")
        if kind is None or kind == "number" and rollup not in {"3", "4"}:
            warnings.append("Неподдержанный тип/агрегация XML-поля сохранится в описании: "+name)
            continue
        if any(item.name.casefold() == name.casefold() for item in custom_fields.values()):
            name += " ("+uid+")"
            warnings.append("Одинаковые названия XML-полей различены по FieldID.")
        key = source_metadata.get(name, "xml-field-"+uid) if kind == "text" else "xml-field-"+uid
        field_ = CustomField(key, name, kind, aggregate=("average" if rollup == "4" else "sum") if kind == "number" else "")
        field_.validate()
        custom_fields[key] = field_
        field_map[uid] = key
        if elements(definition, "ValueList") or value(definition, "LookupTable"):
            warnings.append("Справочник XML-поля не переносится как список опций: "+name)
    task_metadata = {}
    tasks = {}
    uid_map = {}
    source_records = {}
    stored_finish = {}
    stack = []
    first_level = None
    for record in records:
        uid = value(record, "UID")
        if not uid or uid in uid_map or uid in skipped:
            raise XmlImportError("Повторяющийся/пустой UID задачи.")
        if flag(record, "IsNull"):
            warnings.append("Пустая служебная строка XML пропущена.")
            continue
        level = integer(value(record, "OutlineLevel", str(value(record, "OutlineNumber", "1").count(".")+1)))
        if first_level is None:
            first_level = level
        level -= first_level-1
        if not 1 <= level <= 64 or level > len(stack)+1:
            raise XmlImportError("Непоследовательный или слишком глубокий OutlineLevel.")
        stack = stack[:level-1]
        parent = stack[-1] if stack else ""
        key = "xml-task-"+uid
        start_text = value(record, "Start")
        if not start_text:
            raise XmlImportError("У задачи отсутствует Start: " + uid)
        start = local_datetime(start_text)
        finish_text = value(record, "Finish")
        finish = local_datetime(finish_text) if finish_text else None
        if finish is not None and (finish < start or (finish-start).days > 36600):
            raise XmlImportError("Некорректный или превышающий 100 лет диапазон задачи XML.")
        task_calendar = value(record, "CalendarUID", selected_calendar)
        if calendar_nodes and task_calendar not in {"-1", ""} and calendar_signature(calendar(task_calendar)) != calendar_signature(project_calendar):
            raise XmlImportError("Разные календари задач пока не поддержаны без изменения дат.")
        raw_duration = duration_minutes(value(record, "Duration", "PT0M"))
        if raw_duration % 1:
            raise XmlImportError("Субминутная длительность задачи не поддержана.")
        duration = int(raw_duration)
        summary = flag(record, "Summary")
        milestone = flag(record, "Milestone") or not duration and not summary and (finish is None or finish == start)
        if milestone and not flag(record, "Milestone"):
            warnings.append("Нулевые задачи представлены вехами; XML не пометил их флагом Milestone.")
        kind = "group" if summary else "milestone" if milestone else "task"
        if kind == "task" and finish is not None:
            duration = project_calendar.between(start, finish)
            if duration != raw_duration:
                warnings.append("Duration уточнён по явным Start/Finish: " + value(record, "Name", uid))
        if kind != "task":
            duration = 0
        progress = number(value(record, "PercentComplete", "0"))
        effort = float(duration_minutes(value(record, "Work", "PT0M"))*work_scale/60)
        metadata = {}
        custom_values = {}
        extra_notes = []
        seen_fields = set()
        for item in elements(record, "ExtendedAttribute"):
            field_id = value(item, "FieldID")
            if field_id in seen_fields:
                raise XmlImportError("Повторяющееся значение XML-поля задачи.")
            seen_fields.add(field_id)
            raw = value(item, "Value", value(item, "ValueGUID"), strip=False)
            if field_id in metadata_map:
                metadata[metadata_map[field_id]] = raw
            elif field_id in field_map:
                field_ = custom_fields[field_map[field_id]]
                if not raw:
                    continue
                parsed: object = raw
                if field_.kind == "number":
                    parsed = number(raw)
                elif field_.kind == "checkbox":
                    if raw.lower() not in {"0", "1", "true", "false"}:
                        raise XmlImportError("Некорректный флажок пользовательского XML-поля.")
                    parsed = raw.lower() in {"1", "true"}
                elif field_.kind == "date":
                    parsed_date = local_datetime(raw, minute_precision=False)
                    if parsed_date.time() != time():
                        raise XmlImportError("Дата пользовательского XML-поля содержит неподдержанное время суток.")
                    parsed = parsed_date.date().isoformat()
                if not summary or field_.kind != "number":
                    custom_values[field_.id] = field_.normalize(parsed, {})
            else:
                extra_notes.append(field_names.get(field_id, "XML поле "+field_id)+": "+raw)
                warnings.append("Неподдержанные XML-поля сохранены текстом в описании, не как пользовательские поля.")
        for column, field_id, tag in ((11, "ganttpro_spent_minutes", "ActualWork"),
                                      (17, "ganttpro_actual_cost", "ActualCost"),
                                      (18, "ganttpro_created", "CreateDate")):
            raw = value(record, tag)
            if not raw or field_id in custom_values:
                continue
            if tag == "ActualWork":
                raw = str(duration_minutes(raw))
            elif tag == "ActualCost":
                if number(raw) < 0:
                    raise XmlImportError("Фактическая стоимость XML не может быть отрицательной.")
            else:
                raw = local_datetime(raw, minute_precision=False).isoformat(sep=" ")
            custom_fields.setdefault(field_id, CustomField(field_id, HEADERS[column]))
            custom_values[field_id] = raw
        if "progress" in metadata:
            exact_progress = number(metadata["progress"])
            if round(exact_progress) != progress:
                raise XmlImportError("Метаданные прогресса XML противоречат PercentComplete.")
            progress = exact_progress
        color = metadata.get("color", "#d65ab1" if milestone else "#50c7d6")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise XmlImportError("Некорректный цвет задачи в метаданных XML.")
        status = metadata.get("status", status_for_progress(progress))
        if status not in STATUS_LABELS or (status in {"completed", "closed"}) != (progress >= 100) or (status == "open") != (progress == 0):
            raise XmlImportError("Статус XML противоречит прогрессу задачи.")
        priority = number(value(record, "Priority", "500"))
        priority_name = min(((0, "lowest"), (250, "low"), (500, "medium"), (750, "high"), (1000, "highest")), key=lambda pair: abs(pair[0]-priority))[1]
        task = Task(key, value(record, "Name", "Задача "+uid, strip=False), start, duration, parent, kind,
                    progress=progress, effort=effort if kind != "group" else 0,
                    cost=number(value(record, "Cost", value(record, "FixedCost", "0"))) if kind != "group" else 0,
                    color=color, notes=value(record, "Notes", strip=False),
                    status=status, priority=priority_name, custom_values=custom_values)
        if extra_notes:
            task.notes += ("\n" if task.notes else "")+"\n".join(extra_notes)
        task_metadata[key] = metadata
        deadline = value(record, "Deadline")
        if deadline:
            task.deadline = local_datetime(deadline, minute_precision=False).date()
        tasks[key] = task
        uid_map[uid] = key
        source_records[key] = record
        stored_finish[key] = finish
        if parent and tasks[parent].kind != "group":
            tasks[parent].kind, tasks[parent].duration, tasks[parent].effort, tasks[parent].cost = "group", 0, 0, 0
            warnings.append("Группа определена по OutlineLevel: " + tasks[parent].name)
        stack.append(key)
        if value(record, "ConstraintType", "0") != "0":
            warnings.append("Ограничение даты не переносится как правило планировщика: " + task.name)
    project = Project(value(root, "Name", value(root, "Title", fallback_name), strip=False) or "Импорт XML", tasks,
                      calendar=project_calendar, custom_fields=custom_fields)
    for key, record in source_records.items():
        for link in elements(record, "PredecessorLink"):
            predecessor = value(link, "PredecessorUID")
            if predecessor not in uid_map or flag(link, "CrossProject"):
                raise XmlImportError("Неизвестная/межпроектная зависимость XML.")
            lag = Decimal(integer(value(link, "LinkLag", "0")))/10
            if not lag.is_finite() or lag % 1 or abs(lag) > 52_560_000:
                raise XmlImportError("Лаг должен быть целым числом рабочих минут.")
            kinds = {0: "FF", 1: "FS", 2: "SF", 3: "SS"}
            link_kind = integer(value(link, "Type", "1"))
            if link_kind not in kinds:
                raise XmlImportError("Неизвестный тип зависимости XML.")
            project.dependencies.append(Dependency("xml-link-"+str(len(project.dependencies)+1), uid_map[predecessor], key, kinds[link_kind], int(lag)))
            if len(project.dependencies) > MAX_LINKS:
                raise XmlImportError("Слишком много связей XML.")
    for key, finish in stored_finish.items():
        start, derived = project.span(key)
        if finish is not None and derived != finish:
            raise XmlImportError("Finish невозможно сохранить в поддержанном календаре: " + tasks[key].name)
        if tasks[key].kind == "group" and project.children(key) and start != tasks[key].start:
            raise XmlImportError("Start группы не совпадает с границами её детей: " + tasks[key].name)
    spans = [project.span(key) for key in tasks]
    if spans and (max(b for _a, b in spans)-min(a for a, _b in spans)).days > 36600:
        raise XmlImportError("Диапазон XML превышает 100 лет.")

    resource_map = {}
    for record in elements(root, "Resources/Resource"):
        uid = value(record, "UID")
        if not uid or uid in resource_map:
            raise XmlImportError("Повторяющийся/пустой UID ресурса.")
        if uid == "0" and not value(record, "Name"):
            continue
        if value(record, "Type", "1") != "1":
            raise XmlImportError("Материальные/стоимостные ресурсы XML не поддержаны как люди проекта.")
        name = value(record, "Name", "Ресурс "+uid, strip=False)
        if any(item.name.casefold() == name.casefold() for item in project.resources.values()):
            name += " ("+uid+")"
            warnings.append("Одинаковые имена ресурсов различены по UID.")
        resource_calendar_id = value(record, "CalendarUID")
        if calendar_nodes and resource_calendar_id not in {"", "-1"} and resource_calendar_id not in calendar_nodes:
            raise XmlImportError("Неизвестный календарь ресурса XML.")
        availability = calendar(resource_calendar_id) if resource_calendar_id in calendar_nodes else project_calendar
        capacity = number(value(record, "MaxUnits", "1"))*number(value(root, "MinutesPerDay", "480"))/60
        resource = Resource("xml-resource-"+uid, name, capacity, set(availability.workdays))
        dated = [ResourceException("xml-availability-"+str(i), item.start, item.end, "Из XML", capacity if item.periods else 0)
                 for i, item in enumerate(availability.exceptions)
                 if not any(item.id == base.id or item.id.startswith(base.id+"-") for base in project_calendar.exceptions)]
        own_availability = []
        for index, item in enumerate(elements(record, "AvailabilityPeriods/AvailabilityPeriod")):
            start, end = value(item, "AvailableFrom"), value(item, "AvailableTo")
            units = number(value(item, "AvailableUnits", "1"))*number(value(root, "MinutesPerDay", "480"))/60
            if start and end:
                bounds = (local_datetime(start, minute_precision=False).date(), local_datetime(end, minute_precision=False).date())
                if bounds[1] < bounds[0] or (bounds[1]-bounds[0]).days > 36600:
                    raise XmlImportError("Диапазон доступности XML некорректен или превышает 100 лет.")
                if any(a <= bounds[1] and bounds[0] <= b for a, b in own_availability):
                    raise XmlImportError("Пересекающиеся периоды доступности ресурса XML.")
                own_availability.append(bounds)
                dated = _overlay(dated, ResourceException("xml-period-"+str(index), *bounds, "Из XML", units))
            elif units != capacity:
                warnings.append("Неограниченный период доступности ресурса не переносится: " + name)
        resource.exceptions = dated
        if availability.weekly_periods:
            warnings.append("Часы присутствия ресурса по времени суток не переносятся; сохранены дни и дневная ёмкость: " + name)
        resource.validate()
        project.resources[resource.id] = resource
        resource_map[uid] = resource.id
    assigned = defaultdict(list)
    for record in elements(root, "Assignments/Assignment"):
        task_uid, resource_uid = value(record, "TaskUID"), value(record, "ResourceUID")
        if resource_uid == "-65535" or task_uid in skipped:
            continue
        if task_uid not in uid_map or resource_uid not in resource_map:
            raise XmlImportError("Назначение ссылается на неизвестный элемент.")
        task_id = uid_map[task_uid]
        if tasks[task_id].kind == "group":
            warnings.append("Назначение на сводную группу пропущено; группы вычисляются по детям.")
            continue
        work = float(duration_minutes(value(record, "Work", "PT0M"))/60)
        units = number(value(record, "Units", "1"))
        if units < 0:
            raise XmlImportError("Отрицательная загрузка назначения XML.")
        assigned[task_id].append((resource_map[resource_uid], work, units))
    for key, values in assigned.items():
        if len({rid for rid, _work, _units in values}) != len(values):
            raise XmlImportError("Дублирующее назначение ресурса на задачу.")
        total = sum(work for _rid, work, _units in values)
        weights = [work if total else units for _rid, work, units in values]
        denominator = sum(weights)
        tasks[key].resource_ids = [rid for rid, _work, _units in values]
        tasks[key].resource_shares = [weight/denominator for weight in weights] if denominator else []
        if not value(source_records[key], "Work"):
            tasks[key].effort = total
        elif total and not math.isclose(total, tasks[key].effort):
            warnings.append("Сумма Work назначений отличается от Work задачи; общий объём распределён пропорционально: " + tasks[key].name)
    project.sync_resource_names()

    baseline_entries = defaultdict(dict)
    baseline_names = {}
    baseline_dates = {}
    for key, record in source_records.items():
        for item in elements(record, "Baseline"):
            number_ = value(item, "Number", "0")
            start, end = value(item, "Start"), value(item, "Finish")
            if not start or not end:
                warnings.append("Неполная запись базового плана пропущена.")
                continue
            a, b = local_datetime(start, minute_precision=False), local_datetime(end, minute_precision=False)
            kind = "task" if tasks[key].kind == "milestone" and a != b else tasks[key].kind
            baseline_entries[number_][key] = BaselineEntry(key, tasks[key].name, kind, a, b)
            name = next((line.removeprefix("Базовый план: ").strip() for line in tasks[key].notes.splitlines() if line.startswith("Базовый план: ")), "Базовый план XML "+number_)
            native = task_metadata[key] if number_ == "0" else {}
            name = native.get("baseline", name)
            created = date.fromisoformat(native["baseline_created"]) if native.get("baseline_created") else imported_on
            if number_ in baseline_names and (baseline_names[number_] != name or baseline_dates[number_] != created):
                raise XmlImportError("Противоречащие метаданные базового плана XML.")
            baseline_names[number_] = name
            baseline_dates[number_] = created
    for number_, entries in baseline_entries.items():
        key = "xml-baseline-"+number_
        name = baseline_names[number_]
        if any(item.name.casefold() == name.casefold() for item in project.baselines.values()):
            name += " ("+number_+")"
        project.baselines[key] = Baseline(key, name, baseline_dates[number_], entries)
    if project.baselines:
        project.active_baseline = "xml-baseline-0" if "xml-baseline-0" in project.baselines else next(iter(project.baselines))
        if any(not task_metadata[key].get("baseline_created") for entries in baseline_entries.values() for key in entries):
            warnings.append("Дата создания базовых планов без метаданных Desktop — дата импорта.")
    project.validate()
    inconsistent = sum(project.calendar.between(project.span(link.source)[link.kind[0] == "F"], project.span(link.target)[link.kind[1] == "F"]) < link.lag for link in project.dependencies)
    if inconsistent:
        warnings.append(f"Несогласованных по датам связей: {inconsistent}. Даты сохранены без автоматического перепланирования.")
    warnings.append("Переносятся поддержанные поля диаграммы, не все атрибуты MS Project/веб-сервиса. Сохраните исходный XML отдельно.")
    warnings.append("Обратный импорт XML в GanttPRO заблокирован сайтом. Перенос стрелок через CSV-мастер сайта проверяется отдельно от импорта CSV в Desktop.")
    return XmlImport(project, tuple(dict.fromkeys(warnings)), "GanttPRO XML" if ganttpro else "MS Project XML")
