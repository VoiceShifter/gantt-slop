# Gantt Desktop 0.19 audit

**Audited revision:** `4cc7ab3bc` (0.19.0, native schema 9).
**Status:** investigation only; the five findings below are **open**, not fixed. No application code or existing tests were changed for this audit.

## Scope and evidence

Targeted review of the standalone application's document transactions, native save/load, scheduling input validation, MCP bridge/transport/lifecycle, packaging and documentation. Legacy GanttProject code was not part of this review. This is not an exhaustive security or cross-platform certification.

Fresh checks on Linux, using the isolated offscreen/Xvfb launcher:

- Full existing suite: **1,088 passed in 284.54 seconds**.
- `ruff check gantt_desktop tests`: passed.
- Project-configured Pyright: **26 source files, zero errors/warnings**.
- Active LSP probe of controller/domain/MCP server/transport: zero errors.
- `uv pip check --python .venv/bin/python`: **41 packages checked, compatible**. This checks dependency consistency, **not** vulnerability databases.
- README/documentation local links: no missing targets.
- Existing 0.19.0 wheel: all **40 Python/QML files** still byte-match source; no rebuild was needed for this documentation-only audit.
- Six additional disposable diagnostic probes reproduced the save/load and validation failures below. The two MCP editing failures were also confirmed through authenticated HTTP using the official SDK client, not only direct controller calls.

Passing tests do not cover all failure paths. These probes expose gaps in the current suite; they are not new passing regression tests. Temporary documents were removed and all test listeners stopped. No user project or active desktop was used.

All scheduling reproductions use the default Monday–Friday 09:00–13:00 / 14:00–18:00 calendar and one independent root task `a`, starting **2025-12-01 09:00**, with no dependencies. Duration is 480 minutes unless stated otherwise. MCP tests explicitly enable writes and begin at revision 0.

## Confirmed findings

### A1 · P1 — A failed edit can mutate the document without advancing its revision

