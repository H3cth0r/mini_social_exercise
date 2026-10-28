"""
Onboarding domain — use cases: the newcomer rules.

Pure business rules with the claim numbers they implement in the docstrings.
Repositories are passed in, so this module imports no sqlite3 or Flask.

Two mechanics:
1. Welcome crew (DC 18 + DC 20): newcomer accounts that nobody greeted yet
   are shown on the feed's welcome strip; each one gets ONE assigned greeter
   from the most active members; anyone can greet once (a working Say hi).
2. Progressive access (DC 25): during their first NEWCOMER_AGE_DAYS days,
   new accounts earn posting privileges step by step: one post per day,
   then full posting. Comments are never limited.
"""

import math

from .entities import Greeting, NewcomerEntry

# A 'newcomer' is an account younger than this many days (chapter 5's
# socialization window; the moderation domain already taught us 7 days is
# the 'brand new' line for risk, this is the friendlier end).
NEWCOMER_AGE_DAYS = 3.0

# The DC 25 feature: how many posts a new account may create per UTC day.
POSTS_PER_DAY_FOR_NEWCOMERS = 1


def is_newcomer(age_days):
    """True while the account is inside its first NEWCOMER_AGE_DAYS days."""
    return age_days is not None and age_days < NEWCOMER_AGE_DAYS


def posting_privilege(age_days, posts_today):
    """(allowed, reason, unlocks_in_days) — DC 25 as a pure rule.

    New accounts (< 3 days) may create ONE post per UTC day. Comments are
    never limited, because talking is the behaviour we want (DC 18) and
    flooding the feed is not. Old accounts post freely; unlocks_in_days is
    None for them (the privilege is already earned).
    """
    if not is_newcomer(age_days):
        return True, '', None
    days_left = max(1, math.ceil(NEWCOMER_AGE_DAYS - age_days))
    if posts_today >= POSTS_PER_DAY_FOR_NEWCOMERS:
        return (False,
                "You used today's post. You can post again tomorrow.",
                days_left)
    return True, '', days_left


def privilege_banner(age_days):
    """The quiet feed line explaining the limit, or None for old accounts."""
    if not is_newcomer(age_days):
        return None
    days_left = max(1, math.ceil(NEWCOMER_AGE_DAYS - age_days))
    day_word = 'day' if days_left == 1 else 'days'
    return (f"New account: 1 post per day. Unlimited posting unlocks in "
            f"{days_left} {day_word}.")


def needs_welcome(age_days, greetings_received):
    """DC 18 target: a recent account that has had NO interactions yet.

    Once someone greeted them, the newcomer is off the strip — the ask is
    answered, and the strip must never nag users who are already talking."""
    return is_newcomer(age_days) and greetings_received == 0


def assign_greeters(newcomer_ids, greeter_pool_ids):
    """DC 20 in one pure function: {newcomer_id: greeter_id}.

    Deterministic rotation over the most active members: newcomer i gets
    pool[i % pool size]. The pool SHOULD NOT be empty (the seed guarantees
    active users); a newcomer with an empty pool gets no assignment rather
    than a crash."""
    pool = [pid for pid in greeter_pool_ids]
    if not pool:
        return {}
    return {newcomer_ids[i]: pool[i % len(pool)] for i in range(len(newcomer_ids))}


def greeting_confirmation(newcomer_name):
    """Toast the greeter sees after saying hi (interactable response)."""
    return (f"👋 You greeted {newcomer_name} — now check their "
            f"profile and start talking!")


def welcome_toast(greeter_names):
    """Personal toast the newcomer sees on the feed (DC 18: the friend made
    real by a named person, not a system banner)."""
    who = greeter_names[0]
    return f"👋 {who} welcomed you to MiniSocial — browse and say hi!"


def assemble_welcome_entries(newcomer_rows, greetings_received,
                             assignments, viewer_id):
    """Build the strip's entries; rules, not SQL.

    newcomer_rows:       [(user_id, username, age_days)]
    greetings_received:  {user_id: count}
    assignments:         {newcomer_id: greeter_id} from assign_greeters
    greeter_ids:         ids the viewer already greeted
    viewer_id:           the current user (never in their own strip;
                         None means no strip at all — welcoming is a
                         community duty a logged-out user cannot act on)"""
    if viewer_id is None:
        return []
    entries = []
    for user_id, username, age_days in newcomer_rows:
        if user_id == viewer_id:
            continue
        if not needs_welcome(age_days, greetings_received.get(user_id, 0)):
            continue
        entries.append(NewcomerEntry(
            user_id=user_id,
            username=username,
            age_days=age_days,
            assigned_to_me=assignments.get(user_id) == viewer_id,
        ))
    # The DC 20 assignment comes first; then the freshest newcomers first.
    # No ranking is shown beyond this ordering (same limit as assignment 1's
    # crew: the order only decides who is visible).
    entries.sort(key=lambda e: (not e.assigned_to_me, e.user_id))
    return entries


def welcome_crew(repo, viewer_id):
    """Batch assembly for one feed render.

    viewer_id None (visitor) -> no strip: welcoming is a community duty,
    there is nothing a logged-out user can act on.

    Order matters: only members who NEED a welcome get a greeter assigned —
    already-greeted newcomers must not consume a slot in the rotation."""
    if viewer_id is None:
        return []
    newcomer_rows = repo.get_newcomers()
    if not newcomer_rows:
        return []
    greeted_counts = {
        row[0]: repo.count_greetings_received(row[0])
        for row in newcomer_rows}
    roster = [row for row in newcomer_rows
              if needs_welcome(row[2], greeted_counts.get(row[0], 0))]
    if not roster:
        return []
    pool = [pid for pid in repo.get_greeter_pool()
            if pid not in {row[0] for row in roster}]
    assignments = assign_greeters([row[0] for row in roster], pool)
    return assemble_welcome_entries(newcomer_rows, greeted_counts,
                                    assignments, viewer_id)


def can_greet(greeting_exists, viewer_newcomer_days):
    """(allowed, reason) — the single source of truth for the Say hi route.

    Rules (sincerity, like the nudge):
      - one greeting per pair, ever: a welcome is a first meeting, not spam;
      - old-timers do not get greeted either."""
    if greeting_exists:
        return False, "You already greeted them — one welcome per person."
    if viewer_newcomer_days is not None and viewer_newcomer_days < NEWCOMER_AGE_DAYS:
        return False, "Newcomers greet each other later — welcome the older members first!"
    return True, ""