# Gantt Desktop

An independent **Python + PySide6 / Qt Quick** desktop task and Gantt editor. This is a new application, not a patch, port, or wrapper around GanttProject. Its visual/interaction reference is the user-provided synthetic GanttPRO diagram, inspected through the browser. No GanttPRO application code, logos, fonts, or other downloaded assets are included.

**Scope: tasks, Gantt and project-local resource workload.** No Board, account system, comments service, portfolios or cross-project workload application.

**0.15 replaces the CSV shortcut with the supplied GanttPRO table:** exact 23-column headers/order, a native CSV import review, real predecessor links/arrows, hierarchy/type/level, colors, times, effort/cost/status/priority and retained source metadata. Import/re-export reproduces every reference-table cell; all 14 supplied links are checked against XML. [CSV contract, use and limits](docs/CSV.md). This supersedes the eight-column 0.14 preset; it is not a claim that the website accepts every field.

**0.14 adds file transfer:** native GanttPRO/MSPDI XML import with hierarchy/date/link review, explicit fidelity warnings and safe new-project Save; imported weekly working intervals; and a dedicated GanttPRO CSV export preset verified through its public import wizard. **This is not lossless interchange: GanttPRO rejects XML imports and its CSV import does not create dependency arrows.** [Routes, mapping and limits](docs/INTERCHANGE.md).

**0.13 adds persistent baseline snapshots:** capture/select/delete named original plans, immutable captured dates by task ID, grey comparison bars, read-only baseline/deviation fields, calendar-hour differences and all-format export. Selecting a baseline never restores task dates. [Baselines](docs/BASELINES.md).

**0.12 adds critical-path analysis:** a read-only toolbar overlay, working-time total float in task properties, exact min/max summary endpoint handling, critical dependencies and independent PDF/PNG highlighting. Analysis uses the whole current plan; it does not reschedule tasks or level resources. [Rules, limits and verification](docs/CRITICAL_PATH.md).

**0.11 adds dated calendar exceptions:** editable project holidays/working intervals and resource vacations/daily capacity ranges, overlap validation, independent availability warnings, atomic scheduling/history and export. [Calendar exceptions](docs/CALENDAR_EXCEPTIONS.md).

**0.10 adds native task-date calendars and independent deadlines:** calendar buttons in properties/table, explicit Apply/Cancel, a “Крайний срок” field/column, warnings/diagram flags and export support. Deadlines never reschedule tasks. [Dates and deadlines](docs/DATES_AND_DEADLINES.md). The remaining work is tracked in the [parity plan](docs/PARITY_PLAN.md).

**0.9 adds a real export preview:** full-diagram PDF/PNG, paged paper sizes/orientation, selected fields/range/scale, optional workload, typed Excel, MS Project XML and CSV. No application-window capture. [Export](docs/EXPORT.md).

**0.8 replaces free-text assignees with roster dropdowns** in the table, task properties and bulk editor: multiple people, local search, Reset/OK, explicit resource creation and native per-person hours. [Assignee picker](docs/ASSIGNEES.md).

**0.7 makes the header + functional:** show/hide standard columns and create project-local fields of nine types, with typed editors, numeric group rollups, rename/delete, JSON persistence, CSV and Undo/Redo. [Custom fields](docs/CUSTOM_FIELDS.md).

**0.6 adds individually resizable table columns and fixes the creation row:** “Добавить задачу / Добавить веху” stays centered inside the Task column in narrow and wide layouts. [Columns and verification](docs/COLUMNS.md).

**0.5 adds Settings → “Тёмная тема”:** one saved light/dark choice for the workspace, panels, menus and QWidget dialogs. Light is the default; switching is immediate and never modifies the project. [Themes and settings](docs/THEMES.md).

0.4.1 introduced platform-styled `QDialog`/`QMessageBox` editors, confirmations and help, with standard controls/system fonts. [Native dialogs](docs/NATIVE_DIALOGS.md).

**0.4 adds people as persistent entities and the bottom “Загрузка ресурсов” panel:** multi-person assignments, daily capacity, overload/weekend warnings and working-day settings. [Resource usage and verification](docs/RESOURCES.md).

0.3 introduced [task/summary dependency arrows and anchored resizing](docs/DEPENDENCY_ARROWS.md).

0.2 introduced [checkbox bulk editing, status/priority and row reordering/nesting](docs/SELECTION_AND_ROWS.md).

## Run

Python **3.11+** is required. From this directory:

