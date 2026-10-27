# XML import and export · 0.16

Desktop reads and writes **Microsoft Project XML (MSPDI)**, including the supplied GanttPRO export. This is the real task/calendar/resource/dependency structure, not renamed CSV, fake MPP, or a JSON project hidden inside XML. Receiving the file in Microsoft Project itself remains unverified. **GanttPRO's website rejects `.xml` imports.**

## Use

1. **Файл → Импорт GanttPRO / MS Project XML…** opens a native, transactional review.
2. Check the hierarchy, dates, links, resources, **effort/cost totals and columns**, and warnings. Edit the project name if necessary.
3. **Импортировать новым проектом** creates a new dirty project; Save/Discard/Cancel still protects unsaved work. Cancel does not change the current plan or its history.
4. Save as **`.gantt.json`** for complete native project data. Import never overwrites the XML source or makes it the automatic Save destination.
5. **Экспорт → MS Project XML** writes the whole tree, regardless of workspace filters, collapse, date range or graphical overlay settings. The preview uses that same full-tree scope. A persistent warning explains format boundaries above Export.

Export is destination-local and atomic: validation/write failure does not truncate an existing destination. Exceeding custom-field capacity disables Export in the preview. Invalid edited actual-time/cost metadata fails safely rather than producing false numeric XML.

## The supplied GanttPRO XML

Verified result: **20 elements (4 groups, 15 tasks, 1 milestone), 14 real editable dependencies and 212 effort hours**. Sensor remains **11 December 2025 09:00 → 15 December 2025 18:00**, 24 working hours / 8 effort hours. No task dates are silently rescheduled.

This file contains a known exporter defect: `Work=PT0H8M0S` represents the eight effort hours visible in the supplied spreadsheet. Correction applies only to the recognized combination:

- GanttPRO's synthetic first `Total estimate` summary, no Finish, `SaveVersion=9`;
- `Author=Export Tool v.2.1.0.0`, `WorkFormat=2`;
- no Resources or Assignments.

That profile converts **Work ×60**, with an explicit review warning and visible totals. Other exporters, missing/different markers and ordinary MSPDI retain literal ISO Work. Desktop writes version 14 with correct ISO hours, so a later import **does not multiply again**. The sanitized fixture retains only the software signature, not personal author data.

**The supplied XML has no resources, assignments, costs, colors or task creation/creator data.** These are not reconstructed from filenames, another file or guessed defaults. Its planned cost remains 0 with a warning; its resource roster remains empty. The supplied **CSV** contains 3 assigned people, colors, 38,000 cost and source metadata; importing that CSV and then exporting XML carries those data. Source `Title=Project1` is also not proof of the original web project name: review/rename it explicitly.

## Standard schedule and metadata

- Namespace `http://schemas.microsoft.com/project`, or an unnamespaced Project.
- UID references, ordered hierarchy, groups/tasks/milestones, local minute-precision Start/Finish, working Duration and Work.
- FS/SS/FF/SF and signed whole-working-minute lag, including summary/milestone endpoints. Unknown endpoints, duplicates/cycles and cross-project links fail validation. Date-inconsistent links are reported, not propagated.
- Explicit Finish takes precedence over inconsistent Duration when representable. Unsupported calendar/endpoints fail before project replacement.
- Total `Cost` takes precedence over `FixedCost`; the model retains a planned total, not resource-rate accounting. Progress, five priority levels, literal Notes and independent date-only Deadline are retained.
- `ActualWork`, `ActualCost` and `CreateDate` import into the existing **text metadata fields**, not a fabricated time journal or accounting subsystem. Export writes their standard elements as well as the literal named field values. Task creator remains a named text field; project Author is not mistaken for task identity.
- Names, notes and text field values retain leading/trailing whitespace, XML metacharacters and line breaks. Notes no longer accumulate generated status/custom-field/baseline lines on repeated local round-trips.
- The writer follows Microsoft's published standard Project/Task/Assignment sequence order. Decimal costs are written without exponent notation or fixed-ten-decimal truncation. Project 2010 manual-scheduling elements remain present; structural tests are not Microsoft Project runtime certification.

## Calendars and assignments

Project weekdays, at most two intervals per weekday, and dated `WeekDay/TimePeriod` ranges are supported. Child-calendar dated ranges override/split inherited ranges; overlapping ranges in the same calendar are rejected. Project hours and independently overridden resource availability can overlap without corrupting one another.

Work-type resources retain names, capacity, weekdays, dated availability and assignments with proportional effort shares. Resource calendars may have **no weekly workdays**, unlike the project's scheduling calendar. Inherited non-project resource calendars and bounded availability overrides are resolved. Negative assignment units are rejected rather than normalized into positive shares.

Separate task calendars, recurring/extended Exceptions, material/cost resources, overnight shifts and more than two daily intervals are not modeled. Resource attendance by clock time is not a resource-shift system; daily capacity/workday warnings explain that boundary. Resource colors, exception names/IDs and native entity IDs are not fully retained. Imported IDs are new local references, not synchronization keys.

