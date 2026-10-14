"""
Onboarding domain.

Owns the newcomer lifecycle: which members are new, who is responsible for
welcoming them, and the greetings exchanged. Implements two chapter-5
design claims:
  DC 18 - friendly interactions with newcomers soon after joining make them
          stay and contribute more.
  DC 20 - assigning the responsibility for those interactions to particular
          members increases their frequency.

Like every domain, nothing here imports Flask or sqlite3: usecases receive
a repository object and plain data, so the rules are unit-testable on their
own.
"""