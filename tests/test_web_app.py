"""HTTP acceptance of the local adapter, using synthetic fixtures only."""
import re

import pytest
from fastapi.testclient import TestClient

from threegpp_web.app import create_app
from threegpp_web.config import Settings
from threegpp_web.fixtures import FIXTURE_SCOPE


PASSWORD = "test-only-password-123"


def csrf(response):
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', response.text)
    assert match, response.text[:1000]
    return match.group(1)


def login(client):
    token = csrf(client.get("/login"))
    response = client.post("/login", data={"csrf_token": token, "password": PASSWORD})
    assert response.status_code == 200
    return csrf(response)


@pytest.fixture
def settings(tmp_path):
    return Settings(tmp_path / "corpus", tmp_path / "state", PASSWORD, fixture_mode=True)


def start_task(client, token, question="FixtureTopic의 검증용 질문"):
    response = client.post("/questions", data={"csrf_token": token, "question": question})
    assert response.status_code == 200
    assert response.url.path.endswith("/scope")
    return response.url.path.split("/")[2]


def save_and_approve(client, token, task_id):
    response = client.post(f"/tasks/{task_id}/scope", data={
        **FIXTURE_SCOPE, "wg": "RAN1", "user_terms": "FixtureTopic", "csrf_token": token})
    assert response.status_code == 200
    response = client.post(f"/tasks/{task_id}/approve", data={
        "csrf_token": token, "scope_confirmed": "on", "revision": 1})
    assert response.status_code == 200


def test_unauthenticated_pages_and_assets_require_login(settings):
    with TestClient(create_app(settings, run_inline=True)) as client:
        for path in ("/", "/tasks/missing", "/sources/missing/asset-1", "/api/tasks/missing"):
            response = client.get(path, follow_redirects=False)
            assert response.status_code == 303
            assert response.headers["location"] == "/login"
        assert client.get("/health").json()["model_enabled"] is False


def test_password_csrf_rotation_and_logout(settings):
    with TestClient(create_app(settings)) as client:
        response = client.get("/login")
        original = client.cookies.get("threegpp_session")
        assert "httponly" in response.headers["set-cookie"].lower()
        assert "samesite=strict" in response.headers["set-cookie"].lower()
        assert client.post("/login", data={"password": PASSWORD}).status_code == 403
        response = client.post("/login", data={"password": PASSWORD, "csrf_token": csrf(response)})
        assert client.cookies.get("threegpp_session") != original
        token = csrf(response)
        assert client.post("/questions", data={"question": "bad", "csrf_token": "bad"}).status_code == 403
        client.post("/logout", data={"csrf_token": token})
        assert client.get("/", follow_redirects=False).status_code == 303


def test_fixture_flow_reads_three_channels_and_authenticated_source(settings):
    with TestClient(create_app(settings, run_inline=True)) as client:
        token = login(client)
        task_id = start_task(client, token)
        save_and_approve(client, token, task_id)
        for _ in range(10):
            assert client.post(f"/tasks/{task_id}/run", data={"csrf_token": token}).status_code == 200
        backend = client.app.state.backend
        job = backend.latest_job(task_id)
        assert job["status"] == "completed"
        assert job["attempt"] == 1
        result = backend.result(job["id"])
        assert all(result["bundle"][field] for field in (
            "contribution_sources", "discussion_sources", "meeting_outcome_sources"))
        assert result["model_input"]["model_calls"] == 0
        page = client.get(f"/tasks/{task_id}/report")
        assert page.status_code == 200
        assert "fixture" in page.text.lower()
        assert "실제 연구" in page.text
        assert str(settings.data_root) not in page.text
        assert "topic-profile-" not in page.text
        source_url = result["bundle"]["contribution_sources"][0]["source"]["raw_asset"]
        assert source_url.startswith("/sources/")
        assert client.get(source_url).status_code == 200
        assert client.get(f"/sources/{job['id']}/unknown").status_code == 404


def test_empty_data_preserves_question_and_never_creates_report(tmp_path):
    config = Settings(tmp_path / "missing", tmp_path / "state", PASSWORD)
    with TestClient(create_app(config, run_inline=True)) as client:
        token = login(client)
        task_id = start_task(client, token)
        response = client.post(f"/tasks/{task_id}/scope", data={
            **FIXTURE_SCOPE, "wg": "RAN1", "user_terms": "FixtureTopic", "csrf_token": token})
        assert response.status_code == 200
        assert "복원" in response.text
        assert client.post(f"/tasks/{task_id}/approve", data={
            "csrf_token": token, "scope_confirmed": "on", "revision": 1}).status_code == 422
        assert client.post(f"/tasks/{task_id}/run", data={"csrf_token": token}).status_code == 409
        assert client.app.state.backend.latest_job(task_id) is None
        assert not config.data_root.exists()


def test_stale_scope_approval_rejected_and_followup_requires_new_scope(settings):
    with TestClient(create_app(settings)) as client:
        token = login(client)
        task_id = start_task(client, token)
        for _ in range(2):
            client.post(f"/tasks/{task_id}/scope", data={
                **FIXTURE_SCOPE, "wg": "RAN1", "user_terms": "FixtureTopic", "csrf_token": token})
        assert client.post(f"/tasks/{task_id}/approve", data={
            "csrf_token": token, "scope_confirmed": "on", "revision": 1}).status_code == 422
        child = client.post("/questions", data={"csrf_token": token,
                            "question": "후속 질문", "parent_id": task_id})
        child_id = child.url.path.split("/")[2]
        task = client.app.state.backend.get_task(child_id)
        assert task["parent_id"] == task_id
        assert task["scope"] is None and task["approval"] is None


