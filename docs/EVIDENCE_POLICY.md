# Evidence policy

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
