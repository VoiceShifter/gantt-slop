# Local MCP access · 0.19.1

An LLM **client/host** can now access the project open in Gantt Desktop. The application serves the official MCP protocol over **Streamable HTTP**, using the official Python SDK (`mcp>=2.3,<3`). It does not run a model itself. **The server is client-agnostic: there is no pi dependency or pi-specific protocol, and no restriction to one model provider.**

**0.19.1 fixes all five audited save/load and editing defects**, including date-overflow rollback and sub-minute revision tracking. See the [original reproductions and regression evidence](AUDIT.md). MCP remains read-only by default; timeouts/disconnects still require a fresh read before retrying a write.

## Enable and connect

1. Install/update the application in its launch environment: `python -m pip install -e ".[test]"` from `gantt-desktop/`, then `python -m gantt_desktop`.
2. Open **Файл → MCP-сервер…**. Nothing listens before you explicitly enable it.
3. Choose a port (default **8765**; **0** selects a free port). Leave write permission unchecked for read-only access.
4. Click **Включить**, then **Копировать конфигурацию**. The copied JSON contains the actual URL and a newly generated secret token.
5. Add that entry to an MCP-capable host supporting HTTP and custom request headers. Client configuration wrappers differ; the copied example uses `mcpServers`:

```json
{
  "mcpServers": {
    "gantt-desktop": {
      "type": "http",
      "url": "http://127.0.0.1:8765/mcp",
      "headers": {
        "Authorization": "Bearer REPLACE_WITH_THE_TOKEN_FROM_THE_DESKTOP"
      }
    }
  }
}
```

Use the **copied values**, not the placeholder above. Do not commit or publish this configuration. The token grants access to the whole open project, including hidden tasks, notes, resource data and baselines. A connected LLM host may send that data to its model provider; choose a trusted host/provider.

The bottom-bar **MCP · чтение / MCP · изменения** indicator reopens the controls. **Выключить** revokes access. Closing the MCP dialog alone does **not** stop it.

By default (with persistent token unchecked), every enable generates a fresh ephemeral token, and opening another project or exiting stops the server.

### Persistent token across sessions

To avoid re-configuring LLM clients (such as Gemini CLI) each time a new project is opened or between application sessions, check **Постоянный токен (сохраняется между сессиями)** / **Persistent token across sessions**:
- The token is securely stored in application preferences (`QSettings`).
- When persistent token is enabled, opening/loading another project keeps the server active on the same port with the same token, resetting document revisions to 0 for the newly opened project.
- You can generate a new token at any time by clicking **Сгенерировать** / **Regenerate**, or enter a custom token while stopped.
- The **Копировать конфигурацию** / **Copy configuration** output includes both `"url"` and `"httpUrl"`, making it directly compatible with Gemini CLI (`~/.gemini/settings.json`) and other standard MCP clients without manual edits.

## Gemini CLI and other clients

For **Gemini CLI**, merge the following entry into your user `~/.gemini/settings.json`, substituting the URL and token copied from the desktop. Preserve any existing settings and servers:

```json
{
  "mcpServers": {
    "gantt-desktop": {
      "httpUrl": "http://127.0.0.1:8765/mcp",
      "headers": {
        "Authorization": "Bearer REPLACE_WITH_THE_TOKEN_FROM_THE_DESKTOP"
      }
    }
  }
}
```

**Use `httpUrl`, not `url`, in Gemini CLI:** its `httpUrl` selects Streamable HTTP, whereas `url` selects the older SSE transport. This is a client configuration difference, not a different server API. Check the connection with `gemini mcp list`, then inspect the discovered tools with `/mcp`. Keep the client's normal tool-confirmation controls enabled.

