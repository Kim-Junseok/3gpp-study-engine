"""Offline app-state transfer. Sessions and passwords never enter this archive.

The application must hold AppProcessLock for its whole lifetime. Source corpus
transfer is deliberately separate; assets retain relative corpus paths and are
revalidated by the web backend after restore.
"""
from __future__ import annotations

import argparse
import ctypes
import errno
import fcntl
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import tarfile
import tempfile
from contextlib import closing
from pathlib import Path, PurePosixPath
from urllib.parse import quote


MANIFEST = "APP_STATE_MANIFEST.json"
MAX_FILES = 10000
MAX_BYTES = 2 * 1024**3
MAX_MANIFEST_BYTES = 2 * 1024**2


class _StateTarInfo(tarfile.TarInfo):
    """Accept only regular USTAR members, before tarfile reads extensions.

    This module's packer emits USTAR regular files only. PAX/GNU metadata and
    sparse formats are unnecessary here, and tarfile normally consumes their
    payloads before the restore loop can apply manifest/size checks.
    """

    def _proc_member(self, archive):
        if self.type not in (tarfile.REGTYPE, tarfile.AREGTYPE) or self.size < 0:
            raise ValueError("unsupported archive extension or member type")
        return super()._proc_member(archive)


class AppProcessLock:
    """A process-lifetime exclusive lock shared by the web app and state packer."""

    def __init__(self, state_root: Path | str):
        self.root = Path(state_root)
        self._handle = None

    def acquire(self):
        if self._handle is not None:
            return self
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.root / ".app.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        handle = os.fdopen(fd, "a+b")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            raise ValueError("app is running; stop it before backing up app state") from None
        self._handle = handle
        return self

    def release(self):
        if self._handle is not None:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            self._handle.close()
            self._handle = None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *_):
        self.release()


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _allowed(name: str) -> bool:
    return name == "app.sqlite3" or bool(re.fullmatch(
        r"results/[0-9a-f]{32}/(?:result|assets)\.json", name))


def _safe_name(name: str) -> str:
    path = PurePosixPath(name)
    if (not name or "\\" in name or "\x00" in name or path.is_absolute()
            or any(part in {"", ".", ".."} for part in name.split("/"))
            or str(path) != name or not _allowed(name)):
        raise ValueError("archive contains an unsupported or unsafe app-state path")
    return name


def _check_database(path: Path):
    # The process lock and pending-journal check establish a closed snapshot.
    # immutable avoids creating WAL/SHM sidecars during this read-only check.
    uri = "file:" + quote(str(path.resolve()), safe="/") + "?mode=ro&immutable=1"
    try:
        with closing(sqlite3.connect(uri, uri=True)) as conn:
            result = conn.execute("PRAGMA quick_check").fetchall()
            if result != [("ok",)]:
                raise ValueError("app-state database integrity check failed")
    except sqlite3.Error as exc:
        raise ValueError("app-state database is unreadable") from exc


