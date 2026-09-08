from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Iterable
from urllib.parse import unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from threegpp.models import ArtifactType, Meeting, SourceArtifact, TDocMetadata, WorkingGroup


class SourceError(RuntimeError):
    """A public 3GPP resource could not be discovered or retrieved."""


class ThreeGPPSource(ABC):
    @abstractmethod
    def list_meetings(self) -> list[Meeting]: ...

    @abstractmethod
    def get_meeting_metadata(self, meeting: str) -> Meeting: ...

    @abstractmethod
    def get_agenda(self, meeting: str) -> list[SourceArtifact]: ...

    @abstractmethod
    def get_meeting_report(self, meeting: str) -> list[SourceArtifact]: ...

    @abstractmethod
    def get_tdoc_list(self, meeting: str) -> list[SourceArtifact]: ...

    @abstractmethod
    def list_tdocs(self, meeting: str) -> list[TDocMetadata]: ...

    @abstractmethod
    def get_tdoc(self, meeting: str, tdoc_id: str) -> TDocMetadata: ...

    def discover_chair_notes(self, meeting: str):
        """Discover snapshots only; fetching their bytes is a separate action."""
        raise SourceError("Chair Note discovery is not supported by this source")


class DirectorySource(ThreeGPPSource):
    BASE_URL = "https://www.3gpp.org/ftp/tsg_ran/"

    def __init__(
        self,
        working_group: WorkingGroup,
        group_directory: str,
        meeting_prefix: str,
        tdoc_prefix: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = 30.0,
        retries: int = 3,
        backoff: float = 0.5,
    ) -> None:
        self.working_group = working_group
        self.group_directory = group_directory
        self.meeting_prefix = meeting_prefix
        self.tdoc_prefix = tdoc_prefix.upper()
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self._owns_client = client is None
        self._html_cache: dict[str, str] = {}
        self.client = client or httpx.Client(
            follow_redirects=True,
            headers={"User-Agent": "3gpp-study-engine/0.1 (metadata research; sequential access)"},
            timeout=timeout,
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> DirectorySource:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @property
    def group_url(self) -> str:
        return urljoin(self.BASE_URL, f"{self.group_directory}/")

    def meeting_url(self, meeting: str) -> str:
        from threegpp.models import normalize_meeting_identifier

        meeting = normalize_meeting_identifier(meeting)
        return urljoin(self.group_url, f"{self.meeting_prefix}{meeting}/")

    def _get_html(self, url: str) -> str:
        if url in self._html_cache:
            return self._html_cache[url]
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                response = self.client.get(url, timeout=self.timeout)
                response.raise_for_status()
                self._html_cache[url] = response.text
                return response.text
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                if status is not None and status < 500 and status != 429:
                    break
                if attempt + 1 < self.retries:
                    time.sleep(self.backoff * (2**attempt))
        raise SourceError(f"failed to retrieve 3GPP directory {url}: {last_error}") from last_error

    @staticmethod
    def parse_links(html: str, base_url: str) -> list[tuple[str, str]]:
        """Parse unique visible directory entries, ignoring sorting/navigation links."""
        soup = BeautifulSoup(html, "html.parser")
        links: list[tuple[str, str]] = []
        seen: set[str] = set()
        base_path = urlparse(base_url).path.rstrip("/") + "/"
        for anchor in soup.find_all("a", href=True):
            name = anchor.get_text(" ", strip=True)
            href = anchor["href"]
            if not name or href.startswith(("?", "#", "javascript:")) or name in {"..", "."}:
                continue
            absolute = urljoin(base_url, href)
            parsed = urlparse(absolute)
            if parsed.netloc.lower() not in {"www.3gpp.org", "3gpp.org"}:
                continue
            if not parsed.path.startswith(base_path) or absolute in seen:
                continue
            seen.add(absolute)
            links.append((unquote(name.rstrip("/")), absolute))
        return links

    def _links(self, url: str) -> list[tuple[str, str]]:
        return self.parse_links(self._get_html(url), url)

    def list_meetings(self) -> list[Meeting]:
        prefix = self.meeting_prefix.lower()
        results: dict[str, Meeting] = {}
        for name, url in self._links(self.group_url):
            if not name.lower().startswith(prefix):
                continue
            identifier = name[len(self.meeting_prefix) :]
            try:
                meeting = Meeting(
                    working_group=self.working_group,
                    meeting_number=identifier,
                    meeting_name=f"{self.working_group.value}#{identifier}",
                    source_url=url,
                )
            except ValueError:
                continue
            results[meeting.meeting_number] = meeting
        return sorted(results.values(), key=lambda item: _meeting_sort_key(item.meeting_number))

    def get_meeting_metadata(self, meeting: str) -> Meeting:
        url = self.meeting_url(meeting)
        self._get_html(url)
        normalized = PurePosixPath(urlparse(url).path).name[len(self.meeting_prefix) :]
        return Meeting(
            working_group=self.working_group,
            meeting_number=normalized,
            meeting_name=f"{self.working_group.value}#{normalized}",
            source_url=url,
        )

    def _meeting_links(self, meeting: str) -> list[tuple[str, str]]:
        return self._links(self.meeting_url(meeting))

    def _directory_files(self, directory_url: str) -> list[tuple[str, str]]:
        return [
            (name, url)
            for name, url in self._links(directory_url)
            if not urlparse(url).path.rstrip("/").endswith(urlparse(directory_url).path.rstrip("/"))
        ]

    def _artifacts_from_named_directories(
        self, meeting: str, directory_names: Iterable[str], artifact_type: ArtifactType
    ) -> list[SourceArtifact]:
        wanted = {name.casefold() for name in directory_names}
        now = datetime.now(UTC)
        artifacts: list[SourceArtifact] = []
        for name, url in self._meeting_links(meeting):
            if name.casefold() not in wanted:
                continue
            for filename, file_url in self._directory_files(url):
                if not PurePosixPath(urlparse(file_url).path).suffix:
                    continue
                artifacts.append(
                    SourceArtifact(
                        artifact_type=artifact_type,
                        working_group=self.working_group,
                        meeting=meeting,
                        source_url=file_url,
                        discovered_at=now,
                        original_filename=filename,
                    )
                )
        return artifacts

    def get_agenda(self, meeting: str) -> list[SourceArtifact]:
        return self._artifacts_from_named_directories(meeting, ["Agenda"], ArtifactType.AGENDA)

    def discover_chair_notes(self, meeting: str):
        from threegpp.chair_notes.rules import CHAIR_NOTE_DIRECTORY_NAMES, discovered_snapshot
        from threegpp.models import normalize_meeting_identifier

        meeting = normalize_meeting_identifier(meeting)
        now = datetime.now(UTC)
        snapshots = {}
        for name, inbox_url in self._meeting_links(meeting):
            if name.casefold() != "inbox":
                continue
            for directory_name, directory_url in self._links(inbox_url):
                if directory_name.casefold() not in CHAIR_NOTE_DIRECTORY_NAMES:
                    continue
                for _, file_url in self._directory_files(directory_url):
                    path = urlparse(file_url).path
                    # Only direct files in the advertised directory, never nested crawls.
                    if path.endswith("/") or not PurePosixPath(path).suffix:
                        continue
                    if PurePosixPath(path).parent != PurePosixPath(urlparse(directory_url).path):
                        continue
                    snapshot = discovered_snapshot(self.working_group, meeting, file_url,
                                                   directory_url, now)
                    snapshots[snapshot.snapshot_id] = snapshot
        return sorted(snapshots.values(), key=lambda item: str(item.artifact.official_url))

    def get_meeting_report(self, meeting: str) -> list[SourceArtifact]:
        return self._artifacts_from_named_directories(
            meeting, ["Report"], ArtifactType.MEETING_REPORT
        )

    def get_tdoc_list(self, meeting: str) -> list[SourceArtifact]:
        now = datetime.now(UTC)
        artifacts: list[SourceArtifact] = []
        for directory_name, directory_url in self._meeting_links(meeting):
            if directory_name.casefold() not in {"docs", "tdoclists", "tdoclist"}:
                continue
            for filename, url in self._directory_files(directory_url):
                lowered = filename.casefold()
                if "tdoc" in lowered and "list" in lowered:
                    artifacts.append(
                        SourceArtifact(
                            artifact_type=ArtifactType.TDOC_LIST,
                            working_group=self.working_group,
                            meeting=meeting,
                            source_url=url,
                            discovered_at=now,
                            original_filename=filename,
                        )
                    )
        return _unique_artifacts(artifacts)

    def _docs_url(self, meeting: str) -> str:
        for name, url in self._meeting_links(meeting):
            if name.casefold() == "docs":
                return url
        raise SourceError(f"no Docs directory advertised for {self.working_group.value}#{meeting}")

    def list_tdocs(self, meeting: str) -> list[TDocMetadata]:
        docs_url = self._docs_url(meeting)
        pattern = re.compile(rf"^({re.escape(self.tdoc_prefix)}-[0-9]+)(?:\.[^.]+)?$", re.I)
        results: dict[str, TDocMetadata] = {}
        for filename, url in self._directory_files(docs_url):
            match = pattern.fullmatch(filename)
            if not match:
                continue
            tdoc = TDocMetadata(
                tdoc_id=match.group(1),
                working_group=self.working_group,
                meeting=meeting,
                source_url=url,
                directory_present=True,
            )
            results[tdoc.tdoc_id] = tdoc
        return sorted(results.values(), key=lambda item: item.tdoc_id)

    def get_tdoc(self, meeting: str, tdoc_id: str) -> TDocMetadata:
        wanted = tdoc_id.strip().upper()
        for tdoc in self.list_tdocs(meeting):
            if tdoc.tdoc_id == wanted:
                return tdoc
        raise SourceError(f"{wanted} was not found in {self.working_group.value}#{meeting}")


def _meeting_sort_key(identifier: str) -> tuple[int, int, str]:
    match = re.match(r"^([0-9]+)(.*)$", identifier)
    if not match:
        return (0, 0, identifier)
    suffix = match.group(2)
    suffix_order = {"": 0, "bis": 1, "-e": 2}.get(suffix, 3)
    return (int(match.group(1)), suffix_order, suffix)


def _unique_artifacts(items: list[SourceArtifact]) -> list[SourceArtifact]:
    unique: dict[str, SourceArtifact] = {}
    for item in items:
        unique[str(item.source_url)] = item
    return list(unique.values())
