"""Single-owner, server-side sessions; no credentials are written to sessions."""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable


class AuthError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class AuthStore:
    """Opaque cookie tokens are stored only as hashes, with a separate CSRF token.

    The caller owns cookie flags, request CSRF checks, and the password secret.
    A successful login rotates the cookie token and the CSRF token. Failed login
    throttling is persisted per pre-login session and never records passwords.
    """

    def __init__(self, state_root: Path | str, *, ttl_seconds: int = 43200,
                 clock: Callable[[], float] = time.time):
        if ttl_seconds <= 0:
            raise ValueError("session lifetime must be positive")
        self.root = Path(state_root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / "auth.sqlite3"
        self.ttl = ttl_seconds
        self.clock = clock
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY, csrf_token TEXT NOT NULL,
                authenticated INTEGER NOT NULL, created_at REAL NOT NULL,
                expires_at REAL NOT NULL, failures INTEGER NOT NULL DEFAULT 0,
                failure_window REAL NOT NULL DEFAULT 0
            )""")
        self.path.chmod(0o600)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    @staticmethod
    def _hash(token: str | None) -> str | None:
        if not isinstance(token, str) or not token or len(token) > 256:
            return None
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _public(row) -> dict:
        return {"csrf_token": row["csrf_token"],
                "authenticated": bool(row["authenticated"]),
                "created_at": row["created_at"], "expires_at": row["expires_at"]}

    def _insert(self, conn, *, authenticated: bool):
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        now = self.clock()
        conn.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,?)",
                     (self._hash(token), csrf, int(authenticated), now,
                      now + self.ttl, 0, now))
        return token, {"csrf_token": csrf, "authenticated": authenticated,
                       "created_at": now, "expires_at": now + self.ttl}

    def create(self) -> tuple[str, dict]:
        with self._connect() as conn:
            # Expired sessions are disposable, never a research-history record.
            conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (self.clock(),))
            return self._insert(conn, authenticated=False)

    def get(self, token: str | None) -> dict | None:
        digest = self._hash(token)
        if digest is None:
            return None
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE token_hash=?", (digest,)).fetchone()
            if row is None or row["expires_at"] <= self.clock():
                return None
            return self._public(row)

    def authenticate(self, token: str | None, password: str,
                     expected_password: str) -> tuple[str, dict]:
        digest = self._hash(token)
        if digest is None:
            raise AuthError("invalid_session")
        if not isinstance(expected_password, str) or not expected_password:
            raise AuthError("not_configured")
        error = None
        result = None
        # Serialize counters and session rotation across concurrent requests.
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM sessions WHERE token_hash=?", (digest,)).fetchone()
            now = self.clock()
            if row is None or row["expires_at"] <= now:
                error = "invalid_session"
            else:
                failures = row["failures"] if now - row["failure_window"] < 60 else 0
                window = row["failure_window"] if failures else now
                if failures >= 5:
                    error = "rate_limited"
                elif not isinstance(password, str) or not secrets.compare_digest(
                        password.encode("utf-8"), expected_password.encode("utf-8")):
                    conn.execute("UPDATE sessions SET failures=?,failure_window=? WHERE token_hash=?",
                                 (failures + 1, window, digest))
                    error = "invalid_credentials"
                else:
                    conn.execute("DELETE FROM sessions WHERE token_hash=?", (digest,))
                    result = self._insert(conn, authenticated=True)
        if error:
            raise AuthError(error)
        assert result is not None
        return result

    def destroy(self, token: str | None) -> None:
        digest = self._hash(token)
        if digest is not None:
            with self._connect() as conn:
                conn.execute("DELETE FROM sessions WHERE token_hash=?", (digest,))

    @staticmethod
    def verify_csrf(session: dict | None, provided: str | None) -> bool:
        expected = session.get("csrf_token") if isinstance(session, dict) else None
        return (isinstance(expected, str) and isinstance(provided, str)
                and secrets.compare_digest(expected.encode("utf-8"), provided.encode("utf-8")))
