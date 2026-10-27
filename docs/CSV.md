# GanttPRO CSV and Excel import/export — 0.17

The CSV contract now comes from the **actual supplied GanttPRO XLSX table**, not the previous handcrafted eight-column shortcut. The source is a spreadsheet report; this does not claim that the website itself exported a native CSV file. The derived CSV preserves its 23 table columns, including the blank third header and the separate placement of group/task names. Branding/merged title rows are not task data and are excluded.

## Use

- **Import:** Файл → **Импорт GanttPRO CSV…** or **Импорт GanttPRO Excel…** → select the headered `.csv`/`.xlsx` → review dates/hierarchy/counts/warnings → **Импортировать новым проектом** → Save `.gantt.json`.
- **Export:** Экспорт → **GanttPRO CSV · 23 поля** or **GanttPRO Excel · 23 поля** → review the table/warning → Export to `.csv`/`.xlsx`.
- **CSV (выбранные поля)** and **Excel (выбранные поля)** remain separate general-purpose exports, not project-import contracts.
- For the website's wizard, use the separate **Подготовить для мастера импорта GanttPRO** option described below. It does not replace the 23-column report.

Review/Cancel does not change the current project. Acceptance honors existing Save/Discard/Cancel protection and starts a new, dirty project with no fabricated Undo history. Import never sets the CSV/XLSX as the automatic Save destination. The source is not overwritten. Native Save/reopen and subsequent edits/Undo retain imported metadata.

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

CSV report dates export as `YYYY-MM-DD HH:MM:SS`, preserving the times contained in the spreadsheet's Excel serials. Deadline exports as an ISO date. XLSX report dates are typed date/time cells; WBS and literal metadata remain text, while progress/duration/effort/cost/level are numbers. Imported creation strings are retained rather than replaced with the current time. Numbers preserve zero versus unset, and names preserve source whitespace (including the supplied artist's trailing space).

The parser accepts UTF-8/BOM, BOM-marked UTF-16 and Windows-1251, with comma/semicolon/tab delimiters. The recognized 23-column report or 25-column wizard header and every position must match. ISO and `DD.MM.YYYY [HH:MM[:SS]]` dates, plus modern raw Excel serial dates, are supported. Date-only task inputs use 09:00/18:00 defaults and still must agree with duration/calendar; preserve full clock times when converting the workbook.

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

## Direct Excel reader

The `.xlsx` reader finds exactly one recognized task table, including the actual GanttPRO report's row-5 header. It reads shared/inline/rich strings, numeric Excel dates (1900/1904 epochs), and RGB task-color fills. Title/branding rows are not tasks; the exact GanttPRO footer is ignored. No branding images or workbook macros are used. Local report and headered wizard exports can both be reimported; **a headerless file cannot be reimported into Desktop without restoring its exact headers**.

Parsing is offline ZIP/XML with `defusedxml`, without Excel, a converter or a new dependency. Formulas are rejected even when cached results exist. DTD/entities, macros, external workbook relationships, duplicate/ambiguous tables, malformed cells, invalid dates and unsafe package paths fail before project replacement. Bounds: 16 MiB input/per part, 64 MiB declared unpacked data, 256 archive entries, XML depth 64/250,000 nodes per part, 4,096 row numbers and 256 columns. Repeated sheet/part references and shared-string expansion cannot bypass the bounds. Task/graph validation reuses the CSV path (2,000 tasks, 10,000 links, outline depth 64, 100-year diagram).

## Separate website-wizard layout — 25 columns

This is an explicit **Desktop adaptation**, not a claim that GanttPRO exports 25 columns. Enable **Подготовить для мастера импорта GanttPRO** in either task-table format:

