import hashlib
import gzip
import io
import json
import sqlite3
import tarfile

import pytest

from threegpp_web.auth import AuthStore
from threegpp_web.state_backup import AppProcessLock, MANIFEST, main, pack, restore
from threegpp_web import state_backup


def make_state(root):
    root.mkdir()
    with sqlite3.connect(root / "app.sqlite3") as db:
        db.execute("CREATE TABLE questions (question TEXT)")
        db.execute("INSERT INTO questions VALUES (?)", ("synthetic acceptance question",))
    result = root / "results" / ("a" * 32)
    result.mkdir(parents=True)
    (result / "result.json").write_text(json.dumps({"fixture": True, "report": "test only"}))
    (result / "assets.json").write_text(json.dumps({"source": "raw/synthetic.zip"}))
    return root


def archive_parts(path):
    with tarfile.open(path, "r:gz") as tar:
        return [(member, tar.extractfile(member).read()) for member in tar]


def write_parts(path, parts):
    with tarfile.open(path, "w:gz") as tar:
        for member, payload in parts:
            tar.addfile(member, io.BytesIO(payload) if member.isfile() else None)


def test_roundtrip_restores_history_and_assets_without_sessions(tmp_path):
    source = make_state(tmp_path / "state")
    auth = AuthStore(source)
    token, _ = auth.create()
    (source / "password.txt").write_text("never include this")
    archive = tmp_path / "backup.tar.gz"
    before = (source / "app.sqlite3").read_bytes()
    summary = pack(source, archive)
    assert summary["files"] == 3
    assert summary["sessions_included"] is False
    assert archive.with_name(archive.name + ".sha256").read_text().startswith(hashlib.sha256(archive.read_bytes()).hexdigest())
    restored = tmp_path / "new-state"
    result = restore(archive, restored)
    assert result["sessions_restored"] is False
    assert (restored / "app.sqlite3").read_bytes() == before
    assert (source / "app.sqlite3").read_bytes() == before
    assert not (restored / "auth.sqlite3").exists()
    assert not (restored / "password.txt").exists()
    assert AuthStore(restored).get(token) is None
    assert (restored / "results" / ("a" * 32) / "assets.json").read_bytes() == (source / "results" / ("a" * 32) / "assets.json").read_bytes()


def test_running_app_refuses_backup_then_stopped_app_can_pack(tmp_path):
    source = make_state(tmp_path / "state")
    with AppProcessLock(source):
        with pytest.raises(ValueError, match="running"):
            pack(source, tmp_path / "backup.tar.gz")
    assert pack(source, tmp_path / "backup.tar.gz")["ok"]


def test_pack_and_restore_never_overwrite_existing_destination(tmp_path):
    source = make_state(tmp_path / "state")
    archive = tmp_path / "backup.tar.gz"
    pack(source, archive)
    saved = archive.read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        pack(source, archive)
    assert archive.read_bytes() == saved
    destination = tmp_path / "existing"
    destination.mkdir()
    with pytest.raises(ValueError, match="must not exist"):
        restore(archive, destination)
    assert list(destination.iterdir()) == []


def test_restore_does_not_replace_destination_appearing_at_publication(tmp_path, monkeypatch):
    source = make_state(tmp_path / "state")
    archive = tmp_path / "backup.tar.gz"
    pack(source, archive)
    destination = tmp_path / "restored"
    publish = state_backup._publish_directory
    raced_inode = []

    def race(staging, target):
        target.mkdir()
        raced_inode.append(target.stat().st_ino)
        publish(staging, target)

    monkeypatch.setattr(state_backup, "_publish_directory", race)
    with pytest.raises(ValueError, match="appeared during validation"):
        restore(archive, destination)
    assert destination.stat().st_ino == raced_inode[0]
    assert list(destination.iterdir()) == []


def test_pack_output_cannot_alias_inside_state(tmp_path):
    source = make_state(tmp_path / "state")
    alias = tmp_path / "alias"
    alias.symlink_to(source, target_is_directory=True)
    with pytest.raises(ValueError, match="outside its state directory"):
        pack(source, alias / "backup.tar.gz")
    with pytest.raises(ValueError, match="outside its state directory"):
        pack(source, tmp_path / "nonexistent" / ".." / "state" / "backup.tar.gz")
    assert not (source / "backup.tar.gz").exists()
    assert not (tmp_path / "nonexistent").exists()


@pytest.mark.parametrize("kind", [tarfile.XHDTYPE, tarfile.XGLTYPE,
                                  tarfile.GNUTYPE_LONGNAME, tarfile.GNUTYPE_LONGLINK,
                                  tarfile.GNUTYPE_SPARSE])
