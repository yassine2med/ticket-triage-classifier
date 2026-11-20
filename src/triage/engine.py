"""Rules that assign a priority, a response time and a trade to a service ticket."""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import date

PRIORITY_NAMES = {1: "P1 Emergency", 2: "P2 Urgent", 3: "P3 Routine", 4: "P4 Low"}
SLA_HOURS = {1: 2, 2: 24, 3: 72, 4: 240}

BASE_RULES: list[tuple[int, str, tuple[str, ...]]] = [
    (1, "safety hazard", ("fire", "smoke", "gas smell", "gas leak", "sparks", "flood",
                          "stuck between floors", "trapped", "sewage backup", "exposed wire")),
    (2, "service loss", ("no power", "no heat", "no hot water", "no water", "no air conditioning",
                         "not working", "broken lock", "will not lock", "leak", "overflowing",
                         "stuck", "out of service")),
    (4, "cosmetic", ("paint", "scuff", "nameplate", "cosmetic", "stain", "decor")),
]
CRITICAL_PLACES = ("server room", "data center", "lab", "clinic", "kitchen", "lobby", "main entrance")
AGE_BUMP_DAYS = 7

TRADES: dict[str, tuple[str, ...]] = {
    "HVAC": ("thermostat", "air conditioning", "heat", "hot", "cold", "vav", "chiller", "boiler"),
    "Plumbing": ("toilet", "sink", "leak", "drain", "water", "pipe", "faucet", "flood", "sewage"),
    "Electrical": ("power", "outlet", "light", "breaker", "sparks", "wire", "switch"),
    "Elevator": ("elevator", "escalator"),
    "Fire and Safety": ("fire", "smoke", "sprinkler", "extinguisher", "alarm"),
    "Carpentry": ("door", "lock", "ceiling tile", "drywall", "cabinet", "paint", "hinge"),
    "Custodial": ("spill", "trash", "cleaning", "stain", "odor"),
}


@dataclass
class Ticket:
    """One service ticket read from the CSV."""
    id: str
    description: str
    location: str = ""
    opened: date | None = None


@dataclass
class Triage:
    """Triage decision for one ticket."""
    ticket: Ticket
    priority: int
    trade: str
    reasons: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        """Human readable priority."""
        return PRIORITY_NAMES[self.priority]

    @property
    def sla_hours(self) -> int:
        """Target hours to first response."""
        return SLA_HOURS[self.priority]


def _has(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z]){re.escape(phrase)}(?![a-z])", text) is not None


def pick_trade(text: str) -> str:
    """Return the trade with the most keyword hits, or General."""
    best, best_hits = "General", 0
    for trade, words in TRADES.items():
        hits = sum(1 for word in words if _has(text, word))
        if hits > best_hits:
            best, best_hits = trade, hits
    return best


def triage_ticket(ticket: Ticket, today: date) -> Triage:
    """Apply the rules: base priority, then location and age bumps (each moves one level up; age never makes P1)."""
    text = " ".join((ticket.description + " " + ticket.location).lower().split())
    priority, reasons = 3, ["default routine"]
    for level, why, words in BASE_RULES:  # rules are ordered, the first hit wins
        hit = next((w for w in words if _has(text, w)), None)
        if hit:
            priority, reasons = level, [f"{why}: '{hit}'"]
            break
    if priority > 1 and any(_has(text, place) for place in CRITICAL_PLACES):
        priority -= 1
        reasons.append("critical location")
    if priority > 2 and ticket.opened and (today - ticket.opened).days >= AGE_BUMP_DAYS:
        priority -= 1
        reasons.append(f"open {(today - ticket.opened).days} days")
    return Triage(ticket, priority, pick_trade(text), reasons)


def load_tickets(path: str) -> list[Ticket]:
    """Read tickets from a CSV with id and description (location and opened are optional)."""
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = {"id", "description"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"missing column(s): {', '.join(sorted(missing))}")
        tickets = []
        for number, row in enumerate(reader, start=2):
            opened = None
            if row.get("opened"):
                try:
                    opened = date.fromisoformat(row["opened"].strip())
                except ValueError:
                    raise ValueError(f"line {number}: opened must be YYYY-MM-DD, got {row['opened']!r}") from None
            tickets.append(Ticket(row["id"].strip(), row["description"].strip(),
                                  (row.get("location") or "").strip(), opened))
    return tickets


def triage_all(tickets: list[Ticket], today: date) -> list[Triage]:
    """Triage every ticket, most urgent first (ties keep input order)."""
    return sorted((triage_ticket(t, today) for t in tickets), key=lambda r: r.priority)
