# Source policy

Public 3GPP directories are the authoritative acquisition source for V0.2a.3. Source adapters own working-group paths, meeting-directory conventions, filename matching, and HTML parsing. Missing resources remain explicit and upload times are not treated as meeting dates.

Access is explicit, sequential, and bounded: descriptive User-Agent, timeout, retry/backoff, no recursive crawl, and no TDoc archive download. Default ingestion performs discovery only. `--enrich-tdocs` downloads all discovered official list spreadsheets; `--download-artifacts` is required for agenda/report files.

## Snapshot roles and views

All discovered lists are persisted and parsed independently. Filename evidence assigns one base role:

1. standalone `eom` or `final`: `MEETING_CLOSE`;
2. `TDoc_List_Meeting`: `CURRENT_CONSOLIDATED`;
3. another parseable filename timestamp: `HISTORICAL`;
4. otherwise: `UNKNOWN`.

Canonical current prefers current-consolidated, then meeting-close, then the latest historical snapshot, then a lexical fallback. The meeting-close view independently chooses the latest timestamped meeting-close filename. URL breaks ties.

An exact URL selection is request-scoped. It retains and reports the snapshot's base role, URL, checksum, and timestamp plus `request_selected=true`; it does not add a persistent role or replace canonical current. Ordinary candidate discovery always returns to canonical current after any meeting-close or historical query.

These deterministic filename rules do not assert that one snapshot is universally authoritative. Ordinary candidate discovery uses canonical current. Meeting-close questions may select the meeting-close snapshot, and an exact historical question may select that snapshot for only that operation. Every list remains separately recoverable for future evolution analysis.

### RAN2#131 live verification

Verified on 2026-09-05 with all four official lists parsed successfully and no warnings:

- `TDoc_List_Meeting_RAN2#131.xlsx`: current-consolidated, 1,617 rows, SHA-256 `5012401d71a8849fe5ba86278b0ee5ed3f5a3d64b6250a6a08dcfc8f4e902dea`.
- `tdocList_2025-08-29_13h12_eom.xlsx`: meeting-close at filename time `2025-08-29 13:12`, 1,432 rows, SHA-256 `d486de67756daf4f4173d9a1e5d4df34d04b1e44c349a262d2eff281526c4d64`.
- `tdocList_2025-09-02_14h28.xlsx`: historical at filename time `2025-09-02 14:28`, 1,445 rows, SHA-256 `0a510231c2253f8943afeac2bd3dcac0c465c6398d63da53af630ffb15c6f316`.
- `tdocList_2025-09-03_10h00.xlsx`: historical at filename time `2025-09-03 10:00`, 1,454 rows, SHA-256 `ffa4e248da8cd68962f0a77396e7360907bc338f9d355f0d4599f992089a0eff`.

The current list has 185 TDocs absent at meeting close and no meeting-close IDs absent from current. Among shared IDs, 241 statuses, 8 titles, and 20 raw source strings differ. The directory plus current-consolidated normalized view contains 1,618 TDocs. Filename timestamps carry no inferred timezone. No unexpected naming convention or TDoc-body download was observed.

### RAN2#131 V0.2a.3 storage and isolation verification

Verified on 2026-09-06 by explicitly migrating the accepted V0.2a.2 receipt, with no network retrieval:

- embedded-row V0.2a.2 manifest: 40,959,955 bytes;
- slim V0.2a.3 manifest: 24,989 bytes;
- four normalized snapshot files: 853,879 bytes total;
- canonical current normalized file: 257,109 bytes for 1,618 rows;
- DuckDB query store: 101,462,016 bytes.

All four raw spreadsheet SHA-256 values above and the old manifest SHA-256 remained unchanged. Hydration restored 1,617 current-consolidated, 1,432 meeting-close, 1,445 and 1,454 historical snapshot rows, plus the 1,618-row canonical view.

The read sequence canonical (1,618) → historical `2025-09-03_10h00` (1,454) → meeting-close (1,432) → historical (1,454) → canonical (1,618) left the canonical DB digest, normalized-current SHA-256 `28bfddff624469b437f2b67f817857bf72b38e6fca0d819a1228bec60e64911e`, and slim-manifest SHA-256 unchanged. For topic `multihop relay`, metadata matching returned one HIGH and 60 MEDIUM candidates. `R2-2505175`, whose related-WI alone contains both tokens while its anchors do not, was correctly rejected. No TDoc body was retrieved or analyzed.

## Spreadsheet formats

Current inspected RAN1/RAN2 files are OOXML XLSX and are read with `openpyxl`. Legacy binary XLS is read with `xlrd`. The parser scans sheets and the first 25 rows for recognized aliases, stops after a bounded empty tail, reports unmapped rows/unknown columns, and never invents absent fields.
