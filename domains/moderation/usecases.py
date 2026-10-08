"""
Moderation domain — use cases. Only business rules live here.

The module imports no sqlite3 and no Flask: word lists, repositories and
texts are all passed in. Every rule below is numbered after the spec on the
rules page (https://mini-social.szab.eu/rules), so the code can be checked
directly against the assignment.
"""

import re

from .entities import ModDecision

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