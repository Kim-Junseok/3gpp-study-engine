from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from threegpp.models import ArtifactType, Meeting, SourceArtifact, normalize_meeting_identifier


@pytest.mark.parametrize(
    ("raw", "expected"), [("124", "124"), (124, "124"), ("124BIS", "124bis"), ("119-E", "119-e")]
)
def test_normalized_meeting_identifiers(raw: str | int, expected: str) -> None:
    assert normalize_meeting_identifier(raw) == expected


@pytest.mark.parametrize("raw", ["", "RAN1#124", "124-bis", "special"])
def test_invalid_meeting_identifiers(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_meeting_identifier(raw)


def test_pydantic_models_preserve_unknowns() -> None:
    meeting = Meeting(working_group="ran1", meeting_number="124BIS", source_url="https://www.3gpp.org/x")
    assert meeting.meeting_number == "124bis"
    assert meeting.location is None

    artifact = SourceArtifact(
        artifact_type=ArtifactType.TDOC_LIST,
        working_group="RAN1",
        meeting="124bis",
        source_url="https://www.3gpp.org/list.xlsx",
        discovered_at=datetime.now(UTC),
    )
    assert artifact.retrieved_at is None
    assert artifact.checksum is None


def test_downloaded_artifact_requires_complete_retrieval_provenance(tmp_path) -> None:
    now = datetime.now(UTC)
    artifact = SourceArtifact(
        artifact_type=ArtifactType.TDOC_LIST,
        working_group="RAN1",
        meeting="125",
        source_url="https://www.3gpp.org/list.xlsx",
        discovered_at=now,
        retrieved_at=now,
        local_path=tmp_path / "list.xlsx",
        checksum="A" * 64,
    )
    assert artifact.checksum == "a" * 64

    with pytest.raises(ValidationError):
        SourceArtifact(
            artifact_type=ArtifactType.TDOC_LIST,
            working_group="RAN1",
            meeting="125",
            source_url="https://www.3gpp.org/list.xlsx",
            discovered_at=now,
            retrieved_at=now,
        )


def test_v01_metadata_only_timestamp_migrates_to_discovery() -> None:
    now = datetime.now(UTC)
    artifact = SourceArtifact.model_validate(
        {
            "artifact_type": "tdoc_list",
            "working_group": "RAN2",
            "meeting": "131",
            "source_url": "https://www.3gpp.org/list.xlsx",
            "retrieved_at": now,
            "local_path": None,
            "checksum": None,
        }
    )
    assert artifact.discovered_at == now
    assert artifact.retrieved_at is None


def test_meeting_rejects_reversed_dates() -> None:
    with pytest.raises(ValidationError):
        Meeting(
            working_group="RAN1", meeting_number="124", start_date="2025-03-02",
            end_date="2025-03-01", source_url="https://www.3gpp.org/x"
        )
