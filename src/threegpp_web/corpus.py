"""Offline transfer of an existing research corpus; never acquires or repairs it.

Transport checksums establish copy integrity, not official-source authority or
human review. Verification opens the existing core database read-only.
"""
from __future__ import annotations

import argparse
import ctypes
import errno
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import stat
import sys
import tarfile
import tempfile
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

MANIFEST_NAME = "TRANSFER_MANIFEST.json"
TRANSFER_VERSION = 1
COMPONENTS = ("raw", "normalized", "manifests", "derived")
DATABASE_NAME = "metadata.duckdb"
FIXTURE_MARKER = "SYNTHETIC-FIXTURE-ONLY.txt"
ROOT_FILES = (DATABASE_NAME, FIXTURE_MARKER)


class CorpusTransferError(ValueError):
    """An offline transfer is unsafe, inconsistent, or exceeds its limits."""


@dataclass(frozen=True)
class TransferLimits:
    # Transfer guardrails, not limits of the research engine. CLI configurable.
    max_files: int = 100_000
    max_total_bytes: int = 20 * 1024**3
    max_file_bytes: int = 4 * 1024**3
    max_manifest_bytes: int = 32 * 1024**2
    max_normalized_bytes: int = 128 * 1024**2

    def __post_init__(self):
        if any(value <= 0 for value in self.__dict__.values()):
            raise CorpusTransferError("transfer limits must be positive")


def _sha_file(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _root(path: Path | str) -> Path:
    value = Path(path).expanduser()
    if value.is_symlink() or not value.is_dir():
        raise CorpusTransferError("data root must be an existing regular directory")
    return value.resolve()


def _relative(name: str) -> str:
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise CorpusTransferError("invalid transfer path")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in name.split("/")):
        raise CorpusTransferError("transfer path is not a canonical relative path")
    # Reject Windows drive/alternate-stream syntax on every platform.
    if any(":" in part for part in path.parts):
        raise CorpusTransferError("transfer path contains a drive or stream separator")
    if name not in ROOT_FILES and path.parts[0] not in COMPONENTS:
        raise CorpusTransferError("transfer path is outside the research components")
    return path.as_posix()


def _inside(root: Path, path: Path | str) -> Path:
    value = Path(path)
    candidate = value if value.is_absolute() else root / value
    if not candidate.resolve().is_relative_to(root):
        raise CorpusTransferError("receipt path is outside the restored data root")
    relative = candidate.relative_to(root) if candidate.is_absolute() else candidate
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise CorpusTransferError("symbolic links are not research transfer files")
    return candidate


def _files(root: Path, limits: TransferLimits) -> list[dict[str, Any]]:
    if root.joinpath(DATABASE_NAME + ".wal").exists():
        raise CorpusTransferError("DuckDB WAL exists; stop all writers and close the database before transfer")
    paths: list[Path] = []
    for filename in ROOT_FILES:
        candidate = root / filename
        if candidate.exists() or candidate.is_symlink():
            paths.append(candidate)
    for component in COMPONENTS:
        base = root / component
        if base.is_symlink():
            raise CorpusTransferError("symbolic links are not research transfer files")
        if not base.exists():
            continue
        if not base.is_dir():
            raise CorpusTransferError(f"research component must be a directory: {component}")
        for parent, directories, filenames in os.walk(base, followlinks=False):
            for name in directories:
                if (Path(parent) / name).is_symlink():
                    raise CorpusTransferError("symbolic links are not research transfer files")
            paths.extend(Path(parent) / name for name in filenames)
    if len(paths) > limits.max_files:
        raise CorpusTransferError("transfer file count exceeds configured limit")
    records, total = [], 0
    for path in sorted(paths):
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise CorpusTransferError("only regular research files can be transferred")
        if info.st_size > limits.max_file_bytes:
            raise CorpusTransferError("transfer file exceeds configured byte limit")
        total += info.st_size
        if total > limits.max_total_bytes:
            raise CorpusTransferError("transfer total exceeds configured byte limit")
        name = _relative(path.relative_to(root).as_posix())
        records.append({"path": name, "bytes": info.st_size, "sha256": _sha_file(path)})
    return records


