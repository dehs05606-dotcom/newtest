"""CONFORM — the reply is checked before it is accepted, not after.

attest.py checks the reply's factual claims against the log and REPORTS.
Reporting is the right behaviour for a claim about the past: the transcript
should record what the agent said, not a corrected version of it.

It is the wrong behaviour for a rule about form. If the specification says
"every code change is reported as file:line", or "never state a test passed
without the exit code", then a reply that breaks it is not a historical
record to preserve — it is a draft that has not met the contract yet, and
nothing in this package stops it reaching the user.

That is the last place the specification is purely advisory. Actions are
refused, effects are reverted, budgets are enforced, and the text — the one
artefact the user actually reads — is governed by nothing.

So output rules are checked against the DRAFT, and a failing draft is sent
back to the model with the clause it broke:

    [OUT] Test results are reported with the exit code.
    @output forbid (?i)tests? (pass|fail)\\w*(?![^.]*exit)
    @output require file:\\d+   when   (?i)\\b(edited|changed|wrote)\\b

    draft 1  ->  "The tests pass now."          breaks [OUT]
    draft 2  ->  "pytest -q: exit 0, 41 passed"  accepted

Three properties keep this from being a way to launder bad output:

  1. BOUNDED. A fixed number of attempts, then the draft goes through as it
     is, with the unmet clauses attached. An unbounded loop would burn a
     turn and could never terminate on a rule the model cannot satisfy.
  2. HONEST ON FAILURE. What the user sees when conformance fails is the
     real draft plus the rules it broke — never a silently dropped reply
     and never a fabricated conforming one.
  3. THE RULES ARE THE AUTHOR'S. Every check is an @output line in the
     specification. This module invents no requirement and rewrites no
     text; it decides only whether to accept a draft or ask again.

@output kinds:

    @output forbid  <regex>              the reply must not match
    @output require <regex>              the reply must match
    @output require <regex> when <regex> required only if the reply matches
                                          the `when` pattern
    @output max_chars <n>                length ceiling

`when` is a regex over the reply text, so it is exactly as precise as the
pattern the author writes: a condition of /changed/ arms on "nothing was
changed" too. That is a property of the rule and is left to the author to
tighten, because narrowing it here would mean guessing which sentences
they meant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .kernel import EventLog

DEFAULT_ATTEMPTS = 2        # regenerations, not total drafts

_OUTPUT_RE = re.compile(
    r"^\s*@output\s+(?P<kind>forbid|require|max_chars)\s+(?P<rest>.+?)\s*$",
    re.I)
_WHEN = re.compile(r"\s+when\s+", re.I)


@dataclass(frozen=True)
class Rule:
    clause: str
    kind: str              # forbid | require | max_chars
    pattern: str = ""
    when: str = ""         # require only: the condition that arms it
    limit: int = 0         # max_chars only

    def to_dict(self) -> dict:
        d = {"clause": self.clause, "kind": self.kind}
        if self.pattern:
            d["pattern"] = self.pattern
        if self.when:
            d["when"] = self.when
        if self.limit:
            d["limit"] = self.limit
        return d

    def describe(self) -> str:
        if self.kind == "max_chars":
            return f"{self.clause}: the reply must be at most {self.limit} chars"
        if self.kind == "forbid":
            return f"{self.clause}: the reply must not match {self.pattern!r}"
        scope = f" (because it matches {self.when!r})" if self.when else ""
        return f"{self.clause}: the reply must match {self.pattern!r}{scope}"


@dataclass(frozen=True)
class Unmet:
    rule: Rule
    detail: str

    def to_dict(self) -> dict:
        return {**self.rule.to_dict(), "detail": self.detail}


@dataclass
class Outcome:
    text: str
    attempts: int = 1
    unmet: list[Unmet] = None          # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.unmet is None:
            self.unmet = []

    @property
    def conformed(self) -> bool:
        return not self.unmet

    def annotated(self) -> str:
        """The text as the user should see it. A draft that never
        conformed carries the rules it broke, rather than being dropped or
        quietly presented as though it had."""
        if self.conformed:
            return self.text
        lines = [self.text, "",
                 f"[conform] this reply does not meet "
                 f"{len(self.unmet)} output rule"
                 f"{'s' if len(self.unmet) > 1 else ''} after "
                 f"{self.attempts} attempt"
                 f"{'s' if self.attempts > 1 else ''}:"]
        for u in self.unmet:
            lines.append(f"  {u.detail}")
        return "\n".join(lines)


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
        if not re.match(r"^\s*@output\b", line, re.I):
            continue
        m = _OUTPUT_RE.match(line)
        if not m:
            errors.append(f"{clause}: malformed @output — expected "
                          f"'forbid <regex>', 'require <regex> [when "
                          f"<regex>]' or 'max_chars <n>'")
            continue
        kind = m.group("kind").lower()
        rest = m.group("rest").strip()
        if kind == "max_chars":
            try:
                limit = int(rest)
            except ValueError:
                errors.append(f"{clause}: max_chars needs a number")
                continue
            if limit <= 0:
                errors.append(f"{clause}: max_chars must be positive")
                continue
            rules.append(Rule(clause, kind, limit=limit))
            continue
        when = ""
        if kind == "require":
            parts = _WHEN.split(rest, maxsplit=1)
            if len(parts) == 2:
                rest, when = parts[0].strip(), parts[1].strip()
        bad = False
        for rx in (rest, when):
            if not rx:
                continue
            try:
                re.compile(rx)
            except re.error as e:
                errors.append(f"{clause}: invalid @output regex ({e})")
                bad = True
        if bad or not rest:
            if not rest:
                errors.append(f"{clause}: @output {kind} needs a pattern")
            continue
        rules.append(Rule(clause, kind, pattern=rest, when=when))
    return rules, errors


def check(rules: list[Rule], text: str) -> list[Unmet]:
    """Output rules this draft does not meet. Pure and deterministic."""
    out: list[Unmet] = []
    body = text or ""
    for r in rules:
        if r.kind == "max_chars":
            if len(body) > r.limit:
                out.append(Unmet(r, f"{r.clause}: the reply is "
                                    f"{len(body):,} chars, over the "
                                    f"{r.limit:,} allowed"))
        elif r.kind == "forbid":
            m = re.search(r.pattern, body)
            if m:
                out.append(Unmet(r, f"{r.clause}: the reply contains "
                                    f"{m.group(0)[:60]!r}, which this "
                                    f"clause forbids"))
        elif r.kind == "require":
            if r.when and not re.search(r.when, body):
                continue          # the rule is not armed for this reply
            if not re.search(r.pattern, body):
                why = (f" (it matches {r.when!r}, which requires this)"
                       if r.when else "")
                out.append(Unmet(r, f"{r.clause}: the reply must match "
                                    f"{r.pattern!r} and does not{why}"))
    return out


def instruction(unmet: list[Unmet]) -> str:
    """What to send back with the draft.

    States the rule and what the draft did, and nothing else. It does not
    write a replacement or suggest wording: a module that drafted the
    conforming answer would be answering for the model, and the reply would
    stop being the model's.
    """
    lines = [f"Your draft does not meet {len(unmet)} output rule"
             f"{'s' if len(unmet) > 1 else ''} from the specification. "
             f"Rewrite it so that it does. Change nothing else."]
    for u in unmet:
        # both halves are needed: what the draft did, and what the rule
        # requires. The first alone leaves the model guessing at the
        # target; the second alone leaves it guessing at the miss.
        lines.append(f"  {u.detail}")
        lines.append(f"    rule: {u.rule.describe()}")
    return "\n".join(lines)


class Conform:
    """Draft, check, ask again — bounded."""

    def __init__(self, log: EventLog, spec: str = "",
                 attempts: int = DEFAULT_ATTEMPTS) -> None:
        self.log = log
        self.attempts = max(0, int(attempts))
        self.rules: list[Rule] = []
        self.errors: list[str] = []
        self.checked = 0
        self.regenerated = 0
        self.failed = 0
        self.bind(spec)

    def bind(self, spec: str) -> None:
        self.rules, self.errors = parse_rules(spec or "")

    def check(self, text: str) -> list[Unmet]:
        return check(self.rules, text)

    def run(self, draft: str, regenerate) -> Outcome:
        """Accept `draft`, or ask `regenerate(instruction)` for another.

        `regenerate` is a callable the caller supplies — the agent passes
        one that re-runs the model with the instruction appended. Passing
        it in keeps this module free of any model client, so it is testable
        without one and cannot itself call a model.
        """
        if not self.rules:
            return Outcome(draft)
        self.checked += 1
        text = draft
        unmet = self.check(text)
        tries = 1
        while unmet and tries <= self.attempts:
            self.log.append("conform.rejected",
                            {"attempt": tries,
                             "unmet": [u.to_dict() for u in unmet]},
                            actor="kernel")
            self.regenerated += 1
            try:
                nxt = regenerate(instruction(unmet))
            except Exception as e:          # noqa: BLE001 — never lose a draft
                self.log.append("conform.error",
                                {"error": f"{type(e).__name__}: {e}"},
                                actor="kernel")
                break
            tries += 1
            if not nxt or not str(nxt).strip():
                break                       # an empty retry is not progress
            text = str(nxt)
            unmet = self.check(text)

        if unmet:
            self.failed += 1
            self.log.append("conform.unmet",
                            {"attempts": tries,
                             "unmet": [u.to_dict() for u in unmet]},
                            actor="kernel")
        else:
            self.log.append("conform.accepted", {"attempts": tries},
                            actor="kernel")
        return Outcome(text, tries, unmet)

    def report(self) -> str:
        if not self.rules:
            return "conform: no @output rules in the specification"
        lines = [f"conform: {len(self.rules)} output rule(s) · "
                 f"{self.checked} reply(ies) checked · "
                 f"{self.regenerated} regenerated · {self.failed} still unmet"]
        for r in self.rules:
            lines.append(f"  {r.describe()}")
        for e in self.errors:
            lines.append(f"  !! {e}")
        return "\n".join(lines)


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        log = EventLog(Path(td) / "log.jsonl")

        spec = r'''[OUT] Test results are reported with the exit code
@output forbid (?i)tests? (pass|fail)\w*(?![^.]*exit)

[CITE] A described change cites file:line
@output require \S+:\d+   when   (?i)\b(edited|changed|wrote|updated)\b

[LEN] Replies stay short
@output max_chars 400
'''
        con = Conform(log, spec, attempts=2)
        assert len(con.rules) == 3 and not con.errors, (con.rules, con.errors)

        # -- a conforming draft passes untouched, with no regeneration -----
        good = "pytest -q: exit 0, 41 passed."
        out = con.run(good, lambda _: "should not be called")
        assert out.conformed and out.text == good and out.attempts == 1
        assert con.regenerated == 0

        # -- a failing draft is sent back with the clause it broke ---------
        seen: list[str] = []

        def fix(instruction: str) -> str:
            seen.append(instruction)
            return "pytest -q: exit 0, 41 passed."

        out = con.run("The tests pass now.", fix)
        assert out.conformed, out.unmet
        assert out.attempts == 2 and len(seen) == 1
        # the instruction carries BOTH the miss and the rule
        assert "OUT" in seen[0]
        assert "the reply contains" in seen[0]          # what it did
        assert "rule: OUT: the reply must not match" in seen[0]  # the target
        # but it never writes the answer
        assert "exit 0" not in seen[0]

        # -- `when` arms a rule only for replies it applies to -------------
        assert con.check("The parser looks correct as it is.") == []
        # `when` is a regex over the reply, so it is exactly as precise as
        # the author's pattern: "nothing was changed" trips a /changed/
        # condition. That is a property of the rule, not a bug here.
        assert con.check("Nothing was changed here.")
        unmet = con.check("I edited the parser.")
        assert len(unmet) == 1 and unmet[0].rule.clause == "CITE"
        assert con.check("I edited the parser at src/p.py:42.") == []

        # -- BOUNDED: a rule nothing can satisfy does not loop forever -----
        calls = {"n": 0}

        def never(instruction: str) -> str:
            calls["n"] += 1
            return "The tests pass now."

        out = con.run("The tests pass now.", never)
        assert not out.conformed
        assert calls["n"] == 2, calls        # attempts, not unbounded
        assert out.attempts == 3             # the original plus two retries

        # -- HONEST: the user sees the real draft and what it broke --------
        shown = out.annotated()
        assert shown.startswith("The tests pass now.")
        assert "[conform]" in shown and "OUT" in shown
        assert "does not meet" in shown

        # -- a regenerator that raises never loses the draft ---------------
        def boom(instruction: str) -> str:
            raise RuntimeError("model unavailable")

        out = con.run("The tests pass now.", boom)
        assert out.text == "The tests pass now." and not out.conformed
        assert any(e.type == "conform.error" for e in log.events())

        # -- an empty regeneration is not treated as progress --------------
        out = con.run("The tests pass now.", lambda _: "")
        assert out.text == "The tests pass now." and not out.conformed

        # -- max_chars ------------------------------------------------------
        long = Conform(log, "[LEN] short\n@output max_chars 20\n")
        out = long.run("x" * 50, lambda _: "y" * 10)
        assert out.conformed and out.text == "y" * 10

        # -- no rules means the draft is never touched ---------------------
        quiet = Conform(log, "")
        out = quiet.run("anything at all", lambda _: "should not be called")
        assert out.text == "anything at all" and out.conformed
        assert "no @output rules" in quiet.report()

        # -- attempts=0 checks but never regenerates -----------------------
        strict = Conform(log, spec, attempts=0)
        out = strict.run("The tests pass now.", lambda _: "unused")
        assert not out.conformed and out.attempts == 1

        # -- every outcome is sealed ---------------------------------------
        kinds = {e.type for e in log.events()}
        assert {"conform.accepted", "conform.rejected",
                "conform.unmet"} <= kinds, kinds

        # -- malformed rules are reported, never guessed at ----------------
        bad = Conform(log, "[A] x\n@output sideways foo\n"
                           "[B] y\n@output forbid [unclosed\n"
                           "[C] z\n@output max_chars nope\n"
                           "[D] w\n@output max_chars -3\n")
        assert len(bad.errors) == 4, bad.errors
        assert bad.rules == []

    print("CONFORM SELF-TEST PASS")
