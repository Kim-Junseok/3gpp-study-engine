"""Offline handoff tests use synthetic fixtures, never actual research sources."""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import socket
import tarfile
from pathlib import Path

import pytest

from threegpp.db import MetadataRepository
from threegpp.topics import TopicBootstrapRequest, TopicProfileService
from threegpp_web.corpus import (
    MANIFEST_NAME, CorpusTransferError, TransferLimits,
    inspect_corpus, main, pack_corpus, restore_corpus, verify_corpus,
)
from test_report_source_read import prepare_source, stored_bytes


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("offline corpus tooling attempted a network connection")
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)


@pytest.fixture
def corpus(tmp_path):
    db, root, receipt = prepare_source(tmp_path)
    with MetadataRepository(db) as repository:
        _, profile = TopicProfileService(repository, root).bootstrap_and_persist(
            TopicBootstrapRequest(working_group="RAN1", from_meeting="125", to_meeting="125",
                                  user_terms=["HARQ"]))
    return root, receipt, profile


def custom_archive(path, entries, *, manifest_entries=None):
    records = manifest_entries or [
        {"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        for name, content in entries]
    manifest = {"transfer_version": 1, "file_count": len(records),
                "total_bytes": sum(item["bytes"] for item in records), "files": records}
    payload = json.dumps(manifest).encode()
    with tarfile.open(path, "w:gz") as archive:
        header = tarfile.TarInfo(MANIFEST_NAME)
        header.size = len(payload)
        archive.addfile(header, io.BytesIO(payload))
        for name, content in entries:
            header = tarfile.TarInfo("data/" + name)
            header.size = len(content)
            archive.addfile(header, io.BytesIO(content))
    return path


def test_roundtrip_to_new_root_preserves_original_receipts(corpus, tmp_path):
    root, receipt, _ = corpus
    before = stored_bytes(root)
    archive = tmp_path / "handoff.tar.gz"
    packed = pack_corpus(root, archive)
    assert stored_bytes(root) == before
    assert packed["verification"]["checked"]["documents"] == 1
    assert Path(str(archive) + ".sha256").is_file()
    # Prove reading does not depend on the old absolute laptop root.
    shutil.rmtree(root)
    destination = tmp_path / "restored"
    restored = restore_corpus(archive, destination)
    assert restored["transport_verified"] is True
    assert restored["archive_checksum_verified"] is True
    assert restored["verification"]["prepared_sources_ready"] is True
    assert {key: value for key, value in stored_bytes(destination).items()
            if key != MANIFEST_NAME} == before
    with MetadataRepository(destination / "metadata.duckdb", read_only=True) as repository:
        relocated = repository.get_document_receipt(receipt.tdoc_id, "RAN1", "125")
        assert relocated.raw.local_path == receipt.raw.local_path
        assert relocated.raw.sha256 == receipt.raw.sha256
        assert relocated.raw.retrieved_at == receipt.raw.retrieved_at


def test_inspection_sizes_excludes_credentials_and_app_state(corpus):
    root, _, _ = corpus
    (root / ".env").write_text("PRIVATE_KEY=not-for-transfer")
    (root / "app.sqlite3").write_bytes(b"not-source")
    before = stored_bytes(root)
    result = inspect_corpus(root)
    names = {item["path"] for item in result["files"]}
    assert ".env" not in names and "app.sqlite3" not in names
    assert result["total_bytes"] == sum(item["bytes"] for item in result["files"])
    assert result["recommended_free_bytes"] > result["total_bytes"] * 2
    assert stored_bytes(root) == before


def test_missing_database_is_not_created(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    result = verify_corpus(root)
    assert result["status"] == "needs_data" and not result["prepared_sources_ready"]
    assert not (root / "metadata.duckdb").exists()
    with pytest.raises(CorpusTransferError, match="not transferable"):
        pack_corpus(root, tmp_path / "empty.tar.gz")
    assert main(["verify", "--data-root", str(root)]) == 2


def test_missing_profile_is_explicit_but_existing_sources_can_transfer(corpus, tmp_path):
    root, _, _ = corpus
    shutil.rmtree(root / "derived" / "topics")
    result = verify_corpus(root)
    assert not result["prepared_sources_ready"]
    assert any("no topic profile" in gap for gap in result["gaps"])
    archive = tmp_path / "no-profile.tar.gz"
    pack_corpus(root, archive)
    result = restore_corpus(archive, tmp_path / "no-profile-restored")
    assert not result["verification"]["prepared_sources_ready"]


def test_wrong_database_schema_is_blocked_without_migration(tmp_path):
    import duckdb
    root = tmp_path / "old"
    root.mkdir()
    with duckdb.connect(str(root / "metadata.duckdb")) as database:
        database.execute("CREATE TABLE unrelated(value INTEGER)")
    before = stored_bytes(root)
    result = verify_corpus(root)
    assert result["status"] == "blocked" and any("schema" in error for error in result["errors"])
    assert stored_bytes(root) == before


def test_original_receipt_checksum_not_replaced_by_transport_hash(corpus, tmp_path):
    root, receipt, _ = corpus
    raw = root / "raw/tdocs/ran1/125" / receipt.tdoc_id / receipt.raw.filename
    raw.write_bytes(b"tampered bytes")
    before = stored_bytes(root)
    result = verify_corpus(root)
    assert result["status"] == "blocked"
    assert any("original receipt" in error for error in result["errors"])
    with pytest.raises(CorpusTransferError):
        pack_corpus(root, tmp_path / "bad-source.tar.gz")
    assert stored_bytes(root) == before


def test_missing_canonical_raw_never_reads_old_external_absolute_path(corpus, tmp_path):
    root, receipt, _ = corpus
    external = tmp_path / "old-laptop"
    shutil.copytree(root, external)
    from test_report_source_read import replace_receipt
    replace_receipt(root / "metadata.duckdb", receipt,
                    raw=receipt.raw.model_copy(update={"local_path": external / "raw.zip"}))
    shutil.copyfile(root / "raw/tdocs/ran1/125" / receipt.tdoc_id / receipt.raw.filename,
                    external / "raw.zip")
    shutil.rmtree(root / "raw")
    result = verify_corpus(root)
    assert result["status"] == "blocked"
    assert any("outside the restored" in error for error in result["errors"])


def test_profile_tampering_is_blocked(corpus):
    root, _, profile = corpus
    path = root / "derived/topics/ran1" / profile.profile_id / "topic-profile.json"
    value = json.loads(path.read_text())
    value["topic_label"] = "changed without a revision"
    path.write_text(json.dumps(value))
    result = verify_corpus(root)
    assert any("checksum" in error for error in result["errors"])


def test_wal_and_symlinks_are_refused(corpus, tmp_path):
    root, _, _ = corpus
    wal = root / "metadata.duckdb.wal"
    wal.write_bytes(b"writer-active")
    with pytest.raises(CorpusTransferError, match="WAL"):
        inspect_corpus(root)
    wal.unlink()
    (root / "raw" / "outside-link").symlink_to(tmp_path)
    with pytest.raises(CorpusTransferError, match="symbolic"):
        inspect_corpus(root)


def test_existing_outputs_and_destination_never_overwritten(corpus, tmp_path):
    root, _, _ = corpus
    archive = tmp_path / "snapshot.tar.gz"
    pack_corpus(root, archive)
    original = archive.read_bytes()
    with pytest.raises(CorpusTransferError, match="already exists"):
        pack_corpus(root, archive)
    assert archive.read_bytes() == original
    target = tmp_path / "already-present"
    target.mkdir()
    (target / "keep").write_text("retain")
    with pytest.raises(CorpusTransferError, match="already exists"):
        restore_corpus(archive, target)
    assert (target / "keep").read_text() == "retain"


def test_archive_checksum_rejects_transport_tampering(corpus, tmp_path):
    root, _, _ = corpus
    archive = tmp_path / "snapshot.tar.gz"
    pack_corpus(root, archive)
    archive.write_bytes(archive.read_bytes() + b"tampered")
    target = tmp_path / "must-not-exist"
    with pytest.raises(CorpusTransferError, match="archive checksum"):
        restore_corpus(archive, target)
    assert not target.exists()


def test_manifest_detects_changed_member_without_sidecar(tmp_path):
    expected = [{"path": "raw/source.txt", "bytes": 3,
                 "sha256": hashlib.sha256(b"old").hexdigest()}]
    archive = custom_archive(tmp_path / "changed.tar.gz", [("raw/source.txt", b"new")],
                             manifest_entries=expected)
    target = tmp_path / "must-not-exist"
    with pytest.raises(CorpusTransferError, match="member checksum"):
        restore_corpus(archive, target)
    assert not target.exists()
    assert not list(tmp_path.glob(".corpus-restore-*"))


@pytest.mark.parametrize("name", ["../escape", "/absolute", "raw/../escape", "raw\\escape", "raw/C:drive"])
def test_traversal_paths_refused_before_any_publish(tmp_path, name):
    archive = custom_archive(tmp_path / "traversal.tar.gz", [(name, b"bad")])
    with pytest.raises(CorpusTransferError, match="path"):
        restore_corpus(archive, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()
    assert not (tmp_path / "escape").exists()


def test_duplicate_and_unlisted_archive_members_refused(tmp_path):
    record = [{"path": "raw/item.txt", "bytes": 1,
               "sha256": hashlib.sha256(b"x").hexdigest()}]
    archive = custom_archive(tmp_path / "duplicate.tar.gz",
                             [("raw/item.txt", b"x"), ("raw/item.txt", b"x")], manifest_entries=record)
    with pytest.raises(CorpusTransferError, match="duplicate or unlisted"):
        restore_corpus(archive, tmp_path / "restored")


def test_archive_symlink_is_not_extracted(tmp_path):
    archive = custom_archive(tmp_path / "symlink.tar.gz", [("raw/link", b"")])
    # Rebuild with a symlink header but the same bounded manifest.
    with tarfile.open(archive, "r:gz") as source:
        manifest = source.extractfile(source.getmember(MANIFEST_NAME)).read()
    with tarfile.open(archive, "w:gz") as destination:
        header = tarfile.TarInfo(MANIFEST_NAME)
        header.size = len(manifest)
        destination.addfile(header, io.BytesIO(manifest))
        header = tarfile.TarInfo("data/raw/link")
        header.type, header.linkname = tarfile.SYMTYPE, "../../outside"
        destination.addfile(header)
    with pytest.raises(CorpusTransferError, match="type or size"):
        restore_corpus(archive, tmp_path / "restored")
    assert not (tmp_path / "outside").exists()


def test_configurable_capacity_guardrails(corpus, tmp_path):
    root, _, _ = corpus
    with pytest.raises(CorpusTransferError, match="byte limit"):
        inspect_corpus(root, limits=TransferLimits(max_file_bytes=1))
    archive = custom_archive(tmp_path / "limited.tar.gz", [("raw/item", b"1234")])
    with pytest.raises(CorpusTransferError, match="byte count"):
        restore_corpus(archive, tmp_path / "restored", limits=TransferLimits(max_total_bytes=3))


def test_restore_atomic_publish_keeps_raced_destination(corpus, tmp_path, monkeypatch):
    root, _, _ = corpus
    archive = tmp_path / "raced.tar.gz"
    pack_corpus(root, archive)
    import threegpp_web.corpus as module
    original = module._publish_directory
    target = tmp_path / "raced-target"
    def raced(staging, destination):
        target.mkdir()
        (target / "keep").write_text("other process")
        return original(staging, destination)
    monkeypatch.setattr(module, "_publish_directory", raced)
    with pytest.raises(CorpusTransferError, match="appeared"):
        restore_corpus(archive, target)
    assert (target / "keep").read_text() == "other process"
    assert not (target / "metadata.duckdb").exists()


def test_fixture_marker_and_chair_note_survive_roundtrip(tmp_path):
    from threegpp_web.fixtures import FIXTURE_MARKER, seed_fixture_corpus
    root = tmp_path / "synthetic"
    scope = seed_fixture_corpus(root)
    with MetadataRepository(root / "metadata.duckdb") as repository:
        TopicProfileService(repository, root).bootstrap_and_persist(
            TopicBootstrapRequest(working_group="RAN1", from_meeting="125", to_meeting="125",
                                  user_terms=scope["user_terms"]))
    before = stored_bytes(root)
    archive = tmp_path / "synthetic.tar.gz"
    pack_corpus(root, archive)
    result = restore_corpus(archive, tmp_path / "synthetic-restored")
    assert result["verification"]["checked"]["chair_notes"] == 1
    assert result["verification"]["checked"]["documents"] == 3
    assert (tmp_path / "synthetic-restored" / FIXTURE_MARKER).read_bytes() == before[FIXTURE_MARKER]
    assert stored_bytes(root) == before


def test_invalid_checksum_sidecar_reports_clear_error(corpus, tmp_path):
    root, _, _ = corpus
    archive = tmp_path / "sidecar.tar.gz"
    pack_corpus(root, archive)
    Path(str(archive) + ".sha256").write_text("")
    with pytest.raises(CorpusTransferError, match="sidecar is empty"):
        restore_corpus(archive, tmp_path / "must-not-exist")
    assert main(["restore", "--archive", str(archive),
                 "--destination", str(tmp_path / "also-absent")]) == 2


def test_chair_note_corruption_is_a_reported_provenance_error(tmp_path):
    from threegpp_web.fixtures import seed_fixture_corpus
    root = tmp_path / "synthetic"
    seed_fixture_corpus(root)
    note = next(root.glob("raw/chair-notes/*/*/cn-*/*"))
    note.write_bytes(b"changed without a new receipt")
    before = stored_bytes(root)
    result = verify_corpus(root)
    assert result["status"] == "blocked"
    assert any("Chair Note raw evidence" in error for error in result["errors"])
    assert stored_bytes(root) == before


def test_extended_tar_headers_bounded_before_payload_read(tmp_path):
    import gzip
    archive = tmp_path / "huge-pax.tar.gz"
    header = tarfile.TarInfo("pax_global_header")
    header.type = tarfile.XHDTYPE
    header.size = 1024**3
    # Only a 512-byte header exists; a safe parser rejects its declared size
    # rather than asking the gzip stream for the gigabyte payload.
    archive.write_bytes(gzip.compress(header.tobuf(format=tarfile.USTAR_FORMAT)))
    with pytest.raises(CorpusTransferError, match="extended header"):
        restore_corpus(archive, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()


def test_external_reader_view_does_not_qualify_as_source_table(tmp_path):
    import duckdb
    root = tmp_path / "view-db"
    root.mkdir()
    outside = tmp_path / "outside.csv"
    outside.write_text("tdoc_id,working_group,meeting_number,receipt_json\n")
    with MetadataRepository(root / "metadata.duckdb") as repository:
        repository.connection.execute("DROP TABLE tdoc_documents")
        escaped = str(outside).replace("'", "''")
        repository.connection.execute(
            f"CREATE VIEW tdoc_documents AS SELECT * FROM read_csv('{escaped}')")
    outside.unlink()
    # A view is not a supported core base table and must never be evaluated.
    result = verify_corpus(root)
    assert result["status"] == "blocked"
    assert any("schema" in error for error in result["errors"])


def test_archive_output_cannot_alias_inside_corpus(corpus, tmp_path):
    root, _, _ = corpus
    before = stored_bytes(root)
    alias = tmp_path / "corpus-alias"
    alias.symlink_to(root, target_is_directory=True)
    with pytest.raises(CorpusTransferError, match="outside"):
        pack_corpus(root, alias / "mutating.tar.gz")
    with pytest.raises(CorpusTransferError, match="outside"):
        pack_corpus(root, tmp_path / "nonexistent" / ".." / root.name / "mutating.tar.gz")
    assert stored_bytes(root) == before
