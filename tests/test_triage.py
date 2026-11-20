from datetime import date

import pytest

from triage.cli import main
from triage.engine import Ticket, load_tickets, pick_trade, triage_all, triage_ticket

TODAY = date(2026, 11, 19)


def run(desc, loc="", opened=None):
    return triage_ticket(Ticket("x", desc, loc, opened), TODAY)


def test_safety_hazard_is_p1():
    assert run("Sparks coming from outlet").priority == 1


def test_service_loss_is_p2():
    assert run("No hot water in room 3").priority == 2


def test_default_is_routine():
    assert run("Replace light bulb").priority == 3


def test_cosmetic_is_low():
    assert run("Scuff marks on wall").priority == 4


def test_critical_location_bumps_one_level():
    assert run("Light bulb out", "server room").priority == 2


def test_age_bumps_one_level():
    assert run("Light bulb out", opened=date(2026, 11, 1)).priority == 2


def test_recent_ticket_not_bumped():
    assert run("Light bulb out", opened=date(2026, 11, 18)).priority == 3


def test_p1_never_goes_below_one():
    assert run("Fire in the lab", "lab", date(2026, 1, 1)).priority == 1


def test_bumps_stack():
    assert run("Leak in ceiling", "clinic", date(2026, 11, 1)).priority == 1


def test_trade_pick_and_general():
    assert pick_trade("elevator stuck") == "Elevator"
    assert pick_trade("something odd") == "General"


def test_whole_word_keyword():
    # "fire" must not match inside "fireplace"
    assert run("Fireplace screen is dusty").priority == 3


def test_sorted_most_urgent_first():
    out = triage_all([Ticket("a", "light bulb out"), Ticket("b", "gas leak")], TODAY)
    assert [r.ticket.id for r in out] == ["b", "a"]


def test_sla_hours():
    assert run("Sparks").sla_hours == 2


def test_load_missing_column(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("id,text\n1,x\n")
    with pytest.raises(ValueError, match="description"):
        load_tickets(str(p))


def test_load_bad_date(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("id,description,opened\n1,x,11/18\n")
    with pytest.raises(ValueError, match="line 2"):
        load_tickets(str(p))


def test_cli_run_and_filter(capsys):
    assert main(["run", "examples/tickets.csv", "--today", "2026-11-19", "--min-priority", "1"]) == 0
    out = capsys.readouterr().out
    assert "T001" in out and "T007" not in out


def test_cli_missing_file(capsys):
    assert main(["run", "nope.csv"]) == 1


def test_age_never_makes_emergency():
    assert run("Thermostat not working", opened=date(2026, 11, 1)).priority == 2
