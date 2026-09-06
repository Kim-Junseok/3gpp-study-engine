from datetime import UTC, datetime

import pytest

from threegpp.models import SnapshotRole, SourceArtifact
from threegpp.normalize import (
    classify_tdoc_list_snapshot,
    infer_snapshot_timestamp,
    select_snapshot_views,
)


def artifact(filename: str) -> SourceArtifact:
    return SourceArtifact(
        artifact_type="tdoc_list",
        working_group="RAN2",
        meeting="131",
        source_url=f"https://www.3gpp.org/{filename}",
        discovered_at=datetime(2025, 9, 4, tzinfo=UTC),
        original_filename=filename,
    )


def test_snapshot_roles_keep_meeting_close_and_current_views_distinct() -> None:
    snapshots = [
        artifact("tdocList_2025-09-02_14h28.xlsx"),
        artifact("TDoc_List_Meeting_RAN2#131.xlsx"),
        artifact("tdocList_2025-09-03_10h00_eom.xlsx"),
    ]

    views = select_snapshot_views(snapshots)

    assert views.current.artifact.original_filename == "TDoc_List_Meeting_RAN2#131.xlsx"
    assert "current consolidated" in views.current.reason
    assert views.meeting_close is not None
    assert views.meeting_close.artifact.original_filename == "tdocList_2025-09-03_10h00_eom.xlsx"
    assert [classify_tdoc_list_snapshot(item) for item in snapshots] == [
        SnapshotRole.HISTORICAL,
        SnapshotRole.CURRENT_CONSOLIDATED,
        SnapshotRole.MEETING_CLOSE,
    ]
    assert infer_snapshot_timestamp(snapshots[0]) == datetime(2025, 9, 2, 14, 28)
    assert len(views.roles_by_url) == 3


def test_explicit_snapshot_selection_is_request_scoped() -> None:
    snapshots = [artifact("tdocList_2025-09-02_14h28.xlsx"), artifact("final_eom.xlsx")]
    explicit_url = str(snapshots[0].source_url)

    views = select_snapshot_views(snapshots, explicit_url=explicit_url)

    assert views.current.artifact == snapshots[1]
    assert views.request_selected is not None
    assert views.request_selected.artifact == snapshots[0]
    assert "canonical current unchanged" in views.request_selected.reason
    assert views.roles_by_url[explicit_url] == [SnapshotRole.HISTORICAL]
    assert views.meeting_close is not None
    assert views.meeting_close.artifact == snapshots[1]

    with pytest.raises(ValueError):
        select_snapshot_views(snapshots, explicit_url="https://www.3gpp.org/missing.xlsx")
