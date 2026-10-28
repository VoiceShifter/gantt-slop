# Gantt Desktop 0.19 audit and 0.19.1 fixes

**Audited revision:** `4cc7ab3bc` (0.19.0, native schema 9).
**Status:** all five findings, **A1–A5, are fixed in 0.19.1**. The original reproductions below describe 0.19.0, not the corrected behavior. Native schema 9 and supported schema versions 1–9 are unchanged; invalid timestamps/text are rejected rather than silently repaired.

## Fix verification · 0.19.1

Fresh Linux checks used the isolated offscreen/Xvfb launcher; no user document or physical desktop was used:

- Complete suite: **1,151 passed in 302.48 seconds**, including **63 additional regression cases**. The historical calendar test now explicitly rejects seconds and exercises date changes/successor propagation with minute-aligned input.
- [Audit regressions](../tests/test_audit_fixes.py) cover unchanged document/history/dirty/path/view state and signals after rejection; failed Undo/Redo restoration; minute/date boundaries; malformed and valid non-BMP Unicode; temporary-file isolation and creation/write/replacement/encoding failures; and refusing discard after a failed save.
- [Real authenticated SDK HTTP tests](../tests/test_mcp.py) confirm rejected edits leave snapshots/revisions unchanged, subsequent reads and valid edits/Undo still work, failed native loads preserve access to the unchanged current project, and successful project switches revoke access.
- [Native-window MCP regression](../tests/test_mcp_ui.py) checks unchanged rows, chart geometry, dirty state and saved bytes after rejected edits. [Calendar tests](../tests/test_task_dates.py) retain date/time and successor coverage.
- Ruff passed. Pyright checked all application modules and the four changed test modules with **zero errors/warnings**. Active LSP probes of all six changed Python files reported zero errors.
- The independently installed **0.19.1 wheel** passed **149 focused audit/MCP/native-UI/calendar tests in 50.41 seconds**. All 16 imported application modules came from that installation, and all **40 packaged Python/QML files** byte-match both the source and installation.
- Wheel: `dist/gantt_desktop-0.19.1-py3-none-any.whl`, **157,215 bytes**, SHA-256 `57bb132efa3091597ace87b39bd2e3207668c58f8b7341839b9f7c61a98c5415`.

These checks close the five reproduced defects; they are not an exhaustive security, performance or cross-platform certification. MCP remains opt-in and read-only by default. Timeouts/disconnects still do not guarantee cancellation: re-read before retrying a write.

## Original audit scope and evidence

Targeted review of the standalone application's document transactions, native save/load, scheduling input validation, MCP bridge/transport/lifecycle, packaging and documentation. Legacy GanttProject code was not part of this review. This is not an exhaustive security or cross-platform certification.

Original 0.19.0 checks on Linux, using the isolated offscreen/Xvfb launcher:

- Full existing suite: **1,088 passed in 284.54 seconds**.
- `ruff check gantt_desktop tests`: passed.
- Project-configured Pyright: **26 source files, zero errors/warnings**.
- Active LSP probe of controller/domain/MCP server/transport: zero errors.
- `uv pip check --python .venv/bin/python`: **41 packages checked, compatible**. This checks dependency consistency, **not** vulnerability databases.
- README/documentation local links: no missing targets.
- Existing 0.19.0 wheel: all **40 Python/QML files** still byte-match source; no rebuild was needed for this documentation-only audit.
- Six additional disposable diagnostic probes reproduced the save/load and validation failures below. The two MCP editing failures were also confirmed through authenticated HTTP using the official SDK client, not only direct controller calls.

At the audited revision, the passing suite missed these failure paths. The diagnostic probes were not passing regression tests; the new regression coverage is listed above. Temporary documents were removed and all test listeners stopped. No user project or active desktop was used.

All scheduling reproductions use the default Monday–Friday 09:00–13:00 / 14:00–18:00 calendar and one independent root task `a`, starting **2025-12-01 09:00**, with no dependencies. Duration is 480 minutes unless stated otherwise. MCP tests explicitly enable writes and begin at revision 0.

## Original findings · all resolved in 0.19.1

Source line numbers in this section refer to the original audited revision, `4cc7ab3bc`.

### A1 · P1 — A failed edit can mutate the document without advancing its revision

**Original locations:** `controller.py:585–603`, especially `restore(after)` at line 601; `mcp_server.py:180–185`.

**Reproduction:** give task `a` a duration of **960 minutes**, then call:

```json
{"expected_revision": 0, "task_id": "a", "field": "start", "value": "9999-12-31"}
```

Observed over HTTP: `edit_task` returns a tool error, and the subsequent `get_project` also returns an error. The live task's date nevertheless changed; the history index is 1, the document is dirty, but the MCP revision is still 0.

**Cause:** domain validation accepts the date/duration individually without checking that the finish can be calculated. `Controller.edit()` appends history and calls `restore()` outside its rollback guard. Refresh then raises `OverflowError` while calculating the span, before `historyChanged` can advance the revision. The transport correctly reports the exception but cannot undo this partially committed controller state.

**Fix implemented:** [domain validation](../gantt_desktop/domain.py) now evaluates every task span. [Controller edits](../gantt_desktop/controller.py) operate on detached drafts and prepare the restored document/view before publishing history or a revision. Failed view preparation restores the previous document, models and view state; Undo/Redo indices also advance only after successful restoration. Controller, native-window and real-HTTP regressions verify rejection leaves state unchanged and subsequent reads/edits work.

### A2 · P2 — Sub-minute input changes the schedule while reporting “unchanged”

