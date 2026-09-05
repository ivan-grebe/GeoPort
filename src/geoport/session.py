"""One persistent session, one event loop, and serialized device operations."""

import asyncio
import contextlib
import copy
import logging
import threading
import uuid
from concurrent.futures import TimeoutError as FutureTimeout
from contextlib import AsyncExitStack

from .errors import GeoPortError, device_error
from .routes import Route, coordinate, speed

logger = logging.getLogger(__name__)
OPERATION_TIMEOUT = 10
CONNECT_TIMEOUT = 60
PLAYBACK_INTERVAL = 0.5


class DeviceSession:
    def __init__(self, backend):
        self.backend = backend
        self.lock = asyncio.Lock()
        self.stack = AsyncExitStack()
        self.connection = None
        self.playback_task = None
        self.watch_task = None
        self.route = None
        self.distance = 0.0
        self.speed_kmh = 6.0
        self.state = {
            "status": "disconnected",
            "session_id": None,
            "device": None,
            "location": None,
            "error": None,
            "playback": None,
        }

    async def snapshot(self):
        return copy.deepcopy(self.state)

    async def discover(self):
        try:
            return await self.backend.discover()
        except Exception as exc:
            raise device_error(exc) from exc

    async def command(self, command, data):
        # Validate before acquiring/changing a live session. Bad input must not disconnect it.
        point = coordinate(data.get("point")) if command == "location" else None
        route = Route.create(data.get("points")) if command == "play" else None
        velocity = speed(data.get("speed_kmh")) if command == "play" else None
        if command == "connect" and (
            not isinstance(data.get("device_id"), str) or not data["device_id"].strip()
        ):
            raise GeoPortError("Choose a device first.")
        async with self.lock:
            if command != "connect":
                if not self.connection or not self.state["session_id"]:
                    raise GeoPortError("Connect a device first.", "not_connected", 409)
                if data.get("session_id") != self.state["session_id"]:
                    raise GeoPortError(
                        "The device session changed. Refresh its status before trying again.",
                        "stale_session",
                        409,
                    )
            elif self.connection:
                raise GeoPortError("Disconnect the current device first.", "already_connected", 409)
            try:
                async with asyncio.timeout(
                    CONNECT_TIMEOUT if command == "connect" else OPERATION_TIMEOUT
                ):
                    if command == "connect":
                        self.state.update(status="connecting", error=None, location=None)
                        self.connection = await self.stack.enter_async_context(
                            self.backend.connect(data["device_id"])
                        )
                        self.state.update(
                            status="ready", device=self.connection.info, session_id=uuid.uuid4().hex
                        )
                        self.watch_task = asyncio.create_task(self._watch(), name="device-watch")
                    elif command == "disconnect":
                        await self._cancel_playback()
                        await self.connection.clear()
                        await self._close()
                        self.state.update(
                            status="disconnected", device=None, location=None, error=None
                        )
                    elif command == "location":
                        await self._cancel_playback()
                        await self._set(point)
                        self.state.update(status="simulating", playback=None, error=None)
                        self.route = None
                    elif command == "clear":
                        await self._cancel_playback()
                        await self.connection.clear()
                        self.route = None
                        self.state.update(status="ready", location=None, playback=None, error=None)
                    elif command == "wifi":
                        await self.connection.enable_wifi()
                    elif command == "play":
                        await self._cancel_playback()
                        self.route, self.distance, self.speed_kmh = route, 0.0, velocity
                        await self._set(route.points[0])
                        self._start_playback()
                    elif command == "pause":
                        if self.state["status"] != "playing":
                            raise GeoPortError("There is no playing route to pause.", status=409)
                        await self._cancel_playback()
                        self.state["status"] = "paused"
                    elif command == "resume":
                        if self.state["status"] != "paused" or not self.route:
                            raise GeoPortError("There is no paused route to resume.", status=409)
                        self._start_playback()
                    else:
                        raise GeoPortError("Unknown command.")
            except GeoPortError:
                # Setup errors must discard partially acquired resources too.
                if command == "connect":
                    await self._close()
                    self.state["status"] = "disconnected"
                raise
            except asyncio.CancelledError:
                await self._fail(TimeoutError())
                raise
            except Exception as exc:
                await self._fail(exc)
                raise device_error(exc) from exc
            return await self.snapshot()

    async def _set(self, point):
        await self.connection.set(*point)
        self.state["location"] = list(point)

    def _start_playback(self):
        self.state.update(status="playing", error=None)
        self._progress()
        self.playback_task = asyncio.create_task(self._play(), name="route-playback")

    def _progress(self):
        self.state["playback"] = {
            "distance_m": self.distance,
            "total_m": self.route.length,
            "speed_kmh": self.speed_kmh,
        }

    async def _play(self):
        previous = asyncio.get_running_loop().time()
        try:
            while True:
                await asyncio.sleep(PLAYBACK_INTERVAL)
                async with self.lock:
                    now = asyncio.get_running_loop().time()
                    distance = min(
                        self.route.length, self.distance + (now - previous) * self.speed_kmh / 3.6
                    )
                    try:
                        async with asyncio.timeout(OPERATION_TIMEOUT):
                            await self._set(self.route.position(distance))
                    except Exception as exc:
                        await self._fail(exc)
                        return
                    self.distance, previous = distance, now
                    self._progress()
                    if distance >= self.route.length:
                        self.state["status"] = "simulating"
                        return
        except asyncio.CancelledError:
            raise

    async def _watch(self):
        try:
            await self.connection.wait_disconnected()
            async with self.lock:
                await self._fail(ConnectionError("Device disconnected"))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            async with self.lock:
                await self._fail(exc)

    async def _cancel_playback(self):
        task, self.playback_task = self.playback_task, None
        if task and task is not asyncio.current_task():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _close(self):
        await self._cancel_playback()
        task, self.watch_task = self.watch_task, None
        if task and task is not asyncio.current_task():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self.connection = None
        self.route = None
        self.state.update(session_id=None, playback=None)
        stack, self.stack = self.stack, AsyncExitStack()
        async with asyncio.timeout(OPERATION_TIMEOUT):
            await stack.aclose()

    async def _fail(self, exc):
        error = device_error(exc)
        logger.warning("Device operation failed: %s", error.code)
        try:
            await self._close()
        except Exception:
            logger.exception("Device cleanup failed")
        self.state.update(status="error", error={"code": error.code, "message": str(error)})

    async def shutdown(self):
        async with self.lock:
            try:
                if self.connection:
                    async with asyncio.timeout(OPERATION_TIMEOUT):
                        await self.connection.clear()
            except Exception:
                logger.warning("Could not restore GPS during shutdown; reconnect to restore it.")
            finally:
                try:
                    await self._close()
                finally:
                    async with asyncio.timeout(OPERATION_TIMEOUT):
                        await self.backend.close()


