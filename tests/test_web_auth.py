import sqlite3

import pytest

from threegpp_web.auth import AuthError, AuthStore


def test_session_token_is_hashed_and_csrf_is_independent(tmp_path):
    store = AuthStore(tmp_path)
    token, session = store.create()
    assert session["authenticated"] is False
    assert session["csrf_token"] != token
    assert token.encode() not in store.path.read_bytes()
    assert store.get(token) == session
    assert store.get("unknown") is None
    assert store.get(None) is None


def test_login_rotates_token_csrf_and_does_not_store_password(tmp_path):
    store = AuthStore(tmp_path)
    token, before = store.create()
    password = "개인 연구용 test credential"
    rotated, after = store.authenticate(token, password, password)
    assert rotated != token
    assert before["csrf_token"] != after["csrf_token"]
    assert store.get(token) is None
    assert after["authenticated"] is True
    assert store.get(rotated) == after
    assert password.encode() not in store.path.read_bytes()


def test_persisted_sessions_survive_store_reopen_and_logout(tmp_path):
    store = AuthStore(tmp_path)
    token, _ = store.create()
    token, session = store.authenticate(token, "password", "password")
    reopened = AuthStore(tmp_path)
    assert reopened.get(token) == session
    reopened.destroy(token)
    assert store.get(token) is None


def test_expired_session_cannot_authenticate(tmp_path):
    clock = [1000.0]
    store = AuthStore(tmp_path, ttl_seconds=30, clock=lambda: clock[0])
    token, _ = store.create()
    clock[0] += 31
    assert store.get(token) is None
    with pytest.raises(AuthError) as error:
        store.authenticate(token, "password", "password")
    assert error.value.code == "invalid_session"


def test_wrong_password_is_rate_limited_and_window_recovers(tmp_path):
    clock = [1000.0]
    store = AuthStore(tmp_path, clock=lambda: clock[0])
    token, _ = store.create()
    for _ in range(5):
        with pytest.raises(AuthError) as error:
            store.authenticate(token, "wrong", "password")
        assert error.value.code == "invalid_credentials"
    with pytest.raises(AuthError) as error:
        store.authenticate(token, "password", "password")
    assert error.value.code == "rate_limited"
    # Restarting the app must not reset the persistent failure count.
    reopened = AuthStore(tmp_path, clock=lambda: clock[0])
    with pytest.raises(AuthError, match="rate_limited"):
        reopened.authenticate(token, "password", "password")
    clock[0] += 61
    _, session = reopened.authenticate(token, "password", "password")
    assert session["authenticated"] is True


def test_unconfigured_password_is_never_valid(tmp_path):
    store = AuthStore(tmp_path)
    token, _ = store.create()
    with pytest.raises(AuthError, match="not_configured"):
        store.authenticate(token, "", "")
    assert store.get(token)["authenticated"] is False


def test_csrf_requires_exact_value_and_rejects_other_sessions(tmp_path):
    store = AuthStore(tmp_path)
    _, first = store.create()
    _, second = store.create()
    assert store.verify_csrf(first, first["csrf_token"])
    assert not store.verify_csrf(first, second["csrf_token"])
    assert not store.verify_csrf(first, None)
    assert not store.verify_csrf(None, first["csrf_token"])
    assert not store.verify_csrf(first, 1)


def test_auth_requests_close_database_connections(tmp_path, monkeypatch):
    connections = []
    original = sqlite3.connect

    class TrackedConnection(sqlite3.Connection):
        closed = False

        def close(self):
            self.closed = True
            super().close()

    def connect(*args, **kwargs):
        connection = original(*args, **kwargs, factory=TrackedConnection)
        connections.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", connect)
    store = AuthStore(tmp_path)
    token, _ = store.create()
    store.get(token)
    with pytest.raises(AuthError, match="invalid_credentials"):
        store.authenticate(token, "wrong", "password")
    token, _ = store.authenticate(token, "password", "password")
    store.destroy(token)
    assert len(connections) == 6
    assert all(connection.closed for connection in connections)
