# Gantt Desktop

An independent **Python + PySide6 / Qt Quick** desktop task and Gantt editor. This is a new application, not a patch, port, or wrapper around GanttProject. Its visual/interaction reference is the user-provided synthetic GanttPRO diagram, inspected through the browser. No GanttPRO application code, logos, fonts, or other downloaded assets are included.

**Scope: tasks, Gantt and project-local resource workload.** No Board, account system, comments service, portfolios or cross-project workload application.

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

On the current development machine, PySide6 is already installed, so this also works without setting up another environment:

```sh
cd gantt-desktop
python3 -m gantt_desktop
```

Open a saved project with `python -m gantt_desktop path/to/project.gantt.json`.

The initial project is a disposable device-planning example. **Use Save / Ctrl+S to persist edits**; closing a modified project offers Save / Discard / Cancel. This version does not silently autosave to the source project or use the old application's file format.

## Implemented

- White split grid/timeline, cyan **#50c7d6** task/summary bars, orange connectors, magenta milestones, blue assignee badges, compact toolbar, and a right-side task editor.
- Nested groups and tasks, milestones, collapse/expand, inline table editing, per-group creation, deletion with confirmation, and grip-based row reordering/nesting with preview, Escape and auto-scroll.
- Dates/times, working duration, separate effort, cost, resource assignments, notes, synchronized status/progress, five priority levels and task colors.
- Project-local people with stable IDs, create/rename/delete, individual capacity/workdays, multi-person effort allocation and migration of existing assignee names.
- Collapsible/resizable workload below the Gantt, synchronized zoom/panning, green normal load, red overload, weekend/nonworking warnings, Hours/Percent/Tasks modes and expandable assigned-task bars.
- Checkbox/group/select-all bulk editing with explicit Apply/Cancel and one-step Undo; protected deletion never removes an unchecked child through a partially selected parent.
- Body movement for unconstrained tasks and groups; dependency-anchored tasks give an explanatory message instead of silently breaking their links.
- Edge resizing, progress-handle dragging, live non-mutating date previews, three-pixel drag threshold, rapid select-then-drag, double-click inspection, and Escape cancellation.
- Reachable endpoint circles on tasks, milestones and summary groups; drag or click-pair creation, live preview, edge auto-scroll, FS/SS/FF/SF, positive/negative working-hour lag and multiple predecessors.
- Click an arrow to edit its type/lag or delete it; stable link IDs, anchored endpoint protection, hierarchy-aware cycle rejection and one-step Undo.
- Downstream rescheduling with preserved working durations; derived group dates/effort/cost/progress.
- Whole-transaction Python undo/redo, including every task changed by propagated scheduling; no-op/invalid edits do not create history entries.
- Zoom, timeline panning, horizontal/vertical scrolling, adjustable table/timeline divider, optional columns, search and completion/overdue filters.
- Versioned JSON save/load, a dirty indicator, CSV task export, and PNG export of the **current window**, not an entire off-screen project.

### Gestures

| Action | Input |
|---|---|
| Select | Click a row/bar |
| Bulk edit | Toolbar ☑, then row/group checkboxes; Ctrl+A selects the current filter; Apply commits |
| Resource workload | Click “Загрузка ресурсов” in the bottom bar; drag its top divider to resize |
| People and calendars | Bottom “Люди…” or a person's workload calendar button |
| Multiple assignees | Task properties → ⋯ beside the assignee; choose people and hours |
| Reorder/nest rows | Drag the six-dot left grip; use row edges or a group's name area |
| Edit name/field | Click the table cell |
| Inspect task | Double-click bar; or select then Enter |
| Move free task/group | Drag the body |
| Change task boundary | Drag an unanchored edge; FS/SS fix the start, FF/SF fix the finish |
| Change progress | Hover, then drag the small marker below the bar |
| Add dependency | Hover a bar, then drag a side circle to the target's start/finish circle; works on groups too |
| Alternative creation | Click source then target circles; Escape cancels |
| Edit/delete dependency | Click its orange connector or use task properties |
| Pan | Drag empty chart space |
| Zoom | Slider or Ctrl+wheel |
| Scroll horizontally | Horizontal scrollbar or Shift+wheel |
| Cancel gesture | Escape |
| Undo / redo | Toolbar or platform-standard shortcuts |

The default working calendar is Monday–Friday, 09:00–13:00 and 14:00–18:00. Task times are local civil/project times, not UTC timestamps. Project working weekdays and each person's availability are editable through “Люди…”. JSON also persists project holidays; a full holiday/exception calendar editor remains pending. Workload warnings are diagnostic and do not silently move tasks to resolve conflicts.

### Project-file compatibility

New saves use **schema 3** for resource entities, assignment IDs/shares and project/resource workdays. Schema-1/2 files remain importable: existing assignee names are migrated to shared resource records, while dates, effort, status and priority are retained. Older app versions cannot read schema 3; keep a separate copy if needed.

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

The current suite has **200 passing tests**, including 53 native Qt input tests. See [dependency verification](docs/DEPENDENCY_ARROWS.md), [0.2 selection/row verification](docs/SELECTION_AND_ROWS.md), [reference observations](docs/REFERENCE.md) and the [historical baseline verification](docs/VERIFICATION.md).

## Code map

- `gantt_desktop/domain.py`: Qt-independent calendar, hierarchy, dependencies and mutations.
- `gantt_desktop/controller.py`: Qt list model, atomic edits, Python snapshot history, filtering and file operations.
- `gantt_desktop/workload.py`: working-time effort distribution and daily resource availability/warnings.
- `gantt_desktop/qml/`: native Qt Quick interface and direct manipulation.
- `gantt_desktop/sample.py`: independent synthetic fixture based on visible sample labels/dates.
- `tests/`: scheduling, transaction, persistence and real Qt mouse/keyboard regressions.

## Parity boundary

This is a working implementation, **not a claim of complete GanttPRO parity**. Still pending: multi-row dragging, arbitrary multi-bar date gestures, full calendar exception/holiday editing, baselines/critical-path UI, richer scheduling modes/constraints, full date-scale/header parity, full-project PDF/printing, large-project virtualization, and comprehensive accessibility/high-DPI QA. The inspected reference checkbox mode edits bulk properties, not task dates. Less-common dependency editing behaviors still need further live-reference parity testing.

Qt supports Windows, macOS and Linux, but this checkout has only been run and tested on **Linux**. Windows/macOS installation bundles, signing and platform QA have not been produced. When distributing the app, observe PySide6/Qt and other dependency licensing requirements.
