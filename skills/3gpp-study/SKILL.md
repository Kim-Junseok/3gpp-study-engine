---
name: 3gpp-study
description: Build a provenance-aware, metadata-only candidate inventory for a 3GPP RAN1/RAN2 research request using the repository's StudyRequest and Python core. Use for selecting meetings and candidate TDocs; not for document-body or agreement analysis.
---

# 3GPP Study

Turn the user's working groups, meetings, topics, organizations, and questions into the repository's canonical `StudyRequest`. Use [resources/study-request.example.yaml](resources/study-request.example.yaml) as the shape, validate it with `StudyRequest.from_yaml`, and preserve explicit meeting suffixes such as `bis`.

Use the Python core as the source of truth. The CLI is a thin operational interface:

1. Run `threegpp study-inventory --request <request.yaml>` to identify locally available and missing meetings using canonical current.
2. For each missing meeting or meeting without all-snapshot metadata, run `threegpp ingest-meeting --wg <WG> --meeting <ID> --enrich-tdocs`. This retrieves and parses official TDoc-list snapshots but never TDoc archives. If an accepted V0.2a.2 embedded-row manifest already exists, use `threegpp migrate-manifest --manifest <path>` instead; migration performs no source download.
3. Run the inventory again. Apply additional exact metadata filters through `TDocQuery` or `threegpp list-tdocs` when useful.
4. Return snapshot coverage, candidate count, HIGH/MEDIUM/LOW and availability counts, organization/meeting/agenda summaries, and candidates with title, strongest topic, level, separate anchor/supporting matched tokens, covered tokens, availability, status, and metadata source URL.

Use only the Python core's current normalized view and match evidence. Do not independently rescore candidates. Keep list-only records in results and distinguish meeting-close from current-consolidated snapshot coverage. If the user explicitly requests a meeting-close or exact stored snapshot, pass `--view meeting-close` or `--snapshot-url`; report its URL, checksum, role, timestamp, and request-selected status, then explicitly confirm that canonical current was not modified. Do not treat the selection as a persistent role or default.

Always label the result as official-metadata-only candidate discovery. State that V0.2a.3 has not read document bodies and cannot determine technical proposals, agreements, conclusions, company positions, or support/opposition. Never promote metadata labels or company authorship into those claims.
