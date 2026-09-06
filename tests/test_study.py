from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from threegpp.db import MetadataRepository
from threegpp.models import MatchLevel, Meeting, StudyRequest, TDocMetadata, TDocQuery
from threegpp.study import StudyService


def test_study_request_yaml_round_trip(tmp_path) -> None:
    request = StudyRequest(
        name="6g-ul-access",
        working_groups=["RAN1", "RAN2"],
        meetings={"RAN1": ["124", "124BIS"], "RAN2": [133]},
        topics=["contention-based uplink"],
        organizations=["Nokia"],
        questions=["What alternatives were proposed?"],
    )
    path = tmp_path / "study.yaml"
    path.write_text(request.to_yaml(), encoding="utf-8")
    assert StudyRequest.from_yaml(path) == request
    assert request.meetings[request.working_groups[0]] == ["124", "124bis"]

    with pytest.raises(ValidationError):
        StudyRequest(
            name="invalid", working_groups=["RAN1"], meetings={"RAN2": ["133"]}
        )


def test_metadata_filtering_and_candidate_inventory(tmp_path) -> None:
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        for group, meeting in (("RAN1", "125"), ("RAN2", "133")):
            repository.upsert_meeting(
                Meeting(
                    working_group=group,
                    meeting_number=meeting,
                    source_url=f"https://www.3gpp.org/{group}/{meeting}",
                )
            )
        repository.upsert_tdoc(
            TDocMetadata(
                tdoc_id="R1-2604001", working_group="RAN1", meeting="125",
                title="Contention based uplink access", source_organization="Nokia",
                organizations=["Nokia"], agenda_item="9.1", status="discussed",
                metadata_source_kind="tdoc_list", metadata_source_url="https://www.3gpp.org/list.xlsx"
            )
        )
        repository.upsert_tdoc(
            TDocMetadata(
                tdoc_id="R2-2601001", working_group="RAN2", meeting="133",
                title="Downlink mobility", source_organization="Ericsson",
                organizations=["Ericsson"], agenda_item="7.2", status="noted",
                metadata_source_kind="tdoc_list", metadata_source_url="https://www.3gpp.org/list2.xlsx"
            )
        )

        filtered = repository.query_tdocs(
            TDocQuery(
                working_groups=["RAN1"], title_contains="uplink", organization="Nokia",
                agenda_item="9.1", status="discussed", tdoc_id="r1-2604001"
            )
        )
        inventory = StudyService(repository).candidate_inventory(
            StudyRequest(
                name="ul", working_groups=["RAN1", "RAN2"],
                meetings={"RAN1": ["125"], "RAN2": ["133"]},
                topics=["contention-based uplink"], organizations=["Nokia"]
            )
        )

    assert [record.tdoc_id for record in filtered] == ["R1-2604001"]
    assert inventory.candidate_count == 1
    assert inventory.downloadable_count == 0
    assert inventory.listed_only_count == 1
    assert inventory.by_organization == {"Nokia": 1}
    assert inventory.high_match_count == 1
    assert inventory.medium_match_count == 0
    assert inventory.low_match_count == 0
    assert inventory.missing_meetings == {}
    assert "document bodies not analyzed" in inventory.classification


