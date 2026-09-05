import asyncio

import pytest
import pytest_asyncio

from geoport.errors import GeoPortError
from geoport.session import DeviceSession, SessionRuntime

from .fakes import FakeBackend


@pytest_asyncio.fixture
async def connected():
    backend = FakeBackend()
    session = DeviceSession(backend)
    state = await session.command("connect", {"device_id": "phone-a"})
    try:
        yield session, backend, {"session_id": state["session_id"]}
    finally:
        await session.shutdown()


async def test_500_updates_reuse_one_connection_and_serialize(connected):
    session, backend, identity = connected
    await asyncio.gather(
        *(session.command("location", {**identity, "point": [i / 100, -120]}) for i in range(500))
    )
    connection = backend.connections[0]
    assert len(backend.connections) == 1
    assert len(connection.points) == 500
    assert connection.max_inflight == 1
    assert session.playback_task is None
    assert session.watch_task and not session.watch_task.done()
    await session.command("disconnect", identity)
    assert connection.closed and connection.clear_count == 1
    assert session.watch_task is None


async def test_success_waits_for_device_acknowledgement(connected):
    session, backend, identity = connected
    connection = backend.connections[0]
    connection.release_set = asyncio.Event()
    task = asyncio.create_task(session.command("location", {**identity, "point": [1, 2]}))
    await connection.set_started.wait()
    assert not task.done()
    assert (await session.snapshot())["location"] is None
    connection.release_set.set()
    assert (await task)["location"] == [1, 2]


async def test_timeout_clears_resources_and_allows_reconnect(connected, monkeypatch):
    monkeypatch.setattr("geoport.session.OPERATION_TIMEOUT", 0.02)
    session, backend, identity = connected
    backend.connections[0].release_set = asyncio.Event()
    with pytest.raises(GeoPortError) as error:
        await session.command("location", {**identity, "point": [1, 2]})
    assert error.value.code == "device_timeout"
    assert backend.connections[0].closed
    assert session.state["session_id"] is None
    assert session.state["status"] == "error"
    new_state = await session.command("connect", {"device_id": "phone-a"})
    assert new_state["status"] == "ready"
    assert new_state["session_id"] != identity["session_id"]


async def test_stale_tab_cannot_change_new_device(connected):
    session, backend, identity = connected
    await session.command("disconnect", identity)
    await session.command("connect", {"device_id": "phone-b"})
    with pytest.raises(GeoPortError, match="session changed"):
        await session.command("location", {**identity, "point": [1, 2]})
    assert backend.connections[1].points == []
    assert session.state["device"]["id"] == "phone-b"


async def test_invalid_input_does_not_disrupt_session(connected):
    session, backend, identity = connected
    for point in ([91, 1], [True, 1], [1, float("nan")], None):
        with pytest.raises(GeoPortError):
            await session.command("location", {**identity, "point": point})
    assert not backend.connections[0].closed
    assert session.state["status"] == "ready"


async def test_watch_detects_disconnect_without_another_update(connected):
    session, backend, _ = connected
    backend.connections[0].disconnected.set()
    async with asyncio.timeout(1):
        while session.state["status"] != "error":
            await asyncio.sleep(0)
    assert session.connection is None
    assert backend.connections[0].closed


async def test_failed_connection_does_not_cache_partial_state():
    class BrokenBackend(FakeBackend):
        def connect(self, device_id):
            raise ConnectionError("Not connected")

    session = DeviceSession(BrokenBackend())
    with pytest.raises(GeoPortError):
        await session.command("connect", {"device_id": "phone-a"})
    assert session.connection is None
    assert session.state["session_id"] is None
    await session.shutdown()


async def test_cancelled_update_closes_connection(connected):
    session, backend, identity = connected
    connection = backend.connections[0]
    connection.release_set = asyncio.Event()
    task = asyncio.create_task(session.command("location", {**identity, "point": [1, 2]}))
    await connection.set_started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert connection.closed
    assert session.state["status"] == "error"


async def test_route_interpolates_pauses_resumes_and_stops(connected, monkeypatch):
    monkeypatch.setattr("geoport.session.PLAYBACK_INTERVAL", 0.01)
    session, backend, identity = connected
    await session.command("play", {**identity, "points": [[0, 0], [0, 0.01]], "speed_kmh": 9.25})
    connection = backend.connections[0]
    async with asyncio.timeout(1):
        while len(connection.points) < 3:
            await asyncio.sleep(0.005)
    assert 0 < connection.points[-1][1] < 0.01
    assert session.state["playback"]["speed_kmh"] == 9.25
    await session.command("pause", identity)
    count, distance = len(connection.points), session.distance
    await asyncio.sleep(0.03)
    assert len(connection.points) == count
    await session.command("resume", identity)
    assert session.distance == distance
    await session.command("clear", identity)
    count = len(connection.points)
    await asyncio.sleep(0.03)
    assert len(connection.points) == count
    assert session.state["location"] is None
    assert session.playback_task is None


async def test_playback_failure_stops_without_false_progress(connected, monkeypatch):
    monkeypatch.setattr("geoport.session.PLAYBACK_INTERVAL", 0.005)
    session, backend, identity = connected
    await session.command("play", {**identity, "points": [[0, 0], [0, 0.01]], "speed_kmh": 6})
    backend.connections[0].fail_set = ConnectionError()
    async with asyncio.timeout(1):
        while session.state["status"] != "error":
            await asyncio.sleep(0.005)
    assert session.state["location"] == [0, 0]
    assert session.state["playback"] is None
    assert backend.connections[0].closed


@pytest.mark.parametrize("fail_cleanup", [False, True])
def test_runtime_shutdown_restores_and_joins_worker(fail_cleanup):
    backend = FakeBackend()
    if fail_cleanup:

        async def fail_close():
            raise TimeoutError("Cleanup stalled")

        backend.close = fail_close
    runtime = SessionRuntime(backend)
    runtime.call("command", "connect", {"device_id": "phone"})
    runtime.close()
    runtime.close()
    assert not runtime.thread.is_alive()
    assert backend.connections[0].closed
    assert backend.connections[0].clear_count == 1
