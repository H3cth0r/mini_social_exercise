"""
Moderation domain — use cases. Only business rules live here.

The module imports no sqlite3 and no Flask: word lists, repositories and
texts are all passed in. Every rule below is numbered after the spec on the
rules page (https://mini-social.szab.eu/rules), so the code can be checked
directly against the assignment.
"""

import re

from .entities import (ACTION_ACCEPT, ACTION_THROTTLE, ACTION_WARN, ModDecision,
                       Standing)

# Removal messages and the placeholder that replace content (fixed by the
# rules page — do not reword).
REMOVE_SEVERE_MESSAGE = "[content removed due to severe violation]"
REMOVE_SPAM_MESSAGE = "[content removed due to spam/scam policy]"
LINK_PLACEHOLDER = "[link removed]"

# Caps rule (1.2.3) thresholds: >15 characters and >70% of them uppercase.
CAPS_MIN_LETTERS = 15
CAPS_UPPER_RATIO = 0.7

_URL_PATTERN = re.compile(r'https?://\S+|www\.\S+', re.IGNORECASE)


def _word_matches(text, word_or_phrase):
    """How many case-insensitive whole-word/whole-phrase hits of the term."""
    # Word boundaries around the (escaped) term give the rules page's
    # "whole-word" semantics: "class" must not match "as", "cass" not "as".
    pattern = re.compile(r'\b' + re.escape(word_or_phrase) + r'\b', re.IGNORECASE)
    return len(pattern.findall(text))


def _is_caps_violation(text):
    """Caps rule 1.2.3, evaluated on the ORIGINAL text: the violation is the
    user's shouting, which survives even after a word was masked to asterisks
    (and asterisks/URLs are not alphabetic characters anyway)."""
    letters = [c for c in text if c.isalpha()]
    if not letters or len(letters) <= CAPS_MIN_LETTERS:
        return False
    upper_share = sum(1 for c in letters if c.isupper()) / len(letters)
    return upper_share > CAPS_UPPER_RATIO


def moderate(text, tier1_words, tier2_phrases, tier3_words):
    """Detect and score policy violations in one piece of content.

    Args:
        text: the raw content of a post, comment or profile.
        tier1_words: severe word list (whole words).
        tier2_phrases: spam/scam phrase list (whole phrases).
        tier3_words: mild profanity list (whole words).

    Returns:
        A ModDecision (filtered content + severity score):
        score < 1.0 none, 1.0-2.9 low, 3.0-4.9 medium, >= 5.0 high.

    The two removal stages short-circuit: on the first hit the whole content
    is replaced by the fixed message and the score is exactly 5.0.
    """
    # Rule 1.1.1 — Tier 1 severe violation: replace EVERYTHING, score 5.0.
    for word in tier1_words:
        if _word_matches(text, word) > 0:
            return ModDecision(REMOVE_SEVERE_MESSAGE, 5.0)

    # Rule 1.1.2 — Tier 2 spam/scam phrase (only when no Tier 1 word matched):
    # replace EVERYTHING, score 5.0.
    for phrase in tier2_phrases:
        if _word_matches(text, phrase) > 0:
            return ModDecision(REMOVE_SPAM_MESSAGE, 5.0)

    # Stage 1.2 — scored corrections. Nothing was removed, so the corrections
    # apply to the text and stack up the score.
    original = text  # kept for the caps rule, which judges what the user wrote
    score = 0.0

    # Rule 1.2.1 — Tier 3 mild profanity: mask each hit with same-length
    # asterisks, +2.0 per hit.
    for word in tier3_words:
        hits = _word_matches(text, word)
        if hits:
            score += 2.0 * hits
            text = re.sub(
                r'\b' + re.escape(word) + r'\b',
                lambda m: '*' * len(m.group()),
                text,
                flags=re.IGNORECASE)

    # Rule 1.2.2 — Links: replace each URL with a placeholder, +2.0 per link.
    urls = _URL_PATTERN.findall(text)
    if urls:
        score += 2.0 * len(urls)
        text = _URL_PATTERN.sub(LINK_PLACEHOLDER, text)

    # Rule 1.2.3 — excessive capitalisation: +0.5 flat, text left unmodified
    # (evaluated on the original text, see _is_caps_violation).
    if _is_caps_violation(original):
        score += 0.5

    return ModDecision(text, score)


# ----- Risk scores (rules page, stage 2) ------------------------------------

# Labels and boundaries exactly as the rules page defines them.
HIGH = 'HIGH'
MEDIUM = 'MEDIUM'
LOW = 'LOW'
NONE = 'NONE'


def classify(score):
    """Map a risk score to the rules page's labels: HIGH >= 5, MEDIUM >= 3,
    LOW >= 1, NONE below 1."""
    if score >= 5.0:
        return HIGH
    if score >= 3.0:
        return MEDIUM
    if score >= 1.0:
        return LOW
    return NONE


