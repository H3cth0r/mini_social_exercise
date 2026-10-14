"""Onboarding domain — repositories. ONLY SQL lives here.

Like the other domains: plain reads + writes, rules stay in usecases.py.
Age math reuses the julianday() pattern from the streaks domain (timestamps
are TEXT 'YYYY-MM-DD HH:MM:SS' UTC).
"""


class OnboardingRepository:
    """Data access for the welcome crew. One instance per request."""

    def __init__(self, db):
        """db: an open sqlite3 connection (from app.get_db())."""
        self.db = db

    def get_account_age(self, user_id):
        """The account's age in days (float), or None if it doesn't exist.

        Needed by the greeting rule: brand-new members greet later."""
        row = self.db.execute(
            "SELECT julianday('now') - julianday(created_at) FROM users "
            "WHERE id = ?", (user_id,)).fetchone()
        return row[0] if row else None

    def get_newcomers(self):
        """[(user_id, username, age_days)] — accounts inside their first
        3 days. Positional tuples, newest signup first."""
        rows = self.db.execute(
            "SELECT id, username, julianday('now') - julianday(created_at) "
            "FROM users WHERE julianday('now') - julianday(created_at) < 3 "
            "ORDER BY created_at DESC").fetchall()
        return [(row[0], row[1], row[2]) for row in rows]

    def count_greetings_received(self, newcomer_id):
        """How many greetings the newcomer has received (0 = nobody cared yet)."""
        row = self.db.execute(
            "SELECT COUNT(*) FROM greetings WHERE newcomer_id = ?",
            (newcomer_id,)).fetchone()
        return row[0]

    def greeting_exists(self, greeter_id, newcomer_id):
        """True when this pair already has a welcome (once per pair, ever)."""
        return self.db.execute(
            "SELECT 1 FROM greetings WHERE greeter_id = ? AND newcomer_id = ?",
            (greeter_id, newcomer_id)).fetchone() is not None

    def save_greeting(self, greeting):
        """Insert one greeting. The caller has re-checked eligibility."""
        self.db.execute(
            "INSERT INTO greetings (greeter_id, newcomer_id, day) VALUES (?, ?, ?)",
            (greeting.greeter_id, greeting.newcomer_id, greeting.day))
        self.db.commit()

    def get_greeter_names(self, newcomer_id):
        """Usernames of the people who greeted this newcomer — the personal
        toast names a real person, not 'the community'."""
        rows = self.db.execute(
            "SELECT u.username FROM greetings g JOIN users u "
            "ON g.greeter_id = u.id WHERE g.newcomer_id = ? "
            "ORDER BY g.id DESC", (newcomer_id,)).fetchall()
        return [row[0] for row in rows]

    def get_greeter_pool(self, limit=8):
        """The DC 20 pool: the most active members of the last 30 days.

        'Active' = posts + comments in the window, most first. This is who
        takes responsibility for welcoming; rotation spreads newcomers
        between them."""
        rows = self.db.execute(
            """
            SELECT user_id, n FROM (
                SELECT p.user_id AS user_id, COUNT(*) AS n
                FROM posts p
                WHERE julianday('now') - julianday(p.created_at) < 30
                GROUP BY p.user_id
                UNION ALL
                SELECT c.user_id AS user_id, COUNT(*) AS n
                FROM comments c
                WHERE julianday('now') - julianday(c.created_at) < 30
                GROUP BY c.user_id
            ) GROUP BY user_id ORDER BY SUM(n) DESC LIMIT ?
            """,
            (limit,)).fetchall()
        return [row[0] for row in rows]