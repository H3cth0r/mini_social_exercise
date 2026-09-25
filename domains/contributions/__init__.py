"""
Contributions domain — user contribution activity (posts + comments).

The data of this domain is one thing: how much each user contributed, per
day. Features interpret that data in different ways — right now, the streak
feature (Coding Assignment #1); later, e.g. the heatmap (Assignment #2).

Layers inside this package (Clean-style, package-by-domain):

    entities.py      pure data objects (Streak)
    usecases.py      ONLY business rules; receives a repository, no sqlite
    repositories.py  ONLY SQL; returns plain dicts, no rules

The dependency rule: app.py -> usecases -> entities + repositories, never
backwards. app.py never touches repositories directly, and nothing here
imports Flask or Jinja.
"""
