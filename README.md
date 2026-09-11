# 3GPP Study Engine

`3gpp-study-engine` is a provenance-first research foundation for public 3GPP meeting material. V0.8 adds deterministic document/reference-level links across contribution evidence, Chair Note discussion records, and authoritative meeting evidence without changing the accepted evidence-authority hierarchy.

## V0.8 explicit evidence linkage

V0.8 builds links only when a grounded source supplies a literal TDoc/meeting reference or an existing structural contract establishes the parent TDoc. `DISCUSSION_REFERENCE` means that a bounded Chair Note discussion context explicitly references a TDoc. `EXPLICIT_TDOC_REFERENCE` means that SemanticEvidence or metadata literally names a TDoc. Reply, revision, and supersession kinds require those cue words in the source. `SAME_TDOC` binds contribution SemanticEvidence to its parent document.

```text
Contribution evidence
        ↓ SAME_TDOC
      TDoc
      ↑  ↑
Chair Note  Meeting evidence
```

The graph preserves discussion, evidence-source, and metadata meetings separately. For example, a Chair Note from `RAN1#125` may explicitly reference `R1-2603427` whose resolved metadata meeting is `RAN1#124bis`. This cross-meeting edge establishes the literal document reference only. A meeting Agreement that names `R1-2601985` likewise establishes a document-level reference; its separate disposition does not apply automatically to every statement in that TDoc.

Use `show-tdoc-links`, `show-meeting-links`, or `show-topic-links` for read-only local views. `build-explicit-links` persists a compact rebuildable graph and a per-canonical-TDoc status artifact under `data/derived/links/`. The status artifact records Chair Note, contribution evidence, meeting link, cross-meeting, and preparation states independently; `NO_EXPLICIT_LINK` is never negative evidence. `plan-link-preparation` reports missing metadata, bodies, indexes, or SemanticEvidence without executing acquisition or extraction. None of these commands downloads a contribution, Chair Note, TDoc list, or meeting report.

## V0.7 historical coverage

V0.7 resolves literal Chair Note TDoc references against canonical-current metadata and stored official list snapshots. It preserves discussion meeting, metadata meeting, exact snapshot URL/checksum/role, and every ambiguity candidate. The versioned adapter accepts `124b`, `124bis`, `RAN1#124b`, and `RAN1#124bis` as the same identifier while preserving raw notation. Official source discovery also retains a literal path such as `TSGR1_124b` while exposing normalized identity `124bis`; aliases do not equate source artifacts or confer authority.

```bash
python -m threegpp.cli historical-metadata-resolve --wg RAN1 --meeting 124bis --tdoc R1-2603427
python -m threegpp.cli historical-discussion-coverage --wg RAN1 --from-meeting 124bis --to-meeting 126 --query "HARQ Fast-ARQ"
python -m threegpp.cli plan-historical-corpus --wg RAN1 --from-meeting 124bis --to-meeting 126 --query "HARQ Fast-ARQ"
```

Range coverage reuses V0.6 once per meeting. Missing sources and ambiguous snapshots remain per-meeting results. Corpus plans deduplicate exact contribution bodies, preserve every meeting and `ChairNoteRef` association, and split eligible items into existing fetch-plan batches of at most 50. These commands perform no acquisition, indexing, semantic extraction, proposition linkage, or stance inference.

## Milestone status

**Current development milestone: V0.8 explicit evidence linkage.**

```text
3GPP meeting
  ↓
official TDoc-list metadata
  ↓
snapshot-aware normalized metadata
  ↓
metadata-only candidate retrieval
```

V0.2b adds explicit, selective body fetch plans and deterministic structural normalization. It stops before semantic content analysis, proposal/agreement extraction, or company-trend analysis.

```text
Metadata discovery → candidate selection → fetch plan → immutable raw TDoc
→ safe package inspection → parser → normalized blocks/text → local document index
```

Body retrieval is never triggered by `study-inventory`. Inspect a plan, then explicitly execute it:

```bash
threegpp plan-fetch --request studies/example.yaml --minimum-match high --output fetch-plan.yaml
threegpp fetch-tdocs --plan fetch-plan.yaml
threegpp inspect-document --tdoc R1-2600001 --wg RAN1 --meeting 125
threegpp index-documents --wg RAN1 --meeting 125
threegpp search-evidence --query '"HARQ feedback"' --wg RAN1 --meeting 125
threegpp search-tdocs --query 'contention based uplink'
threegpp extract-evidence --wg RAN1 --meeting 125 --tdoc R1-2600001
threegpp list-evidence --wg RAN1 --meeting 125 --kind proposal
```

