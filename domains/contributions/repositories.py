"""
Streaks domain — repositories layer.

ONLY data access lives here: SQL queries against the posts and comments
tables, returning plain {date: count} dictionaries. No business rules, no
Flask, no Jinja. Business rules are in usecases.py; shared data shapes in
entities.py.

The repository is a class with the sqlite connection injected at construction
(app.py, the composition root, creates one per request). This keeps the
usecases free of any database detail — they receive a repository object and
call its methods.

Timestamps are stored as TEXT 'YYYY-MM-DD HH:MM:SS' in UTC (SQLite
CURRENT_TIMESTAMP), so a contribution's day is date(created_at), the UTC date.
"""


class ContributionRepository:
    """Data access for the contributions domain. One instance per request."""

    def __init__(self, db):
        """db: an open sqlite3 connection (from app.get_db())."""
        self.db = db

    def get_daily_counts(self, user_id):
        """{date: count} — posts + comments per UTC day for one user."""
        rows = self.db.execute(
            """
            SELECT date(created_at) AS d, COUNT(*) AS n
            FROM (
                SELECT created_at FROM posts WHERE user_id = ?
                UNION ALL
                SELECT created_at FROM comments WHERE user_id = ?
            )
            GROUP BY d
            """,
            (user_id, user_id),
        ).fetchall()
        # Positional access (row[0], row[1]) so this works with any
        # connection, with or without a custom row_factory.
        return {row[0]: row[1] for row in rows}

    def get_activity_days_for_users(self, user_ids):
        """Batch version: {user_id: {date: count}} for each of user_ids.

        Full history per user, one query for the whole page.
        """
        user_ids = list(user_ids)
        if not user_ids:
            return {}
        placeholders = ','.join('?' * len(user_ids))
        rows = self.db.execute(
            f"""
            SELECT user_id, date(created_at) AS d, COUNT(*) AS n
            FROM (
                SELECT user_id, created_at FROM posts WHERE user_id IN ({placeholders})
                UNION ALL
                SELECT user_id, created_at FROM comments WHERE user_id IN ({placeholders})
            )
            GROUP BY user_id, d
            """,
            tuple(user_ids) + tuple(user_ids),
        ).fetchall()
        days_by_user = {}
        for row in rows:
            days_by_user.setdefault(row[0], {})[row[1]] = row[2]
        # Contract: every requested user gets an entry, even if it is empty,
        # so callers never need to handle a missing key.
        return {user_id: days_by_user.get(user_id, {}) for user_id in user_ids}

    # --- Streak rescue: the at-risk crew and nudges -------------------------
    # Plain reads + writes for the nudge feature; every rule about WHO may
    # be nudged is in usecases.py. Same style as above: positional access,
    # plain Python types out.

    def get_users_except(self, viewer_id):
        """[(user_id, username)] for everyone but the viewer — the crew's
        candidate pool (assembling and filtering happens in usecases)."""
        rows = self.db.execute(
            'SELECT id, username FROM users WHERE id != ? '
            'ORDER BY username', (viewer_id,)).fetchall()
        return [(row[0], row[1]) for row in rows]

    def get_followed_ids(self, viewer_id):
        """set of ids the viewer follows (crews show familiar people first)."""
        rows = self.db.execute(
            'SELECT followed_id FROM follows WHERE follower_id = ?',
            (viewer_id,)).fetchall()
        return {row[0] for row in rows}

    def get_nudged_ids_by(self, nudger_id, day):
        """set of ids this user nudged on one UTC day (the per-day limit)."""
        rows = self.db.execute(
            'SELECT nudged_id FROM nudges WHERE nudger_id = ? AND day = ?',
            (nudger_id, day)).fetchall()
        return {row[0] for row in rows}

    def nudge_pair_exists(self, nudger_id, nudged_id, day):
        """True when this pair already exchanged a nudge on this UTC day."""
        return self.db.execute(
            'SELECT 1 FROM nudges WHERE nudger_id = ? AND nudged_id = ? '
            'AND day = ?', (nudger_id, nudged_id, day)).fetchone() is not None

    def save_nudge(self, nudge):
        """Insert one nudge. The caller has re-checked eligibility against
        fresh data; saving is never trusted to the template/route alone."""
        self.db.execute(
            'INSERT INTO nudges (nudger_id, nudged_id, day) VALUES (?, ?, ?)',
            (nudge.nudger_id, nudge.nudged_id, nudge.day))
        self.db.commit()

    def count_distinct_nudgers(self, nudged_id, since_day):
        """How many different friends nudged this user on/after since_day —
        the profile's 'N friends nudged you this week' credit."""
        row = self.db.execute(
            'SELECT COUNT(DISTINCT nudger_id) FROM nudges '
            'WHERE nudged_id = ? AND day >= ?', (nudged_id, since_day)).fetchone()
        return row[0]