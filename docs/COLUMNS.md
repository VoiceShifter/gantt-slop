# Table columns and creation rows — 0.6.0

## Use

- Drag the **right boundary of a table header** to change that column's width. This works for Task, Assignee, Effort, Cost and all six optional fields.
- The split cursor, blue header guide and tooltip identify a resize boundary.
- Other column widths remain unchanged; the table/timeline and workload boundaries follow the width change when space permits.
- **Escape during a drag** restores the previous widths, divider and table scroll position.
- **Вид → Сбросить ширину таблицы** resets column widths and the divider.
- Widths survive hiding/showing fields and window/fullscreen changes within the current window. They are view state, not project data or Undo commands; cross-launch column-layout persistence is not implemented.

## Layout fix

The old add-task/add-milestone row started at a fixed hierarchy indent, then laid out two unconstrained buttons. In a narrow Task column the second button could cover Assignee.

The creation controls now sit in a clipped Task-width cell, centered horizontally as a compact pair. Their hit areas and text stay before the next column, including at the minimum Task width. Both buttons still create in the corresponding group.

Task names and data cells are clipped to their columns; long header captions elide. Minimum widths are 250 px for Task and 64 px for other fields. If all columns cannot fit, the existing table scrollbar exposes the rest. Headers and cells use the same offsets and scroll position, which is clamped after shrinking/hiding columns.

The table viewport keeps room for the chart when the window narrows; explicit column widths are retained instead of collapsing into adjacent fields. Initial viewport fitting waits for the first polished frame so transient startup layout sizes do not destroy the normal responsive width binding.

## Rendered GanttPRO reference

Only public rendered UI, DOM bounds and mouse drags were inspected, in the existing **headless** browser profile. No application internals, source or downloaded assets were used.

- Original Task text header: 301 px, following a 70 px outline area. Assignee/Effort/Cost: 98/101/97 px; total table: 716 px.
- Dragging Task about 60 px wider produced 360 px, left the other widths unchanged and moved the table/workload divider to 775 px.
- Dragging Assignee about 40 px wider produced 137 px, left the other widths unchanged and moved the divider to 814 px.
- After narrowing Task back to 301 px, both creation labels fit before its right edge.
- All four original widths, x positions and the 716 px divider were restored exactly. No task/resource data was edited; the evidence checklist was audited complete.

The desktop implementation follows this independent-column resize interaction. It does not claim column reordering, header sorting or double-click autofit parity.

## Verification

```sh
./tools/isolated-gui.sh python3 -m pytest -q --tb=short
ruff check gantt_desktop tests
```

**257 tests pass**, including **25 new native-input/layout cases**:

- Centered, contained creation controls at widths 1000, 1366 and 1920 in light/dark themes.
- Actual boundary dragging for all ten columns, no compensating changes to neighbors, synchronized workload divider, unchanged project/history.
- Minimum widths and clipping, Escape cancellation, horizontal-scroll alignment, shrinking/hiding scroll clamping and retained hidden-column widths.
- Reset defaults, no-op clicks preserving responsive sizing, narrow-window fitting and actual fullscreen state on the isolated virtual screen.
- Task/milestone creation in the correct group after narrowing, with Undo restoring the original project.

QML has no configured LSP server here; real engine/input tests and capture runs check for binding/type/reference errors. Ruff and Python LSP checks are clean. All application automation uses private Xvfb plus Qt **offscreen**; no physical desktop or real preferences are touched.

- [Narrow light layout, 1000 px](screenshots/columns-narrow.png)
- [Independently widened Task/Assignee columns, dark](screenshots/columns-resized-dark.png)

The package is `dist/gantt_desktop-0.6.0-py3-none-any.whl`, still with 10 QML components and JSON schema 3. A temporary installed-wheel smoke check verified actual Task/Assignee boundary drags, creation-row containment and unchanged project/history; every packaged QML file also matched its current source bytes. No global installation or real preferences were changed. Windows/macOS runtime and native-window-manager QA remain pending.
