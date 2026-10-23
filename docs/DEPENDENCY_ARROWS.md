# Dependency arrows — 0.3

Historical 0.3 verification. [Version 0.4](RESOURCES.md) adds resource entities/schema 3, working-day controls and an always-headless test harness; the numbers and package details below describe the 0.3 checkpoint.

Follow-up to checkpoint `7565bc50b`. Only `gantt-desktop/` was changed; the legacy application source and unrelated staged changes were not used or modified.

## Using arrows

1. Hover a task, milestone or summary bar. Start/finish circles appear outside it.
2. Drag a circle to the target's start or finish circle. The source endpoint and target endpoint determine **FS, SS, FF or SF**. Clicking the two circles separately also works.
3. A blue preview follows the pointer. Holding a drag near a timeline edge scrolls horizontally/vertically, including to initially hidden rows.
4. Release on the target. The new orange arrow and all propagated dates belong to one undoable edit. Releasing in empty space, row gaps or the table does not create a link. Escape cancels; changing zoom cancels a pending gesture.
5. Click an arrow to edit predecessor, successor, type or **lag in working hours**, including negative/fractional values. Save commits; Cancel/Escape discards the draft. **Delete link** removes it immediately and is undoable.

Task properties offer the same dependency editor and deletion controls. Use these when overlapping/projected arrows make a particular connector difficult to select.

## What was corrected

- The previous endpoint circles had a gap between their small mouse area and the bar. Real pointer movement through that gap hid the controls before they could be reached. The hit regions now touch the bar and cover its full height; resizing and progress controls stay separate.
- Summary bars no longer suppress their endpoint controls. Group/task/milestone choices are available in the editor as well.
- Drop detection checks the visible chart, bar-height region and actual horizontal bar/handle bounds, rather than linking any task that happens to occupy the drop row.
- Both milestone endpoints can be selected while dragging. Arrowheads meet the diamond's outside edges, not its hidden center; summary arrows meet the thin summary line. Minimum-width bars retain matching connector geometry across zoom levels.
- Edited links retain their IDs. An unchanged Save is not a new history entry; invalid/stale edits cannot create replacement links.
- FS/SS protect a task's start, FF/SF protect its finish. The other edge can resize while keeping the anchored endpoint. Finish-anchored date/time fields are read-only; duration can still be edited.
- Hovered/edited connectors are blue; normal connectors remain orange. Hover feedback clears when the pointer leaves the connector. Pending source circles have a blue accent.

## Summary scheduling

Summary start/finish and working span are derived from terminal members. A group relationship translates its members in working time without changing their individual durations, effort or metadata. Descendant constraints and downstream dependencies are then scheduled in dependency order.

The scheduler captures the previous actual/constrained group starts before each date edit. This avoids applying an enclosing group's translation twice and avoids cumulative date drift when an external child predecessor moves back and forth. Start constraints impose child start floors; finish constraints retain a terminal finish witness without permanently pinning every child's old date.

Cycle checking projects group edges onto terminal members, including empty groups. A group cannot be linked to its descendant, nor can a dependency cycle be hidden by using summary nodes. This is deliberately conservative for hierarchy-related cycles.

Creating, removing or reparenting a child can change a linked summary's anchors and therefore reschedule it or its successors. Row ordering alone, and ordinary row moves with no relevant summary links, retain their previous no-date-change behavior. Invalid hierarchy/dependency changes roll back; all scheduling consequences remain in the same controller history transaction.

JSON remains **schema 2**; group dependency endpoints require application **0.3+**. No reference-project export or legacy engine is used.

## Live GanttPRO checks

The authorized synthetic Diagram project was inspected through rendered controls only:

- Hovered bars expose circular endpoint controls in full-height, approximately 20px-wide hit regions outside the bar.
- A temporary Scenario-finish → Sensor-start arrow created an FS dependency. Sensor moved to **11–15 December 2025**, with **24h duration and 8h effort** unchanged.
- Editing its lag from **0 to 1ч** moved Sensor's start from **09:00 to 10:00**, and finish to **16 December, 10:00**, still with 24h working duration and 8h effort. The dependency row showed its FS relationship, editable lag and hover removal control.
- A second temporary FS arrow between **Planning and Preparation summary groups** was accepted and drawn against their thin bars.
- All experiments were undone. **20/20 saved task/date labels** matched the baseline again; all **14 original dependency IDs** were present, with no extras. The timeline position was restored as well. The browser evidence checklist was audited complete.

These checks establish the observed creation/lag/group interaction, not exhaustive live equivalence for every relationship/calendar combination.

## Verification

The full Linux suite has **158 passing tests**, including **45 native mouse/keyboard tests**. Added coverage includes:

- Walking the pointer pixel-by-pixel from a bar to both circles (reproduced the original failure before the fix).
- Drag creation for all four endpoint combinations onto milestones, summary-to-summary creation, Escape, empty-space/row-gap/table rejection and undo.
- Horizontal and vertical auto-scroll with a held pointer, connection to a previously hidden task, click-pair preview and zoom cancellation.
- Actual connector clicks, keyboard type/lag editing, draft isolation, Save, Delete, Cancel/Escape, modal isolation and history restoration.
- Stable IDs, no-op saves, negative fractional lag, stale/invalid edits and anchored-boundary protection.
- Group types/lag, nested constraints, external child predecessors, no cumulative drift, rigid enclosing-group movement, empty groups, hierarchy changes, creation/deletion and schema-2 round trips.

Python LSP checks and Ruff are used in addition to tests. There is **no configured QML LSP**; actual Qt engine loading and the native tests reject runtime type/reference/binding errors instead. The tests run on a private Xvfb display and never automate the user's physical desktop.

The local **`dist/gantt_desktop-0.3.0-py3-none-any.whl`** contains all **9 QML components**. An isolated install verified version 0.3.0 and launched from the installed package, not the checkout. Installed/software-renderer and source/default-renderer launches both produced nonblank **1366×768** frames and exited 0. This wheel is a Python package, not a signed native installer.

Native, unscaled 1920×960 captures:

- [Summary arrow and hover circles](screenshots/dependency-arrows.png)
- [Arrow editor with type, lag and deletion](screenshots/dependency-arrow-editor.png)

The capture journey undoes its temporary local dependency and checks the original in-memory fixture before exiting, without saving a project file.

## Limits

Not complete GanttPRO parity: exhaustive FF/SF/calendar and complex mixed-summary scheduling comparisons, obstacle/collision routing and dense overlapping-link selection still need further live testing. The timeline is day-granular even though scheduling and lag use working minutes. Multi-row date dragging, calendar settings UI, baselines/critical path, full-project printing and large-project virtualization remain separate work. Runtime/platform QA remains Linux-only; Windows/macOS installers/signing and accessibility/high-DPI coverage are not claimed.