def inspect_corpus(data_root: Path | str, *, limits: TransferLimits | None = None) -> dict[str, Any]:
    """Inventory approved components and capacity; does not create anything."""
    limits = limits or TransferLimits()
    root = _root(data_root)
    files = _files(root, limits)
    components = {}
    for component in (*ROOT_FILES, *COMPONENTS):
        entries = [item for item in files if item["path"] == component
                   or item["path"].startswith(component + "/")]
        components[component] = {"present": root.joinpath(component).exists(),
                                 "files": len(entries), "bytes": sum(item["bytes"] for item in entries)}
    total = sum(item["bytes"] for item in files)
    return {"transfer_version": TRANSFER_VERSION, "files": files,
            "file_count": len(files), "total_bytes": total, "components": components,
            # Estimate includes archive + staging, not guaranteed compression.
            "recommended_free_bytes": total * 2 + 64 * 1024**2,
            "excluded": "root files other than metadata.duckdb and the explicit synthetic-fixture marker, including credentials and app state",
            "authority": "copy inventory only; not official-source or human-review validation"}


def _bounded_gzip(path: Path, limit: int) -> None:
    with gzip.open(path, "rb") as handle:
        count = 0
        while chunk := handle.read(min(1024 * 1024, limit + 1 - count)):
            count += len(chunk)
            if count > limit:
                raise CorpusTransferError("normalized expansion exceeds configured byte limit")