This configuration follows the [official Gemini CLI MCP documentation](https://geminicli.com/docs/tools/mcp-server/); a Gemini CLI/model session has not been tested end-to-end here. The existing protocol tests use the independent official MCP SDK client, not pi.

Other MCP hosts can use the same endpoint and bearer header if they support **Streamable HTTP plus custom headers**; adapt their configuration keys rather than changing the server. A local MCP host can use Gemini or another model provider. A cloud-only chat/service cannot directly reach `127.0.0.1` on your computer: it needs a local MCP-capable host/bridge. Stdio-only hosts also need a compatible bridge; a native stdio transport is not currently provided.

## Tools

In read-only mode, only `get_project` is advertised. To expose the other tools, stop the server, explicitly check **Разрешить изменения проекта и Отмену/Повтор**, and enable again. Close the dialog before asking the client to edit.

| Tool | Operation |
|---|---|
| `get_project` | Detached full native project snapshot, revision, computed task/group/milestone start/finish spans, `critical_path` analysis, dirty state and Undo/Redo labels. Includes filtered/collapsed elements; no file-system path. |
| `create_task` | Append a task, group or milestone under an existing group or at the root; returns its stable ID. |
| `edit_task` | Edit one name/notes/color/parent/deadline/status/priority/effort/cost/progress/duration/start/end/time/assignee field using desktop validation and scheduling. |
| `set_assignee` | Set or clear a task's assignee by resource name; automatically resolves or creates the project-local resource. |
| `delete_task` | Delete an element and incident links. Nonempty groups require explicit `include_descendants=true`, including hidden descendants. |
| `assign_resources` | Assign existing project resource IDs, or clear them. No invitations or implicit resource creation. Changed sets receive equal shares; unchanged sets retain their allocation. |
| `save_dependency` | Create a dependency or update an existing ID; FS/SS/FF/SF and signed lag, with cycle validation and downstream scheduling. |
| `delete_dependency` | Remove an existing dependency without pulling dates back. |
| `rename_project` | Rename the active project. |
| `save_resource` | Create or update a project-local resource with daily capacity (hours) and workdays (0=Mon..6=Sun). |
| `delete_resource` | Remove a resource from the project and unassign it from all tasks. |
| `save_custom_field` | Create or update a custom field definition (text, number, date, select, checkbox, color, multi, people, labels). |
| `delete_custom_field` | Remove a custom field definition and clear its values from all tasks. |
| `set_custom_value` | Set or clear a task's custom field value. |
| `create_baseline` | Snapshot the current schedule as a named baseline. |
| `select_baseline` | Activate a baseline for variance tracking or clear active baseline. |
| `delete_baseline` | Delete a baseline by ID. |
| `set_project_workdays` | Set project calendar working days as a list of integers (0..6). |
| `set_holidays` | Set project calendar holidays as a list of ISO date strings (YYYY-MM-DD). |
| `move_task` | Shift a task start date by a signed integer number of days, propagating downstream dependencies. |
| `relocate_task` | Move a task in the WBS before/after another task or into/appended to a group. |
| `bulk_edit_tasks` | Apply changes (status, priority, color, assignee, resources) to multiple tasks in a single Undo step. |
| `undo` / `redo` | Walk the shared document history, which includes **human edits**, not only MCP actions. Check the returned labels first. |

Tool discovery supplies argument schemas and descriptions. Use stable IDs from `get_project`, not row numbers. Use `spans` for computed summary dates/finishes rather than inferring them from stored task duration.

**Units:** native snapshot task durations and dependency lags are working **minutes**. `create_task.duration_minutes` and `save_dependency.lag_minutes` also use minutes. In contrast, `edit_task`'s numeric string values use working **hours** for `duration` and `effort`, 0–100 for progress, and a nonnegative amount for cost. All dates/times are local civil values, not UTC. Creation accepts a local ISO date/time with minute precision; groups/milestones require duration 0. Date edits use `YYYY-MM-DD`, time edits `HH:MM`; an empty deadline or assignee clears it. Nonzero seconds/microseconds and timezone-aware task times are rejected, including during native loading, not silently rounded.

## Transactions and concurrent use

- Read `get_project` and pass its integer `revision` as `expected_revision` on **every mutation**. Human edits, successful MCP changes and Undo/Redo advance the revision. A stale revision returns an actionable tool error without changing the project. Two clients cannot both change the same revision.
- A successful ordinary mutation is one existing document-history transaction, including any propagated dates. Edits are validated on detached drafts; document/view preparation succeeds before history and revision changes are published. Rejected validation preserves the document, history and revision; no-ops do not dirty the document or add history. Editing several fields means several separate tool calls/Undo steps, not a hidden batch.
- Edits are visible in the desktop and remain **unsaved** until the user saves normally. There is no MCP Save/Open/Import/Export or arbitrary file access.
- Reads and writes execute on the Qt thread. The HTTP worker never directly accesses the live document. Writes are refused while a modal editor, bulk draft, text edit or mouse gesture is active; finish the interaction first. Reads remain available.
- Bridge requests cancelled before Qt delivery cannot apply later. Stop/project changes revoke queued requests, including requests from an earlier server generation. A client timeout or network disconnect alone does not guarantee server-side cancellation or rollback: **re-read before retrying**. There is no cross-process exactly-once promise.

## Security and current limits

- The socket binds only to **127.0.0.1**, never LAN/all interfaces. Exact loopback Host validation, rejection of browser Origin headers and constant-time bearer-token checks precede MCP processing.
- The token is generated with `secrets.token_urlsafe(32)`, held in memory and masked in the dialog. The copied configuration deliberately contains it. Logs do not intentionally include authorization headers.
- Request bodies are limited to **256 KiB**, including chunked requests; editable text parameters to **64 KiB**. HTTP concurrency is bounded. Qt bridge waits time out after 15 seconds; an already executing document transaction cannot be interrupted halfway through.
- This is a local static-token integration, **not** an Internet/OAuth/TLS service. Do not expose it through a tunnel/reverse proxy. Direct browser-origin clients and stdio-only hosts are not supported by this transport.
- Reads currently return the whole project; there is no pagination, change subscription, prompt catalog or general GUI automation API.
- Native JSON remains **schema 9**. The feature changes neither file interchange fidelity nor the existing GanttPRO transfer limitations. It does not connect to GanttPRO or revive discontinued MPP work.

## Verification

The complete isolated Linux **0.19.1** suite passes: **1,151 tests in 302.48 s**, including **63 additional audit-fix regression cases** beyond 0.19.0. Environment: Python 3.11.15, PySide6/Qt 6.11.1, MCP SDK 2.3.0.

Checks include real SDK initialization/tool discovery and structured results over HTTP; read-only versus write schemas; task/assignment/dependency editing and shared Undo/Redo; rollback/no-op/conflict behavior; two simultaneous clients; cancelled/queued/in-flight requests; authentication, invalid Host/Origin, duplicate authorization, body limits including chunked bodies; token rotation, occupied ports, immediate same-port restart after live keep-alive traffic, project switching and listener shutdown. Native input checks cover both themes at 1000/1366/1920 widths, copying configuration, busy editors, visible edits and unchanged source files until explicit Save.

New regressions exercise the exact overflow/sub-minute failures through authenticated HTTP: rejected edits preserve snapshots/revisions, subsequent reads and valid edits/Undo succeed, and native-window rows/chart geometry/saved bytes remain unchanged. Failed native loads retain the current document and its access; successful replacement revokes access. See [AUDIT.md](AUDIT.md) for save-error and Unicode coverage.

Ruff and project-configured Pyright pass with zero errors/warnings across the application and the four changed test modules. Active LSP probes of all six changed Python files also report zero errors.

The independently installed **0.19.1 wheel** passed **149 focused audit/MCP/native-UI/calendar tests in 50.41 s**. All 16 imported application modules came from the installation, not the checkout; all 40 packaged Python/QML files byte-match the source and installation. Wheel: `dist/gantt_desktop-0.19.1-py3-none-any.whl`, 157,215 bytes; SHA-256 `57bb132efa3091597ace87b39bd2e3207668c58f8b7341839b9f7c61a98c5415`.

Retained 0.19 UI proof frames (the controls are unchanged; tokens are masked by the native control; all test servers were stopped):

- [Read-only access, light theme](screenshots/mcp-readonly-light.png)
- [Explicit write permission, dark theme](screenshots/mcp-write-dark.png)
- [Task edited over MCP and active-access indicator](screenshots/mcp-diagram.png)

The MCP protocol is tested with an actual SDK client, not merely mocked controller calls. This does **not** claim that every third-party LLM host, Windows/macOS runtime or remote deployment has been verified.
