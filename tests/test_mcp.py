import asyncio
import json
import socket
import threading
from concurrent.futures import Future, ThreadPoolExecutor

import httpx2
import pytest
from conftest import wait_until
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from PySide6.QtCore import QSettings, Qt, QThread
from test_filters import filter_project

from gantt_desktop.controller import Controller
from gantt_desktop.domain import Project
from gantt_desktop.mcp_server import McpServer


@pytest.fixture
def access(qapp):
    controller = Controller(filter_project())
    server = McpServer(controller)
    server._enabled = server.allow_writes = True
    yield controller, server
    server.stop()
    controller.dialogs.dispose()


def call(server, operation, **arguments):
    if operation != "get_project":
        arguments.setdefault("expected_revision", server._revision)
    future = Future()
    server._dispatch(operation, arguments, server._generation, future)
    return future.result(timeout=1)


def run_async(action):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(lambda: asyncio.run(action()))
        wait_until(future.done, timeout=20)
        return future.result()


async def connect(server, action):
    async with (
        httpx2.AsyncClient(
            headers={"Authorization": f"Bearer {server.token}"}, trust_env=False
        ) as http,
        Client(
            streamable_http_client(server.url, http_client=http), raise_exceptions=False
        ) as client,
    ):
        return await action(client)


@pytest.fixture
def online(qapp):
    controller = Controller(filter_project())
    server = McpServer(controller)
    server.start(0, True)
    wait_until(lambda: server.running)
    yield controller, server
    server.stop()
    assert server._thread is None
    controller.dialogs.dispose()


def test_full_snapshot_is_detached_unfiltered_and_has_no_file_path(access, tmp_path):
    c, server = access
    assert c.save_path(tmp_path / "private.gantt.json")
    c.search("Альфа")
    before = c.project.to_dict()
    snapshot = call(server, "get_project")
    assert snapshot["project"] == before and not snapshot["dirty"]
    assert set(snapshot["spans"]) == set(c.project.tasks)
    assert snapshot["spans"]["a"] == ["2025-12-01T09:00", "2025-12-01T18:00"]
    assert str(tmp_path) not in json.dumps(snapshot)
    snapshot["project"]["tasks"][0]["name"] = "Not a live alias"
    assert c.project.to_dict() == before and not c.canUndo


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "LLM task"),
        ("notes", "Project text, not instructions"),
        ("color", "#aabbcc"),
        ("deadline", "2025-12-31"),
        ("status", "closed"),
        ("priority", "highest"),
        ("effort", "12.5"),
        ("cost", "42.25"),
        ("progress", "33.5"),
        ("duration", "12"),
        ("start", "2025-12-04"),
        ("end", "2025-12-05"),
        ("startTime", "10:00"),
        ("endTime", "17:00"),
        ("parent", "empty"),
        ("assignee", "Alice"),
    ],
)
def test_field_edits_use_one_desktop_history_transaction(access, field, value):
    c, server = access
    before = c.project.to_dict()
    result = call(server, "edit_task", task_id="c", field=field, value=value)
    assert result == {"revision": 1, "changed": True, "task_id": "c"}
    after = c.project.to_dict()
    assert before != after and c.dirty and c._history_index == 1
    assert call(server, "get_project")["undo_label"]
    call(server, "undo")
    assert c.project.to_dict() == before and not c.dirty
    call(server, "redo")
    assert c.project.to_dict() == after


@pytest.mark.parametrize(
    "kind,minutes", [("task", 480), ("group", 0), ("milestone", 0)]
)
def test_create_is_explicit_atomic_normalized_and_does_not_open_inspector(
    access, kind, minutes
):
    c, server = access
    inspected = []
    c.inspectRequested.connect(lambda: inspected.append(True))
    before = c.project.to_dict()
    result = call(
        server,
        "create_task",
        name="New",
        start="2025-12-06T09:00",
        parent="g",
        kind=kind,
        duration_minutes=minutes,
    )
    task = c.project.tasks[result["task_id"]]
    assert (
        task.parent == "g"
        and task.kind == kind
        and task.start.isoformat() == "2025-12-08T09:00:00"
    )
    assert c._history_index == 1 and not inspected
    call(server, "undo")
    assert c.project.to_dict() == before