def verify_corpus(data_root: Path | str, *, limits: TransferLimits | None = None) -> dict[str, Any]:
    """Read-only source/provenance checks, with missing material left as gaps."""
    from threegpp.chair_notes.models import ChairNoteSnapshot
    from threegpp.chair_notes.service import ChairNoteService
    from threegpp.db import MetadataRepository
    from threegpp.documents.models import DocumentReceipt
    from threegpp.documents.service import DocumentService
    from threegpp.ingest.manifest import ManifestStore
    from threegpp.topics import TopicProfileService

    limits = limits or TransferLimits()
    root = _root(data_root)
    inventory = inspect_corpus(root, limits=limits)
    errors: list[str] = []
    gaps: list[str] = []
    checked = {"documents": 0, "profiles": 0, "chair_notes": 0, "meeting_manifests": 0,
               "raw_artifact_checksums": 0}
    if not (root / DATABASE_NAME).is_file():
        return {"status": "needs_data", "prepared_sources_ready": False, "research_acceptance_complete": False, "errors": [],
                "gaps": ["metadata.duckdb is missing; no database was created"],
                "checked": checked, "inventory": inventory}
    try:
        with MetadataRepository(root / DATABASE_NAME, read_only=True) as repository:
            required = {"meetings", "artifacts", "tdoc_metadata", "tdoc_list_snapshots",
                        "tdoc_snapshot_records", "tdoc_documents"}
            # read_only protects the DB file, not external readers embedded in views.
            repository.connection.execute("SET enable_external_access=false")
            repository.connection.execute("SET autoload_known_extensions=false")
            repository.connection.execute("SET autoinstall_known_extensions=false")
            tables = {row[0] for row in repository.connection.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='main' AND table_type='BASE TABLE'"
            ).fetchall()}
            if required - tables:
                raise CorpusTransferError("database schema is unsupported; explicit preparation is required")
            rows = repository.connection.execute(
                "SELECT tdoc_id,working_group,meeting_number,receipt_json FROM tdoc_documents"
            ).fetchall()
            if len(rows) > limits.max_files:
                raise CorpusTransferError("document receipt count exceeds configured limit")
            if not rows:
                gaps.append("no prepared document receipts; no technical report source is available")
            service = DocumentService(repository, root)
            for tdoc, wg, meeting, payload in rows:
                label = f"{wg}#{meeting}/{tdoc}"
                try:
                    receipt = DocumentReceipt.model_validate_json(payload)
                    if (tdoc, wg, meeting) != (receipt.tdoc_id, receipt.working_group.value, receipt.meeting):
                        raise CorpusTransferError("database and receipt identities conflict")
                    # Canonical relocated path is already supported by the core. Never
                    # follow an old laptop's absolute path outside the imported root.
                    canonical = _inside(root, Path("raw/tdocs") / wg.lower() / meeting / tdoc / receipt.raw.filename)
                    raw = canonical
                    if not raw.is_file():
                        raw = _inside(root, receipt.raw.local_path)
                    if not raw.is_file():
                        raise CorpusTransferError("retained raw source missing from restored corpus")
                    if raw.stat().st_size != receipt.raw.byte_size or _sha_file(raw) != receipt.raw.sha256:
                        raise CorpusTransferError("raw source differs from original receipt")
                    if receipt.extraction_status.value not in {"parsed", "partially_parsed"}:
                        gaps.append(f"{label}: retained source is not readable ({receipt.extraction_status.value}); not report evidence")
                        continue
                    if receipt.normalized_path is None:
                        gaps.append(f"{label}: normalized source is missing; not report evidence")
                        continue
                    normalized = _inside(root, receipt.normalized_path)
                    _bounded_gzip(normalized, limits.max_normalized_bytes)
                    if receipt.text_path is not None:
                        text_path = _inside(root, receipt.text_path)
                        if text_path.exists() and receipt.text_checksum and _sha_file(text_path) != receipt.text_checksum:
                            raise CorpusTransferError("flattened-text checksum differs from receipt")
                    service.read_source(tdoc, wg, meeting)
                    checked["documents"] += 1
                except (ValueError, OSError, EOFError, RuntimeError, zlib.error) as exc:
                    errors.append(f"{label}: {exc}")
            profiles = sorted(root.glob("derived/topics/*/topic-profile-*/topic-profile.json"))
            if not profiles:
                gaps.append("no topic profile supplied; explicit local terminology bootstrap/review is required")
            for path in profiles:
                try:
                    TopicProfileService(repository, root).load(path.parent.name)
                    checked["profiles"] += 1
                except (ValueError, OSError) as exc:
                    errors.append(f"{path.relative_to(root)}: {exc}")
            # Artifacts can retain legacy absolute local paths. Match unchanged
            # receipt bytes within the transfer by checksum, never rewrite provenance.
            by_checksum: dict[str, list[str]] = {}
            for item in inventory["files"]:
                if item["path"].startswith("raw/"):
                    by_checksum.setdefault(item["sha256"], []).append(item["path"])
            for source, checksum in repository.connection.execute(
                    "SELECT source_url,checksum FROM artifacts WHERE checksum IS NOT NULL").fetchall():
                if checksum in by_checksum:
                    checked["raw_artifact_checksums"] += 1
                else:
                    gaps.append(f"retained meeting artifact bytes not supplied for recorded source: {source}")
    except Exception as exc:
        # Connection/schema validation errors stay observable; no automatic migration.
        errors.append(f"database validation failed: {type(exc).__name__}: {exc}")
    for path in sorted(root.glob("manifests/chair-notes/*/*/cn-*/receipt.json")):
        try:
            snapshot = ChairNoteSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
            if not snapshot.normalized_path or not snapshot.raw_path:
                gaps.append(f"{path.relative_to(root)}: Chair Note source is not prepared")
                continue
            _inside(root, snapshot.raw_path)
            normalized = _inside(root, snapshot.normalized_path)
            _bounded_gzip(normalized, limits.max_normalized_bytes)
            ChairNoteService(root).load_blocks(snapshot.artifact.working_group, snapshot.artifact.meeting,
                                              snapshot.snapshot_id)
            checked["chair_notes"] += 1
        except (ValueError, OSError, EOFError, RuntimeError, zlib.error) as exc:
            errors.append(f"{path.relative_to(root)}: {exc}")
    for path in sorted(root.glob("manifests/*.json")):
        try:
            manifest = ManifestStore.read(path, hydrate=False)
            outputs = ([manifest.current_output] if manifest.current_output else []) + [
                item.normalized_output for item in manifest.tdoc_list_snapshots if item.normalized_output]
            for output in outputs:
                normalized = _inside(root, output.path)
                _bounded_gzip(normalized, limits.max_normalized_bytes)
            # Existing core verifies referenced normalized checksums and row counts.
            ManifestStore.read(path, hydrate=True)
            checked["meeting_manifests"] += 1
        except (ValueError, OSError, EOFError, RuntimeError, zlib.error) as exc:
            errors.append(f"{path.relative_to(root)}: {exc}")
    if checked["chair_notes"] == 0:
        gaps.append("no verified prepared Chair Note supplied; discussion coverage remains a gap")
    # Outcome coverage depends on the selected profile/bundle, not file presence.
    gaps.append("meeting-outcome coverage must be checked independently for each selected report scope")
    ready = not errors and checked["documents"] > 0 and checked["profiles"] > 0
    return {"status": "blocked" if errors else "prepared" if ready else "needs_data",
            "prepared_sources_ready": ready, "research_acceptance_complete": False, "errors": errors, "gaps": gaps, "checked": checked,
            "inventory": inventory,
            "scope_notice": "Prepared source validation only; not report/content/model acceptance. Optional derived reviews are transported unchanged, not certified as human decisions."}