def test_user_text_is_escaped_and_cross_origin_writes_rejected(settings):
    with TestClient(create_app(settings)) as client:
        token = login(client)
        task_id = start_task(client, token, '<script>alert("x")</script>')
        page = client.get(f"/tasks/{task_id}/scope")
        assert '<script>alert("x")</script>' not in page.text
        assert "&lt;script&gt;" in page.text
        response = client.post("/questions", data={"csrf_token": token, "question": "blocked"},
                               headers={"Origin": "https://outside.invalid"})
        assert response.status_code == 403


def test_history_and_completed_report_survive_service_restart(settings):
    with TestClient(create_app(settings, run_inline=True)) as client:
        token = login(client)
        task_id = start_task(client, token)
        save_and_approve(client, token, task_id)
        client.post(f"/tasks/{task_id}/run", data={"csrf_token": token})
    with TestClient(create_app(settings)) as restored:
        login(restored)
        assert restored.get(f"/tasks/{task_id}/report").status_code == 200
        job = restored.app.state.backend.latest_job(task_id)
        assert job["status"] == "completed" and job["attempt"] == 1


def test_requires_configured_password_and_separate_state_paths(tmp_path):
    with pytest.raises(ValueError):
        Settings(tmp_path / "data", tmp_path / "state", "")
    with pytest.raises(ValueError):
        Settings(tmp_path / "data", tmp_path / "data" / "web", PASSWORD)
    with pytest.raises(ValueError):
        Settings(tmp_path / "data", tmp_path / "state", PASSWORD, max_sources=0)


def test_corpus_and_app_restore_keep_reports_and_source_links_on_new_paths(settings, tmp_path):
    from threegpp_web.corpus import pack_corpus, restore_corpus
    from threegpp_web.state_backup import pack, restore
    with TestClient(create_app(settings, run_inline=True)) as client:
        token = login(client)
        task_id = start_task(client, token)
        save_and_approve(client, token, task_id)
        client.post(f"/tasks/{task_id}/run", data={"csrf_token": token})
        old_cookie = client.cookies.get("threegpp_session")
    archive, state_archive = tmp_path / "corpus.tar.gz", tmp_path / "state.tar.gz"
    pack_corpus(settings.data_root, archive)
    pack(settings.state_root, state_archive)
    restored_corpus, restored_state = tmp_path / "other-corpus", tmp_path / "other-state"
    restore_corpus(archive, restored_corpus)
    restore(state_archive, restored_state)
    # Remove the old paths from resolution: provenance must not depend on them.
    settings.data_root.rename(tmp_path / "old-corpus-unavailable")
    settings.state_root.rename(tmp_path / "old-state-unavailable")
    config = Settings(restored_corpus, restored_state, PASSWORD, fixture_mode=True)
    with TestClient(create_app(config)) as client:
        client.cookies.set("threegpp_session", old_cookie)
        assert client.get("/", follow_redirects=False).status_code == 303
        login(client)
        assert client.get(f"/tasks/{task_id}/report").status_code == 200
        job = client.app.state.backend.latest_job(task_id)
        result = client.app.state.backend.result(job["id"])
        url = result["bundle"]["contribution_sources"][0]["source"]["raw_asset"]
        assert client.get(url).status_code == 200


def test_new_scope_can_run_and_old_result_stays_accessible(settings):
    with TestClient(create_app(settings, run_inline=True)) as client:
        token = login(client)
        task_id = start_task(client, token)
        save_and_approve(client, token, task_id)
        client.post(f"/tasks/{task_id}/run", data={"csrf_token": token})
        backend = client.app.state.backend
        first = backend.latest_job(task_id)
        client.post(f"/tasks/{task_id}/scope", data={
            **FIXTURE_SCOPE, "wg": "RAN1", "user_terms": "FixtureTopic", "csrf_token": token,
            "corpus_as_of": "SECOND_SCOPE_REFERENCE"})
        task = backend.get_task(task_id)
        client.post(f"/tasks/{task_id}/approve", data={
            "csrf_token": token, "scope_confirmed": "on", "revision": task["revision"]})
        page = client.get(f"/tasks/{task_id}")
        assert "작업 실행" in page.text and "이전 결과·출처" in page.text
        client.post(f"/tasks/{task_id}/run", data={"csrf_token": token})
        second = backend.latest_job(task_id)
        assert second["id"] != first["id"]
        old = client.get(f"/tasks/{task_id}/report?job_id={first['id']}")
        assert old.status_code == 200 and "자료 선정·읽기 기준" in old.text
        assert "SECOND_SCOPE_REFERENCE" not in old.text
        assert "SECOND_SCOPE_REFERENCE" in client.get(f"/tasks/{task_id}/report").text
        assert client.get(f"/tasks/{task_id}/report?job_id=not-a-job").status_code == 404
        # A later failed attempt must not hide an earlier successful result.
        client.post(f"/tasks/{task_id}/scope", data={
            **FIXTURE_SCOPE, "wg": "RAN1", "user_terms": "FixtureTopic", "csrf_token": token})
        task = backend.get_task(task_id)
        client.post(f"/tasks/{task_id}/approve", data={
            "csrf_token": token, "scope_confirmed": "on", "revision": task["revision"]})
        def failed_writer(packet):
            raise RuntimeError("simulated fixture writer failure")
        backend.report_writer = failed_writer
        client.post(f"/tasks/{task_id}/run", data={"csrf_token": token})
        assert backend.latest_job(task_id)["status"] == "failed"
        assert client.get(f"/tasks/{task_id}/report").status_code == 404
        assert client.get(f"/tasks/{task_id}/report?job_id={first['id']}").status_code == 200


def test_application_dates_use_korea_timezone():
    from threegpp_web.app import _local_datetime
    assert _local_datetime("2026-11-08T15:01:00+00:00") == "2026-11-09 00:01 KST"