def test_candidate_match_levels_and_evidence_are_deterministic(tmp_path) -> None:
    records = [
        TDocMetadata(
            tdoc_id="R1-2605001", working_group="RAN1", meeting="125",
            title="Contention based uplink access", source_url="https://www.3gpp.org/a.zip",
            directory_present=True, official_list_present=True,
            metadata_source_kind="tdoc_list", metadata_source_url="https://www.3gpp.org/list.xlsx",
        ),
        TDocMetadata(
            tdoc_id="R1-2605002", working_group="RAN1", meeting="125",
            abstract="A contention based uplink access mechanism", official_list_present=True,
            metadata_source_kind="tdoc_list", metadata_source_url="https://www.3gpp.org/list.xlsx",
        ),
        TDocMetadata(
            tdoc_id="R1-2605003", working_group="RAN1", meeting="125",
            title="Enhanced uplink access", abstract="Contention based transmission mechanism",
            official_list_present=True,
            metadata_source_kind="tdoc_list", metadata_source_url="https://www.3gpp.org/list.xlsx",
        ),
        TDocMetadata(
            tdoc_id="R1-2605004", working_group="RAN1", meeting="125",
            title="Contention based options", agenda_item_description="Uplink access",
            official_list_present=True, metadata_source_kind="tdoc_list",
            metadata_source_url="https://www.3gpp.org/list.xlsx",
        ),
        TDocMetadata(
            tdoc_id="R1-2605005", working_group="RAN1", meeting="125",
            title="Contention uplink considerations", official_list_present=True,
            metadata_source_kind="tdoc_list", metadata_source_url="https://www.3gpp.org/list.xlsx",
        ),
        TDocMetadata(
            tdoc_id="R1-2605006", working_group="RAN1", meeting="125",
            title="Radio system access", official_list_present=True,
            metadata_source_kind="tdoc_list", metadata_source_url="https://www.3gpp.org/list.xlsx",
        ),
        TDocMetadata(
            tdoc_id="R1-2605007", working_group="RAN1", meeting="125",
            title="Unrelated mobility", status="contention based uplink access",
            official_list_present=True,
            metadata_source_kind="tdoc_list", metadata_source_url="https://www.3gpp.org/list.xlsx",
        ),
        TDocMetadata(
            tdoc_id="R1-2605008", working_group="RAN1", meeting="125",
            title="Unrelated mobility", document_type="contention based uplink access",
            official_list_present=True,
            metadata_source_kind="tdoc_list", metadata_source_url="https://www.3gpp.org/list.xlsx",
        ),
        TDocMetadata(
            tdoc_id="R1-2605009", working_group="RAN1", meeting="125",
            title="Unrelated mobility", related_work_item="contention based uplink access",
            official_list_present=True,
            metadata_source_kind="tdoc_list", metadata_source_url="https://www.3gpp.org/list.xlsx",
        ),
        TDocMetadata(
            tdoc_id="R1-2605010", working_group="RAN1", meeting="125",
            title="Unrelated mobility", release="contention based",
            specification="uplink access", official_list_present=True,
            metadata_source_kind="tdoc_list", metadata_source_url="https://www.3gpp.org/list.xlsx",
        ),
        TDocMetadata(
            tdoc_id="R1-2605011", working_group="RAN1", meeting="125",
            title="Access considerations", related_work_item="contention based uplink access",
            official_list_present=True,
            metadata_source_kind="tdoc_list", metadata_source_url="https://www.3gpp.org/list.xlsx",
        ),
        TDocMetadata(
            tdoc_id="R1-2605012", working_group="RAN1", meeting="125",
            title="Contention uplink options", related_work_item="based access",
            official_list_present=True,
            metadata_source_kind="tdoc_list", metadata_source_url="https://www.3gpp.org/list.xlsx",
        ),
    ]
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        repository.upsert_meeting(
            Meeting(
                working_group="RAN1", meeting_number="125",
                source_url="https://www.3gpp.org/RAN1/125",
            )
        )
        for record in records:
            repository.upsert_tdoc(record)
        inventory = StudyService(repository).candidate_inventory(
            StudyRequest(
                name="metadata-match", working_groups=["RAN1"], meetings={"RAN1": ["125"]},
                topics=["contention based uplink access"],
            )
        )

    assert inventory.candidate_count == 6
    assert inventory.downloadable_count == 1
    assert inventory.listed_only_count == 5
    assert (inventory.high_match_count, inventory.medium_match_count, inventory.low_match_count) == (
        2, 3, 1,
    )
    candidates = {item.tdoc.tdoc_id: item for item in inventory.candidate_tdocs}
    assert candidates["R1-2605001"].match_level is MatchLevel.HIGH
    assert candidates["R1-2605002"].match_level is MatchLevel.HIGH
    assert candidates["R1-2605003"].match_level is MatchLevel.MEDIUM
    assert candidates["R1-2605003"].matched_fields == {
        "title": ["uplink", "access"],
        "abstract": ["contention", "based"],
    }
    assert candidates["R1-2605003"].covered_topic_tokens == [
        "contention", "based", "uplink", "access",
    ]
    assert candidates["R1-2605004"].match_level is MatchLevel.MEDIUM
    assert candidates["R1-2605005"].match_level is MatchLevel.LOW
    assert candidates["R1-2605012"].match_level is MatchLevel.MEDIUM
    assert candidates["R1-2605012"].anchor_fields_matched == {
        "title": ["contention", "uplink"]
    }
    assert candidates["R1-2605012"].supporting_fields_matched == {
        "related_work_item": ["based", "access"]
    }
    assert set(candidates) == {
        "R1-2605001", "R1-2605002", "R1-2605003", "R1-2605004", "R1-2605005",
        "R1-2605012",
    }
    assert candidates["R1-2605001"].availability.value == "downloadable"
    assert candidates["R1-2605002"].availability.value == "listed_only"
    assert "document bodies not analyzed" in inventory.classification


def test_skill_example_is_a_valid_study_request() -> None:
    path = Path("skills/3gpp-study/resources/study-request.example.yaml")
    request = StudyRequest.from_yaml(path)
    assert request.name == "6g-ul-access"
    assert set(request.meetings) == set(request.working_groups)