@pytest.mark.parametrize(
    "start,parent,kind,minutes",
    [
        ("2025-12-01T09:00Z", "", "task", 480),
        ("2025-12-01T09:00:01", "", "task", 480),
        ("invalid", "", "task", 480),
        ("2025-12-01T09:00", "missing", "task", 480),
        ("2025-12-01T09:00", "a", "task", 480),
        ("2025-12-01T09:00", "", "task", 0),
        ("2025-12-01T09:00", "", "milestone", 480),
        ("9999-12-31T09:00", "", "task", 4800),
    ],
)
def test_invalid_creation_rolls_back(access, start, parent, kind, minutes):
    c, server = access
    before = c.project.to_dict()
    with pytest.raises((ValueError, OverflowError)):
        call(
            server,
            "create_task",
            name="New",
            start=start,
            parent=parent,
            kind=kind,
            duration_minutes=minutes,
        )
    assert c.project.to_dict() == before and not c.dirty and server._revision == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", ""),
        ("parent", "missing"),
        ("progress", "101"),
        ("cost", "nan"),
        ("color", "red"),
        ("duration", "0"),
        ("startTime", "09:00+03:00"),
        ("deadline", "wrong"),
    ],
)
def test_invalid_edit_rolls_back_without_revision_or_dirty_change(access, field, value):
    c, server = access
    before = c.project.to_dict()
    with pytest.raises(ValueError):
        call(server, "edit_task", task_id="c", field=field, value=value)
    assert c.project.to_dict() == before and not c.canUndo and server._revision == 0


def test_noop_conflict_and_readonly_are_enforced_on_qt_thread(access):
    c, server = access
    assert not call(server, "edit_task", task_id="c", field="name", value="Гамма")[
        "changed"
    ]
    assert not c.canUndo and server._revision == 0
    c.editField("c", "name", "Human edit")
    with pytest.raises(ValueError, match="Stale revision"):
        call(
            server,
            "edit_task",
            expected_revision=0,
            task_id="c",
            field="name",
            value="Stale model",
        )
    server.allow_writes = False
    with pytest.raises(ValueError, match="Read-only"):
        call(server, "undo")
    assert c.project.tasks["c"].name == "Human edit"


def test_hidden_branch_deletion_requires_explicit_subtree_and_undo_restores_links(
    access,
):
    c, server = access
    c.search("Альфа")
    before = c.project.to_dict()
    with pytest.raises(ValueError, match="include_descendants"):
        call(server, "delete_task", task_id="g", include_descendants=False)
    call(server, "delete_task", task_id="g", include_descendants=True)
    assert set(c.project.tasks) == {"c", "empty"} and not c.project.dependencies
    call(server, "undo")
    assert c.project.to_dict() == before and c.filterQuery == "альфа"


def test_assignments_and_dependency_lifecycle_use_domain_rules(access):
    c, server = access
    before = c.project.to_dict()
    call(server, "assign_resources", task_id="c", resource_ids=["r1", "r2"])
    assert c.project.tasks["c"].resource_ids == ["r1", "r2"]
    assert not call(server, "assign_resources", task_id="c", resource_ids=["r2", "r1"])[
        "changed"
    ]
    with pytest.raises(ValueError):
        call(server, "assign_resources", task_id="c", resource_ids=["missing"])
    result = call(
        server,
        "save_dependency",
        source="b",
        target="c",
        kind="FS",
        lag_minutes=7,
        dependency_id="",
    )
    key = result["dependency_id"]
    assert next(link for link in c.project.dependencies if link.id == key).lag == 7
    call(
        server,
        "save_dependency",
        source="b",
        target="c",
        kind="SS",
        lag_minutes=-7,
        dependency_id=key,
    )
    link = next(link for link in c.project.dependencies if link.id == key)
    assert link.kind == "SS" and link.lag == -7
    linked = c.project.to_dict()
    with pytest.raises(ValueError):
        call(
            server,
            "save_dependency",
            source="c",
            target="a",
            kind="FS",
            lag_minutes=0,
            dependency_id="",
        )
    assert c.project.to_dict() == linked
    call(server, "delete_dependency", dependency_id=key)
    assert all(link.id != key for link in c.project.dependencies)
    with pytest.raises(ValueError, match="Unknown dependency"):
        call(server, "delete_dependency", dependency_id=key)
    for _ in range(4):
        call(server, "undo")
    assert c.project.to_dict() == before


