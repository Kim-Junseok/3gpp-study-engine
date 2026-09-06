import hashlib
import json
from datetime import UTC, datetime

from threegpp.db import MetadataRepository
from threegpp.ingest import ManifestStore, MeetingManifest, NormalizedStore
from threegpp.models import (
    ArtifactType,
    FieldProvenance,
    Meeting,
    MetadataLayer,
    SnapshotRole,
    SourceArtifact,
    TDocAvailability,
    TDocMetadata,
)


def sample_manifest() -> MeetingManifest:
    meeting = Meeting(
        working_group="RAN2", meeting_number="131", meeting_name="RAN2#131",
        source_url="https://www.3gpp.org/ftp/tsg_ran/WG2_RL2/TSGR2_131/"
    )
    return MeetingManifest(
        meeting=meeting,
        created_at=datetime(2025, 8, 15, tzinfo=UTC),
        artifacts=[
            SourceArtifact(
                artifact_type=ArtifactType.TDOC_LIST, working_group="RAN2", meeting="131",
                source_url="https://www.3gpp.org/list.xlsx",
                discovered_at=datetime(2025, 8, 15, tzinfo=UTC), original_filename="list.xlsx"
            )
        ],
        tdocs=[
            TDocMetadata(
                tdoc_id="R2-2505001", working_group="RAN2", meeting="131",
                source_url="https://www.3gpp.org/R2-2505001.zip"
            )
        ],
    )


def test_manifest_round_trip(tmp_path) -> None:
    manifest = sample_manifest()
    output = NormalizedStore(tmp_path / "normalized").write_current(
        manifest.meeting.working_group, manifest.meeting.meeting_number, manifest.tdocs
    )
    manifest = manifest.model_copy(update={"current_output": output})
    store = ManifestStore(tmp_path / "manifests")
    path = store.write(manifest)
    restored = store.read(path)
    assert restored == manifest
    text = path.read_text()
    assert '"schema_version": "0.2a.3"' in text
    assert '"tdocs":' not in text
    assert '"current_output"' in text


def test_v02a_manifest_organization_field_is_read_compatibly(tmp_path) -> None:
    payload = sample_manifest().model_dump(mode="json")
    payload["schema_version"] = "0.2a"
    payload["tdocs"] = [item.model_dump(mode="json") for item in sample_manifest().tdocs]
    tdoc = payload["tdocs"][0]
    tdoc["source_organization"] = "Standards and Testing Institute"
    tdoc.pop("source_organization_raw", None)
    path = tmp_path / "v02a.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    restored = ManifestStore.read(path)

    assert restored.schema_version == "0.2a"
    assert restored.tdocs[0].source_organization_raw == "Standards and Testing Institute"


def test_v02a1_manifest_remains_usable_without_invented_snapshot_roles(tmp_path) -> None:
    payload = sample_manifest().model_dump(mode="json")
    payload["schema_version"] = "0.2a.1"
    payload["preferred_tdoc_list_url"] = "https://www.3gpp.org/legacy-list.xlsx"
    payload["preferred_tdoc_list_reason"] = "legacy single ordering"
    path = tmp_path / "v02a1.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    restored = ManifestStore.read(path)

    assert restored.schema_version == "0.2a.1"
    assert restored.tdoc_list_snapshots == []
    assert restored.current_snapshot_url is None


