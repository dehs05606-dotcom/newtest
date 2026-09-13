"""OBLIGATION — the clauses that are broken by doing nothing.

Every guard so far refuses an act. That shape can only ever catch
COMMISSION: the agent tried to write the wrong thing, delete the wrong
thing, reach the wrong place. Refuse hard enough and the agent complies
perfectly by doing nothing at all.

Most of a real specification is not like that. "Every module ships with a
test." "A public function carries a docstring." "A schema change comes with
a migration." None of these can be enforced by refusing a call, because the
violation is not a call — it is a call that never came. An omission has no
action to gate.

So an obligation is not a guard. It is a DEBT:

    §6 Every module ships with a test.
    @oblige on write src/**/*.py require exists tests/test_{stem}.py

    writing src/parser.py            ->  incurs  tests/test_parser.py
    writing tests/test_parser.py     ->  discharges it
    still outstanding                ->  the debt is the blocker

The ledger is folded from the event log, so it survives a restart and is
auditable: every debt names the clause that created it, the act that
incurred it, and the condition that will settle it. Nothing is remembered
in a variable that a crash can lose.

Enforcement is by BLOCKING PROGRESS rather than by refusing work. An
outstanding debt does not stop the agent editing files — that would make
the specification impossible to satisfy, since the discharging write is
itself an act. It stops the things that mean "done": closing a goal,
declaring a task complete, ending a turn clean. The debt cannot be
out-waited, and it cannot be talked away, because settling it is a fact on
disk rather than an assertion in a reply.

Templates available in a require path: {stem} {name} {parent} {path}.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path, PurePath

from .effects import DELETE, WRITE, derive
from .kernel import EventLog

_OBLIGE_RE = re.compile(
    r"^\s*@oblige\s+on\s+(?P<act>write|delete)\s+(?P<glob>\S+)\s+"
    r"require\s+(?P<kind>exists|absent|contains)\s+(?P<target>\S+)"
    r"(?:\s+matching\s+(?P<pattern>.+))?\s*$", re.I)


@dataclass(frozen=True)
class Rule:
    """A debt-creating clause."""
    clause: str
    act: str          # write | delete
    glob: str         # which paths trigger it
    kind: str         # exists | absent | contains
    target: str       # templated path
    pattern: str = ""  # for `contains`

    def to_dict(self) -> dict:
        d = {"clause": self.clause, "act": self.act, "glob": self.glob,
             "kind": self.kind, "target": self.target}
        if self.pattern:
            d["pattern"] = self.pattern
        return d


@dataclass(frozen=True)
class Debt:
    """One outstanding requirement, traceable to what incurred it."""
    clause: str
    kind: str
    target: str
    pattern: str
    incurred_by: str          # the path whose change created the debt
    act: str = "write"        # the act on that path which created it

    @property
    def id(self) -> str:
        return f"{self.clause}:{self.kind}:{self.target}"

    def to_dict(self) -> dict:
        return {"clause": self.clause, "kind": self.kind,
                "target": self.target, "pattern": self.pattern,
                "incurred_by": self.incurred_by, "act": self.act}

    def settled(self, root: Path | None = None) -> bool:
        """Whether the world now satisfies this debt. A fact on disk —
        never a claim, never a flag someone can set."""
        p = Path(self.target)
        if root and not p.is_absolute():
            p = root / p
        if self.kind == "exists":
            return p.is_file()
        if self.kind == "absent":
            return not p.exists()
        if self.kind == "contains":
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return False
            if not self.pattern:
                return True
            try:
                return re.search(self.pattern, text) is not None
            except re.error:
                return False
        return True

    def describe(self) -> str:
        what = {"exists": "must exist",
                "absent": "must not exist",
                "contains": f"must match {self.pattern!r}"}[self.kind]
        return (f"{self.clause}: {self.target} {what} "
                f"(incurred by {self.incurred_by})")


def parse_rules(spec: str) -> tuple[list[Rule], list[str]]:
    """Read @oblige lines out of a specification."""
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
        if not re.match(r"^\s*@oblige\b", line, re.I):
            continue
        m = _OBLIGE_RE.match(line)
        if not m:
            errors.append(
                f"{clause}: malformed @oblige — expected "
                f"'@oblige on write <glob> require exists <path>'")
            continue
        kind = m.group("kind").lower()
        pattern = (m.group("pattern") or "").strip()
        if kind == "contains" and not pattern:
            errors.append(f"{clause}: `contains` needs `matching <regex>`")
            continue
        if pattern:
            try:
                re.compile(pattern)
            except re.error as e:
                errors.append(f"{clause}: invalid `matching` regex ({e})")
                continue
        rules.append(Rule(clause=clause, act=m.group("act").lower(),
                          glob=m.group("glob"), kind=kind,
                          target=m.group("target"), pattern=pattern))
    return rules, errors


def _norm(path: str) -> str:
    parts: list[str] = []
    for part in PurePath(path).parts:
        if part == "..":
            if parts:
                parts.pop()
        elif part != ".":
            parts.append(part)
    return "/".join(parts)


def _expand(target: str, path: str) -> str:
    p = PurePath(_norm(path))
    return (target.replace("{stem}", p.stem)
                  .replace("{name}", p.name)
                  .replace("{parent}", str(p.parent))
                  .replace("{path}", str(p)))


class Ledger:
    """The outstanding debts, folded from the log."""

    def __init__(self, log: EventLog, spec: str = "",
                 root: Path | None = None) -> None:
        self.log = log
        self.root = root
        self.rules: list[Rule] = []
        self.errors: list[str] = []
        self.bind(spec)

    def bind(self, spec: str) -> None:
        self.rules, self.errors = parse_rules(spec or "")

    # -- incurring ----------------------------------------------------------

    def incurred_by(self, tool: str, args: dict) -> list[Debt]:
        """The debts a call would create. Derived from EFFECTS, so a write
        through the shell incurs exactly what write_file would."""
        out: list[Debt] = []
        seen: set[str] = set()
        for e in derive(tool, args):
            if e.kind not in (WRITE, DELETE) or not e.path:
                continue
            act = "write" if e.kind == WRITE else "delete"
            norm = _norm(e.path)
            for rule in self.rules:
                if rule.act != act:
                    continue
                if not (fnmatch.fnmatch(norm, rule.glob)
                        or fnmatch.fnmatch(norm, rule.glob.rstrip("/") + "/*")
                        or _glob_deep(norm, rule.glob)):
                    continue
                debt = Debt(clause=rule.clause, kind=rule.kind,
                            target=_expand(rule.target, norm),
                            pattern=rule.pattern, incurred_by=norm,
                            act=act)
                if debt.id not in seen:
                    seen.add(debt.id)
                    out.append(debt)
        return out

    def record(self, tool: str, args: dict) -> list[Debt]:
        """Seal the debts a completed call incurred."""
        debts = self.incurred_by(tool, args)
        for d in debts:
            self.log.append("obligation.incurred", d.to_dict(),
                            actor="kernel")
        return debts

    # -- the fold -----------------------------------------------------------

    def outstanding(self) -> list[Debt]:
        """Every debt incurred and not yet satisfied by the world.

        Settlement is re-tested against disk on every fold rather than
        recorded as discharged, so a debt that was settled and then undone
        is outstanding again. A ledger that only ever counted down could be
        satisfied once and then quietly broken.

        A later act on a path SUPERSEDES the debts an earlier act on that
        same path created. "Writing src/x.py requires tests/test_x.py" and
        "deleting src/x.py requires tests/test_x.py to be gone" are both
        reasonable clauses, and after a write then a delete they contradict
        each other — a state no sequence of actions could ever satisfy. The
        path's current act decides, so the ledger always describes the
        world as it now is rather than as it once was.
        """
        live: dict[str, Debt] = {}
        latest_act: dict[str, str] = {}
        for ev in self.log.events():
            if ev.type != "obligation.incurred":
                continue
            d = Debt(clause=ev.data.get("clause", ""),
                     kind=ev.data.get("kind", "exists"),
                     target=ev.data.get("target", ""),
                     pattern=ev.data.get("pattern", ""),
                     incurred_by=ev.data.get("incurred_by", ""),
                     act=ev.data.get("act", "write"))
            live[d.id] = d
            latest_act[d.incurred_by] = d.act
        return [d for d in live.values()
                if latest_act.get(d.incurred_by, d.act) == d.act
                and not d.settled(self.root)]

    def blocker(self) -> str | None:
        """The reason progress cannot be declared complete, or None.

        Shaped for the goal/turn-closing path: an obligation never refuses
        work (the discharging write is itself work), it refuses DONE.
        """
        debts = self.outstanding()
        if not debts:
            return None
        lines = [f"ObligationOutstanding: {len(debts)} requirement"
                 f"{'s' if len(debts) > 1 else ''} from the specification "
                 f"are not met yet."]
        for d in debts[:12]:
            lines.append(f"  {d.describe()}")
        if len(debts) > 12:
            lines.append(f"  … and {len(debts) - 12} more")
        return "\n".join(lines)

    def report(self) -> str:
        if not self.rules:
            return "obligations: no @oblige rules in the specification"
        debts = self.outstanding()
        lines = [f"obligations: {len(self.rules)} rule"
                 f"{'s' if len(self.rules) > 1 else ''} · "
                 f"{len(debts)} outstanding"]
        for d in debts:
            lines.append(f"  ○ {d.describe()}")
        for e in self.errors:
            lines.append(f"  !! {e}")
        return "\n".join(lines)


def _glob_deep(path: str, pattern: str) -> bool:
    """`src/**/*.py` matches at any depth, including directly under src/."""
    if "**/" not in pattern:
        return False
    flat = pattern.replace("**/", "")
    return fnmatch.fnmatch(path, flat) or fnmatch.fnmatch(path, pattern)


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "src").mkdir()
        (root / "tests").mkdir()
        log = EventLog(root / "log.jsonl")

        spec = '''§6 Every module ships with a test
@oblige on write src/**/*.py require exists tests/test_{stem}.py

§7 A deleted module takes its test with it
@oblige on delete src/**/*.py require absent tests/test_{stem}.py

§8 The changelog records every migration
@oblige on write migrations/*.sql require contains CHANGELOG.md matching ^##
'''
        led = Ledger(log, spec, root=root)
        assert len(led.rules) == 3 and not led.errors, (led.rules, led.errors)

        # nothing owed before anything happens
        assert led.outstanding() == [] and led.blocker() is None

        # -- writing a module incurs the test debt -------------------------
        led.record("write_file", {"path": "src/parser.py", "content": "x"})
        debts = led.outstanding()
        assert len(debts) == 1, debts
        assert debts[0].target == "tests/test_parser.py"
        assert debts[0].clause == "6"
        blocker = led.blocker()
        assert blocker and "tests/test_parser.py" in blocker

        # -- it cannot be discharged by saying so, only by the world -------
        assert led.blocker() is not None
        (root / "tests" / "test_parser.py").write_text("ok", encoding="utf-8")
        assert led.outstanding() == [] and led.blocker() is None

        # -- and a debt that is undone comes back --------------------------
        (root / "tests" / "test_parser.py").unlink()
        assert len(led.outstanding()) == 1, "a settled debt stayed settled"

        (root / "tests" / "test_parser.py").write_text("ok", encoding="utf-8")

        # -- the shell route incurs the same debt as the direct one --------
        led.record("run_command", {"command": "echo x > src/lexer.py"})
        assert {d.target for d in led.outstanding()} == {
            "tests/test_lexer.py"}, led.outstanding()
        (root / "tests" / "test_lexer.py").write_text("ok", encoding="utf-8")
        assert not led.outstanding()

        # -- `absent` debts, and supersession ------------------------------
        # deleting src/parser.py must retire the debt that writing it
        # created, or §6 (test must exist) and §7 (test must be gone) would
        # demand a state nothing could reach
        led.record("delete_path", {"path": "src/parser.py"})
        out = led.outstanding()
        assert len(out) == 1 and out[0].kind == "absent", out
        assert out[0].act == "delete"
        (root / "tests" / "test_parser.py").unlink()
        assert not led.outstanding(), led.outstanding()

        # writing it again brings the original requirement back
        led.record("write_file", {"path": "src/parser.py", "content": "x"})
        out = led.outstanding()
        assert len(out) == 1 and out[0].kind == "exists", out
        (root / "tests" / "test_parser.py").write_text("ok", encoding="utf-8")
        assert not led.outstanding()

        # -- `contains` debts ----------------------------------------------
        (root / "migrations").mkdir()
        led.record("write_file", {"path": "migrations/001.sql", "content": ""})
        assert len(led.outstanding()) == 1
        (root / "CHANGELOG.md").write_text("notes\n", encoding="utf-8")
        assert len(led.outstanding()) == 1, "a non-matching file settled it"
        (root / "CHANGELOG.md").write_text("## 1.0\n", encoding="utf-8")
        assert not led.outstanding()

        # -- the ledger survives a restart: it is a fold, not a variable ---
        reopened = Ledger(EventLog(root / "log.jsonl"), spec, root=root)
        assert reopened.outstanding() == []
        (root / "tests" / "test_lexer.py").unlink()
        assert len(reopened.outstanding()) == 1, \
            "the debt did not survive reload"
        (root / "tests" / "test_lexer.py").write_text("ok", encoding="utf-8")

        # -- unmatched paths incur nothing ---------------------------------
        assert led.incurred_by("write_file",
                               {"path": "docs/readme.md", "content": ""}) == []

        # -- malformed rules are reported, never guessed at ----------------
        bad = Ledger(log, "§9 x\n@oblige on write src/* require\n"
                          "§10 y\n@oblige on write a require contains b\n"
                          "§11 z\n@oblige on write a require contains b "
                          "matching [unclosed\n")
        assert len(bad.errors) == 3, bad.errors
        assert bad.rules == []

    print("OBLIGATION SELF-TEST PASS")
