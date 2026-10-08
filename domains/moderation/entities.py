"""
Moderation domain — entities. Plain data + invariants, no framework code.
"""

from dataclasses import dataclass


@dataclass
class ModDecision:
    """Outcome of moderating one piece of content."""
    filtered_content: str   # text as it may be shown to users
    score: float            # severity score (0.0 clean ... 5.0 severe)


# Standing actions, mirroring the DC 31 ladder steps.
ACTION_ACCEPT = 'accept'      # post/comment goes through as normal
ACTION_WARN = 'warn'          # face-saving reminder, content still goes through
ACTION_THROTTLE = 'throttle'  # rejected for now; retry after the cooldown


@dataclass
class Standing:
    """The ladder's response to one content attempt by one user."""
    action: str             # one of the ACTION_* constants
    message: str = None     # flash copy for warn/throttle; None means silent
    wait_minutes: float = None  # only for throttle: minutes left in cooldown