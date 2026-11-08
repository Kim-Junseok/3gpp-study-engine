"""Local-only web orchestration. No source acquisition or paid model client lives here."""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pydantic import ValidationError

from threegpp.db import MetadataRepository
from threegpp.chair_notes import ChairNoteService
from threegpp.historical.rules import expand_numeric_range, meeting_order_key
from threegpp.report_sources import ReportSourceRequest, ReportSourceService
from threegpp.topics import (
    TopicBootstrapRequest, TopicBootstrapService, TopicProfileDecision,
    TopicProfileService, TopicTermState,
)
from threegpp_web.store import AppStore
from threegpp_web.fixtures import FIXTURE_MARKER


DEFAULT_LIMITS = {
    "max_meetings": 3, "max_sources": 20, "max_input_tokens": 32768,
    "max_output_tokens": 8192, "timeout_seconds": 180,
    "max_passages_per_source": 80, "context_blocks": 3, "max_passage_chars": 12000,
}
CHANNELS = ("contribution_sources", "discussion_sources", "meeting_outcome_sources")


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def _atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")
    os.replace(temporary, path)


def _human_locator(passage):
    locator = re.sub(r"; normalized reading order \d+$", "", passage.get("locator", ""))
    numbered_label = re.search(r"\b\d+\b", passage.get("source_native_label") or "")
    if not passage.get("heading") and not numbered_label and not re.search(r"; (page|sheet) ", locator):
        locator += "; 원문: " + passage.get("literal_text", "")[:100]
    return locator


_PRIVATE_DIAGNOSTIC = re.compile(
    r"(?<![:/\w])/(?!/)[^\s]+|\b[A-Za-z]:[\\/]|\b[a-fA-F0-9]{64}\b|"
    r"(?:topic-profile|topic-bootstrap|topic-term|semantic-evidence|source-unit|review|corpus)[-_][a-f0-9]{16,}")


def _human_gap(gap):
    """Do not send source-reader exception paths or engine identities to readers."""
    gap = dict(gap)
    for key in ("reason", "details"):
        if key not in gap:
            continue
        value = gap[key]
        if isinstance(value, list):
            gap[key] = ["원문 처리 상세를 확인하지 못했습니다. 자료 복원 검증 결과를 확인하세요."
                        if isinstance(item, str) and _PRIVATE_DIAGNOSTIC.search(item) else item
                        for item in value]
        elif isinstance(value, str) and _PRIVATE_DIAGNOSTIC.search(value):
            gap[key] = "원문을 검증하거나 읽지 못했습니다. 자료 복원 검증 결과를 확인하세요."
    if isinstance(gap.get("source"), str) and _PRIVATE_DIAGNOSTIC.search(gap["source"]):
        gap["source"] = "준비된 원문"
    if isinstance(gap.get("locator"), str):
        gap["locator"] = re.sub(r"; normalized reading order \d+$", "", gap["locator"])
    return gap


