# Full-diagram export — 0.9.0

**0.15 update:** **GanttPRO CSV · 23 поля** now copies the actual supplied spreadsheet's 23-column table. Headers/order, group/task name placement, colors, full date/times, resource names, effort/cost/status/priority and metadata are retained. **Предшественник is a real link column**, and the new Desktop CSV importer creates arrows. A complete fixture re-export is checked cell-for-cell against the reference. [CSV use and exact schema](CSV.md). The 0.14 eight-column preset below is historical and has been replaced; current website round-trip compatibility is not certified.

**0.14 historical update:** the dedicated **GanttPRO CSV (без стрелок)** preset exports the entire hierarchy as eight fixed, headerless fields: WBS/name/start/finish/start time/finish time/hour duration/description. Its preview includes predecessor descriptions for **manual** link reconstruction; actual arrows, calendars, assignments, baselines and other JSON data do not transfer. The final preset was imported through GanttPRO's public UI, including non-default 10:00/15:00 times. GanttPRO rejects `.xml` imports and renamed XML `.mpp` files. Desktop now imports supported XML through a separate native review. See [file transfer and exact mappings](INTERCHANGE.md). Native schema is now 8; historical counts below describe their original releases.

**0.13 update:** [baselines](BASELINES.md) add a selected-reference PDF/PNG overlay, four baseline/deviation fields, real Excel date/time cells and the active snapshot as MS Project XML Baseline 0. Other snapshots and deleted-element entries remain in the project JSON, now schema 7. The historical feature counts below are unchanged.

**0.12 update:** PDF/PNG now include a real [critical-path option](CRITICAL_PATH.md), computed from the frozen whole project rather than filtered rows. Its initial checkbox follows the workspace and can be changed independently. Invalid/over-budget analysis disables graphical export until the option is unchecked. Schema is now 6; the counts/package below remain the historical 0.9 checkpoint.

## Use

Click **Экспорт** in the toolbar. A standard native dialog contains a vector document preview and export settings. This is **not a capture of the application window**: sidebars, toolbars, inspectors, selection overlays and scroll position are not included.

1. Select **PDF, PNG, Excel, MS Project XML, CSV (выбранные поля) or GanttPRO CSV · 23 поля**. The last preset has fixed fields/whole-project scope and an explicit loss warning.
2. Choose the whole project or the currently visible task rows (current filter/collapsed groups).
3. For graphical export, choose table + chart, chart only or table only; time scale; labels inside/right/hidden; links, closed-task strike/fade, current-date marker and optional workload.
4. Select export fields, including the nine custom-field types. Initial fields/widths/scale come from the current workspace; changing export settings does not change the workspace.
5. Optionally set a timeline/workload date range. Task data is not silently clipped or removed by this date range.
6. For PDF, choose **Полный размер** or A4/A3/A2/A1/A0/Letter/Legal/Tabloid/Ledger, with landscape/portrait for sized paper.
7. Review and press **Экспорт…**, then choose the destination in the normal Save dialog.

Preview fits to width initially; Ctrl+wheel zooms, dragging/scrollbars pan. The preview shows the full document, not separate paper pages; the status shows output dimensions and PDF page count. Graphical sheets use a light print background independently of the app theme; the actual native controls still use the selected app palette/font/style.

## Output behavior

- **PNG:** entire selected document at its natural diagram scale, including offscreen tasks and the chosen timeline. There is no application chrome. Oversized images (32,767 px on either side or 80 million pixels) are rejected with guidance instead of cropped or allocating unbounded memory.
- **PDF, Full size:** one vector page matching the diagram's dimensions, with selectable text. Very large full sheets are rejected; choose a paper size instead.
- **PDF, paper size:** fits the full document width and paginates vertically on row boundaries. Title/table/timeline headers repeat, and page numbers are included. The last offscreen task is retained. Dependencies crossing pages are clipped at the page body rather than losing tasks. Full-size orientation is implicit in the sheet dimensions; its orientation control is disabled.
- **Excel:** a real `.xlsx`, not renamed CSV. Selected columns preserve numeric/boolean/date types, literal formula-like strings, task outline levels, bold summaries, header freeze and an auto-filter. Optional workload is a separate resource/day sheet. Dates earlier than Excel's 1900 epoch are retained as ISO text. Modern Excel-compatible readers are targeted; the independent openpyxl reader validated dates, zero, False, literal `=1+1`, and both sheets.
- **XML:** targets MS Project's MSPDI namespace. It exports the whole task tree, dates, working duration vs effort, milestone/summary flags, calendars/holidays, priority/status metadata, all four link types/working lag and per-resource assignments/shares. Custom values are retained as named entries in task **Notes**, not native typed MS Project custom-field definitions. The UI therefore disables row/column filtering for XML. Link type/lag mappings were checked against Microsoft Learn; structural tests pass, but actual MS Project/third-party application runtime interoperability is **not certified**. A receiving scheduler may apply different scheduling/resource-calendar semantics.
- **CSV:** UTF-8 BOM and selected fields/rows; text that could be interpreted as an Excel formula is prefixed with an apostrophe. Numeric fields remain numbers. The older programmatic CSV entry point remains compatible.

