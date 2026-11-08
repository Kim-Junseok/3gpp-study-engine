# Research report guide

An ordinary research report explains what inspected sources say about the
researcher's question. The Python core supplies validated passages and source
references. The Skill organizes them into readable technical prose. This V0.13.1
workflow does not add organization-level stance or proposition-evolution analysis.

## Choose the workflow

| User request | Read path | Result |
|---|---|---|
| Explain a topic, summarize contributions, compare technical mechanisms, or write a report | `report-sources --profile <id>` | Technical explanation with human-readable sources |
| What happened with a TDoc; what was discussed or agreed? | `show-tdoc-study`, prepared discussion sources, and authoritative meeting sources | Independent Discussion, Contribution, and Meeting outcome answers |
| Prepare propositions or record a supplied proposition/relation decision | Existing V0.12/V0.13 commands | Literal persistent review units and explicit decisions |
| Show exact evidence, stored annotations, IDs, hashes, or review history | Requested audit/provenance output | Separate technical audit artifact |

Do not require proposition preparation, relation review, or an extra approval
round for ordinary report writing. A request to summarize or compare sources
does not authorize writing review decisions. An existing report-writing
authorization does not authorize source acquisition or terminology expansion.

## Source eligibility

A source passage may support a general research report when its literal content
and required context have been successfully read and validated.

`SemanticEvidence`, `AcceptedProposition`, and `PropositionRelation` states may
improve navigation or analysis, but none is a prerequisite for inclusion in a
general research report. Absent reviews, deferred candidates, or zero extracted
statements do not exclude otherwise readable source passages. Conversely, a
stored acceptance label cannot make an unreadable or stale source usable.

Read the actual passage and the context needed to interpret it. A title,
organization, matching keyword, raw ZIP, or document receipt alone cannot support
a technical summary. A successfully read normalized passage can support one
without a proposition review. If a passage is partial, use only the portion
whose meaning is established with its conditions intact. If missing text could
change that meaning, leave the affected claim as an evidence gap.

The direct topic scope still comes from researcher terms, deterministic lexical
variants, and explicitly accepted source terminology. Report editing does not
accept new terms or expand the corpus through synonyms. For a new topic, use the
existing bootstrap/profile workflow before applying this report read path.

## Three independent source channels

| Channel | Source and permitted interpretation | Boundary |
|---|---|---|
| Company Contribution | Readable contribution passages explain what that document proposes, observes, concludes, or leaves open | Attribute claims to the contribution and its recorded organizations; do not infer a company-wide position |
| Meeting Discussion | A selected Chair Note provides its recorded topic context and literal TDoc associations | A reference does not establish support, agreement, adoption, or complete discussion coverage |
| Meeting Outcome | An authoritative report/minutes source supplies its literal meeting statement and qualifications | Preserve authority meeting and disposition; a document reference does not adopt every statement in that TDoc |

Missing discussion or outcome sources do not exclude an otherwise readable
contribution. A Chair Note `Agreement:` heading remains discussion context.
Likewise, a contribution that quotes a previous meeting agreement remains a
contribution account unless independently supported by an authoritative outcome
source. Keep discovery meeting separate from the meeting whose outcome a report
records. An absent explicit outcome reference is unknown, not rejection.

## Read a bounded source bundle

```bash
python -m threegpp.cli report-sources --profile <profile-id>
```

The bundle is input to report writing, not an automatically accepted research
conclusion. Its conceptual contract is:

| Bundle part | Required information |
|---|---|
| Topic / Coverage | Selected topic and meetings, source availability, selection bounds, and truncation |
| ContributionSources | TDoc, organizations, meeting, title, validated passages, necessary surrounding context, explicit source-native labels, human-readable locators, raw/local/official source references |
| DiscussionSources | Meeting, selected Chair Note, matched section/context, literal associated TDocs, human-readable locator, source reference |
| MeetingOutcomeSources | Authority meeting, authoritative report/member, literal Agreement / Decision / Conclusion / FFS statement, qualifications/context, human-readable locator and source reference |
| EvidenceGaps | Affected source and unavailable, unreadable, unsupported, ambiguous, or truncated condition |
| Optional annotations | Existing review metadata, kept separate from source inclusion and source authority |

