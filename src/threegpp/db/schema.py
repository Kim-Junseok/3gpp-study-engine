from __future__ import annotations

import duckdb


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meetings (
    working_group VARCHAR NOT NULL,
    meeting_number VARCHAR NOT NULL,
    meeting_name VARCHAR,
    start_date DATE,
    end_date DATE,
    location VARCHAR,
    source_url VARCHAR NOT NULL,
    PRIMARY KEY (working_group, meeting_number)
);

CREATE TABLE IF NOT EXISTS artifacts (
    source_url VARCHAR PRIMARY KEY,
    artifact_type VARCHAR NOT NULL,
    working_group VARCHAR NOT NULL,
    meeting_number VARCHAR NOT NULL,
    discovered_at TIMESTAMPTZ NOT NULL,
    retrieved_at TIMESTAMPTZ,
    original_filename VARCHAR,
    local_path VARCHAR,
    checksum VARCHAR
);

CREATE TABLE IF NOT EXISTS tdoc_metadata (
    tdoc_id VARCHAR NOT NULL,
    working_group VARCHAR NOT NULL,
    meeting_number VARCHAR NOT NULL,
    title VARCHAR,
    source_organization_raw VARCHAR,
    organizations_json VARCHAR,
    agenda_item VARCHAR,
    revision VARCHAR,
    status VARCHAR,
    document_type VARCHAR,
    document_category VARCHAR,
    related_tdoc_ids_json VARCHAR,
    abstract VARCHAR,
    agenda_item_description VARCHAR,
    intended_for VARCHAR,
    release VARCHAR,
    specification VARCHAR,
    related_work_item VARCHAR,
    directory_present BOOLEAN NOT NULL DEFAULT FALSE,
    official_list_present BOOLEAN NOT NULL DEFAULT FALSE,
    source_url VARCHAR,
    local_path VARCHAR,
    metadata_source_kind VARCHAR,
    metadata_source_url VARCHAR,
    metadata_source_checksum VARCHAR,
    field_provenance_json VARCHAR,
    raw_metadata_json VARCHAR,
    current_view_present BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (tdoc_id, working_group, meeting_number)
);

CREATE TABLE IF NOT EXISTS tdoc_list_snapshots (
    source_url VARCHAR PRIMARY KEY,
    working_group VARCHAR NOT NULL,
    meeting_number VARCHAR NOT NULL,
    filename VARCHAR,
    checksum VARCHAR,
    roles_json VARCHAR NOT NULL,
    snapshot_timestamp TIMESTAMP,
    row_count INTEGER,
    parse_summary_json VARCHAR,
    parse_error VARCHAR
);

CREATE TABLE IF NOT EXISTS tdoc_snapshot_records (
    snapshot_url VARCHAR NOT NULL,
    tdoc_id VARCHAR NOT NULL,
    tdoc_json VARCHAR NOT NULL,
    PRIMARY KEY (snapshot_url, tdoc_id)
);
"""


def ensure_schema(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(SCHEMA_SQL)
    artifact_columns = _columns(connection, "artifacts")
    if "discovered_at" not in artifact_columns:
        connection.execute("ALTER TABLE artifacts ADD COLUMN discovered_at TIMESTAMPTZ")
        connection.execute("UPDATE artifacts SET discovered_at = retrieved_at")
    connection.execute("ALTER TABLE artifacts ALTER COLUMN retrieved_at DROP NOT NULL")
    connection.execute(
        "UPDATE artifacts SET retrieved_at = NULL "
        "WHERE local_path IS NULL OR checksum IS NULL"
    )

    tdoc_columns = _columns(connection, "tdoc_metadata")
    additions = {
        "source_organization_raw": "VARCHAR",
        "organizations_json": "VARCHAR",
        "document_type": "VARCHAR",
        "document_category": "VARCHAR",
        "related_tdoc_ids_json": "VARCHAR",
        "abstract": "VARCHAR",
        "agenda_item_description": "VARCHAR",
        "intended_for": "VARCHAR",
        "release": "VARCHAR",
        "specification": "VARCHAR",
        "related_work_item": "VARCHAR",
        "directory_present": "BOOLEAN",
        "official_list_present": "BOOLEAN",
        "metadata_source_kind": "VARCHAR",
        "metadata_source_url": "VARCHAR",
        "metadata_source_checksum": "VARCHAR",
        "field_provenance_json": "VARCHAR",
        "raw_metadata_json": "VARCHAR",
        "current_view_present": "BOOLEAN DEFAULT TRUE",
    }
    for name, sql_type in additions.items():
        if name not in tdoc_columns:
            connection.execute(f"ALTER TABLE tdoc_metadata ADD COLUMN {name} {sql_type}")
    tdoc_columns = _columns(connection, "tdoc_metadata")
    if "source_organization" in tdoc_columns:
        connection.execute(
            "UPDATE tdoc_metadata SET source_organization_raw = source_organization "
            "WHERE source_organization_raw IS NULL"
        )
    connection.execute(
        "UPDATE tdoc_metadata SET directory_present = (source_url IS NOT NULL) "
        "WHERE directory_present IS NULL"
    )
    connection.execute(
        "UPDATE tdoc_metadata SET official_list_present = "
        "(metadata_source_kind = 'tdoc_list' OR metadata_source_url IS NOT NULL) "
        "WHERE official_list_present IS NULL"
    )
    connection.execute(
        "UPDATE tdoc_metadata SET current_view_present = TRUE "
        "WHERE current_view_present IS NULL"
    )
    connection.execute("ALTER TABLE tdoc_metadata ALTER COLUMN source_url DROP NOT NULL")
    connection.execute(
        "UPDATE tdoc_metadata SET metadata_source_kind = 'directory' "
        "WHERE metadata_source_kind IS NULL"
    )


def _columns(connection: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info('{table}')").fetchall()}
