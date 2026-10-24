# System-styled dialogs — 0.4.1

The resource manager screenshot exposed a mixed-theme QML modal: a dark/black dialog background with hard-coded light inputs and colors. Modal pages now use **PySide6 Qt Widgets** instead of painted Qt Quick overlays.

## Changed

- Resource management/availability, multi-person assignments and dependency editing are real **`QDialog`** windows.
- Task/bulk/resource deletion confirmations and Help use **`QMessageBox`**.
- Forms use `QLineEdit`, `QDoubleSpinBox`, `QComboBox`, `QCheckBox`, `QListWidget`, `QTableWidget`, `QGroupBox` and `QDialogButtonBox`/standard button roles.
- Widget dialogs inherit the application's **platform Qt style, palette and system font**. They have no custom stylesheets or hard-coded foreground/background colors. The application no longer overrides the global system font with Arial; the Gantt QML window retains its own existing font/styling.
- Dialogs are separate decorated windows, transient to the main Gantt window, with window-modal behavior. Escape, native numeric validation and system decimal separators work through the standard controls.
- Main-window command shortcuts are disabled while a native modal is open. Dependency highlighting tracks the native editor. Project changes/main-window closure close its editors and nested confirmations; teardown disposes widgets before Qt shutdown.

The Gantt canvas, workload panel and task/bulk side drawers retain their existing styling. Scheduling/resource commands, project schema 3, assignment sharing and snapshot Undo/Redo are unchanged. Forms preserve values more precise than their displayed decimals when saved without editing.

The old three QML modal components were removed rather than leaving unused duplicate implementations. `dialogs.py` contains their widget replacements and the window/QML bridge.

## Appearance

Actual default style depends on the OS and available Qt platform-theme integration. Linux may use Qt's fallback style when desktop-theme plugins are unavailable; no particular GTK theme is forced. Windows/macOS native style/runtime QA remains pending.

Offscreen captures show the **widget client area**; the title bar/window decorations are supplied by the operating system in a normal desktop run. The dark example simulates a dark application palette, and production code does not force either palette:

- [Resource manager: default/light palette](screenshots/native-resources-light.png)
- [Resource manager: simulated dark palette](screenshots/native-resources-dark.png)
- [Assignment editor](screenshots/native-assignment.png)
- [Dependency editor](screenshots/native-dependency.png)

## Verification

**210 tests pass**, including **63 native Qt input/theme/lifecycle cases**; Ruff passes. Existing resource, assignment, dependency, cancellation, deletion and history scenarios now interact with standard widget controls.

New checks verify:

- Palette/font/style inheritance and absence of hard-coded widget styles under light/dark palettes.
- Standard controls, normal dialog decorations, transient parent and window modality.
- Escape and background-shortcut isolation; native validation/error presentation.
- Resource deletion confirmation/Undo, project-load and main-window closure, including nested confirmations.
- Sub-display-precision no-op saves, larger system fonts/layout hints and the native Save default action.

All GUI verification/captures use **`tools/isolated-gui.sh`**, Qt's **offscreen** plugin/software renderer and private Xvfb. The test fixture refuses an onscreen QApplication. No physical-desktop automation or visible test instance is needed.

The local **`dist/gantt_desktop-0.4.1-py3-none-any.whl`** includes `dialogs.py` and **9 QML components**, with the three obsolete modal QML files absent. A temporary isolated install verified the imported version/path, opened all three QWidget editors against the installed package and captured a nonblank 760×540 native resource editor (exit 0), using offscreen/private Xvfb.

The capture journey opens only local synthetic data and confirms the project snapshot/history remain unchanged. Project/resource data and unrelated staged legacy changes are preserved.
