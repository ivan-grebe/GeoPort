import asyncio
from contextlib import AsyncExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import geoport.device as module
from geoport.errors import GeoPortError


class Context:
    def __init__(self, value=None):
        self.value = value or self
        self.closed = False

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *args):
        await self.close()

    async def close(self):
        self.closed = True


def setup_device(monkeypatch, version="27.0", mounted=True):
    lockdown = Context()
    lockdown.udid = "phone"
    lockdown.product_version = version
    lockdown.all_values = {"DeviceName": "Phone"}
    lockdown.get_developer_mode_status = AsyncMock(return_value=True)
    mounter = Context()
    mounter.is_image_mounted = AsyncMock(return_value=mounted)
    mounter.mount = AsyncMock()
    tunnel = Context(SimpleNamespace(udid="phone"))
    dvt = Context(SimpleNamespace(dtx=SimpleNamespace(wait_disconnected=AsyncMock())))
    simulation = Context(SimpleNamespace(set=AsyncMock(), clear=AsyncMock()))
    monkeypatch.setattr(module, "create_using_usbmux", AsyncMock(return_value=lockdown))
    monkeypatch.setattr(module, "PersonalizedImageMounter", lambda provider: mounter)
    monkeypatch.setattr(module, "PreferredRsdTunnel", lambda **kwargs: tunnel)
    monkeypatch.setattr(module, "DvtProvider", lambda provider: dvt)
    monkeypatch.setattr(module, "LocationSimulation", lambda provider: simulation)
    return lockdown, mounter, tunnel, dvt, simulation


async def test_adapter_owns_all_contexts_and_awaits_service_calls(monkeypatch):
    contexts = setup_device(monkeypatch)
    async with module.MobileDeviceBackend().connect("phone") as connection:
        await connection.set(1, 2)
        await connection.clear()
        contexts[-1].value.set.assert_awaited_once_with(1, 2)
        contexts[-1].value.clear.assert_awaited_once()
    assert all(c.closed for c in contexts)
    contexts[1].mount.assert_not_awaited()


async def test_missing_image_download_and_mount(monkeypatch):
    contexts = setup_device(monkeypatch, mounted=False)
    monkeypatch.setattr(
        module.ImageCache, "get", AsyncMock(return_value=("image", "manifest", "trust"))
    )
    async with module.MobileDeviceBackend().connect("phone"):
        contexts[1].mount.assert_awaited_once_with("image", "manifest", "trust")


async def test_developer_mode_error_closes_lockdown(monkeypatch):
    contexts = setup_device(monkeypatch)
    contexts[0].get_developer_mode_status.return_value = False
    with pytest.raises(GeoPortError) as error:
        async with module.MobileDeviceBackend().connect("phone"):
            pytest.fail("Should not connect")
    assert error.value.code == "developer_mode_required"
    assert contexts[0].closed


async def test_failed_tunnel_closes_earlier_resources(monkeypatch):
    contexts = setup_device(monkeypatch)

    class FailedTunnel(Context):
        async def __aenter__(self):
            raise ConnectionError("Tunnel failed")

    monkeypatch.setattr(module, "PreferredRsdTunnel", lambda **kwargs: FailedTunnel())
    with pytest.raises(ConnectionError):
        async with module.MobileDeviceBackend().connect("phone"):
            pytest.fail("Should not connect")
    assert contexts[0].closed and contexts[1].closed


async def test_discovery_failure_does_not_hide_other_devices(monkeypatch):
    devices = [
        SimpleNamespace(serial="locked", connection_type="USB"),
        SimpleNamespace(serial="healthy", connection_type="Network"),
    ]
    monkeypatch.setattr(module, "list_devices", AsyncMock(return_value=devices))
    healthy = Context()
    healthy.all_values = {"DeviceName": "Healthy"}
    healthy.product_version = "27.0"

    async def connect(serial, **kwargs):
        assert kwargs["autopair"] is False
        if serial == "locked":
            raise ConnectionError("Locked")
        return healthy

    monkeypatch.setattr(module, "create_using_usbmux", connect)
    result = await module.MobileDeviceBackend().discover()
    assert len(result) == 2
    assert result[0]["problem"]
    assert result[1]["name"] == "Healthy"
    assert healthy.closed


async def test_library_imports_match_pinned_api():
    # The real library is imported above; these public methods must remain awaitable.
    assert asyncio.iscoroutinefunction(module.create_using_usbmux)
    assert asyncio.iscoroutinefunction(module.LocationSimulation.set)
    assert asyncio.iscoroutinefunction(module.PersonalizedImageMounter.mount)


@pytest.mark.parametrize("fail_cleanup", [False, True])
async def test_cancelled_acquisition_closes_late_resource_and_blocks_retry(fail_cleanup):
    started, release = asyncio.Event(), asyncio.Event()

    class DelayedContext(Context):
        async def __aenter__(self):
            started.set()
            await release.wait()
            return self

        async def close(self):
            await super().close()
            if fail_cleanup:
                raise ConnectionError("Cleanup failed")

    backend = module.MobileDeviceBackend()
    context = DelayedContext()
    async with AsyncExitStack() as stack:
        task = asyncio.create_task(backend._enter(stack, context))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert backend.pending_cleanup
        with pytest.raises(GeoPortError) as error:
            async with backend.connect("phone"):
                pytest.fail("Should not overlap a pending acquisition")
        assert error.value.code == "cleanup_pending"
        release.set()
        await backend.close()
    assert context.closed
    assert not backend.pending_cleanup
    if fail_cleanup:
        with pytest.raises(GeoPortError) as error:
            backend._check_cleanup()
        assert error.value.code == "cleanup_failed"
    else:
        backend._check_cleanup()