```sh
python -m venv .venv
# Linux / macOS:
. .venv/bin/activate
# Windows PowerShell instead:
# .venv\Scripts\Activate.ps1

python -m pip install -e ".[test]"
python -m gantt_desktop
```

On the current development machine, PySide6 and defusedxml are already installed, so this also works without setting up another environment:

```sh
cd gantt-desktop
python3 -m gantt_desktop
```

Open a saved project with `python -m gantt_desktop path/to/project.gantt.json`.

The initial project is a disposable device-planning example. **Use Save / Ctrl+S to persist edits**; closing a modified project offers Save / Discard / Cancel. This version does not silently autosave to the source project or use the old application's file format.

## Implemented

- Light/dark split grid/timeline, cyan **#50c7d6** task/summary bars, orange connectors, magenta milestones, blue assignee badges, compact toolbar, and a right-side task editor.
- “⚙ Настройки” in the top bar opens an appearance panel with a real Light/Dark switch; the local preference is restored on startup.
- Nested groups and tasks, milestones, collapse/expand, inline table editing, per-group creation, deletion with confirmation, and grip-based row reordering/nesting with preview, Escape and auto-scroll.
- Dates/times, working duration, separate effort, cost, resource assignments, notes, synchronized status/progress, five priority levels and task colors.
- Native calendar pickers for task start/finish, preserving time and scheduling constraints; explicit Apply/Cancel and atomic Undo/Redo.
- Optional date-only deadlines independent of the schedule, including groups/milestones, a standard column, expired/planned-miss warnings, chart flags and PDF/PNG/Excel/CSV/XML export.
- Project-local people with stable IDs, create/rename/delete, individual capacity/workdays, multi-person effort allocation and migration of existing assignee names.
- Native holiday/exception range editors: project dates override weekdays with zero or one/two working intervals; resource ranges override daily capacity, including zero-hour vacations, without moving tasks.
- Assignees are selected from an anchored checkbox roster, not typed as names; search only filters. Resource creation is explicit, and opening/cancelling a draft makes no assignment/history changes.
- Platform-styled Qt Widgets modal dialogs with standard input controls, system fonts, window decorations, keyboard handling and parent-window modality; their palette follows the same app theme as the Gantt.
- Collapsible/resizable workload below the Gantt, synchronized zoom/panning, green normal load, red overload, weekend/nonworking warnings, Hours/Percent/Tasks modes and expandable assigned-task bars.
- Checkbox/group/select-all bulk editing with explicit Apply/Cancel and one-step Undo; protected deletion never removes an unchecked child through a partially selected parent.
- Body movement for unconstrained tasks and groups; dependency-anchored tasks give an explanatory message instead of silently breaking their links.
- Edge resizing, progress-handle dragging, live non-mutating date previews, three-pixel drag threshold, rapid select-then-drag, double-click inspection, and Escape cancellation.
- Reachable endpoint circles on tasks, milestones and summary groups; drag or click-pair creation, live preview, edge auto-scroll, FS/SS/FF/SF, positive/negative working-hour lag and multiple predecessors.
- Click an arrow to edit its type/lag or delete it; stable link IDs, anchored endpoint protection, hierarchy-aware cycle rejection and one-step Undo.
- Downstream rescheduling with preserved working durations; derived group dates/effort/cost/progress.
- Current-plan critical tasks, milestones, groups and dependency arrows; working-time float under FS/SS/FF/SF and signed lags, including summary min/max alternatives. The view is non-mutating, global across filters/collapse, and reports unavailable analysis instead of partial guesses when its exact-search budget is exceeded.
- Whole-transaction Python undo/redo, including every task changed by propagated scheduling; no-op/invalid edits do not create history entries.
- Named baselines stored in the project independently of Undo: captured task/group/milestone dates and kinds, persistent selected reference, grey chart comparison and four read-only date/calendar-hour deviation columns. New elements have no invented baseline values; deleted entries remain archived in the snapshot.
- Zoom, timeline panning, horizontal/vertical scrolling, adjustable table/timeline divider, optional columns, search and completion/overdue filters.
- Drag any column's right header boundary to resize it independently; headers/cells stay aligned, minimum widths and clipping prevent overlap, and the workload split follows the table.
- Header + / “Поля” opens a native field picker. User fields support Text, Number, Date, List, Checkbox, Color, Multi-select, People and Labels, with validation and independent values; numbers sum/average terminal tasks without double-counting groups.
- Native XML import review for GanttPRO/MSPDI task trees, dates, calendars and supported metadata; all four link types and signed working-minute lag; accepted imports are new unsaved projects, never automatic overwrites of the XML source.
- GanttPRO-shaped 23-column CSV import/export, based on the supplied real spreadsheet table: real predecessor references, colors, hierarchy/type/level, dates with times, resource names, progress/status/priority, effort, cost, deadlines and descriptions. Desktop import creates editable arrows; nondefault link types/lags retain a documented minute syntax. Source spent-time/actual-cost/creation/author values persist as text custom fields. Warnings distinguish unsupported project state from fields present in the table.
- Versioned JSON save/load and a dirty indicator; independent full-diagram PDF/PNG export with vector preview, paged paper sizes/orientation, label/style/date/range/field controls and optional resource workload.
- Excel `.xlsx` with real numbers/booleans/dates, hierarchy and optional workload sheet; MS Project XML with calendars/links/assignments and custom metadata in Notes; CSV remains available.

