from __future__ import annotations

import gzip
import hashlib
import io
import json
import zipfile

import duckdb
import pytest

from threegpp.db import MetadataRepository
from threegpp.documents.models import ContentBlock, ExtractionStatus
from threegpp.documents.parsers import parser_for
from threegpp.documents.service import DocumentService, FetchPlanner
from threegpp.ingest.downloader import DownloadResult, HTTPDownloader
from threegpp.models import TDocMetadata


TDOC = "R1-2604000"


class LocalFixtureDownloader:
    def __init__(self, members):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as package:
            for filename, payload in members.items():
                package.writestr(filename, payload)
        self.payload = output.getvalue()

    def download(self, url, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.payload)
        return DownloadResult(destination, hashlib.sha256(self.payload).hexdigest(), True)


def prepare_source(tmp_path, *, members=None):
    data_root = tmp_path / "data"
    db = data_root / "metadata.duckdb"
    with MetadataRepository(db) as repository:
        repository.upsert_tdoc(TDocMetadata(
            tdoc_id=TDOC, working_group="RAN1", meeting="125",
            title="HARQ background", organizations=["Example Company"],
            source_url=f"https://example.test/{TDOC}.zip", directory_present=True,
        ))
        plan = FetchPlanner(repository).explicit([("RAN1", "125", TDOC)])
        receipt = DocumentService(repository, data_root, LocalFixtureDownloader(
            members or {"paper.txt": "HARQ background without a formal label.\n\n"
                                     "Recovery applies only when the timer expires."},
        )).execute(plan)[0].receipt
        assert receipt is not None
    return db, data_root, receipt