Group summaries retain the application's full-group calculations even when only some rows are visible. Workload, when included, uses the whole project's assignments, just like the on-screen workload panel; hiding a task does not hide its load.

Exports use an independent snapshot. No option/filter/preview/write operation changes task schedules, resource assignments, project data, dirty state or Undo history. Successful export does not save the project itself. New project JSON still uses **schema 4**.

Writes are staged in the chosen destination directory and replace the destination only after successful completion. Failure removes the temporary file and preserves an existing file. Invalid ranges, empty row selections, unknown fields, unsupported options and invalid XML characters report errors without producing a partial output. Cancel leaves the export dialog/project unchanged. A destination with the wrong extension is rejected rather than silently changing a filename after overwrite confirmation.

The CLI **`--screenshot`** option intentionally remains a raw window-capture tool for isolated GUI verification; it is separate from user-facing export. No existing user-created image is consumed or overwritten by opening Export.

## Reference and boundaries

The rendered GanttPRO export page was inspected in the shared **headless** browser: PDF/PNG/XML/EXCEL, document preview, Full-size and named paper formats, landscape/portrait, scale, label placement, styling/date/workload switches and field choices. Excel exposed its task filter; XML had no additional settings. The initial PDF format was restored and the export view closed without pressing final Export, downloading a file or editing project data; the checklist was audited complete. No application source, private state or downloaded assets were used.

Features not present in this application's engine are not offered as fake export controls: account creator/comment/file indicators and actual time/cost tracking. Critical-path highlighting was added in 0.12; general reserve columns are not part of the export field picker. Native printer integration, horizontal PDF tiling, exhaustive Office application compatibility and very large project/complex arrow-routing parity remain pending. The export writers need no additional runtime dependency; the separate XML importer added in 0.14 uses `defusedxml`.

## Verification

```sh
./tools/isolated-gui.sh python3 -m pytest -q --tb=short
ruff check gantt_desktop tests
```

**395 tests pass**, including **52 new export checks**: all five formats; full-model/offscreen coverage; PDF Full/A4/A3/Letter pagination and orientations with Qt PDF text/render verification; repeated headers and final-task presence; XLSX types/hierarchy/workload/formula safety; XML calendars/links/assignments/metadata; date/scale/style options; filtering/snapshot isolation; atomic failure protection; native theme/font/modal lifecycle; Save cancellation and invalid/empty settings.

Python checks and Ruff pass. QML has no configured LSP; actual engine/input/capture checks cover the toolbar bridge. All GUI automation is behind private Xvfb + Qt **offscreen**, never the physical desktop. The temporary openpyxl verification did not add a project dependency or global installation.

- [Native export preview/settings](screenshots/export-preview.png)
- [Actual full PNG with workload](screenshots/export-full-diagram.png)
- [Rendered page 2 of a paged PDF](screenshots/export-page-2.png)

Package: `dist/gantt_desktop-0.9.0-py3-none-any.whl`, still with 13 QML components plus the new Python renderer/interchange/dialog modules. A temporary installed-wheel check passed the actual toolbar/native preview and all five export formats with unchanged project/history; packaged QML and changed Python bytes matched current sources. The final preview capture also came from that installed package. No global install or real preference changes were made. Cross-platform/native-window-manager and comprehensive accessibility/performance QA remain pending.
