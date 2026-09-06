from __future__ import annotations

import gzip
import hashlib
import io
import re
from pathlib import Path

from threegpp.models import NormalizedOutput, TDocMetadata, WorkingGroup


class NormalizedConflictError(RuntimeError):
    pass


class NormalizedIntegrityError(RuntimeError):
    pass


class NormalizedStore:
    """Portable deterministic normalized rows; DuckDB remains the query index."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.data_root = root.parent

    def write_current(
        self, working_group: WorkingGroup | str, meeting: str, records: list[TDocMetadata]
    ) -> NormalizedOutput:
        payload, checksum = _encoded_records(records)
        destination = (
            self.root
            / WorkingGroup.parse(working_group).value.lower()
            / meeting
            / "current"
            / f"tdocs-{checksum[:12]}.jsonl.gz"
        )
        return self._write(destination, payload, checksum, len(records))

    def write_snapshot(
        self,
        working_group: WorkingGroup | str,
        meeting: str,
        source_url: str,
        filename: str | None,
        records: list[TDocMetadata],
    ) -> NormalizedOutput:
        payload, checksum = _encoded_records(records)
        source_key = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:12]
        stem = re.sub(r"[^a-zA-Z0-9._-]+", "_", Path(filename or "snapshot").stem)
        destination = (
            self.root
            / WorkingGroup.parse(working_group).value.lower()
            / meeting
            / "snapshots"
            / f"{stem}-{source_key}-{checksum[:12]}.jsonl.gz"
        )
        return self._write(destination, payload, checksum, len(records))

    def read(self, output: NormalizedOutput) -> list[TDocMetadata]:
        path = self.resolve(output.path)
        payload = path.read_bytes()
        checksum = hashlib.sha256(payload).hexdigest()
        if checksum != output.sha256:
            raise NormalizedIntegrityError(
                f"normalized checksum mismatch for {path}: {checksum} != {output.sha256}"
            )
        try:
            lines = gzip.decompress(payload).decode("utf-8").splitlines()
            records = [TDocMetadata.model_validate_json(line) for line in lines if line]
        except Exception as exc:
            raise NormalizedIntegrityError(f"invalid normalized output {path}: {exc}") from exc
        if len(records) != output.rows:
            raise NormalizedIntegrityError(
                f"normalized row-count mismatch for {path}: {len(records)} != {output.rows}"
            )
        return records

    def resolve(self, path: Path) -> Path:
        return path if path.is_absolute() else self.data_root / path

    def _write(
        self, destination: Path, payload: bytes, checksum: str, rows: int
    ) -> NormalizedOutput:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            existing = hashlib.sha256(destination.read_bytes()).hexdigest()
            if existing != checksum:
                raise NormalizedConflictError(
                    f"normalized output conflict at {destination}: {existing} != {checksum}"
                )
        else:
            temporary = destination.with_name(f".{destination.name}.part")
            temporary.write_bytes(payload)
            temporary.replace(destination)
        try:
            portable_path = destination.relative_to(self.data_root)
        except ValueError:
            portable_path = destination
        return NormalizedOutput(path=portable_path, rows=rows, sha256=checksum)


def _encoded_records(records: list[TDocMetadata]) -> tuple[bytes, str]:
    ordered = sorted(
        records,
        key=lambda item: (item.working_group.value, item.meeting, item.tdoc_id),
    )
    raw = b"".join(item.model_dump_json().encode("utf-8") + b"\n" for item in ordered)
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0) as compressed:
        compressed.write(raw)
    payload = buffer.getvalue()
    return payload, hashlib.sha256(payload).hexdigest()