def content_risk_score(base_score, account_age_days):
    """Rule 2.1 — risk for ONE post or comment: the base score, times 1.5
    only for authors with a very new account (the same rule the admin panel
    already applies inline)."""
    if account_age_days < 7:
        return base_score * 1.5
    return base_score


def compute_user_score(profile_score, post_scores, comment_scores,
                       account_age_days):
    """Rule 2.2 — the user-level risk score.

    Args:
        profile_score: content score of the user's profile text.
        post_scores / comment_scores: base content scores (rule 1) of every
            post/comment. The rules page says the averages use these scores
            directly — the age multiplier applies once, at the user level,
            not twice. An empty list contributes an average of 0.
        account_age_days: the user's account age, deciding the multiplier.

    Returns:
        The user risk score: profile*1 + avg_post*3 + avg_comment*1, times
        the age multiplier (<7 days *1.5, <30 days *1.2), capped at 5.0.
    """
    avg_post = sum(post_scores) / len(post_scores) if post_scores else 0.0
    avg_comment = (sum(comment_scores) / len(comment_scores)
                   if comment_scores else 0.0)
    risk = (profile_score * 1) + (avg_post * 3) + (avg_comment * 1)

    if account_age_days < 7:
        risk *= 1.5
    elif account_age_days < 30:
        risk *= 1.2

    return min(5.0, risk)


def user_risk_score(repo, user_id, tier1_words, tier2_phrases, tier3_words):
    """Full user risk analysis: profile, posts and comments through
    moderate(), combined by compute_user_score() (rule 2.2).

    Returns 0.0 for an unknown user id (and logs nothing) — a missing user
    carries no risk."""
    user = repo.get_user_with_age(user_id)
    if user is None:
        return 0.0

    profile_text, post_texts, comment_texts = repo.get_user_content_texts(user_id)

    profile_score = moderate(profile_text or '', tier1_words, tier2_phrases,
                             tier3_words).score
    post_scores = [moderate(text, tier1_words, tier2_phrases, tier3_words).score
                   for text in post_texts]
    comment_scores = [moderate(text, tier1_words, tier2_phrases, tier3_words).score
                      for text in comment_texts]

    return compute_user_score(profile_score, post_scores, comment_scores,
                              user['age_days'])


# ----- DC 31: graduated sanctions ladder -------------------------------------

# A HIGH-risk account may post at most once per this many minutes.
THROTTLE_COOLDOWN_MINUTES = 60

# Face-saving messages (kept in the domain so the copy is testable): they do
# not accuse ("you are a spammer") — they state the rule, invite reading it,
# and make both standing and its end visible (design claims 23 + 31).
WARNING_MESSAGE = ('Heads up: this contribution goes against the community '
                   'guidelines (it will be filtered from view). Not a big '
                   'deal — check the rules page and carry on.')
THROTTLE_MESSAGE = ('To keep the feed safe, accounts currently at high risk '
                    'can post at most once per hour. Try again in about '
                    '{minutes} minutes — your standing improves automatically '
                    'as flagged content is removed.')


def standing(incoming_score, user_risk, minutes_since_last_post,
             content_kind='post'):
    """One attempt under the DC 31 ladder: what standing does the platform
    take on it?

    Args:
        incoming_score: base content score of what is being posted.
        user_risk: the user's current risk score (from user_risk_score).
        minutes_since_last_post: minutes since the author's newest post, or
            None if they never posted.
        content_kind: 'post' or 'comment'. The throttle is deliberately
            post-only: the ladder says a cooling-off limits the most visible
            surface, while conversation stays possible (proportionality).

    Returns:
        A Standing: accept / warn (with copy) / throttle (with copy + minutes).
    """
    label = classify(user_risk)

    # Low or no risk: no ladder response at all (do not nag people who behave).
    if label in (NONE, LOW):
        return Standing(ACTION_ACCEPT)

    # Medium risk: content still goes through, but any scored violation earns
    # a private, face-saving reminder (the ladder's first step).
    if label == MEDIUM:
        if incoming_score >= 1.0:
            return Standing(ACTION_WARN, WARNING_MESSAGE)
        return Standing(ACTION_ACCEPT)

    # High risk: a face-saving reminder is not enough — apply the cooling-off.
    if content_kind == 'comment':
        # Conversation stays open; the incoming comment is accepted.
        return Standing(ACTION_ACCEPT)

    if (minutes_since_last_post is None or
            minutes_since_last_post >= THROTTLE_COOLDOWN_MINUTES):
        return Standing(ACTION_ACCEPT)

    remaining = THROTTLE_COOLDOWN_MINUTES - minutes_since_last_post
    message = THROTTLE_MESSAGE.format(minutes=max(1, int(remaining)))
    return Standing(ACTION_THROTTLE, message, remaining)