"""Manual column migrations for SQLite (and PostgreSQL).

SQLModel's create_all() only creates *missing* tables — it never alters
existing ones.  This module fills that gap: each entry in MIGRATIONS
describes a column that must exist; run_migrations() issues the
ALTER TABLE … ADD COLUMN only when the column is absent.
"""
from __future__ import annotations

from collections import namedtuple
from typing import List

from sqlalchemy import text
from sqlmodel import Session

ColumnMigration = namedtuple("ColumnMigration", ["table", "column", "definition"])

# ---------------------------------------------------------------------------
# Registry — add new entries at the END to keep history readable.
# ---------------------------------------------------------------------------
MIGRATIONS: List[ColumnMigration] = [
    # habits table — new columns added after initial schema
    ColumnMigration("habits", "habit_type",          "VARCHAR(20) NOT NULL DEFAULT 'binary'"),
    ColumnMigration("habits", "target_value",        "FLOAT"),
    ColumnMigration("habits", "current_streak",      "INTEGER NOT NULL DEFAULT 0"),
    ColumnMigration("habits", "max_streak",          "INTEGER NOT NULL DEFAULT 0"),
    ColumnMigration("habits", "streak_last_updated", "DATE"),
    # completions table — new columns added after initial schema
    ColumnMigration("completions", "progress_value", "FLOAT"),
    ColumnMigration("completions", "is_complete",    "BOOLEAN NOT NULL DEFAULT 0"),
]


def _existing_columns(session: Session, table: str) -> set[str]:
    """Return the set of column names currently in *table*."""
    rows = session.exec(text(f"PRAGMA table_info({table})")).fetchall()  # type: ignore[arg-type]
    return {row[1] for row in rows}  # column 1 is the name


def _backfill_is_complete(session: Session) -> None:
    """For pre-existing binary completions, set is_complete = 1."""
    session.exec(  # type: ignore[call-overload]
        text(
            "UPDATE completions SET is_complete = 1 "
            "WHERE is_complete = 0 AND progress_value IS NULL"
        )
    )


def run_migrations(engine) -> None:
    """Apply any missing column migrations, then commit."""
    with Session(engine) as session:
        # Group migrations by table so we only fetch PRAGMA once per table.
        tables: dict[str, list[ColumnMigration]] = {}
        for m in MIGRATIONS:
            tables.setdefault(m.table, []).append(m)

        any_change = False
        for table, cols in tables.items():
            existing = _existing_columns(session, table)
            for m in cols:
                if m.column not in existing:
                    session.exec(  # type: ignore[call-overload]
                        text(f"ALTER TABLE {m.table} ADD COLUMN {m.column} {m.definition}")
                    )
                    print(f"[migration] added {m.table}.{m.column}")
                    any_change = True

        if any_change:
            _backfill_is_complete(session)
            session.commit()