## Typed fields, not Notes

Project `ExtendedAttributes/ExtendedAttribute` declares standard `FieldID`, `FieldName`, `CFType`, `Alias` and numeric RollupType. Each task contains real `ExtendedAttribute/FieldID/Value` records.

| Native field | MSPDI representation | Capacity |
|---|---|---:|
| Text | Text1–26, CFType 7 | 26 |
| Number · Sum/Average | Number1–19, CFType 5, RollupType 3/4 | 19 |
| Date | Date1–10, CFType 1, midnight ISO date | 10 |
| Checkbox | Flag1–20, CFType 4, 0/1 | 20 |
| Select, Multi-select, Color, People, Labels | Literal display text in available Text slots | shares 26 |

Zero, False and unset remain distinct. Numeric groups keep sum/average semantics. Complex fields **do not** retain their native type/options/resource-ID lists through XML; preserve JSON for those. Unsupported external field types/rollups are explicitly retained in Notes with their names, not silently discarded or assigned invented types. Unsupported intraday custom Date values are rejected. Duplicate field definitions/values and nonfinite numbers fail before live replacement.

The four CSV metadata field names are recognized so that **every reference CSV table cell survives CSV → XML → CSV**, including literal author/creation/actual-time/actual-cost data. This is local Desktop verification, not website round-trip certification.

Five ordinary, visibly named MSPDI fields preserve additional Desktop semantics:

| Slot | Alias | Value |
|---|---|---|
| Text27 | Gantt Desktop · Цвет | Task `#RRGGBB` |
| Text28 | Gantt Desktop · Статус | open / in_progress / completed / closed |
| Text29 | Gantt Desktop · Базовый план | Selected snapshot name |
| Text30 | Gantt Desktop · Дата базового плана | Selected snapshot creation date |
| Number20 | Gantt Desktop · Прогресс | Exact progress before integer PercentComplete rounding |

Other readers may display these fields without applying Desktop behavior. They are not an opaque native project payload. Contradictory status/progress or invalid/stale named metadata is rejected rather than overriding the visible standard schedule silently.

Only the selected baseline's matching entries are exported as Baseline 0; its plan name and creation date now survive local round-trips. Other snapshots, deleted entries and all original entry names/types are not a complete XML backup. JSON remains authoritative.

## Safety and verification

Parsing stays offline with defusedxml; DTD, entities and external resolution are forbidden. Existing bounds remain 16 MiB, depth 64, 100,000 XML nodes, 2,000 task records, 10,000 links and a 100-year diagram. Dated exception/availability ranges are also bounded to 100 years. Unsupported structures fail in the review stage without partially replacing the live project.

**889 tests passed**, including **55 additional XML cases** in `test_xml_roundtrip.py` and `test_xml_roundtrip_ui.py`. Coverage includes reference-cell equality through XML, source-unit correction/unknown-profile isolation, all four link types and signed lags, typed field capacities/overflow, zero/False, literal whitespace/CRLF, repeated round-trips, baseline metadata, inherited range splitting, disabled resources, stale metadata, native preview/import/export, editable rendered arrows, Undo and safe Save/reopen. Ruff and active Python error diagnostics are clean.

Package: `dist/gantt_desktop-0.16.0-py3-none-any.whl`. All **35 packaged Python/QML files** match source bytes. A temporary installed-wheel check independently passed the actual user XML's dates/types/effort against the user CSV, every actual CSV cell through XML, real QML import/native reviews in both themes, 14 rendered editable arrows, Undo, JSON Save/reopen and all six exports. No QML runtime errors, global installation or real preference changes; all five original user-file digests stayed unchanged.

Reviewed installed-package proof frames: [corrected XML review · light](screenshots/xml-work-review-light.png), [dark](screenshots/xml-work-review-dark.png), [XML export and persistent warning](screenshots/xml-roundtrip-export.png), [round-tripped diagram](screenshots/xml-roundtrip-diagram.png), [real dependency editor](screenshots/xml-roundtrip-dependency.png).

All GUI verification uses private Xvfb with Qt offscreen/software rendering. No automation is placed on the user's desktop. Windows/macOS runtime, accessibility/high-DPI, large-project behavior and independent receiving-application certification remain pending.

Official data references: [PjField enumeration](https://learn.microsoft.com/en-us/office/vba/api/project.pjfield), [CFType](https://learn.microsoft.com/en-us/office-project/xml-data-interchange/cftype-element), [ExtendedAttributes schema](https://learn.microsoft.com/en-us/office-project/xml-data-interchange/xml-schema-for-the-extendedattributes-element), [Project schema](https://learn.microsoft.com/en-us/office-project/xml-data-interchange/xml-schema-for-the-project-element), [Tasks schema](https://learn.microsoft.com/en-us/office-project/xml-data-interchange/xml-schema-for-the-tasks-element), [Assignments schema](https://learn.microsoft.com/en-us/office-project/xml-data-interchange/xml-schema-for-the-assignments-element).
