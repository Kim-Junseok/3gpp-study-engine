from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import duckdb

from threegpp.models import (
    FieldProvenance,
    Meeting,
    SourceArtifact,
    SpreadsheetParseSummary,
    TDocListSnapshot,
    TDocMetadata,
    TDocQuery,
    WorkingGroup,
    merge_tdoc_metadata,
    normalize_meeting_identifier,
)

from .schema import ensure_schema

if TYPE_CHECKING:
    from threegpp.ingest.manifest import MeetingManifest


_TDOC_COLUMNS = """
tdoc_id, working_group, meeting_number, title, source_organization_raw,
organizations_json, agenda_item, revision, status, document_type, document_category,
related_tdoc_ids_json, abstract, agenda_item_description, intended_for, release,
specification, related_work_item, directory_present, official_list_present,
source_url, local_path, metadata_source_kind, metadata_source_url,
metadata_source_checksum, field_provenance_json, raw_metadata_json,
current_view_present
"""


class MetadataRepository:
    def __init__(self, path: Path | str = Path("data/metadata.duckdb")) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = duckdb.connect(str(self.path))
        ensure_schema(self.connection)

    def close(self) -> None:
        self.connection.close()

    def upsert_document_receipt(self, receipt: object) -> None:
        from threegpp.documents.models import DocumentReceipt
        value = DocumentReceipt.model_validate(receipt)
        self.connection.execute(
            """INSERT OR REPLACE INTO tdoc_documents (
                tdoc_id, working_group, meeting_number, fetched, normalized,
                extraction_status, raw_path, normalized_path, raw_checksum,
                normalized_checksum, text_checksum, normalization_identity_json,
                normalized_schema_version, retention_state, receipt_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [value.tdoc_id, value.working_group.value, value.meeting, True,
             value.normalized_path is not None, value.extraction_status.value,
             str(value.raw.local_path), str(value.normalized_path) if value.normalized_path else None,
             value.raw.sha256, value.normalized_checksum, value.text_checksum,
             value.normalization_identity.model_dump_json() if value.normalization_identity else None,
             value.normalization_identity.normalized_schema_version if value.normalization_identity else None,
             value.raw.retention.value,
             value.model_dump_json()],
        )

    def get_document_receipt(self, tdoc_id: str, working_group: object = None, meeting: str | None = None):
        from threegpp.documents.models import DocumentReceipt
        clauses, values = ["upper(tdoc_id) = upper(?)"], [tdoc_id]
        if working_group is not None:
            clauses.append("working_group = ?")
            values.append(WorkingGroup.parse(working_group).value)
        if meeting is not None:
            clauses.append("meeting_number = ?")
            values.append(normalize_meeting_identifier(meeting))
        rows = self.connection.execute(
            "SELECT receipt_json FROM tdoc_documents WHERE " + " AND ".join(clauses), values
        ).fetchall()
        if not rows: return None
        if len(rows) > 1: raise ValueError("TDoc ID is ambiguous; provide working group and meeting")
        return DocumentReceipt.model_validate_json(rows[0][0])

    def __enter__(self) -> MetadataRepository:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def upsert_meeting(self, meeting: Meeting) -> None:
        self.connection.execute(
            """
            INSERT INTO meetings VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (working_group, meeting_number) DO UPDATE SET
                meeting_name = COALESCE(excluded.meeting_name, meetings.meeting_name),
                start_date = COALESCE(excluded.start_date, meetings.start_date),
                end_date = COALESCE(excluded.end_date, meetings.end_date),
                location = COALESCE(excluded.location, meetings.location),
                source_url = COALESCE(excluded.source_url, meetings.source_url)
            """,
            [
                meeting.working_group.value,
                meeting.meeting_number,
                meeting.meeting_name,
                meeting.start_date,
                meeting.end_date,
                meeting.location,
                str(meeting.source_url),
            ],
        )

    def upsert_artifact(self, artifact: SourceArtifact) -> None:
        existing = self.connection.execute(
            "SELECT checksum FROM artifacts WHERE source_url = ?", [str(artifact.source_url)]
        ).fetchone()
        if existing and existing[0] and artifact.checksum and existing[0] != artifact.checksum:
            raise ValueError(f"artifact checksum changed for {artifact.source_url}")
        self.connection.execute(
            """
            INSERT INTO artifacts (
                source_url, artifact_type, working_group, meeting_number, discovered_at,
                retrieved_at, original_filename, local_path, checksum
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (source_url) DO UPDATE SET
                artifact_type = excluded.artifact_type,
                working_group = excluded.working_group,
                meeting_number = excluded.meeting_number,
                discovered_at = LEAST(artifacts.discovered_at, excluded.discovered_at),
                retrieved_at = COALESCE(excluded.retrieved_at, artifacts.retrieved_at),
                original_filename = COALESCE(excluded.original_filename, artifacts.original_filename),
                local_path = COALESCE(excluded.local_path, artifacts.local_path),
                checksum = COALESCE(excluded.checksum, artifacts.checksum)
            """,
            [
                str(artifact.source_url),
                artifact.artifact_type.value,
                artifact.working_group.value,
                artifact.meeting,
                artifact.discovered_at,
                artifact.retrieved_at,
                artifact.original_filename,
                str(artifact.local_path) if artifact.local_path else None,
                artifact.checksum,
            ],
        )

    def upsert_tdoc(self, tdoc: TDocMetadata) -> TDocMetadata:
        existing = self._get_tdoc(tdoc.working_group, tdoc.meeting, tdoc.tdoc_id)
        merged = merge_tdoc_metadata(existing, tdoc) if existing else tdoc
        self.connection.execute(
            f"INSERT OR REPLACE INTO tdoc_metadata ({_TDOC_COLUMNS}) VALUES ({', '.join(['?'] * 28)})",
            _tdoc_values(merged),
        )
        return merged

    def upsert_tdoc_list_snapshot(self, snapshot: TDocListSnapshot) -> None:
        parse_summary = (
            snapshot.parse_summary.model_dump_json() if snapshot.parse_summary else None
        )
        self.connection.execute(
            """
            INSERT OR REPLACE INTO tdoc_list_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                str(snapshot.source_url),
                snapshot.working_group.value,
                snapshot.meeting,
                snapshot.filename,
                snapshot.checksum,
                json.dumps([role.value for role in snapshot.roles]),
                snapshot.snapshot_timestamp,
                snapshot.row_count,
                parse_summary,
                snapshot.parse_error,
            ],
        )
        self.connection.execute(
            "DELETE FROM tdoc_snapshot_records WHERE snapshot_url = ?",
            [str(snapshot.source_url)],
        )
        if snapshot.tdocs:
            self.connection.executemany(
                "INSERT INTO tdoc_snapshot_records VALUES (?, ?, ?)",
                [
                    [str(snapshot.source_url), item.tdoc_id, item.model_dump_json()]
                    for item in snapshot.tdocs
                ],
            )

    def import_manifest(self, manifest: MeetingManifest) -> None:
        self.connection.execute("BEGIN")
        try:
            self.upsert_meeting(manifest.meeting)
            for artifact in manifest.artifacts:
                self.upsert_artifact(artifact)
            if manifest.tdoc_list_snapshots:
                self.connection.execute(
                    "UPDATE tdoc_metadata SET current_view_present = FALSE "
                    "WHERE working_group = ? AND meeting_number = ?",
                    [manifest.meeting.working_group.value, manifest.meeting.meeting_number],
                )
                for snapshot in manifest.tdoc_list_snapshots:
                    self.upsert_tdoc_list_snapshot(snapshot)
            for tdoc in manifest.tdocs:
                self.upsert_tdoc(tdoc)
        except Exception:
            self.connection.execute("ROLLBACK")
            raise
        else:
            self.connection.execute("COMMIT")

    def get_meeting(self, working_group: WorkingGroup | str, meeting: str) -> Meeting | None:
        working_group = WorkingGroup.parse(working_group)
        meeting = normalize_meeting_identifier(meeting)
        row = self.connection.execute(
            """
            SELECT working_group, meeting_number, meeting_name, start_date, end_date, location, source_url
            FROM meetings WHERE working_group = ? AND meeting_number = ?
            """,
            [working_group.value, meeting],
        ).fetchone()
        if row is None:
            return None
        return Meeting(
            working_group=row[0], meeting_number=row[1], meeting_name=row[2], start_date=row[3],
            end_date=row[4], location=row[5], source_url=row[6]
        )

    def get_tdoc(
        self, working_group: WorkingGroup | str, meeting: str, tdoc_id: str
    ) -> TDocMetadata | None:
        return self._get_tdoc(working_group, meeting, tdoc_id, current_only=True)

    def _get_tdoc(
        self,
        working_group: WorkingGroup | str,
        meeting: str,
        tdoc_id: str,
        *,
        current_only: bool = False,
    ) -> TDocMetadata | None:
        current_clause = " AND current_view_present" if current_only else ""
        row = self.connection.execute(
            f"SELECT {_TDOC_COLUMNS} FROM tdoc_metadata "
            "WHERE working_group = ? AND meeting_number = ? AND upper(tdoc_id) = upper(?)"
            + current_clause,
            [WorkingGroup.parse(working_group).value, normalize_meeting_identifier(meeting), tdoc_id],
        ).fetchone()
        return _row_to_tdoc(row) if row else None

    def list_tdoc_list_snapshots(
        self,
        working_group: WorkingGroup | str,
        meeting: str,
        *,
        include_records: bool = True,
    ) -> list[TDocListSnapshot]:
        group = WorkingGroup.parse(working_group)
        meeting = normalize_meeting_identifier(meeting)
        rows = self.connection.execute(
            """
            SELECT source_url, working_group, meeting_number, filename, checksum,
                   roles_json, snapshot_timestamp, row_count, parse_summary_json, parse_error
            FROM tdoc_list_snapshots
            WHERE working_group = ? AND meeting_number = ?
            ORDER BY snapshot_timestamp NULLS LAST, source_url
            """,
            [group.value, meeting],
        ).fetchall()
        return [
            TDocListSnapshot(
                source_url=row[0],
                working_group=row[1],
                meeting=row[2],
                filename=row[3],
                checksum=row[4],
                roles=json.loads(row[5]),
                snapshot_timestamp=row[6],
                row_count=row[7],
                parse_summary=(
                    SpreadsheetParseSummary.model_validate_json(row[8]) if row[8] else None
                ),
                parse_error=row[9],
                tdocs=self.list_snapshot_tdocs(row[0]) if include_records else [],
            )
            for row in rows
        ]

    def get_tdoc_list_snapshot(self, snapshot_url: str) -> TDocListSnapshot | None:
        row = self.connection.execute(
            "SELECT working_group, meeting_number FROM tdoc_list_snapshots WHERE source_url = ?",
            [snapshot_url],
        ).fetchone()
        if row is None:
            return None
        return next(
            (
                item
                for item in self.list_tdoc_list_snapshots(row[0], row[1])
                if str(item.source_url) == snapshot_url
            ),
            None,
        )

    def get_snapshot_for_role(
        self,
        working_group: WorkingGroup | str,
        meeting: str,
        role: object,
    ) -> TDocListSnapshot | None:
        from threegpp.models import SnapshotRole

        wanted = SnapshotRole(role)
        snapshots = self.list_tdoc_list_snapshots(working_group, meeting)
        matching = [item for item in snapshots if wanted in item.roles]
        return max(
            matching,
            key=lambda item: (
                item.snapshot_timestamp.isoformat() if item.snapshot_timestamp else "",
                str(item.source_url),
            ),
            default=None,
        )

    def list_snapshot_tdocs(self, snapshot_url: str) -> list[TDocMetadata]:
        rows = self.connection.execute(
            "SELECT tdoc_json FROM tdoc_snapshot_records "
            "WHERE snapshot_url = ? ORDER BY tdoc_id",
            [snapshot_url],
        ).fetchall()
        return [TDocMetadata.model_validate_json(row[0]) for row in rows]

    def list_tdocs(self, working_group: WorkingGroup | str, meeting: str) -> list[TDocMetadata]:
        return self.query_tdocs(
            TDocQuery(
                working_groups=[WorkingGroup.parse(working_group)],
                meetings={WorkingGroup.parse(working_group): [meeting]},
            )
        )

    def query_tdocs(self, query: TDocQuery) -> list[TDocMetadata]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if query.working_groups:
            placeholders = ", ".join("?" for _ in query.working_groups)
            clauses.append(f"working_group IN ({placeholders})")
            parameters.extend(item.value for item in query.working_groups)
        if query.meetings:
            meeting_clauses: list[str] = []
            for group, meetings in query.meetings.items():
                placeholders = ", ".join("?" for _ in meetings)
                meeting_clauses.append(
                    f"(working_group = ? AND meeting_number IN ({placeholders}))"
                )
                parameters.append(group.value)
                parameters.extend(meetings)
            clauses.append("(" + " OR ".join(meeting_clauses) + ")")
        if query.tdoc_id:
            clauses.append("upper(tdoc_id) = upper(?)")
            parameters.append(query.tdoc_id)
        if query.title_contains:
            clauses.append("title ILIKE ?")
            parameters.append(f"%{query.title_contains}%")
        if query.agenda_item:
            clauses.append("agenda_item ILIKE ?")
            parameters.append(query.agenda_item)
        if query.status:
            clauses.append("status ILIKE ?")
            parameters.append(query.status)
        sql = f"SELECT {_TDOC_COLUMNS} FROM tdoc_metadata"
        clauses.append("current_view_present")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY working_group, meeting_number, tdoc_id"
        records = [_row_to_tdoc(row) for row in self.connection.execute(sql, parameters).fetchall()]
        if query.organization:
            wanted = query.organization.casefold()
            records = [
                record
                for record in records
                if any(organization.casefold() == wanted for organization in record.organizations)
            ]
        return records


