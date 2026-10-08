"""
Moderation domain — entities. Plain data + invariants, no framework code.
"""

from dataclasses import dataclass


@dataclass
class ModDecision:
    """Outcome of moderating one piece of content."""
    filtered_content: str   # text as it may be shown to users
    score: float            # severity score (0.0 clean ... 5.0 severe)