# Gantt Desktop

An independent **Python + PySide6 / Qt Quick** desktop task and Gantt editor. This is a new application, not a patch, port, or wrapper around GanttProject. Its visual/interaction reference is the user-provided synthetic GanttPRO diagram, inspected through the browser. No GanttPRO application code, logos, fonts, or other downloaded assets are included.

**Scope: tasks and Gantt only.** No Board, account system, comments service, portfolios, or resource-workload application.

**0.3 fixes dependency-handle interaction and adds summary-group arrows, anchored endpoint resizing and drag auto-scroll.** [Arrow overview](docs/screenshots/dependency-arrows.png) · [Arrow controls and verification](docs/DEPENDENCY_ARROWS.md).

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
- Dates/times, working duration, separate effort, cost, assignee text, notes, synchronized status/progress, five priority levels and task colors.
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

The default working calendar is Monday–Friday, 09:00–13:00 and 14:00–18:00. Task times are local civil/project times, not UTC timestamps. JSON can persist explicit holiday dates; a calendar-settings UI is not implemented yet.

### Project-file compatibility

New saves use **schema 2** for status/priority metadata. Schema-1 projects from the 0.1 baseline remain importable, with status derived from progress and priority defaulting to Medium. The old baseline cannot read schema 2; keep a separate copy if you still need its format. Summary dependencies require application 0.3 or later; the JSON structure remains schema 2.

## Tests and native screenshots

```sh
python -m pytest -q
```

For isolated Linux GUI automation (no interaction with the physical desktop):

```sh
xvfb-run -a -s '-screen 0 1920x1080x24 -nolisten tcp' \
  env QT_QUICK_BACKEND=software QT_QPA_PLATFORMTHEME=generic \
  python -m pytest -q

xvfb-run -a -s '-screen 0 1920x1080x24 -nolisten tcp' \
  env QT_QUICK_BACKEND=software QT_QPA_PLATFORMTHEME=generic \
  python -m gantt_desktop --size 1920x960 \
  --screenshot docs/screenshots/overview-current.png
```

Qt tests use an offscreen platform when Linux has no display; Xvfb is preferred for real-window/input checks. A desktop user does **not** need Xvfb to run the application.

The current suite has **158 passing tests**, including 45 native input tests. See [dependency verification](docs/DEPENDENCY_ARROWS.md), [0.2 selection/row verification](docs/SELECTION_AND_ROWS.md), [reference observations](docs/REFERENCE.md) and the [historical baseline verification](docs/VERIFICATION.md).

## Code map

- `gantt_desktop/domain.py`: Qt-independent calendar, hierarchy, dependencies and mutations.
- `gantt_desktop/controller.py`: Qt list model, atomic edits, Python snapshot history, filtering and file operations.
- `gantt_desktop/qml/`: native Qt Quick interface and direct manipulation.
- `gantt_desktop/sample.py`: independent synthetic fixture based on visible sample labels/dates.
- `tests/`: scheduling, transaction, persistence and real Qt mouse/keyboard regressions.

## Parity boundary

This is a working implementation, **not a claim of complete GanttPRO parity**. Still pending: multi-row dragging, arbitrary multi-bar date gestures, calendar configuration UI, baselines/critical-path UI, richer scheduling modes/constraints, full date-scale/header parity, full-project PDF/printing, large-project virtualization, and comprehensive accessibility/high-DPI QA. The inspected reference checkbox mode edits bulk properties, not task dates. Less-common dependency editing behaviors still need further live-reference parity testing.

Qt supports Windows, macOS and Linux, but this checkout has only been run and tested on **Linux**. Windows/macOS installation bundles, signing and platform QA have not been produced. When distributing the app, observe PySide6/Qt and other dependency licensing requirements.