def test_cancelled_or_revoked_queued_requests_cannot_edit_later(access, qapp):
    c, server = access
    before = c.project.to_dict()
    args = {
        "expected_revision": 0,
        "task_id": "c",
        "field": "name",
        "value": "Late edit",
    }
    cancelled = Future()
    cancelled.cancel()
    server.requested.emit("edit_task", args.copy(), server._generation, cancelled)
    revoked = Future()
    server.requested.emit("edit_task", args.copy(), server._generation, revoked)
    server.stop()
    qapp.processEvents()
    with pytest.raises(ValueError, match="revoked"):
        revoked.result()
    assert c.project.to_dict() == before


def test_cancelled_async_request_does_not_apply_after_qt_unblocks(access, qapp):
    c, server = access
    before = c.project.to_dict()

    def worker():
        async def expire():
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(
                    server.request(
                        "undo", {"expected_revision": 0}, server._generation
                    ),
                    timeout=0.02,
                )

        asyncio.run(expire())

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(
        timeout=2
    )  # Deliberately do NOT dispatch Qt events before client cancellation.
    assert not thread.is_alive()
    qapp.processEvents()
    assert c.project.to_dict() == before


def test_real_sdk_handshake_tools_read_edit_undo_redo_and_qt_thread(online):
    c, server = online
    threads = []
    c.historyChanged.connect(lambda: threads.append(QThread.currentThread()))
    before = c.project.to_dict()

    async def journey(client):
        assert client.protocol_version and client.server_info.name == "Gantt Desktop"
        tools = (await client.list_tools()).tools
        assert {tool.name for tool in tools} == {
            "get_project",
            "create_task",
            "edit_task",
            "delete_task",
            "set_assignee",
            "assign_resources",
            "save_dependency",
            "delete_dependency",
            "rename_project",
            "save_resource",
            "delete_resource",
            "save_custom_field",
            "delete_custom_field",
            "set_custom_value",
            "create_baseline",
            "select_baseline",
            "delete_baseline",
            "set_project_workdays",
            "set_holidays",
            "move_task",
            "relocate_task",
            "bulk_edit_tasks",
            "undo",
            "redo",
        }
        assert next(
            tool for tool in tools if tool.name == "get_project"
        ).annotations.read_only_hint
        state = (await client.call_tool("get_project")).structured_content
        assert state is not None
        edit = await client.call_tool(
            "edit_task",
            {
                "expected_revision": state["revision"],
                "task_id": "c",
                "field": "name",
                "value": "From MCP",
            },
        )
        assert not edit.is_error and edit.structured_content == {
            "revision": 1,
            "changed": True,
            "task_id": "c",
        }
        undone = await client.call_tool("undo", {"expected_revision": 1})
        assert undone.structured_content == {"revision": 2, "changed": True}
        redone = await client.call_tool("redo", {"expected_revision": 2})
        assert redone.structured_content == {"revision": 3, "changed": True}

    run_async(lambda: connect(server, journey))
    assert c.project.tasks["c"].name == "From MCP" and len(threads) == 3
    assert all(thread is c.thread() for thread in threads)
    c.undo()
    assert c.project.to_dict() == before and not c.dirty


def test_sdk_schema_validation_and_tool_error_do_not_mutate(online):
    c, server = online
    before = c.project.to_dict()

    async def journey(client):
        for args in [
            {"task_id": "c", "field": "name", "value": "Missing revision"},
            {
                "expected_revision": 0,
                "task_id": "c",
                "field": "shell",
                "value": "anything",
            },
            {
                "expected_revision": 0,
                "task_id": "c",
                "field": "progress",
                "value": "999",
            },
            {
                "expected_revision": 0,
                "task_id": "missing",
                "field": "name",
                "value": "Bad ID",
            },
            {
                "expected_revision": True,
                "task_id": "c",
                "field": "name",
                "value": "Wrong type",
            },
        ]:
            assert (await client.call_tool("edit_task", args)).is_error

    run_async(lambda: connect(server, journey))
    assert c.project.to_dict() == before and not c.canUndo


@pytest.mark.parametrize(
    "headers,status",
    [
        ({}, 401),
        ({"Authorization": "Bearer wrong"}, 401),
        ({"Origin": "https://untrusted.example"}, 403),
        ({"Origin": "null"}, 403),
        ({"Host": "untrusted.example"}, 421),
    ],
)
def test_http_auth_origin_and_host_protection(online, headers, status):
    _c, server = online
    supplied = {"Authorization": f"Bearer {server.token}", **headers}
    if not headers:
        supplied.clear()
    response = httpx2.get(server.url, headers=supplied, trust_env=False)
    assert response.status_code == status
    assert server.token not in response.text


