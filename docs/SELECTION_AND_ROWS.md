# Task selection and row movement — 0.2

Follow-up to baseline **`cc77fec92`**, committed before this work. Only the standalone application was changed; unrelated staged legacy work was preserved.

## What the live reference actually does

The authorized synthetic GanttPRO project was inspected in its Diagram view, not Board or other product areas.

- The toolbar checkbox opens **Массовое изменение** and exposes task-row checkboxes. Selecting Scenario and Sensor gives **Выбрано: 2**. Selecting Planning selects the group and all five children (**6**); deselecting Scenario leaves **5** and an indeterminate parent checkbox.
- Checkbox mode is **bulk property editing, not a bulk date-drag gesture**. Pressing/dragging Scenario's bar in that mode deselected its checkbox; all 20 task/date labels stayed unchanged. The implementation therefore does not invent a multi-bar schedule gesture for this mode.
- The reference bulk editor offers assignee, status, priority and color with a separate Apply action. Assignee here remains local text, not a separate People/account system.
- Explicit status changes set progress: **Open → 0%, In progress → 50%, Completed → 100%, Closed → 100%**. Entering **25%** manually changes status to In progress while preserving **25%**, rather than rounding it to 50%. The Closed reference row becomes muted/struck through.
- The five inspected priorities are Highest, High, Medium, Low and Lowest.
- Dragging Scenario's six-dot grip below Sensor changed their outline numbers to **Sensor 1.1 / Scenario 1.2**, without changing dates.
- Dropping Scenario on Preparation's name area inserted it as the **first child, 2.1**. Its original **1–10 December** dates stayed intact. Planning effort became **48h**, Preparation effort **72h**, and their summary spans updated from the new hierarchy.
- Both row moves were undone. Status/progress were restored to **Open / 0%**. All **20 rendered task/date labels** and the **21-row ID/text/order** baseline matched again. No reference task was deleted.

## Delivered

- Checkbox toolbar mode, individual/group/select-all checkboxes, indeterminate parent states, selected counters, Ctrl+A and Escape.
- Explicit bulk drafts and Apply/Cancel. Assignee, status, priority and color update in **one undoable transaction**; dates, working duration, effort and cost remain unchanged.
- Group selection includes descendants, even when collapsed. Select-all respects the current filter; changing search/filter clears selection. An operation that hides selected tasks under a completion filter drops those hidden checks.
- Group progress/status remain derived. Bulk assignee/status/priority changes affect selected non-group tasks; color can also change a selected summary's own bar.
- Bulk deletion has confirmation and a separate effective-delete count. **A partially selected parent never deletes an unchecked child**: the 5-row partial Planning selection deletes only the 4 checked leaves. This safety rule is tested locally; reference deletion parity is not claimed.
- Status/priority controls in task properties and optional table columns; blue progress control with direct numeric input; Closed-row styling.
- Grip-based row drag with non-mutating ghost/target feedback, before/after drops, first-child nesting on a group's name area, append-to-group/root drop rows, and edge auto-scrolling.
- Dragging one summary row keeps its subtree. Hierarchy cycles are rejected. A three-pixel threshold, semantic no-op detection and Escape cancellation avoid spurious edits/history.
- Row moves change hierarchy/order only, not leaf schedules or dependency links. Derived summary totals and connector endpoints refresh accordingly.

## Project format

Version **0.2.0** saves JSON **schema 2**, including status and priority. Schema-1 files from the committed 0.1 baseline still load: missing priority defaults to Medium and missing status is derived from stored progress. Explicit valid metadata round-trips unchanged. The 0.1 baseline does not read schema 2; keep a separate copy if you still need its file format.

## Verification

- **106 tests passed, exit 0**: 50 domain tests, 31 controller/regression tests and 25 real Qt mouse/keyboard tests.
- `ruff check gantt_desktop tests`: all checks passed.
- Real input tests cover checkbox/group/partial/all selection, draft cancellation, multi-field Apply plus one Undo, protected deletion, status/progress input, sibling and cross-group drops, invalid cycles, Escape and edge auto-scrolling. All 55 baseline regressions remain in the suite.
- Controller tests also cover no-op status/progress submissions: a Closed task stays Closed when 100% is re-entered, and an unchanged In progress status preserves partial completion.
- Tests also reject Qt TypeError, ReferenceError, invalid assignment and binding-loop messages. Transient drop-marker bool conversion and confirmation-dialog sizing were corrected rather than suppressing those errors.
- Standard launcher smoke check with the default Linux renderer: exit 0 at 1920×960. Deterministic input tests and interaction captures use Qt's software renderer on private Xvfb.
- Local wheel: **`dist/gantt_desktop-0.2.0-py3-none-any.whl`**, including all **9 QML components**. It is a Python package, not a native installer. An isolated local install and launch from the installed package also completed with exit 0.

## Native evidence

Unscaled, unmasked 1920×960 app-client frames on isolated Xvfb. Captures wait for real rendered frames and completed drawer transitions; the source model is checked before release and after Undo. The final native capture journey ended with its original in-memory fixture restored, without saving a project file.

| Frame | Visible result |
| --- | --- |
| [Current overview](screenshots/overview-current.png) | Current application through the standard launcher |
| [Bulk selection](screenshots/bulk-selection.png) | Five selected rows, partial Planning checkbox, unchecked Scenario, effective deletion count four |
| [Bulk applied](screenshots/bulk-applied.png) | Selected leaf metadata/progress updated; unchecked Scenario and task dates retained |
| [Row preview](screenshots/row-drop-preview.png) | Original hierarchy still intact while the ghost and first-child target are displayed |
| [Nested row](screenshots/row-drop-nested.png) | Scenario 2.1, Planning 48h, Preparation 72h, original leaf dates |
| [Task metadata](screenshots/task-status-priority.png) | Closed / 100%, Highest priority, blue progress control and muted/struck row |

## Limits

Not complete GanttPRO parity. Multi-row drag, arbitrary multi-bar schedule gestures outside checkbox mode, keyboard range selection, summary-task dependency links, calendar configuration, baselines/critical path, advanced filtering, full date-scale parity and cross-platform/high-DPI/accessibility/performance QA remain separate work. Bulk date editing is intentionally not smuggled into the checkbox editor. Windows/macOS runtimes and signed installation bundles remain untested/unbuilt.
