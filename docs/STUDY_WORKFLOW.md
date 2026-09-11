# Study workflow

## Explicit evidence linkage

Run linkage after local metadata, Chair Note coverage, historical resolution, document normalization, lexical indexing, and SemanticEvidence extraction are prepared as needed:

```text
metadata
→ Chair Note coverage
→ historical resolution
→ contribution acquisition
→ normalization
→ lexical indexing
→ SemanticEvidence extraction
→ explicit linkage
→ evidence-limited synthesis
```

Use `show-tdoc-links --wg <WG> --tdoc <ID>` for a TDoc-centered local view and `show-meeting-links --wg <WG> --meeting <ID>` for one metadata meeting. Use `show-topic-links --wg <WG> --from-meeting <ID> --to-meeting <ID> --query <terms>` to feed V0.7 historical coverage into the link graph. The range view preserves V0.7 chronology and keeps discussion meeting separate from metadata meeting.

`build-explicit-links` writes a rebuildable graph; it performs no acquisition. `plan-link-preparation` reports `SOURCE_MISSING`, `BODY_NOT_LOCAL`, `SEMANTIC_EVIDENCE_NOT_EXTRACTED`, unresolved, ambiguous, and no-link states without executing any action. Missing explicit links do not prove that no relationship exists.

Read each edge literally. A Chair Note edge records an explicit discussion reference. A meeting edge records that accepted meeting evidence names a TDoc. A composed chain through one TDoc remains document-level unless the source explicitly identifies a narrower statement. Do not describe repeated topics as continuity, compare proposition meaning, or infer company stance.

## Historical meeting-range coverage

Prepare official Chair Note snapshots and TDoc-list metadata independently, then run `historical-discussion-coverage` for an explicit bounded range. Repeated `--snapshot MEETING=SNAPSHOT_ID` options resolve V0.6 selection ambiguity. Missing inventories, ambiguous snapshots, and unnormalized selections remain visible for one meeting while other meetings continue.

Review source completeness, meeting order, selected snapshot, positive sections, metadata resolution, metadata-only candidates, unresolved/ambiguous candidates, and local body state. `COMPLETE_FOR_SELECTED_SOURCES` is a source statement only. Always state that absence from a selected Chair Note is not evidence that the topic or TDoc was not discussed.

Use `plan-historical-corpus` to identify exact missing bodies. One body may carry many meeting/anchor edges, and batches contain at most 50 eligible TDocs. `--batch N --fetch-plan path.yaml` only compiles the chosen batch. Fetching, indexing, and semantic extraction remain later explicit steps. Present coverage chronology, not proposition evolution; V0.8 owns future proposition linkage and technical synthesis.

1. Express the task as a validated `StudyRequest` YAML.
2. Query a candidate inventory to identify locally available and missing meetings.
3. Discover missing meetings with safe default ingestion.
4. Explicitly run all-snapshot TDoc-list enrichment for meetings that need searchable metadata.
5. Query/filter by working group, meeting, title, organization, agenda, status, or TDoc ID.
6. Produce a metadata-only candidate inventory from canonical current, or explicitly request a stored meeting-close/historical snapshot without mutating canonical state.
7. Clearly report missing meetings, parse warnings, unknown columns, and that document bodies were not analyzed.

V0.2a.3 matching lowercases text, converts punctuation to spaces, deduplicates tokens, and removes common English stopwords.

- Anchor fields: `title`, `abstract`, `agenda_item_description`.
- Supporting fields: `related_work_item`, `document_type`, `status`, `release`, `specification`, `intended_for`.
- HIGH: every meaningful topic token occurs in one anchor field.
- MEDIUM: all meaningful topic tokens are covered across at least two fields, and anchor evidence includes at least one non-generic token.
- LOW: anchor fields cover at least two meaningful topic tokens and at least half of the topic tokens, including a non-generic token.

All levels therefore require specific anchor evidence. Supporting fields may complete or explain an anchored MEDIUM match but can never independently create a candidate. The tokens `3gpp`, `access`, `change`, `discussion`, `document`, `mode`, `radio`, `system`, `study`, and `update` are generic safeguards: a generic anchor token plus a complete supporting phrase is rejected.

Each candidate reports its strongest topic match, level, combined per-field tokens, separate anchor/supporting tokens, covered tokens, all qualifying topic matches, and availability. Optional organization selection remains exact and case-insensitive against conservatively split organizations. Questions are preserved but not answered.

Request-scoped results identify the exact snapshot URL, checksum, base role, filename timestamp, and selection status, and state `canonical_current_modified=false`. Such reads never import snapshot records as current or rewrite normalized files/manifests.