**Original locations:** `controller.py:856–862`, `domain.py:761` and `domain.py:1038`.

**Reproduction:** for the ordinary 480-minute task, call `edit_task` with `field="startTime"` and `value="09:00:30"`.

Observed over HTTP:

- Result: `{"task_id":"a","revision":0,"changed":false}`.
- Finish changes from **2025-12-01 18:00** to **2025-12-02 09:01**.
- The live start contains 30 seconds, but the returned/native serialized start is truncated to minutes. There is no corresponding history/revision change.

**Cause:** `time.fromisoformat()` accepts seconds/fractions; task validation rejects timezones but not sub-minute precision. Calendar arithmetic assumes whole minutes. `to_dict(timespec="minutes")` masks the difference during the no-op comparison, leaving a changed live object without refreshing/history.

**Fix implemented:** shared domain validation rejects nonzero seconds/microseconds in task starts. Start/end time edits reject sub-minute or timezone-aware input before calendar normalization; direct project loading validates before minute-formatted serialization. Rejected input cannot mutate the live project. Regressions cover seconds/fractions, native loading, spans, dirty/history state and MCP revisions, while valid minute-aligned edits remain undoable. Calendar interval counting also stops on its final date instead of incrementing beyond `date.max`.

### A3 · P2 — A failed native load replaces the current state before it fails

**Original locations:** `controller.py:1034–1049`, `controller.py:1108–1115`.

**Reproduction:** write a native JSON document containing task `a` with start `9999-12-31T09:00:00` and duration 960; call `load_path()` while another project is open.

Observed: `OverflowError` escapes; the old project is not preserved, `_path` now points at the invalid document, and history has already been replaced. A previously enabled MCP bridge remains active because `projectLoaded` was never emitted. This active-bridge observation used the actual Qt bridge directly; it was not a separate HTTP disclosure test.

**Cause:** decoding/basic validation are guarded, but `load_project()` is called afterward. It assigns the new project/path/history before computing the timeline and emitting successful-load notifications.

**Fix implemented:** native loading validates the candidate and prepares its document/view before changing path/history or emitting successful-load signals. `load_path()` catches validation, overflow and view-preparation failures and returns the normal error result, retaining the old project/path/history/view and its MCP access. Real-HTTP tests verify that unchanged document remains readable and a subsequent successful switch revokes the old capability.

### A4 · P2 — Native Save clobbers a predictable temporary sibling

**Original location:** `controller.py:1124–1131`.

**Reproduction:** create `example.gantt.json.tmp` containing unrelated sentinel data; save a project to `example.gantt.json`.

Observed: Save succeeds, but the sibling is overwritten and then moved away. The user only selected the final JSON destination, not that sibling. A separate simulated replacement failure preserves the original destination and dirty state, but leaves the temporary project copy behind.

**Cause:** the temporary name is always `path.name + ".tmp"`; it is not exclusively created and failure cleanup is absent.

**Fix implemented:** Save exclusively creates a unique same-directory temporary file, closes it before atomic replacement, and attempts cleanup in `finally`. Creation/write/replacement errors preserve the destination and do not mark the document clean. Regressions preserve an existing `.tmp` sentinel and verify cleanup after injected failures. This does not add file locking or certify concurrent saves to the same destination.

### A5 · P2 — Accepted native JSON text can make Save raise an unhandled encoding error

**Original locations:** `domain.py:1057–1109`, `controller.py:1127–1131`.

**Reproduction:** put an escaped lone surrogate (`\ud800`) in a task's notes in a native JSON file. `load_path()` accepts it. Make an ordinary name edit and save.

Observed: `UnicodeEncodeError` escapes; the document remains dirty. This was reproduced through native JSON loading, not through the MCP transport.

**Cause:** malformed Unicode text survives native validation. `ensure_ascii=False` then requires valid UTF-8 text, while the save error handler catches only `OSError`.

**Fix implemented:** domain validation checks the UTF-8 encodability of all persisted strings, including nested metadata, and rejects unpaired surrogates without replacing text. Save also handles `UnicodeError` non-destructively and cleans its temporary file. Tests reject malformed edits/native files, preserve valid emoji/non-BMP text through save/reload, and exercise the defensive save-error path.

## Remaining improvements and operating limits

1. Keep independent `.gantt.json` backups and enable MCP writes only for a trusted host. Rejected validation is covered by the regressions above, but a timeout/disconnect may follow a completed write: **re-read before retrying**. There is no exactly-once or automatic-save promise.
2. Add a real Gemini CLI integration journey when available. Its documented configuration is covered in [MCP.md](MCP.md#gemini-cli-and-other-clients), but neither this audit nor its fixes installed/configured Gemini or certified every LLM host. The server remains standard MCP, not pi-specific.
3. Extend repeatable QA to Windows/macOS and large/deep projects before claiming those environments are verified. Native JSON still lacks the explicit input-size/depth budgets used by interchange readers; resource limits need a deliberate design, not arbitrary silent truncation.
4. The repairs retain the controller architecture, snapshot history and native schema. Unrelated parity features remain separate work.

## Commit and preservation boundary

The original audit commit (`789bfb9d3`) was documentation-only and did not fix runtime behavior. The 0.19.1 remediation changes the shared domain/controller boundaries, adds regression coverage and updates release documentation; it does not change native schema 9, dependencies or the MCP tool surface.

Unrelated legacy changes/staging, local configuration/possible credential files and the protected inputs `gantt.png`, `test.file`, `Новый_проект.xml` are excluded from both the audit and remediation commits. No push was requested or performed.
