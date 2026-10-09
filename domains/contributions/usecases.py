"""
Contributions domain — use cases (streak rules).

Only business rules live here (what a streak is, when it is at risk, toast
copy). Repositories are passed in, so this module imports no sqlite3 or
Flask and is unit-testable with a fake repository.
"""

import datetime

from .entities import CrewEntry, Streak

# Streak lengths celebrated with a special toast (design claim 13).
MILESTONES = (3, 7, 14, 30)

_DATE_FORMAT = '%Y-%m-%d'


def utc_today():
    """Today as the app stores it: the UTC date, 'YYYY-MM-DD'.

    Server time and SQLite timestamps are both UTC, so they share one
    timeline (and the day boundary is UTC midnight).
    """
    return datetime.datetime.utcnow().strftime(_DATE_FORMAT)


def compute_streak(daily_counts, today):
    """Streak for one user from their daily counts.

    daily_counts: {date_string: count} (from a repository).
    today: the current UTC date, 'YYYY-MM-DD'.
    Returns a Streak: consecutive days ending today, or ending yesterday
    when nothing today yet (at_risk=True); a missed day resets to 0.
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
    """Longest run of consecutive days in the user's full history (int)."""
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


def current_streak(repo, user_id, today=None):
    """Current streak for one user (badge/banner state; best not computed)."""
    if today is None:
        today = utc_today()
    return compute_streak(repo.get_daily_counts(user_id), today)


def get_user_streak(repo, user_id, today=None):
    """Full streak info for one user: current, at_risk and personal best."""
    if today is None:
        today = utc_today()
    days = repo.get_daily_counts(user_id)
    streak = compute_streak(days, today)
    streak.best = compute_best_streak(days)
    return streak


def get_streaks_for_users(repo, user_ids, today=None):
    """Batch version for pages showing many users at once.

    One repository query for the whole page, one rule pass per user.
    Returns {user_id: Streak} for every requested user (no history ->
    Streak(0, False), rendered as nothing by the badge macro).
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
    """Toast copy for the contribution that grew the streak to `current`.

    Milestones get their own wording; everything else reports the length.
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


# ---------------------------------------------------------------------------
# Streak rescue: the at-risk crew and nudges.
#
# A nudge is a personal ASK from one user to another ("save your streak!") —
# a mechanic between users, not a display. The rules it follows:
#   - Only a *genuinely at-risk* streak can be nudged (streak >= 1 day,
#     nothing contributed today) — there must be something real to rescue.
#   - One nudge per (nudger -> target) per UTC day.
#   - A nudge NEVER extends or fakes a streak; only the target's own
#     posting/commenting does (praise/asks must stay sincere — claim 20).
#   - The crew shows familiar people first (claim 11: asks from people we
#     know feel personal), never a ranking (claim 22: no competition).
# ---------------------------------------------------------------------------

# How many crew cards the feed shows at most.
CREW_SIZE = 6


def nudge_eligibility(target_streak, target_at_risk, already_nudged_today):
    """(allowed, reason) — the single source of truth for whether a nudge
    happens. The route re-checks with fresh data; the button in the template
    is never trusted."""
    if already_nudged_today:
        return False, 'You already nudged them today — one nudge per day.'
    if target_streak < 1 or not target_at_risk:
        return False, 'Their streak is not at risk right now.'
    return True, ''


def nudge_message(nudger_name, streak):
    """Toast the nudged user sees on their next visit (claims 4 and 10: a
    personal ask from a named peer, stressing the benefit of acting today)."""
    day_word = 'day' if streak == 1 else 'days'
    return (f"🔥 {nudger_name} hopes you keep your {streak}-{day_word} "
            f"streak — contribute today!")


def nudge_confirmation(nudged_name):
    """Toast the nudger sees after sending (interactable response)."""
    return f"You nudged {nudged_name} — hopefully they're back for one more day!"


def nudged_you_message(count):
    """Profile-card credit line, or None when nobody nudged (rendered as
    nothing — no nagging, no counters for idle users, claims 20/21)."""
    if count <= 0:
        return None
    who = '1 friend nudged' if count == 1 else f'{count} friends nudged'
    return f"{who} you this week — the streak must go on!"


def assemble_crew(streak_by_user, username_by_id, viewer_id, followed_ids,
                  nudged_today_ids, crew_size=CREW_SIZE):
    """The feed's rescue crew: at-risk users, viewer excluded.

    streak_by_user:   {user_id: Streak}
    username_by_id:   {user_id: username}
    followed_ids:     set of ids the viewer follows
    nudged_today_ids: ids the viewer already nudged today

    Ordering rule (no ranking is SHOWN — the order only decides who gets
    the limited card slots): followed users first (claim 11: familiar asks
    work), then the longest streaks (the most saveable one is closest to
    their milestone, claim 13). Capped at crew_size.
    """
    entries = []
    for user_id, streak_entity in streak_by_user.items():
        # Eligibility, again pure: alive streak, nothing today, not the viewer.
        if user_id == viewer_id:
            continue
        if not streak_entity.at_risk or streak_entity.current < 1:
            continue
        entries.append(CrewEntry(
            user_id=user_id,
            username=username_by_id.get(user_id, f'user {user_id}'),
            streak=streak_entity.current,
            followed_by_viewer=user_id in (followed_ids or ()),
            nudged_today=user_id in (nudged_today_ids or ()),
        ))
    # False sorts before True, so followed entries come first; then longest.
    entries.sort(key=lambda e: (not e.followed_by_viewer, -e.streak, e.username))
    return entries[:crew_size]


def rescue_crew(repo, viewer_id, today=None):
    """One batch assembly of the whole crew for a feed render.

    Repository reads happen here (they are batch-sized, one small query
    each); every rule lives in assemble_crew / compute_streak above. No
    crew for logged-out visitors.
    """
    if viewer_id is None:
        return []
    if today is None:
        today = utc_today()
    users = repo.get_users_except(viewer_id)
    user_ids = [uid for uid, _ in users]
    username_by_id = {uid: name for uid, name in users}
    streak_by_user = get_streaks_for_users(repo, user_ids, today)
    return assemble_crew(
        streak_by_user,
        username_by_id,
        viewer_id,
        repo.get_followed_ids(viewer_id),
        repo.get_nudged_ids_by(viewer_id, today),
    )


def week_start_day(today):
    """'YYYY-MM-DD' six days before `today` — the start of this UTC week
    (inclusive), the window the profile's nudge credit counts over."""
    day = _to_date(today) - datetime.timedelta(days=6)
    return day.strftime(_DATE_FORMAT)