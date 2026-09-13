"""HORIZON — the clauses no single action can break.

Every guard so far judges one call in isolation. That is the right unit for
"never write outside src/", because each write either lands inside or does
not. It is the wrong unit — structurally, not by oversight — for a whole
class of real constraints:

    "a change touches at most 20 files"
    "no more than 400 lines are rewritten without review"
    "delete at most 5 files in a session"
    "run at most 3 destructive commands per turn"

None of these can be violated by one action. Each individual step is
perfectly legal and would be waved through by any per-call check; the
breach exists only in the SUM. A boundary that only ever sees one call at a
time cannot see it at all, and an agent hitting such a limit does not do so
by making one bad decision — it does so by making forty reasonable ones.

So a horizon clause is evaluated against an accumulating window:

    §12 A change touches at most 20 files.
    @horizon per turn max files_written 20

    §13 No session deletes more than five files.
    @horizon per session max files_deleted 5

The window is the unit the limit is about: `turn` resets when the agent
takes a new instruction, `session` never resets. Counters are folded from
the sealed effects, not tallied in a variable, so they survive a restart
and cannot drift from what actually happened.

What makes this enforceable rather than merely observable is WHERE it is
checked: the projected total. Before a call runs, its effects are added to
the window's current total, and the call is refused if that projection
crosses the limit. The limit is therefore never exceeded — not detected
after the fact, when twenty-one files are already written and the clause is
already broken.

Measures available: files_written, files_deleted, lines_written,
commands_run, opaque_commands, bytes_written.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .effects import DELETE, EXEC, OPAQUE, WRITE, derive
from .kernel import EventLog

TURN = "turn"
SESSION = "session"

_MEASURES = ("files_written", "files_deleted", "lines_written",
             "commands_run", "opaque_commands", "bytes_written")

_HORIZON_RE = re.compile(
    r"^\s*@horizon\s+per\s+(?P<window>turn|session)\s+max\s+"
    r"(?P<measure>\w+)\s+(?P<limit>\d+)\s*$", re.I)


@dataclass(frozen=True)
class Limit:
    clause: str
    window: str
    measure: str
    limit: int

    def to_dict(self) -> dict:
        return {"clause": self.clause, "window": self.window,
                "measure": self.measure, "limit": self.limit}


@dataclass(frozen=True)
class Breach:
    clause: str
    measure: str
    window: str
    limit: int
    projected: int
    current: int

    def to_dict(self) -> dict:
        return {"clause": self.clause, "measure": self.measure,
                "window": self.window, "limit": self.limit,
                "projected": self.projected, "current": self.current}

    def describe(self) -> str:
        return (f"{self.clause}: {self.measure} per {self.window} is capped "
                f"at {self.limit}; this call would reach {self.projected} "
                f"(currently {self.current})")


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
        if not re.match(r"^\s*@horizon\b", line, re.I):
            continue
        m = _HORIZON_RE.match(line)
        if not m:
            errors.append(f"{clause}: malformed @horizon — expected "
                          f"'@horizon per turn max files_written 20'")
            continue
        measure = m.group("measure").lower()
        if measure not in _MEASURES:
            errors.append(f"{clause}: unknown measure {measure!r} — known: "
                          f"{', '.join(_MEASURES)}")
            continue
        limits.append(Limit(clause=clause, window=m.group("window").lower(),
                            measure=measure, limit=int(m.group("limit"))))
    return limits, errors


def measure_call(tool: str, args: dict) -> dict[str, int]:
    """What one call contributes to each measure.

    Counted from effects, so a shell write weighs exactly what the same
    write through write_file weighs. Paths are counted once per call: a
    command that writes one file twice is one file.
    """
    effects = derive(tool, args)
    written = {e.path for e in effects if e.kind == WRITE and e.path}
    deleted = {e.path for e in effects if e.kind == DELETE and e.path}
    content = [e.content for e in effects if e.kind == WRITE and e.content]
    return {
        "files_written": len(written),
        "files_deleted": len(deleted),
        "lines_written": sum(c.count("\n") + 1 for c in content),
        "bytes_written": sum(len(c.encode("utf-8", "replace"))
                             for c in content),
        "commands_run": sum(1 for e in effects if e.kind == EXEC),
        "opaque_commands": sum(1 for e in effects if e.kind == OPAQUE),
    }


class Horizon:
    """Accumulating windows, and the projection that keeps them uncrossed."""

    def __init__(self, log: EventLog, spec: str = "") -> None:
        self.log = log
        self.limits: list[Limit] = []
        self.errors: list[str] = []
        self.blocked = 0
        self.bind(spec)

    def bind(self, spec: str) -> None:
        self.limits, self.errors = parse_limits(spec or "")

    # -- the fold -----------------------------------------------------------

    def totals(self, window: str) -> dict[str, int]:
        """Current totals, folded from the sealed record.

        A counter kept in memory would reset on restart and drift whenever
        an event was written that it did not see. Folding costs a pass over
        the log and is always exactly what happened.
        """
        totals = dict.fromkeys(_MEASURES, 0)
        for ev in self.log.events():
            if ev.type == "horizon.spent":
                if window == TURN and ev.data.get("turn_boundary"):
                    totals = dict.fromkeys(_MEASURES, 0)
                    continue
                for k in _MEASURES:
                    totals[k] += int(ev.data.get(k, 0) or 0)
            elif ev.type == "horizon.turn" and window == TURN:
                totals = dict.fromkeys(_MEASURES, 0)
        return totals

    def open_turn(self) -> None:
        """Start a new turn window. Sealed, so the reset is part of the
        record rather than an in-memory fact the log cannot show."""
        self.log.append("horizon.turn", {}, actor="kernel")

    def spend(self, tool: str, args: dict) -> dict[str, int]:
        """Seal what a completed call consumed."""
        spent = measure_call(tool, args)
        if any(spent.values()):
            self.log.append("horizon.spent", {**spent, "tool": tool},
                            actor="kernel")
        return spent

    # -- the boundary -------------------------------------------------------

    def project(self, tool: str, args: dict) -> list[Breach]:
        """Breaches this call WOULD cause if it ran."""
        if not self.limits:
            return []
        spent = measure_call(tool, args)
        cache: dict[str, dict[str, int]] = {}
        out: list[Breach] = []
        for lim in self.limits:
            if lim.window not in cache:
                cache[lim.window] = self.totals(lim.window)
            current = cache[lim.window][lim.measure]
            projected = current + spent.get(lim.measure, 0)
            if projected > lim.limit:
                out.append(Breach(clause=lim.clause, measure=lim.measure,
                                  window=lim.window, limit=lim.limit,
                                  projected=projected, current=current))
        return out

    def gate(self, tool: str, args: dict) -> str | None:
        """Block reason, or None. Refuses on the PROJECTED total, so the
        limit is never crossed rather than noticed once it has been."""
        breaches = self.project(tool, args)
        if not breaches:
            return None
        self.blocked += 1
        self.log.append("horizon.blocked",
                        {"tool": tool,
                         "breaches": [b.to_dict() for b in breaches]},
                        actor="kernel")
        lines = [f"HorizonExceeded: this call would cross "
                 f"{len(breaches)} limit"
                 f"{'s' if len(breaches) > 1 else ''} in the specification."]
        for b in breaches:
            lines.append(f"  {b.describe()}")
        return "\n".join(lines)

    def report(self) -> str:
        if not self.limits:
            return "horizon: no @horizon limits in the specification"
        lines = [f"horizon: {len(self.limits)} limit(s) · "
                 f"{self.blocked} call(s) refused"]
        cache: dict[str, dict[str, int]] = {}
        for lim in self.limits:
            if lim.window not in cache:
                cache[lim.window] = self.totals(lim.window)
            now = cache[lim.window][lim.measure]
            bar = "●" if now >= lim.limit else "○"
            lines.append(f"  {bar} {lim.clause:<8} {lim.measure:<16} "
                         f"{now}/{lim.limit} per {lim.window}")
        for e in self.errors:
            lines.append(f"  !! {e}")
        return "\n".join(lines)


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        log = EventLog(Path(td) / "log.jsonl")
        spec = '''§12 A change touches at most 3 files
@horizon per turn max files_written 3

§13 A session deletes at most 2 files
@horizon per session max files_deleted 2

§14 At most 1 unanalysable command per turn
@horizon per turn max opaque_commands 1
'''
        hz = Horizon(log, spec)
        assert len(hz.limits) == 3 and not hz.errors

        # -- measurement counts effects, not tools -------------------------
        m = measure_call("write_file", {"path": "a.py", "content": "x\ny\n"})
        assert m["files_written"] == 1 and m["lines_written"] == 3
        m = measure_call("run_command", {"command": "echo x > a.py"})
        assert m["files_written"] == 1, m
        m = measure_call("run_command", {"command": "touch a && touch b"})
        assert m["files_written"] == 2, m
        # a path written twice in one call is one file
        m = measure_call("run_command", {"command": "echo x > a; echo y > a"})
        assert m["files_written"] == 1, m

        # -- each step is legal; the sum is not ----------------------------
        hz.open_turn()
        for i in range(3):
            call = ("write_file", {"path": f"f{i}.py", "content": "x"})
            assert hz.gate(*call) is None, f"file {i} refused too early"
            hz.spend(*call)
        # the fourth is refused although it is identical to the first three
        blocked = hz.gate("write_file", {"path": "f3.py", "content": "x"})
        assert blocked and "12" in blocked, blocked
        assert "would reach 4" in blocked, blocked

        # and the limit was never actually crossed
        assert hz.totals(TURN)["files_written"] == 3

        # -- a new turn resets the turn window, not the session one --------
        hz.open_turn()
        assert hz.totals(TURN)["files_written"] == 0
        assert hz.gate("write_file", {"path": "f4.py", "content": "x"}) is None

        # -- session windows do not reset ----------------------------------
        hz.spend("delete_path", {"path": "a.py"})
        hz.spend("run_command", {"command": "rm b.py"})
        assert hz.totals(SESSION)["files_deleted"] == 2
        hz.open_turn()
        assert hz.totals(SESSION)["files_deleted"] == 2, "session reset"
        blocked = hz.gate("delete_path", {"path": "c.py"})
        assert blocked and "13" in blocked, blocked

        # -- one call that alone crosses a limit is refused whole ----------
        hz2 = Horizon(EventLog(Path(td) / "l2.jsonl"), spec)
        hz2.open_turn()
        bulk = ("run_command", {"command": "touch a && touch b && touch c "
                                           "&& touch d"})
        assert hz2.gate(*bulk), "a 4-file call passed a 3-file cap"

        # -- opaque commands are their own measure -------------------------
        hz3 = Horizon(EventLog(Path(td) / "l3.jsonl"), spec)
        hz3.open_turn()
        opaque = ("run_command", {"command": 'eval "$CMD"'})
        assert hz3.gate(*opaque) is None
        hz3.spend(*opaque)
        assert hz3.gate(*opaque), "a second opaque command passed a cap of 1"

        # -- totals are a fold: they survive a restart ---------------------
        reopened = Horizon(EventLog(Path(td) / "log.jsonl"), spec)
        assert reopened.totals(SESSION)["files_deleted"] == 2, \
            "session total did not survive reload"

        # -- no limits means no interference -------------------------------
        quiet = Horizon(EventLog(Path(td) / "l4.jsonl"), "")
        assert quiet.gate("run_command",
                          {"command": "rm -rf everything"}) is None
        assert "no @horizon limits" in quiet.report()

        # -- malformed limits are reported, never guessed at ---------------
        bad = Horizon(log, "§20 x\n@horizon per turn max\n"
                           "§21 y\n@horizon per turn max sideways 4\n"
                           "§22 z\n@horizon per fortnight max files_written 4\n")
        assert len(bad.errors) == 3, bad.errors
        assert bad.limits == []

    print("HORIZON SELF-TEST PASS")
