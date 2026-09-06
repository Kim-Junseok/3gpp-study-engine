from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import xlwt
from openpyxl import Workbook

from threegpp.models import SourceArtifact
from threegpp.normalize import TDocListParser, normalize_organizations


def downloaded_artifact(path: Path, *, working_group: str, meeting: str) -> SourceArtifact:
    timestamp = datetime(2026, 5, 1, tzinfo=UTC)
    return SourceArtifact(
        artifact_type="tdoc_list",
        working_group=working_group,
        meeting=meeting,
        source_url=f"https://www.3gpp.org/{working_group.lower()}-{meeting}-list{path.suffix}",
        discovered_at=timestamp,
        retrieved_at=timestamp,
        local_path=path,
        checksum=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def test_parse_ran1_xlsx_layout_variant(tmp_path) -> None:
    path = tmp_path / "ran1.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Documents"
    sheet.append(["RAN1 meeting document list"])
    sheet.append([])
    sheet.append(
        [
            "Document Number", "Document Title", "Submitted By", "AI", "Decision",
            "Document Type", "CR Revision", "Replaces", "Useful Future Column",
            "Abstract", "Agenda item description", "For", "Release", "Spec", "Related WIs",
        ]
    )
    sheet.append(
        [
            "R1-2604001", "Uplink access options",
            " Pengcheng Laboratory,\nZGC Institute of Ubiquitous-X Innovation and Application ",
            "8.1", "agreed", "discussion", "2", "R1-2603999", "preserve me",
            "Evaluates uplink access", "6G radio study", "Discussion", "Rel-20",
            "38.300", "FS_6G_Radio",
        ]
    )
    sheet.append(["not-a-tdoc", "unmapped row"])
    workbook.save(path)

    result = TDocListParser().parse(path, downloaded_artifact(path, working_group="RAN1", meeting="125"))

    assert result.summary.sheet_name == "Documents"
    assert result.summary.header_row == 3
    assert result.summary.mapped_rows == 1
    assert result.summary.unmapped_rows == 1
    assert "Useful Future Column" in result.summary.unknown_columns
    record = result.tdocs[0]
    assert record.title == "Uplink access options"
    assert record.source_organization_raw == (
        " Pengcheng Laboratory,\nZGC Institute of Ubiquitous-X Innovation and Application "
    )
    assert record.organizations == [
        "Pengcheng Laboratory", "ZGC Institute of Ubiquitous-X Innovation and Application"
    ]
    assert record.related_tdoc_ids == ["R1-2603999"]
    assert record.raw_metadata["Useful Future Column"] == "preserve me"
    assert str(record.field_provenance["title"].source_url).endswith("ran1-125-list.xlsx")
    assert record.abstract == "Evaluates uplink access"
    assert record.agenda_item_description == "6G radio study"
    assert record.intended_for == "Discussion"
    assert record.release == "Rel-20"
    assert record.specification == "38.300"
    assert record.related_work_item == "FS_6G_Radio"
    expected_columns = {
        "abstract": "Abstract",
        "agenda_item_description": "Agenda item description",
        "intended_for": "For",
        "release": "Release",
        "specification": "Spec",
        "related_work_item": "Related WIs",
    }
    assert {
        field: record.field_provenance[field].source_column for field in expected_columns
    } == expected_columns
    assert all(
        record.field_provenance[field].source_checksum
        == record.field_provenance["title"].source_checksum
        for field in expected_columns
    )


def test_parse_ran2_legacy_xls_layout_variant(tmp_path) -> None:
    path = tmp_path / "ran2.xls"
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet("TDoc list")
    headers = [
        "TDoc No.", "Title", "Source Organisation", "Agenda", "Status", "Category",
        "Is revision of", "Mystery",
    ]
    for column, value in enumerate(headers):
        sheet.write(0, column, value)
    values = [
        "R2-2601001", "Scheduling request enhancement", "Nokia Shanghai Bell Co., Ltd., Qualcomm",
        "7.2.1", "noted", "B", "R2-2600999", "raw value",
    ]
    for column, value in enumerate(values):
        sheet.write(1, column, value)
    workbook.save(str(path))

    result = TDocListParser().parse(path, downloaded_artifact(path, working_group="RAN2", meeting="133"))

    assert result.summary.mapped_rows == 1
    record = result.tdocs[0]
    assert record.document_category == "B"
    assert record.organizations == ["Nokia Shanghai Bell Co., Ltd.", "Qualcomm"]
    assert record.agenda_item == "7.2.1"
    assert record.abstract is None


def test_organization_normalization_is_conservative() -> None:
    assert normalize_organizations("Nokia / Ericsson\nSamsung; Nokia") == [
        "Nokia / Ericsson", "Samsung", "Nokia"
    ]
    assert normalize_organizations("Example Co., Ltd., Qualcomm") == [
        "Example Co., Ltd.", "Qualcomm"
    ]
    assert normalize_organizations("Standards and Testing Institute") == [
        "Standards and Testing Institute"
    ]
    assert normalize_organizations("Research & Development Institute") == [
        "Research & Development Institute"
    ]
    assert normalize_organizations("Access/Network + Systems Lab") == [
        "Access/Network + Systems Lab"
    ]
    assert normalize_organizations(
        "Pengcheng Laboratory,\nZGC Institute of Ubiquitous-X Innovation and Application"
    ) == [
        "Pengcheng Laboratory",
        "ZGC Institute of Ubiquitous-X Innovation and Application",
    ]