### Gestures

| Action | Input |
|---|---|
| Select | Click a row/bar |
| Appearance | Top “⚙ Настройки” → “Тёмная тема”; applies immediately and persists locally |
| Bulk edit | Toolbar ☑, then row/group checkboxes; Ctrl+A selects the current filter; Apply commits |
| Resource workload | Click “Загрузка ресурсов” in the bottom bar; drag its top divider to resize |
| People and calendars | Bottom “Люди…” or a person's workload calendar button |
| Project holidays / special hours | “Люди…” → “Праздники и исключения…” → Add/Edit → Save |
| Resource vacations / dated capacity | Select a saved person → “Отпуска и исключения…” → Add/Edit → Save |
| Multiple assignees | Click Assignee in the table/properties → check people → Ок |
| Assignment hours | Picker “Часы…” or task-properties ⋯ → native allocation draft → Apply |
| New resource | Picker “＋ Добавить ресурс…” → explicit native form Save; then select it |
| Reorder/nest rows | Drag the six-dot left grip; use row edges or a group's name area |
| Edit name/field | Click the table cell |
| Choose/create columns | Header + or “Поля”; select Standard/Custom, create/edit/delete fields |
| Edit a custom value | Click its cell; checkboxes also toggle directly; “Не задано” clears a value |
| Resize a column | Drag its right header boundary; Escape restores the pre-drag widths |
| Reset column widths | “Вид” → “Сбросить ширину таблицы” |
| Inspect task | Double-click bar; or select then Enter |
| Choose task date | Calendar button in Start/Finish in properties or visible table columns → choose → Apply |
| Deadline | Properties “Крайний срок” or Fields → Standard → “Крайний срок”; calendar or typed date; × clears |
| Move free task/group | Drag the body |
| Change task boundary | Drag an unanchored edge; FS/SS fix the start, FF/SF fix the finish |
| Change progress | Hover, then drag the small marker below the bar |
| Add dependency | Hover a bar, then drag a side circle to the target's start/finish circle; works on groups too |
| Alternative creation | Click source then target circles; Escape cancels |
| Edit/delete dependency | Click its orange connector or use task properties |
| Pan | Drag empty chart space |
| Zoom | Slider or Ctrl+wheel |
| Scroll horizontally | Horizontal scrollbar or Shift+wheel |
| Baselines | Header “Базовые планы” (▱ in a narrow window) → capture/select/hide/delete; comparison columns are in Fields |
| Critical path | Toolbar ⌁ → red critical elements/arrows; task properties show working-hour float; toggle off restores original colors |
| Import XML | “Файл” → “Импорт GanttPRO / MS Project XML…” → review/warnings → import as new → Save .gantt.json |
| Import/export GanttPRO CSV | “Файл” → “Импорт GanttPRO CSV…”; export format “GanttPRO CSV · 23 поля”; retain the header and blank third column |
| Export | “Экспорт” → preview/settings → format → choose a local destination; PDF/PNG also offer a critical-path checkbox |
| Cancel gesture | Escape |
| Undo / redo | Toolbar or platform-standard shortcuts |

The default working calendar is Monday–Friday, 09:00–13:00 and 14:00–18:00. Task times are local civil/project times, not UTC timestamps. Project working weekdays and each person's availability are editable through “Люди…”. Dated project exceptions override weekdays/legacy holidays; native editors support nonworking ranges and up to two same-day working intervals. Resource exceptions override available daily hours; dates closed for the project show zero project capacity. Workload warnings are diagnostic and do not silently move tasks to resolve conflicts.

### Project-file compatibility

