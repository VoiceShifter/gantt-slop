# Functional + and typed user fields — 0.7.0

## Use

1. Click **+ at the right edge of the table header**, or **Поля** in the toolbar. The + stays reachable in narrow windows and when the table scrolls.
2. **Стандартные** enables/disables the existing Assignee, Effort, Cost, Start, End, Duration, Progress, Status and Priority columns. Their scheduling/resource/status behavior is unchanged.
3. **Создать поле…** opens a standard native definition dialog. Set its name/type and, for lists, one option per line; Number has Sum/Average aggregation.
4. The new column is shown and scrolled into view. Click a cell to edit its value. Checkboxes can also be toggled directly; click their text area to open the full editor.
5. Use **Не задано** to clear a value, **Сохранить** to apply, or Cancel/Escape to discard a draft.
6. In the Custom tab, select a field to rename/configure or delete it. Delete confirms removal of the definition and all task values; Undo restores both.

All editors are standard `QDialog`/QWidget controls, inherit the shared app theme/system font and participate in the existing modal/lifecycle cleanup. No account, invitation or cross-project field registry is introduced.

## Types and behavior

| Type | Stored value and editor |
| --- | --- |
| Text | Plain Unicode text; multiline native editor |
| Number | Finite number, including negative/decimal/zero; native text input with validation |
| Date | Independent civil date, stored `YYYY-MM-DD`; native calendar/date editor |
| List | One configured option; native ComboBox |
| Checkbox | True/False, distinct from unset; actual grid checkbox and native checkbox editor |
| Color | Valid `#RRGGBB`, canonical lowercase; swatch and native color picker/text input |
| Multi-select | Configured options, deduplicated in definition order; checkable native list |
| People | IDs of existing project resources; checkable list with current resource names |
| Labels | Independent free-form labels, one per line, deduplicated; plain-text display |

Number groups and the project total derive **Sum** or **Average** from terminal tasks/milestones, counting each once. Unset values are excluded while zero is included; empty aggregates are blank. Group numeric cells are read-only. Reparenting/deletion recalculates summaries; overflowing/nonfinite numbers or totals are rejected.

Other custom values may be entered on groups as independent metadata. User dates do **not** reschedule work. Custom People fields do **not** assign effort or affect workload: real task assignments remain the Assignee/assignment editor. Resource renames update displayed names; deletion removes that resource from People values in the same undoable operation. Custom Color values do not recolor the Gantt bar.

Field type is immutable after creation. Names and list options can be edited, but an option still used by a task cannot be removed silently. Multi-select values follow a reordered option list as part of the definition edit. Labels are simple strings, not a global colored-label service.

## Persistence and history

Definitions have stable IDs and task values reference those IDs. Renaming therefore retains values. Definition/value edits and confirmed deletion use the normal atomic snapshot Undo/Redo and dirty marker; invalid/no-op saves do not add history. Clearing removes the value without confusing `0`, `False` and unset.

New saves use **schema 4**; schemas **1/2/3** remain importable. Mutable options/values are copied when restoring a snapshot so later edits cannot corrupt Undo. Pre-0.7 applications cannot read schema 4; keep an older copy when needed.

CSV includes all custom definitions/values, even hidden columns, with numeric group rollups. Hiding and resizing are non-destructive view operations, not data edits; visibility/width preferences are currently window-local rather than persisted into the project. Bulk-property mode does not edit custom values. Account-dependent creator, comment/file indicators, time tracking, global reuse, field filtering/sorting and full GanttPRO parity are not claimed.

## Reference and verification

The rendered GanttPRO + panel was inspected in the shared **headless** browser: Standard/Custom tabs, the creation form, nine type choices, list options and Sum/Average. Nothing was saved in the reference; the panel was closed with original headers intact and the evidence checklist audited. No source, private state or downloaded assets were used.

```sh
./tools/isolated-gui.sh python3 -m pytest -q --tb=short
ruff check gantt_desktop tests
```

**324 tests pass**, including **67 new custom-field checks** covering all types, validation, numerical limits/rollups, native creation/value input in both themes, CSV, schema migration, deep-copy/history safety, resource cleanup, hide/rename/delete, real + clicks at 1000/1366/1920, resizing and modal teardown. Python checks and Ruff pass; QML has no configured LSP, so real engine/input tests and captures verify its bindings.

All GUI automation and captures use private Xvfb plus Qt **offscreen**, never the physical desktop or real preferences:

- [Typed columns and numeric summaries](screenshots/custom-fields-table.png)
- [Native field picker](screenshots/custom-field-picker.png)
- [Native number-field definition](screenshots/custom-field-definition.png)
- [Native value editor](screenshots/custom-field-value.png)

Package: `dist/gantt_desktop-0.7.0-py3-none-any.whl`, with **11 QML components** and `field_dialogs.py`. A temporary installed-wheel smoke test passed actual + input, native Number/List creation/value editing, group totals and schema-4 save/reload; packaged QML/domain/controller/editor bytes matched current sources. No global installation or real preferences were changed. Cross-platform/native-window-manager, large-project and comprehensive accessibility QA remain pending.