def test_http_request_size_bound_and_protocol_errors(online):
    _c, server = online
    headers = {
        "Authorization": f"Bearer {server.token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    assert (
        httpx2.post(
            server.url, headers=headers, content=b"x" * 262145, trust_env=False
        ).status_code
        == 413
    )
    assert (
        httpx2.post(
            server.url, headers=headers, content=b"not json", trust_env=False
        ).status_code
        == 400
    )


def test_readonly_tool_list_and_restart_revokes_old_token(online):
    c, server = online
    old_token = server.token
    url = server.url
    port = int(url.split(":")[-1].split("/")[0])
    with httpx2.Client(trust_env=False) as http:
        assert (
            http.get(
                url + "/missing", headers={"Authorization": f"Bearer {old_token}"}
            ).status_code
            == 404
        )
        server.stop()  # Close a live keep-alive connection from the server side.
        assert not server.token and not server.configuration() and not server.active
        server.start(port)
        wait_until(lambda: server.running)
    assert server.token != old_token and not server.allow_writes
    assert (
        httpx2.get(
            url, headers={"Authorization": f"Bearer {old_token}"}, trust_env=False
        ).status_code
        == 401
    )

    async def journey(client):
        assert [tool.name for tool in (await client.list_tools()).tools] == [
            "get_project"
        ]
        assert (await client.call_tool("undo", {"expected_revision": 0})).is_error
        assert not (await client.call_tool("get_project")).is_error

    run_async(lambda: connect(server, journey))
    assert not c.dirty


def test_switch_project_stops_server_and_frees_port(online):
    c, server = online
    port = int(server.url.split(":")[-1].split("/")[0])
    c.load_project(Project(name="Other project"))
    assert not server.active and not server.token and server._thread is None
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", port))


def test_occupied_port_never_binds_another_interface_or_enables_access(qapp):
    c = Controller(filter_project())
    server = McpServer(c)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        with pytest.raises(OSError):
            server.start(sock.getsockname()[1])
    assert not server.active and not server.token and server._thread is None
    server.stop()


def test_simultaneous_clients_cannot_overwrite_each_other(online):
    c, server = online

    async def journey():
        async def edit(name):
            return await connect(
                server,
                lambda client: client.call_tool(
                    "edit_task",
                    {
                        "expected_revision": 0,
                        "task_id": "c",
                        "field": "name",
                        "value": name,
                    },
                ),
            )

        results = await asyncio.gather(edit("First client"), edit("Second client"))
        assert sum(not result.is_error for result in results) == 1
        assert any(
            "Stale revision" in getattr(content, "text", "")
            for result in results
            for content in result.content
        )

    run_async(journey)
    assert c._history_index == 1 and c.project.tasks["c"].name in {
        "First client",
        "Second client",
    }


def test_queued_revision_and_generation_are_checked_at_delivery(access, qapp):
    c, server = access
    future = Future()
    args = {
        "expected_revision": 0,
        "task_id": "c",
        "field": "name",
        "value": "Old request",
    }
    server.requested.emit("edit_task", args.copy(), server._generation, future)
    c.editField("c", "name", "Human wins")
    qapp.processEvents()
    with pytest.raises(ValueError, match="Stale revision"):
        future.result()
    old = Future()
    server.requested.emit("undo", {"expected_revision": 1}, server._generation, old)
    server.stop()
    server._enabled = True
    qapp.processEvents()
    with pytest.raises(ValueError, match="revoked"):
        old.result()
    assert c.project.tasks["c"].name == "Human wins" and c._history_index == 1


def test_duplicate_auth_and_chunked_body_do_not_bypass_guards(online):
    _c, server = online
    authorization = f"Bearer {server.token}"
    response = httpx2.get(
        server.url,
        headers=[("Authorization", authorization), ("Authorization", authorization)],
        trust_env=False,
    )
    assert response.status_code == 401
    response = httpx2.post(
        server.url,
        headers={"Authorization": authorization},
        content=iter([b"x" * 131073, b"x" * 131073]),
        trust_env=False,
    )
    assert response.status_code == 413


