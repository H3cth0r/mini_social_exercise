"""
Streaks domain — the streak feature of MiniSocial.

Layers inside this package (Clean-style, package-by-domain):

    entities.py      pure data objects (Streak)
    usecases.py      ONLY business rules; receives a repository, no sqlite
    repositories.py  ONLY SQL; returns plain dicts, no rules

The dependency rule: app.py -> usecases -> entities + repositories, never
backwards. app.py never touches repositories directly, and nothing here
imports Flask or Jinja.
"""