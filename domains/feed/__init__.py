"""
Feed domain.

Owns the ranking behind the feed's 'Recommended' tab: what to show a user
whose interests come from the posts they reacted to positively and the
users they follow (Coding Assignment #3).

Like every domain, nothing here imports Flask or sqlite3: usecases receive
a repository object and plain data, so the rules are unit-testable on their
own.
"""