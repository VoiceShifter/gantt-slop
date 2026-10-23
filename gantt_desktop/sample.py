"""A synthetic device-planning example, independently transcribed from the visible reference."""
from datetime import datetime

from .domain import Dependency, Project, Task


def sample_project() -> Project:
    project = Project()
    groups = [("planning", "Планирование", "2025-12-01"),
              ("preparation", "Подготовка", "2025-12-31"),
              ("case", "Создать кейс для девайса", "2026-01-07"),
              ("assembly", "Сборка", "2026-01-21")]
    for task_id, name, day in groups:
        project.tasks[task_id] = Task(task_id, name, datetime.fromisoformat(day + "T09:00"),
                                     duration=0, kind="group")
    # Duration and effort are deliberately separate quantities, just as in the reference.
    items = [
        ("scenario", "planning", "Определение сценария", "2025-12-01T09:00", 64, 40, 0, "Клиент"),
        ("sensor", "planning", "Выбор сенсора", "2025-12-15T09:00", 24, 8, 0, "Клиент"),
        ("controller", "planning", "Выбор системы контроля", "2025-12-18T09:00", 32, 16, 0, "Клиент"),
        ("protocol", "planning", "Выбор протокола", "2025-12-24T09:00", 24, 16, 0, "Клиент"),
        ("router", "planning", "Выбор роутера", "2025-12-29T09:00", 16, 8, 0, "Клиент"),
        ("supplier", "preparation", "Выбрать поставщика сенсора", "2025-12-31T09:00", 24, 16, 0, "Клиент"),
        ("supplier-control", "preparation", "Выбрать поставщика контроллеров", "2026-01-05T09:00", 16, 8, 0, "Клиент"),
        ("components", "preparation", "Приобретение компонентов", "2026-01-07T09:00", 0, 0, 10000, "Клиент"),
        ("prototype", "preparation", "Прототипирование на макетной плате", "2026-01-07T09:00", 80, 8, 0, "Клиент"),
        ("model", "case", "Смоделировать кейс", "2026-01-07T09:00", 26, 26, 10000, "3д артист"),
        ("material", "case", "Выбрать материал для кейса", "2026-01-12T11:00", 8, 8, 0, "3д артист"),
        ("print", "case", "Распечатать кейс", "2026-01-14T09:00", 16, 8, 5000, "3д артист"),
        ("solder", "assembly", "Пайка девайса", "2026-01-21T09:00", 32, 16, 3000, "Электрик"),
        ("electric", "assembly", "Проведение электричества", "2026-01-21T09:00", 32, 16, 5000, "Электрик"),
        ("assemble", "assembly", "Сборка финального проекта", "2026-01-27T09:00", 16, 8, 5000, "Электрик"),
        ("configure", "assembly", "Настройка сценариев в приложении", "2026-01-29T09:00", 80, 10, 0, "Клиент"),
    ]
    for task_id, parent, name, start, hours, effort, cost, assignee in items:
        project.tasks[task_id] = Task(
            task_id, name, datetime.fromisoformat(start), int(hours * 60), parent,
            "milestone" if not hours else "task", assignee=assignee, effort=effort, cost=cost,
            color="#d65ab1" if not hours else "#50c7d6",
        )
    pairs = [("sensor", "controller"), ("controller", "protocol"), ("protocol", "router"),
             ("router", "supplier"), ("supplier", "supplier-control"),
             ("supplier-control", "components"), ("components", "prototype"),
             ("components", "model"), ("model", "material"), ("material", "print"),
             ("prototype", "solder"), ("prototype", "electric"),
             ("solder", "assemble"), ("electric", "assemble"), ("assemble", "configure")]
    for index, (source, target) in enumerate(pairs):
        lag = project.calendar.between(project.span(source)[1], project.tasks[target].start)
        project.dependencies.append(Dependency(f"link-{index}", source, target, "FS", lag))
    project.validate()
    return project
