from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx


class DownloadConflictError(RuntimeError):
    """The source changed and would overwrite immutable raw evidence."""


@dataclass(frozen=True)
class DownloadResult:
    path: Path
    sha256: str
    downloaded: bool


class HTTPDownloader:
    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        timeout: float = 60.0,
        retries: int = 3,
        backoff: float = 0.5,
    ) -> None:
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self._owns_client = client is None
        self.client = client or httpx.Client(
            follow_redirects=True,
            headers={"User-Agent": "3gpp-study-engine/0.1 (explicit artifact retrieval)"},
            timeout=timeout,
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> HTTPDownloader:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def download(self, url: str, destination: Path) -> DownloadResult:
        data = self._get_bytes(url)
        digest = hashlib.sha256(data).hexdigest()
        destination = destination.resolve()

        if destination.exists():
            existing_digest = _sha256_file(destination)
            if existing_digest != digest:
                raise DownloadConflictError(
                    f"refusing to overwrite changed raw artifact {destination}; "
                    f"existing sha256={existing_digest}, source sha256={digest}"
                )
            return DownloadResult(destination, digest, downloaded=False)

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.part")
        temporary.write_bytes(data)
        temporary.replace(destination)
        return DownloadResult(destination, digest, downloaded=True)

    def _get_bytes(self, url: str) -> bytes:
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                response = self.client.get(url, timeout=self.timeout)
                response.raise_for_status()
                return response.content
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                if status is not None and status < 500 and status != 429:
                    break
                if attempt + 1 < self.retries:
                    time.sleep(self.backoff * (2**attempt))
        raise RuntimeError(f"failed to download {url}: {last_error}") from last_error


def safe_filename(url_or_name: str, fallback: str) -> str:
    parsed = urlparse(url_or_name)
    source_path = parsed.path if parsed.scheme or parsed.netloc else url_or_name
    name = Path(source_path).name or fallback
    if name in {".", ".."} or "/" in name or "\\" in name:
        raise ValueError(f"unsafe artifact filename derived from {url_or_name!r}")
    return name


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
