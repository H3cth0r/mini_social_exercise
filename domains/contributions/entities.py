"""
Contributions domain — entities.

Pure data objects shared by usecases.py and (unwrapped) by the interface layer.
No SQL, no Flask, no Jinja — entities know nothing about how they are stored
or displayed.
"""

from dataclasses import dataclass


@dataclass
class Streak:
    """A user's contribution streak, computed from their daily activity.

    current:  consecutive days with at least one contribution, ending today
              or yesterday.
    at_risk:  True when the streak is alive only via yesterday — one more
              day without contributing breaks it.
    best:     the longest streak this user ever had (0 when not computed;
              profile pages compute it, batch pages don't need it).
    """

    current: int
    at_risk: bool
    best: int = 0


# --- Streak rescue: the at-risk crew and nudges -----------------------------
# A nudge is a personal ASK from one user to another to save the target's
# at-risk streak. It never changes any streak — only the target's own
# contribution does. An ask is an interaction between users, not a display.

@dataclass
class Nudge:
    """One rescue nudge, nudger -> nudged, on one UTC day.

    day: 'YYYY-MM-DD'. Only the day is stored (no timestamp) because every
    nudge rule is day-scoped: one nudge per pair per day, weekly credit.
    """

    nudger_id: int
    nudged_id: int
    day: str


@dataclass
class CrewEntry:
    """One at-risk user as shown in the feed's rescue-crew strip."""

    user_id: int
    username: str
    streak: int                      # days they could still save today
    followed_by_viewer: bool = False # the viewer follows them (crews show
                                     # familiar people first)
    nudged_today: bool = False       # viewer already nudged them today