class ResearchBackend:
    def __init__(self, data_root, state_root, *, limits=None, fixture_mode=False,
                 report_writer=None):
        self.data_root = Path(data_root).resolve()
        self.state_root = Path(state_root).resolve()
        if self.state_root == self.data_root or self.state_root.is_relative_to(self.data_root):
            raise ValueError("application state must be stored outside the research corpus")
        self.limits = {**DEFAULT_LIMITS, **(limits or {})}
        if any(not isinstance(value, int) or value < 1 for value in self.limits.values()):
            raise ValueError("MVP operating limits must be positive integers")
        self.fixture_mode = bool(fixture_mode)
        if not self.fixture_mode and (self.data_root / FIXTURE_MARKER).exists():
            raise ValueError("검증용 fixture 자료는 실제 연구 모드에서 사용할 수 없습니다. fixture 모드를 명시하세요.")
        if report_writer is not None and not self.fixture_mode:
            raise ValueError("Stage A only permits an explicitly enabled fixture report writer")
        self.report_writer = report_writer
        self.store = AppStore(self.state_root)
        self.store.recover()
        self._run_lock = threading.Lock()

    @property
    def database_path(self):
        return self.data_root / "metadata.duckdb"

    @contextmanager
    def _repository(self):
        """Treat restored SQL catalogs as data, never as an external reader.

        DuckDB's read_only flag protects database writes but still permits a
        stored view or macro to call external file/network table functions.
        Disable that capability before inspecting any user-defined object.
        The engine schema uses base tables; user-defined views are unsupported.
        """
        with MetadataRepository(self.database_path, read_only=True) as repository:
            repository.connection.execute("SET enable_external_access=false")
            repository.connection.execute("SET autoload_known_extensions=false")
            repository.connection.execute("SET autoinstall_known_extensions=false")
            views = repository.connection.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_catalog=current_database() AND table_schema='main' "
                "AND table_type <> 'BASE TABLE'").fetchall()
            if views:
                raise ValueError("연구 DB에 지원하지 않는 SQL view가 있습니다. 원본 자료의 복원 검증을 확인하세요.")
            yield repository

    def availability(self):
        exists = self.database_path.is_file()
        return {"database_present": exists, "fixture_mode": self.fixture_mode,
                "model_enabled": False,
                "message": ("준비된 로컬 자료를 읽습니다. 완전한 자료 범위를 뜻하지 않습니다."
                            if exists else "연구 DB와 준비된 원문이 없습니다. 자료를 복원해야 합니다.")}

    def create_task(self, question, parent_id=None):
        question = str(question).strip()
        if not question or len(question) > 10000:
            raise ValueError("질문은 1자 이상 10,000자 이하로 입력하세요.")
        if parent_id:
            self.get_task(parent_id)
        return self.store.new_task(question, parent_id)

    def get_task(self, task_id):
        return self.store.get_task(task_id)

    def list_tasks(self):
        return self.store.list_tasks()

    def _scope(self, values):
        terms = values.get("user_terms", [])
        if isinstance(terms, str):
            terms = [term.strip() for term in terms.splitlines() if term.strip()]
        if not isinstance(terms, list) or len(terms) > 20:
            raise ValueError("원문 용어를 줄마다 입력하세요. MVP 운영 한도는 20개입니다.")
        interpretation = values.get("interpretation", "")
        if interpretation not in {"meeting", "time", "release_comparison"}:
            raise ValueError("‘이후’의 의미를 회의 범위 또는 시간 기준으로 확인하세요.")
        if interpretation == "release_comparison":
            raise ValueError("자동 릴리스 비교는 첫 버전에서 지원하지 않습니다. 명시적인 회의 범위를 정하세요.")
        as_of = str(values.get("corpus_as_of", "")).strip()
        if not as_of or len(as_of) > 200:
            raise ValueError("사용할 자료 사본·snapshot의 기준을 입력하세요.")
        time_boundary = str(values.get("time_boundary", "")).strip()
        if interpretation == "time" and (not time_boundary or len(time_boundary) > 300):
            raise ValueError("시간 기준의 ‘이후’에 사용할 명시적인 기준점을 입력하세요.")
        group = str(values.get("working_group", values.get("wg", ""))).upper()
        if group not in {"RAN1", "RAN2"}:
            raise ValueError("첫 버전은 RAN1 또는 RAN2 한 개 WG를 지원합니다.")
        if any(len(str(term)) > 300 for term in terms):
            raise ValueError("원문 용어 하나는 300자 이하로 입력하세요.")
        try:
            request = TopicBootstrapRequest(
                working_group=group, from_meeting=str(values.get("from_meeting", "")),
                to_meeting=str(values.get("to_meeting", "")), user_terms=terms,
                max_meetings=self.limits["max_meetings"])
        except (ValidationError, ValueError, KeyError):
            raise ValueError("WG·회의 범위·원문 용어를 확인하세요.") from None
        minimum_count = meeting_order_key(request.to_meeting)[0] - meeting_order_key(request.from_meeting)[0] + 1
        if minimum_count > self.limits["max_meetings"]:
            raise ValueError("회의 수가 설정된 MVP 운영 한도를 넘습니다. 범위를 좁히세요.")
        return {"working_group": request.working_group.value,
                "from_meeting": request.from_meeting, "to_meeting": request.to_meeting,
                "user_terms": request.user_terms, "interpretation": interpretation,
                "corpus_as_of": as_of, "time_boundary": time_boundary}

    def save_scope(self, task_id, scope):
        task = self.get_task(task_id)
        task["scope"] = self._scope(scope)
        task["revision"] += 1
        task["status"] = "draft"
        task["approval"] = task["preview"] = None
        return self.store.save_task(task)

    def _bootstrap(self, scope):
        request = TopicBootstrapRequest(
            working_group=scope["working_group"], from_meeting=scope["from_meeting"],
            to_meeting=scope["to_meeting"], user_terms=scope["user_terms"],
            max_meetings=self.limits["max_meetings"])
        with self._repository() as repository:
            meetings = expand_numeric_range(request.from_meeting, request.to_meeting,
                                           repository.list_known_meetings(request.working_group))
            if len(meetings) > self.limits["max_meetings"]:
                raise ValueError("회의 수가 설정된 MVP 운영 한도를 넘습니다. 범위를 좁히세요.")
            result = TopicBootstrapService(repository, self.data_root).bootstrap(request)
        return result, meetings

    @staticmethod
    def _term(term):
        return {"literal_text": term.literal_text, "state": term.state.value,
                "meetings": term.meetings, "organizations": term.candidate_organizations,
                "occurrences": [{"literal_text": item.literal_text,
                    "meeting": item.locator.meeting,
                    "source_type": item.locator.source_type.value,
                    "tdoc": item.locator.associated_tdoc_id,
                    "member": item.locator.member} for item in term.occurrences]}

    def preview_scope(self, task_id):
        task = self.get_task(task_id)
        if not task["scope"]:
            raise ValueError("먼저 조사 범위를 저장하세요.")
        availability = self.availability()
        if not availability["database_present"]:
            preview = {"status": "needs_data", "availability": availability,
                       "meetings": [], "terms": [], "candidates": [],
                       "coverage": {}, "limitations": [availability["message"]]}
        else:
            try:
                result, meetings = self._bootstrap(task["scope"])
            except ValueError as exc:
                # Only intentional operating-limit messages are safe for readers.
                if "MVP" in str(exc):
                    raise
                raise ValueError("준비된 자료·회의 범위·프로필 정의를 확인할 수 없습니다.") from None
            except Exception:
                raise ValueError("연구 DB를 읽지 못했습니다. 복원 검증 결과를 확인하세요.") from None
            terms = [self._term(term) for term in result.terms]
            preview = {"status": "scope_ready", "availability": availability,
                       "meetings": meetings, "terms": terms,
                       "candidates": [term for term in terms if term["state"] == "source_candidate"],
                       "coverage": result.source_coverage.model_dump(mode="json"),
                       "limitations": result.limitations,
                       "_bootstrap_identity": result.bootstrap_id}
        task["preview"] = preview
        if task["approval"] and task["approval"]["bootstrap_identity"] != preview.get("_bootstrap_identity"):
            task["approval"] = None
        if not task["approval"]:
            task["status"] = preview["status"]
        self.store.save_task(task)
        return {key: value for key, value in preview.items() if not key.startswith("_")}

    def approve_scope(self, task_id, *, accepted_terms=(), related_terms=(), rejected_terms=(),
                      confirmed=False, expected_revision=None):
        task = self.get_task(task_id)
        if not confirmed:
            raise ValueError("조사 범위와 원문 용어를 확인한 뒤 승인하세요.")
        if expected_revision is not None and int(expected_revision) != task["revision"]:
            raise ValueError("범위가 변경됐습니다. 현재 범위를 다시 확인하세요.")
        if not task["scope"] or not task["preview"] or task["preview"]["status"] != "scope_ready":
            raise ValueError("준비된 자료의 범위 미리보기를 먼저 확인하세요.")
        result, meetings = self._bootstrap(task["scope"])
        if result.bootstrap_id != task["preview"].get("_bootstrap_identity"):
            raise ValueError("자료나 용어 후보가 변경됐습니다. 범위를 다시 확인하세요.")
        candidate_terms = {term.literal_text for term in result.terms
                           if term.state in {TopicTermState.SOURCE_CANDIDATE, TopicTermState.RELATED_ONLY}}
        for values in (accepted_terms, related_terms, rejected_terms):
            if any(term not in candidate_terms for term in values):
                raise ValueError("직접 읽은 자료에 표시된 용어 후보만 결정할 수 있습니다.")
        with self._repository() as repository:
            profiles = TopicProfileService(repository, self.data_root)
            profile = profiles.create(result)
            # Validate all decisions before persisting either profile revision.
            decision = TopicProfileDecision(profile_id=profile.profile_id,
                accept=list(accepted_terms), related=list(related_terms), reject=list(rejected_terms))
            profiles.persist(profile)
            if accepted_terms or related_terms or rejected_terms:
                profile = profiles.update(decision)
        semantic_approval = {"scope": task["scope"],
            "profile_id": profile.profile_id, "bootstrap_identity": result.bootstrap_id,
            "meetings": meetings, "accepted_terms": sorted(set(accepted_terms)),
            "related_terms": sorted(set(related_terms)), "rejected_terms": sorted(set(rejected_terms))}
        approval_identity = _digest(semantic_approval)
        prior_approval = task["approval"]
        if prior_approval is None:
            latest = self.store.latest_job(task_id)
            if latest and latest["revision"] == task["revision"]:
                prior_approval = latest["approved_scope"]
        prior_identity = task.get("approved_identity")
        prior_revision = task.get("approved_identity_revision")
        if prior_identity is None and prior_approval is not None:
            prior_identity = _digest({key: value for key, value in prior_approval.items() if key != "revision"})
            prior_revision = prior_approval["revision"]
        # A revision is immutable once approved. A source refresh or changed
        # checkbox decision must never reuse a job created for another profile.
        if prior_revision == task["revision"] and prior_identity != approval_identity:
            task["revision"] += 1
        unchanged = (task["approval"] is not None
                     and prior_identity == approval_identity)
        task["approval"] = {**semantic_approval, "revision": task["revision"]}
        task["approved_identity"] = approval_identity
        task["approved_identity_revision"] = task["revision"]
        if not unchanged:
            task["status"] = "approved"
        return self.store.save_task(task)

    def enqueue(self, task_id, *, retry=False):
        task = self.get_task(task_id)
        if not task["approval"] or task["approval"]["revision"] != task["revision"]:
            raise ValueError("현재 조사 범위를 먼저 승인하세요.")
        job = self.store.create_job(task, retry=retry)
        self.store.set_task_status(task_id, task["revision"], job["status"])
        return job

    def get_job(self, job_id):
        return self.store.get_job(job_id)

    def latest_job(self, task_id):
        job = self.store.latest_job(task_id)
        return self.get_job(job["id"]) if job else None

    def list_jobs(self, task_id):
        self.get_task(task_id)
        return self.store.list_jobs(task_id)

    def _result_path(self, job_id):
        if not re.fullmatch(r"[a-f0-9]{32}", job_id):
            raise KeyError("job not found")
        return self.state_root / "results" / job_id / "result.json"

    def result(self, job_id):
        self.get_job(job_id)
        path = self._result_path(job_id)
        return json.loads(path.read_text(encoding="utf8")) if path.is_file() else None

    def _public_bundle(self, bundle, job_id):
        data = bundle.presentation()
        assets = {}
        index = 0
        for channel in CHANNELS:
            for source, original_source in zip(data[channel], getattr(bundle, channel)):
                index += 1
                source["key"] = f"source-{index}"
                source["channel"] = channel
                for passage in source["passages"]:
                    for part in [passage] + passage["surrounding_context"]:
                        part["locator"] = part["human_locator"] = _human_locator(part)
                links = source["source"]
                public_links = {"official_url": links.get("official_url")}
                official = public_links["official_url"]
                if official and urlsplit(official).scheme not in {"http", "https"}:
                    public_links["official_url"] = None
                expected = {"normalized_local": original_source["audit"].get("normalized_checksum"),
                            "raw_local": original_source["audit"].get("raw_checksum")}
                if channel != "discussion_sources":
                    with self._repository() as repository:
                        receipt = repository.get_document_receipt(
                            source["tdoc"], bundle.topic["working_group"],
                            source.get("discovery_meeting", source.get("meeting")))
                    if receipt:
                        raw = (self.data_root / "raw" / "tdocs" / receipt.working_group.value.lower()
                               / receipt.meeting / receipt.tdoc_id / receipt.raw.filename)
                        if raw.is_file():
                            links["raw_local"] = str(raw)
                        if receipt.normalized_path:
                            normalized = self.data_root / receipt.normalized_path
                            links["normalized_local"] = str(normalized)
                        expected["raw_local"] = receipt.raw.sha256
                else:
                    selection = ChairNoteService(self.data_root).select(
                        bundle.topic["working_group"], source["meeting"],
                        original_source["audit"]["snapshot_id"])
                    if selection.selected_snapshot:
                        selected = selection.selected_snapshot
                        expected["raw_local"] = selected.raw_sha256
                        if selected.raw_path:
                            links["raw_local"] = str(self.data_root / selected.raw_path)
                        if selected.normalized_path:
                            links["normalized_local"] = str(self.data_root / selected.normalized_path)
                for kind in ("raw_local", "normalized_local"):
                    value = links.get(kind)
                    if not value:
                        continue
                    original = Path(value)
                    path = original.resolve()
                    safe = path.is_relative_to(self.data_root) and path.is_file() and not original.is_symlink()
                    digest = hashlib.sha256(path.read_bytes()).hexdigest() if safe else None
                    if not safe or not expected[kind] or digest != expected[kind]:
                        data["evidence_gaps"].append({"source": source.get("tdoc", source.get("selected_chair_note")),
                            "reason": "local source is outside the restored corpus; download unavailable"})
                        continue
                    asset_id = f"asset-{len(assets)+1}"
                    assets[asset_id] = {"relative_path": str(path.relative_to(self.data_root)),
                        "sha256": expected[kind], "filename": path.name}
                    public_links[kind.replace("_local", "_asset")] = f"/sources/{job_id}/{asset_id}"
                source["source"] = public_links
        # Keep private file paths and checksums out of browser-facing results.
        data["evidence_gaps"] = [_human_gap(gap) for gap in data["evidence_gaps"]]
        _atomic_json(self._result_path(job_id).with_name("assets.json"), assets)
        return data

    def resolve_asset(self, job_id, asset_id):
        result = self.result(job_id)
        if result is None:
            raise KeyError("source not found")
        path = self._result_path(job_id).with_name("assets.json")
        assets = json.loads(path.read_text(encoding="utf8")) if path.is_file() else {}
        if asset_id not in assets:
            raise KeyError("source not found")
        item = assets[asset_id]
        original = self.data_root / item["relative_path"]
        resolved = original.resolve()
        if (not resolved.is_relative_to(self.data_root) or not resolved.is_file()
                or original.is_symlink()
                or hashlib.sha256(resolved.read_bytes()).hexdigest() != item["sha256"]):
            raise ValueError("출처 파일이 변경되었거나 검증할 수 없습니다.")
        return resolved, item["filename"]

    @staticmethod
    def model_packet(bundle, question):
        sources = []
        for channel in CHANNELS:
            for source in bundle[channel]:
                sources.append({"key": source["key"], "channel": channel,
                    "tdoc": source.get("tdoc"), "organizations": source.get("organizations", []),
                    "meeting": (source.get("authority_meeting") if channel == "meeting_outcome_sources"
                                else source.get("meeting")),
                    "authority_meeting": source.get("authority_meeting"),
                    "discovery_meeting": source.get("discovery_meeting", source.get("meeting")),
                    "passages": source["passages"]})
        return {"question": question, "sources": sources,
                "evidence_gaps": bundle["evidence_gaps"], "coverage": bundle["coverage"]}

    @staticmethod
    def _validate_fixture_report(report, bundle):
        if not isinstance(report, dict) or not isinstance(report.get("claims"), list):
            raise ValueError("fixture report must contain structured claims")
        known = {source["key"]: source for channel in CHANNELS for source in bundle[channel]}
        for claim in report["claims"]:
            if not isinstance(claim.get("text"), str) or not claim["text"].strip() or not claim.get("sources"):
                raise ValueError("every fixture claim requires text and source citations")
            for citation in claim["sources"]:
                if citation not in known:
                    raise ValueError("report citation does not resolve to a source actually read")
        return {**report, "fixture_only": True, "human_review_pending": True,
                "notice": "검증용 fixture 결과입니다. 실제 연구 보고서가 아닙니다."}

    def run_job(self, job_id):
        with self._run_lock:
            job = self.store.claim_job(job_id)
            if job is None:
                return self.get_job(job_id)
            try:
                self.store.add_event(job_id, "validating", "승인된 범위와 준비된 원문을 읽기 전용으로 확인합니다.")
                if not self.database_path.is_file():
                    self._finish(job, "needs_data", "연구 DB가 없습니다. 자료를 복원한 뒤 명시적으로 재시도하세요.")
                    return self.get_job(job_id)
                approval = job["approved_scope"]
                current, meetings = self._bootstrap(approval["scope"])
                if (current.bootstrap_id != approval["bootstrap_identity"]
                        or meetings != approval["meetings"]):
                    self._finish(job, "failed", "자료 범위가 승인 이후 변경됐습니다. 범위를 다시 확인하고 승인하세요.")
                    return self.get_job(job_id)
                with self._repository() as repository:
                    bundle = ReportSourceService(repository, self.data_root).build(ReportSourceRequest(
                        profile_id=approval["profile_id"],
                        max_passages_per_source=self.limits["max_passages_per_source"],
                        context_blocks=self.limits["context_blocks"],
                        max_passage_chars=self.limits["max_passage_chars"]))
                document_count = sum(len(getattr(bundle, channel)) for channel in CHANNELS)
                public = self._public_bundle(bundle, job_id)
                question = self.get_task(job["task_id"])["question"]
                packet = self.model_packet(public, question)
                # Byte count is an explicitly conservative bound, not an asserted
                # model tokenizer measurement. No model is enabled in Stage A.
                upper_bound = len(json.dumps(packet, ensure_ascii=False).encode("utf8"))
                result = {"fixture_mode": self.fixture_mode, "bundle": public, "report": None,
                    "validation": {"local_source_links_checked": True, "official_links_live_checked": False,
                                   "content_accuracy_reviewed": False,
                                   "stage_b_accepted": False},
                    "model_input": {"token_upper_bound": upper_bound,
                        "count_method": "UTF-8 bytes; conservative bound, not exact model token count",
                        "calculation_basis": "selected literal passages plus required context and report envelope",
                        "limit": self.limits["max_input_tokens"], "model_calls": 0}}
                if document_count > self.limits["max_sources"]:
                    _atomic_json(self._result_path(job_id), result)
                    job["result_available"] = True
                    self._finish(job, "scope_limit", "문서 수가 설정된 MVP 운영 한도를 넘습니다. 임의로 제외하지 않았습니다.")
                elif not any(source["passages"] for channel in CHANNELS for source in public[channel]):
                    _atomic_json(self._result_path(job_id), result)
                    job["result_available"] = True
                    self._finish(job, "needs_data", "보고서를 뒷받침할 읽을 수 있는 원문 구절이 없습니다.")
                elif upper_bound > self.limits["max_input_tokens"]:
                    _atomic_json(self._result_path(job_id), result)
                    job["result_available"] = True
                    self._finish(job, "scope_limit", "원문과 필요한 문맥이 입력 예산을 넘습니다. 누락하거나 조용히 잘라내지 않았습니다.")
                elif self.report_writer is None:
                    _atomic_json(self._result_path(job_id), result)
                    job["result_available"] = True
                    self._finish(job, "sources_ready", "원문 검토 준비가 완료됐습니다. 모델은 비활성화되어 보고서를 작성하지 않았습니다.")
                else:
                    self.store.add_event(job_id, "fixture_report", "네트워크 없는 fixture 작성기로 화면 흐름만 검증합니다.")
                    report = self.report_writer(packet)
                    result["report"] = self._validate_fixture_report(report, public)
                    _atomic_json(self._result_path(job_id), result)
                    job["result_available"] = True
                    self._finish(job, "completed", "검증용 fixture 결과를 저장했습니다. 실제 연구 검증은 대기 상태입니다.")
            except Exception:
                self._finish(job, "failed", "작업을 완료하지 못했습니다. 자료·설정·출처 검증을 확인한 뒤 명시적으로 재시도하세요.")
            return self.get_job(job_id)

    def _finish(self, job, status, message):
        job["status"] = status
        job["error"] = message if status in {"failed", "needs_data", "scope_limit"} else None
        self.store.save_job(job)
        self.store.add_event(job["id"], status, message)
        self.store.set_task_status(job["task_id"], job["revision"], status)
