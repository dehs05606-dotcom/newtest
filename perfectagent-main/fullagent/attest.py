"""ATTEST — the reply is a claim about the world, and claims are checkable.

Everything upstream governs what the agent DOES. Nothing governs what it
SAYS it did, and the reply is where a specification is most casually
broken: "I ran the tests and they pass", "the file is updated", "I fixed
the import" — sentences whose truth nobody checked, in the one artefact the
user actually reads.

This is not a hypothetical failure. A model under length pressure, or one
that had a tool call fail three turns ago, reliably summarises the plan it
intended rather than the events that occurred. The summary is fluent,
confident, and wrong, and it is wrong in exactly the direction that looks
like success.

The event log already knows. Every tool call, every exit code, every
result is sealed in it. So a claim is not opinion — it is a proposition
about a record that exists:

    "tests pass"            -> was a test command run? did it exit 0?
    "I ran X"               -> is there a tool.call for X?
    "I created src/a.py"    -> did a write effect land on that path?
    "all 12 tests pass"     -> is 12 what the run actually reported?

attest() extracts those propositions and checks each against the log and
the filesystem. Every claim gets one of three verdicts:

    SUPPORTED    the record backs it
    CONTRADICTED the record refutes it — a test command ran and failed, a
                 file was never written
    UNSUPPORTED  nothing in the record speaks to it either way

The distinction matters. CONTRADICTED is a false statement about a
knowable fact. UNSUPPORTED is a statement the agent was not entitled to
make, which is a different failure and deserves different handling.

This module REPORTS. It does not rewrite the model's words, and nothing
here is fed back into the prompt: a summary that silently edits what the
agent said would make the transcript a worse record than the log it came
from. The verdict is sealed as 'attest.verdict' and surfaced to the user,
who can then see the gap between what was claimed and what happened.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .effects import DELETE, WRITE, derive
from .kernel import EventLog

SUPPORTED = "supported"
CONTRADICTED = "contradicted"
UNSUPPORTED = "unsupported"

# commands that constitute "running the tests"
_TEST_CMD_RE = re.compile(
    r"\b(pytest|py\.test|unittest|nose2|tox|jest|vitest|mocha|go\s+test|"
    r"cargo\s+test|npm\s+(?:run\s+)?test|yarn\s+test|make\s+test|"
    r"gradle\s+test|mvn\s+test|rspec|phpunit)\b", re.I)

_PASS_RE = re.compile(
    r"\b(?:all\s+)?(?:the\s+)?(?:(\d+)\s+)?tests?\b[^.!\n]{0,40}?"
    r"\b(pass(?:es|ed|ing)?|green|succeed(?:ed|s)?)\b", re.I)
_FAIL_RE = re.compile(r"\btests?\b[^.!\n]{0,30}?\b(fail(?:ed|s|ing)?)\b", re.I)

# "I ran `pytest -q`" is a claim about a command. "I ran the tests and they
# pass" is prose, and the tests_pass check already covers it — reading it as
# a command named "the tests and they pass" would manufacture a violation
# out of ordinary English. Backticks make it a command claim; bare text does
# so only when the first word could plausibly be a program.
_RAN_BACKTICK_RE = re.compile(
    r"\bI\s+(?:just\s+)?(?:ran|executed|invoked)\s+`([^`\n]{2,80})`", re.I)
_RAN_BARE_RE = re.compile(
    r"\bI\s+(?:just\s+)?(?:ran|executed|invoked)\s+([\w./\-]+)", re.I)
_NOT_A_COMMAND = frozenset({
    "the", "a", "an", "all", "it", "them", "this", "that", "these", "those",
    "tests", "test", "suite", "again", "both", "each", "everything", "some",
    "my", "our", "your", "into", "through", "over",
})

_FILE_RE = re.compile(
    r"\bI\s+(?:have\s+)?(created|wrote|written|added|updated|modified|"
    r"edited|deleted|removed)\s+(?:the\s+)?(?:file\s+)?"
    r"`?([\w./\-]+\.[A-Za-z0-9]{1,8})`?", re.I)

_WROTE_VERBS = {"created", "wrote", "written", "added", "updated",
                "modified", "edited"}


@dataclass(frozen=True)
class Claim:
    """One checkable proposition lifted out of a reply."""
    kind: str           # tests_pass | ran_command | file_written | file_deleted
    subject: str        # the command, path, or count the claim is about
    verdict: str
    evidence: str
    quote: str

    def to_dict(self) -> dict:
        return {"kind": self.kind, "subject": self.subject,
                "verdict": self.verdict, "evidence": self.evidence,
                "quote": self.quote[:200]}


@dataclass
class Attestation:
    claims: list[Claim]

    @property
    def contradicted(self) -> list[Claim]:
        return [c for c in self.claims if c.verdict == CONTRADICTED]

    @property
    def unsupported(self) -> list[Claim]:
        return [c for c in self.claims if c.verdict == UNSUPPORTED]

    @property
    def clean(self) -> bool:
        return not self.contradicted and not self.unsupported

    def report(self) -> str:
        if not self.claims:
            return "attest: the reply made no checkable claim"
        mark = {SUPPORTED: "✓", CONTRADICTED: "✗", UNSUPPORTED: "?"}
        lines = [f"attest: {len(self.claims)} claim(s) · "
                 f"{len(self.contradicted)} contradicted · "
                 f"{len(self.unsupported)} unsupported"]
        for c in self.claims:
            lines.append(f"  {mark[c.verdict]} {c.kind:<14} "
                         f"{c.subject[:40]:<42} {c.evidence}")
        return "\n".join(lines)


class Record:
    """What the log actually says, folded once per attestation."""

    def __init__(self, log: EventLog) -> None:
        self.commands: list[tuple[str, str]] = []   # (command, result)
        self.written: set[str] = set()
        self.deleted: set[str] = set()
        self.tool_calls: list[str] = []

        pending: dict = {}
        for ev in log.events():
            if ev.type == "tool.call":
                name = str(ev.data.get("name") or "")
                args = ev.data.get("args") or {}
                self.tool_calls.append(name)
                pending = {"name": name, "args": args}
                cmd = str(args.get("command") or "")
                if cmd:
                    self.commands.append((cmd, ""))
                for e in derive(name, args if isinstance(args, dict) else {}):
                    if e.kind == WRITE and e.path:
                        self.written.add(_tail(e.path))
                    elif e.kind == DELETE and e.path:
                        self.deleted.add(_tail(e.path))
            elif ev.type == "tool.result" and pending:
                result = str(ev.data.get("result") or "")
                cmd = str((pending.get("args") or {}).get("command") or "")
                if cmd and self.commands and self.commands[-1][0] == cmd:
                    self.commands[-1] = (cmd, result)
                pending = {}

    def test_runs(self) -> list[tuple[str, str]]:
        return [(c, r) for c, r in self.commands if _TEST_CMD_RE.search(c)]


def _tail(path: str) -> str:
    """Compare paths by their meaningful tail, so 'src/a.py' matches an
    absolute '/home/u/proj/src/a.py' without pretending to resolve either."""
    return path.replace("\\", "/").lstrip("./")


def _mentions(haystack: str, needle: str) -> bool:
    a, b = _tail(haystack), _tail(needle)
    return a.endswith(b) or b.endswith(a)


def _exit_ok(result: str) -> bool | None:
    """Whether a recorded command result shows success. None when the
    record does not say."""
    m = re.search(r"exit[_ ]?code[:= ]+(-?\d+)", result, re.I)
    if m:
        return int(m.group(1)) == 0
    if re.search(r"\b\d+\s+failed\b|\bFAILED\b|\bERROR\b", result):
        return False
    if re.search(r"\b\d+\s+passed\b|\bOK\b|\ball tests? pass", result, re.I):
        return True
    return None


def _count_reported(result: str) -> int | None:
    m = re.search(r"\b(\d+)\s+passed\b", result, re.I)
    return int(m.group(1)) if m else None


def attest(reply: str, log: EventLog) -> Attestation:
    """Check a reply's checkable claims against the sealed record."""
    rec = Record(log)
    claims: list[Claim] = []
    text = reply or ""

    # -- "the tests pass" ---------------------------------------------------
    for m in _PASS_RE.finditer(text):
        count = m.group(1)
        runs = rec.test_runs()
        if not runs:
            claims.append(Claim(
                "tests_pass", count or "tests", UNSUPPORTED,
                "no test command appears in this session's log", m.group(0)))
            continue
        cmd, result = runs[-1]
        ok = _exit_ok(result)
        if ok is False:
            claims.append(Claim("tests_pass", cmd, CONTRADICTED,
                                f"the run recorded a failure: {cmd}",
                                m.group(0)))
        elif ok is None:
            claims.append(Claim("tests_pass", cmd, UNSUPPORTED,
                                f"{cmd} ran but its result records no "
                                f"outcome", m.group(0)))
        elif count is not None:
            reported = _count_reported(result)
            if reported is not None and reported != int(count):
                claims.append(Claim(
                    "tests_pass", count, CONTRADICTED,
                    f"the run reported {reported} passing, not {count}",
                    m.group(0)))
            else:
                claims.append(Claim("tests_pass", cmd, SUPPORTED,
                                    f"{cmd} passed", m.group(0)))
        else:
            claims.append(Claim("tests_pass", cmd, SUPPORTED,
                                f"{cmd} passed", m.group(0)))

    for m in _FAIL_RE.finditer(text):
        runs = rec.test_runs()
        if runs and _exit_ok(runs[-1][1]) is True:
            claims.append(Claim("tests_pass", runs[-1][0], CONTRADICTED,
                                "the recorded run passed", m.group(0)))

    # -- "I ran X" ----------------------------------------------------------
    said_commands: list[tuple[str, str]] = [
        (m.group(1).strip(), m.group(0)) for m in _RAN_BACKTICK_RE.finditer(text)]
    spans = [m.span() for m in _RAN_BACKTICK_RE.finditer(text)]
    for m in _RAN_BARE_RE.finditer(text):
        if any(s <= m.start() < e for s, e in spans):
            continue                      # already read as a backticked claim
        token = m.group(1).strip()
        if token.lower() in _NOT_A_COMMAND:
            continue                      # prose, not a command claim
        said_commands.append((token, m.group(0)))

    for said, quote in said_commands:
        head = said.split()[0] if said.split() else said
        if any(_mentions(c, head) or head in c for c, _ in rec.commands):
            claims.append(Claim("ran_command", said, SUPPORTED,
                                "a matching command is in the log", quote))
        elif any(head == t for t in rec.tool_calls):
            claims.append(Claim("ran_command", said, SUPPORTED,
                                "a matching tool call is in the log", quote))
        else:
            claims.append(Claim("ran_command", said, CONTRADICTED,
                                "no such command or tool call was recorded",
                                quote))

    # -- "I created/updated/deleted <file>" ---------------------------------
    for m in _FILE_RE.finditer(text):
        verb, path = m.group(1).lower(), m.group(2)
        deleting = verb in ("deleted", "removed")
        pool = rec.deleted if deleting else rec.written
        kind = "file_deleted" if deleting else "file_written"
        if any(_mentions(p, path) for p in pool):
            claims.append(Claim(kind, path, SUPPORTED,
                                "a matching effect is in the log", m.group(0)))
        else:
            other = rec.written if deleting else rec.deleted
            if any(_mentions(p, path) for p in other):
                claims.append(Claim(
                    kind, path, CONTRADICTED,
                    "the log records the opposite effect on this path",
                    m.group(0)))
            else:
                claims.append(Claim(
                    kind, path, CONTRADICTED,
                    "no write or delete on this path was recorded",
                    m.group(0)))

    return Attestation(claims)