The Skill may coordinate this workflow, but `StudyRequest`, ingestion, parsing, filtering, and candidate selection remain Python-core responsibilities.
# Selective document preparation

After metadata candidate review, construct and inspect a fetch plan. Automatically generated plans include only downloadable candidates at or above the requested match level and default to 50 items maximum. Explicit identity selection is separate. Execution reports cached, downloadable, listed-only, and unknown counts, isolates ordinary per-document parser failures, and keeps provenance conflicts loud. Retrieve normalized blocks/text through `DocumentService.retrieve`; downstream callers must not infer filesystem paths.

V0.2b ends at deterministic structural extraction. Semantic retrieval, proposal/agreement extraction, support/opposition classification, and company-position inference are future work.

# Deterministic evidence retrieval

After normalization, run `index-documents` (no downloads), then use
`search-evidence` for exact blocks or `search-tdocs` for aggregation derived from
block hits. Quoted text requests exact token phrases. Preserve a `StudyRequest`
scope with WG, meeting, organization, and TDoc filters. Present literal snippet,
member/block ID, heading/page/sheet, matched terms, and score components.

V0.3 ends at lexical evidence candidates. Proposal/agreement extraction,
support/opposition classification, and company-position inference remain future.

# Explicit semantic evidence extraction

Run `extract-evidence` only when semantic evidence is explicitly requested, then
query it with `list-evidence` or resolve it with `inspect-evidence`. The operation
reads existing normalized blocks and downloads nothing. Report document role and
basis, kind, contribution/meeting scope, literal statement, source organizations
only for contributions, detection rule/cue, and every EvidenceRef/span.

Treat rejected authority candidates and ambiguous cues as diagnostics, not hidden
evidence. V0.4 performs no support/opposition inference, proposal equivalence,
company-position inference, synthesis, or cross-meeting trend analysis.

## Offline topic study

After documents are normalized, indexed, and semantically extracted, run `threegpp study-topic --query <terms>`. Review coverage first, then each distinct evidence layer, authority meeting, disposition, qualification, and unresolved link. A report under `RAN1#125` titled `Report of RAN1#124b meeting` appears on the `RAN1#124bis` timeline while preserving discovery under `#125`.

Context examines at most three immediately following blocks in the same member and heading path, accepts only explicit labels, and stops at an unlabelled block or heading. Incomplete studies must be phrased as “within the currently normalized material”.

Coverage counts are scoped to working-group and discovery-meeting filters, before topic and evidence-level filters. `documents_indexable` counts stored INDEXED states; `meeting_reports_available` counts role-classified extraction states. These are local processing diagnostics, not a complete meeting inventory. Semantic candidate scanning is currently bounded to 5000 fresh records; lexical retrieval has its own result limit. Results are capped per contribution organization and per authority meeting, and semantic truncation is reported. An unresolved-authority group is separately bounded. These limits can omit relevant material.

## Chair Note guided corpus expansion

Use this order for a meeting/topic whose contribution bodies are incomplete:

1. Ingest or inspect the official TDoc List to establish the metadata universe.
2. Run `discover-chair-notes --wg <WG> --meeting <ID>` to record advertised snapshots. This fetches directory listings, not Chair Note or TDoc bodies.
3. Select a snapshot explicitly when more than one non-unique-final candidate exists. Run `fetch-chair-note` for that snapshot; this is the separate explicit Chair Note acquisition boundary.
4. Inspect its checksum-bound blocks with `inspect-chair-note`.
5. Run `discussion-coverage --query <terms>` and review matched sections, exact `ChairNoteRef`s, confirmed references, metadata-only candidates, unresolved references, diagnostics, and limitations.
6. Run `plan-topic-corpus` to review reuse, downloadable, listed-only, unknown, and unresolved states. Supplying both `--tdoc` and `--fetch-plan` compiles only those explicit eligible selections to the existing fetch-plan YAML; it does not execute the plan.
7. Execute `fetch-tdocs` separately, then normalize/index/extract and use the V0.5 topic-study workflow.

Discovery, inspection, coverage, corpus planning, and topic study cause zero contribution-body downloads. An explicitly final snapshot may be selected only when unique; a single non-final snapshot may be selected as the only available artifact without asserting finality. Ambiguous snapshot sets require an explicit snapshot ID.

Report confirmed references as “explicitly associated with the matched topic in the selected Chair Note snapshot.” Never describe them as the only contributions discussed. Chair Note absence is not negative evidence, Chair Note completeness is not assumed, and Chair Note `Agreement:` text does not carry meeting-agreement authority.
