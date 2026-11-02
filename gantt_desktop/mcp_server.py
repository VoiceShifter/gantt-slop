"""Opt-in loopback server; every document read/write is queued onto the Qt thread."""
from __future__ import annotations

import asyncio
import json
import secrets
import socket
import threading
import weakref
from concurrent.futures import Future
from copy import deepcopy
from datetime import date, datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QSettings, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from .domain import Project, Task, new_id

if TYPE_CHECKING:
    from .controller import Controller


class McpServer(QObject):
    changed = Signal()
    requested = Signal(str, dict, int, object)

    def __init__(self, controller: Controller, settings: QSettings | None = None):
        super().__init__(controller.dialogs)
        self._controller = weakref.ref(controller)
        self._settings = settings if settings is not None else getattr(controller, "settings", None)
        self.persistent_token_enabled = False
        self.persistent_token = ""
        if self._settings is not None:
            self.persistent_token_enabled = bool(self._settings.value("mcp/persistent_token", False, type=bool))
            self.persistent_token = str(self._settings.value("mcp/token", "") or "")
        self._generation = 0
        self._revision = 0
        self._enabled = False
        self.allow_writes = False
        self.token = ""
        self.url = ""
        self.status = "Выключен"
        self._server = None
        self._thread: threading.Thread | None = None
        self._failure = ""
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._poll)
        self.requested.connect(self._dispatch, Qt.ConnectionType.QueuedConnection)
        controller.historyChanged.connect(self._revised)
        controller.projectLoaded.connect(self._on_project_loaded)

    @property
    def settings(self) -> QSettings | None:
        if self._settings is not None:
            return self._settings
        controller = self._controller()
        if controller is not None and getattr(controller, "settings", None) is not None:
            self._settings = controller.settings
            return self._settings
        return None

    def _ensure_settings(self) -> QSettings:
        current = self.settings
        if current is not None:
            return current
        self._settings = QSettings()
        return self._settings

    def get_persistent_token(self) -> str:
        if not self.persistent_token:
            current = self.settings
            if current is not None:
                stored = str(current.value("mcp/token", "") or "")
                if stored:
                    self.persistent_token = stored
            if not self.persistent_token:
                self.regenerate_persistent_token()
        return self.persistent_token

    def set_persistent_token(self, token: str) -> None:
        self.persistent_token = token
        settings = self._ensure_settings()
        settings.setValue("mcp/token", token)
        settings.sync()

    def regenerate_persistent_token(self) -> str:
        new_token = secrets.token_urlsafe(32)
        self.set_persistent_token(new_token)
        return new_token

    def set_persistent_token_enabled(self, enabled: bool) -> None:
        self.persistent_token_enabled = enabled
        settings = self._ensure_settings()
        settings.setValue("mcp/persistent_token", enabled)
        settings.sync()
        if enabled and not self.persistent_token:
            self.get_persistent_token()

    @Slot()
    def _on_project_loaded(self):
        if self.persistent_token_enabled and self.active:
            self._revision = 0
            self.changed.emit()
        else:
            self.stop()

    @Slot()
    def _revised(self):
        self._revision += 1

    @property
    def active(self) -> bool:
        return self._enabled

    @property
    def running(self) -> bool:
        return self.active and self._server is not None and self._server.started

    @property
    def label(self) -> str:
        if not self.active:
            return ""
        return "MCP · " + ("изменения" if self.allow_writes else "чтение")

    def configuration(self) -> str:
        if not self.running:
            return ""
        return json.dumps({"mcpServers": {"gantt-desktop": {
            "type": "http",
            "url": self.url,
            "httpUrl": self.url,
            "headers": {"Authorization": f"Bearer {self.token}"},
        }}}, indent=2)

    def start(self, port: int, allow_writes: bool = False, token: str | None = None) -> None:
        if self._thread is not None:
            raise ValueError("Сначала остановите текущий MCP-сервер.")
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("Порт должен быть от 0 до 65535.")
        import uvicorn

        from .mcp_transport import build_app

        sock = socket.create_server(("127.0.0.1", port), backlog=16)
        try:
            sock.setblocking(False)
            port = sock.getsockname()[1]
            if not token:
                if self.persistent_token_enabled and self.get_persistent_token():
                    token = self.get_persistent_token()
                else:
                    token = secrets.token_urlsafe(32)
            generation = self._generation + 1
            app = build_app(self.request, generation, token, port, allow_writes)
            server = uvicorn.Server(uvicorn.Config(app, log_config=None, log_level="warning", access_log=False,
                                                  ws="none", limit_concurrency=16, timeout_keep_alive=2,
                                                  timeout_graceful_shutdown=1))
        except Exception:
            sock.close()
            raise
        self._generation = generation
        self._enabled, self.allow_writes = True, allow_writes
        self.token, self.url = token, f"http://127.0.0.1:{port}/mcp"
        self.status, self._failure = "Запуск…", ""
        self._server = server

        def serve():
            try:
                server.run(sockets=[sock])
            except (OSError, RuntimeError, ValueError, SystemExit) as error:
                self._failure = str(error)
            finally:
                sock.close()

        self._thread = threading.Thread(target=serve, name="gantt-mcp", daemon=True)
        self._thread.start()
        self._timer.start()
        self.changed.emit()

    @Slot()
    def _poll(self):
        if self._thread is not None and not self._thread.is_alive():
            failure = self._failure
            self.stop()
            if failure:
                self.status = "Ошибка MCP: " + failure
                self.changed.emit()
        elif self.running and self.status == "Запуск…":
            self.status = "Включён · " + ("чтение и изменения" if self.allow_writes else "только чтение")
            self.changed.emit()

    @Slot()
    def stop(self):
        # Revoke queued requests before waiting for HTTP shutdown; never pump Qt here.
        self._enabled = False
        self._generation += 1
        self.token = self.url = ""
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=2)
            if self._thread.is_alive():
                self.status = "Остановка…"
                self.changed.emit()
                return
        self._thread = self._server = None
        self._timer.stop()
        self.status = "Выключен"
        self.changed.emit()

    async def request(self, operation: str, arguments: dict, generation: int) -> dict:
        future: Future = Future()
        self.requested.emit(operation, arguments, generation, future)
        try:
            return await asyncio.wait_for(asyncio.wrap_future(future), timeout=15)
        except TimeoutError as error:
            raise ValueError("Desktop request timed out. Re-read the project; do not blindly retry a mutation.") from error

    @Slot(str, dict, int, object)
    def _dispatch(self, operation: str, arguments: dict, generation: int, future: Future):
        # Cancellation before delivery prevents a late edit after disconnect/timeout.
        if not future.set_running_or_notify_cancel():
            return
        try:
            if not self.active or generation != self._generation:
                raise ValueError("MCP access has been revoked. Reconnect using the current desktop configuration.")
            controller = self._controller()
            if controller is None:
                raise ValueError("The desktop is closed.")
            if operation == "get_project":
                result = self.snapshot(controller)
            else:
                if not self.allow_writes:
                    raise ValueError("Read-only MCP access.")
                if arguments.pop("expected_revision", None) != self._revision:
                    raise ValueError("Stale revision. Call get_project before editing.")
                window = controller.dialogs.window
                if (controller.dialogs.modalOpen or QApplication.activeModalWidget() is not None or controller.bulkMode
                        or QGuiApplication.mouseButtons() != Qt.MouseButton.NoButton
                        or window is not None and (window.property("modalBlocked") or window.property("editingText"))):
                    raise ValueError("Desktop is busy. Finish editing/dragging and close dialogs before making MCP changes.")
                revision = self._revision
                messages: list[str] = []
                controller.toast.connect(messages.append)
                try:
                    result = self.mutate(controller, operation, arguments, messages)
                finally:
                    controller.toast.disconnect(messages.append)
                result.update(revision=self._revision, changed=revision != self._revision)
            future.set_result(result)
        except Exception as error:  # noqa: BLE001 - forward failures across the Qt/async boundary
            future.set_exception(error)

    def snapshot(self, controller: Controller) -> dict:
        project = controller.project
        from .critical_path import analyze
        critical_info = None
        try:
            critical = analyze(project)
            critical_info = {
                "critical_tasks": sorted(critical.critical_tasks),
                "critical_links": sorted(critical.critical_links),
                "total_float": critical.total_float,
                "finish": critical.finish.isoformat(timespec="minutes") if critical.finish else None,
            }
        except Exception as error:  # noqa: BLE001
            critical_info = {"error": str(error)}
        return {"revision": self._revision, "project": project.to_dict(), "dirty": controller.dirty,
                "spans": {key: [value.isoformat(timespec="minutes") for value in project.span(key)] for key in project.tasks},
                "critical_path": critical_info,
                "undo_label": controller._history[controller._history_index][0] if controller.canUndo else "",
                "redo_label": controller._history[controller._history_index + 1][0] if controller.canRedo else ""}

    def mutate(self, controller: Controller, operation: str, args: dict, messages: list[str]) -> dict:
        project = controller.project
        result = {}
        task_id = args.get("task_id", "")
        if operation in {"edit_task", "delete_task", "assign_resources", "set_assignee",
                         "set_custom_value", "move_task", "relocate_task"} and task_id not in project.tasks:
            raise ValueError("Unknown task ID.")
        if operation == "create_task":
            task_id = new_id()
            start = datetime.fromisoformat(args["start"])
            if start.tzinfo is not None or start.second or start.microsecond:
                raise ValueError("Use a local ISO date/time with minute precision and no timezone.")

            def add(p: Project):
                previous = p.group_anchors()
                p.tasks[task_id] = Task(task_id, args["name"], p.calendar.normalize(start), args["duration_minutes"],
                                        args["parent"], args["kind"])
                p.validate()
                p.hierarchy_changed(p.ancestors(task_id), previous)
                for key in p.tasks:
                    p.span(key)
            success = controller.edit("MCP · Добавление задачи", add)
        elif operation == "edit_task":
            success = controller.editField(task_id, args["field"], args["value"])
        elif operation == "set_assignee":
            success = controller.editField(task_id, "assignee", args.get("assignee", ""))
        elif operation == "delete_task":
            if project.descendants(task_id) and not args["include_descendants"]:
                raise ValueError("Deleting a nonempty group requires include_descendants=true.")
            success = controller.edit("MCP · Удаление задачи", lambda p: p.remove(task_id))
        elif operation == "assign_resources":
            success = controller.chooseTaskResources(task_id, args["resource_ids"])
        elif operation == "save_dependency":
            dependency_id = args["dependency_id"]
            values = (args["source"], args["target"], args["kind"], str(args["lag_minutes"] / 60))
            if dependency_id:
                success = controller.updateDependency(dependency_id, *values)
            else:
                previous_ids = {link.id for link in project.dependencies}
                success = controller.addDependency(*values)
                if success:
                    dependency_id = next(link.id for link in controller.project.dependencies if link.id not in previous_ids)
            result["dependency_id"] = dependency_id
        elif operation == "delete_dependency":
            key = args["dependency_id"]
            if not any(link.id == key for link in project.dependencies):
                raise ValueError("Unknown dependency ID.")
            success = controller.edit("MCP · Удаление зависимости",
                                      lambda p: setattr(p, "dependencies", [link for link in p.dependencies if link.id != key]))
        elif operation == "rename_project":
            name = args["name"]
            success = controller.edit("MCP · Название проекта", lambda p: setattr(p, "name", name))
            result["name"] = name
        elif operation == "save_resource":
            resource_id = args.get("resource_id", "")
            name = args["name"]
            capacity = args.get("capacity", 8.0)
            workdays = args.get("workdays", list(range(5)))
            key = controller.saveResource(resource_id, name, str(capacity), workdays)
            success = bool(key)
            result["resource_id"] = key
        elif operation == "delete_resource":
            resource_id = args["resource_id"]
            if resource_id not in project.resources:
                raise ValueError("Unknown resource ID.")
            success = controller.removeResource(resource_id)
            result["resource_id"] = resource_id
        elif operation == "save_custom_field":
            field_id = args.get("field_id", "")
            name = args["name"]
            kind = args.get("kind", "text")
            options = args.get("options", [])
            aggregate = args.get("aggregate", "")
            key = controller.saveCustomField(field_id, name, kind, options, aggregate)
            success = bool(key)
            result["field_id"] = key
        elif operation == "delete_custom_field":
            field_id = args["field_id"]
            if field_id not in project.custom_fields:
                raise ValueError("Unknown custom field ID.")
            success = controller.removeCustomField(field_id)
            result["field_id"] = field_id
        elif operation == "set_custom_value":
            field_id = args["field_id"]
            if field_id not in project.custom_fields:
                raise ValueError("Unknown custom field ID.")
            success = controller.setCustomValue(task_id, field_id, args.get("value"))
            result["field_id"] = field_id
        elif operation == "create_baseline":
            name = args["name"]
            baseline_id = controller.createBaseline(name)
            success = bool(baseline_id)
            result["baseline_id"] = baseline_id
        elif operation == "select_baseline":
            baseline_id = args.get("baseline_id", "")
            if baseline_id and baseline_id not in project.baselines:
                raise ValueError("Unknown baseline ID.")
            success = controller.selectBaseline(baseline_id)
            result["baseline_id"] = baseline_id
        elif operation == "delete_baseline":
            baseline_id = args["baseline_id"]
            if baseline_id not in project.baselines:
                raise ValueError("Unknown baseline ID.")
            success = controller.removeBaseline(baseline_id)
            result["baseline_id"] = baseline_id
        elif operation == "set_project_workdays":
            workdays = args["workdays"]
            success = controller.setProjectWorkdays(workdays)
            result["workdays"] = sorted(workdays)
        elif operation == "set_holidays":
            raw_holidays = args["holidays"]
            try:
                parsed_holidays = {date.fromisoformat(h) for h in raw_holidays}
            except ValueError as error:
                raise ValueError(f"Invalid holiday date format: {error}") from error

            def update_holidays(p: Project):
                calendar = deepcopy(p.calendar)
                calendar.holidays = parsed_holidays
                p.set_calendar(calendar)

            success = controller.edit("MCP · Праздники проекта", update_holidays)
            result["holidays"] = sorted(h.isoformat() for h in parsed_holidays)
        elif operation == "move_task":
            days = args["days"]
            success = controller.moveTask(task_id, days)
        elif operation == "relocate_task":
            target_id = args.get("target_id", "")
            placement = args.get("placement", "after")
            if target_id and target_id not in project.tasks:
                raise ValueError("Unknown target task ID.")
            success = controller.relocateRow(task_id, target_id, placement)
            result["target_id"] = target_id
            result["placement"] = placement
        elif operation == "bulk_edit_tasks":
            task_ids = args.get("task_ids", [])
            if not task_ids:
                raise ValueError("No task IDs provided for bulk edit.")
            for tid in task_ids:
                if tid not in project.tasks:
                    raise ValueError(f"Unknown task ID: {tid}")
            status = args.get("status", "")
            priority = args.get("priority", "")
            color = args.get("color", "")
            has_assignee = "assignee" in args and args["assignee"] is not None
            assignee_val = args.get("assignee", "")
            has_resources = "resource_ids" in args and args["resource_ids"] is not None
            resource_ids_val = args.get("resource_ids", [])

            def apply_bulk(p: Project):
                for tid in task_ids:
                    t = p.tasks[tid]
                    if status and t.kind != "group":
                        t.set_status(status)
                    if priority and t.kind != "group":
                        t.priority = priority
                    if color:
                        t.color = color
                    if has_assignee and t.kind != "group":
                        p.assign_name(tid, assignee_val)
                    elif has_resources and t.kind != "group":
                        p.assign_resources(tid, list(resource_ids_val))

            success = controller.edit("MCP · Массовое изменение задач", apply_bulk)
            result["task_ids"] = task_ids
        elif operation in {"undo", "redo"}:
            if operation == "undo":
                controller.undo()
            else:
                controller.redo()
            success = True
        else:
            raise ValueError("Unknown MCP operation.")
        if not success:
            raise ValueError(messages[-1] if messages else "Desktop rejected the change.")
        if task_id and "task_id" not in result:
            result["task_id"] = task_id
        return result