Selection returns relevant sections and necessary nearby context within explicit
bounds. It does not send whole documents to an LLM without limits. Read coverage
and truncation before treating the returned passages as sufficient. A successful
bounded read is not a claim to contain every relevant statement or document.
Never infer absence of a technical position from an omitted passage.

The default limits are 80 passages per source, three neighboring blocks on
either side within the same member and heading, and 12,000 characters per
passage. Use `--max-passages`, `--context-blocks` (up to 10), and
`--max-passage-chars` to inspect a larger bounded context. Character and passage
omissions are reported; these limits do not establish that all qualifications
have been read. The two local acceptance reports use `--context-blocks 10`.

Discussion reading also follows literal references to direct-inventory TDocs
within the selected Chair Notes. This exposes linked context without accepting
new topic terms. `associated_tdocs` retains exact-term structural associations;
`context_referenced_tdocs` lists identifiers literally present in the returned
context. The latter is not a new topic association or an adoption link. A TDoc
title joined to its identifier during normalization is matched using the
existing deterministic identifier boundary, while the returned text stays literal.

For topic outcomes, the reader starts at an explicit outcome label in a validated
authoritative report member. A neighboring Agreement does not promote a Proposal
paragraph into an outcome. The current reader handles explicit labels, including
`For further study`; it does not claim exhaustive discovery of every decision
expressed in unlabelled prose. Check the report coverage before describing a
missing outcome. Existing review annotations are not loaded automatically by this
command and remain available through their separate audit workflows.

This read path opens the existing database read-only. It does not create or
migrate a database, alter runtime artifacts, download source bytes, normalize
documents, index passages, extract evidence, or repair parsers. A missing source
remains a gap. Use separately authorized preparation commands when needed; do
not hide preparation inside reporting. In a local-only task, preserve all gaps
and perform no acquisition.

## Write the report

Start with the technical question and the findings supported by the selected
sources. Use technical-item sections when they help compare mechanisms. State
the inspected meeting/source scope briefly. Add meeting discussion and outcomes
where they answer the question, with each channel clearly attributed. The
three-channel authority rule does not require repeating three headings for every
technical item.

Prefer bullets for parallel findings, questions, alternatives, and company
claims. If an introduction announces three questions, present exactly three
question bullets. Use prose where a causal explanation benefits from connected
sentences; do not hide an enumeration in a paragraph.

Describe coverage with the meetings, source types, and counts actually inspected.
Distinguish downloaded files from sources whose relevant content was read.
Avoid using "current local documents" alone as the scope: storage location does
not establish inspection or completeness. State Chair Note coverage separately
from the TDoc count, and distinguish company contributions from LS documents.

State the document-selection criteria in the report: meeting scope, literal
terms and allowed formatting variants, discovery channels actually used,
readability requirements, and any ranking or document-count limits. Distinguish
metadata and Chair Note discovery from body-text search. Do not imply that all
available bodies were searched if they were read only after candidate selection.
Expose confirmed omissions and whether their technical content has been included.

Use the requested language. Faithful Korean paraphrase may shorten or explain a
source passage without changing its meaning. Preserve:

- the actor and exact organization attribution, including joint submissions;
- conditions, evaluation assumptions, qualifiers, and unresolved issues;
- numbers, units, comparison baselines, and limits;
- modality such as may, can, should, and further study;
- alternatives and the parent wording that makes them alternatives;
- the difference between an observation, a proposal, and a reported meeting act.

Use Proposal, Observation, Conclusion, FFS, Agreement, and Decision labels only
when explicitly present in the source. A parser's stored category is an audit
fact; it must not overwrite a readable source's explicit label in ordinary
prose. A label still carries only its document's authority. When no explicit
label exists, describe the passage without inventing one.

Keep the executive summary concise, but explain a compressed mechanism in its
technical-item section. When the sources support it, identify the sender and
receiver, what is transmitted or misinterpreted, and the consequence for the
procedure. State which signal or data object a qualifier applies to and what
error event a numerical target measures. Distinguish a condition from a cause,
a proposed target from an achieved result, and error prevention from subsequent
detection or recovery. Do not invent missing mechanisms to make an explanation
appear complete; expose the missing detail instead.

