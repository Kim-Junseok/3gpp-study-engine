# Study vocabulary

## Topic corpus completion

Normal completion output continues to use **Topic**, **Companies / TDocs**,
**Discussion**, **Contribution**, **Meeting outcome**, and **TDoc content
inspected**. Operational plan state names belong in provenance or developer
output.

Say that a bounded set of direct-corpus TDocs was inspected. Do not call the
topic semantically complete. `TDoc content inspected: Yes` means that current
contribution extraction ran successfully, including a valid zero-evidence
result. It does not mean the meeting agreed with the contribution.

## Topic and source terminology

Use these terms for a new-topic study:

| Term | Meaning |
|---|---|
| User term | Wording supplied by the researcher |
| Exact lexical variant | The same tokens with deterministic case, punctuation, or hyphen/space formatting |
| Source terminology candidate | A literal phrase observed near seed tokens in selected prepared sources; it is awaiting review |
| Accepted source term | A source phrase explicitly selected for direct retrieval |
| Related terminology | Diagnostic source wording kept outside the direct topic corpus |

Do not describe a source candidate as a synonym or equivalent concept. Default
output may say, “Source terminology observed: …” and then identify which terms
the inventory uses. Provenance output may show occurrence counts, locators,
retrieval-support scores, and identities.

For company lists, use source-bounded wording: “Within the selected meetings,
selected source snapshots, and accepted topic terminology profile, the
following Chair-note-associated TDocs were found.” Authorship metadata does not
establish support, opposition, or any other company stance.

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
the body is absent, the read-only view marks content inspection as required.
V0.9 performs selective acquisition only through the explicit completion
workflow. A direct request for the technical content of a specific TDoc may
authorize that action unless the user requests an offline, metadata-only, or
no-download workflow.

After successful normalization and contribution SemanticEvidence extraction,
the view changes to `TDoc content inspected: Yes`. This remains true when the
current rules extract zero qualifying statements. A failure or stale extraction
keeps the value `No`.

The document model defines `CACHE` and `PINNED` retention. V0.9 retains a newly
requested body as `CACHE` and uses `PINNED` only on explicit request. It does not
automatically delete or prune either state.