**Location:** [`controller.py:585–603`](../gantt_desktop/controller.py#L585-L603), especially `restore(after)` at line 601; [`mcp_server.py:180–185`](../gantt_desktop/mcp_server.py#L180-L185).

**Reproduction:** give task `a` a duration of **960 minutes**, then call:

```json
{"expected_revision": 0, "task_id": "a", "field": "start", "value": "9999-12-31"}
```

Observed over HTTP: `edit_task` returns a tool error, and the subsequent `get_project` also returns an error. The live task's date nevertheless changed; the history index is 1, the document is dirty, but the MCP revision is still 0.

**Cause:** domain validation accepts the date/duration individually without checking that the finish can be calculated. `Controller.edit()` appends history and calls `restore()` outside its rollback guard. Refresh then raises `OverflowError` while calculating the span, before `historyChanged` can advance the revision. The transport correctly reports the exception but cannot undo this partially committed controller state.

**Recommended fix:** validate derived spans/renderable state before publishing a transaction, and make failures preserve the live project, history, dirty state, models and revision together. Add controller and real-HTTP regressions asserting both unchanged data and a successful subsequent read after rejection.

### A2 · P2 — Sub-minute input changes the schedule while reporting “unchanged”

**Location:** [`controller.py:856–862`](../gantt_desktop/controller.py#L856-L862), [`domain.py:761`](../gantt_desktop/domain.py#L761) and [`domain.py:1038`](../gantt_desktop/domain.py#L1038).

**Reproduction:** for the ordinary 480-minute task, call `edit_task` with `field="startTime"` and `value="09:00:30"`.

Observed over HTTP:

- Result: `{"task_id":"a","revision":0,"changed":false}`.
- Finish changes from **2025-12-01 18:00** to **2025-12-02 09:01**.
- The live start contains 30 seconds, but the returned/native serialized start is truncated to minutes. There is no corresponding history/revision change.

**Cause:** `time.fromisoformat()` accepts seconds/fractions; task validation rejects timezones but not sub-minute precision. Calendar arithmetic assumes whole minutes. `to_dict(timespec="minutes")` masks the difference during the no-op comparison, leaving a changed live object without refreshing/history.

**Recommended fix:** enforce minute precision in shared domain validation and editing/native-load boundaries. Reject nonzero seconds/microseconds without mutation rather than silently truncating them. Test both seconds and fractional seconds, including serialization, spans, dirty state, Undo and MCP revision consistency.

### A3 · P2 — A failed native load replaces the current state before it fails

**Location:** [`controller.py:1034–1049`](../gantt_desktop/controller.py#L1034-L1049), [`controller.py:1108–1115`](../gantt_desktop/controller.py#L1108-L1115).

**Reproduction:** write a native JSON document containing task `a` with start `9999-12-31T09:00:00` and duration 960; call `load_path()` while another project is open.

Observed: `OverflowError` escapes; the old project is not preserved, `_path` now points at the invalid document, and history has already been replaced. A previously enabled MCP bridge remains active because `projectLoaded` was never emitted. This active-bridge observation used the actual Qt bridge directly; it was not a separate HTTP disclosure test.

**Cause:** decoding/basic validation are guarded, but `load_project()` is called afterward. It assigns the new project/path/history before computing the timeline and emitting successful-load notifications.

**Recommended fix:** fully prepare and validate a candidate document before replacing the current one. Failed loads must preserve project/path/history/view state and return the normal error result. Successful switches must reliably revoke the old MCP capability. Add a regression beyond the existing missing-field/invalid-JSON test.

### A4 · P2 — Native Save clobbers a predictable temporary sibling

**Location:** [`controller.py:1124–1131`](../gantt_desktop/controller.py#L1124-L1131).

**Reproduction:** create `example.gantt.json.tmp` containing unrelated sentinel data; save a project to `example.gantt.json`.

Observed: Save succeeds, but the sibling is overwritten and then moved away. The user only selected the final JSON destination, not that sibling. A separate simulated replacement failure preserves the original destination and dirty state, but leaves the temporary project copy behind.

**Cause:** the temporary name is always `path.name + ".tmp"`; it is not exclusively created and failure cleanup is absent.

**Recommended fix:** use a unique, exclusively created same-directory temporary file and guaranteed cleanup, retaining atomic destination replacement. The existing [`atomic_export()` pattern](../gantt_desktop/exporting.py#L577-L588) already demonstrates this for exports. Test an existing sentinel sibling and failures during both writing and replacement. Concurrent saves were not exercised by this audit.

### A5 · P2 — Accepted native JSON text can make Save raise an unhandled encoding error

**Location:** [`domain.py:1057–1109`](../gantt_desktop/domain.py#L1057-L1109) and [`controller.py:1127–1131`](../gantt_desktop/controller.py#L1127-L1131).

**Reproduction:** put an escaped lone surrogate (`\ud800`) in a task's notes in a native JSON file. `load_path()` accepts it. Make an ordinary name edit and save.

Observed: `UnicodeEncodeError` escapes; the document remains dirty. This was reproduced through native JSON loading, not through the MCP transport.

**Cause:** malformed Unicode text survives native validation. `ensure_ascii=False` then requires valid UTF-8 text, while the save error handler catches only `OSError`.

**Recommended fix:** reject malformed Unicode during native input validation and surface encoding failures as ordinary, non-destructive save errors. Add tests preserving valid emoji/non-BMP characters as well as rejecting unpaired surrogates. Do not silently replace user text.

## Priority and improvements

1. Repair transaction atomicity and minute-precision validation before expanding write tools. Then fix native-load staging and save isolation/error handling. Add regressions for every reproduction above, not just additional successful-path tests.
2. Until these are fixed, keep an independent `.gantt.json` backup before enabling MCP writes; use exact minute-aligned times and avoid date-boundary edits. **A tool error currently does not always imply rollback.** Read-only MCP is the safer choice for important documents.
3. Add a real Gemini CLI integration journey when available. Its documented configuration is covered in [MCP.md](MCP.md#gemini-cli-and-other-clients), but this audit did not install/configure Gemini or certify every LLM host. The server remains standard MCP, not pi-specific.
4. Extend repeatable QA to Windows/macOS and large/deep projects before claiming those environments are verified. Native JSON currently lacks the explicit input-size/depth budgets used by interchange readers; resource limits need a deliberate design, not an arbitrary silent truncation.
5. Keep changes surgical: these findings do not justify rewriting the controller, replacing snapshot history, changing the schema, or starting unrelated parity features.

## Commit and preservation boundary

All pre-audit standalone implementation/client-documentation changes were already committed (`3a1547b9a`, `4cc7ab3bc`). This audit adds documentation and warnings only. Application version, schema, packaged code and test definitions are unchanged.

Unrelated legacy changes/staging, local configuration/possible credential files and the protected inputs `gantt.png`, `test.file`, `Новый_проект.xml` are intentionally excluded from the audit commit. No push was requested or performed.
