"""Tests for Tier 1 infrastructure: auth, encryption, database, scheduler."""

import shutil
from pathlib import Path

import pytest

from agentic_cxo.infrastructure.auth import AuthManager
from agentic_cxo.infrastructure.database import (
    DBMessage,
    DBReminder,
    get_session,
    init_db,
)
from agentic_cxo.infrastructure.encryption import EncryptedStore
from agentic_cxo.infrastructure.scheduler import (
    list_jobs,
    start_scheduler,
    stop_scheduler,
)


@pytest.fixture(autouse=True)
def clean_data():
    yield
    data_dir = Path(".cxo_data")
    if data_dir.exists():
        shutil.rmtree(data_dir)
    db_path = Path("cxo.db")
    if db_path.exists():
        db_path.unlink()
    stop_scheduler()


class TestAuth:
    def test_signup(self):
        auth = AuthManager()
        result = auth.signup("test@example.com", "password123", "Test User")
        assert "token" in result
        assert result["user"]["email"] == "test@example.com"

    def test_duplicate_signup(self):
        auth = AuthManager()
        auth.signup("test@example.com", "pass123")
        result = auth.signup("test@example.com", "pass456")
        assert "error" in result

    def test_login_success(self):
        auth = AuthManager()
        auth.signup("test@example.com", "password123")
        result = auth.login("test@example.com", "password123")
        assert "token" in result

    def test_login_wrong_password(self):
        auth = AuthManager()
        auth.signup("test@example.com", "password123")
        result = auth.login("test@example.com", "wrong")
        assert "error" in result

    def test_login_nonexistent(self):
        auth = AuthManager()
        result = auth.login("nobody@example.com", "pass")
        assert "error" in result

    def test_verify_token(self):
        auth = AuthManager()
        result = auth.signup("test@example.com", "pass123")
        token = result["token"]
        user = auth.verify_token(token)
        assert user is not None
        assert user.email == "test@example.com"

    def test_verify_bad_token(self):
        auth = AuthManager()
        assert auth.verify_token("invalid.token.here") is None


class TestEncryption:
    def test_encrypt_decrypt(self):
        store = EncryptedStore()
        data = {"api_key": "sk-secret-123", "name": "test"}
        encrypted = store.encrypt(data)
        decrypted = store.decrypt(encrypted)
        assert decrypted == data

    def test_save_and_load(self):
        store = EncryptedStore()
        path = Path(".cxo_data/test_encrypted.bin")
        data = {"secret": "value123"}
        store.save_encrypted(path, data)
        loaded = store.load_encrypted(path)
        assert loaded == data

    def test_load_nonexistent(self):
        store = EncryptedStore()
        assert store.load_encrypted(Path("nonexistent.bin")) is None

    def test_delete(self):
        store = EncryptedStore()
        path = Path(".cxo_data/to_delete.bin")
        store.save_encrypted(path, {"test": True})
        store.delete(path)
        assert not path.exists()


class TestDatabase:
    def test_init_creates_tables(self):
        import agentic_cxo.infrastructure.database as db_mod
        db_mod._engine = None
        db_mod._SessionLocal = None
        init_db()
        session = get_session()
        session.add(DBMessage(
            message_id="test1", role="user", content="Hello"
        ))
        session.commit()
        result = session.query(DBMessage).filter_by(
            message_id="test1"
        ).first()
        assert result is not None
        assert result.content == "Hello"
        session.close()

    def test_reminder_table(self):
        from datetime import datetime, timezone

        import agentic_cxo.infrastructure.database as db_mod
        db_mod._engine = None
        db_mod._SessionLocal = None
        init_db()
        session = get_session()
        session.add(DBReminder(
            reminder_id="r1",
            title="Test reminder",
            due_date=datetime.now(timezone.utc),
        ))
        session.commit()
        result = session.query(DBReminder).first()
        assert result.title == "Test reminder"
        session.close()


class TestScheduler:
    def test_start_stop(self):
        scheduler = start_scheduler()
        assert scheduler.running
        stop_scheduler()

    def test_list_jobs(self):
        start_scheduler()
        jobs = list_jobs()
        assert isinstance(jobs, list)
        stop_scheduler()
