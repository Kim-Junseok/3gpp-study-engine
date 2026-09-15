---
name: 3gpp-study
description: Build provenance-aware 3GPP studies and evidence-grounded topic summaries through the deterministic Python core. Never infer company stance, proposal equivalence, adoption, or trends.
---

# 3GPP Study

## V0.11 bounded topic corpus completion

When the user explicitly asks to inspect contributions across an accepted
topic profile, run `plan-topic-completion` first. Show the direct TDocs,
companies, matched accepted terms, Discussion, Contribution inspection, and
Meeting outcome states. Planning performs no contribution acquisition.

Execute `complete-topic-corpus` only for the explicitly authorized TDocs or one
deterministic batch. The default batch contains at most 20 TDocs and no
operation may exceed 50. Do not continue to later batches without explicit
scope. Use `CACHE` unless the user explicitly requests `PINNED`; preserve an
existing `PINNED` body. Use `--offline` when acquisition is prohibited.

After execution, rebuild the same profile inventory and report the resulting
`TDoc content inspected` transitions. Keep Discussion and Meeting outcome
unchanged unless their own authoritative sources changed. An item failure is
an operational gap, not evidence about its technical contents.

The corpus comes only from user seeds, exact formatting variants, and accepted
source terms. Never include source candidates, related terms, or rejected
terms without a profile revision. Corpus completion does not establish
proposition equivalence, company stance, consensus, or meeting agreement. A
single-TDoc content question continues to use V0.9 directly.

## V0.10 unknown-topic bootstrap

For a new topic, first check whether the local runtime has an accepted topic
profile. If none exists, run `bootstrap-topic` over the requested prepared
meeting range. Present user terms, exact formatting variants, observed source
candidates, and related diagnostic terms separately. Do not add model-generated
synonyms or silently accept a candidate.

Record the researcher's explicit decisions with `update-topic-profile`. Then
use `show-topic-profile` to build the source-limited company/TDoc inventory.
Only user seeds, exact variants, and accepted source terms may drive the direct
corpus. Related and rejected terms remain outside it. If the profile is applied
to a later meeting, report newly observed candidates separately.

Use Topic, Source terminology, Discussion, Contribution, and Meeting outcome
as the research-facing labels. State briefly which accepted terms affected
retrieval. Keep candidate states, retrieval-support scores, and internal IDs in
provenance output unless the user requests engine details.

Bootstrap and profile use perform zero contribution-body downloads. Invoke the
V0.9 completion workflow only after the user asks a contribution-content
question. Source-term co-occurrence is not semantic equivalence, metadata-title
relevance is not discussion evidence, and profile inclusion is not company
stance.

## V0.9 content-required questions

Separate read-only questions from questions that require contribution content.
Use local Discussion or Meeting outcome evidence for questions about Chair Note
references, submitter, title, meeting, or explicit agreement references. Do not
fetch the contribution for those questions.

Questions about what a specific TDoc proposes, argues, observes, concludes, or
says technically require inspected contribution content. If the study view says
`TDoc content inspected: No`, invoke `complete-tdoc-evidence --wg <WG> --tdoc
<ID>` unless the user requested metadata-only, offline, local-only, or
no-download behavior. This authorization applies only to the named TDoc. Use
`--offline` when network acquisition is prohibited.

Do not answer a contribution-content question from its title, organization,
Chair Note context, or meeting outcome. After completion, answer from the
Contribution-scoped SemanticEvidence in the standard three-section study view.

## V0.8.1 research-facing TDoc view

For a user-facing question about one TDoc, run `show-tdoc-study --wg <WG>
--tdoc <ID>` and organize the answer as Discussion, Contribution, and Meeting
outcome. Follow `docs/STUDY_VOCABULARY.md`. Use `--provenance` only when the user
asks for evidence details or engine internals.

Map “Was this TDoc discussed?” to Discussion, “What did it propose?” to
Contribution, “What was agreed about it?” to Meeting outcome, and “What happened
with this TDoc?” to all three sections. Preserve each section independently.
Not observed in the selected Chair Note does not mean not discussed. No explicit
meeting-outcome reference does not mean rejection or prove that no outcome
exists. A contribution conclusion is not a meeting conclusion.

If the view reports `TDoc content inspected: No`, state that content inspection
is required to answer proposal, observation, conclusion, or FFS questions. Do
not fetch the contribution in V0.8.1. Selective on-demand acquisition belongs to
V0.9.

## V0.8 explicit evidence links

