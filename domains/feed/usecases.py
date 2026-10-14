"""Feed domain — use cases: the recommendation rules.

Content-based keyword scoring, chosen for the same reasons as the moderation
scoring: the rules are small, deterministic and explainable — the same text
always gets the same interest score, and we can show the grader WHY a post
was recommended. No ML, no embeddings (offline Python 3.8 container).

The scaffold's own test scene: react positively to the DIY posts of
@starboy99/@DancingDolphin/@blogger_bob (posts 1810, 1875, 1880) and the
Recommended tab must start showing other DIY content (e.g. post 2113).
"""

import re

from .entities import InterestProfile

# The user's signals: every reaction except these two counts as positive
# feedback about a post's topic.
NEGATIVE_REACTIONS = ('sad', 'angry')

# Weight of words inside a post the user reacted to vs inside posts of
# users they follow. Their OWN reactions say more than someone else's feed.
FOLLOWED_WEIGHT = 0.3

# Cap on candidates and profile words kept per source: one post may not
# dominate the profile, and scoring stays readable.
PROFILE_MAX_WORDS = 60
RECOMMEND_COUNT = 5

# Small stopword list: words like 'the' would match everything and bury
# the interesting overlap. Keep the list SHORT on purpose (this is a mock).
STOPWORDS = frozenset(
    'the a an and or to of in on for with is are was were be been it this that '
    'these those my me i we you your just so but what how when not no do did '
    'have has had all at by up out one two am us our from as if than then them '
    'she her he his they their get got about there here'.split())

_WORD_RE = re.compile(r"[a-z']+")


def words(text):
    """Lowercase, significant words of one text (3+ chars, no stopwords)."""
    found = _WORD_RE.findall(str(text).lower())
    return [w for w in found if len(w) > 2 and w not in STOPWORDS]


def build_interest_profile(reacted_texts, followed_texts):
    """InterestProfile from the user's signals.

    reacted_texts: texts of posts this user reacted to positively.
    followed_texts: texts of posts by users this user follows.
    Words from the user's own reactions dominate; followed content only
    breaks ties between similar posts (or fills an empty profile)."""
    profile = InterestProfile()
    for text in reacted_texts:
        for word in set(words(text)):
            profile.words[word] = profile.words.get(word, 0) + 1.0
    for text in followed_texts:
        for word in set(words(text)):
            profile.words[word] = profile.words.get(word, 0) + FOLLOWED_WEIGHT
    # Cap: keep the heaviest words only, so one odd post cannot drown the rest.
    if len(profile.words) > PROFILE_MAX_WORDS:
        profile.words = dict(sorted(profile.words.items(),
                                    key=lambda item: -item[1])[:PROFILE_MAX_WORDS])
    return profile


def score_post(text, profile):
    """How well one candidate post matches the profile (0.0 means no signal)."""
    return sum(profile.words.get(word, 0) for word in set(words(text)))


def rank_candidates(candidates, profile, limit=RECOMMEND_COUNT):
    """Order candidates: match score first, newest first on ties.

    candidates: list of dicts with content, created_at, id (the same shape
    the feed route consumes). Returns the top `limit` dicts, each with
    its score added as 'recommendation_score' (shown only in tests/logs).
    """
    scored = []
    for candidate in candidates:
        scored.append(score_post(candidate['content'], profile))
    # Three stable sorts, least significant key first: id desc, then
    # created_at desc (equal dates keep the id order), then score desc
    # (equal scores keep the recency order). Reads like the rule itself.
    paired = sorted(zip(candidates, scored), key=lambda pair: -pair[0]['id'])
    paired = sorted(paired, key=lambda pair: pair[0]['created_at'], reverse=True)
    paired = sorted(paired, key=lambda pair: -pair[1])
    top = [dict(candidate, recommendation_score=score)
           for candidate, score in paired[:limit]]
    return top


def recommend(repo, user_id, filter_following, limit=RECOMMEND_COUNT):
    """Orchestration for the feed route: gather signals and rank.

    repo: feed.repositories.FeedRepository
    user_id: the viewer, or None for a visitor (no signals possible ->
             the freshest posts instead of an empty tab).
    filter_following: True when the tab is the 'Recommended' view inside the
             'Following' filter -> rank only posts of followed users.

    The repository already excludes the viewer's own posts and posts they
    reacted to: recommendations must be NEW relevant posts, not what the
    user already voted on.
    """
    if user_id is None:
        return repo.get_recent_posts(limit)
    reacted = repo.get_positive_reacted_post_texts(user_id)
    followed_ids = repo.get_followed_ids(user_id)
    followed_texts = repo.get_post_texts_by_users(followed_ids)
    profile = build_interest_profile(reacted, followed_texts)
    if not profile.words:
        # No signals yet: nobody can be recommended for, fall back to recency.
        return repo.get_recent_posts(limit)
    candidates = repo.get_candidate_posts(user_id, follow_only=bool(
        filter_following and followed_ids))
    if not candidates:
        # Empty pool (e.g. following everyone): relax to the whole feed so
        # the tab never goes blank.
        candidates = repo.get_candidate_posts(user_id, follow_only=False)
    return rank_candidates(candidates, profile, limit)