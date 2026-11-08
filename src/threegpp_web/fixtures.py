"""Explicit synthetic data for Stage A tests and a separately labelled demo.

Nothing in this module discovers or contacts 3GPP. It must never populate a real
research data directory or be presented as actual research evidence.
"""
from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as ET

from threegpp.chair_notes.rules import discovered_snapshot
from threegpp.chair_notes.service import ChairNoteService
from threegpp.db import MetadataRepository
from threegpp.documents import DocumentService, FetchPlanner
from threegpp.ingest.downloader import DownloadResult
from threegpp.models import TDocMetadata


FIXTURE_MARKER = "SYNTHETIC-FIXTURE-ONLY.txt"
FIXTURE_SCOPE = {"working_group": "RAN1", "from_meeting": "125", "to_meeting": "125",
                 "user_terms": ["FixtureTopic"], "interpretation": "meeting",
                 "corpus_as_of": "Synthetic fixture v1 — not actual 3GPP research"}


class _BytesSource:
    """Implements the core's byte-source protocol without any network client."""
    def __init__(self, payload):
        self.payload = payload

    def download(self, url, destination):
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.payload)
        return DownloadResult(destination, hashlib.sha256(self.payload).hexdigest(), True)


def _package(text):
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    document = ET.Element(namespace + "document")
    body = ET.SubElement(document, namespace + "body")
    for text_part in text.split("\n\n"):
        paragraph = ET.SubElement(body, namespace + "p")
        run = ET.SubElement(paragraph, namespace + "r")
        ET.SubElement(run, namespace + "t").text = text_part
    docx = io.BytesIO()
    with zipfile.ZipFile(docx, "w") as archive:
        archive.writestr("word/document.xml", ET.tostring(document))
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        member = zipfile.ZipInfo("SYNTHETIC_FIXTURE.docx", (2026, 1, 1, 0, 0, 0))
        archive.writestr(member, docx.getvalue())
    return output.getvalue()


def seed_fixture_corpus(data_root):
    """Create a new *synthetic* fixture directory, never modify existing research."""
    root = Path(data_root)
    if root.exists() and any(p.is_file() and p.name != ".gitkeep" for p in root.rglob("*")):
        if (root / FIXTURE_MARKER).is_file() and (root / "metadata.duckdb").is_file():
            return dict(FIXTURE_SCOPE)
        raise ValueError("fixture data require a new empty directory")
    root.mkdir(parents=True, exist_ok=True)
    (root / FIXTURE_MARKER).write_text(
        "Synthetic fixture only. Not actual 3GPP sources or a research report.\n", encoding="utf8")
    documents = [
        ("R1-9900001", "FixtureTopic synthetic contribution", ["Synthetic Company A"],
         "Proposal: FixtureTopic uses a synthetic timer.\n\n"
         "Condition: This is test data only and applies after a synthetic timeout."),
        ("R1-9900002", "FixtureTopic synthetic contribution", ["Synthetic Company B"],
         "Observation: FixtureTopic has a synthetic alternative.\n\n"
         "This example is not an actual technical claim."),
        ("R1-9900999", "Report of RAN1#125 meeting — SYNTHETIC FIXTURE", ["ETSI MCC"],
         "Agreement: FixtureTopic retains the synthetic evaluation step.\n\n"
         "Note: This statement exists only to test the independent outcome channel."),
    ]
    with MetadataRepository(root / "metadata.duckdb") as repository:
        for tdoc, title, organizations, text in documents:
            repository.upsert_tdoc(TDocMetadata(
                tdoc_id=tdoc, working_group="RAN1", meeting="125", title=title,
                organizations=organizations, official_list_present=True,
                directory_present=True, source_url=f"https://fixture.invalid/{tdoc}.zip"))
            plan = FetchPlanner(repository).explicit([("RAN1", "125", tdoc)])
            outcomes = DocumentService(repository, root, _BytesSource(_package(text))).execute(plan)
            if not outcomes[0].receipt:
                raise RuntimeError("synthetic fixture normalization failed")
    directory = "https://fixture.invalid/RAN1/125/Inbox/Chair_notes/"
    snapshot = discovered_snapshot("RAN1", "125", directory + "chair_notes_final.txt",
                                   directory, datetime(2026, 1, 1, tzinfo=UTC))
    text = ("FixtureTopic synthetic discussion R1-9900001.\n\n"
            "Agreement: This is Chair Note discussion context only, not a meeting outcome.")
    chairs = ChairNoteService(root, _BytesSource(text.encode()))
    chairs.discover(SimpleNamespace(working_group="RAN1", discover_chair_notes=lambda _: [snapshot]), "125")
    chairs.fetch("RAN1", "125", snapshot.snapshot_id)
    return dict(FIXTURE_SCOPE)


def fixture_report_writer(packet):
    """Deterministic quotation cards, never a claim of a real model's output."""
    claims = []
    for source in packet["sources"]:
        if source["passages"]:
            passage = source["passages"][0]
            claims.append({"text": "검증용 원문 인용: " + passage["literal_text"],
                           "sources": [source["key"]]})
    return {"title": "검증용 fixture 보고서 화면", "claims": claims}
