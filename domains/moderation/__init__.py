"""
Moderation domain (Coding Assignment #2).

Owns two things:
  1. Detection: scoring and filtering the content of posts, comments and
     profiles against the platform's word lists (the rules page spec).
  2. Standing: the user-level risk score and the DC 31 sanctions ladder
     that turns it into fair, escalating responses.

Like every domain, nothing here imports Flask or sqlite3: usecases receive a
repository object and plain data, so the rules are unit-testable on their own.
"""