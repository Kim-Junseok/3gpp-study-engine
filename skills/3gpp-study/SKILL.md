---
name: 3gpp-study
description: Build provenance-aware 3GPP studies and evidence-grounded topic summaries through the deterministic Python core. Never infer company stance, proposal equivalence, adoption, or trends.
---

# 3GPP Study

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

## V0.5 evidence-grounded topic answers

Run `threegpp study-topic --query <query>` over already-local state. Structure the answer as: Topic; Relevant contribution evidence; Meeting-level evidence by authority meeting; What the meeting agreed to do; Relevant qualifications; What is not established; Coverage. Every technical statement must identify TDoc, member, kind/scope, authority meeting, EvidenceRef, and literal support.

Treat `STUDY` as “the meeting agreed to study”, never adopted, selected, approved, or standardized. Inspect attached context and preserve limitations. No attached context does not establish that none exists. Organization grouping identifies contribution origin only, not stance. Similar contribution and meeting text without a literal link means relationship/adoption is **not established**, not adopted or rejected. Begin coverage-limited synthesis with “Within the currently normalized material”.

## V0.6 Chair Note guided coverage

For topic-driven corpus expansion within one meeting, first establish the official TDoc-list metadata universe. Run `discover-chair-notes`, select a snapshot explicitly when selection is ambiguous, and use `fetch-chair-note` only when the user has asked to acquire that Chair Note. Then run `discussion-coverage` and `plan-topic-corpus`. Coverage and planning are offline with respect to contribution bodies; supplying explicit `--tdoc` selections plus `--fetch-plan` writes an inspectable existing-format fetch plan but does not execute it.

Separate `CHAIR_NOTE_CONFIRMED`, `METADATA_RELEVANT_ONLY`, and unresolved/ambiguous references. Cite snapshot ID, heading path, exact ChairNoteRef, literal topic anchor/reference, structural association basis, and joined official metadata. Say: “These TDocs are explicitly associated with the matched topic in the selected Chair Note snapshot.” Also state that absence from that snapshot is not proof a TDoc was not discussed and that Chair Note completeness is not assumed.

Chair Note source text never supplies V0.4/V0.5 meeting Agreement, Decision, or Conclusion evidence—even if it contains those labels. Use only the accepted meeting-report/minutes path for meeting outcomes. Do not infer a TDoc from an organization, title, technical similarity, or snapshot absence. Do not call `fetch-tdocs` unless the user explicitly authorizes executing the selected contribution-body plan.