def test_stop_cancels_inflight_http_write_without_late_mutation(online, qapp):
    c, server = online
    before = c.project.to_dict()
    queued = threading.Event()
    server.requested.connect(
        lambda *_args: queued.set(), Qt.ConnectionType.DirectConnection
    )

    async def journey(client):
        return await client.call_tool(
            "edit_task",
            {
                "expected_revision": 0,
                "task_id": "c",
                "field": "name",
                "value": "Too late",
            },
        )

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(lambda: asyncio.run(connect(server, journey)))
        assert queued.wait(timeout=10)  # No Qt events: the write has not run yet.
        server.stop()
        qapp.processEvents()
        wait_until(future.done)
        try:
            result = future.result()
        except (ExceptionGroup, httpx2.HTTPError):
            result = None  # A closing HTTP transport may end without an MCP response.
        assert result is None or result.is_error
    assert (
        not server.active and server._thread is None and c.project.to_dict() == before
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("start", "9999-12-31"),
        ("startTime", "09:00:30"),
        ("startTime", "08:00:30"),
        ("endTime", "17:00:30"),
        ("endTime", "18:00:00.5"),
    ],
)
def test_rejected_schedule_edit_keeps_http_snapshot_and_allows_next_edit(
    online, field, value
):
    c, server = online
    assert c.editField("c", "duration", "16")

    async def journey(client):
        before = (await client.call_tool("get_project")).structured_content
        assert before is not None
        revision = before["revision"]
        rejected = await client.call_tool(
            "edit_task",
            {
                "expected_revision": revision,
                "task_id": "c",
                "field": field,
                "value": value,
            },
        )
        assert rejected.is_error
        after = await client.call_tool("get_project")
        assert not after.is_error and after.structured_content == before
        edited = await client.call_tool(
            "edit_task",
            {
                "expected_revision": revision,
                "task_id": "c",
                "field": "name",
                "value": "After rejection",
            },
        )
        assert not edited.is_error
        assert edited.structured_content == {
            "revision": revision + 1,
            "changed": True,
            "task_id": "c",
        }
        undone = await client.call_tool("undo", {"expected_revision": revision + 1})
        assert not undone.is_error and undone.structured_content == {
            "revision": revision + 2,
            "changed": True,
        }
        restored = (await client.call_tool("get_project")).structured_content
        assert (
            restored is not None
            and restored["project"] == before["project"]
            and restored["spans"] == before["spans"]
        )

    run_async(lambda: connect(server, journey))
    assert c._history_index == 1 and c.canRedo


@pytest.mark.parametrize("invalid", ["overflow", "precision", "unicode", "view"])
def test_failed_native_load_keeps_current_http_access_and_success_revokes_it(
    online, tmp_path, monkeypatch, invalid
):
    c, server = online
    assert c.editField("c", "duration", "16")
    original = tmp_path / "original.gantt.json"
    assert c.save_path(original)
    original_bytes = original.read_bytes()
    assert c.editField("c", "name", "Human edit")
    c.search("Альфа")
    old_rows = c._rows.records.copy()
    old_path = c._path
    generation = server._generation

    async def snapshot(client):
        result = await client.call_tool("get_project")
        assert not result.is_error
        return result.structured_content

    before = run_async(lambda: connect(server, snapshot))
    payload = c.project.to_dict()
    task = next(item for item in payload["tasks"] if item["id"] == "c")
    if invalid == "overflow":
        task["start"] = "9999-12-31T09:00"
    elif invalid == "precision":
        task["start"] = "2025-12-01T09:00:00.5"
    elif invalid == "unicode":
        task["notes"] = "\ud800"
    else:
        payload["name"] = "Rejected"
        record = c.record

        def fail_candidate(task_id):
            if c.project.name == "Rejected":
                raise OverflowError("simulated view failure")
            return record(task_id)

        monkeypatch.setattr(c, "record", fail_candidate)
    rejected = tmp_path / "rejected.gantt.json"
    rejected.write_text(json.dumps(payload), encoding="utf-8")
    assert not c.load_path(rejected)
    assert server.running and server._generation == generation
    assert run_async(lambda: connect(server, snapshot)) == before
    assert (
        c._path == old_path and c._rows.records == old_rows and c.filterQuery == "альфа"
    )
    assert original.read_bytes() == original_bytes

    accepted = tmp_path / "accepted.gantt.json"
    accepted.write_text(json.dumps(Project("Accepted").to_dict()), encoding="utf-8")
    assert c.load_path(accepted)
    assert not server.active and server._thread is None and not server.token


