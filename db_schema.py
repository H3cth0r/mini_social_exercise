"""
Database schema boot: make sure the tables the app needs exist.

Background: this codebase has no schema file — the tables ship inside
database.sqlite. This module reads schema.sql (one CREATE TABLE IF NOT
EXISTS per table), asks the database which tables it already has, and runs
only the statements whose table is missing. Two properties make it safe to
run at every startup:

  - idempotent: a healthy database gets zero writes;
  - bootstrap: a brand-new database file comes up fully formed.

Existing tables are never rewritten — the check is the migration mechanism.
"""

import re
import sqlite3

# Table names the schema file creates, read from each statement.
_CREATE_PATTERN = re.compile(
    r'CREATE TABLE (?:IF NOT EXISTS )?["\']?(\w+)', re.IGNORECASE)


def statements_from_file(schema_path):
    """The CREATE statements in schema.sql, comments stripped.

    A naive ';' split would break on a comment containing one, so comment
    lines are removed first (the file format is simple: '--' comments)."""
    with open(schema_path) as schema_file:
        lines = [line for line in schema_file if not line.strip().startswith('--')]
    return [part.strip() for part in '\n'.join(lines).split(';') if part.strip()]


def ensure_schema(db_path, schema_path):
    """Create the missing tables per schema.sql. Returns the names of the
    tables it created ([] on a healthy/unmodified database)."""
    statements = statements_from_file(schema_path)
    created = []
    db = sqlite3.connect(db_path)
    try:
        existing = {row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        for statement in statements:
            table = _CREATE_PATTERN.match(statement)
            if table and table.group(1) in existing:
                continue  # healthy database: skip, write nothing
            db.execute(statement)
            created.append(table.group(1) if table else '<unnamed statement>')
        db.commit()
    finally:
        db.close()
    return created