def seal(log: EventLog, att: Attestation) -> None:
    """Record the verdict. Always sealed, including a clean one — an
    attestation that only appears when something is wrong is evidence of
    absence nobody can audit."""
    log.append("attest.verdict",
               {"claims": [c.to_dict() for c in att.claims],
                "contradicted": len(att.contradicted),
                "unsupported": len(att.unsupported)},
               actor="kernel")


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        log = EventLog(Path(td) / "log.jsonl")

        # a session in which pytest ran and FAILED, and one file was written
        log.append("tool.call", {"name": "run_command",
                                 "args": {"command": "pytest -q"}})
        log.append("tool.result", {"result": "exit_code: 1\n2 failed, 3 passed"})
        log.append("tool.call", {"name": "write_file",
                                 "args": {"path": "src/parser.py",
                                          "content": "x = 1"}})
        log.append("tool.result", {"result": "OK wrote 5 bytes"})

        # -- the classic false summary -------------------------------------
        a = attest("I ran the tests and they pass. I created src/parser.py.",
                   log)
        kinds = {(c.kind, c.verdict) for c in a.claims}
        assert ("tests_pass", CONTRADICTED) in kinds, a.report()
        assert ("file_written", SUPPORTED) in kinds, a.report()
        assert not a.clean
        assert len(a.contradicted) == 1, a.report()
        # "ran the tests" is prose, not a command claim — reading it as a
        # command named "the tests and they pass" would invent a violation
        assert not any(c.kind == "ran_command" for c in a.claims), a.report()

        # a backticked command IS a command claim, and this one is real
        a = attest("I ran `pytest -q` first.", log)
        assert a.claims[0].kind == "ran_command"
        assert a.claims[0].verdict == SUPPORTED, a.report()

        # -- a claim about a file that was never touched -------------------
        a = attest("I updated src/never.py to fix the import.", log)
        assert a.contradicted and a.contradicted[0].subject == "src/never.py"

        # -- a command that was never run ----------------------------------
        a = attest("I ran `mypy src` to confirm the types.", log)
        assert a.contradicted[0].kind == "ran_command"

        # -- an honest reply attests clean ---------------------------------
        a = attest("The tests fail: 2 failed. I created src/parser.py.", log)
        assert a.clean, a.report()

        # -- a reply with nothing checkable in it --------------------------
        a = attest("Here is how the parser is structured, broadly.", log)
        assert a.claims == [] and a.clean

        # -- a passing run supports the claim ------------------------------
        log2 = EventLog(Path(td) / "log2.jsonl")
        log2.append("tool.call", {"name": "run_command",
                                  "args": {"command": "pytest -q"}})
        log2.append("tool.result", {"result": "exit_code: 0\n12 passed"})
        a = attest("All tests pass.", log2)
        assert a.clean and a.claims[0].verdict == SUPPORTED, a.report()

        # -- but an inflated count is caught -------------------------------
        a = attest("All 40 tests pass.", log2)
        assert a.contradicted, a.report()
        assert "12" in a.contradicted[0].evidence

        # -- claiming failure when the record passed is also a mismatch ----
        a = attest("The tests fail.", log2)
        assert a.contradicted, a.report()

        # -- no test run at all: unsupported, not contradicted -------------
        log3 = EventLog(Path(td) / "log3.jsonl")
        a = attest("The tests pass.", log3)
        assert a.unsupported and not a.contradicted, a.report()

        # -- a result with no recorded outcome is unsupported --------------
        log4 = EventLog(Path(td) / "log4.jsonl")
        log4.append("tool.call", {"name": "run_command",
                                  "args": {"command": "pytest -q"}})
        log4.append("tool.result", {"result": "(output truncated)"})
        a = attest("The tests pass.", log4)
        assert a.unsupported and not a.contradicted, a.report()

        # -- a shell-route write supports a file claim ---------------------
        log5 = EventLog(Path(td) / "log5.jsonl")
        log5.append("tool.call", {"name": "run_command",
                                  "args": {"command": "echo x > src/b.py"}})
        log5.append("tool.result", {"result": "exit_code: 0"})
        a = attest("I created src/b.py.", log5)
        assert a.claims[0].verdict == SUPPORTED, a.report()

        # -- the verdict is always sealed, clean or not --------------------
        seal(log, attest("Nothing checkable here.", log))
        assert any(e.type == "attest.verdict" for e in log.events())

    print("ATTEST SELF-TEST PASS")
