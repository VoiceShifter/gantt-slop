# People and resource workload — 0.4

**0.8 update:** [assignee dropdowns](ASSIGNEES.md) replace the old single-name and bulk text inputs. Users now select existing resource IDs; creation is a separate explicit action. The older shortcut behavior below is historical, not the current task-assignment UI.

Version **0.4.1** replaces the QML modal pages with [system-styled QWidget dialogs](NATIVE_DIALOGS.md). The controls and resource calculations below are retained; the screenshots and package/test counts here record the 0.4 checkpoint.

Implemented only in the independent `gantt-desktop/` application. The legacy application's code and unrelated staged changes are not used or modified.

## Controls

- Click **Загрузка ресурсов** in the bottom bar to open/close the workload panel. Drag its top divider to resize it. It starts collapsed to preserve the existing Gantt workspace.
- **Люди…** opens the project's resource roster. Add, rename or delete people/roles and configure their daily available hours and working weekdays. Resource calendar buttons open the same editor for that person.
- In task properties, use **⋯ beside the assignee** to select multiple people and their effort hours. Changing the selection initially shares the task's effort equally; individual totals can then be entered. Apply commits one transaction; Cancel discards the draft.
- Existing single-name fields and bulk assignment remain convenient shortcuts: an existing name resolves to its resource entity; a new name creates one. Empty text clears assignment while retaining the task's effort.
- Click a person's workload row to expand its assigned-task bars. Click a task bar to open its actual properties. Hover/click a workload cell for dates, hours/capacity and contributing task names.
- Hours, Percent and Tasks modes share the Gantt's zoom, horizontal position and grid divider. Vertical resource scrolling is independent. Coarse time scales aggregate periods, retaining a warning if any constituent day is over capacity or has weekend work.

These are **project-local entities**, not user accounts, email invitations or a company-wide people directory.

## Data and calculations

A resource has a stable ID, name, avatar color, daily available hours (default **8**) and working weekdays (default **Monday–Friday**). Tasks reference resource IDs and optional effort shares. Renaming changes labels everywhere without reassigning tasks; removing a resource clears its references and retains task effort. Remaining assignees take the remaining normalized shares.

`Task.assignee` is retained as an internal legacy-constructor/display cache for existing Python callers. It is synchronized from entities; new project JSON stores IDs/shares rather than that text cache.

Daily load is allocated from **effort, not working duration alone**:

`assigned effort × that day's scheduled working minutes / task's full scheduled working minutes`

Multiple assignments default to equal shares. Explicit assignment totals set the task's effort and corresponding shares. Partial days, lunch breaks, project holidays and offscreen portions of a task are accounted for. Daily rounding carries the remaining effort into the last working day. Milestone effort is reported on its date. Summary groups are excluded from resource totals to prevent double counting.

Examples:

- 8h effort over ten full working days → **0.8h/day**.
- Concurrent 8h and 4h assignments for one person → **12h**, above the default 8h capacity.
- A Friday–Monday task does **not** imply Saturday/Sunday work when the project calendar skips those days.

Resource availability is independent of the project's scheduling calendar. **Hours above daily capacity are red** (`#b93d30`, pale red fill); normal load is green (`#129534`). Actual work on Saturday/Sunday is flagged, including a warning when a customized person calendar permits weekend work. Work against zero availability is an overload/nonworking-day warning. Merely spanning a weekend is not flagged as work.

Workload totals use the whole current project, independent of the task search/completion filter, so hiding a task does not hide its contribution to an overload.

## Calendars

The roster editor separately exposes **project working weekdays**. Enable Saturday/Sunday there to schedule weekend work. Leave a person's calendar Monday–Friday to see that work against zero weekend availability. Changing person availability does not move tasks. Applying a project calendar explicitly recalculates schedules in one undoable edit.

Working task time remains 09:00–13:00 and 14:00–18:00 on enabled project weekdays. Project holidays remain serializable. Individual dated availability exceptions/vacations, editable time-of-day shifts and manually shaped daily effort curves are not implemented in this version.

The workload view is diagnostic: changing assignment effort does **not** silently extend/shorten task durations or automatically level conflicting work. This preserves the application's separate effort/duration contract. Advanced GanttPRO scheduling-mode parity is not claimed.

## Persistence and history

New files use **schema 3**, including resources, assignment IDs/shares and working weekdays. Schema-1/2 imports migrate equal assignee names to shared resource records. Status, priority, schedules, effort and dependencies retain their prior import behavior. Older app versions do not read schema 3.

Resource creation, rename, deletion, assignment edits and calendar updates participate in whole-project snapshot Undo/Redo. Loaded assignment lists are copied: editing or deleting a resource cannot mutate an earlier history snapshot. File saves and schema-3 round trips retain resource IDs.

## Reference observations

The authorized synthetic GanttPRO Diagram project was inspected through visible controls. Its workload panel has compact 30px person rows, round avatars/calendar icons, a shared timeline/divider, pale-blue weekend columns, green capacity bars, red overload and Hours/Percent/Tasks controls. Expanding a resource reveals its task bars.

The reference picker shares 8h as **4h + 4h** when a second resource is checked. The prototype displayed 8h effort / 80h duration and 0.8h per weekday. Its resource calendar explicitly showed eight available hours Monday–Friday. Temporary overlapping assignments produced **16h and 13h red cells**, with measured `rgb(185,61,48)` text and `rgba(231,76,60,0.1)` fill.

Reference effort/assignment edits also recalculated task duration; its Undo did not recreate the original manually stretched duration automatically. The experiment was restored explicitly: prototype Client-only, 8h effort / 80h duration, 5–16 January; model Artist-only, 26h/26h, 5–8 January and original cost; original workload and downstream dates were verified again. No resource calendar setting was changed. The browser checklist was audited complete.

## Verification and isolation

The suite has **200 passing tests**, including **53 native Qt mouse/keyboard tests**. New checks cover entity identity/rename/delete, multi-person effort, overlapping work, partial days, weekend skipping and actual weekend work, availability, calendar/assignment history, schema migration and defensive snapshot copies. Native checks cover the panel, synchronized pan/zoom/divider, modes, person creation/rename, picker Apply/Cancel/invalid input, working-Saturday warnings and task inspection from expanded rows.

**All automation must stay isolated.** `tools/isolated-gui.sh` creates private Xvfb, forces Qt's non-windowing **offscreen** plugin/software renderer and removes desktop-session variables. The test harness also forces offscreen on import and refuses an onscreen QApplication, including background-runner invocation. The isolation probe verified `platformName() == 'offscreen'`, private display `:99` and zero windows before test setup. The browser remains headless.

QML has no configured LSP; actual Qt loading/input checks reject binding/type/reference errors. Python LSP and Ruff supplement the tests. Windows/macOS runtime QA, signed native installers and large-project performance/accessibility work remain pending.

`ruff check gantt_desktop tests` passed. The local wheel **`dist/gantt_desktop-0.4.0-py3-none-any.whl`** includes all **12 QML components**. A temporary isolated install verified the imported module/version came from that install, opened its workload panel offscreen on private Xvfb and rendered a nonblank **1366×768** client frame (exit 0).

Native captures (unscaled, without masking) use a disposable local example with a seven-day project calendar and 96h Scenario effort: **12h/day**, including weekend warnings. The assignment image shows an uncommitted 48h/48h draft. The capture journey undoes the demonstration changes and verifies its original project snapshot before exiting, without saving a project file:


- [Workload and weekend/overload warnings](screenshots/resource-workload.png)
- [Multiple-resource assignment](screenshots/resource-assignment.png)
- [People and availability editor](screenshots/resource-manager.png)
