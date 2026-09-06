from __future__ import annotations

import io
import hashlib
import zipfile

import pytest
from openpyxl import Workbook

from threegpp.db import MetadataRepository
from threegpp.documents.archive import UnsafeArchiveError, inspect_package
from threegpp.documents.models import ExtractionStatus, RetentionState
from threegpp.documents.parsers import DocxParser, PdfParser, SpreadsheetDocumentParser, TextParser, parser_for
from threegpp.documents.service import DocumentService, FetchPlanner
from threegpp.ingest.downloader import DownloadConflictError, DownloadResult
from threegpp.models import TDocMetadata
from threegpp.models import CandidateInventory, CandidateTDoc, CandidateView, MatchLevel


def _docx() -> bytes:
    xml = b'''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Introduction</w:t></w:r></w:p><w:p><w:r><w:t>Body text</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>A</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>B</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>'''
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w") as z: z.writestr("word/document.xml", xml)
    return target.getvalue()


def test_docx_structure_and_stable_ids():
    first = DocxParser().parse(_docx(), "paper.docx")[0]
    second = DocxParser().parse(_docx(), "paper.docx")[0]
    assert [b.type for b in first] == ["heading", "paragraph", "table"]
    assert first[0].heading_level == 1 and first[2].rows == [["A", "B"]]
    assert [b.block_id for b in first] == ["b000001", "b000002", "b000003"]
    assert first == second


def test_spreadsheet_multiple_sheets():
    book = Workbook(); book.active.title = "Main"; book.active.append(["a", 1]); book.create_sheet("Other").append(["b", 2])
    data = io.BytesIO(); book.save(data)
    blocks, status, _ = SpreadsheetDocumentParser().parse(data.getvalue(), "x.xlsx")
    assert status is ExtractionStatus.PARSED
    assert [(b.sheet_name, b.rows) for b in blocks] == [("Main", [["a", 1]]), ("Other", [["b", 2]])]


def test_archive_multiple_nested_and_unsupported():
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w") as z:
        z.writestr("nested/readme.txt", "hello"); z.writestr("image.bin", b"x")
    members = inspect_package(target.getvalue(), "R1.zip")
    assert [m.metadata.filename for m in members] == ["nested/readme.txt", "image.bin"]
    assert members[0].metadata.role == "probable_primary"


@pytest.mark.parametrize(
    "name",
    ["../evil.txt", "../../evil.txt", "/absolute/path.txt", "ok/../../evil.txt", r"C:\evil.txt", "C:/evil.txt"],
)
def test_archive_rejects_traversal(name):
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w") as z: z.writestr(name, "bad")
    with pytest.raises(UnsafeArchiveError): inspect_package(target.getvalue(), "x.zip")


def test_archive_size_guard():
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w") as z: z.writestr("big.txt", "12345")
    with pytest.raises(UnsafeArchiveError): inspect_package(target.getvalue(), "x.zip", max_member_bytes=4)


class FakeDownloader:
    def __init__(self, data): self.data, self.calls = data, 0
    def download(self, url, destination):
        import hashlib
        self.calls += 1; destination.parent.mkdir(parents=True, exist_ok=True); destination.write_bytes(self.data)
        return DownloadResult(destination, hashlib.sha256(self.data).hexdigest(), True)


def _pdf(page_texts: list[str]) -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{' '.join(f'{3 + 2 * index} 0 R' for index in range(len(page_texts)))}] /Count {len(page_texts)} >>".encode(),
    ]
    font_object = 3 + 2 * len(page_texts)
    for index, page_text in enumerate(page_texts):
        page_object = 3 + 2 * index
        content_object = page_object + 1
        escaped = page_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode()
        objects.extend([
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_object} 0 R >> >> /Contents {content_object} 0 R >>".encode(),
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        ])
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    output = io.BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = [0]
    for number, payload in enumerate(objects, 1):
        offsets.append(output.tell())
        output.write(f"{number} 0 obj\n".encode() + payload + b"\nendobj\n")
    xref = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n".encode())
    output.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.write(f"{offset:010d} 00000 n \n".encode())
    output.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return output.getvalue()