class _HashedReader:
    def __init__(self, handle: BinaryIO):
        self.handle, self.digest = handle, hashlib.sha256()

    def read(self, size: int = -1) -> bytes:
        data = self.handle.read(size)
        self.digest.update(data)
        return data


def _publish_new(temporary: Path, destination: Path) -> None:
    # Atomic create without overwriting a raced destination. Both files share a filesystem.
    os.link(temporary, destination)
    temporary.unlink()


def pack_corpus(data_root: Path | str, output: Path | str, *, limits: TransferLimits | None = None) -> dict[str, Any]:
    limits = limits or TransferLimits()
    root = _root(data_root)
    output = Path(output).expanduser().resolve(strict=False)
    if output.is_relative_to(root):
        raise CorpusTransferError("archive output must be outside the research data root")
    sidecar = Path(str(output) + ".sha256")
    manifest_output = Path(str(output) + ".manifest.json")
    if any(path.exists() or path.is_symlink() for path in (output, sidecar, manifest_output)):
        raise CorpusTransferError("archive or sidecar already exists; choose a new output")
    verification = verify_corpus(root, limits=limits)
    if verification["errors"] or verification["checked"]["documents"] == 0:
        raise CorpusTransferError("existing corpus is not transferable: " + "; ".join(
            verification["errors"] + verification["gaps"]))
    inventory = verification["inventory"]
    manifest = {"transfer_version": TRANSFER_VERSION,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "file_count": inventory["file_count"], "total_bytes": inventory["total_bytes"],
                "files": inventory["files"],
                "authority": "transport checksums only; original provenance is unchanged"}
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    if len(manifest_bytes) > limits.max_manifest_bytes:
        raise CorpusTransferError("transfer manifest exceeds configured byte limit")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".corpus-pack-", dir=output.parent)
    os.close(descriptor)
    pending = Path(temporary_name)
    published: list[Path] = []
    try:
        with tarfile.open(pending, "w:gz", format=tarfile.PAX_FORMAT) as archive:
            info = tarfile.TarInfo(MANIFEST_NAME)
            info.size, info.mode, info.mtime = len(manifest_bytes), 0o600, 0
            archive.addfile(info, io.BytesIO(manifest_bytes))
            for item in manifest["files"]:
                path = _inside(root, item["path"])
                descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                with os.fdopen(descriptor, "rb") as handle:
                    details = os.fstat(handle.fileno())
                    if not stat.S_ISREG(details.st_mode) or details.st_size != item["bytes"]:
                        raise CorpusTransferError("corpus changed during transfer; stop writers and retry")
                    info = tarfile.TarInfo("data/" + item["path"])
                    info.size, info.mode, info.mtime = item["bytes"], 0o600, 0
                    reader = _HashedReader(handle)
                    archive.addfile(info, reader)
                    if reader.digest.hexdigest() != item["sha256"]:
                        raise CorpusTransferError("corpus changed during transfer; stop writers and retry")
        # A transfer is a closed snapshot. A newly appeared WAL must not be hidden.
        if (root / (DATABASE_NAME + ".wal")).exists():
            raise CorpusTransferError("database writer became active during transfer")
        digest = _sha_file(pending)
        _publish_new(pending, output)
        published.append(output)
        with sidecar.open("x", encoding="utf-8") as handle:
            handle.write(f"{digest}  {output.name}\n")
        published.append(sidecar)
        with manifest_output.open("xb") as handle:
            handle.write(manifest_bytes)
        published.append(manifest_output)
        return {"archive": str(output), "archive_sha256": digest, "checksum_file": str(sidecar),
                "manifest_file": str(manifest_output), "file_count": manifest["file_count"],
                "source_bytes": manifest["total_bytes"], "archive_bytes": output.stat().st_size,
                "verification": verification}
    except Exception:
        for path in published:
            path.unlink(missing_ok=True)
        raise
    finally:
        pending.unlink(missing_ok=True)


def _publish_directory(staging: Path, destination: Path) -> None:
    """Linux atomic directory publish with RENAME_NOREPLACE (never clobber)."""
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    if rename is None:
        raise CorpusTransferError("atomic no-replace restore requires Linux renameat2; destination was not created")
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(staging), -100, os.fsencode(destination), 1) != 0:
        code = ctypes.get_errno()
        if code == errno.EEXIST:
            raise CorpusTransferError("restore destination appeared during validation; nothing was replaced")
        raise OSError(code, os.strerror(code))


