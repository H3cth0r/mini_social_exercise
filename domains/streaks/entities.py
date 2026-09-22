"""
Streaks domain — entities.

Pure data objects shared by usecases.py and (unwrapped) by the interface layer.
No SQL, no Flask, no Jinja — entities know nothing about how they are stored
or displayed.
"""

from dataclasses import dataclass


@dataclass
class Streak:
    """
    A user's contribution streak.

    current: number of consecutive days with >= 1 contribution (post or
             comment), ending today — or yesterday if nothing today yet.
    at_risk: True when the streak is alive via yesterday but the user has
             not contributed today; the feed banner warns about this state.
    best:    the longest run of consecutive days in the user's FULL history
             (computed on request, so no schema change is needed). Only
             populated where the page shows it (the profile).
    """
    current: int
    at_risk: bool
    best: int = 0