class SessionRuntime:
    """Bridge synchronous Flask handlers to a single long-lived asyncio loop."""

    def __init__(self, backend):
        # pymobiledevice3's Windows socket handling requires a selector loop.
        self.loop = asyncio.SelectorEventLoop()
        self.session = DeviceSession(backend)
        self.thread = threading.Thread(target=self._run, name="geoport-device", daemon=True)
        self.thread.start()
        self.closed = False

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
        pending = asyncio.all_tasks(self.loop)
        for task in pending:
            task.cancel()
        self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        self.loop.run_until_complete(self.loop.shutdown_asyncgens())
        self.loop.run_until_complete(self.loop.shutdown_default_executor(timeout=2))
        self.loop.close()

    def call(self, method, *args):
        if self.closed:
            raise GeoPortError("GeoPort is shutting down.", "shutting_down", 503)
        future = asyncio.run_coroutine_threadsafe(getattr(self.session, method)(*args), self.loop)
        try:
            return future.result(timeout=CONNECT_TIMEOUT + 2 * OPERATION_TIMEOUT)
        except FutureTimeout as exc:
            future.cancel()
            raise device_error(TimeoutError()) from exc

    def close(self):
        if self.closed:
            return
        try:
            self.call("shutdown")
        except Exception:
            logger.exception("Device cleanup failed during shutdown; restart before reconnecting.")
        finally:
            self.closed = True
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(timeout=2 * OPERATION_TIMEOUT)
