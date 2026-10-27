# GanttPRO / MS Project file transfer

**Current 0.16 XML workflow:** [XML.md](XML.md) supersedes the historical XML mapping below: identified exporter-unit correction (212 effort hours), typed custom fields, named color/status/exact-progress/baseline metadata and inherited calendar/availability overrides. Every reference CSV table cell survives local CSV → XML → CSV transfer. The original XML itself lacks people/cost/color data; missing data are not invented. **GanttPRO still rejects XML; Microsoft Project runtime acceptance is unverified.**

**Current 0.15 CSV workflow:** [CSV.md](CSV.md) documents the actual supplied 23-column table, the new native Desktop CSV importer and matching exporter. The supplied 20-element/14-link diagram now imports from CSV with real arrows, resource names, correct 212-hour effort/38,000 cost, colors and retained source metadata. Re-export matches every reference-table cell. **The eight-column CSV procedure below is historical 0.14 behavior and has been replaced.** Website import behavior remains separately unverified for the new table; full native project state remains JSON.

## Historical 0.14 investigation

**This is not lossless, bidirectional GanttPRO compatibility.** The original investigation had two different routes:

| Direction | Route | Verified boundary |
|---|---|---|
| GanttPRO → Desktop | GanttPRO XML export → native XML import review | Reference's 20 elements, hierarchy, dates and 14 dependency links imported |
| Desktop → GanttPRO | Export **GanttPRO CSV (без стрелок)** → GanttPRO import wizard | Group/children, milestones, dates, separate clock times and working-hour duration verified; **no dependency arrows** |
| Desktop → Desktop through XML | MSPDI writer → XML importer | Supported diagram/calendar/resource/deadline/selected-baseline fields tested; not a replacement for JSON backups |
| Desktop → MS Project | Existing MSPDI XML export | Structural/local round-trip tests only; actual Microsoft Project runtime is not certified |

GanttPRO's public importer accepts `.xlsx`, `.csv` and `.mpp`, **not `.xml`**. An XML upload is rejected by its type check. Renaming the application's XML to `.mpp` was also tested and rejected as unreadable; this application does not manufacture a fake binary MPP file. A genuinely link-preserving website return path requires a verified receiving/import route. MPP conversion is one possibility, not an established requirement for matching CSV columns.

## GanttPRO → Desktop

1. In GanttPRO, export the project as **XML** and retain the original file.
2. In Desktop, open **Файл → Импорт GanttPRO / MS Project XML…**.
3. Review the hierarchy, computed dates, element/link/resource counts and all warnings. The project name is editable in this draft.
4. Press **Импортировать новым проектом**. Existing unsaved work still requires the normal Save/Discard/Cancel decision.
5. Save the imported project as a new **`.gantt.json`** file. The XML is never made the automatic Save destination or overwritten by import.

Opening/rejecting the review does not change the current project or its history. Accepted import starts a new, dirty project without fabricated Undo history. Malformed/unsupported data fails before replacement. A declined discard keeps both the old project and the import draft.

### XML mapping and important source limitations

- MSPDI namespace (or an unnamespaced `Project`), stable UID references, document order and outline levels become a new local task tree. IDs are remapped; this is not live synchronization with the website.
- Start/Finish are local civil datetimes with minute precision. Explicit Finish is preserved when representable; inconsistent Duration is recomputed from the explicit endpoints with a warning. Unsupported endpoints/calendars are rejected rather than silently shifted.
- The inspected GanttPRO profile has a synthetic `Total estimate` wrapper, starts and durations but no Finish. The wrapper is removed, end dates are computed with the exported calendar, and zero-duration elements become milestones with a warning. An ordinary user task merely named `Total estimate` is not removed.
- The real Sensor record imports **11 December 2025 09:00 → 15 December 2025 18:00**, duration **24 working hours**, with its Scenario FS predecessor retained.
- **The inspected GanttPRO XML omits resources/assignments.** The importer cannot invent them. It also writes values such as eight visible effort hours as `PT0H8M0S`. Desktop imports that Work literally as 8 minutes and explicitly warns to check effort; it does not silently multiply unknown files by 60.
- Supported links: FS/SS/FF/SF and signed whole-working-minute lag (`LinkLag` tenths of a minute). Unknown/missing endpoints, cycles, fractional-minute lag and cross-project links are rejected. Import does not propagate/reschedule the source plan; a date-inconsistent dependency produces a warning.
- Project weekdays, up to two working intervals per weekday and dated `WeekDay/TimePeriod` exceptions are retained. Imported weekly hours survive JSON, scheduling, workload and XML re-export; the current native editor edits weekdays/dated exceptions, **not a new weekly-shift form**.
- Calendar inheritance is resolved; distinct task calendars, recurring/extended `Exceptions/Exception`, overnight/more-than-two-interval shifts and calendars without regular working time are rejected.
- Where present in standard MSPDI: work-type resources, weekday availability, bounded dated availability/vacations, assignments/proportional shares, task effort/cost/progress/priority/notes, deadlines and dated baselines are read. Material/cost resources are not silently reinterpreted as people. Resource time-of-day attendance is not modeled; warnings explain that boundary. Mismatched assignment/task Work is reported.
- Baseline entries are remapped to local IDs. Their creation date is the import date because the original snapshot creation date is absent. XML does not preserve all original baseline names/types/archived data. Keep JSON for the complete local history of snapshots.
- Typed XML ExtendedAttribute values are preserved as plain description text, not invented typed custom-field definitions. Other service attributes, presentation, comments, actual-time journals, unsupported scheduling constraints and native custom fields are not promised. Always retain the source file and review the report.