For “Which meeting agreements explicitly reference these TDocs?”, use `show-tdoc-links`, `show-meeting-links`, or `show-topic-links`. Treat the returned `EvidenceLinkGraph` as the source of truth. Separate contribution evidence, Chair Note discussion records, meeting evidence, explicit links, ambiguous references, unresolved references, and preparation gaps.

State each relationship at its recorded level. Safe wording is: “The meeting Agreement explicitly references TDoc R1-…, authored by Company X.” If the edge carries a disposition, report it as a separate property of the meeting evidence. Do not say that the meeting adopted or endorsed every proposition in the referenced contribution.

`DISCUSSION_REFERENCE` means that one bounded selected Chair Note context literally names the TDoc. It does not mean considered, supported, rejected, or adopted. `SAME_TDOC` identifies a parent document and does not establish equivalence with another statement. Similar wording, the same topic, the same organization, and placement in one section cannot create a link.

Use `plan-link-preparation` when the graph reports missing metadata, bodies, indexes, or SemanticEvidence. The plan never executes work. Do not call acquisition, indexing, or extraction commands unless the user separately requests the relevant operation. Never create company stance, support/opposition, proposition clusters, cross-meeting semantic continuity, or trend language from link counts.

When a persisted `tdoc-status.jsonl.gz` is available, inspect its Chair Note, contribution SemanticEvidence, meeting explicit-link, cross-meeting, and preparation dimensions independently. Do not summarize them into one coverage label. Treat `NO_EXPLICIT_LINK` only as absence from the available inspected explicit-link sources, never as negative evidence.

## V0.7 historical meeting coverage

For an explicit historical range, use `historical-discussion-coverage --wg <WG> --from-meeting <ID> --to-meeting <ID> --query <terms>`. If a meeting has ambiguous snapshots, report `SNAPSHOT_SELECTION_REQUIRED` and use an explicit `--snapshot MEETING=SNAPSHOT_ID` only when supplied or selected by the user. Preserve raw meeting notation and source provenance when the core aliases `124b` to `124bis`.

Report each meeting's selected source, Chair-note-confirmed references, metadata-only candidates, historical resolution, unresolved/ambiguous references, local bodies, and fetch-needed counts. State that coverage is positive evidence from selected sources and absence is not negative evidence. A later Chair Note reference to an older TDoc does not establish continuity or adoption.

Use `plan-historical-corpus` for missing bodies and preserve all `ChairNoteRef` edges for deduplicated items. `--batch` plus `--fetch-plan` may compile one bounded batch but does not execute it. Keep discussion coverage, metadata resolution, corpus availability, unresolved references, and limitations separate. Safe wording is: “The selected Chair Note associates TDoc R1-… authored by Company X with the requested topic section.” V0.7 cannot support company stance, proposal equivalence, agreement linkage, cross-company comparison, proposition evolution, consensus, or trend wording.

Turn the user's working groups, meetings, topics, organizations, and questions into the repository's canonical `StudyRequest`. Use [resources/study-request.example.yaml](resources/study-request.example.yaml) as the shape, validate it with `StudyRequest.from_yaml`, and preserve explicit meeting suffixes such as `bis`.

Use the Python core as the source of truth. The CLI is a thin operational interface:

1. Run `threegpp study-inventory --request <request.yaml>` to identify locally available and missing meetings using canonical current.
2. For each missing meeting or meeting without all-snapshot metadata, run `threegpp ingest-meeting --wg <WG> --meeting <ID> --enrich-tdocs`. This retrieves and parses official TDoc-list snapshots but never TDoc archives. If an accepted V0.2a.2 embedded-row manifest already exists, use `threegpp migrate-manifest --manifest <path>` instead; migration performs no source download.
3. Run the inventory again. Apply additional exact metadata filters through `TDocQuery` or `threegpp list-tdocs` when useful.
4. Return snapshot coverage, candidate count, HIGH/MEDIUM/LOW and availability counts, organization/meeting/agenda summaries, and candidates with title, strongest topic, level, separate anchor/supporting matched tokens, covered tokens, availability, status, and metadata source URL.

Use only the Python core's current normalized view and match evidence. Do not independently rescore candidates. Keep list-only records in results and distinguish meeting-close from current-consolidated snapshot coverage. If the user explicitly requests a meeting-close or exact stored snapshot, pass `--view meeting-close` or `--snapshot-url`; report its URL, checksum, role, timestamp, and request-selected status, then explicitly confirm that canonical current was not modified. Do not treat the selection as a persistent role or default.

If the user explicitly asks to download and prepare candidates:

