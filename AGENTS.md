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
The default per-TDoc view answers three questions: Discussion, Contribution,
and Meeting outcome. Do not expose graph, link, or status terminology unless
the user requests engine internals. Absence from a selected Chair Note does
not prove that a TDoc was not discussed. Absence of an explicit meeting-outcome
reference is not rejection and does not prove that no meeting outcome exists.

Read-only study commands must never fetch contribution bodies. A user request
that explicitly requires the technical content of a specific TDoc may authorize
selective completion through the V0.9 workflow unless the user requests
offline, local-only, or no-download behavior. Do not extend that authorization
to unrelated TDocs.

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

## Branch policy

- `main` is the latest accepted and validated repository state.
- Development occurs on `work/<version>-<topic>` branches created from `main`.
- Do not modify `main` during implementation or live acceptance.
- After acceptance, fast-forward `main` to the accepted work-branch HEAD.
- Create an annotated version tag on the accepted SHA.
- Do not create new `milestone/*` branches.
- Existing `milestone/*` branches are legacy historical references.
