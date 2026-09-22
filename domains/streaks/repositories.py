"""
Streaks domain — repositories layer.

ONLY data access lives here: SQL queries against the posts and comments
tables, returning plain {date: count} dictionaries. No business rules, no
Flask, no Jinja. Business rules are in usecases.py; shared data shapes in
entities.py.

Timestamps are stored as TEXT 'YYYY-MM-DD HH:MM:SS' in UTC (SQLite
CURRENT_TIMESTAMP), so a contribution's day is date(created_at), the UTC date.
"""


def get_daily_counts(db, user_id):
    """
    Args:
        db: an open sqlite3 connection.
        user_id: the user whose contribution history we count.

    Returns:
        {date_string: contribution_count} — the number of posts plus comments
        this user made on each UTC day, e.g. {'2026-09-21': 2, '2026-09-20': 1}.
        Days without contributions are simply absent from the dict.
    """
    rows = db.execute(
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
    # Positional access (row[0], row[1]) so the module works with any
    # connection, with or without a custom row_factory.
    return {row[0]: row[1] for row in rows}


def get_activity_days_for_users(db, user_ids):
    """
    Batch version for pages that show many usernames at once (the feed, post
    detail, follower lists), so we never run one query per post.

    Args:
        db: an open sqlite3 connection.
        user_ids: iterable of user ids shown on the page.

    Returns:
        {user_id: {date_string: count}} — the same shape get_daily_counts()
        returns for one user, for every user in user_ids. The full history is
        returned (not just recent days), so the usecases can compute both the
        current streak and the personal best.
    """
    user_ids = list(user_ids)
    if not user_ids:
        return {}
    placeholders = ','.join('?' * len(user_ids))
    rows = db.execute(
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