def stored_bytes(root):
    return {str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


def replace_receipt(db, receipt, **updates):
    receipt = receipt.model_copy(update=updates)
    with MetadataRepository(db) as repository:
        repository.upsert_document_receipt(receipt)
    return receipt


def rewrite_blocks(db, root, receipt, change):
    path = root / receipt.normalized_path
    blocks = [json.loads(line) for line in gzip.decompress(path.read_bytes()).splitlines()]
    change(blocks)
    payload = gzip.compress("".join(json.dumps(block) + "\n" for block in blocks).encode(), mtime=0)
    path.write_bytes(payload)
    return replace_receipt(db, receipt, normalized_checksum=hashlib.sha256(payload).hexdigest())


def test_read_only_repository_skips_schema_and_preserves_database(tmp_path, monkeypatch):
    db, root, _ = prepare_source(tmp_path)
    before = stored_bytes(root)
    monkeypatch.setattr("threegpp.db.repository.ensure_schema",
                        lambda *a: pytest.fail("read-only connection initialized schema"))
    with MetadataRepository(db, read_only=True) as repository:
        assert repository.read_only
        assert repository.get_tdoc("RAN1", "125", TDOC).tdoc_id == TDOC
        with pytest.raises(duckdb.Error):
            repository.connection.execute("CREATE TABLE forbidden(value INTEGER)")
    assert stored_bytes(root) == before


def test_read_only_repository_does_not_create_missing_parent(tmp_path):
    missing = tmp_path / "absent" / "metadata.duckdb"
    with pytest.raises(duckdb.Error):
        MetadataRepository(missing, read_only=True)
    assert not missing.parent.exists()


def test_valid_source_needs_no_semantic_extraction_or_review(tmp_path, monkeypatch):
    db, root, expected_receipt = prepare_source(tmp_path)
    before = stored_bytes(root)
    monkeypatch.setattr(HTTPDownloader, "download", lambda *a, **k: pytest.fail("download"))
    monkeypatch.setattr(DocumentService, "execute", lambda *a, **k: pytest.fail("normalization"))
    with MetadataRepository(db, read_only=True) as repository:
        assert repository.connection.execute("SELECT count(*) FROM semantic_evidence").fetchone() == (0,)
        metadata, receipt, blocks = DocumentService(repository, root).read_source(
            TDOC.lower(), "ran1", "125")
        assert metadata.organizations == ["Example Company"]
        assert receipt == expected_receipt
        assert all(isinstance(block, ContentBlock) for block in blocks)
        assert [block.text for block in blocks] == [
            "HARQ background without a formal label.",
            "Recovery applies only when the timer expires.",
        ]
        assert [(block.block_id, block.member_filename, block.order) for block in blocks] == [
            ("b000001", "paper.txt", 1), ("b000002", "paper.txt", 2),
        ]
    assert stored_bytes(root) == before


def test_read_source_does_not_require_current_metadata_raw_or_flattened_text(tmp_path):
    db, root, receipt = prepare_source(tmp_path)
    with MetadataRepository(db) as repository:
        repository.connection.execute("DELETE FROM tdoc_metadata")
    receipt.raw.local_path.unlink()
    (root / receipt.text_path).unlink()
    before = stored_bytes(root)
    with MetadataRepository(db, read_only=True) as repository:
        metadata, actual_receipt, blocks = DocumentService(repository, root).read_source(TDOC)
    assert metadata is None and actual_receipt == receipt and len(blocks) == 2
    assert stored_bytes(root) == before


def test_partial_package_preserves_member_gaps(tmp_path):
    db, root, expected = prepare_source(tmp_path, members={
        "paper.txt": "A readable contribution.", "attachment.bin": b"unsupported",
    })
    with MetadataRepository(db, read_only=True) as repository:
        _, receipt, blocks = DocumentService(repository, root).read_source(TDOC)
    assert receipt == expected
    assert receipt.extraction_status is ExtractionStatus.PARTIALLY_PARSED
    assert receipt.members[1].extraction_status is ExtractionStatus.UNSUPPORTED_FORMAT
    assert receipt.warnings and [block.member_filename for block in blocks] == ["paper.txt"]


@pytest.mark.parametrize("damage,reason", [
    ("raw", "retained raw source checksum"),
    ("normalized", "normalized source checksum"),
    ("missing_normalized", "source bytes are unavailable"),
    ("parser", "identity is stale"),
    ("schema", "identity is stale"),
    ("receipt_schema", "receipt schema is stale"),
    ("identity_raw", "identity is stale"),
    ("parser_versions", "identity is stale"),
    ("count", "block count"),
    ("duplicate_member", "duplicate member"),
    ("primary_member", "primary member"),
    ("receipt_identity", "receipt identity"),
    ("unsupported", "unreadable \\(unsupported_format\\)"),
])
def test_invalid_sources_raise_without_mutating_state(tmp_path, monkeypatch, damage, reason):
    db, root, receipt = prepare_source(tmp_path)
    if damage == "raw":
        receipt.raw.local_path.write_bytes(b"changed raw")
    elif damage == "normalized":
        (root / receipt.normalized_path).write_bytes(b"changed normalized")
    elif damage == "missing_normalized":
        (root / receipt.normalized_path).unlink()
    elif damage == "parser":
        monkeypatch.setattr(parser_for("paper.txt"), "version", "changed")
    elif damage in {"schema", "identity_raw"}:
        updates = ({"normalized_schema_version": "changed"} if damage == "schema"
                   else {"raw_sha256": "changed"})
        replace_receipt(db, receipt, normalization_identity=receipt.normalization_identity.model_copy(
            update=updates))
    elif damage == "parser_versions":
        replace_receipt(db, receipt, parser_versions={"text": "changed"})
    elif damage == "receipt_schema":
        replace_receipt(db, receipt, schema_version="changed")
    elif damage == "count":
        replace_receipt(db, receipt, block_count=receipt.block_count + 1)
    elif damage == "duplicate_member":
        replace_receipt(db, receipt, members=receipt.members + receipt.members)
    elif damage == "primary_member":
        replace_receipt(db, receipt, primary_member="missing.txt")
    elif damage == "receipt_identity":
        with MetadataRepository(db) as repository:
            repository.connection.execute("UPDATE tdoc_documents SET receipt_json=?", [
                receipt.model_copy(update={"meeting": "126"}).model_dump_json()])
    elif damage == "unsupported":
        replace_receipt(db, receipt, extraction_status=ExtractionStatus.UNSUPPORTED_FORMAT)
    before = stored_bytes(root)
    with MetadataRepository(db, read_only=True) as repository:
        with pytest.raises(ValueError, match=reason):
            DocumentService(repository, root).read_source(TDOC)
    assert stored_bytes(root) == before


@pytest.mark.parametrize("field,value,reason", [
    ("block_id", "b999999", "block identity"),
    ("order", 9, "block identity"),
    ("member_filename", "other.txt", "block identity"),
    ("type", "fabricated", "block structure"),
    ("page_number", 0, "block structure"),
    ("rows", [["wrong shape"]], "block structure"),
])
def test_invalid_block_locators_and_structure_are_rejected(tmp_path, field, value, reason):
    db, root, receipt = prepare_source(tmp_path)
    rewrite_blocks(db, root, receipt, lambda blocks: blocks[0].update({field: value}))
    before = stored_bytes(root)
    with MetadataRepository(db, read_only=True) as repository:
        with pytest.raises(ValueError, match=reason):
            DocumentService(repository, root).read_source(TDOC)
    assert stored_bytes(root) == before


def test_unreadable_gzip_and_missing_source_remain_explicit(tmp_path):
    db, root, receipt = prepare_source(tmp_path)
    payload = b"not a gzip source"
    (root / receipt.normalized_path).write_bytes(payload)
    replace_receipt(db, receipt, normalized_checksum=hashlib.sha256(payload).hexdigest())
    before = stored_bytes(root)
    with MetadataRepository(db, read_only=True) as repository:
        service = DocumentService(repository, root)
        with pytest.raises(ValueError, match="blocks are unreadable"):
            service.read_source(TDOC)
        with pytest.raises(ValueError, match="source is unavailable"):
            service.read_source("R1-9999999")
    assert stored_bytes(root) == before


def test_relative_raw_path_is_verified_from_data_root(tmp_path, monkeypatch):
    db, root, receipt = prepare_source(tmp_path)
    relative = receipt.raw.local_path.relative_to(tmp_path)
    replace_receipt(db, receipt, raw=receipt.raw.model_copy(update={"local_path": relative}))
    receipt.raw.local_path.write_bytes(b"corrupt retained raw")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    with MetadataRepository(db, read_only=True) as repository:
        with pytest.raises(ValueError, match="retained raw source checksum"):
            DocumentService(repository, root).read_source(TDOC)


def test_docx_source_preserves_heading_and_table_context(tmp_path):
    from test_documents import _docx

    db, root, _ = prepare_source(tmp_path, members={"paper.docx": _docx()})
    with MetadataRepository(db, read_only=True) as repository:
        _, _, blocks = DocumentService(repository, root).read_source(TDOC)
    assert [block.type for block in blocks] == ["heading", "paragraph", "table"]
    assert all(block.heading_path == ["Introduction"] for block in blocks)
    assert blocks[0].heading_level == 1
    assert blocks[2].rows == [["A", "B"]]
