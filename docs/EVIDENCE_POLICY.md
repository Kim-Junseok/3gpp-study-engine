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
