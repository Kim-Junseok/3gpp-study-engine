# Study vocabulary

This guide defines the default research-facing vocabulary for a study of one
3GPP TDoc. The engine retains its provenance and link models internally. The
normal study view translates those models into three researcher questions:

```text
TDoc
├─ Discussion
├─ Contribution
└─ Meeting outcome
```

## Canonical terms

| Term | Meaning and authority | Establishes | Does not establish | Backend mapping |
|---|---|---|---|---|
| Discussion | Evidence from a selected Chair Note about the recorded discussion context | The selected source explicitly associates the TDoc with that context | Agreement, adoption, support, rejection, or complete meeting coverage | Linked `DISCUSSION_REFERENCE` and `ChairNoteRef` |
| Contribution | Technical statements extracted from the TDoc body under contribution authority | What that contribution explicitly proposes, observes, concludes, or marks FFS | A meeting outcome or another organization's position | Contribution-scoped `SemanticEvidence` grouped by `EvidenceKind` |
| Meeting outcome | Agreement, decision, conclusion, or FFS evidence from an accepted report or minutes | The literal meeting-level statement and any explicit TDoc reference or disposition it contains | Adoption of every statement in the referenced TDoc | Meeting-scoped `SemanticEvidence`, explicit link, and separate `AgreementDisposition` |
| Referenced in selected Chair Note | A qualifying literal reference occurs in the selected local Chair Note material | Positive, source-bounded discussion evidence | That the TDoc was handled, agreed, supported, rejected, or adopted | Discussion state `LINKED` |
| TDoc content inspected | The local corpus acquired and processed the contribution sufficiently to run SemanticEvidence extraction | The engine inspected the available normalized content | That every possible statement was extracted or that the document is complete | Fresh contribution extraction state, including a valid zero-evidence result |
| Explicit TDoc reference found | Meeting-outcome evidence literally names the TDoc and resolves to it | A document-level meeting-evidence reference | Proposition equivalence or adoption of every contribution statement | Meeting explicit-link state `LINKED` |
| Not observed | No qualifying Chair Note reference occurs in the selected locally prepared source set | A bounded absence in the inspected source | That the TDoc was not discussed | Discussion state `NO_EXPLICIT_LINK` |
| No explicit outcome reference found | Prepared meeting-outcome evidence contains no qualifying resolved reference to the TDoc | A bounded absence in the inspected outcome sources | Rejection or proof that no meeting outcome exists | Meeting state `NO_EXPLICIT_LINK` |

## Default TDoc view

The normal view uses exactly these primary sections:

```text
DISCUSSION
CONTRIBUTION
MEETING OUTCOME
```

Source availability is subordinate information. It is not a fourth evidence
section. The normal view may state `TDoc content inspected: No` while retaining
known title, organization, meeting, and official URL metadata.

The following combinations are valid:

```text
Discussion referenced
+ contribution inspected
+ no explicit outcome reference found
```

```text
Discussion referenced
+ contribution not inspected
+ explicit meeting-outcome reference found
```

The first combination does not imply rejection. The second does not reveal what
the uninspected contribution says.

## Backend-to-research mapping

| Backend state | Normal wording |
|---|---|
| Discussion `LINKED` | `Referenced in selected Chair Note: Yes` |
| Discussion `NO_EXPLICIT_LINK` | `Referenced in selected Chair Note: Not observed` |
| Contribution `BODY_NOT_LOCAL` | `TDoc content inspected: No` |
| Fresh contribution extraction | `TDoc content inspected: Yes` plus actual evidence categories |
| Meeting link `LINKED` | `Explicit TDoc reference found: Yes` |
| Meeting link `NO_EXPLICIT_LINK` | `Explicit TDoc reference found: No` |

The normal view does not expose `BODY_NOT_LOCAL`, `NO_EXPLICIT_LINK`, graph
nodes, coverage axes, or link kinds. Provenance mode may expose these internal
values for audit and development.

## Wording boundaries

Avoid these phrases unless literal source evidence supports them:

```text
explicit-link coverage
coverage axis
graph node
BODY_NOT_LOCAL
NO_EXPLICIT_LINK
handled by the meeting
not discussed
no meeting outcome
rejected
adopted proposal
```

Use these question mappings:

```text
Was this TDoc discussed?       → DISCUSSION
What did this TDoc propose?    → CONTRIBUTION
What was agreed about it?      → MEETING OUTCOME
What happened with this TDoc?  → all three sections
```

A contribution conclusion remains contribution-scoped. It is not a meeting
conclusion. A Chair Note reference remains discussion evidence. It is not a
meeting outcome.

## Content inspection and V0.9 boundary

Answering what a TDoc proposes, observes, or concludes requires its content. If
the body is absent, V0.8.1 marks content inspection as required and performs no
download. V0.9 may implement selective acquisition, normalization, indexing,
and extraction. Under that future policy, a request for technical TDoc content
authorizes inspection of the necessary body unless the user requests an
offline, metadata-only, or no-download workflow.

The current document model defines `CACHE` and `PINNED` retention. A future
on-demand workflow may retain a requested body as `CACHE` and explicitly promote
research-essential material to `PINNED`. V0.8.1 changes no retention behavior
and implements no automatic deletion.
