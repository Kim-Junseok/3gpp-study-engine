# Study workflow

1. Express the task as a validated `StudyRequest` YAML.
2. Query a candidate inventory to identify locally available and missing meetings.
3. Discover missing meetings with safe default ingestion.
4. Explicitly run all-snapshot TDoc-list enrichment for meetings that need searchable metadata.
5. Query/filter by working group, meeting, title, organization, agenda, status, or TDoc ID.
6. Produce a metadata-only candidate inventory from canonical current, or explicitly request a stored meeting-close/historical snapshot without mutating canonical state.
7. Clearly report missing meetings, parse warnings, unknown columns, and that document bodies were not analyzed.

V0.2a.3 matching lowercases text, converts punctuation to spaces, deduplicates tokens, and removes common English stopwords.

- Anchor fields: `title`, `abstract`, `agenda_item_description`.
- Supporting fields: `related_work_item`, `document_type`, `status`, `release`, `specification`, `intended_for`.
- HIGH: every meaningful topic token occurs in one anchor field.
- MEDIUM: all meaningful topic tokens are covered across at least two fields, and anchor evidence includes at least one non-generic token.
- LOW: anchor fields cover at least two meaningful topic tokens and at least half of the topic tokens, including a non-generic token.

All levels therefore require specific anchor evidence. Supporting fields may complete or explain an anchored MEDIUM match but can never independently create a candidate. The tokens `3gpp`, `access`, `change`, `discussion`, `document`, `mode`, `radio`, `system`, `study`, and `update` are generic safeguards: a generic anchor token plus a complete supporting phrase is rejected.

Each candidate reports its strongest topic match, level, combined per-field tokens, separate anchor/supporting tokens, covered tokens, all qualifying topic matches, and availability. Optional organization selection remains exact and case-insensitive against conservatively split organizations. Questions are preserved but not answered.

Request-scoped results identify the exact snapshot URL, checksum, base role, filename timestamp, and selection status, and state `canonical_current_modified=false`. Such reads never import snapshot records as current or rewrite normalized files/manifests.

The Skill may coordinate this workflow, but `StudyRequest`, ingestion, parsing, filtering, and candidate selection remain Python-core responsibilities.
