"""Authenticated, local-only HTTP adapter. No source acquisition or model client."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .auth import AuthError, AuthStore
from .state_backup import AppProcessLock
from .backend import ResearchBackend
from .config import Settings

PACKAGE = Path(__file__).parent
COOKIE = "threegpp_session"


def create_app(settings: Settings, *, backend=None, run_inline=False):
    templates = Jinja2Templates(directory=str(PACKAGE / "templates"))
    templates.env.filters["local_datetime"] = _local_datetime
    templates.env.filters["local_date"] = lambda value: _local_datetime(value)[:10]
    auth = AuthStore(settings.state_root)
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="research-reader")
    scheduled, schedule_lock = set(), Lock()

    @asynccontextmanager
    async def lifespan(app):
        process_lock = AppProcessLock(settings.state_root)
        process_lock.acquire()
        try:
            writer = None
            if backend is None and settings.fixture_mode:
                from .fixtures import seed_fixture_corpus, fixture_report_writer
                seed_fixture_corpus(settings.data_root)
                writer = fixture_report_writer
            app.state.backend = backend or ResearchBackend(
                settings.data_root, settings.state_root,
                limits=settings.limits, fixture_mode=settings.fixture_mode, report_writer=writer)
            yield
        finally:
            pool.shutdown(wait=True, cancel_futures=True)
            process_lock.release()

    app = FastAPI(title="3GPP 연구 데스크", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.mount("/static", StaticFiles(directory=str(PACKAGE / "static")), name="static")

    @app.middleware("http")
    async def boundary(request, call_next):
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > 65536:
            return HTMLResponse("요청 크기가 허용 범위를 넘었습니다.", status_code=413)
        response = await call_next(request)
        response.headers.update({
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-Robots-Tag": "noindex, nofollow",
            "Referrer-Policy": "same-origin",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; form-action 'self'; base-uri 'none'",
        })
        return response

    def session(request, required=True):
        value = auth.get(request.cookies.get(COOKIE, ""))
        if required and (not value or not value["authenticated"]):
            raise HTTPException(401, "로그인이 필요합니다.")
        return value

    def render(request, name, context=None, status=200):
        value = session(request, required=False)
        return templates.TemplateResponse(request=request, name=name, context={
            "csrf_token": value["csrf_token"] if value else "",
            "fixture_mode": settings.fixture_mode, "model_enabled": False,
            "page_title": "3GPP 연구 데스크", "limits": settings.limits,
            **(context or {}),
        }, status_code=status)

    def cookie(response, token):
        response.set_cookie(COOKIE, token, httponly=True, samesite="strict",
                            secure=settings.secure_cookies, max_age=43200, path="/")
        return response

    async def checked_form(request, *, authenticated=True):
        value = session(request, required=authenticated)
        form = await request.form(max_fields=100)
        if not value or not auth.verify_csrf(value, str(form.get("csrf_token", ""))):
            raise HTTPException(403, "요청 확인에 실패했습니다. 화면을 새로 열어주세요.")
        origin = request.headers.get("origin")
        if origin:
            from urllib.parse import urlsplit
            if urlsplit(origin).netloc != request.url.netloc:
                raise HTTPException(403, "다른 사이트의 요청은 허용하지 않습니다.")
        return form

    def core(request):
        return request.app.state.backend

    def task_or_404(request, task_id):
        try:
            task = core(request).get_task(task_id)
            if task is None:
                raise KeyError(task_id)
            return task
        except (KeyError, ValueError):
            raise HTTPException(404, "조사를 찾을 수 없습니다.")

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        if exc.status_code == 401:
            return RedirectResponse("/login", status_code=303)
        return render(request, "error.html", {"error": exc.detail}, exc.status_code)

    @app.get("/health")
    def health():
        return {"status": "ok", "model_enabled": False}

    @app.get("/favicon.ico")
    def favicon():
        return Response(status_code=204)

    @app.get("/login")
    def login(request: Request):
        value = session(request, required=False)
        if value and value["authenticated"]:
            return RedirectResponse("/", status_code=303)
        if value:
            return render(request, "login.html")
        token, value = auth.create()
        response = render(request, "login.html", {"csrf_token": value["csrf_token"]})
        return cookie(response, token)

    @app.post("/login")
    async def login_post(request: Request):
        form = await checked_form(request, authenticated=False)
        try:
            token, _ = auth.authenticate(request.cookies.get(COOKIE, ""),
                                         str(form.get("password", "")), settings.password)
        except AuthError as exc:
            message = ("로그인 시도가 많습니다. 잠시 후 다시 시도하세요."
                       if exc.code == "rate_limited" else "비밀번호를 확인해주세요.")
            return render(request, "login.html", {"error": message}, 429 if exc.code == "rate_limited" else 403)
        return cookie(RedirectResponse("/", status_code=303), token)

    @app.post("/logout")
    async def logout(request: Request):
        await checked_form(request)
        auth.destroy(request.cookies.get(COOKIE, ""))
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(COOKIE, path="/")
        return response

    @app.get("/")
    def home(request: Request):
        session(request)
        parent_id = request.query_params.get("parent_id")
        parent = task_or_404(request, parent_id) if parent_id else None
        return render(request, "home.html", {"tasks": core(request).list_tasks(),
                      "parent_id": parent_id, "parent_task": parent,
                      "data_available": (settings.data_root / "metadata.duckdb").is_file()})

    @app.post("/questions")
    async def create_question(request: Request):
        form = await checked_form(request)
        parent_id = str(form.get("parent_id", "")) or None
        if parent_id:
            task_or_404(request, parent_id)
        try:
            task = core(request).create_task(str(form.get("question", "")),
                                           parent_id=parent_id)
        except ValueError:
            return render(request, "home.html", {"tasks": core(request).list_tasks(),
                          "error": "질문을 1~10,000자로 입력해주세요."}, 422)
        return RedirectResponse(f"/tasks/{task['id']}/scope", status_code=303)

    def scope_context(request, task_id, **extra):
        task = task_or_404(request, task_id)
        if task.get("scope"):
            try:
                preview = core(request).preview_scope(task_id)
            except ValueError as exc:
                preview = {"status": "blocked", "candidates": [], "terms": [],
                           "meetings": [], "limitations": [_safe_message(exc)]}
        else:
            preview = {"status": "draft", "candidates": [], "terms": [], "meetings": [],
                       "limitations": [], "availability": core(request).availability()}
        return {"task": task, "scope": task.get("scope") or {}, "preview": preview, **extra}

    @app.get("/tasks/{task_id}/scope")
    def scope(request: Request, task_id: str):
        session(request)
        return render(request, "scope.html", scope_context(request, task_id))

    @app.post("/tasks/{task_id}/scope")
    async def scope_post(request: Request, task_id: str):
        form = await checked_form(request)
        task_or_404(request, task_id)
        interpretation = {"meeting_range": "meeting", "time_after": "time"}.get(
            str(form.get("interpretation", "")), str(form.get("interpretation", "")))
        values = {"wg": form.get("wg", ""), "from_meeting": form.get("from_meeting", ""),
                  "to_meeting": form.get("to_meeting", ""), "interpretation": interpretation,
                  "corpus_as_of": form.get("corpus_as_of", ""), "user_terms": form.get("user_terms", ""),
                  "time_boundary": form.get("time_boundary", "")}
        try:
            core(request).save_scope(task_id, values)
        except ValueError as exc:
            return render(request, "scope.html", scope_context(request, task_id,
                          error=_safe_message(exc)), 422)
        return RedirectResponse(f"/tasks/{task_id}/scope", status_code=303)

    @app.post("/tasks/{task_id}/approve")
    async def approve(request: Request, task_id: str):
        form = await checked_form(request)
        task_or_404(request, task_id)
        try:
            revision = form.get("revision")
            if not revision or not str(revision).isdigit():
                raise ValueError("현재 범위의 승인 화면을 다시 열어주세요.")
            core(request).approve_scope(task_id, accepted_terms=form.getlist("accepted_terms"),
                confirmed=form.get("scope_confirmed") in {"on", "yes", "true"},
                expected_revision=int(revision) if revision else None)
        except (ValueError, KeyError) as exc:
            return render(request, "scope.html", scope_context(request, task_id,
                          error=_safe_message(exc)), 422)
        return RedirectResponse(f"/tasks/{task_id}", status_code=303)

    @app.get("/tasks/{task_id}")
    def task_page(request: Request, task_id: str):
        session(request)
        task = task_or_404(request, task_id)
        job = core(request).latest_job(task_id)
        if job and job["revision"] != task["revision"]:
            job = None
        past_jobs = [item for item in core(request).list_jobs(task_id)
                     if job is None or item["id"] != job["id"]]
        return render(request, "task.html", {"task": task, "scope": task.get("scope") or {},
                      "job": job, "past_jobs": past_jobs,
                      "events": job.get("events", []) if job else []})

    def schedule(reader, job):
        with schedule_lock:
            if job["id"] in scheduled or job["status"] != "queued":
                return
            scheduled.add(job["id"])
        def work():
            try:
                reader.run_job(job["id"])
            finally:
                with schedule_lock:
                    scheduled.discard(job["id"])
        if run_inline:
            work()
        else:
            pool.submit(work)

    @app.post("/tasks/{task_id}/run")
    async def run(request: Request, task_id: str):
        form = await checked_form(request)
        task_or_404(request, task_id)
        try:
            job = core(request).enqueue(task_id, retry=form.get("retry") in {"on", "yes", "true"})
            schedule(core(request), job)
        except (ValueError, KeyError) as exc:
            raise HTTPException(409, _safe_message(exc))
        return RedirectResponse(f"/tasks/{task_id}", status_code=303)

    @app.get("/api/tasks/{task_id}")
    def task_status(request: Request, task_id: str):
        session(request)
        task = task_or_404(request, task_id)
        selected_job = request.query_params.get("job_id")
        try:
            job = (core(request).get_job(selected_job) if selected_job
                   else core(request).latest_job(task_id))
        except KeyError:
            raise HTTPException(404, "실행 기록을 찾을 수 없습니다.")
        if job and job["task_id"] != task_id:
            raise HTTPException(404, "이 조사에 연결된 실행 기록이 아닙니다.")
        return JSONResponse({"status": job["status"] if job else task["status"]})

    @app.get("/tasks/{task_id}/report")
    def report(request: Request, task_id: str):
        session(request)
        task = task_or_404(request, task_id)
        selected_job = request.query_params.get("job_id")
        try:
            job = (core(request).get_job(selected_job) if selected_job
                   else core(request).latest_job(task_id))
        except KeyError:
            raise HTTPException(404, "실행 기록을 찾을 수 없습니다.")
        if job and job["task_id"] != task_id:
            raise HTTPException(404, "이 조사에 연결된 실행 기록이 아닙니다.")
        if not job:
            raise HTTPException(404, "실행 결과가 아직 없습니다.")
        try:
            result = core(request).result(job["id"])
            if result is None:
                raise FileNotFoundError()
        except (ValueError, KeyError, FileNotFoundError):
            raise HTTPException(404, "결과가 저장되지 않았습니다. 작업 상태를 확인해주세요.")
        return render(request, "report.html", {"task": task, "job": job,
                      "approved_scope": job["approved_scope"]["scope"],
                      "fixture_mode": settings.fixture_mode or result.get("fixture_mode", False)
                          or bool((result.get("report") or {}).get("fixture_only")),
                      "result": _report_view(result)})

    @app.get("/sources/{job_id}/{asset_id}")
    def source(request: Request, job_id: str, asset_id: str):
        session(request)
        try:
            path, filename = core(request).resolve_asset(job_id, asset_id)
        except (ValueError, KeyError, OSError):
            raise HTTPException(404, "검증된 출처 파일을 사용할 수 없습니다.")
        return FileResponse(path, filename=filename, media_type="application/octet-stream")

    return app


def _safe_message(exc):
    # Never return paths/tracebacks/credentials through a backend exception.
    message = str(exc)
    if any(token in message for token in ("/", "\\", "Traceback", "password", "secret")):
        return "입력을 확인하거나 자료 검증 상태를 확인해주세요."
    return message[:500] or "요청을 처리할 수 없습니다."


def _local_datetime(value):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    try:
        stamp = datetime.fromisoformat(str(value))
        if stamp.tzinfo is None:
            return "시각 확인 필요"
        return stamp.astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M KST")
    except ValueError:
        return "시각 확인 필요"


def _report_view(result):
    """Resolve writer citation keys to the existing, validated source presentation."""
    import copy
    result = copy.deepcopy(result)
    bundle = result.get("bundle", {})
    sources = {source.get("key"): source for field in (
        "contribution_sources", "discussion_sources", "meeting_outcome_sources")
        for source in bundle.get(field, [])}
    report = result.get("report") or {}
    for claim in report.get("claims", []):
        resolved = []
        for reference in claim.get("sources", []):
            if isinstance(reference, dict):
                resolved.append(reference)
                continue
            source = sources.get(reference)
            if not source:
                continue
            info = source.get("source", {})
            passage = next(iter(source.get("passages", [])), {})
            organizations = ", ".join(source.get("organizations", []))
            meeting = (source.get("authority_meeting") if source.get("channel") == "meeting_outcome_sources"
                       else source.get("meeting"))
            resolved.append({"label": " · ".join(filter(None, [organizations,
                source.get("tdoc"), meeting, source.get("title")])),
                "url": info.get("raw_asset") or info.get("official_url"),
                "locator": passage.get("human_locator") or passage.get("locator", "")})
        claim["sources"] = resolved
    result["report"] = report or None
    return result
