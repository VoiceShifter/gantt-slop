# Shared application themes — 0.5.0

## Use

Open **⚙ Настройки** in the top bar and flip **Тёмная тема**:

- Off: light workspace and light Qt dialog client areas, including on a dark desktop.
- On: dark workspace and dark Qt dialog client areas.
- Changes apply immediately; close Settings with **Готово**, × or Escape.
- The choice is restored on the next launch. It is a local application preference, not project data; it does not dirty the project or enter Undo/Redo.

Settings currently contains only appearance. No placeholder controls or speculative preferences were added.

## Why the mismatch happened

The modal forms had been moved to standard QWidget dialogs, inheriting the OS/application palette. The QML workspace still used fixed white backgrounds and dark text. A dark system could therefore produce dark resource dialogs beside a white Gantt view.

`gantt_desktop/theme.py` now provides one light/dark selection, shared color tokens and a corresponding `QApplication` palette. The preference uses `QSettings`, under the application's existing GanttDesktop / Gantt Desktop identity, key `appearance/dark`. A missing preference defaults to light.

The selected scheme also updates Qt's color-scheme hint. The QWidget controls remain standard platform-styled widgets with system fonts, no custom widget stylesheets. QML menus, controls, task/bulk drawers, Settings, notifications, table/timeline and workload use the same selection. Both canvases explicitly repaint on theme changes; an already-open native editor also updates.

Task/resource colors, progress colors, milestone colors and ordinary orange links remain data/diagram colors rather than being inverted. Workload warning text/fills and summary captions have light/dark UI colors. Scheduling, JSON schema 3, resource availability and history semantics are unchanged.

## Captures

All captures use private Xvfb, Qt offscreen/software rendering and temporary preferences, never the user's desktop or saved settings:

- [Settings: light](screenshots/theme-settings-light.png)
- [Settings: dark](screenshots/theme-settings-dark.png)
- [Gantt and workload: dark](screenshots/theme-workspace-dark.png)
- [Resource editor: selected dark theme](screenshots/theme-resources-dark.png)

Native editor captures contain the widget **client area**, not OS-supplied decorations. Title bars and OS-managed file/color pickers ultimately depend on platform integration; Windows/macOS runtime/theme QA remains pending.

## Verification

```sh
./tools/isolated-gui.sh python3 -m pytest -q --tb=short
ruff check gantt_desktop tests
```

**232 tests pass**, including **22 new theme/settings checks**:

- Default light despite a previous dark palette; matching QML/widget tokens in both modes.
- Actual mouse and Space-key switch input; Escape closes Settings.
- Pixel checks confirm both Gantt and workload canvases repaint in both directions.
- Preference round-trip, no-op change notification and restoration in a new QML window.
- Resource, assignment, dependency, Help and delete dialogs follow the selected theme, including repeated changes while open; their standard style/fonts remain inherited.
- Task/bulk drawers, ComboBox popup and Settings match in both modes.
- Settings is reachable at widths 1000, 1366 and 1920; background project shortcuts are blocked while it is open.
- Theme changes preserve task/resource data, dirty state and existing Undo history. Escape from Settings does not exit bulk selection.

Tests and captures use in-memory or temporary-file settings, never real application preferences. The 0.5.0 wheel includes `theme.py` and **10 QML components**, including `Settings.qml`.

A temporary wheel installation also passed actual entry-point launches in both default-light and saved-dark modes. Each launch captured a 1366×768 window and verified its palette from rendered pixels, using private Xvfb/offscreen and isolated temporary `XDG_CONFIG_HOME`; no global installation or real settings were changed. Local package: `dist/gantt_desktop-0.5.0-py3-none-any.whl`.
