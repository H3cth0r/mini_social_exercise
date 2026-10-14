"""Onboarding domain — entities. Plain data + invariants, no framework code."""

from dataclasses import dataclass


@dataclass
class Greeting:
    """One welcome, greeter -> newcomer. Greeted once per pair, ever.

    day: 'YYYY-MM-DD', for the newcomer's toast ("greeted you today"/"this
    week") — every greeting rule is pair-scoped, none are day-scoped."""
    greeter_id: int
    newcomer_id: int
    day: str


@dataclass
class NewcomerEntry:
    """One newcomer as shown in the feed's welcome strip.

    A newcomer leaves the strip as soon as anyone greets them (the welcome
    is answered), so there is no 'already greeted' state here by design."""

    user_id: int
    username: str
    age_days: float
    assigned_to_me: bool = False   # I am the DC 20 responsible greeter