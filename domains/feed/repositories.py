"""Feed domain — repositories. ONLY SQL lives here.

Mirrors the other domains: the app passes in its request-scoped sqlite
connection, this class turns it into the small reads the recommendation
usecases need. Returns plain dicts/lists — no rules here.

Timestamps are TEXT 'YYYY-MM-DD HH:MM:SS' UTC and reactions carry no
timestamps, so no date math is needed in this repository.
"""


class FeedRepository:
    """Data access for the recommendation feature. One instance per request."""

    def __init__(self, db):
        """db: an open sqlite3 connection (from app.get_db())."""
        self.db = db

    def get_positive_reacted_post_texts(self, user_id):
        """Texts of the posts this user reacted to positively.

        'Positive' is everything except sad/angry (the usecase owns that
        definition; this query just takes its NEGATIVE_REACTIONS list)."""
        rows = self.db.execute(
            'SELECT p.content FROM posts p '
            'JOIN reactions r ON r.post_id = p.id '
            'WHERE r.user_id = ? AND r.reaction_type NOT IN (?, ?)',
            (user_id, 'sad', 'angry')).fetchall()
        return [row[0] for row in rows]

    def get_followed_ids(self, viewer_id):
        """set: the users the viewer follows."""
        rows = self.db.execute(
            'SELECT followed_id FROM follows WHERE follower_id = ?',
            (viewer_id,)).fetchall()
        return {row[0] for row in rows}

    def get_post_texts_by_users(self, user_ids):
        """Texts of ALL posts written by the given users (their general
        topics, the weaker half of the interest profile)."""
        user_ids = list(user_ids)
        if not user_ids:
            return []
        placeholders = ','.join('?' * len(user_ids))
        rows = self.db.execute(
            f'SELECT p.content FROM posts p WHERE p.user_id IN ({placeholders})',
            tuple(user_ids)).fetchall()
        return [row[0] for row in rows]

    def get_candidate_posts(self, user_id, follow_only=False):
        """The posts that may be recommended to this user.

        Excluded by design (the recommendation must be NEW relevant content):
          - the viewer's own posts;
          - posts the viewer already reacted to, negatively included
            (they have seen and judged them).
        follow_only restricts the pool to followed users' posts.

        Shape matches what the feed route consumes: id, content,
        created_at, username, user_id — plus ordering here so the usecase
        only scores."""
        where = ('p.user_id != ? '
                 'AND p.id NOT IN (SELECT post_id FROM reactions WHERE user_id = ?)')
        params = [user_id, user_id]
        if follow_only:
            where += (' AND p.user_id IN '
                      '(SELECT followed_id FROM follows WHERE follower_id = ?)')
            params.append(user_id)
        rows = self.db.execute(
            f'SELECT p.id, p.content, p.created_at, u.username, u.id AS user_id '
            f'FROM posts p JOIN users u ON p.user_id = u.id '
            f'WHERE {where} ORDER BY p.created_at DESC, p.id DESC',
            tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def get_recent_posts(self, limit):
        """Newest posts, the fallback content when there are no signals.

        Same shape as get_candidate_posts; excludes nothing, so visitors
        (user_id None) and zero-signal users still get a useful tab."""
        rows = self.db.execute(
            'SELECT p.id, p.content, p.created_at, u.username, u.id AS user_id '
            'FROM posts p JOIN users u ON p.user_id = u.id '
            'ORDER BY p.created_at DESC, p.id DESC LIMIT ?',
            (limit,)).fetchall()
        return [dict(row) for row in rows]