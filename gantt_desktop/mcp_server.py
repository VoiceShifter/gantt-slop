"""Opt-in loopback server; every document read/write is queued onto the Qt thread."""
from __future__ import annotations

import asyncio
import json
import secrets
import socket
import threading
import weakref
from concurrent.futures import Future
from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from .domain import Project, Task, new_id

if TYPE_CHECKING:
    from .controller import Controller


class McpServer(QObject):
    changed = Signal()
    requested = Signal(str, dict, int, object)

    def __init__(self, controller: Controller):
        super().__init__(controller.dialogs)
        self._controller = weakref.ref(controller)
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
        controller.projectLoaded.connect(self.stop)

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
            "type": "http", "url": self.url, "headers": {"Authorization": f"Bearer {self.token}"},
        }}}, indent=2)

    def start(self, port: int, allow_writes: bool = False) -> None:
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
        return {"revision": self._revision, "project": project.to_dict(), "dirty": controller.dirty,
                "spans": {key: [value.isoformat(timespec="minutes") for value in project.span(key)] for key in project.tasks},
                "undo_label": controller._history[controller._history_index][0] if controller.canUndo else "",
                "redo_label": controller._history[controller._history_index + 1][0] if controller.canRedo else ""}

    def mutate(self, controller: Controller, operation: str, args: dict, messages: list[str]) -> dict:
        project = controller.project
        result = {}
        task_id = args.get("task_id", "")
        if operation in {"edit_task", "delete_task", "assign_resources", "set_assignee"} and task_id not in project.tasks:
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
        if task_id:
            result["task_id"] = task_id
        return result
