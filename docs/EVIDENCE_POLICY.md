# Evidence policy

## V0.9 contribution inspection

Metadata, a title, organization attribution, Chair Note context, and
meeting-outcome text do not establish what a contribution itself proposes,
observes, concludes, or leaves for further study. Only fresh
contribution-scoped SemanticEvidence extracted from inspected contribution
content may populate those categories.

A successful extraction with zero qualifying statements still establishes that
the available contribution content was inspected under the current rules. A
failed or stale extraction does not. On-demand preparation never promotes a
contribution statement to meeting authority.

## V0.8.1 research-facing wording

- Referenced in discussion does not mean agreed.
- Not observed in a selected Chair Note does not mean not discussed.
- No explicit meeting reference found does not mean rejected and does not prove
  that no meeting outcome exists.
- A contribution conclusion is not a meeting conclusion.
- Missing local contribution content does not mean that official metadata or
  the official TDoc is unavailable.

The canonical user-facing terms are defined in `STUDY_VOCABULARY.md`. Backend
states remain available through explicit provenance output.

## V0.8 explicit-link policy

An explicit TDoc reference establishes a document-level relationship. It does not automatically establish semantic equivalence between a meeting statement and every proposition in the referenced TDoc.

`SAME_TDOC` states that contribution SemanticEvidence belongs to its recorded parent TDoc. `DISCUSSION_REFERENCE` states that the selected Chair Note explicitly references the TDoc in a bounded discussion context. Meeting evidence links require a literal identifier inside accepted meeting-report/minutes SemanticEvidence. A disposition remains attached to that meeting evidence and is not projected onto contribution evidence.

Similar wording, a shared topic, one Chair Note section, or common authorship cannot create a link. Reply, revision, supersession, and cross-meeting continuity require literal source wording. An unresolved or ambiguous reference remains visible, and `NO_EXPLICIT_LINK` is not negative evidence.

Per-TDoc link status keeps Chair Note discussion, contribution SemanticEvidence, meeting explicit links, cross-meeting references, and source preparation separate. One missing or present dimension cannot overwrite another. In every dimension, `NO_EXPLICIT_LINK` describes inspected-source coverage only; it never establishes rejection, opposition, or absence of an underlying relationship.

The link graph does not contain company stance, support/opposition, semantic proposition clusters, or trend scores. Chair Note text labelled `Agreement:` remains discussion context and never becomes meeting SemanticEvidence through linkage.

## V0.7 historical boundaries

- Historical resolution adds official metadata provenance; it does not add discussion evidence. `METADATA_RELEVANT_ONLY` remains separate from `CHAIR_NOTE_CONFIRMED`.
- `124b -> 124bis` is identifier equivalence only. Source discovery preserves the literal official path. The alias does not make snapshots identical or assign authority.
- Chair Note meeting and TDoc metadata meeting remain separate. A later Chair Note reference establishes only that the selected later snapshot references the older TDoc.
- Such a reference does not establish continuity, continuing activity, acceptance, or an ongoing meeting outcome.
- Missing sources produce limitations, never a fabricated zero-discussion conclusion.
- Organization values and historical URLs come only from official metadata. Listed-only URLs are never synthesized.
- Historical coverage is lexical and structural. It performs no semantic similarity, proposal equivalence, company stance, consensus, or trend inference.

Discovery and byte retrieval are different events. A discovered-only artifact has `discovered_at` but null `retrieved_at`, `local_path`, and `checksum`. An actual download sets all three retrieval fields. The model rejects partial retrieval provenance.

Raw source bytes are immutable. A URL returning bytes that conflict with an existing local checksum raises an error instead of overwriting the file. Normalized metadata, manifests, and future extracted content remain separate from raw bytes.

Normalized JSONL.gz files are derived evidence representations, not official originals. Their compressed bytes are deterministic, and every reference carries a SHA-256 and row count checked on hydration. Content-addressed paths may be regenerated from the same normalized records; an existing path with conflicting bytes raises an error. Manifests are provenance receipts and do not duplicate complete datasets. DuckDB is a disposable/rebuildable query index, not a replacement for raw or portable normalized evidence.

