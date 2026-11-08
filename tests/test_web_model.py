"""Mocked model-boundary tests. No credentials or network access are used."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import json
import sqlite3

import httpx
import pytest

from threegpp_web.model import BudgetLedger, ModelError, ModelPolicy, ReportModelAdapter


PACKET = {"question": "원문은 무엇을 제안하는가?", "sources": [{
    "key": "source-1", "channel": "contribution_sources", "tdoc": "SYNTHETIC",
    "organizations": ["Fixture Company"], "meeting": "125", "raw_local": "/private/raw.zip",
    "audit": {"secret": "do-not-send"}, "passages": [{
        "literal_text": "Proposal: Use the synthetic timer only after expiry.",
        "human_locator": "fixture.docx; Proposal 1",
        "audit": {"identity": "do-not-send"},
        "surrounding_context": [{"literal_text": "The condition applies only to the fixture.",
                                 "locator": "fixture.docx; Condition"}]}]}],
    "audit": {"secret": "do-not-send"}, "evidence_gaps": []}
REPORT = {"title": "검증용 보고서", "claims": [{"text": "이 문서는 만료 후의 동작을 제안한다.",
    "sources": ["source-1"], "citations": [{"source_key": "source-1", "passage_index": 0}]}]}


def active(**changes):
    return replace(ModelPolicy(model="synthetic-model", input_price_per_million="1",
        output_price_per_million="2", pricing_verified=True, pricing_reference="fixture prices only",
        usage_authorized=True, authorization_reference="mock test only", max_input_tokens=100,
        max_output_tokens=20), **changes)


def response(report=None, *, usage=None):
    return {"status": "completed", "output": [{"type": "message", "content": [{
        "type": "output_text", "text": json.dumps(REPORT if report is None else report)}]}],
        "usage": usage or {"input_tokens": 50, "output_tokens": 10}}


def adapter(tmp_path, handler, *, policy=None, counter=None, key="synthetic-test-key"):
    ledger = BudgetLedger(tmp_path / "budget.sqlite3")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return ReportModelAdapter(policy or active(), ledger, api_key=key,
        token_counter=counter or (lambda payload: 50), tokenizer_model="synthetic-model", client=client)


def test_disabled_default_never_calls_http_or_reserves_budget(tmp_path):
    calls = []
    model = adapter(tmp_path, lambda request: calls.append(request), policy=ModelPolicy())
    with pytest.raises(ModelError) as exc:
        model.write(PACKET, task_id="one")
    assert exc.value.code == "model_disabled" and not calls
    assert model.ledger.record("one:report") is None


@pytest.mark.parametrize("change", [
    {"pricing_verified": False}, {"pricing_reference": ""}, {"model": None},
    {"input_price_per_million": None}, {"input_price_per_million": "NaN"},
    {"output_price_per_million": "-1"}, {"authorization_reference": ""},
    {"timeout_seconds": 0}, {"max_output_tokens": True},
    {"pricing_reference": None}, {"model": 123}, {"timeout_seconds": True},
])
def test_incomplete_policy_refuses_before_network(tmp_path, change):
    calls = []
    model = adapter(tmp_path, lambda request: calls.append(request), policy=active(**change))
    with pytest.raises(ModelError) as exc:
        model.write(PACKET, task_id="one")
    assert exc.value.code == "setup" and not calls


def test_key_tokenizer_and_complete_input_are_required(tmp_path):
    calls = []
    model = adapter(tmp_path, lambda request: calls.append(request), key=None)
    with pytest.raises(ModelError):
        model.write(PACKET, task_id="one")
    model._api_key = "fixture-key"
    model._counter = None
    with pytest.raises(ModelError):
        model.write(PACKET, task_id="two")
    model._counter = lambda payload: 1
    model._tokenizer_model = "wrong-model"
    with pytest.raises(ModelError):
        model.write(PACKET, task_id="three")
    assert not calls


def test_success_preserves_context_counts_entire_request_and_reconciles(tmp_path):
    seen = []
    counted = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=response())
    def counter(payload):
        counted.append(payload)
        return 50
    model = adapter(tmp_path, handler, counter=counter)
    result = model.write(PACKET, task_id="one")
    assert len(seen) == len(counted) == 1
    payload = json.loads(seen[0].content)
    assert payload == counted[0] and payload["store"] is False and "tools" not in payload
    assert "only after expiry" in payload["input"][0]["content"]
    assert "condition applies" in payload["input"][0]["content"]
    assert "/private" not in seen[0].content.decode() and "do-not-send" not in seen[0].content.decode()
    assert "instructions" in counted[0] and "schema" in counted[0]["text"]["format"]
    assert result["human_review_pending"] is True
    assert result["automatic_validation"]["content_accuracy_reviewed"] is False
    record = model.ledger.record("one:report")
    assert record["status"] == "succeeded"
    assert Decimal(record["charged_usd"]) == Decimal("0.00007")
    assert b"synthetic-test-key" not in model.ledger.path.read_bytes()


def test_context_over_limit_does_not_truncate_or_call(tmp_path):
    calls = []
    model = adapter(tmp_path, lambda request: calls.append(request), counter=lambda payload: 101)
    with pytest.raises(ModelError) as exc:
        model.write(PACKET, task_id="one")
    assert exc.value.code == "context_limit" and not calls
    assert model.ledger.record("one:report") is None


@pytest.mark.parametrize("status,code", [(401, "auth"), (403, "auth"), (429, "rate_limit"),
                                         (500, "api_error"), (302, "api_error")])
def test_http_failure_is_sanitized_never_retried_and_reservation_remains(tmp_path, status, code):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, text="provider detail synthetic-test-key", headers={"Location": "https://other.invalid"})
    model = adapter(tmp_path, handler)
    with pytest.raises(ModelError) as exc:
        model.write(PACKET, task_id="one")
    assert exc.value.code == code and "synthetic-test-key" not in str(exc.value)
    assert len(calls) == 1
    row = model.ledger.record("one:report")
    assert row["status"] == "uncertain" and row["charged_usd"] == row["reservation_usd"]
    with pytest.raises(ModelError) as repeat:
        model.write(PACKET, task_id="one")
    assert repeat.value.code == "already_attempted" and len(calls) == 1


def test_timeout_keeps_reservation_after_new_adapter_and_ledger(tmp_path):
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("provider-key-should-not-leak", request=request)
    model = adapter(tmp_path, handler)
    with pytest.raises(ModelError) as exc:
        model.write(PACKET, task_id="one")
    assert exc.value.code == "timeout" and "provider-key" not in str(exc.value)
    restored = adapter(tmp_path, handler)
    with pytest.raises(ModelError) as repeat:
        restored.write(PACKET, task_id="one")
    assert repeat.value.code == "already_attempted" and len(calls) == 1


@pytest.mark.parametrize("mutate", [
    lambda report: report["claims"][0].update(sources=["unread-source"]),
    lambda report: report["claims"][0]["citations"][0].update(passage_index=99),
    lambda report: report["claims"][0]["citations"][0].update(passage_index=True),
    lambda report: report["claims"][0].update(citations=[]),
    lambda report: report["claims"][0].update(sources=[]),
])
def test_wrong_or_missing_citation_rejected_without_claiming_fidelity(tmp_path, mutate):
    report = json.loads(json.dumps(REPORT))
    mutate(report)
    model = adapter(tmp_path, lambda request: httpx.Response(200, json=response(report)))
    with pytest.raises(ModelError) as exc:
        model.write(PACKET, task_id="one")
    assert exc.value.code == "invalid_response"
    assert model.ledger.record("one:report")["status"] == "uncertain"


def test_malformed_json_incomplete_output_and_usage_are_rejected(tmp_path):
    bodies = [
        {**response(), "status": "incomplete"},
        {**response(), "output": []},
        response(usage={"input_tokens": 500, "output_tokens": 10}),
    ]
    for number, body in enumerate(bodies):
        model = adapter(tmp_path, lambda request: httpx.Response(200, json=body))
        with pytest.raises(ModelError) as exc:
            model.write(PACKET, task_id=str(number))
        assert exc.value.code == "invalid_response"


def test_budget_reservation_is_atomic_under_ten_simultaneous_tasks(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.sqlite3")
    policy = active(month_usd="0.00014")  # exactly one worst-case reservation
    def reserve(number):
        try:
            ledger.reserve(task_id=str(number), request_id=str(number), policy=policy, request_digest="fixture")
            return "reserved"
        except ModelError as exc:
            return exc.code
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(reserve, range(10)))
    assert results.count("reserved") == 1 and results.count("budget") == 9


def test_task_budget_sums_multiple_phases_and_month_uses_kst(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.sqlite3",
        clock=lambda: datetime(2026, 10, 31, 15, 1, tzinfo=timezone.utc))
    policy = active(per_task_usd="0.00014")
    ledger.reserve(task_id="same", request_id="scope", policy=policy, request_digest="one")
    with pytest.raises(ModelError) as exc:
        ledger.reserve(task_id="same", request_id="report", policy=policy, request_digest="two")
    assert exc.value.code == "budget"
    assert ledger.record("scope")["month"] == "2026-11"


def test_budget_connections_close_after_success_and_rollback(tmp_path):
    ledger = BudgetLedger(tmp_path / "app.sqlite3")
    with ledger._connect() as successful:
        assert successful.execute("SELECT count(*) FROM model_attempts").fetchone()[0] == 0
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        successful.execute("SELECT 1")

    with pytest.raises(RuntimeError, match="synthetic failure"):
        with ledger._connect() as failed:
            failed.execute("CREATE TABLE temporary_fixture (value TEXT)")
            failed.execute("INSERT INTO temporary_fixture VALUES ('must rollback')")
            raise RuntimeError("synthetic failure")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        failed.execute("SELECT 1")
    with ledger._connect() as checked:
        assert checked.execute("SELECT count(*) FROM temporary_fixture").fetchone()[0] == 0
