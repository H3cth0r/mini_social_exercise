"""Feed domain — entities. Plain data + invariants, no framework code."""

from dataclasses import dataclass, field


@dataclass
class InterestProfile:
    """The words a user cares about, with a weight each.

    Built from their positive reactions (weight 1.0) and from posts of the
    users they follow (weight 0.3). Scoring a candidate post is just: sum
    the weights of the profile words the post contains.
    """

    words: dict = field(default_factory=dict)


@dataclass
class PostScore:
    """One ranked candidate: a post and how well it matches the profile."""

    post_id: int
    score: float