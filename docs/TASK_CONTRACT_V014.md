# TASK CONTRACT V0.14.0 — personal research web app

Status: first implementation authorized with the user's amendments on 2026-11-09 (Asia/Seoul). Main merge, tag, production deployment, source acquisition, and paid model calls are not authorized.

## Baseline and correction

- Remote main: `566d16845f540ce84b21587ef75a20e4d5f32ea8`, package 0.13.1. Development branch: `work/0.14.0-personal-web`.
- Existing core baseline: 396 tests passed in 22.30 seconds with external socket connections blocked; zero connection attempts. This is a newly executed baseline, not a historical CI claim.
- The initial checkout (`b95ccb6`, branch `work`) is preserved. Its branch name conflicts with the required `work/…` prefix, so implementation uses an independent local clone.
- Canonical technical writing guide: `$CODEX_HOME/TECHNICAL_WRITING_STYLE.md`. At inspection, CODEX_HOME was `/home/agent/.codex`; the guide was **not provided**. The earlier investigation omitted this check. `docs/RESEARCH_REPORT_GUIDE.md` and `docs/STUDY_VOCABULARY.md` were read but are separate instructions, not substitutes.
- The user may transfer the canonical guide as an attached file or include a tracked copy in the repository and identify it as canonical. Do not infer its contents. Its absence does not block independent Stage A work; record it as pending for prose acceptance.
- Runtime source data are absent: no research DuckDB, raw corpus, normalized corpus, manifests, or accepted topic profiles. Existing Markdown reports and synthetic fixtures are not a supplied research corpus.

## Goal and acceptance stages

Question → confirmed research scope/terminology → explicit run and progress → report/source reading → history/follow-up, usable on mobile.

**A — web implementation:** existing core integration, synthetic fixtures, empty data, failures, persistence/restart, authenticated source navigation, and offline transfer/restore tooling. If A passes, report exactly: “웹 기능 구현 완료, 실제 연구 검증 대기”. Never claim that the complete research app or real report fidelity has been validated.

**B — real research acceptance:** a user-supplied existing corpus plus an explicitly authorized real model, followed by source/claim review. No actual corpus or paid calls are available now. B remains pending independently of A.

The NTN question is a product example only. Do not research NTN or collect any sources for it.

## Inputs and limits

Fixed inputs: code baseline; fixed corpus/snapshot; approved scope revision; source-terminology decisions; model/prompt/pricing configuration when separately authorized.

Variable inputs: question, interpretation of “after Release-18”, WG/meeting range, corpus reference date, literal user terms, explicit source-term decisions. Derived outputs: local inventory, validated source bundle, gaps/coverage, job events, report revisions and follow-up links.

Defaults: one WG (RAN1 or RAN2), three meetings, twenty documents across all source channels, 32,768 input tokens and 8,192 output tokens per task across both possible model calls, 180-second timeout. These are **configurable MVP operating limits**, not engine limitations. Do not silently choose a top-N corpus or remove context to satisfy a limit. Model input accounting must include the actual passages, necessary context, source references and instructions; expose all omissions/truncation. With no selected model/tokenizer/pricing, live execution stays disabled.

“After Release-18” must be resolved as release comparison versus time-based intent. The current core does not implement release/date filtering. Require an explicit meeting range and corpus/snapshot reference. Automatic release comparison is outside A. A corpus reference date never claims complete coverage through that date.

## Reuse and boundaries

Use `MetadataRepository(read_only=True)`, `TopicBootstrapService`, `TopicProfileService`, `ReportSourceService.build`, `DocumentService.read_source`, and existing topic/source terminology rules. Do not shell arbitrary CLI commands from web inputs. Source reads never migrate, acquire, normalize, index, extract, repair, or create reviews. Explicit terminology approval may write an immutable profile revision; app history is separate persistent state.

Company contributions, selected Chair Note discussion, and authoritative meeting outcomes remain independent. A missing channel cannot exclude readable sources in another channel or supply authority. No company proposal becomes meeting agreement; no absence becomes rejection/non-discussion. Read literal source and necessary context, retain qualifiers/numbers/modality/organizations, and put real TDoc/company/locator citations near every claim. Proposition/relation preparation or review is not a report gate and is not performed. No vector search, embeddings, or LLM/agent framework.

## Implementation and screens

Python FastAPI + server-rendered responsive Korean screens and small local JavaScript. Separate SQLite app state and a single worker. Screens: login; question/history; scope/terminology approval; run/progress/failure; report and three independent source channels. Natural-language model assistance is separate from current core capabilities. Manual scope confirmation works without a model.

Default writer is disabled. A clearly labeled synthetic fixture writer may be injected only in explicit fixture mode for A tests; never present its output as a real research report. No production model network client is activated in A. A future live adapter requires model name, verified prices, budget reservation/enforcement, user's usage authorization and a secret provided through environment settings. Proposed model API budget (not hosting costs) remains $1/task and $10/month; no paid automatic retries. Unknown pricing or uncertain prior call completion blocks automatic execution.

Source URLs must be authenticated asset routes mapped to verified corpus files, or actual official URLs from the read receipts. Never expose server/laptop absolute paths or invent extracted ZIP member paths. Default reports hide internal identifiers/hashes; requested audit is a separate artifact. Local data are not sent to any model during A.

## Transfer, persistence and deployment

Prepare concrete offline `inspect`, `verify`, `pack`, `restore` commands, file/directory requirements, byte-size/disk-capacity measurements, transfer SHA-256 and original provenance validation. Do not assume direct laptop access. No new real corpus or source collection is authorized. Preserve source receipts unchanged; unsafe/nonportable/missing paths remain reported gaps. Restore into a new destination, validate checksums and refuse archive traversal, symlinks and overwrite.

Raw/normalized/manifests/source DB are fixed research inputs; profiles are versioned derived configuration; questions/approvals/jobs/reports/assets live in persistent app storage. After restart, in-flight work is interrupted and never automatically repeats a possibly charged call. Prepare stopped-app state backup/restore and test an independent restored environment.

Provider/domain/recurring backup schedule are deferred to deployment. Their absence must not block local work. Default service binds loopback and requires a configured password/session; external previews require access control and HTTPS boundary. No external service registration or deployment during A.

## Verification and stop conditions

A: existing 396 tests remain passing; at least 12 meaningful web scenarios; zero unauthorized source downloads/normalization/extraction/reviews or paid calls; source input bytes unchanged except explicitly approved profile settings; empty/missing/stale/unsupported/truncated data visible; no generated report for absent data; ten repeated starts yield one job; queued/running/completed restart retention; authenticated assets reject missing/tampered/outside-root paths; failure injection; restored state/source navigation; 360/390/1440-pixel browser checks with no page overflow and primary targets at least 44px.

B separately: validate all source links automatically. Then compare **every technical claim** in the actual acceptance report with literal source and required context, including conditions, quantities, organizations and authority. Report automatic checks separately from human review still needed. Link validity or Python tests alone never prove Korean prose fidelity. Canonical writing guide remains required input for this review.

Stop affected work and propose CONTRACT CHANGE if source meaning/authority would change, source acquisition/repair/new real corpus becomes necessary, supported WG/release-comparison scope expands, or authentication/context/cost boundaries cannot be maintained. Recheck meaningful main drift before rebaselining. Final acceptance precedes main fast-forward, annotated tag, and deployment.

## Evidence preservation

Keep contract, transfer/run instructions and architecture changes in the work branch. Preserve test commands, JUnit reports, browser captures and limitations as review artifacts. Keep source data, app DB, session material and reports out of Git; never log credentials. The inspection snapshot and original checkout are not durable production storage.