def test_v02a2_manifest_migration_externalizes_rows_without_touching_raw(tmp_path) -> None:
    rows = [
        TDocMetadata(
            tdoc_id=f"R2-25{index:05d}", working_group="RAN2", meeting="131",
            title=f"Legacy normalized title {index}", official_list_present=True,
            metadata_source_kind="tdoc_list",
            metadata_source_url="https://www.3gpp.org/list.xlsx",
            metadata_source_checksum="a" * 64,
        )
        for index in range(80)
    ]
    payload = sample_manifest().model_dump(mode="json")
    payload.update(
        schema_version="0.2a.2",
        tdocs=[item.model_dump(mode="json") for item in rows],
        tdoc_list_snapshots=[
            {
                "source_url": "https://www.3gpp.org/list.xlsx",
                "working_group": "RAN2",
                "meeting": "131",
                "filename": "TDoc_List_Meeting_RAN2#131.xlsx",
                "checksum": "a" * 64,
                "roles": [SnapshotRole.CURRENT_CONSOLIDATED.value],
                "row_count": len(rows),
                "tdocs": [item.model_dump(mode="json") for item in rows],
            }
        ],
    )
    manifest_root = tmp_path / "data" / "manifests"
    manifest_root.mkdir(parents=True)
    legacy_path = manifest_root / "ran2-131-v02a2.json"
    legacy_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    legacy_bytes = legacy_path.read_bytes()
    raw_path = tmp_path / "data" / "raw" / "list.xlsx"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_bytes(b"immutable official bytes")
    raw_checksum = hashlib.sha256(raw_path.read_bytes()).hexdigest()

    migrated, migrated_path = ManifestStore(manifest_root).migrate(legacy_path)
    hydrated = ManifestStore.read(migrated_path)

    assert legacy_path.read_bytes() == legacy_bytes
    assert hashlib.sha256(raw_path.read_bytes()).hexdigest() == raw_checksum
    assert migrated.schema_version == "0.2a.3"
    assert migrated.current_output is not None
    assert migrated.tdoc_list_snapshots[0].normalized_output is not None
    assert len(hydrated.tdocs) == 80
    assert len(hydrated.tdoc_list_snapshots[0].tdocs) == 80
    assert '"tdocs":' not in migrated_path.read_text()
    assert migrated_path.stat().st_size < legacy_path.stat().st_size


def test_duckdb_insert_read_and_manifest_rebuild(tmp_path) -> None:
    manifest = sample_manifest()
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        repository.import_manifest(manifest)
        repository.import_manifest(manifest)
        meeting = repository.get_meeting("ran2", "131")
        tdocs = repository.list_tdocs("RAN2", "131")

    assert meeting == manifest.meeting
    assert tdocs == manifest.tdocs


def test_null_directory_record_does_not_erase_enriched_metadata(tmp_path) -> None:
    enriched = TDocMetadata(
        tdoc_id="R2-2600001",
        working_group="RAN2",
        meeting="133",
        title="Known title",
        abstract="Known abstract",
        source_organization="Nokia",
        organizations=["Nokia"],
        source_url="https://www.3gpp.org/R2-2600001.zip",
        metadata_source_kind="tdoc_list",
        metadata_source_url="https://www.3gpp.org/list.xlsx",
        metadata_source_checksum="a" * 64,
        field_provenance={
            "title": FieldProvenance(
                layer=MetadataLayer.TDOC_LIST,
                source_url="https://www.3gpp.org/list.xlsx",
                source_checksum="a" * 64,
                source_column="Title",
            ),
            "abstract": FieldProvenance(
                layer=MetadataLayer.TDOC_LIST,
                source_url="https://www.3gpp.org/list.xlsx",
                source_checksum="a" * 64,
                source_column="Abstract",
            ),
        },
    )
    directory_only = TDocMetadata(
        tdoc_id="R2-2600001",
        working_group="RAN2",
        meeting="133",
        source_url="https://www.3gpp.org/R2-2600001.zip",
    )
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        repository.upsert_tdoc(enriched)
        repository.upsert_tdoc(directory_only)
        stored = repository.get_tdoc("RAN2", "133", "R2-2600001")

    assert stored is not None
    assert stored.title == "Known title"
    assert stored.abstract == "Known abstract"
    assert stored.organizations == ["Nokia"]
    assert stored.field_provenance["title"].source_column == "Title"
    assert stored.field_provenance["abstract"].source_column == "Abstract"


def test_v01_database_migration_separates_discovery_from_retrieval(tmp_path) -> None:
    import duckdb

    path = tmp_path / "v01.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute(
        """
        CREATE TABLE artifacts (
            source_url VARCHAR PRIMARY KEY, artifact_type VARCHAR NOT NULL,
            working_group VARCHAR NOT NULL, meeting_number VARCHAR NOT NULL,
            retrieved_at TIMESTAMPTZ NOT NULL, original_filename VARCHAR,
            local_path VARCHAR, checksum VARCHAR
        )
        """
    )
    connection.execute(
        "INSERT INTO artifacts VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            "https://www.3gpp.org/list.xlsx", "tdoc_list", "RAN2", "131",
            datetime(2025, 8, 15, tzinfo=UTC), "list.xlsx", None, None,
        ],
    )
    connection.close()

    with MetadataRepository(path) as repository:
        row = repository.connection.execute(
            "SELECT discovered_at, retrieved_at FROM artifacts"
        ).fetchone()

    assert row[0] == datetime(2025, 8, 15, tzinfo=UTC)
    assert row[1] is None


