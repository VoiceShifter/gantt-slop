# GanttPRO-shaped CSV import/export — 0.15

The CSV contract now comes from the **actual supplied GanttPRO XLSX table**, not the previous handcrafted eight-column shortcut. The source is a spreadsheet report; this does not claim that the website itself exported a native CSV file. The derived CSV preserves its 23 table columns, including the blank third header and the separate placement of group/task names. Branding/merged title rows are not task data and are excluded.

## Use

- **Import:** Файл → **Импорт GanttPRO CSV…** → select the headered CSV → review dates/hierarchy/counts/warnings → **Импортировать новым проектом** → Save `.gantt.json`.
- **Export:** Экспорт → **GanttPRO CSV · 23 поля** → review the table/warning → Export to `.csv`.
- **CSV (выбранные поля)** remains the separate general-purpose table export. It is not the 23-column project-import contract.

Review/Cancel does not change the current project. Acceptance honors existing Save/Discard/Cancel protection and starts a new, dirty project with no fabricated Undo history. Import never sets the CSV as the automatic Save destination. The source is not overwritten. Native Save/reopen and subsequent edits/Undo retain imported metadata.

## Exact columns

| Position | Header | Meaning |
|---|---|---|
| A | Цвет | `#rrggbb`; spreadsheet fill must become data in plain CSV |
| B | Структура задач | WBS, e.g. `1`, `1.1`; retained as text |
| C | *(empty header)* | Group name; ordinary task/milestone rows leave this empty |
| D | Наименование задач | Task/milestone name; group rows leave this empty |
| E | Исполнитель | Resource names; comma/quote/newline names use a quoted inner CSV list |
| F | Дата начала | Local civil date/time |
| G | Дата окончания | Local civil date/time |
| H | Крайний срок | Optional date-only deadline |
| I | Прогресс (%) | Numeric percentage 0–100 |
| J | Длительность (часы) | Working duration in hours, not effort |
| K | Трудозатраты в часах | Total task effort |
| L | Затраченное время (минуты) | Retained source metadata, not a new actual-time journal |
| M | Статус | Открыт / В работе / Выполнено / Закрыт; blank for groups |
| N | Приоритет | Existing five priority labels; blank for groups |
| O | Описание задачи | Literal description, with quoting/newlines preserved |
| P | Предшественник | Incoming WBS references; **not description text** |
| Q | Стоимость | Planned task cost |
| R | Фактическая стоимость | Retained source metadata, independent of planned cost |
| S | Создан | Retained creation timestamp text |
| T | Создатель | Retained author text; not an account/service identity |
| U | Тип | `проект` = group, `задача` = task, `веха` = milestone |
| V | Проект | Project/ancestor-name path; verified against WBS hierarchy |
| W | Уровень | One-based hierarchy level |

Dates export as `YYYY-MM-DD HH:MM:SS`, preserving the times contained in the spreadsheet's Excel serials. Deadline exports as an ISO date. Imported creation strings are retained rather than replaced with the current time. Numbers preserve zero versus unset, and names preserve source whitespace (including the supplied artist's trailing space).

The parser accepts UTF-8/BOM, BOM-marked UTF-16 and Windows-1251, with comma/semicolon/tab delimiters. The header and all 23 positions must match. ISO and `DD.MM.YYYY [HH:MM[:SS]]` dates, plus modern raw Excel serial dates, are supported. Date-only task inputs use 09:00/18:00 defaults and still must agree with duration/calendar; preserve full clock times when converting the workbook.

CSV uses standard quoting and UTF-8 BOM. Formula-like strings are apostrophe-protected reversibly, including literal leading apostrophes. No formulas/macros are executed. The supplied originals are never rewritten.

## Real dependencies and scheduling

`Предшественник` contains actual graph references. Import creates `Dependency` records and the existing Gantt renderer draws editable arrows.

