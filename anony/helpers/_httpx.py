import asyncio
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union
from urllib.parse import unquote

import aiofiles
import httpx

from config import DOWNLOADS_DIR, API_URL, API_KEY
from anony import logger


@dataclass
class DownloadResult:
    success: bool
    file_path: Optional[Path] = None
    error: Optional[str] = None


class HttpxClient:
    DEFAULT_TIMEOUT = 120
    DEFAULT_DOWNLOAD_TIMEOUT = 300
    CHUNK_SIZE = 8192
    MAX_RETRIES = 2
    BACKOFF_FACTOR = 1.0

    def __init__(self):
        self._session = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=self.DEFAULT_TIMEOUT,
                read=self.DEFAULT_TIMEOUT,
                write=self.DEFAULT_TIMEOUT,
                pool=self.DEFAULT_TIMEOUT,
            ),
            follow_redirects=True,
        )

    async def close(self):
        try:
            await self._session.aclose()
        except Exception as e:
            logger.error("Error closing HTTP session: %s", repr(e))

    # 🔐 Auto API key header
    @staticmethod
    def _get_headers(url: str, base_headers: dict[str, str]):
        headers = base_headers.copy()

        if API_URL and API_KEY and url.startswith(API_URL):
            headers["X-API-Key"] = API_KEY

        headers.setdefault("User-Agent", "AnonXMusicBot/1.0")

        return headers

    # 🌐 API JSON request
    async def make_request(self, url: str, **kwargs) -> Optional[dict]:
        headers = self._get_headers(url, kwargs.pop("headers", {}))

        for attempt in range(self.MAX_RETRIES):
            try:
                response = await self._session.get(url, headers=headers, **kwargs)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.warning("API request failed (%s): %s", attempt + 1, e)
                await asyncio.sleep(self.BACKOFF_FACTOR * (2 ** attempt))

        logger.error("All retries failed for %s", url)
        return None

    # 📥 File download
    async def download_file(
        self,
        url: str,
        file_path: Optional[Union[str, Path]] = None,
        overwrite: bool = False,
        **kwargs,
    ) -> DownloadResult:

        headers = self._get_headers(url, kwargs.pop("headers", {}))

        try:
            async with self._session.stream(
                "GET", url, timeout=self.DEFAULT_DOWNLOAD_TIMEOUT, headers=headers
            ) as response:

                response.raise_for_status()

                if file_path is None:
                    cd = response.headers.get("Content-Disposition", "")
                    match = re.search(r'filename="?([^"]+)"?', cd)

                    filename = (
                        unquote(match.group(1))
                        if match
                        else (Path(url).name or uuid.uuid4().hex)
                    )

                    path = Path(DOWNLOADS_DIR) / filename
                else:
                    path = Path(file_path)

                if path.exists() and not overwrite:
                    return DownloadResult(True, file_path=path)

                path.parent.mkdir(parents=True, exist_ok=True)

                async with aiofiles.open(path, "wb") as f:
                    async for chunk in response.aiter_bytes(self.CHUNK_SIZE):
                        await f.write(chunk)

                return DownloadResult(True, file_path=path)

        except Exception as e:
            logger.error("Download failed: %s", e)
            return DownloadResult(False, error=str(e))