New saves use **schema 8**, retaining imported per-weekday working intervals. Schema-1/2/3/4/5/6/7 files remain readable with their existing data; absent new fields keep the default calendar. Older assignee names still migrate to shared resources, and schema-7 baselines remain intact. App versions through 0.13 cannot read schema 8; keep a separate copy before saving with 0.14. The critical-path toggle and computed reserves remain window-local, not project data.

Native `.gantt.json` is desktop-specific. Use the separate [XML/CSV transfer workflows](docs/INTERCHANGE.md) and [23-column CSV contract](docs/CSV.md) for GanttPRO; it does not preserve all project data or automatically recreate website links.

## Tests and native screenshots

```sh
python -m pytest -q
```

For isolated Linux GUI automation (no interaction with the physical desktop):

```sh
./tools/isolated-gui.sh python3 -m pytest -q

./tools/isolated-gui.sh python3 -m gantt_desktop --size 1920x960 \
  --screenshot docs/screenshots/overview-current.png
```

The wrapper creates a private Xvfb display, forces Qt's **offscreen** plugin/software renderer and removes desktop-session variables. Tests also force offscreen themselves and refuse an onscreen QApplication, including background-runner invocation. A desktop user does **not** need this wrapper to launch the app normally.

The current suite has **834 passing tests**, including 95 additional CSV application checks in 0.15 and 70 XML/import/calendar/transfer cases from 0.14, 66 baseline and 71 critical-path and 79 calendar-exception, 22 task-calendar and 36 deadline regressions, as well as 52 export, 19 assignee-picker, 67 custom-field, 25 column/layout and 22 theme/settings regressions. See [dependency verification](docs/DEPENDENCY_ARROWS.md), [0.2 selection/row verification](docs/SELECTION_AND_ROWS.md), [reference observations](docs/REFERENCE.md) and the [historical baseline verification](docs/VERIFICATION.md).

## Code map

- `gantt_desktop/domain.py`: Qt-independent calendar, hierarchy, dependencies and mutations.
- `gantt_desktop/controller.py`: Qt list model, atomic edits, Python snapshot history, filtering and file operations.
- `gantt_desktop/critical_path.py`: read-only current-plan float analysis, DAG passes and exact bounded summary alternatives.
- `gantt_desktop/workload.py`: working-time effort distribution and daily resource availability/warnings.
- `gantt_desktop/dialogs.py`: platform-styled QWidget dialogs and QML/window lifecycle bridge.
- `gantt_desktop/field_dialogs.py`: native field picker, definition and typed-value editors.
- `gantt_desktop/date_dialog.py`: native calendar draft for start/finish/deadline dates.
- `gantt_desktop/calendar_dialog.py`: native project/resource exception lists and transactional range editors.
- `gantt_desktop/baseline_dialog.py`: native persistent snapshot capture/selection/deletion manager.
- `gantt_desktop/xml_import.py`, `xml_dialog.py`: bounded/offline MSPDI parsing, GanttPRO profile mapping and shared transactional XML/CSV native import review.
- `gantt_desktop/ganttpro_csv.py`: exact supplied 23-column table schema, bounded CSV parsing, dependency/resource/metadata mapping and reversible literal-safe writing.
- `gantt_desktop/theme.py`: shared light/dark tokens, application/widget palette and local `QSettings` preference.
- `gantt_desktop/exporting.py`, `interchange.py`, `export_dialog.py`: frozen export snapshots, shared vector rendering, atomic format writers and native preview/settings.
- `gantt_desktop/qml/`: native Qt Quick interface and direct manipulation.
- `gantt_desktop/sample.py`: independent synthetic fixture based on visible sample labels/dates.
- `tests/`: scheduling, transaction, persistence and real Qt mouse/keyboard regressions.

## Parity boundary

This is a working implementation, **not a claim of complete GanttPRO parity**. Still pending: multi-row dragging, arbitrary multi-bar date gestures, recurring/overnight or resource time-of-day shift editing, baseline restoration/cost tracking, richer scheduling modes/constraints, full date-scale/header parity, direct native-printer integration, large-project virtualization, and comprehensive accessibility/high-DPI QA. The inspected reference checkbox mode edits bulk properties, not task dates. Less-common dependency editing behaviors still need further live-reference parity testing.

Qt supports Windows, macOS and Linux, but this checkout has only been run and tested on **Linux**. Windows/macOS installation bundles, signing and platform QA have not been produced. When distributing the app, observe PySide6/Qt and other dependency licensing requirements.
