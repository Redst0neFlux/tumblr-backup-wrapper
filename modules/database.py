"""Database management for Tumblr backup tracking.

This module stores two concerns in a single SQLite file `data.db`:
- `previous_names` — tracks historical blog names and last backup timestamps
- `blog_options` — stores per-blog options that were previously kept in
"""

import datetime
import json
import sqlite3

DB_LOCATION = "data.db"


def initialize_db() -> sqlite3.Connection:
    """Create or open the previous names database and required tables.

    Returns an open `sqlite3.Connection`. Callers may use it as a context
    manager (``with initialize_db() as conn:``).
    """
    connection: sqlite3.Connection = sqlite3.connect(DB_LOCATION)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS previous_names (
            uuid TEXT NOT NULL,
            name TEXT NOT NULL,
            last_backup TEXT,
            UNIQUE(uuid, name)
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_previous_names_uuid ON previous_names(uuid)"
    )

    # Table to hold options that used to live in blogoptions.json
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS blog_options (
            uuid TEXT PRIMARY KEY,
            options TEXT NOT NULL
        )
        """
    )
    connection.commit()

    return connection


def get_last_backup_timestamp(connection: sqlite3.Connection, uuid: str) -> str | None:
    """Get the most recent backup timestamp for a blog UUID.

    Args:
        connection: SQLite database connection
        uuid: Blog UUID

    Returns:
        ISO format timestamp string or None if no backups recorded
    """
    cursor: sqlite3.Cursor = connection.execute(
        "SELECT MAX(last_backup) FROM previous_names WHERE uuid = ?",
        (uuid,),
    )
    row: list[str] = cursor.fetchone()
    return row[0] if row and row[0] is not None else None


def upsert_previous_name(
    connection: sqlite3.Connection, uuid: str, name: str, last_backup: str | None = None
) -> None:
    """Insert or update a previous name record with optional timestamp.

    Args:
        connection: SQLite database connection
        uuid: Blog UUID
        name: Blog name
        last_backup: Optional ISO format timestamp. If None, uses current UTC time, or a very early UTC time for new records.
    """
    connection.execute(
        """
        INSERT INTO previous_names (uuid, name, last_backup)
        VALUES (?, ?, ?)
        ON CONFLICT(uuid, name) DO UPDATE SET last_backup = ?
        """,
        (
            uuid,
            name,
            last_backup or "0001-01-01T00:00:00",
            last_backup or datetime.datetime.now(datetime.timezone.utc).isoformat(),
        ),
    )
    connection.commit()


# -- Blog options helpers (migrated from blogoptions.json) --


def get_blog_options(connection: sqlite3.Connection) -> dict[str, list[str]]:
    """Return all blog options stored in the database.

    The options are returned as a mapping of `uuid -> list[str]`.
    """
    cursor: sqlite3.Cursor = connection.execute(
        "SELECT uuid, options FROM blog_options"
    )
    rows: list[list[str]] = cursor.fetchall()
    out: dict[str, list[str]] = {}
    for uuid, options_text in rows:
        out[uuid] = json.loads(options_text)
    return out


def save_blog_options(
    connection: sqlite3.Connection, blog_options: dict[str, list[str]]
) -> None:
    """Persist the given blog options mapping into the DB.

    This upserts rows and removes any entries not present in `blog_options`.
    """
    # Upsert provided options
    for uuid, opts in blog_options.items():
        connection.execute(
            "INSERT INTO blog_options (uuid, options) VALUES (?, ?) \
                ON CONFLICT(uuid) DO UPDATE SET options = excluded.options",
            (uuid, json.dumps(list(opts))),
        )

    # Delete rows not present in the provided mapping
    if blog_options:
        placeholders: str = ",".join("?" for _ in blog_options)
        connection.execute(
            f"DELETE FROM blog_options WHERE uuid NOT IN ({placeholders})",
            tuple(blog_options.keys()),
        )
    else:
        # No options provided; clear the table
        connection.execute("DELETE FROM blog_options")
    connection.commit()


def search_blog_names(conn, query, strict=False) -> list[list[str]]:
    if query.startswith("t:"):
        cursor: sqlite3.Cursor = conn.execute(
            "SELECT uuid, name FROM previous_names WHERE uuid = ? ORDER BY last_backup DESC",
            (query,),
        )
    elif strict:
        cursor: sqlite3.Cursor = conn.execute(
            "SELECT uuid, name FROM previous_names WHERE name = ?",
            (query,),
        )
    else:
        cursor: sqlite3.Cursor = conn.execute(
            "SELECT uuid, name FROM previous_names WHERE name LIKE ?",
            (f"%{query}%",),
        )
    return cursor.fetchall()