def test_pdf_pages_are_ordered_and_empty_pdf_has_no_fabricated_text():
    parser = PdfParser()
    first, status, warnings = parser.parse(_pdf(["First page", "Second page"]), "paper.pdf")
    second = parser.parse(_pdf(["First page", "Second page"]), "paper.pdf")[0]
    assert status is ExtractionStatus.PARSED and warnings == []
    assert [(block.block_id, block.page_number, block.text) for block in first] == [
        ("b000001", 1, "First page"),
        ("b000002", 2, "Second page"),
    ]
    assert first == second

    blocks, status, warnings = parser.parse(_pdf([""]), "empty.pdf")
    assert blocks == []
    assert status is ExtractionStatus.TEXT_UNAVAILABLE
    assert warnings == ["PDF has no extractable text; OCR is not enabled"]


def test_explicit_plan_fetch_cache_retrieval_and_receipt(tmp_path):
    repo = MetadataRepository(tmp_path / "metadata.duckdb")
    repo.upsert_tdoc(TDocMetadata(tdoc_id="R1-2600001", working_group="RAN1", meeting="125", source_url="https://example.test/R1-2600001.zip", directory_present=True))
    plan = FetchPlanner(repo).explicit([("RAN1", "125", "R1-2600001")], reason="explicitly requested by user")
    assert plan.items[0].selection_reasons == ["explicitly requested by user"]
    fake = FakeDownloader(_docx())
    # A DOCX package delivered under a ZIP-looking official URL remains a package;
    # use text ZIP here to exercise package extraction.
    package = io.BytesIO()
    with zipfile.ZipFile(package, "w") as z: z.writestr("readme.txt", "hello world")
    fake.data = package.getvalue()
    service = DocumentService(repo, tmp_path, fake)
    first = service.execute(plan)[0]
    second = service.execute(plan)[0]
    assert first.status is ExtractionStatus.PARSED and first.receipt.block_count == 1
    assert second.message.startswith("reused") and fake.calls == 1
    metadata, receipt, blocks, text = service.retrieve("R1-2600001")
    assert metadata.tdoc_id == receipt.tdoc_id and blocks[0]["block_id"] == "b000001"
    assert "hello world" in text and receipt.raw.retention is RetentionState.CACHE
    assert "normalized_text" not in (tmp_path / "manifests/documents/ran1/125/R1-2600001/receipt.json").read_text()
    repo.close()