Each spreadsheet-enriched field retains the exact TDoc-list URL, downloaded checksum, and source column. All non-empty row values remain in `raw_metadata`; unknown canonical values remain null. Every parsed snapshot also retains its complete normalized rows independently, so a current-value merge cannot erase historical status, title, source, or first-appearance evidence.

Snapshot roles express purpose, not a universal authority ordering. Meeting-close, current-consolidated, historical, and unknown roles remain distinct. A filename timestamp is stored without inventing a timezone. Request selection is recorded in operation output rather than persisted as an evidence role: it cannot alter canonical current rows, flags, normalized output, or receipts.

List membership and archive availability are separate facts. `official_list_present` records a row in the selected official list; `directory_present` plus an archive URL records a downloadable TDoc. List-only rows, including withdrawn entries, remain queryable and are never silently discarded.

Directory facts, official-list facts, document-content facts, and analytical inference must never be mixed silently. Authorship and status labels alone are not evidence of a meeting agreement.
# Document evidence

Downloaded bytes are official raw evidence and are never silently overwritten. `CACHE` is removable only by a future explicit retention workflow; `PINNED` must not be automatically pruned. No pruning is implemented. Normalized text is derived evidence and every receipt links it to the raw SHA-256, package member, parser/version, and stable block ID. Extracted wording is not itself classified as a proposal or meeting agreement in V0.2b.

# Retrieval evidence

A V0.3 hit is a lexically relevant evidence candidate, not a proposal, agreement,
support, or company-position conclusion. Every hit resolves to a current
normalized member and stable block ID. Search verifies the normalized checksum;
missing or changed files/blocks become stale and their postings are removed.
Snippets preserve literal source text and are non-authoritative bounded views.

# Explicit semantic evidence

V0.4 semantic evidence is derived analysis tied to one or more exact normalized
blocks. Literal statements are never paraphrased. A lexical hit is not semantic
evidence, and semantic evidence is not a cross-meeting trend.

Authority is role-gated. Company contributions may yield only contribution-scope
proposal, observation, conclusion, or FFS evidence, attributed exactly to stored
source organizations. Only a document deterministically classified as an ETSI MCC
RAN meeting report may yield meeting-scope agreement, conclusion, decision, or FFS
evidence; meeting evidence carries no company-position attribution. “We agree” or
an “Agreement” label in a contribution is never promoted to a meeting agreement.
Company proposal ≠ meeting agreement, and company conclusion ≠ meeting conclusion.

## V0.5 synthesis guards

- Discovery meeting is not necessarily authority meeting.
- Agreement is not adoption. “Agreed to study X” must not be shortened to “agreed X”; “study X” must never be rendered as “adopt X”.
- Context is not SemanticEvidence; absent bounded context does not prove no qualification exists elsewhere.
- A company contribution is not a meeting outcome. Meeting-report metadata source organization must not become company attribution.
- Similar wording is not proposal linkage. Only literal references are links.
- Absence of explicit adoption evidence does not mean rejection.

## V0.6 Chair Note authority

The official TDoc List defines the meeting document universe and official metadata. A selected Chair Note provides positive evidence only that it explicitly associates a referenced TDoc with the bounded recorded discussion context. Contribution bodies remain authoritative for company statements, while accepted reports/minutes remain authoritative for meeting agreements and decisions.

Chair-note-confirmed references are positive evidence that the selected Chair Note associates a TDoc with the recorded discussion context. Absence from the selected Chair Note snapshot is not proof that a TDoc was not discussed. `METADATA_RELEVANT_ONLY` means that metadata matched the topic but no positive association was extracted from this selected snapshot; it never means `NOT_DISCUSSED`.

Chair Note wording, including an `Agreement:` label, remains literal discussion/context source text and cannot become `AGREEMENT + MEETING`, `DECISION + MEETING`, or `CONCLUSION + MEETING` through the Chair Note path. Similar titles, organizations, and technical wording cannot create TDoc associations. Associations require a literal R1/R2 identifier inside a bounded matched section, with an exact `ChairNoteRef` and structural basis.

Each snapshot remains independent. EOM naming does not assert finality, snapshots are not silently unioned, and a later absence does not establish withdrawal. Unresolved references retain their literal identifier and source locator without fabricated title, organization, URL, availability, or meeting.