def test_set_assignee_mcp_tool_and_edit_task_assignee(access, online):
    c, server = access
    # 1. Test set_assignee tool
    result = call(server, "set_assignee", task_id="c", assignee="Bob")
    assert result["changed"] and result["task_id"] == "c"
    assert c.project.tasks["c"].assignee == "Bob"
    assert any(r.name == "Bob" for r in c.project.resources.values())

    # Redundant set is no-op
    no_change = call(server, "set_assignee", task_id="c", assignee="Bob")
    assert not no_change["changed"]

    # Clear assignee
    cleared = call(server, "set_assignee", task_id="c", assignee="")
    assert cleared["changed"]
    assert c.project.tasks["c"].assignee == ""
    assert c.project.tasks["c"].resource_ids == []

    # Assigning to a group is rejected
    with pytest.raises(ValueError, match="групп"):
        call(server, "set_assignee", task_id="g", assignee="Bob")

    # Unknown task is rejected
    with pytest.raises(ValueError, match="Unknown task ID"):
        call(server, "set_assignee", task_id="nonexistent", assignee="Bob")

    # 2. Test via real HTTP client in online fixture
    c_online, server_online = online

    async def online_test(client):
        state = (await client.call_tool("get_project")).structured_content
        # Test set_assignee over HTTP
        res = await client.call_tool(
            "set_assignee",
            {
                "expected_revision": state["revision"],
                "task_id": "c",
                "assignee": "Charlie",
            },
        )
        assert not res.is_error
        assert c_online.project.tasks["c"].assignee == "Charlie"

        # Test edit_task field="assignee" over HTTP
        state2 = (await client.call_tool("get_project")).structured_content
        res2 = await client.call_tool(
            "edit_task",
            {
                "expected_revision": state2["revision"],
                "task_id": "c",
                "field": "assignee",
                "value": "Dave",
            },
        )
        assert not res2.is_error
        assert c_online.project.tasks["c"].assignee == "Dave"

    run_async(lambda: connect(server_online, online_test))


def test_mcp_critical_path_in_get_project(online):
    _c, server = online

    async def journey(client):
        state = (await client.call_tool("get_project")).structured_content
        assert "critical_path" in state
        cp = state["critical_path"]
        assert "critical_tasks" in cp and "critical_links" in cp and "total_float" in cp
        assert cp["finish"] is not None

    run_async(lambda: connect(server, journey))


def test_mcp_rename_project(access):
    c, server = access
    before = c.project.name
    res = call(server, "rename_project", name="Renamed Project")
    assert res["changed"] and c.project.name == "Renamed Project"
    undone = call(server, "undo")
    assert undone["changed"] and c.project.name == before


def test_mcp_resources_management(access):
    c, server = access
    # 1. Create resource
    res = call(server, "save_resource", name="Senior Dev", capacity=7.0, workdays=[0, 1, 2, 3])
    r_id = res["resource_id"]
    assert res["changed"] and r_id in c.project.resources
    r = c.project.resources[r_id]
    assert r.name == "Senior Dev" and r.capacity == 7.0 and r.workdays == {0, 1, 2, 3}

    # 2. Update resource
    res_up = call(server, "save_resource", resource_id=r_id, name="Lead Dev", capacity=6.0, workdays=[1, 2, 3, 4])
    assert res_up["changed"]
    assert c.project.resources[r_id].name == "Lead Dev"
    assert c.project.resources[r_id].capacity == 6.0
    assert c.project.resources[r_id].workdays == {1, 2, 3, 4}

    # 3. Delete resource
    res_del = call(server, "delete_resource", resource_id=r_id)
    assert res_del["changed"] and r_id not in c.project.resources

    # 4. Unknown resource
    with pytest.raises(ValueError, match="Unknown resource ID"):
        call(server, "delete_resource", resource_id="nonexistent")


def test_mcp_custom_fields_management(access):
    c, server = access
    # 1. Create text custom field
    field_res = call(server, "save_custom_field", name="Ticket ID", kind="text")
    fid = field_res["field_id"]
    assert field_res["changed"] and fid in c.project.custom_fields
    assert c.project.custom_fields[fid].name == "Ticket ID"

    # 2. Set custom value on task
    val_res = call(server, "set_custom_value", task_id="c", field_id=fid, value="PROJ-1234")
    assert val_res["changed"] and c.project.tasks["c"].custom_values[fid] == "PROJ-1234"

    # 3. Clear custom value
    clear_res = call(server, "set_custom_value", task_id="c", field_id=fid, value=None)
    assert clear_res["changed"] and fid not in c.project.tasks["c"].custom_values

    # 4. Delete custom field
    del_res = call(server, "delete_custom_field", field_id=fid)
    assert del_res["changed"] and fid not in c.project.custom_fields

    # 5. Invalid IDs
    with pytest.raises(ValueError, match="Unknown custom field ID"):
        call(server, "delete_custom_field", field_id="nonexistent")
    with pytest.raises(ValueError, match="Unknown custom field ID"):
        call(server, "set_custom_value", task_id="c", field_id="nonexistent", value="test")


