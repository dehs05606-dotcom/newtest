"""DISTILL — proposing rules for the clauses that enforce nothing.

audit.py reports the number and it is always the same shape: a
specification of several hundred clauses, of which a handful carry an
@enforce or @output rule and the rest are prose. The prose clauses are not
idle — they are what the author actually wrote, and they are the reason the
specification is 150k chars — but to every mechanism in this package they
are invisible. They cannot refuse an action, cannot check a reply, and
cannot be measured by adherence.py, which reports them as UNSCORABLE rather
than counting them as followed.

Writing a rule for each one by hand is the correct fix and nobody does it,
because there are four hundred of them. So this reads the prose and
proposes the rule it implies:

    "Secrets never appear in source."
        -> @enforce forbid_content: (?i)(api[_-]?key|token|password)\\s*=

    "Writes stay under src/ and tests/."
        -> @enforce confine_paths: src, tests

    "Every module ships with a test."
        -> @oblige on write **/*.py require exists tests/test_{stem}.py

It PROPOSES. Nothing here edits the specification, and nothing it produces
is enforced until the author pastes it in. That restraint is the whole
design, not caution for its own sake:

  * An inferred rule that is too broad refuses legitimate work, and the
    operator's fix for a boundary that blocks real work is to switch the
    boundary off — so a wrong guess does not cost one clause, it costs the
    whole mechanism's credibility.
  * An inferred rule that is too narrow is worse, because it reports as
    enforced. The author reads "247 clauses enforced" and believes a
    guarantee that does not exist, which is the precise failure this
    package was built to remove.

So every proposal carries the clause it came from, the sentence that
triggered it, and a confidence, and the output is a patch to read — never a
change to apply.

Confidence is what the PATTERN earned, not what the rule is worth:
    high    an unambiguous prohibition with a concrete object
    medium  a clear directive whose object had to be generalised
    low     a plausible reading that needs the author's eye

Nothing above "low" is guessed at from a verb alone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

HIGH = "high"
MEDIUM = "medium"
LOW = "low"
_ORDER = {HIGH: 0, MEDIUM: 1, LOW: 2}


@dataclass(frozen=True)
class Proposal:
    clause: str
    line: str              # the @enforce / @output / @oblige line to paste
    confidence: str
    because: str           # the sentence it was read from
    note: str = ""

    def to_dict(self) -> dict:
        return {"clause": self.clause, "line": self.line,
                "confidence": self.confidence, "because": self.because,
                "note": self.note}


# ---------------------------------------------------------------------------
# readings — each returns proposals for one sentence
# ---------------------------------------------------------------------------

_NEG = r"(?:never|must not|must never|do not|don't|no\b|cannot|shall not)"
_POS = r"(?:always|must|shall|should|has to|have to)"

_SECRET = r"(?:secret|credential|api[_ -]?key|token|password|passphrase)"

# "secrets never appear in source" / "never commit credentials"
_R_SECRET = re.compile(
    rf"\b{_SECRET}s?\b[^.]*\b{_NEG}\b|\b{_NEG}\b[^.]*\b{_SECRET}s?\b", re.I)

# "writes stay under src/ and tests/" / "work only in src"
_R_CONFINE = re.compile(
    r"\b(?:writes?|work|changes?|edits?|files?)\b[^.]*?\b(?:stay|remain|live|"
    r"confined|only)\b[^.]*?\b(?:under|in|within|inside)\s+"
    r"(?P<roots>[\w./*-]+(?:\s*(?:,|and|or)\s*[\w./*-]+)*)", re.I)

# "never delete" / "nothing is ever deleted"
_R_DELETE = re.compile(
    rf"\b{_NEG}\b[^.]*\b(?:delete|remove|rm|erase)\b"
    rf"|\b(?:nothing|no файл|no file)\b[^.]*\bever\s+(?:deleted|removed)\b",
    re.I)

# "never run destructive shell commands" / "no rm -rf"
_R_DESTRUCTIVE = re.compile(
    rf"\b{_NEG}\b[^.]*\b(?:rm\s+-rf|force[- ]push|drop\s+table|"
    rf"destructive)\b", re.I)

# "every module ships with a test" / "each .py file has a test"
_R_OBLIGE_TEST = re.compile(
    r"\b(?:every|each|all)\b[^.]*\b(?:module|file|source file)\b[^.]*"
    r"\b(?:ships? with|has|have|needs?|requires?|comes? with)\b[^.]*\btests?\b",
    re.I)

# "every public function carries a docstring"
_R_DOCSTRING = re.compile(
    r"\b(?:every|each|all)\b[^.]*\b(?:function|module|class)\b[^.]*"
    r"\b(?:carr(?:y|ies)|has|have|needs?|requires?)\b[^.]*\bdocstring\b", re.I)

# "never claim a test passed without the exit code"
_R_EXITCODE = re.compile(
    rf"\b{_NEG}\b[^.]*\b(?:claim|say|state|report)\b[^.]*\b(?:test|pass)\w*"
    rf"|\btests?\b[^.]*\breported?\b[^.]*\bexit code\b", re.I)

# "cite file:line" / "always reference the file and line"
_R_CITE = re.compile(
    rf"\b(?:cite|reference|quote)\b[^.]*\b(?:file:?line|file and line|"
    rf"path and line)\b|\b{_POS}\b[^.]*\bcite\b", re.I)

# "the agent reaches only <hosts>" / "network access only to X"
_R_HOSTS = re.compile(
    # verbs take their inflections: "reaches", "contacts", "connects to"
    r"\b(?:reach\w*|contact\w*|connect\w*|network access|fetch\w*)\b[^.]*?"
    r"\bonly\b[^.]*?(?P<hosts>[\w-]+\.[\w.]{2,}(?:\s*(?:,|and)\s*"
    r"[\w-]+\.[\w.]{2,})*)", re.I)


def _split_roots(raw: str) -> list[str]:
    parts = re.split(r"\s*(?:,|\band\b|\bor\b)\s*", raw)
    return [p.strip().rstrip("/") for p in parts
            if p.strip() and p.strip() not in ("the", "a", "an")]


def read_sentence(clause_id: str, sentence: str) -> list[Proposal]:
    """Every rule this one sentence plausibly implies."""
    s = sentence.strip()
    if len(s) < 12:
        return []
    out: list[Proposal] = []

    if _R_SECRET.search(s):
        out.append(Proposal(
            clause_id,
            "@enforce forbid_content: (?i)(api[_-]?key|token|password|"
            "secret)\\s*=\\s*[\"'][A-Za-z0-9]",
            HIGH, s,
            "matches a literal assignment; widen it if your secrets appear "
            "in other shapes"))

    m = _R_CONFINE.search(s)
    if m:
        roots = _split_roots(m.group("roots"))
        if roots:
            out.append(Proposal(
                clause_id, f"@enforce confine_paths: {', '.join(roots)}",
                HIGH if len(roots) <= 3 else MEDIUM, s,
                "confine_paths refuses every write and delete outside these "
                "roots, by any route"))

    if _R_DELETE.search(s):
        out.append(Proposal(
            clause_id, "@enforce forbid_effect: delete", HIGH, s,
            "refuses deletion by any route, including rm and mv"))

    if _R_DESTRUCTIVE.search(s):
        out.append(Proposal(
            clause_id,
            "@enforce forbid_command: (?i)(rm\\s+-rf\\s+/|push\\s+--force|"
            "drop\\s+table)",
            MEDIUM, s,
            "matches the command text; list the exact forms you mean"))

    if _R_OBLIGE_TEST.search(s):
        out.append(Proposal(
            clause_id,
            "@oblige on write src/**/*.py require exists "
            "tests/test_{stem}.py",
            MEDIUM, s,
            "adjust the paths to your layout; this blocks 'done', not work"))

    if _R_DOCSTRING.search(s):
        out.append(Proposal(
            clause_id,
            '@enforce {"kind": "require_content", "value": "^\\\\s*[\\"\']{3}",'
            ' "where": "*.py"}',
            MEDIUM, s,
            "checks the written content of .py files only"))

    if _R_EXITCODE.search(s):
        out.append(Proposal(
            clause_id,
            "@output forbid (?i)tests? (pass|fail)\\w*(?![^.]*exit)",
            HIGH, s,
            "checks the reply, and a failing draft is regenerated"))

    if _R_CITE.search(s):
        out.append(Proposal(
            clause_id,
            "@output require \\S+:\\d+   when   (?i)\\b(edited|changed|"
            "wrote|updated)\\b",
            MEDIUM, s,
            "armed only for replies that describe a change"))

    m = _R_HOSTS.search(s)
    if m:
        hosts = _split_roots(m.group("hosts"))
        if hosts:
            out.append(Proposal(
                clause_id, f"@egress allow_hosts {', '.join(hosts)}",
                HIGH, s,
                "an allowlist: every host not named is refused, including "
                "ones that cannot be read before the command runs"))
    return out


def sentences(text: str) -> list[str]:
    """Split a clause body into sentences, skipping its own rule lines."""
    out: list[str] = []
    for line in (text or "").splitlines():
        if re.match(r"^\s*@(enforce|output|oblige|horizon|ration|egress|"
                    r"sequence|origin|except|authority)\b", line, re.I):
            continue
        for part in re.split(r"(?<=[.!?])\s+", line):
            part = part.strip()
            if part:
                out.append(part)
    return out


def distill(clauses, only_unenforced: bool = True) -> list[Proposal]:
    """Proposals for a specification's clauses.

    Defaults to clauses that carry no rule: proposing a rule for a clause
    that already has one invites the author to add a second, subtly
    different one, and two rules for a clause is how a specification starts
    contradicting itself.
    """
    out: list[Proposal] = []
    seen: set[tuple[str, str]] = set()
    for c in clauses:
        if only_unenforced and getattr(c, "enforced", False):
            continue
        body = ((c.title or "") + "\n" + (c.body or ""))
        for s in sentences(body):
            for p in read_sentence(c.id, s):
                key = (p.clause, p.line)
                if key in seen:
                    continue
                seen.add(key)
                out.append(p)
    out.sort(key=lambda p: (_ORDER[p.confidence], p.clause))
    return out


def patch(proposals: list[Proposal], minimum: str = LOW) -> str:
    """The proposals as text to paste into the specification."""
    keep = [p for p in proposals if _ORDER[p.confidence] <= _ORDER[minimum]]
    if not keep:
        return ""
    lines = ["# Proposed rules — read each one, then paste the ones you want",
             "# into the matching clause in systemprompt.py. Nothing here is",
             "# in force until you do.", ""]
    current = ""
    for p in keep:
        if p.clause != current:
            lines.append(f"# --- clause {p.clause} " + "-" * 44)
            current = p.clause
        lines.append(f"#   because: {p.because[:100]}")
        if p.note:
            lines.append(f"#   note   : {p.note}")
        lines.append(f"#   [{p.confidence}]")
        lines.append(p.line)
        lines.append("")
    return "\n".join(lines)


def report(clauses, proposals: list[Proposal] | None = None) -> str:
    clauses = list(clauses)
    props = distill(clauses) if proposals is None else proposals
    unenforced = [c for c in clauses if not getattr(c, "enforced", False)]
    if not clauses:
        return "distill: no specification is bound"
    by_conf: dict[str, int] = {}
    for p in props:
        by_conf[p.confidence] = by_conf.get(p.confidence, 0) + 1
    covered = len({p.clause for p in props})
    lines = [
        f"distill: {len(unenforced)} of {len(clauses)} clauses carry no rule",
        f"  {len(props)} proposal(s) for {covered} of them "
        f"({', '.join(f'{k}:{v}' for k, v in sorted(by_conf.items()))or 'none'})",
        f"  {len(unenforced) - covered} clause(s) yielded nothing — prose "
        f"this module cannot read into a rule",
        "  nothing is applied: run /distill patch to see the text",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    from .covenant import Covenant
    from .kernel import EventLog

    with tempfile.TemporaryDirectory() as td:
        log = EventLog(Path(td) / "log.jsonl")

        spec = '''[SEC] Secrets never appear in source
Credentials and API keys live in the environment, not in files.

[PATH] Writes stay under src/ and tests/
Nothing outside those roots is ever modified by the agent.

[DEL] Nothing is ever deleted
If something must go, move it aside instead.

[TEST] Every module ships with a test
A source file without a matching test is incomplete.

[EXIT] Never claim a test passed without the exit code
Report the command and its exit status.

[NET] The agent reaches only pypi.org and github.com
No other host is contacted.

[DOC] Every public function carries a docstring

[VAGUE] Write thoughtful code that other people can maintain.

[DONE] This one already has a rule
@enforce forbid_effect: exec
'''
        cov = Covenant(log, spec)
        props = distill(cov.clauses)
        by_clause = {}
        for p in props:
            by_clause.setdefault(p.clause, []).append(p)

        # -- the readings that should fire ----------------------------------
        assert "forbid_content" in by_clause["SEC"][0].line
        assert by_clause["SEC"][0].confidence == HIGH

        confine = next(p for p in by_clause["PATH"]
                       if "confine_paths" in p.line)
        assert "src" in confine.line and "tests" in confine.line, confine.line

        assert any("forbid_effect: delete" in p.line for p in by_clause["DEL"])
        assert any("@oblige" in p.line for p in by_clause["TEST"])
        assert any("@output forbid" in p.line for p in by_clause["EXIT"])
        assert any("require_content" in p.line for p in by_clause["DOC"])

        nets = next(p for p in by_clause["NET"] if "allow_hosts" in p.line)
        assert "pypi.org" in nets.line and "github.com" in nets.line, nets.line

        # -- prose it cannot read yields nothing, rather than a guess ------
        assert "VAGUE" not in by_clause, by_clause.get("VAGUE")

        # -- a clause that already has a rule is left alone ----------------
        assert "DONE" not in by_clause

        # -- every proposal carries its evidence ---------------------------
        for p in props:
            assert p.because and p.because in spec, p.because
            assert p.confidence in (HIGH, MEDIUM, LOW)
            assert p.clause

        # -- it PROPOSES: the patch is text, and nothing is in force -------
        text = patch(props)
        assert "Nothing here is" in text and "in force until you do" in text
        assert "@enforce confine_paths" in text
        # the specification is untouched
        assert Covenant(log, spec).guards == cov.guards

        # -- and the proposals really are valid rules ----------------------
        # (paste them back and the parser accepts them)
        pasted = "\n".join(
            f"[{p.clause}] x\n{p.line}" for p in props
            if p.line.startswith("@enforce"))
        checked = Covenant(log, pasted)
        assert checked.guards, "proposed @enforce lines did not parse"
        assert not checked.errors, checked.errors

        # -- confidence filters ---------------------------------------------
        high_only = patch(props, minimum=HIGH)
        assert "[high]" in high_only and "[medium]" not in high_only

        # -- deterministic ---------------------------------------------------
        assert [p.to_dict() for p in distill(cov.clauses)] == \
               [p.to_dict() for p in distill(cov.clauses)]

        # -- the report counts what was NOT covered, not just what was -----
        rep = report(cov.clauses)
        assert "yielded nothing" in rep and "nothing is applied" in rep

        # -- an empty specification proposes nothing -----------------------
        assert distill(Covenant(log, "").clauses) == []
        assert patch([]) == ""

    print("DISTILL SELF-TEST PASS")