def pack(state_root: Path | str, output: Path | str, *,
         max_bytes: int = MAX_BYTES, max_files: int = MAX_FILES) -> dict:
    supplied_output = Path(output).expanduser()
    if supplied_output.is_symlink():
        raise ValueError("archive destination already exists as a symbolic link")
    root = Path(state_root).expanduser().resolve()
    output = supplied_output.resolve(strict=False)
    if not root.is_dir():
        raise ValueError("app-state directory does not exist")
    if output.is_relative_to(root):
        raise ValueError("write app-state archive outside its state directory")
    checksum_path = output.with_name(output.name + ".sha256")
    if output.exists() or checksum_path.exists():
        raise ValueError("archive or checksum destination already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    with AppProcessLock(root):
        database = root / "app.sqlite3"
        if not database.is_file() or database.is_symlink():
            raise ValueError("app.sqlite3 is missing or unsafe")
        for suffix in ("-wal", "-journal"):
            sidecar = database.with_name(database.name + suffix)
            if sidecar.exists() and sidecar.stat().st_size:
                raise ValueError("app database has pending journal data; close the app cleanly")
        _check_database(database)
        files = [database]
        results = root / "results"
        if results.is_symlink():
            raise ValueError("symlink app-state directories are not portable")
        if results.exists():
            for path in sorted(results.rglob("*")):
                if path.is_symlink():
                    raise ValueError("symlink app-state files are not portable")
                if path.is_file():
                    _safe_name(path.relative_to(root).as_posix())
                    files.append(path)
        if len(files) > max_files:
            raise ValueError("app-state file count exceeds backup limit")
        entries, total = [], 0
        for path in files:
            name = _safe_name(path.relative_to(root).as_posix())
            size = path.stat().st_size
            total += size
            if total > max_bytes:
                raise ValueError("app-state bytes exceed backup limit")
            entries.append({"path": name, "bytes": size, "sha256": _digest(path)})
        manifest = {"schema": 1, "kind": "threegpp-web-app-state",
                    "sessions_included": False, "source_corpus_included": False,
                    "files": entries, "total_bytes": total}
        payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode("utf-8")
        fd, temporary_name = tempfile.mkstemp(prefix=".app-state-", suffix=".tar.gz", dir=output.parent)
        os.close(fd)
        temporary = Path(temporary_name)
        try:
            with tarfile.open(temporary, "w:gz", format=tarfile.USTAR_FORMAT) as archive:
                info = tarfile.TarInfo(MANIFEST)
                info.size, info.mode = len(payload), 0o600
                archive.addfile(info, io.BytesIO(payload))
                for path, entry in zip(files, entries):
                    info = tarfile.TarInfo(entry["path"])
                    info.size, info.mode = entry["bytes"], 0o600
                    with path.open("rb") as stream:
                        archive.addfile(info, stream)
                    if _digest(path) != entry["sha256"]:
                        raise ValueError("app state changed during backup")
            checksum = _digest(temporary)
            # Hard-link publication is atomic and refuses an existing archive.
            os.link(temporary, output)
            try:
                with checksum_path.open("x", encoding="ascii") as stream:
                    stream.write(f"{checksum}  {output.name}\n")
            except Exception:
                output.unlink()
                raise
        finally:
            temporary.unlink(missing_ok=True)
    return {"ok": True, "archive": str(output), "sha256": checksum,
            "files": len(entries), "total_bytes": total,
            "sessions_included": False, "source_corpus_included": False}


def _validate_manifest(payload: bytes, *, max_bytes: int, max_files: int) -> dict:
    try:
        value = json.loads(payload)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("app-state manifest is unreadable") from exc
    if (not isinstance(value, dict) or value.get("schema") != 1
            or value.get("kind") != "threegpp-web-app-state"
            or value.get("sessions_included") is not False
            or value.get("source_corpus_included") is not False
            or not isinstance(value.get("files"), list)):
        raise ValueError("unsupported app-state manifest")
    entries = value["files"]
    if len(entries) > max_files:
        raise ValueError("app-state file count exceeds restore limit")
    found, total = {}, 0
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "bytes", "sha256"}:
            raise ValueError("invalid app-state manifest entry")
        name = _safe_name(entry["path"]) if isinstance(entry["path"], str) else None
        size, digest = entry["bytes"], entry["sha256"]
        if (name is None or name in found or type(size) is not int or size < 0
                or not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest)):
            raise ValueError("invalid or duplicate app-state manifest entry")
        found[name], total = entry, total + size
        if total > max_bytes:
            raise ValueError("app-state bytes exceed restore limit")
    if "app.sqlite3" not in found or value.get("total_bytes") != total:
        raise ValueError("incomplete app-state manifest")
    return found


class _BoundedReader:
    def __init__(self, stream, limit):
        self.stream, self.remaining = stream, limit

    def read(self, size=-1):
        wanted = self.remaining + 1 if size < 0 else min(size, self.remaining + 1)
        data = self.stream.read(wanted)
        self.remaining -= len(data)
        if self.remaining < 0:
            raise ValueError("uncompressed archive exceeds restore limit")
        return data


