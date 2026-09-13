"""REPLAY — re-deriving the decisions, to prove they were the right ones.

witness.py proves the enforcement RECORD is complete and unedited. That is
a real property and it is not the one an operator actually wants, because a
chain records what was decided, not whether the decision was correct. Both
of these produce a perfect, intact, gap-free chain:

    a boundary that judged every call correctly
    a boundary whose rules were wrong, or were not the rules you think

The chain cannot tell them apart. It commits to "write_file was refused by
clause 1" — never to the fact that clause 1, applied to those arguments,
actually refuses. A guard with an inverted comparison, a specification
quietly different from the one you read, a subsystem that returned early on
an exception: each produces decisions that chain perfectly and are wrong.

So replay closes the last gap by RE-DERIVING. Every tool call in the log is
judged again, now, from a specification you supply, and the fresh verdict
is compared to the one that was recorded:

    AGREED       re-judging produces the recorded verdict
    DIVERGED     it does not — the rules today would decide differently
    UNWITNESSED  the call has no decision at all: enforcement did not run

DIVERGED is the interesting one, and it is deliberately not called
"wrong" — it has two causes and replay cannot distinguish them from the log
alone:

    the rules CHANGED since the call (expected, and often fine)
    the rules did NOT change, and the decision does not follow from them

Which it is depends on whether the specification is the same one, and
integrity.py answers that. Replay reports the divergence and the clause;
naming a cause it cannot establish would be the same overreach this package
refuses everywhere else.

The point of all this: enforcement stops being something you trust because
the code looks right. Hand someone the log and the specification, and they
can derive every decision themselves, on their own machine, with no access
to the process that made them — and get the same answers or find out
exactly where they do not.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .covenant import Covenant
from .egress import Perimeter
from .horizon import Horizon
from .kernel import EventLog
from .provenance import Lineage
from .sequence import Timeline
from .witness import ALLOWED, REFUSED, Witness

AGREED = "agreed"
DIVERGED = "diverged"
UNWITNESSED = "unwitnessed"


@dataclass(frozen=True)
class Row:
    """One replayed call."""
    seq: int
    tool: str
    state: str
    recorded: str = ""
    rederived: str = ""
    clauses: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {"seq": self.seq, "tool": self.tool, "state": self.state,
                "recorded": self.recorded, "rederived": self.rederived,
                "clauses": list(self.clauses)}

    def describe(self) -> str:
        if self.state == UNWITNESSED:
            return (f"seq {self.seq} {self.tool}: no decision was recorded "
                    f"— enforcement did not run for this call")
        return (f"seq {self.seq} {self.tool}: recorded {self.recorded}, "
                f"re-deriving gives {self.rederived}"
                + (f" ({', '.join(self.clauses)})" if self.clauses else ""))


@dataclass
class Result:
    rows: list[Row] = field(default_factory=list)
    agreed: int = 0
    diverged: int = 0
    unwitnessed: int = 0
    chain_intact: bool = True

    @property
    def ok(self) -> bool:
        return (self.chain_intact and not self.diverged
                and not self.unwitnessed)

    def problems(self) -> list[Row]:
        return [r for r in self.rows if r.state != AGREED]

    def describe(self) -> str:
        if not self.rows:
            return "replay: no gated calls in this log"
        head = (f"replay: {len(self.rows)} call(s) re-derived · "
                f"{self.agreed} agreed · {self.diverged} diverged · "
                f"{self.unwitnessed} unwitnessed")
        if not self.chain_intact:
            head += "\n  !! the witness chain itself is broken — the record " \
                    "was edited, so agreement below proves nothing"
        if self.ok:
            return head + "\n  every recorded decision follows from these " \
                          "rules"
        lines = [head]
        for r in self.problems()[:20]:
            lines.append(f"  !! {r.describe()}")
        if len(self.problems()) > 20:
            lines.append(f"  … and {len(self.problems()) - 20} more")
        if self.diverged:
            lines.append("  a divergence means the rules today decide "
                         "differently — either they changed since, or the "
                         "decision did not follow from them. integrity.py "
                         "says which.")
        return "\n".join(lines)


def _gated_calls(log: EventLog) -> list[tuple[int, str, dict]]:
    out: list[tuple[int, str, dict]] = []
    for ev in log.events():
        if ev.type != "tool.call":
            continue
        name = str(ev.data.get("name") or "")
        args = ev.data.get("args") or {}
        if name and isinstance(args, dict):
            out.append((ev.seq, name, args))
    return out


def replay(log: EventLog, spec: str, chain: list[dict] | None = None,
           ) -> Result:
    """Re-judge every gated call in `log` under `spec`.

    Deliberately rebuilds the subsystems from scratch rather than reusing a
    live Charter: reusing the object that made the decisions would be the
    same process vouching for itself, which is what this module exists to
    avoid.
    """
    res = Result()

    decisions = chain
    if decisions is None:
        decisions = [ev.data for ev in log.events()
                     if ev.type == "witness.decision"]
    res.chain_intact = Witness.check(decisions).intact if decisions else True

    # recorded verdicts, in order, by tool
    pending: dict[str, list[dict]] = {}
    for d in decisions:
        pending.setdefault(str(d.get("tool", "")), []).append(d)

    # a fresh boundary, built only from the specification
    cov = Covenant(log, spec)
    seq = Timeline(log, spec)
    lin = Lineage(log, spec)
    per = Perimeter(log, spec)
    hor = Horizon(log, spec)

    for s, tool, args in _gated_calls(log):
        recorded = pending.get(tool)
        if not recorded:
            res.rows.append(Row(s, tool, UNWITNESSED))
            res.unwitnessed += 1
            continue
        d = recorded.pop(0)

        clauses: list[str] = []
        for found in (seq.check(tool, args), cov.check(tool, args),
                      lin.check(tool, args), per.check(tool, args),
                      hor.project(tool, args)):
            if found:
                clauses = [str(getattr(v, "clause", "?")) for v in found]
                break
        rederived = REFUSED if clauses else ALLOWED
        was = str(d.get("verdict", ""))

        if rederived == was:
            res.rows.append(Row(s, tool, AGREED, was, rederived,
                                tuple(clauses)))
            res.agreed += 1
        else:
            res.rows.append(Row(s, tool, DIVERGED, was, rederived,
                                tuple(clauses)))
            res.diverged += 1

    return res


def independent(decisions: list[dict], calls: list[tuple[int, str, dict]],
                spec: str) -> Result:
    """Verify with no EventLog at all — decisions, calls and a spec.

    This is the form you hand to someone who does not trust the process
    that produced the record: three plain values, and a verdict they can
    compute themselves.
    """
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        scratch = EventLog(Path(td) / "scratch.jsonl")
        for s, tool, args in calls:
            scratch.append("tool.call", {"name": tool, "args": args})
        return replay(scratch, spec, chain=decisions)


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    from .charter import Charter

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        spec = '''§1 Writes stay under src/ and tests/
@enforce confine_paths: src, tests

§2 Nothing is ever deleted
@enforce forbid_effect: delete
'''
        log = EventLog(root / "log.jsonl")
        ch = Charter(log, spec)
        ch.open_turn()

        calls = [
            ("write_file", {"path": "src/a.py", "content": "x = 1"}),
            ("write_file", {"path": "/etc/passwd", "content": "root"}),
            ("run_command", {"command": "pytest -q"}),
            ("delete_path", {"path": "src/a.py"}),
            ("run_command", {"command": "echo x > /etc/y"}),
        ]
        for tool, args in calls:
            log.append("tool.call", {"name": tool, "args": args})
            ch.gate(tool, args)

        # -- a faithful record re-derives to itself ------------------------
        r = replay(log, spec)
        assert r.ok, r.describe()
        assert r.agreed == len(calls) and r.diverged == 0
        assert "every recorded decision follows" in r.describe()

        # -- a DIFFERENT specification diverges ----------------------------
        loose = "§1 nothing is forbidden here\n"
        r2 = replay(log, loose)
        assert not r2.ok and r2.diverged == 3, r2.describe()
        assert all(row.recorded == REFUSED and row.rederived == ALLOWED
                   for row in r2.problems())
        assert "rules today decide differently" in r2.describe()

        # a stricter spec diverges the other way
        strict = "§9 nothing may be written at all\n@enforce forbid_effect: write\n"
        r3 = replay(log, strict)
        assert r3.diverged and any(row.recorded == ALLOWED and
                                   row.rederived == REFUSED
                                   for row in r3.problems())

        # -- a call nobody judged is found ---------------------------------
        log2 = EventLog(root / "log2.jsonl")
        ch2 = Charter(log2, spec)
        log2.append("tool.call", {"name": "write_file",
                                  "args": {"path": "src/a.py",
                                           "content": "x"}})
        ch2.gate("write_file", {"path": "src/a.py", "content": "x"})
        # this one bypassed the gate entirely
        log2.append("tool.call", {"name": "delete_path",
                                  "args": {"path": "src/a.py"}})
        r4 = replay(log2, spec)
        assert r4.unwitnessed == 1 and not r4.ok, r4.describe()
        assert "enforcement did not run" in r4.describe()

        # -- a broken chain invalidates agreement --------------------------
        decisions = ch.witness.export()
        tampered = [dict(d) for d in decisions]
        tampered[1]["verdict"] = ALLOWED
        r5 = replay(log, spec, chain=tampered)
        assert not r5.chain_intact and not r5.ok
        assert "proves nothing" in r5.describe()

        # -- verification with no access to the process --------------------
        plain_calls = [(i, t, a) for i, (t, a) in enumerate(calls)]
        r6 = independent(decisions, plain_calls, spec)
        assert r6.ok, r6.describe()
        # and it catches the wrong spec just the same
        assert not independent(decisions, plain_calls, loose).ok

        # -- an empty log is honest about being empty ----------------------
        empty = replay(EventLog(root / "empty.jsonl"), spec)
        assert "no gated calls" in empty.describe()

    print("REPLAY SELF-TEST PASS")
