import asyncio
import plistlib

import httpx
import pytest

from geoport.errors import GeoPortError
from geoport.images import FILES, LATEST_DDI_BUILD_ID, ImageCache


def client_for(handler):
    return lambda **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)


def payload(request):
    if request.url.path.endswith(".plist"):
        return httpx.Response(
            200,
            content=plistlib.dumps(
                {
                    "ProductBuildVersion": LATEST_DDI_BUILD_ID,
                }
            ),
        )
    return httpx.Response(200, content=b"image or trustcache")


async def test_complete_image_is_cached_and_reused(tmp_path):
    calls = []

    def handler(request):
        calls.append(request.url)
        return payload(request)

    cache = ImageCache(tmp_path, client_for(handler))
    first, second = await asyncio.gather(cache.get(), cache.get())
    assert first == second
    assert len(calls) == 3
    assert all(path.exists() for path in first)
    assert sorted(p.name for p in tmp_path.iterdir()) == [LATEST_DDI_BUILD_ID]


async def test_cancelled_download_does_not_publish_partial_cache(tmp_path):
    started = asyncio.Event()

    async def stalled(request):
        started.set()
        await asyncio.Event().wait()

    cache = ImageCache(tmp_path, client_for(stalled))
    task = asyncio.create_task(cache.get())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert list(tmp_path.iterdir()) == []
    cache.client_factory = client_for(payload)
    assert len(await cache.get()) == 3


@pytest.mark.parametrize("manifest", [{"ProductBuildVersion": "wrong"}, ["invalid structure"]])
async def test_wrong_image_build_is_not_published(tmp_path, manifest):
    def wrong(request):
        return httpx.Response(200, content=plistlib.dumps(manifest))

    with pytest.raises(GeoPortError) as error:
        await ImageCache(tmp_path, client_for(wrong)).get()
    assert error.value.code == "image_version_mismatch"
    assert list(tmp_path.iterdir()) == []


async def test_corrupt_cache_is_reported_without_overwriting(tmp_path):
    target = tmp_path / LATEST_DDI_BUILD_ID
    target.mkdir()
    (target / FILES[0]).write_bytes(b"partial")
    with pytest.raises(GeoPortError) as error:
        await ImageCache(tmp_path, client_for(payload)).get()
    assert error.value.code == "image_cache_invalid"