def _publish_directory(staging: Path, destination: Path) -> None:
    """Publish on Linux atomically without replacing a raced destination."""
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    if rename is None:
        raise ValueError("atomic no-replace restore requires Linux renameat2")
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(staging), -100, os.fsencode(destination), 1) != 0:
        code = ctypes.get_errno()
        if code == errno.EEXIST:
            raise ValueError("restore destination appeared during validation; nothing was replaced")
        raise OSError(code, os.strerror(code))


def restore(archive: Path | str, destination: Path | str, *,
            max_bytes: int = MAX_BYTES, max_files: int = MAX_FILES) -> dict:
    import gzip

    archive, destination = Path(archive), Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError("restore destination must not exist")
    if not archive.is_file() or archive.is_symlink():
        raise ValueError("app-state archive is missing or unsafe")
    if archive.stat().st_size > max_bytes + MAX_MANIFEST_BYTES + max_files * 2048:
        raise ValueError("compressed archive exceeds restore limit")
    companion = archive.with_name(archive.name + ".sha256")
    if companion.exists():
        if companion.is_symlink() or companion.stat().st_size > 1024:
            raise ValueError("archive checksum companion is unsafe")
        expected = companion.read_text(encoding="ascii").split()
        if (not expected or not re.fullmatch("[0-9a-f]{64}", expected[0])
                or _digest(archive) != expected[0]):
            raise ValueError("app-state archive checksum mismatch")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".app-restore-", dir=destination.parent))
    try:
        with gzip.open(archive, "rb") as compressed:
            bounded = _BoundedReader(compressed, max_bytes + MAX_MANIFEST_BYTES + max_files * 2048 + 10240)
            with tarfile.open(fileobj=bounded, mode="r|", tarinfo=_StateTarInfo) as source:
                first = next(iter(source), None)
                if (first is None or first.name != MANIFEST or not first.isfile()
                        or first.size > MAX_MANIFEST_BYTES):
                    raise ValueError("app-state manifest must be the first archive file")
                manifest_stream = source.extractfile(first)
                assert manifest_stream is not None
                entries = _validate_manifest(manifest_stream.read(MAX_MANIFEST_BYTES + 1),
                                             max_bytes=max_bytes, max_files=max_files)
                seen = set()
                # Iterating the existing iterator would emit first again; next()
                # uses TarFile.offset and advances to the subsequent member.
                while (member := source.next()) is not None:
                    name = _safe_name(member.name)
                    entry = entries.get(name)
                    if (not member.isfile() or name in seen or entry is None
                            or member.size != entry["bytes"]):
                        raise ValueError("archive contains unexpected, duplicate or unsafe app state")
                    seen.add(name)
                    path = temporary / name
                    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    incoming = source.extractfile(member)
                    assert incoming is not None
                    digest, count = hashlib.sha256(), 0
                    with path.open("xb") as output:
                        for chunk in iter(lambda: incoming.read(1024 * 1024), b""):
                            count += len(chunk)
                            if count > entry["bytes"]:
                                raise ValueError("app-state member exceeds declared size")
                            digest.update(chunk)
                            output.write(chunk)
                    path.chmod(0o600)
                    if count != entry["bytes"] or digest.hexdigest() != entry["sha256"]:
                        raise ValueError("app-state file checksum mismatch")
                if seen != set(entries):
                    raise ValueError("archive is missing app-state files")
        _check_database(temporary / "app.sqlite3")
        if destination.exists() or destination.is_symlink():
            raise ValueError("restore destination must not exist")
        _publish_directory(temporary, destination)
        return {"ok": True, "destination": str(destination), "files": len(entries),
                "sessions_restored": False, "source_corpus_included": False,
                "next_step": "configure login again and reconnect the separately restored corpus"}
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise ValueError("app-state archive is invalid or unavailable") from exc
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pack_parser = commands.add_parser("pack")
    pack_parser.add_argument("--state-root", required=True, type=Path)
    pack_parser.add_argument("--output", required=True, type=Path)
    restore_parser = commands.add_parser("restore")
    restore_parser.add_argument("--archive", required=True, type=Path)
    restore_parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = pack(args.state_root, args.output) if args.command == "pack" else restore(args.archive, args.destination)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