def test_mcp_baselines_management(access):
    c, server = access
    # 1. Create baseline (automatically activates it)
    base_res = call(server, "create_baseline", name="Initial Baseline")
    bid = base_res["baseline_id"]
    assert base_res["changed"] and bid in c.project.baselines
    assert c.project.baselines[bid].name == "Initial Baseline"
    assert c.project.active_baseline == bid

    # 2. Deselect baseline
    desel_res = call(server, "select_baseline", baseline_id="")
    assert desel_res["changed"] and c.project.active_baseline == ""

    # 3. Re-select baseline
    sel_res = call(server, "select_baseline", baseline_id=bid)
    assert sel_res["changed"] and c.project.active_baseline == bid

    # 4. Delete baseline
    del_res = call(server, "delete_baseline", baseline_id=bid)
    assert del_res["changed"] and bid not in c.project.baselines

    # 5. Unknown baseline
    with pytest.raises(ValueError, match="Unknown baseline ID"):
        call(server, "select_baseline", baseline_id="nonexistent")
    with pytest.raises(ValueError, match="Unknown baseline ID"):
        call(server, "delete_baseline", baseline_id="nonexistent")


def test_mcp_calendar_workdays_and_holidays(access):
    c, server = access
    # 1. Set project workdays
    wd_res = call(server, "set_project_workdays", workdays=[0, 1, 2, 3, 4, 5])
    assert wd_res["changed"] and c.project.calendar.workdays == {0, 1, 2, 3, 4, 5}

    # 2. Set holidays
    h_res = call(server, "set_holidays", holidays=["2026-01-01", "2026-12-31"])
    assert h_res["changed"]
    from datetime import date
    assert date(2026, 1, 1) in c.project.calendar.holidays
    assert date(2026, 12, 31) in c.project.calendar.holidays

    # 3. Invalid holiday format
    with pytest.raises(ValueError, match="Invalid holiday date format"):
        call(server, "set_holidays", holidays=["not-a-date"])


def test_mcp_task_movement_and_relocation(access):
    c, server = access
    # 1. Move task
    start_before = c.project.tasks["c"].start
    move_res = call(server, "move_task", task_id="c", days=3)
    assert move_res["changed"] and c.project.tasks["c"].start > start_before

    # 2. Relocate task
    reloc_res = call(server, "relocate_task", task_id="c", target_id="g", placement="inside")
    assert reloc_res["changed"] and c.project.tasks["c"].parent == "g"

    # 3. Unknown task / target
    with pytest.raises(ValueError, match="Unknown task ID"):
        call(server, "move_task", task_id="nonexistent", days=1)
    with pytest.raises(ValueError, match="Unknown target task ID"):
        call(server, "relocate_task", task_id="c", target_id="nonexistent", placement="before")


def test_mcp_bulk_edit_tasks(access):
    c, server = access
    # 1. Bulk edit status, priority, color
    res = call(server, "bulk_edit_tasks", task_ids=["a", "c"],
               status="in_progress", priority="high", color="#123456")
    assert res["changed"]
    assert c.project.tasks["a"].status == "in_progress"
    assert c.project.tasks["c"].status == "in_progress"
    assert c.project.tasks["a"].priority == "high"
    assert c.project.tasks["c"].priority == "high"
    assert c.project.tasks["a"].color == "#123456"
    assert c.project.tasks["c"].color == "#123456"

    # 2. Single Undo undoes both
    undone = call(server, "undo")
    assert undone["changed"]
    assert c.project.tasks["a"].color != "#123456"
    assert c.project.tasks["c"].color != "#123456"

    # 3. Validation: empty task_ids or unknown task ID
    with pytest.raises(ValueError, match="No task IDs provided"):
        call(server, "bulk_edit_tasks", task_ids=[])
    with pytest.raises(ValueError, match="Unknown task ID"):
        call(server, "bulk_edit_tasks", task_ids=["c", "nonexistent"])