def test_v02a_database_migrates_raw_organization_and_evidence_flags(tmp_path) -> None:
    import duckdb

    path = tmp_path / "v02a.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute(
        """
        CREATE TABLE tdoc_metadata (
            tdoc_id VARCHAR NOT NULL, working_group VARCHAR NOT NULL,
            meeting_number VARCHAR NOT NULL, title VARCHAR,
            source_organization VARCHAR, organizations_json VARCHAR,
            agenda_item VARCHAR, revision VARCHAR, status VARCHAR,
            document_type VARCHAR, document_category VARCHAR,
            related_tdoc_ids_json VARCHAR, source_url VARCHAR NOT NULL,
            local_path VARCHAR, metadata_source_kind VARCHAR,
            metadata_source_url VARCHAR, metadata_source_checksum VARCHAR,
            field_provenance_json VARCHAR, raw_metadata_json VARCHAR,
            PRIMARY KEY (tdoc_id, working_group, meeting_number)
        )
        """
    )
    connection.execute(
        "INSERT INTO tdoc_metadata VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            "R2-2506001", "RAN2", "131", "Known title", "Research and Standards Lab",
            '["Research and Standards Lab"]', None, None, None, None, None, "[]",
            "https://www.3gpp.org/R2-2506001.zip", None, "tdoc_list",
            "https://www.3gpp.org/list.xlsx", "a" * 64, "{}", "{}",
        ],
    )
    connection.close()

    with MetadataRepository(path) as repository:
        restored = repository.get_tdoc("RAN2", "131", "R2-2506001")
        snapshots = repository.list_tdoc_list_snapshots("RAN2", "131")

    assert restored is not None
    assert restored.source_organization_raw == "Research and Standards Lab"
    assert restored.organizations == ["Research and Standards Lab"]
    assert restored.directory_present is True
    assert restored.official_list_present is True
    assert restored.availability is TDocAvailability.DOWNLOADABLE
    assert snapshots == []


def test_availability_states_persist_and_enrich_without_metadata_loss(tmp_path) -> None:
    listed_only = TDocMetadata(
        tdoc_id="R2-2602001",
        working_group="RAN2",
        meeting="133",
        title="Withdrawn uplink proposal",
        status="withdrawn",
        official_list_present=True,
        metadata_source_kind="tdoc_list",
        metadata_source_url="https://www.3gpp.org/list.xlsx",
    )
    directory_only = TDocMetadata(
        tdoc_id="R2-2602002",
        working_group="RAN2",
        meeting="133",
        source_url="https://www.3gpp.org/R2-2602002.zip",
        directory_present=True,
    )
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        repository.upsert_tdoc(listed_only)
        repository.upsert_tdoc(directory_only)
        before = repository.get_tdoc("RAN2", "133", "R2-2602001")
        repository.upsert_tdoc(
            TDocMetadata(
                tdoc_id="R2-2602001",
                working_group="RAN2",
                meeting="133",
                source_url="https://www.3gpp.org/R2-2602001.zip",
                directory_present=True,
            )
        )
        after = repository.get_tdoc("RAN2", "133", "R2-2602001")
        stored_directory = repository.get_tdoc("RAN2", "133", "R2-2602002")

    assert before is not None and before.availability is TDocAvailability.LISTED_ONLY
    assert before.source_url is None
    assert after is not None and after.availability is TDocAvailability.DOWNLOADABLE
    assert after.title == "Withdrawn uplink proposal"
    assert after.status == "withdrawn"
    assert after.official_list_present is True
    assert stored_directory is not None
    assert stored_directory.availability is TDocAvailability.DOWNLOADABLE
    assert stored_directory.official_list_present is False