def _tdoc_values(tdoc: TDocMetadata) -> list[Any]:
    provenance = {
        field: value.model_dump(mode="json") for field, value in tdoc.field_provenance.items()
    }
    return [
        tdoc.tdoc_id,
        tdoc.working_group.value,
        tdoc.meeting,
        tdoc.title,
        tdoc.source_organization_raw,
        json.dumps(tdoc.organizations, ensure_ascii=False),
        tdoc.agenda_item,
        tdoc.revision,
        tdoc.status,
        tdoc.document_type,
        tdoc.document_category,
        json.dumps(tdoc.related_tdoc_ids, ensure_ascii=False),
        tdoc.abstract,
        tdoc.agenda_item_description,
        tdoc.intended_for,
        tdoc.release,
        tdoc.specification,
        tdoc.related_work_item,
        tdoc.directory_present,
        tdoc.official_list_present,
        str(tdoc.source_url) if tdoc.source_url else None,
        str(tdoc.local_path) if tdoc.local_path else None,
        tdoc.metadata_source_kind.value,
        str(tdoc.metadata_source_url) if tdoc.metadata_source_url else None,
        tdoc.metadata_source_checksum,
        json.dumps(provenance, ensure_ascii=False),
        json.dumps(tdoc.raw_metadata, ensure_ascii=False),
        True,
    ]


def _row_to_tdoc(row: tuple[Any, ...]) -> TDocMetadata:
    return TDocMetadata(
        tdoc_id=row[0],
        working_group=row[1],
        meeting=row[2],
        title=row[3],
        source_organization_raw=row[4],
        organizations=json.loads(row[5] or "[]"),
        agenda_item=row[6],
        revision=row[7],
        status=row[8],
        document_type=row[9],
        document_category=row[10],
        related_tdoc_ids=json.loads(row[11] or "[]"),
        abstract=row[12],
        agenda_item_description=row[13],
        intended_for=row[14],
        release=row[15],
        specification=row[16],
        related_work_item=row[17],
        directory_present=bool(row[18]),
        official_list_present=bool(row[19]),
        source_url=row[20],
        local_path=row[21],
        metadata_source_kind=row[22] or "directory",
        metadata_source_url=row[23],
        metadata_source_checksum=row[24],
        field_provenance={
            field: FieldProvenance.model_validate(value)
            for field, value in json.loads(row[25] or "{}").items()
        },
        raw_metadata=json.loads(row[26] or "{}"),
    )
