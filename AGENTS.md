# 3GPP Study Engine

Build a general, provenance-first system for studying 3GPP RAN meeting material.

- Correctness and source traceability matter more than breadth.
- Never fabricate missing 3GPP metadata; preserve unknowns as null.
- Never conflate a company proposal or observation with a meeting agreement.
- Keep discovery time separate from byte-retrieval time; preserve downloaded raw source material unchanged with URL, identity, retrieval time, and checksum.
- Prefer small, incremental changes and run the tests after each change.
- Update architecture documents when architectural decisions change.
- Do not add vector search, embeddings, or LLM/agent frameworks unless explicitly requested.

## Research-facing 3GPP study vocabulary

For user-facing 3GPP study output, follow `docs/STUDY_VOCABULARY.md`.
Route ordinary technical explanations, company-contribution summaries, and
research reports through `docs/RESEARCH_REPORT_GUIDE.md`. A source passage is
eligible when its literal content and required context have been read and
validated. SemanticEvidence, AcceptedProposition, and PropositionRelation are
optional aids; none is a report eligibility gate. An unreadable source remains
an evidence gap. Do not require proposition preparation or review to write a
report, and do not create review records from a report request.

The Python core supplies a bounded read-only source bundle through
`report-sources --profile <id>`; the Skill writes the explanation. Keep company
contributions, selected Chair Note discussion, and authoritative meeting outcomes
as three independent source channels. A missing channel cannot exclude readable
material from another channel or supply its authority.

Default report vocabulary is Company Contribution, Meeting Discussion, Meeting
Outcome, Source, and Open Issue / Evidence Gap. Use Proposal, Observation,
Conclusion, FFS, Agreement, and Decision only when present in the source, with
that source's authority. Faithful Korean paraphrase belongs in report prose;
stored source text, evidence, and reviewed spans remain literal. Put internal
identities, extraction metadata, hashes, and review history in a separate audit
artifact only when requested. Preserve legacy review provenance without claiming
that an automated record proves a human decision.

The per-TDoc meeting-study view answers three questions: Discussion,
Contribution, and Meeting outcome. Do not expose graph, link, or status terminology unless
the user requests engine internals. Absence from a selected Chair Note does
not prove that a TDoc was not discussed. Absence of an explicit meeting-outcome
reference is not rejection and does not prove that no meeting outcome exists.

Read-only study commands must never fetch contribution bodies. A user request
that explicitly requires the technical content of a specific TDoc may authorize
selective completion through the V0.9 workflow unless the user requests
offline, local-only, or no-download behavior. Do not extend that authorization
to unrelated TDocs.

`report-sources` never acquires, normalizes, indexes, extracts, or repairs source
state. An ordinary report request does not authorize corpus completion. Keep
missing, unsupported, and truncated sources visible; use the separate existing
preparation workflow only within its authorized scope.

For a new research topic, do not silently expand the user's wording through
semantic similarity or model-generated synonyms. Use the topic bootstrap and
source-terminology profile workflow. Keep observed candidate terms distinct
from source terms that the researcher explicitly accepts.

Topic bootstrap, profile, and inventory operations remain read-only for
contribution bodies. Bounded topic corpus completion requires an accepted
topic profile and explicit acquisition authorization. Do not expand
terminology during completion or execute an unbounded topic acquisition.

Proposition preparation operates only on current contribution-scoped
SemanticEvidence from a reviewed direct topic corpus. Preserve literal text,
qualifiers, spans, evidence kind, organizations, and EvidenceRefs. Candidates
remain unreviewed until an explicit researcher decision. Exact-span replacement
cannot introduce free text. Do not infer or score equivalence, stance, polarity,
consensus, meeting outcomes, or proposition evolution.

Proposition relations operate only on accepted propositions from a current
V0.12 corpus. A relation is an explicit symmetric researcher annotation with
exact bilateral source bases. It is not SemanticEvidence, company stance,
consensus, a meeting outcome, adoption, or proposition evolution. Never assign
a relation from wording, lexical overlap, or semantic similarity. An unreviewed
or absent relation is unknown, not negative evidence.

## Branch policy

- `main` is the latest accepted and validated repository state.
- Development occurs on `work/<version>-<topic>` branches created from `main`.
- Do not modify `main` during implementation or live acceptance.
- After acceptance, fast-forward `main` to the accepted work-branch HEAD.
- Create an annotated version tag on the accepted SHA.
- Do not create new `milestone/*` branches.
- Existing `milestone/*` branches are legacy historical references.