- The supplied `1.1` reference means **FS / lag 0**. All **14 supplied references** were compared with the paired XML, where all are FS with zero lag.
- Bare references cannot reveal a different type/lag omitted by the producer. The import report states the FS/0 assumption explicitly.
- Desktop retains nondefault supported relations in the same column as `1.1 SS`, `1.1 FS +7m`, or `1.1 FF -7m`. This is a documented Desktop extension for whole **working-minute** lag, not a claim that the website consumes that syntax.
- Multiple references are comma-separated inside the quoted cell. Missing endpoints, duplicates, hierarchy cycles and unsupported relation syntax fail the import rather than becoming notes or disappearing.
- Imported dates are not propagated/rescheduled. Inconsistent dependency dates are reported. Project working duration and explicit endpoints must be representable under the available calendar; unsupported dates fail before replacing the current project.

The source table has no calendar definitions. Import explicitly uses Monday–Friday, 09–13/14–18, and default 8h/day resource capacity. Summary dates/effort/cost/progress remain derived from children. Conflicting group boundaries are rejected; differing numeric group totals are reported as recalculated.

## Preservation and boundaries

Source L/R/S/T values are stored in four persistent **text custom fields** with stable IDs (`ganttpro_spent_minutes`, `ganttpro_actual_cost`, `ganttpro_created`, `ganttpro_creator`). Text avoids silently replacing source group values with numeric rollups. They can be inspected/edited through existing custom-field controls and re-export into the original columns. Numeric/timestamp metadata is validated on export so invalid edits do not produce an unreadable CSV. This does not implement time tracking, cost accounting or an account system.

The table does **not** carry complete native project state: project/resource calendars, resource capacity/color/vacations, unused roster members, unequal assignment shares, baselines or arbitrary custom-field definitions/values. The export warning remains visible outside the settings scroller. Keep `.gantt.json` for a complete project backup. Native JSON remains **schema 8**; this feature adds no runtime dependency or schema bump.

This update verifies **Desktop CSV import/export**, not full GanttPRO-site round-tripping. The inspected website CSV wizard did not expose a dependency destination, even though its spreadsheet export contains predecessor references. Do not equate a populated column with successful website arrow creation.

## Verification

- **834 passing tests**, including **102 CSV checks** (95 additional cases versus 0.14); Ruff clean.
- Sanitized fixture copied from the supplied 23-column table, with only the author replaced by synthetic text; the user's XLSX/XML/derived CSV remain untouched and uncommitted.
- Import/export reproduces **every fixture cell**, not merely its visible rows: 20 elements (4 groups, 15 tasks, 1 milestone), 14 links, 3 assigned resource entities, 212 task effort hours and 38,000 task cost.
- Every task/group/milestone date pair, type and hierarchy level was checked against the paired XML. Sensor remains **11 December 2025 09:00 → 15 December 2025 18:00**, with **8 effort hours** from the spreadsheet rather than the XML's misleading 8-minute Work encoding.
- All four endpoint types and ±7-minute lag, minute-duration rounding, status, quoted names/newlines, formula/literal-apostrophe safety, all four retained metadata columns, delimiter/encoding variants, strict invalid-data/limit rejection, native themes/dialog lifecycle, dirty-work protection, a real rendered-arrow click opening its dependency editor, Undo and Save/reopen are covered.
- GUI verification uses private Xvfb + Qt offscreen/software rendering, never the user's physical desktop. Website compatibility, Windows/macOS and comprehensive large-project/high-DPI/accessibility QA are not inferred from these tests.

Package: `dist/gantt_desktop-0.15.0-py3-none-any.whl`. All **34 packaged Python/QML files** matched source bytes. A temporary installed-wheel probe checked the **actual supplied user CSV cell-for-cell**, not only the sanitized fixture. It passed native menu/review/accept in both themes, 14 rendered arrows, a real arrow click opening the dependency editor, a real task drag with complete Undo, all six exports, and native Save/reopen. No QML runtime errors, global installation or real-settings changes.

Reviewed installed-package images: [light review](screenshots/csv-import-light.png), [dark review](screenshots/csv-import-dark.png), [imported diagram and totals](screenshots/csv-import-diagram.png), [clicked dependency editor](screenshots/csv-dependency-editor.png), [23-column export preview](screenshots/csv-export-table.png).
