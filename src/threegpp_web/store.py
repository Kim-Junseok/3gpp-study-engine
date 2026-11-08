"""Small durable application store, deliberately separate from research DuckDB."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


def now() -> str:
    return datetime.now(UTC).isoformat()


class AppStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "app.sqlite3"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                    revision INTEGER NOT NULL, attempt INTEGER NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, payload TEXT NOT NULL,
                    UNIQUE(task_id, revision, attempt));
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL, created_at TEXT NOT NULL,
                    stage TEXT NOT NULL, message TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def new_task(self, question: str, parent_id: str | None):
        task = {"id": uuid.uuid4().hex, "question": question,
                "parent_id": parent_id, "created_at": now(), "updated_at": now(),
                "status": "draft", "scope": None, "revision": 0,
                "approval": None, "preview": None}
        with self.connect() as db:
            db.execute("INSERT INTO tasks VALUES(?,?,?,?)", (
                task["id"], task["created_at"], task["updated_at"], json.dumps(task)))
        return task

    def get_task(self, task_id):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM tasks WHERE id=?", [task_id]).fetchone()
        if row is None:
            raise KeyError("task not found")
        return json.loads(row[0])

    def save_task(self, task):
        previous_timestamp = task["updated_at"]
        task["updated_at"] = now()
        with self.connect() as db:
            count = db.execute("UPDATE tasks SET updated_at=?,payload=? WHERE id=? AND updated_at=?", (
                task["updated_at"], json.dumps(task), task["id"], previous_timestamp)).rowcount
        if count != 1:
            raise ValueError("작업 범위가 다른 요청에서 변경됐습니다. 현재 화면을 다시 확인하세요.")
        return task

    def set_task_status(self, task_id, revision, status):
        """Update a job status without replacing a newer draft or approval."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM tasks WHERE id=?", [task_id]).fetchone()
            if row is None:
                raise KeyError("task not found")
            task = json.loads(row[0])
            if task["revision"] != revision:
                return
            task["status"] = status
            task["updated_at"] = now()
            db.execute("UPDATE tasks SET updated_at=?,payload=? WHERE id=?", (
                task["updated_at"], json.dumps(task), task_id))

    def list_tasks(self):
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM tasks ORDER BY updated_at DESC,id DESC").fetchall()
        return [json.loads(row[0]) for row in rows]

    def latest_job(self, task_id):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM jobs WHERE task_id=? "
                             "ORDER BY created_at DESC,id DESC LIMIT 1", [task_id]).fetchone()
        return json.loads(row[0]) if row else None

    def list_jobs(self, task_id):
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM jobs WHERE task_id=? "
                              "ORDER BY created_at DESC,id DESC", [task_id]).fetchall()
        return [json.loads(row[0]) for row in rows]

    def create_job(self, task, *, retry=False):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current_row = db.execute("SELECT payload FROM tasks WHERE id=?", [task["id"]]).fetchone()
            current = json.loads(current_row[0]) if current_row else None
            if (current is None or current["revision"] != task["revision"]
                    or current["approval"] != task["approval"]):
                raise ValueError("조사 범위가 변경됐습니다. 현재 범위를 다시 승인하세요.")
            rows = db.execute("SELECT payload FROM jobs WHERE task_id=? AND revision=? "
                              "ORDER BY attempt DESC", [task["id"], task["revision"]]).fetchall()
            old = json.loads(rows[0][0]) if rows else None
            if old and not retry:
                return old
            if old and old["status"] not in {"failed", "interrupted", "needs_data", "scope_limit"}:
                raise ValueError("only a failed or interrupted attempt may be retried")
            job = {"id": uuid.uuid4().hex, "task_id": task["id"],
                   "revision": task["revision"], "attempt": old["attempt"] + 1 if old else 1,
                   "status": "queued", "created_at": now(), "updated_at": now(),
                   "approved_scope": task["approval"], "error": None,
                   "result_available": False}
            db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)", (
                job["id"], job["task_id"], job["revision"], job["attempt"],
                job["status"], job["created_at"], job["updated_at"], json.dumps(job)))
        self.add_event(job["id"], "queued", "승인한 범위의 작업을 대기열에 저장했습니다.")
        return job

    def get_job(self, job_id):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM jobs WHERE id=?", [job_id]).fetchone()
        if row is None:
            raise KeyError("job not found")
        job = json.loads(row[0])
        with self.connect() as db:
            job["events"] = [dict(row) for row in db.execute(
                "SELECT sequence,created_at,stage,message FROM events WHERE job_id=? "
                "ORDER BY sequence", [job_id]).fetchall()]
        return job

    def save_job(self, job):
        job = {key: value for key, value in job.items() if key != "events"}
        job["updated_at"] = now()
        with self.connect() as db:
            db.execute("UPDATE jobs SET status=?,updated_at=?,payload=? WHERE id=?", (
                job["status"], job["updated_at"], json.dumps(job), job["id"]))
        return job

    def claim_job(self, job_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            running = db.execute("SELECT id FROM jobs WHERE status='running'").fetchone()
            row = db.execute("SELECT payload FROM jobs WHERE id=? AND status='queued'", [job_id]).fetchone()
            if running or row is None:
                return None
            job = json.loads(row[0])
            job["status"] = "running"
            job["updated_at"] = now()
            db.execute("UPDATE jobs SET status=?,updated_at=?,payload=? WHERE id=?", (
                job["status"], job["updated_at"], json.dumps(job), job_id))
        return job

    def recover(self):
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM jobs WHERE status IN ('queued','running')").fetchall()
        for row in rows:
            job = json.loads(row[0])
            job["status"] = "interrupted"
            job["error"] = "서비스가 재시작되어 중단됐습니다. 자동 재실행하지 않았습니다."
            self.save_job(job)
            self.add_event(job["id"], "interrupted", job["error"])
            self.set_task_status(job["task_id"], job["revision"], "interrupted")

    def add_event(self, job_id, stage, message):
        with self.connect() as db:
            db.execute("INSERT INTO events(job_id,created_at,stage,message) VALUES(?,?,?,?)", (
                job_id, now(), stage, message))

