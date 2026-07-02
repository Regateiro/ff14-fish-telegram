"""Tests for the SQLite database layer (caught_fish and sent_reminders tables)."""

import os
import tempfile

import pytest

from ff14_fish_telegram import db as db_module
from ff14_fish_telegram.db.database import (
    cleanup_old_reminders,
    get_all_user_ids,
    get_caught_fish_ids,
    get_connection,
    init_db,
    is_caught,
    mark_caught,
    mark_reminder_sent,
    mark_uncaught,
    reminder_sent,
)


@pytest.fixture(autouse=True)
def _use_temp_db():
    """Replace DATABASE_PATH with a temporary file for each test, then clean up."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    original = db_module.database.DATABASE_PATH
    db_module.database.DATABASE_PATH = path
    init_db()
    yield
    db_module.database.DATABASE_PATH = original
    os.unlink(path)


class TestCaughtFish:
    """Tests for mark_caught, mark_uncaught, is_caught, and related queries."""

    def test_mark_and_check_caught(self):
        mark_caught(1001, 4898)
        assert is_caught(1001, 4898) is True

    def test_mark_uncaught(self):
        mark_caught(1001, 4898)
        mark_uncaught(1001, 4898)
        assert is_caught(1001, 4898) is False

    def test_is_caught_returns_false_for_uncaught(self):
        assert is_caught(1001, 4898) is False

    def test_get_caught_fish_ids(self):
        mark_caught(1001, 4898)
        mark_caught(1001, 4911)
        ids = get_caught_fish_ids(1001)
        assert ids == {4898, 4911}

    def test_get_caught_fish_ids_empty(self):
        assert get_caught_fish_ids(1001) == set()

    def test_get_all_user_ids(self):
        mark_caught(1001, 4898)
        mark_caught(2002, 4911)
        users = get_all_user_ids()
        assert users == {1001, 2002}

    def test_get_all_user_ids_empty(self):
        assert get_all_user_ids() == set()

    def test_replace_caught(self):
        mark_caught(1001, 4898)
        mark_caught(1001, 4898)
        assert is_caught(1001, 4898) is True

    def test_delete_nonexistent(self):
        mark_uncaught(9999, 9999)
        assert True


class TestReminders:
    """Tests for sent_reminders tracking (deduplication, isolation, cleanup)."""

    def test_reminder_not_sent_initially(self):
        assert reminder_sent(1001, 4898, 12345) is False

    def test_mark_and_check_reminder(self):
        mark_reminder_sent(1001, 4898, 12345)
        assert reminder_sent(1001, 4898, 12345) is True

    def test_reminder_different_window(self):
        mark_reminder_sent(1001, 4898, 12345)
        assert reminder_sent(1001, 4898, 67890) is False

    def test_reminder_different_user(self):
        mark_reminder_sent(1001, 4898, 12345)
        assert reminder_sent(2002, 4898, 12345) is False

    def test_reminder_duplicate(self):
        mark_reminder_sent(1001, 4898, 12345)
        mark_reminder_sent(1001, 4898, 12345)
        assert reminder_sent(1001, 4898, 12345) is True

    def test_cleanup_old_reminders(self):
        mark_reminder_sent(1001, 4898, 12345)
        with get_connection() as conn:
            conn.execute("UPDATE sent_reminders SET sent_at = datetime('now', '-30 days')")
        cleanup_old_reminders(days=7)
        assert reminder_sent(1001, 4898, 12345) is False
