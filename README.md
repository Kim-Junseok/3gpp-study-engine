# 3GPP Study Engine

`3gpp-study-engine` is a provenance-first research foundation for public 3GPP meeting material. V0.2a.3 preserves and parses every discovered official TDoc-list snapshot, keeps canonical and request-scoped views isolated, and produces explainable metadata-only candidate inventories without embedding thousands of rows in each manifest.

## Milestone status

**Current stable milestone: V0.2a.3. The metadata layer is accepted and frozen.**

```text
3GPP meeting
  ↓
official TDoc-list metadata
  ↓
snapshot-aware normalized metadata
  ↓
metadata-only candidate retrieval
```

V0.2b is intentionally not implemented on this milestone branch. V0.2a.3 does not provide TDoc body extraction, semantic content analysis, proposal/agreement extraction, or company-trend analysis.

## Interface layering

```text
User
  ↓
3GPP Study Skill
  ↓
StudyRequest
  ↓
Python core
  ├── source
  ├── ingest
  ├── normalize
  ├── persistence
  └── retrieval/study

CLI = developer/debug interface
```

The Skill is intentionally thin. Research logic, spreadsheet mappings, merge policy, and retrieval behavior live in the Python core.

## Metadata-first workflow

A meeting can expose thousands of TDoc archives. Plain `ingest-meeting` only discovers meeting resources and records directory-level metadata. `--enrich-tdocs` explicitly downloads and parses all discovered official TDoc-list spreadsheets, which are small metadata artifacts; it never downloads individual TDocs. `--download-artifacts` also retrieves meeting-level agenda and report files.

```text
meeting directory → discover all list snapshots → classify roles
                  → retrieve and parse every list → preserve snapshot records
                  → deterministic JSONL.gz → canonical current → DuckDB
```

Identifiers such as `124`, `124bis`, and `119-e` remain distinct. Missing source values remain null.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
```

`openpyxl` reads current XLSX/XLSM lists, while `xlrd` reads legacy binary XLS files. `PyYAML` loads the canonical study request. `xlwt` is test-only and creates a real legacy XLS fixture.

## CLI examples

```bash
# Read-only discovery; default ingestion downloads nothing.
python -m threegpp.cli list-meetings --wg RAN1
python -m threegpp.cli inspect-meeting --wg RAN2 --meeting 133
python -m threegpp.cli ingest-meeting --wg RAN2 --meeting 133

# Explicitly retrieve all official TDoc-list snapshots and enrich metadata.
python -m threegpp.cli ingest-meeting --wg RAN2 --meeting 133 --enrich-tdocs

# Explicitly retrieve all meeting-level artifacts, never individual TDocs.
python -m threegpp.cli ingest-meeting --wg RAN2 --meeting 133 --download-artifacts

# Query enriched local metadata.
python -m threegpp.cli list-tdocs --wg RAN2 --meeting 133 --organization Nokia
python -m threegpp.cli list-tdocs --wg RAN1 --meeting 125 --title-contains uplink

# Build a metadata-only candidate inventory.
python -m threegpp.cli study-inventory \
  --request skills/3gpp-study/resources/study-request.example.yaml

# Query one stored snapshot without changing canonical current state.
python -m threegpp.cli study-inventory \
  --request skills/3gpp-study/resources/study-request.example.yaml \
  --snapshot-url 'https://www.3gpp.org/.../tdocList_....xlsx'

# Explicitly migrate one embedded-row V0.2a.2 receipt; no source download occurs.
python -m threegpp.cli migrate-manifest \
  --manifest data/manifests/ran2-131-legacy.json
```

Use global `--data-dir` and `--db` before the subcommand to override default paths.

## Spreadsheet normalization

The parser scans worksheets and header rows rather than assuming one fixed layout. Column aliases also promote abstract, agenda-item description, intended purpose, release, specification, and related work item when present. Exact source-organization text and all non-empty raw row fields are retained. Organization normalization splits only on comma, semicolon, or newline boundaries (while protecting common legal-suffix commas); `and`, `&`, `/`, and `+` are not assumed to separate organizations.

Every list remains an independent artifact and parsed snapshot. `eom`/`final` denotes a meeting-close role, while `TDoc_List_Meeting` denotes a current-consolidated role. Candidate discovery defaults to canonical current. An exact snapshot URL is a request-scoped view and never redefines canonical current.

## Storage responsibilities

```text
data/raw/         immutable downloaded official evidence
data/normalized/  deterministic portable snapshot/current JSONL.gz rows
data/metadata.duckdb  local query/index database
data/manifests/   timestamped provenance receipts and normalized-output references
```

Normalized filenames are content-addressed. Each manifest reference records path, compressed-file SHA-256, row count, and format. A conflicting existing normalized file is never silently overwritten. A slim V0.2a.3 manifest can hydrate its rows from those outputs, so DuckDB can be rebuilt from the receipt plus normalized files. Raw artifacts plus the receipt can also regenerate normalized outputs with the same parser; raw checksums remain unchanged.

Live runtime research data under `data/raw/`, `data/normalized/`, `data/manifests/`, and `data/metadata.duckdb` stay local and are normally excluded from Git history. Only intentional small placeholders and test fixtures belong in the repository.

V0.2a.2 embedded-row manifests remain readable. `migrate-manifest` externalizes their current and per-snapshot rows, writes a new V0.2a.3 receipt, preserves source and field provenance, and leaves both the old receipt and raw evidence untouched.

## Current limitations

- Candidate matching reports deterministic HIGH/MEDIUM/LOW levels, covered tokens, and separate anchor/supporting evidence; it is not document-content analysis.
- Candidate results report the fields that matched and separate `downloadable`, `listed_only`, and `unknown` counts.
- V0.2a.3 implements directory and official-list metadata layers only.
- Spreadsheet formulas depend on cached workbook values supplied by the source.
- Password-protected, corrupt, zipped spreadsheet bundles, and unusual unrecognized headers are reported but not automatically repaired.
- Organization normalization splits source strings but applies no curated alias equivalence.
- Meeting dates and locations are not inferred from upload timestamps.
- No proposal, agreement, conclusion, or company-trend extraction is implemented.

## Roadmap

- V0.1 — Meeting and directory-derived TDoc metadata ingestion
- V0.2a — TDoc-list metadata enrichment and Skill-facing request contract
- V0.2a.1 — Metadata parsing, availability, and candidate-matching stabilization
- V0.2a.2 — Snapshot-role views and deterministic cross-field candidate recall
- V0.2a.3 — Slim portable metadata storage, isolated snapshot queries, and anchor-safe matching
- V0.2b — Document normalization / extraction
- V0.3 — Metadata and full-text retrieval
- V0.4 — Proposal/agreement evidence extraction
- V0.5 — Cross-meeting topic study
- V0.6 — Company trend analysis
- V1.0 — General RAN1/RAN2 research workflow
