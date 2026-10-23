# Live-reference observations

The reference is the already-authorized, synthetic device-planning project in the GanttPRO browser application. Only its **Diagram/tasks** UI was explored. No application source, private JavaScript state, or implementation assets were read/copied. The old GanttProject source was not used for this application.

The follow-up [selection, status/progress and row-drag observations](SELECTION_AND_ROWS.md) record the additional live research for 0.2. [Dependency arrows](DEPENDENCY_ARROWS.md) records the 0.3 task/group-link experiments and native verification.

## Appearance

The inspected light view has a white task tree and timeline, thin gray cell dividers, a compact project header/toolbar, blue active accents and assignee circles, cyan task/summary bars, orange orthogonal dependency arrows and a magenta milestone. Rendered bar styles were read from visible DOM elements: **RGB(80,199,214), #50c7d6**, 22px high, 2px corners, Arial 12px white text. Summary bars are thin lines with bold name/date captions above them. The new app uses its own text branding and native Qt primitives, not the site's marks/assets.

## Observed movement rules

1. **A predecessor fixes the target's start.** Dragging the last task body showed an information message explaining that linked tasks cannot be freely moved. Its dates remained **29 January–11 February 2026**, duration **80h**, effort **10h**, with an FS predecessor and lag 0. No lag was silently created by dragging.
2. **Moving a group shifts children and downstream dependents.** A one-week Planning-group drag changed its span from **1–30 December 2025** to **8 December–6 January 2026**. All child task/date labels moved. The downstream final task changed from **29 January–11 February** to **5–18 February**, while duration stayed **80h** and effort **10h**.
3. **Summary values are derived.** In the Planning editor, the start was editable; end, duration and effort were read-only derived values. The moved group still had **176h** duration and **88h** effort.
4. **Resizing is not effort editing.** Earlier in the same browser journey, a right-edge drag changed a leaf's finish and working duration without changing its start or effort. The actual resulting values were read from the editor, not inferred from cursor distance.
5. **Undo is asynchronous in the reference.** After Undo, the rendered schedule needed to finish recalculating before labels matched the baseline. The group-move test ended with all **20 rendered task/date labels** matching its freshly recorded pre-test baseline.
6. The dependency editor exposes four endpoint types, working-time lag, task selection, and an explicit Save. Only the inspected FS movement/resize chain was exercised against the live schedule; exhaustive FF/SF/calendar parity is not established by these observations.

The supplied project had different dates after the browser session restarted. A new live baseline was recorded before mutation; previous-session dates were not assumed to still be current. The independent bundled fixture reproduces visible labels and approximate scheduling structure, not a hidden data export of the reference project.

## Implementation decisions

- Keep previews separate from committed scheduling. One release creates one undoable scheduling transaction.
- Keep duration, effort and progress separate; never turn a date move into an effort/progress edit.
- Represent milestones as zero working duration, summaries as derived spans, and dependencies as a directed acyclic graph.
- Reuse no legacy application engine. The scheduling implementation and native Qt interface are new code.
- The first native renderer uses Qt Quick items for bars/handles and a canvas for grid/connectors. It is not an embedded website.
