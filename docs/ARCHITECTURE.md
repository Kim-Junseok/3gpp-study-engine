# Architecture

## Stable boundaries

V0.2a.3 preserves the accepted boundaries:

1. `threegpp.sources` owns public 3GPP URL construction and directory parsing.
2. `threegpp.models` defines stable Pydantic contracts, including `StudyRequest`.
3. `threegpp.ingest` performs explicit downloads, writes immutable raw files, deterministic portable normalized outputs, and append-only timestamped manifests.
4. `threegpp.normalize` classifies snapshot roles, derives role-specific views, and parses spreadsheet metadata.
5. `threegpp.db.MetadataRepository` owns schema migration, safe merge, persistence, and metadata filters.
6. `threegpp.study` produces metadata-only candidate inventories.
7. `skills/3gpp-study` orchestrates these interfaces but owns no research logic.

```text
User → 3GPP Study Skill → StudyRequest → Python core
                                      ├─ source
                                      ├─ ingest
                                      ├─ normalize
                                      ├─ persistence
                                      └─ retrieval/study

CLI = developer/debug interface
```

## Ingestion modes

`MeetingIngestor.ingest()` is discovery-only by default. `enrich_tdocs=True` downloads and parses every discovered official list while leaving agenda/report artifacts discovery-only. `download_artifacts=True` also retrieves those meeting-level artifacts. Neither mode downloads individual TDoc archives.

## Persistence responsibilities

```text
Official server
  ↓
Raw artifact                immutable official bytes
  ↓ parse
Normalized JSONL.gz         deterministic portable rows, checksum and count verified
  ├──→ DuckDB               local query/index store
  └──→ Manifest reference   provenance/index/receipt, not row storage
```

`data/normalized/<wg>/<meeting>/snapshots/` retains each parsed list independently; `current/` retains the canonical merged inventory. Content-addressed paths and deterministic gzip encoding make regeneration verifiable. The manifest stores descriptors and references, while DuckDB remains the operational query store.

The repository separates canonical current rows from snapshot rows. A `current_view_present` marker removes historical-only rows from ordinary queries without deleting prior metadata, while snapshot tables retain each list's complete values and provenance. Request-scoped snapshot reads query `tdoc_snapshot_records` directly and never import those records as current, alter flags, rewrite normalized current output, or rewrite a manifest.

## Repository boundary

Runtime research data are operational state, not source code. Raw downloads, normalized live datasets, timestamped live manifests, and the local DuckDB database remain on disk but are excluded from Git history. Small deterministic fixtures under `tests/fixtures/` remain version-controlled because the validation suite depends on them. Repository hygiene must never delete local research evidence merely to remove it from Git tracking.

## Extensibility

RAN1 and RAN2 share a directory adapter configured by group path, meeting prefix, and TDoc prefix. New working groups can implement `ThreeGPPSource` without changing ingestion, normalization, persistence, or study operations. Spreadsheet aliases are centralized and layout scanning is source-independent.

## Compatibility

On opening a V0.1–V0.2a.1 DuckDB file, the repository adds snapshot tables and marks existing normalized records current. V0.2a.1 manifests load with empty role data rather than fabricated roles. A new all-snapshot ingestion establishes canonical current while preserving earlier metadata and availability evidence.

V0.2a.2 embedded-row manifests remain readable. Migration is deliberately explicit: `threegpp migrate-manifest --manifest ...` writes deterministic snapshot/current JSONL.gz files and a new slim V0.2a.3 receipt without modifying the legacy receipt or downloading sources. A hydrated V0.2a.3 manifest can re-import its normalized rows into DuckDB.