def test_extended_headers_are_rejected_before_payload_allocation(tmp_path, monkeypatch, kind):
    def forbidden_extension_read(*args, **kwargs):
        raise AssertionError("extension payload must not be read")

    monkeypatch.setattr(tarfile.TarInfo, "_proc_pax", forbidden_extension_read)
    monkeypatch.setattr(tarfile.TarInfo, "_proc_gnulong", forbidden_extension_read)
    monkeypatch.setattr(tarfile.TarInfo, "_proc_sparse", forbidden_extension_read)
    header = tarfile.TarInfo("extended-header")
    header.type, header.size = kind, 1024**3
    archive = tmp_path / "oversized-header.tar.gz"
    # Deliberately omit its advertised 1 GiB payload. The header guard must
    # reject before tarfile attempts its otherwise internal extension read.
    archive.write_bytes(gzip.compress(header.tobuf(format=tarfile.USTAR_FORMAT) + b"\0" * 1024))
    with pytest.raises(ValueError, match="unsupported archive extension"):
        restore(archive, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()


def test_tampered_member_and_missing_member_are_rejected(tmp_path):
    source = make_state(tmp_path / "state")
    archive = tmp_path / "backup.tar.gz"
    pack(source, archive)
    parts = archive_parts(archive)
    member, payload = parts[-1]
    corrupted = payload[:-1] + bytes([payload[-1] ^ 1])
    bad = tmp_path / "bad.tar.gz"
    write_parts(bad, parts[:-1] + [(member, corrupted)])
    with pytest.raises(ValueError, match="checksum"):
        restore(bad, tmp_path / "tampered")
    assert not (tmp_path / "tampered").exists()
    missing = tmp_path / "missing.tar.gz"
    write_parts(missing, parts[:-1])
    with pytest.raises(ValueError, match="missing"):
        restore(missing, tmp_path / "missing-state")


@pytest.mark.parametrize("name,kind", [("../escape", tarfile.REGTYPE), ("/escape", tarfile.REGTYPE), ("results/" + "a"*32 + "/result.json", tarfile.SYMTYPE)])
def test_unsafe_archive_paths_and_links_are_rejected(tmp_path, name, kind):
    source = make_state(tmp_path / "state")
    archive = tmp_path / "backup.tar.gz"
    pack(source, archive)
    parts = archive_parts(archive)
    malicious = tarfile.TarInfo(name)
    malicious.type = kind
    malicious.size = 0
    malicious.linkname = "/etc/passwd" if kind == tarfile.SYMTYPE else ""
    bad = tmp_path / "unsafe.tar.gz"
    write_parts(bad, parts + [(malicious, b"")])
    with pytest.raises(ValueError):
        restore(bad, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()
    assert not (tmp_path / "escape").exists()


def test_duplicate_archive_member_is_rejected(tmp_path):
    source = make_state(tmp_path / "state")
    archive = tmp_path / "backup.tar.gz"
    pack(source, archive)
    parts = archive_parts(archive)
    bad = tmp_path / "duplicate.tar.gz"
    write_parts(bad, parts + [parts[-1]])
    with pytest.raises(ValueError, match="duplicate"):
        restore(bad, tmp_path / "restored")


def test_archive_checksum_companion_is_checked_before_restore(tmp_path):
    source = make_state(tmp_path / "state")
    archive = tmp_path / "backup.tar.gz"
    pack(source, archive)
    archive.with_name(archive.name + ".sha256").write_text("0" * 64 + "  backup.tar.gz\n")
    with pytest.raises(ValueError, match="archive checksum mismatch"):
        restore(archive, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()


def test_limits_and_pending_journal_are_explicit(tmp_path):
    source = make_state(tmp_path / "state")
    archive = tmp_path / "backup.tar.gz"
    with pytest.raises(ValueError, match="bytes"):
        pack(source, archive, max_bytes=1)
    with pytest.raises(ValueError, match="count"):
        pack(source, archive, max_files=1)
    (source / "app.sqlite3-wal").write_bytes(b"pending")
    with pytest.raises(ValueError, match="journal"):
        pack(source, archive)
    (source / "app.sqlite3-wal").unlink()
    pack(source, archive)
    with pytest.raises(ValueError, match="limit"):
        restore(archive, tmp_path / "restored", max_bytes=1)


def test_missing_db_symlink_and_unexpected_result_files_fail(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="missing"):
        pack(empty, tmp_path / "empty.tar.gz")
    source = make_state(tmp_path / "state")
    extra = source / "results" / ("a" * 32) / "secret.key"
    extra.write_text("not allowed")
    with pytest.raises(ValueError, match="unsafe"):
        pack(source, tmp_path / "backup.tar.gz")
    extra.unlink()
    extra.symlink_to(source / "app.sqlite3")
    with pytest.raises(ValueError, match="symlink"):
        pack(source, tmp_path / "backup.tar.gz")


def test_cli_reports_safe_failures_without_traceback(tmp_path, capsys):
    assert main(["pack", "--state-root", str(tmp_path / "missing"), "--output", str(tmp_path / "x.tar.gz")]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is False