- Keep the 23 report positions, but duplicate a group's name into D so one website task-name mapping covers all rows.
- Write F/G as `DD.MM.YYYY`; append X **Время начала** and Y **Время окончания** as `HH:mm`.
- Supply derived group status and default medium priority for wizard value matching.
- Keep the whole hierarchy; workspace filters, custom field selections and graphical ranges do not truncate either task-table format.
- **Строка заголовков в файле** defaults on. If the website's header preview is blank, export this wizard layout with that option off and choose **В моем файле нет строки с заголовками** there. The Desktop preview still shows labels as mapping hints; they are not written to a headerless file.

Headered wizard tables reverse locally to the report semantics; conflicting duplicate group fields are rejected. The 23-column report always has headers, even if an irrelevant headerless option was passed programmatically.

### Tested public website procedure

1. Create a separately named project via **Создать новый проект → Импорт Excel, csv, mpp** and upload the wizard CSV/XLSX. The site's entry label does not imply MPP support in Desktop; **MPP work is discontinued**.
2. Choose the headerless setting only when the exported file actually has no header. In the observed wizard this advances directly to mapping.
3. Map by the **displayed data**, not a fixed screen index: the wizard hides all-empty columns.

   | Desktop field | Website destination / format |
   |---|---|
   | B Структура задач | Нумерация задач |
   | D Наименование задач (including duplicated groups) | Название задачи |
   | E Исполнитель | Исполнитель; match existing resources, without invitations |
   | F / G | Начало / Завершение, `DD.MM.YYYY` |
   | I / J / K | Прогресс / Длительность (**Часы**) / Трудозатраты |
   | M / N | Статус / Приоритет; review value matching |
   | Q / R | Стоимость / Фактическая стоимость |
   | X / Y | Время начала / Время окончания, `HH:mm` |

4. Skip fields without a supported destination. In this test, the all-zero spent-time column was rejected and skipped. Descriptions and deadlines were empty in the reference; their transfer was not established by this run.
5. Review zero-duration milestones, then import. Verify dates/times, effort/cost and assignments; **recreate missing dependencies manually**. Matching column names alone does not prove website fidelity.

## Observed website results — 27 October 2026

- CSV probe → disposable GanttPRO project → actual downloaded Excel report → Desktop: **20 elements (4 groups, 15 tasks, 1 milestone), 3 resources, 212 effort hours and 38,000 planned cost** retained. Task/group types, hierarchy, every date pair, progress and priority were compared. Sensor remained **11 December 2025 09:00 → 15 December 2025 18:00**, duration 24h / effort 8h.
- **All 14 predecessor values were lost.** The wizard had no predecessor destination. Milestone **2.3 Приобретение компонентов** also lost its **Клиент** assignment. Desktop imports that return as zero links and an unassigned milestone; it does not patch it with data from a different source.
- The final production exporter-generated, headerless **25-column XLSX** was also imported through the public wizard. Hierarchy/milestone, sensor dates/duration/effort and totals rendered correctly, but the milestone assignment was again missing. Its return download failed when the browser closed; **a second XLSX → site → XLSX file comparison is not claimed**. The live CSV upload used the earlier probe; the final production CSV writer is covered locally.
- Colors, deadlines and original authors are not mapped by this tested route. The source had no nonempty descriptions/deadlines to certify. Complete resource rosters/calendars/shares/baselines/custom fields are outside the table contract. This is **lossy transfer, not synchronization**.
- Both disposable projects were deleted by their exact names. The original project was reopened with totals 212h / 38,000 and the original milestone assignment still present; PDF export selection was unchanged. No original task was edited, and no resource invitation was sent. The all-fields browser checklist remains incomplete rather than falsely certifying lossless interchange.

The retained `tests/fixtures/ganttpro-return-table.xlsx` is the actual CSV-return table with author/project identifiers sanitized and top branding/drawing assets removed. It deliberately retains the missing links/assignment as regression evidence.

## Verification — 0.17

**953 tests pass**, including **64 new Excel/wizard checks**; Ruff passes. Coverage includes every local reference cell, typed numbers/dates, all four link types with signed lag, both formats/header modes, real return-file losses, Unicode/CRLF/SpreadsheetML escapes, formula/package/size rejection, atomic destination preservation, native light/dark review, dirty Cancel/Apply, editable arrows, Undo and JSON Save/reopen. GUI tests run on private Xvfb + Qt offscreen/software rendering, not the physical desktop. No new runtime dependency or JSON schema change.