def _parse_manifest(payload: bytes, limits: TransferLimits) -> dict[str, Any]:
    if len(payload) > limits.max_manifest_bytes:
        raise CorpusTransferError("transfer manifest exceeds configured byte limit")
    try:
        manifest = json.loads(payload)
    except (ValueError, UnicodeError) as exc:
        raise CorpusTransferError("invalid transfer manifest JSON") from exc
    if not isinstance(manifest, dict) or manifest.get("transfer_version") != TRANSFER_VERSION:
        raise CorpusTransferError("unsupported transfer manifest version")
    entries = manifest.get("files")
    if not isinstance(entries, list) or len(entries) > limits.max_files:
        raise CorpusTransferError("invalid or excessive manifest file count")
    names, total = set(), 0
    for item in entries:
        if not isinstance(item, dict):
            raise CorpusTransferError("invalid manifest file record")
        name = _relative(item.get("path"))
        size, digest = item.get("bytes"), item.get("sha256")
        if name in names:
            raise CorpusTransferError("duplicate manifest path")
        names.add(name)
        if type(size) is not int or size < 0 or size > limits.max_file_bytes:
            raise CorpusTransferError("invalid or excessive manifest file size")
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise CorpusTransferError("invalid manifest checksum")
        total += size
    if total > limits.max_total_bytes or manifest.get("total_bytes") != total:
        raise CorpusTransferError("manifest total byte count is invalid or excessive")
    if manifest.get("file_count") != len(entries):
        raise CorpusTransferError("manifest file count mismatch")
    return manifest


def _bounded_tarinfo(limits: TransferLimits):
    # tarfile normally consumes PAX/GNU extension payloads before returning a
    # member to the caller. Bound those headers before their internal reads.
    class BoundedTarInfo(tarfile.TarInfo):
        consecutive_extensions = 0

        def _proc_member(self, package):
            cls = type(self)
            if self.type in (tarfile.XHDTYPE, tarfile.GNUTYPE_LONGNAME):
                cls.consecutive_extensions += 1
                if cls.consecutive_extensions > 16 or self.size < 0 or self.size > min(65536, limits.max_manifest_bytes):
                    raise CorpusTransferError("archive extended header exceeds configured safety limit")
            elif self.type in (tarfile.REGTYPE, tarfile.AREGTYPE):
                cls.consecutive_extensions = 0
            else:
                raise CorpusTransferError("archive member type or size conflicts with manifest")
            return super()._proc_member(package)

        def _proc_gnusparse_00(self, *args):
            raise CorpusTransferError("sparse archive members are unsupported")

        def _proc_gnusparse_01(self, *args):
            raise CorpusTransferError("sparse archive members are unsupported")

        def _proc_gnusparse_10(self, *args):
            raise CorpusTransferError("sparse archive members are unsupported")

    return BoundedTarInfo


