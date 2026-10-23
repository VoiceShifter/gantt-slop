# Gantt Desktop

An independent **Python + PySide6 / Qt Quick** desktop task and Gantt editor. This is a new application, not a patch, port, or wrapper around GanttProject. Its visual/interaction reference is the user-provided synthetic GanttPRO diagram, inspected through the browser. No GanttPRO application code, logos, fonts, or other downloaded assets are included.

**Scope: tasks and Gantt only.** No Board, account system, comments service, portfolios, or resource-workload application.

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
- Nested groups and tasks, milestones, collapse/expand, inline table editing, per-group creation, deletion with confirmation, sibling ordering, and reparenting through the editor.
- Dates/times, working duration, separate effort, cost, assignee text, notes, progress, and task colors.
- Body movement for unconstrained tasks and groups; dependency-anchored tasks give an explanatory message instead of silently breaking their links.
- Edge resizing, progress-handle dragging, live non-mutating date previews, three-pixel drag threshold, rapid select-then-drag, double-click inspection, and Escape cancellation.
- Endpoint-to-endpoint dependency dragging, FS/SS/FF/SF relationships, positive/negative working-time lag, multiple predecessors, dependency editing/deletion, and cycle rejection.
- Downstream rescheduling with preserved working durations; derived group dates/effort/cost/progress.
- Whole-transaction Python undo/redo, including every task changed by propagated scheduling; no-op/invalid edits do not create history entries.
- Zoom, timeline panning, horizontal/vertical scrolling, adjustable table/timeline divider, optional columns, search and completion/overdue filters.
- Versioned JSON save/load, a dirty indicator, CSV task export, and PNG export of the **current window**, not an entire off-screen project.

### Gestures

| Action | Input |
|---|---|
| Select | Click a row/bar |
| Edit name/field | Click the table cell |
| Inspect task | Double-click bar; or select then Enter |
| Move free task/group | Drag the body |
| Change task boundary | Drag left/right edge |
| Change progress | Hover, then drag the small marker below the bar |
| Add dependency | Drag a side circle to another task; clicking source then target circles also works |
| Edit dependency | Click its orange connector or use task properties |
| Pan | Drag empty chart space |
| Zoom | Slider or Ctrl+wheel |
| Scroll horizontally | Horizontal scrollbar or Shift+wheel |
| Cancel gesture | Escape |
| Undo / redo | Toolbar or platform-standard shortcuts |

The default working calendar is Monday–Friday, 09:00–13:00 and 14:00–18:00. Task times are local civil/project times, not UTC timestamps. JSON can persist explicit holiday dates; a calendar-settings UI is not implemented yet.

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
  --screenshot docs/screenshots/overview-1920.png
```

Qt tests use an offscreen platform when Linux has no display; Xvfb is preferred for real-window/input checks. A desktop user does **not** need Xvfb to run the application.

See [reference observations](docs/REFERENCE.md) and [verification/limits](docs/VERIFICATION.md).

## Code map

- `gantt_desktop/domain.py`: Qt-independent calendar, hierarchy, dependencies and mutations.
- `gantt_desktop/controller.py`: Qt list model, atomic edits, Python snapshot history, filtering and file operations.
- `gantt_desktop/qml/`: native Qt Quick interface and direct manipulation.
- `gantt_desktop/sample.py`: independent synthetic fixture based on visible sample labels/dates.
- `tests/`: scheduling, transaction, persistence and real Qt mouse/keyboard regressions.

## Parity boundary

This is a functional first implementation, **not a claim of complete GanttPRO parity**. Still pending: multi-selection/bulk drag, drag-and-drop row reordering (menu-based sibling moves already work), summary-task dependency links, calendar configuration UI, baselines/critical-path UI, richer scheduling modes/constraints, full date-scale/header parity, full-project PDF/printing, large-project virtualization, and comprehensive accessibility/high-DPI QA. Less-common dependency editing behaviors still need further live-reference parity testing.

Qt supports Windows, macOS and Linux, but this checkout has only been run and tested on **Linux**. Windows/macOS installation bundles, signing and platform QA have not been produced. When distributing the app, observe PySide6/Qt and other dependency licensing requirements.
