# Verification of the first working implementation

## Environment and automated checks

- Linux; Python **3.12.3**, PySide6/Qt **6.11.1**, pytest **9.1.1**.
- **55 tests passed, exit code 0**: 25 domain tests, 17 controller/regression tests, and 13 real Qt mouse/keyboard tests.
- `ruff check gantt_desktop tests`: **all checks passed**.
- Python LSP probes were used during development. There is no configured QML language server on this host; empty QML diagnostics are not a clean gate. Actual QQmlApplicationEngine loading, captured Qt runtime diagnostics, and native input tests supply the QML verification instead.
- A local Python wheel built successfully with all **7 QML components** included: `dist/gantt_desktop-0.1.0-py3-none-any.whl`. This is a Python package, not a self-contained Windows/macOS installer.

The full test command was:

```sh
xvfb-run -a -s '-screen 0 1920x1080x24 -nolisten tcp' \
  env QT_QUICK_BACKEND=software QT_QPA_PLATFORMTHEME=generic \
  python3 -m pytest -q --tb=short
```

`QT_QPA_PLATFORMTHEME=generic` isolates test styling from the host desktop theme; it is not required for ordinary use.

## Real input coverage

Native tests send mouse/key events to the actual QQuickWindow; they do not simply call scheduling setters and infer that dragging works.

- Free leaf body drag and complete downstream propagation; real toolbar Undo/Redo restores the whole schedule.
- Rapid select-then-drag does not open properties; genuine double-click still does.
- Predecessor-anchored body drag gives a message without modifying dates or creating undo history.
- Right-edge resizing preserves start and effort and updates successors.
- Summary movement shifts children once and propagates to dependent phases.
- Escape discards a live drag preview before release.
- Progress handle dragging, endpoint-to-endpoint dependency creation, and Undo.
- Task creation followed by typing into the native inspector.
- Zoom changes, divider resizing, empty-chart panning, and search/clear with restored hierarchy.
- Qt runtime errors such as ReferenceError, TypeError, invalid assignments and binding loops are checked during these tests.

Additional tests cover weekends/holidays/lunch breaks, all four dependency types, lag, multiple predecessors, cycles, milestones, invalid-number rollback, whole-document history branching/dirty state, hierarchy validation, deletion, metadata-only edits, earlier-date range extension, and JSON save/reopen.

## Corrections caught by verification

- A progress handle initially disappeared when the pointer left the bar to reach it. Its hover lifetime was corrected; the real handle test now passes.
- The first Qt undo-command ownership approach crashed during garbage collection when controller and GUI suites ran together, despite individual assertions passing. Native debugging located the fault in `QUndoStack::clear()`. History is now a simpler Python snapshot/index model. The combined suite completes with **exit 0**, without disabling garbage collection, suppressing a crash, or forcing process exit.
- Tests wait for the inspector's actual opened/focus state before typing, rather than assuming that a visible-but-animating drawer is ready.

## Native evidence

All images are unscaled, unmasked **app-client** captures from private Xvfb, never the physical desktop. The standard `python -m gantt_desktop` launcher produced both overview sizes and exited successfully. The editor and drag captures use the same application/window factory and genuine native input.

| Evidence | What it establishes |
|---|---|
| [1920×960 overview](screenshots/overview-1920.png) | Complete synthetic project, cyan task/summary hierarchy, orange links, magenta milestone, assignee badges and matching light workspace structure |
| [1366×768 overview](screenshots/overview-1366.png) | Working smaller window; overflow uses real scrolling and the divider remains adjustable. Some cells/captions truncate; this is not a claim of perfect small-window parity. |
| [Task editor](screenshots/task-editor.png) | Fixed predecessor-controlled start, editable finish, duration 80h versus effort 10h, group and dependency controls |
| [Dependency editor](screenshots/dependency-editor.png) | Actual task/type/lag controls; no Save was submitted merely to capture the dialog |
| [Committed drag](screenshots/drag-moved.png) | Sensor moves to 22.12.2025; downstream final task ends 18.02.2026 |
| [Undo](screenshots/drag-undo.png) | Complete original schedule restored after that move |

The captured native interaction session ended with the original in-memory sample restored and did not save a project file. Browser reference mutations were likewise undone and checked against a freshly recorded baseline.

## What is not established

Full feature/visual parity, every FF/SF edit-boundary behavior, arbitrary task calendars/time zones, native file-dialog UX on all platforms, printing/full-range PDF export, very large-project performance, screen-reader completeness, high-DPI configurations, and Windows/macOS runtime/signing remain unverified or pending. See the README's explicit parity boundary. Passing tests are not a substitute for those remaining product checks.