def test_persistent_token_saved_to_qsettings_and_reused_on_restart(qapp, tmp_path):
    ini_path = str(tmp_path / "mcp_settings.ini")
    settings = QSettings(ini_path, QSettings.Format.IniFormat)
    c = Controller(filter_project())
    server = McpServer(c, settings=settings)
    assert not server.persistent_token_enabled
    server.set_persistent_token_enabled(True)
    assert server.persistent_token_enabled
    token1 = server.get_persistent_token()
    assert token1 and len(token1) >= 32
    assert settings.value("mcp/token") == token1
    assert settings.value("mcp/persistent_token", type=bool) is True

    # Start server - should use persistent token
    server.start(0)
    wait_until(lambda: server.running)
    assert server.token == token1
    port = int(server.url.split(":")[-1].split("/")[0])

    # Restart server - should reuse same persistent token
    server.stop()
    assert not server.running
    server.start(port)
    wait_until(lambda: server.running)
    assert server.token == token1
    server.stop()
    c.dialogs.dispose()


def test_persistent_token_across_mcp_server_instances(qapp, tmp_path):
    ini_path = str(tmp_path / "mcp_settings.ini")
    settings1 = QSettings(ini_path, QSettings.Format.IniFormat)
    c1 = Controller(filter_project())
    server1 = McpServer(c1, settings=settings1)
    server1.set_persistent_token_enabled(True)
    token = server1.get_persistent_token()
    c1.dialogs.dispose()

    # Second instance with same settings file
    settings2 = QSettings(ini_path, QSettings.Format.IniFormat)
    c2 = Controller(filter_project())
    server2 = McpServer(c2, settings=settings2)
    assert server2.persistent_token_enabled
    assert server2.persistent_token == token
    assert server2.get_persistent_token() == token
    server2.start(0)
    wait_until(lambda: server2.running)
    assert server2.token == token
    server2.stop()
    c2.dialogs.dispose()


def test_project_switch_with_persistent_token_keeps_server_online(qapp, tmp_path):
    ini_path = str(tmp_path / "mcp_settings.ini")
    settings = QSettings(ini_path, QSettings.Format.IniFormat)
    c = Controller(filter_project())
    server = McpServer(c, settings=settings)
    server.set_persistent_token_enabled(True)
    server.start(0, allow_writes=True)
    wait_until(lambda: server.running)
    port = int(server.url.split(":")[-1].split("/")[0])
    token = server.token

    # Verify HTTP connection before switch
    snapshot1 = run_async(lambda: connect(server, lambda client: client.call_tool("get_project", {})))
    data1 = json.loads(snapshot1.content[0].text)
    assert "project" in data1 and data1["project"]["name"] != "Second Project"

    # Load new project while server is running
    c.load_project(Project(name="Second Project"))
    assert server.running and server.active
    assert server.token == token
    assert int(server.url.split(":")[-1].split("/")[0]) == port
    assert server._revision == 0

    # Verify HTTP connection returns new project
    snapshot2 = run_async(lambda: connect(server, lambda client: client.call_tool("get_project", {})))
    data2 = json.loads(snapshot2.content[0].text)
    assert data2["project"]["name"] == "Second Project"
    assert data2["revision"] == 0

    server.stop()
    c.dialogs.dispose()


def test_regenerate_and_custom_persistent_token(qapp, tmp_path):
    ini_path = str(tmp_path / "mcp_settings.ini")
    settings = QSettings(ini_path, QSettings.Format.IniFormat)
    c = Controller(filter_project())
    server = McpServer(c, settings=settings)
    server.set_persistent_token_enabled(True)
    token1 = server.get_persistent_token()

    # Regenerate
    token2 = server.regenerate_persistent_token()
    assert token2 != token1
    assert settings.value("mcp/token") == token2

    # Custom token
    server.set_persistent_token("my-custom-persistent-token-12345")
    assert server.get_persistent_token() == "my-custom-persistent-token-12345"
    assert settings.value("mcp/token") == "my-custom-persistent-token-12345"

    server.start(0)
    wait_until(lambda: server.running)
    assert server.token == "my-custom-persistent-token-12345"

    # Test HTTP auth with custom token
    async def check_auth(client):
        return await client.call_tool("get_project", {})

    res = run_async(lambda: connect(server, check_auth))
    assert res.content

    server.stop()
    c.dialogs.dispose()

