"""MSPDI custom-field slots (Microsoft PjField and CFType enumerations)."""

# https://learn.microsoft.com/en-us/office/vba/api/project.pjfield
FIELD_IDS = {
    "text": (188743731, 188743734, 188743737, 188743740, 188743743,
             *range(188743746, 188743751), *range(188743997, 188744013)),
    "number": (*range(188743767, 188743772), *range(188743982, 188743996)),
    "date": tuple(range(188743945, 188743955)),
    "checkbox": (*range(188743752, 188743762), *range(188743972, 188743982)),
}
CF_TYPES = {"text": 7, "number": 5, "date": 1, "checkbox": 4}
FIELD_NAMES = {"text": "Text", "number": "Number", "date": "Date", "checkbox": "Flag"}
# Ordinary, named MSPDI fields, not a hidden project snapshot. Other readers can
# display them as Text27–30 / Number20 without understanding Desktop semantics.
METADATA_FIELDS = (
    ("color", 188744013, "Text27", "Gantt Desktop · Цвет", 7),
    ("status", 188744014, "Text28", "Gantt Desktop · Статус", 7),
    ("baseline", 188744015, "Text29", "Gantt Desktop · Базовый план", 7),
    ("baseline_created", 188744016, "Text30", "Gantt Desktop · Дата базового плана", 7),
    ("progress", 188743996, "Number20", "Gantt Desktop · Прогресс", 5),
)


def export_fields(project):
    fields = []
    counts = dict.fromkeys(FIELD_IDS, 0)
    for field_ in project.custom_fields.values():
        kind = field_.kind if field_.kind in FIELD_IDS else "text"
        index = counts[kind]
        if index >= len(FIELD_IDS[kind]):
            raise ValueError("Превышен лимит XML-полей типа "+FIELD_NAMES[kind]+". Сохраните полный проект как .gantt.json.")
        fields.append((field_, kind, FIELD_IDS[kind][index], FIELD_NAMES[kind]+str(index+1)))
        counts[kind] += 1
    return fields
