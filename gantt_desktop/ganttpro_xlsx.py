"""Bounded, offline reader for the GanttPRO 23-column Excel task table."""
from __future__ import annotations

import csv
import io
import posixpath
import re
import zlib
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import iterparse

from .ganttpro_csv import (
    HEADERS,
    MAX_BYTES,
    SITE_HEADERS,
    CsvImport,
    CsvImportError,
    literal,
    parse_project_csv,
)

SS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = {"s": SS}
MAX_UNPACKED = 64*1024*1024
MAX_NODES = 250000


class XlsxImportError(ValueError):
    pass


def read_project_xlsx(path: Path) -> CsvImport:
    with path.open("rb") as stream:
        return parse_project_xlsx(stream.read(MAX_BYTES+1), path.stem)


def _xml(archive: ZipFile, name: str):
    depth = count = 0
    root = None
    parser = iterparse(io.BytesIO(archive.read(name)), events=("start", "end"),
                       forbid_dtd=True, forbid_entities=True, forbid_external=True)
    for event, _node in parser:
        if event == "start":
            depth += 1
            count += 1
            if depth > 64 or count > MAX_NODES:
                raise XlsxImportError("Превышен предел вложенности/элементов XML внутри XLSX.")
        else:
            depth -= 1
            root = _node
    if root is None:
        raise XlsxImportError("Пустая XML-часть XLSX.")
    return root


def _string(node) -> str:
    # SpreadsheetML escapes are decoded once: _x005F_x0041_ is literal _x0041_.
    value = "".join(t.text or "" for t in node.findall("s:t", NS) + node.findall("s:r/s:t", NS))
    value = re.sub(r"_x([0-9a-fA-F]{4})_", lambda m: chr(int(m[1], 16)), value)
    # Excel may escape non-BMP characters as a UTF-16 surrogate pair.
    return value.encode("utf-16-le", errors="surrogatepass").decode("utf-16-le")


def _part(target: str) -> str:
    if not target or "\\" in target or ":" in target or ".." in target.split("/"):
        raise XlsxImportError("Недопустимый путь части XLSX.")
    result = target.lstrip("/") if target.startswith("/") else posixpath.join("xl", target)
    if not result.startswith("xl/"):
        raise XlsxImportError("Часть XLSX находится вне книги.")
    return result


def _date(value: str, date1904: bool) -> str:
    serial = Decimal(value)
    if not serial.is_finite() or serial < 0 or serial >= 2958466:
        raise XlsxImportError("Дата Excel вне поддержанного диапазона.")
    if not date1904 and 60 <= serial < 61:
        raise XlsxImportError("Фиктивная дата Excel 29.02.1900 не поддерживается.")
    epoch = datetime.fromisoformat("1904-01-01" if date1904 else "1899-12-30" if serial >= 61 else "1899-12-31")
    seconds = serial*86400
    rounded = round(seconds)
    if abs(seconds-rounded) > Decimal("0.001"):
        raise XlsxImportError("Дата Excel содержит доли секунды.")
    return (epoch+timedelta(seconds=rounded)).isoformat(sep=" ", timespec="seconds")


def _table(archive: ZipFile, name: str, strings: list[str], formats: list, fills: list, date1904: bool):
    root = _xml(archive, name)
    if root.tag != "{"+SS+"}worksheet":
        raise XlsxImportError("Неподдержанный лист XLSX.")
    records = []
    text_size = 0
    headers = None
    footer_seen = False
    seen_rows = set()
    for row in root.findall("s:sheetData/s:row", NS):
        index = int(row.get("r", "0"))
        if index < 1 or index > 4096 or index in seen_rows:
            raise XlsxImportError("Некорректный/повторяющийся номер строки XLSX или больше 4096 строк.")
        seen_rows.add(index)
        values, cells = [""]*len(SITE_HEADERS), {}
        extra_values = False
        for cell in row.findall("s:c", NS):
            address = re.fullmatch(r"([A-Z]{1,3})([1-9]\d*)", cell.get("r", ""))
            if address is None or int(address[2]) != index:
                raise XlsxImportError("Некорректный адрес ячейки XLSX.")
            column = 0
            for letter in address[1]:
                column = column*26+ord(letter)-64
            if column in cells or column > 256:
                raise XlsxImportError("Повторяющаяся ячейка или слишком много столбцов XLSX.")
            cells[column] = cell
            if cell.find("s:f", NS) is not None:
                raise XlsxImportError("Формулы XLSX не импортируются. Сохраните вычисленные значения отдельно.")
            kind = cell.get("t", "n")
            value = cell.findtext("s:v", "", NS)
            if kind == "s" and value:
                slot = int(value)
                if not 0 <= slot < len(strings):
                    raise XlsxImportError("Некорректная ссылка sharedStrings XLSX.")
                value = strings[slot]
            elif kind == "inlineStr":
                inline = cell.find("s:is", NS)
                value = _string(inline) if inline is not None else ""
            elif kind not in {"n", "s", "d", "str"}:
                raise XlsxImportError("Неподдержанный тип/ошибка ячейки XLSX.")
            if column > (len(headers) if headers else len(SITE_HEADERS)):
                if headers and value:
                    raise XlsxImportError("Лист содержит дополнительные поля вне таблицы GanttPRO.")
                extra_values = extra_values or bool(value)
                continue
            if headers and value and column in {6, 7, 8, 19} and kind == "n":
                value = _date(value, date1904)
                if (column == 8 or headers == SITE_HEADERS and column in {6, 7}) and value.endswith(" 00:00:00"):
                    value = value[:10]
            values[column-1] = value
        candidate = tuple(values) if any(values[23:]) else tuple(values[:23])
        if candidate in {HEADERS, SITE_HEADERS}:
            if extra_values:
                raise XlsxImportError("Строка заголовков содержит дополнительные поля.")
            if headers:
                raise XlsxImportError("Повторная строка заголовков XLSX.")
            headers = candidate
            continue
        if not headers:
            continue
        values = values[:len(headers)]
        if not any(values):
            continue
        if values[0] == "Этот документ был создан с помощью онлайн-сервиса https://ganttpro.com" and not any(values[1:]):
            footer_seen = True
            continue
        if footer_seen:
            raise XlsxImportError("После подписи GanttPRO обнаружены дополнительные данные.")
        if not values[0] and 1 in cells and (formats or cells[1].get("s")):
            style = int(cells[1].get("s", "0"))
            if not 0 <= style < len(formats):
                raise XlsxImportError("Неизвестный стиль цвета XLSX.")
            fill_id = int(formats[style].get("fillId", "0"))
            if not 0 <= fill_id < len(fills):
                raise XlsxImportError("Неизвестная заливка XLSX.")
            pattern = fills[fill_id].find("s:patternFill", NS)
            if pattern is not None and pattern.get("patternType") == "solid":
                color = pattern.find("s:fgColor", NS)
                rgb = color.get("rgb", "") if color is not None else ""
                if not re.fullmatch(r"(?:[0-9a-fA-F]{2})?[0-9a-fA-F]{6}", rgb):
                    raise XlsxImportError("Цвет задачи XLSX должен быть задан RGB, не темой/индексом.")
                values[0] = "#"+rgb[-6:].lower()
        text_size += sum(len(value) for value in values)
        if text_size > MAX_BYTES:
            raise XlsxImportError("Текст таблицы XLSX превышает допустимый предел.")
        records.append(values)
    return (headers, records) if headers else None


