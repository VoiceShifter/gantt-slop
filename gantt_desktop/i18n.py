"""Application-wide localization (i18n) for QML and QWidget components."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QSettings, Signal, Slot

LANGUAGES = [
    {"code": "ru", "label": "Русский"},
    {"code": "en", "label": "English"},
]

MONTHS_RU = (
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
)
MONTHS_EN = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

DAYS_RU = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
DAYS_EN = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

STATUSES_RU = {
    "open": "Открыт",
    "in_progress": "В работе",
    "completed": "Выполнено",
    "closed": "Закрыт",
}
STATUSES_EN = {
    "open": "Open",
    "in_progress": "In progress",
    "completed": "Completed",
    "closed": "Closed",
}

PRIORITIES_RU = {
    "highest": "Самый высокий",
    "high": "Высокий",
    "medium": "Средний",
    "low": "Низкий",
    "lowest": "Самый низкий",
}
PRIORITIES_EN = {
    "highest": "Highest",
    "high": "High",
    "medium": "Normal",
    "low": "Low",
    "lowest": "Lowest",
}

FIELD_TYPES_RU = {
    "text": "Текст",
    "number": "Число",
    "date": "Дата",
    "select": "Список",
    "checkbox": "Флажок",
    "color": "Цвет",
    "multi": "Мультиселект",
    "people": "Люди",
    "labels": "Лейблы",
}
FIELD_TYPES_EN = {
    "text": "Text",
    "number": "Number",
    "date": "Date",
    "select": "Dropdown",
    "checkbox": "Checkbox",
    "color": "Color",
    "multi": "Multi-select",
    "people": "People",
    "labels": "Labels",
}

MESSAGES_RU: dict[str, str] = {
    # Settings drawer
    "settings": "Настройки",
    "close_settings": "Закрыть настройки",
    "appearance": "Внешний вид",
    "dark_theme": "Тёмная тема",
    "theme_description": "Одна тема для диаграммы, таблицы, панелей и всех диалогов.",
    "language": "Язык",
    "language_description": "Выбор языка интерфейса приложения.",
    "startup": "Запуск",
    "open_last_file": "Открывать последний файл",
    "open_last_file_description": "При запуске открывать последний отредактированный файл. Если выключено — открывается пустой проект.",
    "settings_note": "Изменения применяются сразу и сохраняются между запусками на этом компьютере. Файл проекта не меняется.",
    "done": "Готово",

    # Main window & Sidebar
    "hide_project_panel": "Скрыть панель проектов",
    "show_project_panel": "Показать панель проектов",
    "local_projects": "Локальные проекты",
    "new_project_btn": "＋  Создать новый проект",
    "current_project": "□   Текущий проект",
    "open_project_btn": "Открыть проект…",
    "save_project_btn": "Сохранить проект",
    "sample_project_btn": "Демонстрационный проект",
    "unsaved_changes": "Есть несохранённые изменения",
    "changes_saved": "Изменения сохранены",
    "local_file_no_account": "Локальный файл · Без аккаунта",
    "help_btn": "?  Помощь",
    "file_menu_btn": "Файл ⌄",
    "baselines_btn": "Базовые планы",
    "baselines_hint": "Базовые планы: создать, выбрать, удалить",
    "local_project": "Локальный проект",
    "settings_btn": "⚙ Настройки",
    "settings_hint": "Настройки приложения",
    "save_btn": "Сохранить",
    "save_hint": "Сохранить · Ctrl+S",
    "chart_tab": "Диаграмма",
    "how_to_use": "▷  Как использовать",

    # Toolbar
    "undo_hint": "Отменить · Ctrl+Z",
    "redo_hint": "Повторить · Ctrl+Shift+Z",
    "bulk_hint": "Массовое изменение задач",
    "add_task_hint": "Добавить задачу",
    "add_milestone_hint": "Добавить веху",
    "add_group_hint": "Добавить группу",
    "critical_path_hint": "Критический путь",
    "expand_all": "⌃ Развернуть все",
    "collapse_all": "⌄ Свернуть все",
    "search_placeholder": "Поиск по имени задачи",
    "fields_btn": "Поля",
    "filter_btn": "Фильтр",
    "time_scale": "Масштаб времени",
    "scale_days": "Дни",
    "scale_weeks": "Недели",
    "scale_months": "Месяцы",
    "scale_quarters": "Кварталы",
    "scale_years": "Годы",
    "export_btn": "Экспорт",
    "view_menu_btn": "Вид ⌄",

    # Menus
    "menu_new_project": "Новый проект",
    "menu_open": "Открыть…",
    "menu_import_xml": "Импорт GanttPRO / MS Project XML…",
    "menu_import_csv": "Импорт GanttPRO CSV…",
    "menu_import_xlsx": "Импорт GanttPRO Excel…",
    "menu_save": "Сохранить",
    "menu_save_as": "Сохранить как…",
    "menu_open_sample": "Открыть демонстрационный проект",
    "menu_mcp": "MCP-сервер…",
    "menu_quit": "Выход",

    "menu_open_task": "Открыть задачу",
    "menu_show_on_chart": "Показать на диаграмме",
    "menu_add_task": "Добавить задачу",
    "menu_add_milestone": "Добавить веху",
    "menu_add_subtask": "Добавить подзадачу",
    "menu_move_up": "Переместить выше",
    "menu_move_down": "Переместить ниже",
    "menu_add_dependency": "Добавить зависимость",
    "menu_delete": "Удалить",

    "menu_advanced_filters": "Расширенные и сохранённые…",
    "menu_no_quick_filter": "Без быстрого фильтра",
    "menu_incomplete": "Незавершённые",
    "menu_complete": "Завершённые",
    "menu_overdue": "Просроченные",
    "menu_clear_filters": "Очистить все условия",

    "menu_to_start": "К началу проекта",
    "menu_to_task": "К выбранной задаче",
    "menu_hide_sidebar": "Скрыть боковую панель",
    "menu_show_sidebar": "Показать боковую панель",
    "menu_reset_columns": "Сбросить ширину таблицы",

    # Bottom bar
    "workload_toggle": "Загрузка ресурсов",
    "people_btn": "Люди…",
    "tasks_count_suffix": "задач",
    "double_click_hint": "Двойной щелчок — свойства задачи",

    # GanttView
    "col_name": "Задача",
    "col_assignee": "Исполнитель",
    "col_effort": "Трудозатраты",
    "col_cost": "Стоимость",
    "col_start": "Начало",
    "col_end": "Завершение",
    "col_deadline": "Крайний срок",
    "col_duration": "Длительность",
    "col_progress": "Прогресс",
    "col_status": "Статус",
    "col_priority": "Приоритет",
    "col_baseline_start": "Базовое начало",
    "col_baseline_end": "Базовое завершение",
    "col_start_variance": "Δ начала, кал. ч",
    "col_end_variance": "Δ завершения, кал. ч",
    "add_fields_hint": "Добавить или выбрать поля",
    "resize_col_tooltip": "Перетащите границу, чтобы изменить ширину колонки",
    "task_actions": "Действия с задачей",
    "add_task_inline": "⊕  Добавить задачу",
    "add_milestone_inline": "Добавить веху",
    "empty_start_hint": "Начните с задачи или группы\nПеретащите блок, чтобы изменить даты",
    "empty_filter_hint": "Нет задач по заданному фильтру",
    "drop_row_hint": "Отпустите строку в таблице.",
    "cannot_move_row": "Нельзя переместить строку.",
    "hour_unit": "ч",
    "week_unit": "н",

    # TaskInspector
    "task_color": "Цвет задачи",
    "close": "Закрыть",
    "add_link": "＋  Добавить зависимость",
    "add_link_short": "＋ Связь",
    "float_not_calculated": "Резерв не рассчитан: ",
    "critical_group": "Критическая группа. ",
    "critical_task": "Критическая задача. ",
    "float_prefix": "Резерв: ",
    "work_h": " рабочих ч.",
    "cal_h": " календарных ч.",
    "start_label": "Начало",
    "end_label": "Завершение",
    "duration_h": "Длительность, ч",
    "effort_h": "Трудозатраты, ч",
    "cost_label": "Стоимость",
    "choose_resources_hint": "Выбрать ресурсы и распределить часы",
    "baseline_prefix": "Базовый план: ",
    "baseline_start_prefix": "Начало: ",
    "baseline_end_prefix": " · завершение: ",
    "delta_start_prefix": "\nΔ начала: ",
    "delta_end_prefix": " · Δ завершения: ",
    "baseline_missing_item": "Элемента нет в выбранном базовом плане.",
    "deadline_label": "Крайний срок",
    "not_set": "Не задан",
    "remove_deadline_hint": "Убрать крайний срок",
    "deadline_missed": "Плановое завершение позже крайнего срока.",
    "deadline_passed": "Крайний срок прошёл, задача не завершена.",
    "dates_locked_deps": "Даты закреплены зависимостями. Чтобы сдвинуть задачу, измените связь или её лаг.",
    "group_label": "Группа",
    "task_desc_placeholder": "Добавить описание задачи",
    "task_deps_title": "Зависимости между задачами",
    "predecessor": "ПРЕДШЕСТВЕННИК",
    "successor": "ПОСЛЕДОВАТЕЛЬ",
    "lag_label": "Лаг: ",
    "delete_link_hint": "Удалить связь (можно отменить)",
    "show_on_chart": "Показать на диаграмме",
    "delete_task_btn": "Удалить задачу",

    # BulkEditor
    "bulk_edit_title": "Массовое изменение",
    "cancel_unapplied": "Отменить неприменённые изменения",
    "selected_prefix": "Выбрано: ",
    "unassign": "Снять назначение",
    "choose_color": "Выбрать цвет…",
    "keep_color_hint": "Не менять цвет",
    "bulk_note": "Отмечаются только нужные поля. Статус меняет процент выполнения; даты и трудозатраты сохраняются.",
    "apply_changes": "Применить изменения",
    "delete_tasks_prefix": "Удалить задачи (",
    "dont_change": "Не менять",

    # AssigneePicker
    "assignees": "Исполнители",
    "find_resource": "Найти ресурс",
    "no_resources_found": "Ресурсы не найдены",
    "selected_count_prefix": "Выбрано: ",
    "apply_by_ok": " · Применить по «Ок»",
    "reset": "Сбросить",
    "hours_btn": "Часы…",
    "cancel": "Отмена",
    "ok": "Ок",
    "add_resource_btn": "＋ Добавить ресурс…",

    # ResourceWorkload
    "hours_mode": "Часы",
    "percent_mode": "Проценты",
    "tasks_mode": "Задачи",
    "hide_workload": "Скрыть загрузку ресурсов",
    "resource_calendar_hint": "Календарь ресурса",
    "overload": "Перегрузка",
    "weekend_work": "Работа в выходной",
    "empty_workload_hint": "Добавьте людей и назначьте их задачам",

    # Other QML
    "choose_date_in_calendar": "Выбрать дату в календаре",
    "link_from_start": "Связь от начала задачи",
    "link_from_end": "Связь от завершения задачи",
    "checkbox_field": "Флажок",
    "field_label": "Поле",
    "change_field_value": "Изменить значение поля",
    "value_read_only": "Значение вычисляется или редактирование недоступно",
    "unassigned": "Не назначен",
    "assignee_prefix": "Исполнитель: ",
    "choose_assignees_hint": "Выбрать исполнителей из ресурсов проекта",
    "critical_label": "Критическая",
    "critical_comma": ", критическая",

    # Dialogs & Controller
    "no_file": "Без файла",
    "save": "Сохранить",
    "delete": "Удалить",
    "apply": "Применить",
    "create": "Создать",
    "edit": "Изменить…",
    "remove": "Удалить…",
    "add_ellipsis": "Добавить…",
}

MESSAGES_EN: dict[str, str] = {
    # Settings drawer
    "settings": "Settings",
    "close_settings": "Close settings",
    "appearance": "Appearance",
    "dark_theme": "Dark theme",
    "theme_description": "One theme for chart, table, panels and all dialogs.",
    "language": "Language",
    "language_description": "Choose application interface language.",
    "startup": "Startup",
    "open_last_file": "Open last edited file",
    "open_last_file_description": "Open the last edited project file on startup. If disabled, a blank project is opened.",
    "settings_note": "Changes apply immediately and are saved across launches on this computer. The project file does not change.",
    "done": "Done",

    # Main window & Sidebar
    "hide_project_panel": "Hide project panel",
    "show_project_panel": "Show project panel",
    "local_projects": "Local projects",
    "new_project_btn": "＋  Create new project",
    "current_project": "□   Current project",
    "open_project_btn": "Open project…",
    "save_project_btn": "Save project",
    "sample_project_btn": "Sample project",
    "unsaved_changes": "Unsaved changes",
    "changes_saved": "Changes saved",
    "local_file_no_account": "Local file · No account",
    "help_btn": "?  Help",
    "file_menu_btn": "File ⌄",
    "baselines_btn": "Baselines",
    "baselines_hint": "Baselines: create, select, delete",
    "local_project": "Local project",
    "settings_btn": "⚙ Settings",
    "settings_hint": "Application settings",
    "save_btn": "Save",
    "save_hint": "Save · Ctrl+S",
    "chart_tab": "Gantt chart",
    "how_to_use": "▷  How to use",

    # Toolbar
    "undo_hint": "Undo · Ctrl+Z",
    "redo_hint": "Redo · Ctrl+Shift+Z",
    "bulk_hint": "Bulk edit tasks",
    "add_task_hint": "Add task",
    "add_milestone_hint": "Add milestone",
    "add_group_hint": "Add group",
    "critical_path_hint": "Critical path",
    "expand_all": "⌃ Expand all",
    "collapse_all": "⌄ Collapse all",
    "search_placeholder": "Search tasks by name",
    "fields_btn": "Fields",
    "filter_btn": "Filter",
    "time_scale": "Time scale",
    "scale_days": "Days",
    "scale_weeks": "Weeks",
    "scale_months": "Months",
    "scale_quarters": "Quarters",
    "scale_years": "Years",
    "export_btn": "Export",
    "view_menu_btn": "View ⌄",

    # Menus
    "menu_new_project": "New project",
    "menu_open": "Open…",
    "menu_import_xml": "Import GanttPRO / MS Project XML…",
    "menu_import_csv": "Import GanttPRO CSV…",
    "menu_import_xlsx": "Import GanttPRO Excel…",
    "menu_save": "Save",
    "menu_save_as": "Save as…",
    "menu_open_sample": "Open sample project",
    "menu_mcp": "MCP server…",
    "menu_quit": "Quit",

    "menu_open_task": "Open task",
    "menu_show_on_chart": "Show on chart",
    "menu_add_task": "Add task",
    "menu_add_milestone": "Add milestone",
    "menu_add_subtask": "Add subtask",
    "menu_move_up": "Move up",
    "menu_move_down": "Move down",
    "menu_add_dependency": "Add dependency",
    "menu_delete": "Delete",

    "menu_advanced_filters": "Advanced and saved…",
    "menu_no_quick_filter": "No quick filter",
    "menu_incomplete": "Incomplete",
    "menu_complete": "Completed",
    "menu_overdue": "Overdue",
    "menu_clear_filters": "Clear all filters",

    "menu_to_start": "Go to project start",
    "menu_to_task": "Go to selected task",
    "menu_hide_sidebar": "Hide sidebar",
    "menu_show_sidebar": "Show sidebar",
    "menu_reset_columns": "Reset column widths",

    # Bottom bar
    "workload_toggle": "Resource workload",
    "people_btn": "People…",
    "tasks_count_suffix": "tasks",
    "double_click_hint": "Double-click for task details",

    # GanttView
    "col_name": "Task",
    "col_assignee": "Assignee",
    "col_effort": "Effort",
    "col_cost": "Cost",
    "col_start": "Start",
    "col_end": "End",
    "col_deadline": "Deadline",
    "col_duration": "Duration",
    "col_progress": "Progress",
    "col_status": "Status",
    "col_priority": "Priority",
    "col_baseline_start": "Baseline start",
    "col_baseline_end": "Baseline end",
    "col_start_variance": "Δ start, cal. h",
    "col_end_variance": "Δ end, cal. h",
    "add_fields_hint": "Add or choose fields",
    "resize_col_tooltip": "Drag border to resize column",
    "task_actions": "Task actions",
    "add_task_inline": "⊕  Add task",
    "add_milestone_inline": "Add milestone",
    "empty_start_hint": "Start with a task or group\nDrag a bar to adjust dates",
    "empty_filter_hint": "No tasks match the active filter",
    "drop_row_hint": "Drop row in the table.",
    "cannot_move_row": "Cannot move row.",
    "hour_unit": "h",
    "week_unit": "w",

    # TaskInspector
    "task_color": "Task color",
    "close": "Close",
    "add_link": "＋  Add dependency",
    "add_link_short": "＋ Link",
    "float_not_calculated": "Float not calculated: ",
    "critical_group": "Critical group. ",
    "critical_task": "Critical task. ",
    "float_prefix": "Float: ",
    "work_h": " work h",
    "cal_h": " cal. h",
    "start_label": "Start",
    "end_label": "End",
    "duration_h": "Duration, h",
    "effort_h": "Effort, h",
    "cost_label": "Cost",
    "choose_resources_hint": "Choose resources and allocate hours",
    "baseline_prefix": "Baseline: ",
    "baseline_start_prefix": "Start: ",
    "baseline_end_prefix": " · end: ",
    "delta_start_prefix": "\nΔ start: ",
    "delta_end_prefix": " · Δ end: ",
    "baseline_missing_item": "Item not present in selected baseline.",
    "deadline_label": "Deadline",
    "not_set": "Not set",
    "remove_deadline_hint": "Remove deadline",
    "deadline_missed": "Planned completion is after the deadline.",
    "deadline_passed": "Deadline passed, task is not complete.",
    "dates_locked_deps": "Dates are constrained by dependencies. To move the task, change the dependency or its lag.",
    "group_label": "Group",
    "task_desc_placeholder": "Add task description",
    "task_deps_title": "Task dependencies",
    "predecessor": "PREDECESSOR",
    "successor": "SUCCESSOR",
    "lag_label": "Lag: ",
    "delete_link_hint": "Delete link (can be undone)",
    "show_on_chart": "Show on chart",
    "delete_task_btn": "Delete task",

    # BulkEditor
    "bulk_edit_title": "Bulk edit",
    "cancel_unapplied": "Cancel unapplied changes",
    "selected_prefix": "Selected: ",
    "unassign": "Unassign",
    "choose_color": "Choose color…",
    "keep_color_hint": "Do not change color",
    "bulk_note": "Only checked fields are applied. Status changes progress percentage; dates and effort are preserved.",
    "apply_changes": "Apply changes",
    "delete_tasks_prefix": "Delete tasks (",
    "dont_change": "Do not change",

    # AssigneePicker
    "assignees": "Assignees",
    "find_resource": "Find resource",
    "no_resources_found": "No resources found",
    "selected_count_prefix": "Selected: ",
    "apply_by_ok": " · Click OK to apply",
    "reset": "Reset",
    "hours_btn": "Hours…",
    "cancel": "Cancel",
    "ok": "OK",
    "add_resource_btn": "＋ Add resource…",

    # ResourceWorkload
    "hours_mode": "Hours",
    "percent_mode": "Percentages",
    "tasks_mode": "Tasks",
    "hide_workload": "Hide resource workload",
    "resource_calendar_hint": "Resource calendar",
    "overload": "Overload",
    "weekend_work": "Weekend work",
    "empty_workload_hint": "Add people and assign them to tasks",

    # Other QML
    "choose_date_in_calendar": "Choose date from calendar",
    "link_from_start": "Link from task start",
    "link_from_end": "Link from task end",
    "checkbox_field": "Checkbox",
    "field_label": "Field",
    "change_field_value": "Change field value",
    "value_read_only": "Value is calculated or read-only",
    "unassigned": "Unassigned",
    "assignee_prefix": "Assignee: ",
    "choose_assignees_hint": "Choose assignees from project resources",
    "critical_label": "Critical",
    "critical_comma": ", critical",

    # Dialogs & Controller
    "no_file": "No file",
    "save": "Save",
    "delete": "Delete",
    "apply": "Apply",
    "create": "Create",
    "edit": "Edit…",
    "remove": "Delete…",
    "add_ellipsis": "Add…",
}


class I18n(QObject):
    changed = Signal()

    def __init__(self, settings: QSettings | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._settings = settings
        saved = str(settings.value("general/language", "ru")) if settings is not None else "ru"
        self._language = saved if saved in {"ru", "en"} else "ru"

    @Property(str, notify=changed)
    def language(self) -> str:
        return self._language

    @Property(list, constant=True)
    def languages(self) -> list[dict[str, str]]:
        return list(LANGUAGES)

    @Property(dict, notify=changed)
    def tr(self) -> dict[str, str]:
        return MESSAGES_EN if self._language == "en" else MESSAGES_RU

    @Property(list, notify=changed)
    def months(self) -> tuple[str, ...]:
        return MONTHS_EN if self._language == "en" else MONTHS_RU

    @Property(list, notify=changed)
    def dayNames(self) -> tuple[str, ...]:
        return DAYS_EN if self._language == "en" else DAYS_RU

    @Property(dict, notify=changed)
    def statuses(self) -> dict[str, str]:
        return STATUSES_EN if self._language == "en" else STATUSES_RU

    @Property(dict, notify=changed)
    def priorities(self) -> dict[str, str]:
        return PRIORITIES_EN if self._language == "en" else PRIORITIES_RU

    @Slot(str)
    def setLanguage(self, language: str) -> None:
        if language not in {"ru", "en"} or self._language == language:
            return
        self._language = language
        if self._settings is not None:
            self._settings.setValue("general/language", language)
            self._settings.sync()
        self.changed.emit()

    @Slot(str, result=str)
    def t(self, key: str) -> str:
        messages = MESSAGES_EN if self._language == "en" else MESSAGES_RU
        return messages.get(key, key)


_GLOBAL_I18N: I18n | None = None


def get_i18n() -> I18n:
    global _GLOBAL_I18N
    if _GLOBAL_I18N is not None:
        try:
            _ = _GLOBAL_I18N.language
        except RuntimeError:
            _GLOBAL_I18N = None
    if _GLOBAL_I18N is None:
        _GLOBAL_I18N = I18n()
    return _GLOBAL_I18N


def set_i18n(instance: I18n | None) -> None:
    global _GLOBAL_I18N
    _GLOBAL_I18N = instance


def tr(key: str, default: str | None = None) -> str:
    i18n = get_i18n()
    res = i18n.t(key)
    if res == key and default is not None:
        return default
    return res
