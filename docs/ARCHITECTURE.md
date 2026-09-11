# Architecture

## V0.7 historical range layer

```text
explicit meeting range
 -> V0.6 per-meeting Chair Note coverage
 -> canonical-current + stored official snapshot metadata resolver
 -> HistoricalTopicCoverage
 -> HistoricalCorpusExpansionPlan
 -> existing TDocFetchPlan
```

`threegpp.historical` is offline. Its versioned meeting adapter maps `b` to `bis` only as identifier normalization and preserves raw notation. The source adapter resolves normalized requests through the advertised official directory list, so a `124bis` request can retain the literal `TSGR1_124b` URL. Numeric suffix ordering gives `124 < 124bis < 125`; explicit ranges have a configurable meeting-count bound and insert only locally known suffixed meetings.

The resolver reads canonical-current records before stored official list snapshots. A current exact record wins over a historical duplicate. Incompatible candidates at the same precedence tier yield `AMBIGUOUS` with every candidate. Snapshot candidates retain URL, checksum, role, timestamp, and exact metadata; canonical-current state is unchanged.

Missing Chair Notes, unnormalized snapshots, and ambiguous selection are isolated to one meeting. Completeness describes selected source coverage only. Corpus planning deduplicates resolved bodies while retaining cross-meeting discussion edges and can compile a batch to `TDocFetchPlan`. It never executes acquisition, indexing, or semantic extraction. V0.8 proposition linkage and technical synthesis are outside this layer.

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

## V0.2b document boundary

`TDocFetchPlan` is the explicit safety boundary between metadata candidates and network retrieval. `DocumentService` validates availability, stores official bytes immutably, inspects packages without filesystem extraction, delegates formats to `DocumentParser`, writes portable gzip outputs, and indexes only receipts in DuckDB. Large text and block records never enter meeting manifests or DuckDB. Cache reuse requires exact raw-checksum, per-member parser, and normalized-schema identity plus valid checksums for both derived outputs. Parser or schema changes may rebuild derived output without changing raw evidence.

## Extensibility

RAN1 and RAN2 share a directory adapter configured by group path, meeting prefix, and TDoc prefix. New working groups can implement `ThreeGPPSource` without changing ingestion, normalization, persistence, or study operations. Spreadsheet aliases are centralized and layout scanning is source-independent.

## Compatibility

On opening a V0.1–V0.2a.1 DuckDB file, the repository adds snapshot tables and marks existing normalized records current. V0.2a.1 manifests load with empty role data rather than fabricated roles. A new all-snapshot ingestion establishes canonical current while preserving earlier metadata and availability evidence.

V0.2a.2 embedded-row manifests remain readable. Migration is deliberately explicit: `threegpp migrate-manifest --manifest ...` writes deterministic snapshot/current JSONL.gz files and a new slim V0.2a.3 receipt without modifying the legacy receipt or downloading sources. A hydrated V0.2a.3 manifest can re-import its normalized rows into DuckDB.

## V0.3 search boundary

```text
Normalized TDocs → block lexical index → EvidenceSearchQuery
                 → EvidenceSearchHit → EvidenceRef → exact normalized block
```

`threegpp.search` owns the disposable `search_blocks`, `search_postings`, and
`search_index_state` DuckDB tables. Complete body text remains in normalized
files. Matching normalization identity and schema/tokenizer versions reuse an
index; changed identity replaces only that TDoc. Missing or checksum-conflicting
evidence evicts postings and becomes stale. Ranking is block BM25 (`k1=1.2`,
`b=0.75`, positive probabilistic IDF), plus explicit phrase, heading, and title
bonuses. Metadata can boost only a block with body query evidence. All operations
are offline and cause zero TDoc downloads.

## V0.4 explicit semantic evidence boundary

```text
Official raw evidence → normalized blocks → EvidenceRef → SemanticEvidence
```

`threegpp.evidence` scans one checksum-verified normalized document at a time.
Centralized, versioned rules recognize explicit labels, bounded heading sections,
table labels, and narrow sentence cues. Deterministic document-role classification
gates authority: contributions may yield contribution proposals, observations,
conclusions, and FFS; accepted meeting reports may yield meeting agreements,
conclusions, decisions, and FFS. Agenda, chair, and unknown roles yield none.

Portable evidence JSONL.gz is derived and rebuildable. DuckDB stores its receipt,
query columns, short literal statements, and evidence JSON—not complete source
documents. Queries validate metadata identity, normalization identity/checksum,
rule/schema versions, derived checksum, and every referenced block/span. Invalid
sets become stale and cannot return evidence. Extraction and querying are offline.
The semantic evidence schema is version `1`; the centralized extraction ruleset
is `explicit-structural-v2`, with stable individual rule IDs at version `1`.
Meeting-record authority is member-scoped: normalized document/PDF members may
emit meeting evidence, while bundled participant and TDoc-list spreadsheets remain
searchable normalized data but cannot inherit meeting-report semantic authority.

## V0.5 analytical layer

```text
Official raw evidence -> Normalized blocks -> EvidenceRef -> SemanticEvidence
 -> authority meeting + disposition + bounded context -> TopicEvidenceBundle
 -> evidence-grounded Skill synthesis
```

The core reads current normalized, indexed, and semantic derived state and never persists narrative synthesis. Timelines aggregate meeting outcomes by **authority meeting**, while retaining the metadata **discovery meeting**. Contribution evidence remains grouped only by stored source organization and is never promoted to a meeting outcome.

## V0.6 Chair Note coverage layer

```text
Official TDoc List -> Chair Note snapshots -> bounded topic sections
 -> literal TDoc references -> positive discussion coverage
 -> topic corpus expansion plan -> existing selective TDoc fetch
 -> normalization -> lexical evidence -> SemanticEvidence -> TopicEvidenceBundle
```

`DirectorySource.discover_chair_notes` examines only the meeting's advertised `Inbox` and recognized case-insensitive Chair Note directory name. It preserves the exact directory URL and performs directory discovery only. Chair Note bytes are acquired separately by `ChairNoteService.fetch`; immutable raw files, slim receipts, and content-bound normalized blocks occupy Chair Note-specific runtime paths. Package inspection, parser selection, block shape, and checksum-conflict behavior reuse the document layer.

Every normalized block locator is a `ChairNoteRef` bound to a snapshot ID, normalization ID, normalized checksum, member, block, structure, and optional page/sheet/row/cell/character coordinates. Resolution revalidates raw and normalized checksums, current parser/schema identity, block identity, and coordinates. Coverage is computed on demand, so rule or metadata changes produce new deterministic identities rather than reusing stale associations.

Prose associations are bounded by heading, member, table, and a 200-block safety cap. Unheaded text and text-native PDF pages remain block-local; table associations remain row-local. These conservative boundaries prefer missing an association to leaking references from unrelated sections.

Chair Note coverage never writes SemanticEvidence and never calls `DocumentService.execute`. An explicit selection may be compiled through `FetchPlanner` into the accepted `TDocFetchPlan`; executing that plan remains a separate user action.
