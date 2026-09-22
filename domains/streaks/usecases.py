"""
Streaks domain — use cases.

ONLY business rules live here: what a streak is, when it is at risk, which
lengths count as milestones, what the flash message says. Receives a
repository as a parameter (dependency injection) and returns entities —
this module never imports sqlite3, Flask, or Jinja, so it is unit-testable
with a plain fake repository.
"""

import datetime

from .entities import Streak

# Streak lengths celebrated with a special toast, exactly once (on the
# contribution that reaches them). System-suggested goals
# (Kraut & Resnick 2011, ch. 2, design claim 13).
MILESTONES = (3, 7, 14, 30)

_DATE_FORMAT = '%Y-%m-%d'


def utc_today():
    """Today's date as the app stores it: the UTC date, 'YYYY-MM-DD'.

    The server and the Docker container both run UTC and SQLite stores
    CURRENT_TIMESTAMP in UTC, so utcnow() and date(created_at) share one
    timeline. Simplification: a post at 00:30 Finnish time (21:30 UTC of the
    previous day) counts toward the previous UTC day.
    """
    return datetime.datetime.utcnow().strftime(_DATE_FORMAT)


def compute_streak(daily_counts, today):
    """
    Args:
        daily_counts: {date_string: count} for one user (from a repository).
        today: the current UTC date, 'YYYY-MM-DD'.

    Returns:
        Streak: consecutive days ending today — or yesterday if nothing
        today yet (then at_risk=True). A fully missed day resets to
        Streak(0, at_risk=False).
    """
    current = 0
    day = _to_date(today)
    # Keys may be date strings ('2026-09-22'); compare everything as dates.
    days = {_to_date(k) for k in daily_counts}
    if day not in days:
        # Nothing today: the streak can only survive via yesterday,
        # and it is "at risk" until the user contributes today.
        day = _day_before(day)
        if day not in days:
            return Streak(current=0, at_risk=False)
        at_risk = True
    else:
        at_risk = False

    # Walk back, day by day, while the user contributed.
    while day in days:
        current += 1
        day = _day_before(day)
    return Streak(current=current, at_risk=at_risk)


def compute_best_streak(daily_counts):
    """
    Args:
        daily_counts: {date_string: count}, as returned by a repository.

    Returns:
        The longest run of consecutive days anywhere in the user's full
        history (int). Pure computation over the daily counts.
    """
    if not daily_counts:
        return 0
    best = 0
    run = 0
    previous = None
    for day in sorted(daily_counts):
        day_date = _to_date(day)
        if previous is not None and day_date == previous + datetime.timedelta(days=1):
            run += 1
        else:
            run = 1
        best = max(best, run)
        previous = day_date
    return best


def get_streaks_for_users(repo, user_ids, today=None):
    """
    Batch use case for pages that show many usernames at once (the feed,
    post detail, follower lists). One repository query for the whole page,
    then one rule pass per user.

    Args:
        repo: a streaks repository (the real one, or a fake in tests).
        user_ids: iterable of user ids shown on the page.
        today: optional UTC date override ('YYYY-MM-DD'), for testing.

    Returns:
        {user_id: Streak} for every user in user_ids. Users with no history
        map to Streak(0, False), which the streak_badge macro renders as
        nothing.
    """
    user_ids = list(user_ids)
    if not user_ids:
        return {}
    if today is None:
        today = utc_today()
    days_by_user = repo.get_activity_days_for_users(user_ids)
    return {
        user_id: compute_streak(days_by_user.get(user_id, {}), today)
        for user_id in user_ids
    }


def streak_flash_message(current):
    """
    Toast copy shown right after the contribution that grew the streak.
    Only called when the streak actually changed today, so the praise always
    states a verifiable fact (design claim 20: feedback must be sincere).

    Milestone streaks get their own wording (design claim 13: concrete,
    challenging goals); everything else reports the streak length.
    """
    if current in MILESTONES:
        return f"🎉 You posted {current} days in a row!"
    return (f"🔥 Streak extended to {current} "
            f"day{'s' if current != 1 else ''}!")


def _to_date(value):
    """'YYYY-MM-DD' (or a full 'YYYY-MM-DD HH:MM:SS' timestamp) -> date."""
    if isinstance(value, datetime.date):
        return value
    return datetime.datetime.strptime(str(value)[:10], _DATE_FORMAT).date()


def _day_before(day):
    return day - datetime.timedelta(days=1)