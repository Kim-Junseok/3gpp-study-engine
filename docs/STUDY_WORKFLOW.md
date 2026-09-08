# Study workflow

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