Parsing is offline with `defusedxml`: DTD, entities and external resolution are forbidden. Limits are 16 MiB, XML depth 64 / 100,000 nodes, 2,000 task records, 10,000 links, outline depth 64 and a 100-year diagram span. This is bounded format support, not a universal Microsoft Project reader or a large-project performance certification.

## Desktop → GanttPRO

1. Open **Экспорт**, choose **GanttPRO CSV (без стрелок)**, review the persistent loss warning and save a `.csv` file.
2. Use GanttPRO's **new project → import** flow, not an overwrite of a valuable existing project.
3. Give the disposable/new project a short valid name. Select the sheet and advance; the first wizard card is only a preview placeholder, not proof that the data is empty.
4. Choose **В моем файле нет строки с заголовками**. This dedicated preset intentionally has **no header row**, unlike ordinary CSV export.
5. Map the eight columns in this exact order:

   | Column | GanttPRO field | Format/unit |
   |---|---|---|
   | 1 | Нумерация задач | WBS, e.g. `1`, `1.1` |
   | 2 | Название задачи | Text |
   | 3 | Начало | `DD.MM.YYYY` |
   | 4 | Завершение | `DD.MM.YYYY` |
   | 5 | Время начала | `HH:mm` |
   | 6 | Время окончания | `HH:mm` |
   | 7 | Длительность | **Часы**, not days |
   | 8 | Описание задачи | Text |

6. Review the zero-duration milestone checkboxes and then import.
7. **Recreate dependencies manually.** Incoming source links are listed in each affected task's description, e.g. `Связи (создать вручную): 1.1 FS +1ч`. This text does not make an arrow.

The preset always exports the **whole hierarchy** with fixed fields, irrespective of workspace filtering or generic export range/field drafts. Its table preview uses those fields and the same augmented description data. It writes UTF-8, LF-separated, headerless CSV, quoted by the standard CSV writer; formula-like user text remains literal. Generic CSV behavior is unchanged.

This route does **not** transfer project/resource calendars, assignments, deadlines, baselines, custom fields, progress/priority/cost or the application's full JSON state. Match the receiving project's working calendar yourself and inspect the result; dates/durations may be interpreted differently under a different GanttPRO calendar. There is no automatic web synchronization, binary MPP writer, or CSV/Excel import into Desktop.

## Verification

All application automation uses private Xvfb + Qt offscreen/software rendering. The shared website browser stays headless. No legacy GanttProject code or GanttPRO source/assets were used.

- Local suite: **739 tests**, including **70 new import/transfer cases** (57 parsing/calendar/domain, 6 native import UI, 7 CSV/export UI). DTD/UTF-16/external-entity, size/depth, invalid hierarchy/link/date/calendar/resource data, all four link types with signed lag, imported hours, native old-schema migration and mutable snapshot independence are covered.
- A task/calendar-only fixture was sanitized from the real XML: no author/account/creation metadata. It is regression data, not application code/assets.
- Native review is exercised through the actual QML file-menu signal and standard widgets in both palettes; Cancel, dirty-work rejection, Save/reopen, source preservation and window lifecycle are tested.
- Public GanttPRO test project **1793028085634**, `Desktop CSV TEST 20261026`, was created from the final preset. A retained **1 June 2026 09–18 / 8h**; B retained **2 June 10–18 / 7h**; the checkpoint retained **3 June 15:00 / 0h**. WBS hierarchy and milestone survived; both predecessor descriptions survived, while rendered arrow count remained **0**. Only that test project was deleted.
- Renamed XML `.mpp` was rejected before project creation. There is no filename-renaming workaround.
- Original project **1731492177590** was restored. All **27 rendered row strings** (26 task/add rows plus totals) exactly matched the saved pre-test snapshot; totals stayed **212h / 38,000** and import/task/delete overlays were closed. Browser evidence checklists were audited complete.

Package: `dist/gantt_desktop-0.14.0-py3-none-any.whl`. All **33 packaged Python/QML files** matched source bytes. Temporary installed-wheel verification passed the actual QML import action, native review/accept, both themes, imported 20-element/14-link diagram, edits/Undo/Redo, native JSON Save/reopen, all six export choices and local XML re-import; no QML runtime errors. The detailed transfer warning remains outside the settings scroller, visible above Export. No global installation or real preference changes were made. Windows/macOS runtime, native-window-manager/accessibility/high-DPI and large-project performance QA remain pending.

Reviewed installed-package screenshots: [light review](screenshots/xml-import-light.png), [dark review](screenshots/xml-import-dark.png), [imported diagram](screenshots/xml-import-diagram.png), [GanttPRO preset and visible loss warning](screenshots/ganttpro-export-preset.png).

New native saves use **schema 8** for imported weekly working intervals and still read schemas **1–7**. Versions through 0.13 cannot read schema 8: retain an old file copy before saving with 0.14. Native JSON is still the only complete local project format.