def restore_corpus(archive: Path | str, destination: Path | str, *,
                   limits: TransferLimits | None = None, expected_sha256: str | None = None) -> dict[str, Any]:
    """Validate every archive member before publishing a brand-new directory."""
    limits = limits or TransferLimits()
    archive = Path(archive).expanduser()
    if archive.is_symlink() or not archive.is_file():
        raise CorpusTransferError("archive must be a regular file")
    destination = Path(destination).expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise CorpusTransferError("restore destination already exists; choose a new directory")
    # Detect corruption when the separately supplied archive checksum is present.
    sidecar = Path(str(archive) + ".sha256")
    if expected_sha256 is None and sidecar.is_symlink():
        raise CorpusTransferError("archive checksum sidecar must not be a symbolic link")
    if expected_sha256 is None and sidecar.is_file():
        if sidecar.stat().st_size > 4096:
            raise CorpusTransferError("archive checksum sidecar is too large")
        fields = sidecar.read_text(encoding="utf-8").split()
        if not fields:
            raise CorpusTransferError("archive checksum sidecar is empty")
        expected_sha256 = fields[0]
    if expected_sha256 is not None:
        if not re.fullmatch(r"[a-fA-F0-9]{64}", expected_sha256) or _sha_file(archive) != expected_sha256.lower():
            raise CorpusTransferError("archive checksum mismatch")
    if archive.stat().st_size > limits.max_total_bytes + limits.max_manifest_bytes + 64 * 1024**2:
        raise CorpusTransferError("archive exceeds configured byte limit")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".corpus-restore-", dir=destination.parent))
    try:
        with tarfile.open(archive, "r|gz", tarinfo=_bounded_tarinfo(limits)) as package:
            first = package.next()
            if (first is None or first.name != MANIFEST_NAME or not first.isfile()
                    or first.sparse is not None or first.size < 0 or first.size > limits.max_manifest_bytes):
                raise CorpusTransferError("archive must begin with a bounded regular transfer manifest")
            stream = package.extractfile(first)
            if stream is None:
                raise CorpusTransferError("archive manifest is unreadable")
            manifest = _parse_manifest(stream.read(limits.max_manifest_bytes + 1), limits)
            wanted = {"data/" + item["path"]: item for item in manifest["files"]}
            seen = set()
            while (member := package.next()) is not None:
                if member.name in seen or member.name not in wanted:
                    raise CorpusTransferError("archive contains a duplicate or unlisted member")
                seen.add(member.name)
                item = wanted[member.name]
                if not member.isfile() or member.sparse is not None or member.size != item["bytes"]:
                    raise CorpusTransferError("archive member type or size conflicts with manifest")
                # No extract()/extractall(): all paths are independently validated.
                path = staging / _relative(item["path"])
                path.parent.mkdir(parents=True, exist_ok=True)
                source = package.extractfile(member)
                if source is None:
                    raise CorpusTransferError("archive member is unreadable")
                digest, copied = hashlib.sha256(), 0
                with path.open("xb") as handle:
                    while chunk := source.read(min(1024 * 1024, item["bytes"] + 1 - copied)):
                        copied += len(chunk)
                        if copied > item["bytes"]:
                            raise CorpusTransferError("archive member exceeded declared bytes")
                        digest.update(chunk)
                        handle.write(chunk)
                if copied != item["bytes"] or digest.hexdigest() != item["sha256"]:
                    raise CorpusTransferError("archive member checksum mismatch")
            if seen != set(wanted):
                raise CorpusTransferError("archive is missing manifest files")
        verification = verify_corpus(staging, limits=limits)
        if verification["errors"] or verification["checked"]["documents"] == 0:
            raise CorpusTransferError("restored provenance/source validation failed: " + "; ".join(
                verification["errors"] + verification["gaps"]))
        # A marker contains transfer evidence only, separate from original receipts.
        (staging / MANIFEST_NAME).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _publish_directory(staging, destination)
        return {"destination": str(destination), "transport_verified": True,
                "archive_checksum_verified": expected_sha256 is not None,
                "file_count": manifest["file_count"], "source_bytes": manifest["total_bytes"],
                "verification": verification,
                "notice": "No source acquisition, database migration, normalization, or review creation occurred."}
    except (tarfile.TarError, EOFError, OSError, zlib.error) as exc:
        raise CorpusTransferError(f"archive restore failed: {exc}") from exc
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline existing-corpus handoff; no acquisition or repair")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("inspect", "verify", "pack", "restore"):
        sub = subparsers.add_parser(command)
        if command == "restore":
            sub.add_argument("--archive", type=Path, required=True)
            sub.add_argument("--destination", type=Path, required=True)
            sub.add_argument("--expected-sha256")
        else:
            sub.add_argument("--data-root", type=Path, required=True)
            if command == "pack":
                sub.add_argument("--output", type=Path, required=True)
        sub.add_argument("--max-files", type=int, default=TransferLimits.max_files)
        sub.add_argument("--max-bytes", type=int, default=TransferLimits.max_total_bytes)
        sub.add_argument("--max-file-bytes", type=int, default=TransferLimits.max_file_bytes)
        sub.add_argument("--max-normalized-bytes", type=int, default=TransferLimits.max_normalized_bytes)
    args = parser.parse_args(argv)
    try:
        limits = TransferLimits(max_files=args.max_files, max_total_bytes=args.max_bytes,
                                max_file_bytes=args.max_file_bytes, max_normalized_bytes=args.max_normalized_bytes)
        if args.command == "inspect":
            result = inspect_corpus(args.data_root, limits=limits)
        elif args.command == "verify":
            result = verify_corpus(args.data_root, limits=limits)
        elif args.command == "pack":
            result = pack_corpus(args.data_root, args.output, limits=limits)
        else:
            result = restore_corpus(args.archive, args.destination, limits=limits,
                                    expected_sha256=args.expected_sha256)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if args.command == "verify" and not result["prepared_sources_ready"] else 0
    except (CorpusTransferError, OSError, ValueError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
