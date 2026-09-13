"""RATION — the budgets a specification sets, enforced before they are spent.

horizon.py counts effects: files written, commands run. Those are the units
of what the agent DOES. They are not the units anyone actually runs out of.
What runs out is money, context, and time, and none of the three is visible
to a rule about files:

    "a turn costs at most $2"
    "a session costs at most $25"
    "no single model call sends more than 120k tokens"
    "a turn takes at most 10 minutes of wall clock"

These are the constraints an operator cares about most and the ones a
boundary usually cannot express at all, so they end up as a monitor that
notices overspend after it has happened. Noticing is not enforcing. Money
spent is spent; a 200k-token request that was going to be rejected by the
provider is rejected whether or not a dashboard recorded it.

So a ration is checked on the PROJECTION, like a horizon: the cost of the
call about to be made is added to what the window has already spent, and
the call is refused if the total would cross the line. The budget is
therefore never exceeded rather than reported as exceeded.

    §30 A turn costs at most two dollars.
    @ration per turn max cost_usd 2.00

    §31 No single request sends more than 120k tokens.
    @ration per call max tokens_in 120000

    §32 A turn takes at most ten minutes.
    @ration per turn max seconds 600

Three windows, because the three run out differently:

    call      one model request — the only place a hard provider limit bites
    turn      one instruction from the user
    session   the whole run

Spend is folded from sealed events, so it survives a restart and cannot
drift from what was actually billed. A ration and a horizon are deliberately
separate: one is about the size of the work, the other about what the work
consumes, and collapsing them would make it impossible to say "any number
of files, but only two dollars".
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

from .kernel import EventLog

CALL = "call"
TURN = "turn"
SESSION = "session"
_WINDOWS = (CALL, TURN, SESSION)

_MEASURES = ("cost_usd", "tokens_in", "tokens_out", "tokens_total",
             "seconds", "calls")

_RATION_RE = re.compile(
    r"^\s*@ration\s+per\s+(?P<window>call|turn|session)\s+max\s+"
    r"(?P<measure>\w+)\s+(?P<limit>[0-9]+(?:\.[0-9]+)?)\s*$", re.I)


@dataclass(frozen=True)
class Limit:
    clause: str
    window: str
    measure: str
    limit: float

    def to_dict(self) -> dict:
        return {"clause": self.clause, "window": self.window,
                "measure": self.measure, "limit": self.limit}


@dataclass(frozen=True)
class Overspend:
    clause: str
    window: str
    measure: str
    limit: float
    spent: float
    projected: float

    def to_dict(self) -> dict:
        return {"clause": self.clause, "window": self.window,
                "measure": self.measure, "limit": self.limit,
                "spent": round(self.spent, 6),
                "projected": round(self.projected, 6)}

    def describe(self) -> str:
        fmt = (lambda v: f"${v:,.2f}") if self.measure == "cost_usd" else (
            lambda v: f"{v:,.0f}")
        return (f"{self.clause}: {self.measure} per {self.window} is capped "
                f"at {fmt(self.limit)}; this call would reach "
                f"{fmt(self.projected)} (spent {fmt(self.spent)})")


def parse_limits(spec: str) -> tuple[list[Limit], list[str]]:
    limits: list[Limit] = []
    errors: list[str] = []
    clause = "preamble"
    for line in (spec or "").splitlines():
        head = re.match(r"^\s{0,3}§\s*([\d.]+[a-z]?)", line)
        if head:
            clause = head.group(1)
            continue
        tag = re.match(r"^\s{0,3}\[([A-Za-z0-9_.\-]+)\]", line)
        if tag:
            clause = tag.group(1)
            continue
        if not re.match(r"^\s*@ration\b", line, re.I):
            continue
        m = _RATION_RE.match(line)
        if not m:
            errors.append(f"{clause}: malformed @ration — expected "
                          f"'@ration per turn max cost_usd 2.00'")
            continue
        measure = m.group("measure").lower()
        if measure not in _MEASURES:
            errors.append(f"{clause}: unknown measure {measure!r} — known: "
                          f"{', '.join(_MEASURES)}")
            continue
        value = float(m.group("limit"))
        if value <= 0:
            errors.append(f"{clause}: a limit of {value} forbids all work")
            continue
        limits.append(Limit(clause, m.group("window").lower(), measure,
                            value))
    return limits, errors


@dataclass
class Estimate:
    """What a call is expected to consume, before it is made."""
    cost_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    seconds: float = 0.0

    def as_measures(self) -> dict[str, float]:
        return {"cost_usd": self.cost_usd,
                "tokens_in": float(self.tokens_in),
                "tokens_out": float(self.tokens_out),
                "tokens_total": float(self.tokens_in + self.tokens_out),
                "seconds": self.seconds,
                "calls": 1.0}


class Ration:
    """Budgets, folded from sealed spend and enforced on the projection."""

    def __init__(self, log: EventLog, spec: str = "") -> None:
        self.log = log
        self.limits: list[Limit] = []
        self.errors: list[str] = []
        self.blocked = 0
        self._turn_started = time.time()
        self._session_started = time.time()
        self.bind(spec)

    def bind(self, spec: str) -> None:
        self.limits, self.errors = parse_limits(spec or "")

    # -- windows ------------------------------------------------------------

    def open_turn(self) -> None:
        self._turn_started = time.time()
        self.log.append("ration.turn", {}, actor="kernel")

    def totals(self, window: str) -> dict[str, float]:
        """Spend so far in this window, folded from the log."""
        totals = {k: 0.0 for k in _MEASURES}
        if window == CALL:
            return totals          # a call window starts empty every time
        for ev in self.log.events():
            if ev.type == "ration.turn" and window == TURN:
                totals = {k: 0.0 for k in _MEASURES}
            elif ev.type == "ration.spent":
                for k in _MEASURES:
                    if k in ev.data:
                        totals[k] += float(ev.data.get(k) or 0)
                totals["calls"] += 1
        # elapsed time is read from the clock, not accumulated per call:
        # a turn that sat waiting has still used its ten minutes
        now = time.time()
        if window == TURN:
            totals["seconds"] = now - self._turn_started
        elif window == SESSION:
            totals["seconds"] = now - self._session_started
        return totals

    def spend(self, cost_usd: float = 0.0, tokens_in: int = 0,
              tokens_out: int = 0, seconds: float = 0.0) -> None:
        """Seal what a completed call actually consumed."""
        self.log.append("ration.spent",
                        {"cost_usd": float(cost_usd),
                         "tokens_in": int(tokens_in),
                         "tokens_out": int(tokens_out),
                         "tokens_total": int(tokens_in) + int(tokens_out),
                         "seconds": float(seconds)},
                        actor="kernel")

    # -- the boundary -------------------------------------------------------

    def project(self, estimate: Estimate) -> list[Overspend]:
        if not self.limits:
            return []
        want = estimate.as_measures()
        cache: dict[str, dict[str, float]] = {}
        out: list[Overspend] = []
        for lim in self.limits:
            if lim.window not in cache:
                cache[lim.window] = self.totals(lim.window)
            spent = cache[lim.window][lim.measure]
            projected = spent + want.get(lim.measure, 0.0)
            if projected > lim.limit:
                out.append(Overspend(lim.clause, lim.window, lim.measure,
                                     lim.limit, spent, projected))
        return out

    def gate(self, estimate: Estimate) -> str | None:
        """Block reason, or None. Refused on the projection, so a budget is
        never exceeded rather than reported as exceeded."""
        over = self.project(estimate)
        if not over:
            return None
        self.blocked += 1
        self.log.append("ration.blocked",
                        {"overspend": [o.to_dict() for o in over]},
                        actor="kernel")
        lines = [f"RationExceeded: this call would cross {len(over)} budget"
                 f"{'s' if len(over) > 1 else ''} in the specification."]
        for o in over:
            lines.append(f"  {o.describe()}")
        return "\n".join(lines)

    def report(self) -> str:
        if not self.limits:
            return "ration: no @ration budgets in the specification"
        lines = [f"ration: {len(self.limits)} budget(s) · {self.blocked} "
                 f"call(s) refused"]
        cache: dict[str, dict[str, float]] = {}
        for lim in self.limits:
            if lim.window not in cache:
                cache[lim.window] = self.totals(lim.window)
            now = cache[lim.window][lim.measure]
            pct = int(100 * now / lim.limit) if lim.limit else 0
            bar = "●" if now >= lim.limit else "○"
            unit = "$" if lim.measure == "cost_usd" else ""
            lines.append(f"  {bar} {lim.clause:<8} {lim.measure:<13} "
                         f"{unit}{now:,.2f}/{unit}{lim.limit:,.2f} "
                         f"({pct}%) per {lim.window}")
        for e in self.errors:
            lines.append(f"  !! {e}")
        return "\n".join(lines)


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        log = EventLog(Path(td) / "log.jsonl")
        spec = '''§30 A turn costs at most two dollars
@ration per turn max cost_usd 2.00

§31 No single request sends more than 120k tokens
@ration per call max tokens_in 120000

§32 A session costs at most twenty-five dollars
@ration per session max cost_usd 25.00
'''
        r = Ration(log, spec)
        assert len(r.limits) == 3 and not r.errors

        # -- a per-call limit bites on the call itself ---------------------
        assert r.gate(Estimate(tokens_in=100_000)) is None
        big = r.gate(Estimate(tokens_in=150_000))
        assert big and "31" in big, big
        assert "would reach 150,000" in big

        # -- a turn budget accumulates -------------------------------------
        r.open_turn()
        for _ in range(4):
            assert r.gate(Estimate(cost_usd=0.40)) is None
            r.spend(cost_usd=0.40, tokens_in=1000, tokens_out=500)
        # 1.60 spent; the next 0.40 reaches exactly 2.00 and is allowed
        assert r.gate(Estimate(cost_usd=0.40)) is None
        r.spend(cost_usd=0.40)
        # now at 2.00 — anything further crosses
        over = r.gate(Estimate(cost_usd=0.01))
        assert over and "30" in over, over
        assert abs(r.totals(TURN)["cost_usd"] - 2.0) < 1e-9

        # -- a new turn resets the turn window, not the session ------------
        r.open_turn()
        assert r.totals(TURN)["cost_usd"] == 0.0
        assert r.totals(SESSION)["cost_usd"] >= 2.0
        assert r.gate(Estimate(cost_usd=0.40)) is None

        # -- the session budget still holds --------------------------------
        r2 = Ration(EventLog(Path(td) / "l2.jsonl"),
                    "§32 session cap\n@ration per session max cost_usd 1.00\n")
        r2.open_turn()
        r2.spend(cost_usd=0.90)
        r2.open_turn()          # a new turn does not refill a session budget
        blocked = r2.gate(Estimate(cost_usd=0.20))
        assert blocked and "32" in blocked, blocked

        # -- spend is a fold: it survives a restart ------------------------
        reopened = Ration(EventLog(Path(td) / "l2.jsonl"),
                          "§32 session cap\n"
                          "@ration per session max cost_usd 1.00\n")
        assert reopened.totals(SESSION)["cost_usd"] == 0.90, \
            "session spend did not survive reload"

        # -- elapsed time is read from the clock ---------------------------
        rt = Ration(EventLog(Path(td) / "l3.jsonl"),
                    "§33 ten minutes\n@ration per turn max seconds 600\n")
        rt.open_turn()
        assert rt.gate(Estimate(seconds=1)) is None
        rt._turn_started = time.time() - 700      # the turn has run long
        late = rt.gate(Estimate(seconds=1))
        assert late and "33" in late, late

        # -- a call that alone exceeds a turn budget is refused whole ------
        r3 = Ration(EventLog(Path(td) / "l4.jsonl"),
                    "§30 two dollars\n@ration per turn max cost_usd 2.00\n")
        r3.open_turn()
        assert r3.gate(Estimate(cost_usd=5.00)), "a $5 call passed a $2 cap"

        # -- no budgets means no interference ------------------------------
        quiet = Ration(EventLog(Path(td) / "l5.jsonl"), "")
        assert quiet.gate(Estimate(cost_usd=1e6, tokens_in=10**9)) is None
        assert "no @ration budgets" in quiet.report()

        # -- refusals are sealed -------------------------------------------
        assert any(e.type == "ration.blocked" for e in log.events())

        # -- malformed budgets are reported, never guessed at --------------
        bad = Ration(log, "§34 x\n@ration per turn max\n"
                          "§35 y\n@ration per turn max sideways 4\n"
                          "§36 z\n@ration per fortnight max cost_usd 4\n"
                          "§37 w\n@ration per turn max cost_usd 0\n")
        assert len(bad.errors) == 4, bad.errors
        assert bad.limits == []

    print("RATION SELF-TEST PASS")