Compare source-backed mechanisms on the same technical dimension. For example,
if one passage specifies a scheduling DCI and another specifies a dedicated DCI,
describe those choices with sources for both. Do not turn the comparison into a
formal equivalence/conflict annotation or an inferred company position.
Grouping passages under a common question is report organization; it creates no
ontology entry, accepted source term, review decision, or meeting consensus.

Keep observation, mechanism, and interpretation distinct. A source's simulation
observation is that source's observation, not an independently reproduced result.
If an explanatory inference goes beyond direct restatement, identify it as an
interpretation and give the premises and limits. Do not fill absent conditions
from general domain knowledge and present them as source content.

## Human-readable sources and separate audit

Use the vocabulary in [STUDY_VOCABULARY.md](STUDY_VOCABULARY.md). A normal report
uses Company Contribution, Meeting Discussion, Meeting Outcome, Source, and
Open Issue / Evidence Gap. Korean explanations may accompany these labels.

Every technical claim must lead to its source. Cite a TDoc and an actual locator,
such as a section heading, numbered Proposal/Observation, table, or page when
available. Include organization and meeting in the text or source index. Link
the official source and/or a validated local copy. If the local file is a ZIP,
identify the real member filename; do not invent an extracted-file path. Where
no section or page exists, identify the member and a short distinctive literal
excerpt as the locator. Do not invent page numbers.

Place each citation immediately after the sentence it supports, including in
executive-summary bullets. Make the company, TDoc, and source locator visible
at the claim. Do not collect sources for different claims at the end of a
paragraph. Group citations only when they support the same stated claim with
compatible qualifiers; shared subject matter alone is insufficient. Preserve
each source's Proposal, Observation, or Conclusion label and authority when
grouping citations.

Encode spaces and literal `#` characters in Markdown link targets. Validate the
URL-decoded path, so a Chair Note filename does not become a fragment identifier.

For example, a human source entry can contain:

```text
vivo, R1-2603619, RAN1 #125, Proposal 1.
Official ZIP / local ZIP; member: R1-2603619 Discussion on fast ARQ.docx.
```

Use the actual source label and locator for each entry. The example is not a
substitute for inspecting that source. A readable source link should not require
the reader to understand a database identifier or evidence model.

Keep internal terms and IDs out of ordinary prose, tables, footnotes, and
appendices. In particular, omit SemanticEvidence, AcceptedProposition,
PropositionCandidate, PropositionRelation, TopicProfile, corpus/profile/review
IDs, SourceUnit, ruleset, checksum, SHA, and Git SHA. Full block identities,
source spans, hashes, extraction state, and review history belong in a physically
separate audit JSON file only when requested. `report-sources --profile <id>
--audit` exposes audit information without modifying runtime evidence. Store
requested report audit files under `reports/audit/`; do not append their contents
to the human report.

## Existing review records

Existing V0.12/V0.13 records are optional annotations. Their acceptance state
does not determine report source eligibility. Report writing neither creates
new decisions nor promotes explanatory prose into stored evidence.

Keep legacy records, exact spans, IDs, and history unchanged. A recorded review
ID does not itself establish who made a decision or whether the user explicitly
authorized it. In an audit, state the provenance that exists and leave the
reviewer or authorization unknown when absent. Do not silently relabel legacy
records as verified human review, and do not rewrite them to match new prose.

## Check the deliverable

Validate source links and read each technical summary against its literal
passage and required context. Confirm that readable source-backed content was
not excluded solely because extraction or proposition review was absent. Check
that discussion, contribution, and outcome statements keep their own authority.
Retain meaningful source gaps and bounded-coverage limitations in plain language.

Check the report without opening its audit file: the question, technical
findings, qualifications, and route to the original sources should be clear.
Code tests validate read behavior and source integrity. They do not prove the
quality or fidelity of Korean report prose. The rewritten Fast-ARQ and
Contention-based PUSCH reports are the V0.13.1 human acceptance examples.