def parse_project_xlsx(data: bytes, fallback_name: str = "Импорт Excel") -> CsvImport:
    if len(data) > MAX_BYTES:
        raise XlsxImportError("XLSX превышает допустимые 16 MiB.")
    try:
        with ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if len(entries) > 256 or len(set(names)) != len(names) or sum(e.file_size for e in entries) > MAX_UNPACKED:
                raise XlsxImportError("Слишком большой XLSX-архив или повторяющиеся части.")
            if any(e.file_size > MAX_BYTES or e.flag_bits & 1 or e.compress_type not in {0, 8} for e in entries):
                raise XlsxImportError("Часть XLSX слишком велика, зашифрована или имеет неподдержанное сжатие.")
            if any(".." in n.split("/") or n.startswith("/") or "\\" in n for n in names):
                raise XlsxImportError("Недопустимый путь в XLSX-архиве.")
            if any(n.lower().endswith("vbaproject.bin") or "/externallinks/" in n.lower() for n in names):
                raise XlsxImportError("Макросы и внешние связи XLSX не поддерживаются.")
            workbook = _xml(archive, "xl/workbook.xml")
            relationships = _xml(archive, "xl/_rels/workbook.xml.rels")
            parts = {}
            targets = set()
            for relation in relationships:
                uid = relation.get("Id", "")
                target = _part(relation.get("Target", ""))
                if uid in parts or target in targets or relation.get("TargetMode") == "External":
                    raise XlsxImportError("Повторная/внешняя связь книги XLSX.")
                targets.add(target)
                parts[uid] = (target, relation.get("Type", ""))
            strings, formats, fills = [], [], []
            for name, kind in parts.values():
                if kind == REL+"/sharedStrings":
                    strings = [_string(node) for node in _xml(archive, name).findall("s:si", NS)]
                elif kind == REL+"/styles":
                    style = _xml(archive, name)
                    formats, fills = style.findall("s:cellXfs/s:xf", NS), style.findall("s:fills/s:fill", NS)
            properties = workbook.find("s:workbookPr", NS)
            date1904 = properties is not None and properties.get("date1904", "0") in {"1", "true"}
            tables = []
            seen_sheets = set()
            for sheet in workbook.findall("s:sheets/s:sheet", NS):
                name, kind = parts[sheet.get("{"+REL+"}id")]
                if kind != REL+"/worksheet":
                    continue
                if name in seen_sheets:
                    raise XlsxImportError("Повторная ссылка на лист XLSX.")
                seen_sheets.add(name)
                rows = _table(archive, name, strings, formats, fills, date1904)
                if rows is not None:
                    tables.append(rows)
            if len(tables) != 1:
                raise XlsxImportError("Ожидается ровно один лист с таблицей GanttPRO из 23 столбцов.")
            text = io.StringIO(newline="")
            writer = csv.writer(text)
            headers, rows = tables[0]
            writer.writerow(headers)
            writer.writerows([[literal(value) for value in row] for row in rows])
            report = parse_project_csv(text.getvalue().encode("utf-8"), fallback_name)
            return replace(report, profile=report.profile.replace("CSV", "Excel"),
                           warnings=tuple(w.replace("CSV", "XLSX") for w in report.warnings))
    except XlsxImportError:
        raise
    except CsvImportError as error:
        raise XlsxImportError(str(error).replace("CSV", "XLSX")) from error
    except (BadZipFile, ParseError, DefusedXmlException, InvalidOperation, ValueError, KeyError, TypeError, IndexError,
            OverflowError, RuntimeError, EOFError, zlib.error) as error:
        raise XlsxImportError("Повреждённый или неподдержанный XLSX: "+str(error)) from error