1. Run `threegpp plan-fetch --request <request.yaml> --minimum-match high --output <plan.yaml>` and show the exact plan before retrieval.
2. Confirm the set is bounded and contains only `DOWNLOADABLE` records. Never invent URLs for listed-only records.
3. Run `threegpp fetch-tdocs --plan <plan.yaml>` only after the explicit action is clear.
4. Report counts for parsed, partial, unsupported, text-unavailable, and failed outcomes. Report structural/provenance facts only.

Ordinary `study-inventory` never downloads TDoc bodies. Never independently parse paths or rescore records when the core API supplies the result. Never infer technical proposals, agreements, conclusions, company positions, or support/opposition from extracted text.

For “find relevant passages about HARQ feedback within normalized RAN1#125
TDocs”, run `threegpp index-documents --wg RAN1 --meeting 125`, then
`threegpp search-evidence --query 'HARQ feedback' --wg RAN1 --meeting 125`.
These commands use only local normalized evidence and download nothing. Present
each result as a **lexically relevant evidence candidate** with TDoc, member,
block ID/type, heading/page/sheet, literal snippet, matched terms, match kind, and
score explanation. `search-tdocs` is aggregation derived from block hits. Never
turn a lexical hit into “company proposes/supports” or “RAN agreed”.

For explicit semantic requests, run `threegpp extract-evidence` over the bounded
normalized scope, then `threegpp list-evidence`; use `inspect-evidence` when exact
source blocks are needed. Present the role and its basis, kind, scope, literal
statement, exact source organizations for contribution evidence, EvidenceRefs,
and detection rule/cue. These commands download no TDocs.

Only describe “company proposed X” for `proposal + contribution` evidence whose
stored organizations include that company. Only describe “RAN agreed X” for
`agreement + meeting` evidence from an accepted meeting-report role. A company’s
“we agree” wording is never a meeting agreement. Do not independently classify,
paraphrase, infer support/opposition or company positions, cluster proposals, or
synthesize cross-meeting trends.

## V0.12 proposition preparation

For proposition-level preparation, use `build-proposition-corpus`, then inspect
literal candidates with `show-proposition-corpus --provenance`. Do not
propositionize meeting evidence. Keep candidates unreviewed until the researcher
explicitly accepts, defers, excludes, or selects exact source spans.

Use `review-proposition` for the decision. Exact-span replacement may select
source wording but cannot add a paraphrase. Preserve qualifiers, evidence kind,
organization attribution, EvidenceRefs, and separate spans. Do not merge
duplicates or infer equivalence, stance, polarity, consensus, meeting adoption,
or evolution.

## V0.5 evidence-grounded topic answers

Run `threegpp study-topic --query <query>` over already-local state. Structure the answer as: Topic; Relevant contribution evidence; Meeting-level evidence by authority meeting; What the meeting agreed to do; Relevant qualifications; What is not established; Coverage. Every technical statement must identify TDoc, member, kind/scope, authority meeting, EvidenceRef, and literal support.

Treat `STUDY` as “the meeting agreed to study”, never adopted, selected, approved, or standardized. Inspect attached context and preserve limitations. No attached context does not establish that none exists. Organization grouping identifies contribution origin only, not stance. Similar contribution and meeting text without a literal link means relationship/adoption is **not established**, not adopted or rejected. Begin coverage-limited synthesis with “Within the currently normalized material”.

## V0.6 Chair Note guided coverage

For topic-driven corpus expansion within one meeting, first establish the official TDoc-list metadata universe. Run `discover-chair-notes`, select a snapshot explicitly when selection is ambiguous, and use `fetch-chair-note` only when the user has asked to acquire that Chair Note. Then run `discussion-coverage` and `plan-topic-corpus`. Coverage and planning are offline with respect to contribution bodies; supplying explicit `--tdoc` selections plus `--fetch-plan` writes an inspectable existing-format fetch plan but does not execute it.

Separate `CHAIR_NOTE_CONFIRMED`, `METADATA_RELEVANT_ONLY`, and unresolved/ambiguous references. Cite snapshot ID, heading path, exact ChairNoteRef, literal topic anchor/reference, structural association basis, and joined official metadata. Say: “These TDocs are explicitly associated with the matched topic in the selected Chair Note snapshot.” Also state that absence from that snapshot is not proof a TDoc was not discussed and that Chair Note completeness is not assumed.

Chair Note source text never supplies V0.4/V0.5 meeting Agreement, Decision, or Conclusion evidence—even if it contains those labels. Use only the accepted meeting-report/minutes path for meeting outcomes. Do not infer a TDoc from an organization, title, technical similarity, or snapshot absence. Do not call `fetch-tdocs` unless the user explicitly authorizes executing the selected contribution-body plan.
