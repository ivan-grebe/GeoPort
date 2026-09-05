"""Cancellable developer-image downloads, published only as a complete cache entry."""

import asyncio
import plistlib
import tempfile
from pathlib import Path

import httpx
from pymobiledevice3.common import get_home_folder
from pymobiledevice3.services.mobile_image_mounter import LATEST_DDI_BUILD_ID

from .errors import GeoPortError

IMAGE_ROOT = "https://raw.githubusercontent.com/doronz88/DeveloperDiskImage/main/PersonalizedImages/Xcode_iOS_DDI_Personalized"
FILES = ("Image.dmg", "BuildManifest.plist", "Image.dmg.trustcache")


class ImageCache:
    def __init__(self, root=None, client_factory=httpx.AsyncClient):
        self.root = root
        self.client_factory = client_factory
        self.lock = asyncio.Lock()

    def _complete(self, folder):
        try:
            if not all((folder / name).stat().st_size > 0 for name in FILES):
                return False
            manifest = plistlib.loads((folder / FILES[1]).read_bytes())
            return (
                isinstance(manifest, dict)
                and manifest.get("ProductBuildVersion") == LATEST_DDI_BUILD_ID
            )
        except (OSError, ValueError, plistlib.InvalidFileException):
            return False

    async def get(self):
        async with self.lock:
            root = self.root or get_home_folder() / "geoport-ddi"
            root.mkdir(parents=True, exist_ok=True)
            target = root / LATEST_DDI_BUILD_ID
            if self._complete(target):
                return tuple(target / name for name in FILES)
            if target.exists():
                raise GeoPortError(
                    "The cached developer image is incomplete. Close GeoPort, "
                    f"delete the image folder at {target}, and reconnect.",
                    "image_cache_invalid",
                    503,
                )
            with tempfile.TemporaryDirectory(dir=root, prefix="download-") as temporary:
                staging = Path(temporary) / "image"
                staging.mkdir()
                async with self.client_factory(
                    timeout=httpx.Timeout(20, connect=5), follow_redirects=True
                ) as client:
                    for name in FILES:
                        async with client.stream("GET", f"{IMAGE_ROOT}/{name}") as response:
                            response.raise_for_status()
                            with (staging / name).open("wb") as output:
                                async for chunk in response.aiter_bytes(64 * 1024):
                                    output.write(chunk)
                if not self._complete(staging):
                    raise GeoPortError(
                        "The published developer image does not match this pymobiledevice3 build. "
                        "Update GeoPort before trying again.",
                        "image_version_mismatch",
                        503,
                    )
                try:
                    staging.rename(target)
                except OSError:
                    # Another GeoPort process may have published the same complete build.
                    if not self._complete(target):
                        raise
            return tuple(target / name for name in FILES)
