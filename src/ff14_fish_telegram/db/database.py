"""SQLite database layer for tracking caught fish and sent reminders per user."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager

from ff14_fish_telegram.config import DATABASE_PATH


def get_connection() -> sqlite3.Connection:
    """Create and return a new SQLite connection with WAL mode and foreign keys."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create the caught_fish and sent_reminders tables if they don't exist."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS caught_fish (
                user_id INTEGER NOT NULL,
                fish_id INTEGER NOT NULL,
                caught_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, fish_id)
            )
        """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sent_reminders (
                user_id INTEGER NOT NULL,
                fish_id INTEGER NOT NULL,
                window_start_eorzea INTEGER NOT NULL,
                sent_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, fish_id, window_start_eorzea)
            )
        """
        )


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager providing a committed connection, with auto-rollback on error."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def mark_caught(user_id: int, fish_id: int) -> None:
    """Record that a user has caught a specific fish (upsert by primary key)."""
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO caught_fish (user_id, fish_id) VALUES (?, ?)",
            (user_id, fish_id),
        )


def mark_uncaught(user_id: int, fish_id: int) -> None:
    """Remove a fish from a user's caught list."""
    with get_db() as conn:
        conn.execute(
            "DELETE FROM caught_fish WHERE user_id = ? AND fish_id = ?",
            (user_id, fish_id),
        )


def is_caught(user_id: int, fish_id: int) -> bool:
    """Return True if the user has caught the given fish."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM caught_fish WHERE user_id = ? AND fish_id = ?",
            (user_id, fish_id),
        ).fetchone()
        return row is not None


def get_caught_fish_ids(user_id: int) -> set[int]:
    """Return the set of fish IDs the user has caught."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT fish_id FROM caught_fish WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        return {row["fish_id"] for row in rows}


def get_all_user_ids() -> set[int]:
    """Return all distinct user IDs that have at least one caught fish."""
    with get_db() as conn:
        rows = conn.execute("SELECT DISTINCT user_id FROM caught_fish").fetchall()
        return {row["user_id"] for row in rows}


# Prepared SQL statements for reminder deduplication lookups
_SENT_CHECK_SQL = (
    "SELECT 1 FROM sent_reminders WHERE user_id = ? AND fish_id = ? AND window_start_eorzea = ?"
)
_SENT_INSERT_SQL = (
    "INSERT OR IGNORE INTO sent_reminders (user_id, fish_id, window_start_eorzea) VALUES (?, ?, ?)"
)


def reminder_sent(user_id: int, fish_id: int, window_start_eorzea: int) -> bool:
    """Check whether a reminder was already sent for this user/fish/window combination."""
    with get_db() as conn:
        row = conn.execute(_SENT_CHECK_SQL, (user_id, fish_id, window_start_eorzea)).fetchone()
        return row is not None


def mark_reminder_sent(user_id: int, fish_id: int, window_start_eorzea: int) -> None:
    """Record that a reminder was sent to avoid duplicate notifications."""
    with get_db() as conn:
        conn.execute(_SENT_INSERT_SQL, (user_id, fish_id, window_start_eorzea))


def mark_caught_many(user_id: int, fish_ids: list[int]) -> None:
    """Atomically mark multiple fish as caught for a user in a single transaction."""
    with get_db() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO caught_fish (user_id, fish_id) VALUES (?, ?)",
            [(user_id, fid) for fid in fish_ids],
        )


def mark_uncaught_many(user_id: int, fish_ids: list[int]) -> None:
    """Atomically mark multiple fish as uncaught for a user in a single transaction."""
    with get_db() as conn:
        conn.executemany(
            "DELETE FROM caught_fish WHERE user_id = ? AND fish_id = ?",
            [(user_id, fid) for fid in fish_ids],
        )


def cleanup_old_reminders(days: int = 7) -> None:
    """Delete sent_reminders rows older than the given number of days."""
    with get_db() as conn:
        conn.execute(
            "DELETE FROM sent_reminders WHERE sent_at < datetime('now', ?)",
            (f"-{days} days",),
        )
