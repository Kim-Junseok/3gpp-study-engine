---
name: 3gpp-study
description: Build provenance-aware 3GPP RAN1/RAN2 candidate inventories and, only when explicitly requested, plan, fetch, and structurally normalize selected official TDocs through the Python core. Use for meeting/TDoc selection and factual extraction outcomes; not for proposal, agreement, or company-position analysis.
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