def test_normalization_identity_output_integrity_and_retention_round_trip(tmp_path, monkeypatch):
    repo = MetadataRepository(tmp_path / "metadata.duckdb")
    repo.upsert_tdoc(TDocMetadata(tdoc_id="R1-2600002", working_group="RAN1", meeting="125", source_url="https://example.test/R1-2600002.zip", directory_present=True))
    plan = FetchPlanner(repo).explicit([("RAN1", "125", "R1-2600002")])
    package = io.BytesIO()
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("readme.txt", "identity test")
    fake = FakeDownloader(package.getvalue())

    service = DocumentService(repo, tmp_path, fake, normalized_schema_version="1")
    first = service.execute(plan)[0]
    reused = service.execute(plan)[0]
    assert reused.message.startswith("reused") and fake.calls == 1
    assert first.receipt.normalization_identity == reused.receipt.normalization_identity
    assert first.receipt.normalization_identity.parser_members == {"readme.txt": "text@1"}

    text_parser = parser_for("readme.txt")
    monkeypatch.setattr(text_parser, "version", "2")
    parser_changed = service.execute(plan)[0]
    assert parser_changed.message == "normalized cached raw artifact" and fake.calls == 1
    assert parser_changed.receipt.normalization_identity.parser_members == {"readme.txt": "text@2"}

    schema_service = DocumentService(repo, tmp_path, fake, normalized_schema_version="2")
    schema_changed = schema_service.execute(plan)[0]
    assert schema_changed.message == "normalized cached raw artifact" and fake.calls == 1
    assert schema_changed.receipt.normalization_identity.normalized_schema_version == "2"
    assert schema_changed.receipt.raw.sha256 == first.receipt.raw.sha256

    text_path = tmp_path / schema_changed.receipt.text_path
    text_path.write_bytes(b"corrupt")
    repaired = schema_service.execute(plan)[0]
    assert repaired.message == "normalized cached raw artifact" and fake.calls == 1
    assert hashlib.sha256(text_path.read_bytes()).hexdigest() == repaired.receipt.text_checksum

    pinned_plan = plan.model_copy(update={"items": [plan.items[0].model_copy(update={"retention": RetentionState.PINNED})]})
    before_checksums = (repaired.receipt.raw.sha256, repaired.receipt.normalized_checksum, repaired.receipt.text_checksum)
    pinned = schema_service.execute(pinned_plan)[0]
    assert pinned.message.startswith("reused") and fake.calls == 1
    assert pinned.receipt.raw.retention is RetentionState.PINNED
    assert (pinned.receipt.raw.sha256, pinned.receipt.normalized_checksum, pinned.receipt.text_checksum) == before_checksums
    assert repo.get_document_receipt("R1-2600002").raw.retention is RetentionState.PINNED
    indexed = repo.connection.execute(
        "SELECT text_checksum, normalization_identity_json, normalized_schema_version, retention_state "
        "FROM tdoc_documents WHERE tdoc_id = 'R1-2600002'"
    ).fetchone()
    assert indexed == (pinned.receipt.text_checksum, pinned.receipt.normalization_identity.model_dump_json(), "2", "pinned")

    raw_path = pinned.receipt.raw.local_path
    original_raw = raw_path.read_bytes()
    raw_path.write_bytes(b"conflicting local bytes")
    with pytest.raises(DownloadConflictError, match="provenance conflicts"):
        schema_service.execute(pinned_plan)
    assert raw_path.read_bytes() == b"conflicting local bytes"
    raw_path.write_bytes(original_raw)
    repo.close()


def test_listed_only_is_preserved_not_fetched(tmp_path):
    repo = MetadataRepository(tmp_path / "db.duckdb")
    repo.upsert_tdoc(TDocMetadata(tdoc_id="R1-1", working_group="RAN1", meeting="125", official_list_present=True))
    plan = FetchPlanner(repo).explicit([("RAN1", "125", "R1-1")])
    outcome = DocumentService(repo, tmp_path, FakeDownloader(b"never")).execute(plan)[0]
    assert outcome.status is ExtractionStatus.NOT_FETCHED
    assert outcome.message == "body unavailable from discovered official source"
    repo.close()


def test_inventory_plan_filters_levels_availability_and_limit(tmp_path):
    repo = MetadataRepository(tmp_path / "db.duckdb")
    def candidate(number, level, downloadable=True):
        tdoc = TDocMetadata(tdoc_id=f"R1-{number}", working_group="RAN1", meeting="125", source_url=f"https://example.test/R1-{number}.zip" if downloadable else None, directory_present=downloadable, official_list_present=True)
        return CandidateTDoc(tdoc=tdoc, match_level=level, availability=tdoc.availability)
    inventory = CandidateInventory(study_name="s", view=CandidateView(), meetings_inspected={"RAN1":["125"]}, candidate_count=3, downloadable_count=2, listed_only_count=1, unknown_availability_count=0, high_match_count=1, medium_match_count=2, low_match_count=0, by_organization={}, by_meeting={}, by_agenda_item={}, candidate_tdocs=[candidate("1", MatchLevel.HIGH), candidate("2", MatchLevel.MEDIUM), candidate("3", MatchLevel.MEDIUM, False)])
    assert [x.tdoc_id for x in FetchPlanner(repo).from_inventory(inventory).items] == ["R1-1"]
    assert [x.tdoc_id for x in FetchPlanner(repo).from_inventory(inventory, minimum_match=MatchLevel.MEDIUM).items] == ["R1-1", "R1-2"]
    with pytest.raises(ValueError, match="batch limit"):
        FetchPlanner(repo, batch_limit=1).from_inventory(inventory, minimum_match=MatchLevel.MEDIUM)
    repo.close()
