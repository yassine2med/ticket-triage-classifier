"""Command line entry: python -m triage ..."""
from __future__ import annotations

import argparse
import sys
from datetime import date

from .engine import Ticket, load_tickets, triage_all, triage_ticket


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    parser = argparse.ArgumentParser(prog="triage", description="Assign priority and trade to tickets")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="triage every ticket in a CSV")
    run.add_argument("csv", help="columns: id, description, location (optional), opened (optional)")
    run.add_argument("--today", help="date used for ticket age, YYYY-MM-DD (default: today)")
    run.add_argument("--min-priority", type=int, choices=[1, 2, 3, 4], default=4,
                     help="hide tickets less urgent than this level")
    one = sub.add_parser("explain", help="triage one description and show the reasons")
    one.add_argument("description")
    one.add_argument("--location", default="")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "explain":
            res = triage_ticket(Ticket("-", args.description, args.location), date.today())
            print(f"{res.label} | {res.trade} | respond within {res.sla_hours}h")
            print("Why: " + "; ".join(res.reasons))
            return 0
        today = date.fromisoformat(args.today) if args.today else date.today()
        results = [r for r in triage_all(load_tickets(args.csv), today) if r.priority <= args.min_priority]
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"{'ID':<7}{'Priority':<14}{'Trade':<17}{'SLA':<6}Why")
    for r in results:
        print(f"{r.ticket.id:<7}{r.label:<14}{r.trade:<17}{str(r.sla_hours) + 'h':<6}{'; '.join(r.reasons)}")
    counts = {p: sum(1 for r in results if r.priority == p) for p in (1, 2, 3, 4)}
    print("\n" + ", ".join(f"P{p}: {n}" for p, n in counts.items()))
    return 0
