import asyncio
from contextlib import asynccontextmanager


class FakeConnection:
    def __init__(self, device_id):
        self.info = {"id": device_id, "name": "Test iPhone", "ios": "27.0"}
        self.points = []
        self.clear_count = 0
        self.closed = False
        self.wifi = False
        self.disconnected = asyncio.Event()
        self.set_started = asyncio.Event()
        self.release_set = None
        self.fail_set = None
        self.inflight = 0
        self.max_inflight = 0

    async def set(self, lat, lon):
        self.inflight += 1
        self.max_inflight = max(self.max_inflight, self.inflight)
        try:
            self.set_started.set()
            if self.release_set:
                await self.release_set.wait()
            if self.fail_set:
                raise self.fail_set
            await asyncio.sleep(0)
            self.points.append([lat, lon])
        finally:
            self.inflight -= 1

    async def clear(self):
        self.clear_count += 1

    async def enable_wifi(self):
        self.wifi = True

    async def wait_disconnected(self):
        await self.disconnected.wait()


class FakeBackend:
    def __init__(self):
        self.connections = []

    async def discover(self):
        return [
            {
                "id": "test-phone",
                "name": "Test iPhone",
                "ios": "27.0",
                "transports": ["USB", "Network"],
                "problem": None,
            }
        ]

    async def close(self):
        pass

    @asynccontextmanager
    async def connect(self, device_id):
        connection = FakeConnection(device_id)
        self.connections.append(connection)
        try:
            yield connection
        finally:
            connection.closed = True
