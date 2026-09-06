# Data model

## Provenance layers

1. Directory discovery: TDoc identity and archive URL.
2. Official TDoc list: title, exact source-organization text, agenda item/description, abstract, purpose, status, type/category, release/specification, revision, related TDocs, and related work item.
3. Actual TDoc content/header: reserved for later work.
4. Analytical inference: reserved and always separate from authoritative metadata.

V0.2a.3 implements Layers 1 and 2 only. `TDocMetadata.metadata_source_*` records the list supplying the normalized value, and `field_provenance` identifies its URL, checksum, and source column. `raw_metadata` retains every non-empty spreadsheet cell.

## Records

- `Meeting`: working group, normalized meeting identifier/name, nullable dates/location, source URL.
- `SourceArtifact`: type, meeting identity, source URL, `discovered_at`, optional download triple (`retrieved_at`, `local_path`, `checksum`), and original filename.
- `TDocMetadata`: identity, nullable canonical fields, `source_organization_raw`, conservative organization list, document relationships, record/field provenance, raw row metadata, and explicit directory/list presence flags. Its derived availability is `downloadable` only with directory URL evidence, `listed_only` with official-list evidence but no directory URL, otherwise `unknown`.
- `SpreadsheetParseSummary`: chosen sheet/header, mapped/unmapped/duplicate counts, mapped columns, unknown columns, and warnings.
- `NormalizedOutput`: portable path, normalized row count, compressed-file SHA-256, and `jsonl+gzip` format.
- `TDocListSnapshot`: source URL, checksum, filename, inferred roles, filename timestamp when parseable, row count, parse summary/error, and a normalized-output reference. Runtime hydration may attach complete per-snapshot records, but they are excluded from manifest serialization.
- `MeetingManifest`: one slim timestamped ingestion receipt containing discovered artifacts, snapshot descriptors, canonical/request-selected view provenance, normalized-output references, and migration notes. Runtime current rows are excluded from serialization.
- `StudyRequest`: stable user request shared by Python, CLI, Skill, and future applications.
- `TDocQuery` and `CandidateInventory`: deterministic metadata retrieval contracts. Each candidate carries match level, matched field/token evidence, and availability; inventory counts summarize match levels, availability, and snapshot coverage.

DuckDB keeps the canonical current view in `tdoc_metadata`, snapshot metadata in `tdoc_list_snapshots`, and the uncollapsed TDoc values for each source list in `tdoc_snapshot_records`. This permits future first-appearance and status/title/source change comparisons without treating them as current facts now. Portable JSONL.gz is the rebuild/interchange representation; DuckDB is the query index; neither changes the authority of raw official bytes.

## Safe merge policy

Identity is `(working_group, meeting, tdoc_id)`. Null or empty incoming fields never erase known values. Higher provenance layers may replace lower-layer values. Within Layer 2, the selected current snapshot's non-null values win; other official snapshots only fill missing fields for TDocs belonging to the directory/current inventory. Historical-only TDocs remain in snapshot storage rather than entering the default candidate view. Field provenance moves with its value. Artifact discovery never clears retrieval provenance.

The V0.2a organization/availability migration remains in place. V0.2a.1 manifests load with empty snapshot-role data. Existing normalized rows remain current until an all-snapshot ingestion establishes a newer canonical view; old artifacts are not assigned roles without new classification evidence. V0.2a.2 embedded rows can be explicitly externalized without fabricating absent values or snapshot roles.

## Reserved semantic distinctions

Company proposal, company observation, discussion, meeting agreement, meeting conclusion, and FFS/unresolved issue remain separate future evidence entities. “Samsung proposed X” must never become “RAN1 agreed X” without separate meeting-agreement evidence.
# V0.2b document models

`TDocFetchPlan` contains exact identities, official URLs when known, availability, per-item selection reasons, and retention state. `RawArtifact` records URL, path, retrieval time, media type, byte count, and SHA-256. A package has zero or more `PackageMember` records; a probable primary is assigned only when exactly one supported member exists.

`NormalizedTDoc` contains member parser/status information, warnings, deterministic blocks, flattened text, and source linkage. Blocks are numbered globally in package order as `b000001`, `b000002`, and so on and retain member, page, heading path, sheet, and table/row context. `NormalizationIdentity` combines the raw SHA-256, each member's parser name/version, and the normalized-document schema version; cache reuse requires exact equality. `DocumentReceipt` contains that identity plus paths, independent block/text checksums, counts, parser versions, retention, and warnings—not body text. DuckDB indexes the receipt status, checksums, identity/schema, retention, and derived-output path while body content remains in portable files.
