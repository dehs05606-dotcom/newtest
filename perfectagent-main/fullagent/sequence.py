"""SEQUENCE — the clauses about ORDER.

Every rule so far is timeless. A guard asks "is this act permitted?" and a
horizon asks "how many so far?", and neither can express the constraints
that are entirely about when something happens relative to something else:

    "read a file before rewriting it"
    "run the tests after touching src/, before declaring done"
    "a migration is written before the schema it migrates"
    "never push before the tests have passed on the current tree"

These are not permissions. Each act in them is individually allowed — it is
the ORDER that is wrong, and order is invisible to a per-call check. An
agent that rewrites a file it never read has broken a real clause without
performing a single forbidden act.

The event log is already a total order, so this is a fold over it rather
than new bookkeeping. Two shapes cover the useful cases:

    §20 A file is read before it is rewritten.
    @sequence before write src/** require read same

    §21 Touching src/ obliges a test run before done.
    @sequence after write src/** require run pytest

`before` is a PRECONDITION: checked on the pending call, refused if unmet,
so the out-of-order act does not happen. `after` is a POSTCONDITION: it
does not refuse anything — refusing the write would make the clause
impossible, since the write is what creates the requirement — it blocks
DONE until satisfied, exactly as an obligation does.

`require read same` is the special case worth naming: "same" binds the
requirement to the very path being written, so one clause covers every
file instead of needing one rule per path.

A satisfied precondition is not consumed: reading a file and then writing
it twice is fine. It is re-armed only when the path changes in a way the
agent did not author — a formatter, a build step, a redirect — because
then, and only then, is the picture it read no longer what is on disk. Its
own write_file carries content it supplied and cannot surprise it.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from pathlib import PurePath

from .effects import DELETE, WRITE, derive
from .kernel import EventLog

BEFORE = "before"
AFTER = "after"

_SEQ_RE = re.compile(
    r"^\s*@sequence\s+(?P<when>before|after)\s+(?P<act>write|delete)\s+"
    r"(?P<glob>\S+)\s+require\s+(?P<req>read|run)\s+(?P<target>.+?)\s*$",
    re.I)

# tools that count as having READ a path
_READ_TOOLS = frozenset({"read_file", "search_files", "file_info",
                         "list_dir", "glob_files"})

# tools where the agent supplied the content it wrote, so the result holds
# no surprises for it
_AUTHORED_TOOLS = frozenset({"write_file", "edit_file", "apply_patch",
                             "create_directory"})


def _norm(path: str) -> str:
    parts: list[str] = []
    for part in PurePath(path or "").parts:
        if part == "..":
            if parts:
                parts.pop()
        elif part != ".":
            parts.append(part)
    return "/".join(parts)


def _glob(path: str, pattern: str) -> bool:
    norm = _norm(path)
    if fnmatch.fnmatch(norm, pattern):
        return True
    if "**" in pattern:
        flat = pattern.replace("**/", "").replace("/**", "")
        if fnmatch.fnmatch(norm, flat):
            return True
        head = pattern.split("**")[0].rstrip("/")
        if head and norm.startswith(head + "/"):
            return True
    return False


@dataclass(frozen=True)
class Rule:
    clause: str
    when: str        # before | after
    act: str         # write | delete
    glob: str
    req: str         # read | run
    target: str      # a path glob, "same", or a command substring

    def to_dict(self) -> dict:
        return {"clause": self.clause, "when": self.when, "act": self.act,
                "glob": self.glob, "req": self.req, "target": self.target}

    def describe(self, path: str = "") -> str:
        target = path if self.target.lower() == "same" else self.target
        verb = "read" if self.req == "read" else "run"
        if self.when == BEFORE:
            return (f"{self.clause}: {target!r} must be {verb} before "
                    f"{self.act} to {path or self.glob!r}")
        return (f"{self.clause}: {self.act} to {path or self.glob!r} "
                f"requires {verb} {target!r} afterwards")


@dataclass(frozen=True)
class Unmet:
    clause: str
    detail: str

    def to_dict(self) -> dict:
        return {"clause": self.clause, "detail": self.detail}


def parse_rules(spec: str) -> tuple[list[Rule], list[str]]:
    rules: list[Rule] = []
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
        if not re.match(r"^\s*@sequence\b", line, re.I):
            continue
        m = _SEQ_RE.match(line)
        if not m:
            errors.append(
                f"{clause}: malformed @sequence — expected "
                f"'@sequence before write src/** require read same' or "
                f"'@sequence after write src/** require run pytest'")
            continue
        req = m.group("req").lower()
        target = m.group("target").strip()
        if req == "run" and target.lower() == "same":
            errors.append(f"{clause}: 'require run same' is meaningless — "
                          f"name the command")
            continue
        rules.append(Rule(clause, m.group("when").lower(),
                          m.group("act").lower(), m.group("glob"),
                          req, target))
    return rules, errors


class Timeline:
    """Order-sensitive clauses, folded from the event log."""

    def __init__(self, log: EventLog, spec: str = "") -> None:
        self.log = log
        self.rules: list[Rule] = []
        self.errors: list[str] = []
        self.blocked = 0
        self.bind(spec)

    def bind(self, spec: str) -> None:
        self.rules, self.errors = parse_rules(spec or "")

    # -- the fold -----------------------------------------------------------

    def _history(self) -> tuple[dict[str, int], list[tuple[int, str]],
                                dict[str, int], dict[str, int]]:
        """(reads, command runs, all writes, incidental writes) by seq.

        Writes are split by whether the agent AUTHORED the content. A
        write_file or a patch carries content the agent supplied, so it
        cannot be surprised by the result. A file changed as a side effect
        of a command — a formatter, a build step, a redirect — leaves the
        agent holding a stale picture of that path, which is the situation
        a "read before write" clause actually exists to prevent.

        Written as one pass: every question below is about the relative
        order of these, and separate folds could disagree if the log grew
        between them.
        """
        reads: dict[str, int] = {}
        runs: list[tuple[int, str]] = []
        writes: dict[str, int] = {}
        incidental: dict[str, int] = {}
        for ev in self.log.events():
            if ev.type != "tool.call":
                continue
            name = str(ev.data.get("name") or "")
            args = ev.data.get("args") or {}
            if not isinstance(args, dict):
                continue
            if name in _READ_TOOLS:
                p = str(args.get("path") or "")
                if p:
                    reads[_norm(p)] = ev.seq
            cmd = str(args.get("command") or "")
            if cmd:
                runs.append((ev.seq, cmd))
            authored = name in _AUTHORED_TOOLS
            for e in derive(name, args):
                if e.kind in (WRITE, DELETE) and e.path:
                    writes[_norm(e.path)] = ev.seq
                    if not authored:
                        incidental[_norm(e.path)] = ev.seq
        return reads, runs, writes, incidental

    # -- preconditions ------------------------------------------------------

    def check(self, tool: str, args: dict) -> list[Unmet]:
        """`before` rules this pending call would violate."""
        befores = [r for r in self.rules if r.when == BEFORE]
        if not befores:
            return []
        reads, runs, writes, incidental = self._history()
        out: list[Unmet] = []
        for e in derive(tool, args):
            if e.kind not in (WRITE, DELETE) or not e.path:
                continue
            act = "write" if e.kind == WRITE else "delete"
            path = _norm(e.path)
            for r in befores:
                if r.act != act or not _glob(path, r.glob):
                    continue
                if r.req == "read":
                    target = path if r.target.lower() == "same" else r.target
                    seq = reads.get(_norm(target))
                    if seq is None:
                        out.append(Unmet(r.clause, r.describe(path)))
                    elif incidental.get(_norm(target), -1) > seq:
                        # read, then changed by something the agent did not
                        # author — it no longer knows what it would overwrite
                        out.append(Unmet(
                            r.clause,
                            f"{r.clause}: {target!r} was read, then changed "
                            f"by a command afterwards — read it again "
                            f"before {act}"))
                else:
                    if not any(r.target in cmd for _, cmd in runs):
                        out.append(Unmet(r.clause, r.describe(path)))
        return out

    def gate(self, tool: str, args: dict) -> str | None:
        unmet = self.check(tool, args)
        if not unmet:
            return None
        self.blocked += 1
        self.log.append("sequence.blocked",
                        {"tool": tool, "unmet": [u.to_dict() for u in unmet]},
                        actor="kernel")
        lines = [f"OutOfOrder: {len(unmet)} clause"
                 f"{'s' if len(unmet) > 1 else ''} require something to "
                 f"happen before this call."]
        for u in unmet:
            lines.append(f"  {u.detail}")
        return "\n".join(lines)

    # -- postconditions -----------------------------------------------------

    def outstanding(self) -> list[Unmet]:
        """`after` rules triggered and not yet satisfied.

        Order matters: a test run BEFORE the write does not satisfy a rule
        that says the run must follow it, because it did not see the change.
        """
        afters = [r for r in self.rules if r.when == AFTER]
        if not afters:
            return []
        reads, runs, writes, _incidental = self._history()
        out: list[Unmet] = []
        for r in afters:
            triggered = [seq for path, seq in writes.items()
                         if _glob(path, r.glob)]
            if not triggered:
                continue
            last = max(triggered)
            if r.req == "run":
                if not any(seq > last and r.target in cmd
                           for seq, cmd in runs):
                    out.append(Unmet(
                        r.clause,
                        f"{r.clause}: {r.glob} changed, so {r.target!r} "
                        f"must run after that change and has not"))
            else:
                target = _norm(r.target)
                if reads.get(target, -1) <= last:
                    out.append(Unmet(r.clause, r.describe()))
        return out

    def blocker(self) -> str | None:
        """Why progress cannot be declared complete, or None."""
        unmet = self.outstanding()
        if not unmet:
            return None
        lines = [f"SequenceOutstanding: {len(unmet)} ordering requirement"
                 f"{'s' if len(unmet) > 1 else ''} are not met yet."]
        for u in unmet:
            lines.append(f"  {u.detail}")
        return "\n".join(lines)

    def report(self) -> str:
        if not self.rules:
            return "sequence: no @sequence rules in the specification"
        unmet = self.outstanding()
        lines = [f"sequence: {len(self.rules)} rule(s) · {self.blocked} "
                 f"refused · {len(unmet)} outstanding"]
        for r in self.rules:
            lines.append(f"  {r.clause:<10} {r.when:<7} {r.act} {r.glob} "
                         f"require {r.req} {r.target}")
        for u in unmet:
            lines.append(f"  ○ {u.detail}")
        for e in self.errors:
            lines.append(f"  !! {e}")
        return "\n".join(lines)


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        log = EventLog(Path(td) / "log.jsonl")
        spec = '''§20 A file is read before it is rewritten
@sequence before write src/** require read same

§21 Touching src/ obliges a test run before done
@sequence after write src/** require run pytest
'''
        tl = Timeline(log, spec)
        assert len(tl.rules) == 2 and not tl.errors

        # -- the precondition refuses a blind overwrite --------------------
        blind = ("write_file", {"path": "src/app.py", "content": "x = 1"})
        blocked = tl.gate(*blind)
        assert blocked and "20" in blocked, blocked
        assert "must be read before" in blocked

        # -- reading it first satisfies the rule ---------------------------
        log.append("tool.call", {"name": "read_file",
                                 "args": {"path": "src/app.py"}})
        assert tl.gate(*blind) is None

        # and the read is not consumed — twice is still fine
        log.append("tool.call", {"name": "write_file",
                                 "args": {"path": "src/app.py",
                                          "content": "x = 1"}})
        assert tl.gate(*blind) is None

        # -- a different file is still unread ------------------------------
        assert tl.gate("write_file", {"path": "src/other.py", "content": "y"})

        # -- "same" binds to the path actually being written --------------
        log.append("tool.call", {"name": "read_file",
                                 "args": {"path": "src/other.py"}})
        assert tl.gate("write_file", {"path": "src/other.py",
                                      "content": "y"}) is None

        # -- the shell route is judged identically -------------------------
        assert tl.gate("run_command", {"command": "echo x > src/third.py"})

        # -- the postcondition blocks DONE, not the write ------------------
        # src/ has been written; pytest has not run since
        blocker = tl.blocker()
        assert blocker and "21" in blocker, blocker
        assert "must run after that change" in blocker

        # a run BEFORE the change does not satisfy it — it never saw it
        early = EventLog(Path(td) / "early.jsonl")
        t2 = Timeline(early, spec)
        early.append("tool.call", {"name": "run_command",
                                   "args": {"command": "pytest -q"}})
        early.append("tool.call", {"name": "write_file",
                                   "args": {"path": "src/a.py",
                                            "content": "x"}})
        assert t2.blocker(), "a pre-change test run satisfied a post rule"

        # running it after does satisfy it
        early.append("tool.call", {"name": "run_command",
                                   "args": {"command": "pytest -q"}})
        assert t2.blocker() is None

        # -- a read invalidated by a later write is re-armed ---------------
        inv = EventLog(Path(td) / "inv.jsonl")
        t3 = Timeline(inv, "§20 read first\n"
                           "@sequence before write src/** require read same\n")
        inv.append("tool.call", {"name": "read_file",
                                 "args": {"path": "src/a.py"}})
        assert t3.gate("write_file", {"path": "src/a.py",
                                      "content": "x"}) is None
        # something else rewrote it after the read
        inv.append("tool.call", {"name": "run_command",
                                 "args": {"command": "echo z > src/a.py"}})
        again = t3.gate("write_file", {"path": "src/a.py", "content": "x"})
        assert again and "read it again" in again, again

        # -- rules that never trigger stay quiet ---------------------------
        assert tl.gate("run_command", {"command": "ls -la"}) is None
        assert tl.gate("read_file", {"path": "src/app.py"}) is None

        # -- no rules means no interference --------------------------------
        quiet = Timeline(EventLog(Path(td) / "q.jsonl"), "")
        assert quiet.gate("write_file", {"path": "anything", "content": "x"}) \
            is None
        assert quiet.blocker() is None
        assert "no @sequence rules" in quiet.report()

        # -- refusals are sealed -------------------------------------------
        assert any(e.type == "sequence.blocked" for e in log.events())

        # -- malformed rules are reported, never guessed at ----------------
        bad = Timeline(log, "§22 x\n@sequence sideways write a require read b\n"
                            "§23 y\n@sequence before write a\n"
                            "§24 z\n@sequence before write a require run same\n")
        assert len(bad.errors) == 3, bad.errors
        assert bad.rules == []

    print("SEQUENCE SELF-TEST PASS")
