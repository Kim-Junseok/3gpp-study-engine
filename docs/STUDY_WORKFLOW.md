# Study workflow

## V0.11 bounded direct-corpus completion

Use this sequence for a contribution-content question spanning an accepted
topic corpus:

```text
new topic → V0.10 bootstrap/profile → direct inventory
          → V0.11 bounded completion → future proposition analysis
```

Run `plan-topic-completion --topic-profile <id>` first. This read-only step
shows already inspected, eligible, unavailable, unresolved, ambiguous,
filtered, and deferred TDocs with their source associations. Its deterministic
order is meeting chronology, source association order, then numeric TDoc ID.
The default batch is 20 and the hard operation limit is 50.

Run `complete-topic-corpus` only for an explicitly authorized list of `--tdoc`
values or one `--batch`. The command executes no later batch automatically. It
uses V0.9 for raw reuse/acquisition, retention, normalization, indexing,
contribution evidence, targeted link status, and study-view refresh. Rebuild
the profile inventory after partial completion; progress comes from actual
per-TDoc state rather than a mutable counter.

An item-local failure does not roll back successful independent items. A
systemic exception stops the rest. Replan after a profile revision or direct
source change. If a compatible planned TDoc was completed separately, reuse it
without downloading it again.

The corpus remains limited to selected meetings, prepared official sources,
and accepted profile terms. Completing it does not establish technical
completeness beyond that scope.

## New-topic first pass

For a topic without an accepted terminology profile, run the offline bootstrap
before broad historical retrieval:

1. Supply the literal researcher terms and a bounded meeting range to
   `bootstrap-topic`.
2. Inspect observed source phrases and their provenance. Case and hyphen/space
   variants are safe lexical variants; other phrases remain candidates.
3. Use `update-topic-profile --accept`, `--related`, or `--reject` to record an
   explicit decision in a new immutable profile.
4. Run `show-topic-profile` to apply user seeds, exact variants, and accepted
   source terms to historical coverage and build the company/TDoc inventory.
5. Invoke V0.9 completion only when the user asks what a selected contribution
   says and its content has not been inspected.

The same profile can be applied to a later meeting with `--from-meeting` and
`--to-meeting`. Accepted terms drive that request. Newly observed phrases stay
separate candidates until another explicit profile revision. Related and
rejected terms do not add TDocs to the direct corpus.

Bootstrap and profile operations read prepared sources only. Missing Chair
Notes, ambiguous snapshots, unnormalized snapshots, and missing metadata remain
explicit source-coverage limitations. These operations never download a
contribution body.

## Read-only study and on-demand inspection

```text
Research question
     ↓
Does the answer require contribution content?
     ├─ No → use local evidence
     └─ Yes
          ↓
     Is the content already inspected?
          ├─ Yes → reuse it
          └─ No
               ↓
          complete-tdoc-evidence
               ↓
          CACHE acquisition when authorized
               ↓
          normalize → index → extract
               ↓
          rebuild the three-section study view
```

The completion command handles exactly one named TDoc. `--offline` reuses valid
local raw content and repairs downstream state without network access. If the
body is missing, offline mode reports a preparation gap. `LISTED_ONLY`,
`UNKNOWN`, unresolved, and ambiguous metadata never cause a guessed download.

Valid raw and normalized artifacts remain after a downstream failure. A retry
resumes from the first missing or stale stage. The current refresh policy is
`IF_STALE`; V0.9 does not force remote refresh or delete cached evidence.

## Explicit evidence linkage

For a TDoc-centered research question, build the read view from the locally
prepared layers:

```text
User asks about a TDoc
        ↓
Discussion evidence
        +
Contribution content/evidence
        +
Meeting outcome evidence
        ↓
Research-facing TDoc study view
```

Run `show-tdoc-study --wg <WG> --tdoc <ID>`. If contribution content has not
been inspected, the view states that gap. V0.8.1 does not fetch the body.

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

`build-explicit-links` writes a rebuildable graph and a deterministic per-TDoc status artifact at `data/derived/links/<wg>/<graph-id>/tdoc-status.jsonl.gz`; it performs no acquisition. The status artifact keeps Chair Note discussion links, contribution SemanticEvidence, meeting explicit links, cross-meeting references, preparation, and their provenance identities independent. `plan-link-preparation` reports `SOURCE_MISSING`, `BODY_NOT_LOCAL`, `SEMANTIC_EVIDENCE_NOT_EXTRACTED`, unresolved, ambiguous, and no-link states without executing any action. Missing explicit links do not prove that no relationship exists.

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

## Proposition preparation

After bounded completion and SemanticEvidence extraction, build candidates
without fetching bodies:

```bash
python -m threegpp.cli build-proposition-corpus --topic-profile <profile-id>
python -m threegpp.cli show-proposition-corpus --corpus <corpus-id> --provenance
python -m threegpp.cli review-proposition --corpus <corpus-id> \
  --candidate <candidate-id> --decision accept
```

Replacement uses one or more `--span START:END` source-unit ranges. The CLI
copies the literal slices and accepts no replacement prose. Review qualifiers,
kind, organization metadata, and EvidenceRefs before accepting. A stale profile,
inventory, normalization, evidence artifact, or ruleset requires rebuilding.
Reviews for missing candidate IDs do not transfer silently.
For an explicit option child, inspect `context_source_unit_id` before reviewing;
the parent source remains separate from the candidate text.

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
