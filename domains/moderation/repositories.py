"""
Moderation domain — repositories. ONLY SQL lives here.

Mirrors the contributions domain: the app passes in its request-scoped
sqlite connection, this class turns it into small typed reads the usecases
need (user age, content texts, last-post time). Returns plain dicts/lists —
no rules, no entities with behavior.
"""


class ModerationRepository:
    def __init__(self, db):
        self.db = db

    def get_user_with_age(self, user_id):
        """The user row plus their account age in days (float), or None.

        Timestamps are TEXT 'YYYY-MM-DD HH:MM:SS' UTC, exactly what SQLite's
        julianday() parses, so the age is computed in the database where
        'now' is UTC like the stored timestamps."""
        row = self.db.execute(
            'SELECT id, username, profile, '
            'julianday(\'now\') - julianday(created_at) AS age_days '
            'FROM users WHERE id = ?', (user_id,)).fetchone()
        if row is None:
            return None
        return {'id': row['id'], 'username': row['username'],
                'profile': row['profile'], 'age_days': row['age_days']}

    def get_user_content_texts(self, user_id):
        """Everything of this user that moderation scores:
        (profile_text, [post texts], [comment texts])."""
        row = self.db.execute(
            'SELECT profile FROM users WHERE id = ?', (user_id,)).fetchone()
        if row is None:
            return None, [], []
        profile = row[0]
        posts = [row[0] for row in self.db.execute(
            'SELECT content FROM posts WHERE user_id = ? '
            'ORDER BY created_at', (user_id,))]
        comments = [row[0] for row in self.db.execute(
            'SELECT content FROM comments WHERE user_id = ? '
            'ORDER BY created_at', (user_id,))]
        return profile, posts, comments

    def get_minutes_since_last_post(self, user_id):
        """Minutes since the user's newest post, or None if they never posted
        (the ladder's throttle treats a first-ever post as outside any
        cooldown)."""
        row = self.db.execute(
            'SELECT (julianday(\'now\') - julianday(MAX(created_at))) * 1440.0 '
            'FROM posts WHERE user_id = ?', (user_id,)).fetchone()
        return row[0] if row[0] is not None else None