An active LSP probe reported no errors in all 10 changed Python files. QML has no configured LSP; isolated engine/input/render checks cover the menu bridge. Heuristic numeric-parsing warnings are not treated as proof of runtime failure: parsing errors are handled by the outer import transaction.

Installed package: `dist/gantt_desktop-0.17.0-py3-none-any.whl` (SHA-256 `99b383481788b60067c91cc90fc59fb45d4044f9d78d5545945b152b275e5179`). All **36 packaged Python/QML files** matched source. A temporary isolated installation passed the actual QML menu/native review in both themes, Cancel/Apply, 14 local arrows and a real arrow-editor click, task drag/Undo, JSON Save/reopen, all seven export choices and both 25-column header modes. Independent **openpyxl 3.1.5** readback matched every reference-table cell and verified date/number/text types. Both the raw downloaded return and sanitized fixture imported with their actual losses. Source hashes stayed unchanged; no QML runtime errors, global installation or real preference changes. Openpyxl was temporary QA tooling, not a runtime dependency.

Reviewed installed-package images: [light review](screenshots/xlsx-import-light.png), [dark review](screenshots/xlsx-import-dark.png), [real return with zero links](screenshots/xlsx-return-review.png), [local imported diagram](screenshots/xlsx-import-diagram.png), [clicked dependency editor](screenshots/xlsx-dependency-editor.png), [25-column/headerless export and visible loss warning](screenshots/xlsx-wizard-export.png).

Windows/macOS runtime, exhaustive Office compatibility, large-project/high-DPI/accessibility QA and lossless website transfer remain unverified.

## Historical verification — 0.15

- **834 passing tests**, including **102 CSV checks** (95 additional cases versus 0.14); Ruff clean.
- Sanitized fixture copied from the supplied 23-column table, with only the author replaced by synthetic text; the user's XLSX/XML/derived CSV remain untouched and uncommitted.
- Import/export reproduces **every fixture cell**, not merely its visible rows: 20 elements (4 groups, 15 tasks, 1 milestone), 14 links, 3 assigned resource entities, 212 task effort hours and 38,000 task cost.
- Every task/group/milestone date pair, type and hierarchy level was checked against the paired XML. Sensor remains **11 December 2025 09:00 → 15 December 2025 18:00**, with **8 effort hours** from the spreadsheet rather than the XML's misleading 8-minute Work encoding.
- All four endpoint types and ±7-minute lag, minute-duration rounding, status, quoted names/newlines, formula/literal-apostrophe safety, all four retained metadata columns, delimiter/encoding variants, strict invalid-data/limit rejection, native themes/dialog lifecycle, dirty-work protection, a real rendered-arrow click opening its dependency editor, Undo and Save/reopen are covered.
- GUI verification uses private Xvfb + Qt offscreen/software rendering, never the user's physical desktop. Website compatibility, Windows/macOS and comprehensive large-project/high-DPI/accessibility QA are not inferred from these tests.

Package: `dist/gantt_desktop-0.15.0-py3-none-any.whl`. All **34 packaged Python/QML files** matched source bytes. A temporary installed-wheel probe checked the **actual supplied user CSV cell-for-cell**, not only the sanitized fixture. It passed native menu/review/accept in both themes, 14 rendered arrows, a real arrow click opening the dependency editor, a real task drag with complete Undo, all six exports, and native Save/reopen. No QML runtime errors, global installation or real-settings changes.

Reviewed installed-package images: [light review](screenshots/csv-import-light.png), [dark review](screenshots/csv-import-dark.png), [imported diagram and totals](screenshots/csv-import-diagram.png), [clicked dependency editor](screenshots/csv-dependency-editor.png), [23-column export preview](screenshots/csv-export-table.png).
