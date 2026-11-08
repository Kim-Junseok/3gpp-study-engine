"""Real Chromium QA of explicit synthetic/empty modes. No external URLs allowed."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--chromium", default=shutil.which("chromium"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = {"fixture_only": True, "stage_b_accepted": False, "screens": [],
               "external_browser_requests": [], "console_errors": []}
    password = "synthetic-local-browser-qa-only"
    with TemporaryDirectory(prefix="threegpp-web-browser-") as temporary:
        root = Path(temporary)
        processes = []
        try:
            for port, fixture in ((8765, True), (8766, False)):
                command = [sys.executable, "-m", "threegpp_web", "--port", str(port),
                           "--data-root", str(root / f"corpus-{port}"),
                           "--state-root", str(root / f"state-{port}")]
                if fixture:
                    command.append("--fixture")
                environment = {**os.environ, "THREEGPP_WEB_PASSWORD": password,
                               "PYTHONDONTWRITEBYTECODE": "1"}
                environment.pop("THREEGPP_WEB_PASSWORD_FILE", None)
                log = (args.output / f"server-{port}.log").open("w")
                process = subprocess.Popen(command, env=environment, stdout=log, stderr=log)
                log.close()
                processes.append(process)
                for attempt in range(150):
                    if process.poll() is not None:
                        raise RuntimeError(f"QA server on port {port} did not start")
                    try:
                        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise RuntimeError("QA server readiness timed out")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=args.chromium,
                                                     headless=True, args=["--no-sandbox"])
                for width in (360, 390, 1440):
                    context = browser.new_context(viewport={"width": width, "height": 900},
                                                  device_scale_factor=1)
                    def route_request(route):
                        from urllib.parse import urlsplit
                        if urlsplit(route.request.url).hostname != "127.0.0.1":
                            results["external_browser_requests"].append(route.request.url)
                            route.abort()
                        else:
                            route.continue_()
                    context.route("**/*", route_request)
                    page = context.new_page()
                    page.on("pageerror", lambda error: results["console_errors"].append(str(error)))
                    page.on("console", lambda message: results["console_errors"].append(message.text)
                            if message.type == "error" else None)
                    page.goto("http://127.0.0.1:8765/login")
                    page.locator('[name="password"]').fill(password)
                    page.get_by_role("button", name="접속하기").click()
                    page.wait_for_url("http://127.0.0.1:8765/")

                    def capture(name):
                        page.screenshot(path=str(args.output / f"{width}-{name}.png"), full_page=True)
                        metrics = page.evaluate("""() => ({width:innerWidth,
                          scrollWidth:document.documentElement.scrollWidth,
                          undersized:[...document.querySelectorAll('button,.button,summary,.choice-row,.consent-row,.candidate-row,input:not([type=hidden]):not([type=checkbox]):not([type=radio]),select,textarea')]
                            .filter(x => x.getBoundingClientRect().height > 0 && x.getBoundingClientRect().height < 44)
                            .map(x => x.textContent.trim() || x.name)})""")
                        assert metrics["scrollWidth"] <= width, (name, metrics)
                        assert not metrics["undersized"], (name, metrics)
                        results["screens"].append({"width": width, "page": name, **metrics})

                    capture("home")
                    page.locator('[name="question"]').fill("FixtureTopic의 제안과 논의를 검증용 자료에서 확인하고 싶다.")
                    page.get_by_role("button", name="범위 확인").click()
                    page.wait_for_url("**/scope")
                    page.locator('[name="from_meeting"]').fill("125")
                    page.locator('[name="to_meeting"]').fill("125")
                    page.locator('[name="corpus_as_of"]').fill("합성 fixture 사본 — 실제 3GPP 자료 아님")
                    page.locator('[name="user_terms"]').fill("FixtureTopic")
                    page.get_by_role("button", name="자료·용어 확인").click()
                    page.get_by_role("button", name="이 범위 승인하기").wait_for()
                    capture("scope")
                    page.locator('[name="scope_confirmed"]').check()
                    page.get_by_role("button", name="이 범위 승인하기").click()
                    page.get_by_role("button", name="작업 실행").click()
                    for attempt in range(100):
                        if page.get_by_role("link", name="결과·출처 열기").count():
                            break
                        page.wait_for_timeout(100)
                        page.reload()
                    else:
                        raise RuntimeError("fixture job did not finish")
                    capture("task")
                    page.get_by_role("link", name="결과·출처 열기").click()
                    page.get_by_role("heading", name="읽은 출처", exact=True).wait_for()
                    assert page.get_by_text("실제 3GPP 자료나 연구 결과가 아닙니다.").count()
                    capture("report")
                    page.get_by_role("link", name="후속 질문 작성").click()
                    assert page.locator('[name="parent_id"]').input_value()
                    capture("followup")
                    page.goto("http://127.0.0.1:8766/login")
                    page.locator('[name="password"]').fill(password)
                    page.get_by_role("button", name="접속하기").click()
                    capture("empty")
                    page.locator('[name="question"]').fill("자료 없는 상태의 질문")
                    page.get_by_role("button", name="범위 확인").click()
                    capture("empty-scope")
                    context.close()
                browser.close()
        finally:
            for process in processes:
                process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    (args.output / "browser-results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf8")
    assert not results["external_browser_requests"] and not results["console_errors"], results
    print(json.dumps({"screens_checked": len(results["screens"]), "external_requests": 0,
                      "console_errors": 0, "stage_b_accepted": False}))


if __name__ == "__main__":
    main()
