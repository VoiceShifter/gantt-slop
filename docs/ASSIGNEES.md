# Resource roster dropdowns — 0.8.0

## Use

- Click **Исполнитель** in a task row or in task properties. A dropdown lists existing project resources with names, avatars and checkboxes. There is no editable executor-name field.
- Choose one or several people. **Ок** applies the selection as one undoable operation. **Сбросить** clears the draft; confirm to unassign while retaining effort and the people themselves.
- Escape, Cancel or clicking outside dismisses the draft without changing assignments, creating resources or adding history.
- **Найти ресурс** filters names locally, case-insensitively. Typing an unknown name, or pressing Enter in search, does not create or assign anyone.
- **＋ Добавить ресурс…** opens an explicit native resource form, optionally prefilled from the search text. Only that form's Save creates the entity. It is not assigned automatically: select its new roster entry and confirm.
- **Часы…**, or the existing ⋯ beside the task-property field, opens the native per-person allocation editor. The selection is passed as a draft: Cancel changes nothing; Apply commits selection/hours together.
- In bulk mode, enable **Исполнитель**, open the same roster and confirm the picker. This only updates the bulk draft. **Применить изменения** commits all checked non-group tasks in one transaction; cancelling bulk mode discards it.

A changed resource set initially shares the task's existing effort equally. Confirming the same set, including a different selection order, preserves explicit per-person shares and creates no spurious history. Calendar dates/durations and task effort are not silently changed by roster-only selection. Resource IDs are validated against the project; neither the dropdown nor bulk selection accepts a name as an ID.

The roster updates after explicit creation/renaming. Deleted resources are removed from an open selection draft. Unassigned tasks show **Не назначен**, and disabled/group fields cannot assign summary resources.

## Reference and boundaries

The rendered GanttPRO Assignee cell was inspected in the existing **headless** browser. It opened an anchored multi-checkbox roster with people/resource names, per-person hour controls, **Сбросить**, **Ок** and a separate **Добавить еще людей** action, rather than a plain name input. The four-entry reference roster did not expose a search input; this application adds a local name filter for larger rosters.

The reference selector was dismissed with Escape, and its original Client/8h assignment was verified unchanged. No checkbox or effort edit was made; the evidence checklist was audited complete. No source/private state or downloaded assets were used.

This app uses project-local resources, not accounts or invitation services. It keeps the existing system-styled native editor for advanced hours rather than reproducing account-dependent controls or every reference scheduling mode. The legacy programmatic/import name-resolution path remains for compatibility, but it is no longer used by task/table/bulk assignment inputs.

JSON **schema 4 is unchanged**. Opening/cancelling dropdowns, filtering and bulk drafts do not dirty the project. Actual assignment, allocation and explicit resource creation retain normal snapshot Undo/Redo semantics.

## Verification

```sh
./tools/isolated-gui.sh python3 -m pytest -q --tb=short
ruff check gantt_desktop tests
```

**343 tests pass**, including **19 new assignee-picker checks** for:

- Table and task-property dropdowns in both themes; correct checked IDs, multi-selection, a single confirmed transaction and Undo.
- Escape/outside/Cancel preserving project/catalog/history; search and unknown names not creating people.
- No-op/reordered selection preserving manual shares; Reset retaining effort and resources.
- Explicit native creation and separate assignment, allocation-draft Cancel and one-step native Apply.
- Bulk checked-leaf assignment, draft cancellation, shared ID validation and retained manual shares.
- Bounds at 1000/1366/1920, scrollable large catalogs and removal of deleted people from a live draft.

All GUI verification/captures use private Xvfb plus Qt **offscreen**, not the physical desktop. Browser reference work stays headless. QML has no configured LSP here; real engine/input tests detect binding/reference/type errors. Ruff passes and Python LSP reported no findings.

- [Table dropdown, light](screenshots/assignee-dropdown-light.png)
- [Task-property dropdown, dark](screenshots/assignee-dropdown-dark.png)
- [Bulk selection draft](screenshots/assignee-bulk.png)

Package: `dist/gantt_desktop-0.8.0-py3-none-any.whl`, with **13 QML components**, including `AssigneeField.qml` and `AssigneePicker.qml`. A temporary installed-wheel smoke check passed actual dropdown multi-selection, draft-to-native Hours cancellation and schema-4 save/reload. Packaged QML and changed Python bytes matched current sources; no global install or real preferences were changed. Windows/macOS/native-window-manager and comprehensive accessibility/high-DPI QA remain pending.