Indexing and searching use only local normalized documents and cause zero TDoc downloads. Results are lexically relevant evidence candidates, not semantic proposal or agreement conclusions.

Semantic extraction is a separate explicit operation. It recognizes only versioned labels, bounded heading context, table labels, and narrow sentence cues. Contribution evidence and authoritative meeting-record evidence have different scopes; a company contribution can never create a meeting agreement.

Set `THREEGPP_DATA_ROOT=/another/disk/3gpp-data` to relocate runtime research storage; the fallback remains `./data`. Existing data are never moved automatically. Raw TDocs default to `CACHE`; `PINNED` marks evidence that must not be automatically pruned. This release does not implement pruning.

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

The rebuildable DuckDB search index stores block locators, token counts, and term frequencies—not complete body text. V0.4 evidence is stored as portable `data/derived/evidence/` JSONL.gz plus a minimal DuckDB query index and lifecycle receipt. Statements remain literal and every span resolves to normalized blocks.

## Current limitations

- Candidate matching reports deterministic HIGH/MEDIUM/LOW levels, covered tokens, and separate anchor/supporting evidence; it is not document-content analysis.
- Candidate results report the fields that matched and separate `downloadable`, `listed_only`, and `unknown` counts.
- V0.2a.3 implements directory and official-list metadata layers only.
- Spreadsheet formulas depend on cached workbook values supplied by the source.
- Password-protected, corrupt, zipped spreadsheet bundles, and unusual unrecognized headers are reported but not automatically repaired.
- Organization normalization splits source strings but applies no curated alias equivalence.
- Meeting dates and locations are not inferred from upload timestamps.
- Explicit rules intentionally miss implicit or ambiguous semantic statements; no support/opposition, equivalence, company-position, or cross-meeting trend inference is implemented.

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
- V0.6 — Chair Note guided discussion coverage and topic-corpus expansion planning
- V0.7 — Historical metadata resolution and meeting-range Chair Note coverage
- V0.8 — Explicit document/reference-level evidence linkage
- V0.9 — Semantic proposition equivalence and cross-company/cross-meeting analysis (future)
- V1.0 — General RAN1/RAN2 research workflow

## V0.5 offline topic evidence

V0.5 adds deterministic offline topic studies over lexical and semantic evidence. `study-topic` keeps lexical candidates, contribution evidence, and authoritative meeting evidence separate while reporting local-corpus coverage. `inspect-meeting-authority` explains when a report discovered under one meeting records another. Both commands perform zero TDoc downloads. Agreement dispositions use explicit cues: an agreement to **study** is not adoption.

## V0.6 Chair Note discussion coverage

V0.6 treats Chair Notes as first-class, snapshot-specific artifacts. `discover-chair-notes` records the exact advertised `Inbox/Chair_notes` or `Inbox/Chair_Notes` directory and filenames without fetching bytes. `fetch-chair-note` is the only Chair Note command that performs explicit Chair Note acquisition; it stores immutable raw bytes under `data/raw/chair-notes/`, reuses the existing safe package inspection and DOCX/PDF/XLS/XLSX/text parsers, and writes checksum-bound normalized blocks under `data/normalized/chair-notes/`.

`discussion-coverage` lexically locates bounded structural sections, extracts only literal R1/R2 TDoc identifiers, and joins them to official metadata. `plan-topic-corpus` reports local/index/semantic state and can compile an explicitly selected, fetch-eligible subset into the existing `TDocFetchPlan`. Discovery, inspection, coverage, and planning never execute contribution-body fetches.

The authority hierarchy is explicit:

```text
Official TDoc List     = meeting document universe and TDoc metadata
Selected Chair Note   = positive discussion association only
Contribution TDoc     = company proposal/observation/conclusion evidence
Meeting report/minutes = meeting agreement/decision/conclusion authority
```

Chair-note-confirmed references are positive evidence that the selected Chair Note associates a TDoc with the recorded discussion context. Absence from the selected Chair Note snapshot is not proof that a TDoc was not discussed. Chair Note text—including text labelled `Agreement:`—is never promoted to V0.4/V0.5 meeting SemanticEvidence.
