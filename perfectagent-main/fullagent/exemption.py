"""EXEMPTION — the "except" that every real specification contains.

Every guard built so far is absolute. `confine_paths: src, tests` means
every write, without exception, forever. No real specification is shaped
like that. They all read:

    writes stay under src/ and tests/ — except the changelog
    never delete — except build artefacts
    no secrets in source — except the fixtures that test secret detection

A boundary with no way to say "except" forces the author into one of two
failures, and both end with the specification not being followed:

  * DROP THE CLAUSE. The exception is real and the rule cannot express it,
    so the whole rule comes out. One legitimate exception removes all the
    enforcement the clause was carrying.
  * WORK AROUND IT. The clause stays, and the agent is refused on
    legitimate work, so the operator raises autonomy, disables the rule for
    a session, or edits the spec under pressure. The rule survives on paper
    while being routinely bypassed in practice.

The second is worse, because the enforcement report still shows the clause
as bound. An unusable rule is abandoned in fact and enforced on paper.

So exceptions are first-class, written next to the rule they narrow, and
they are as explicit and auditable as the rule itself:

    §1 Writes stay under src/ and tests/.
    @enforce confine_paths: src, tests
    @except path CHANGELOG.md
    @except path docs/**

Three properties make this safe rather than a hole:

  1. SCOPED TO ONE CLAUSE. An @except narrows the clause it appears under
     and nothing else. It cannot accidentally widen a different rule, and a
     path exempted from §1 is still judged by §2.
  2. NARROWING ONLY. An exemption can forgive a violation; it can never
     create permission on its own. Remove every guard and the exemptions
     do nothing at all.
  3. RECORDED. Every forgiveness is sealed as 'exemption.applied' with the
     clause and the path, so an exception that is load-bearing in practice
     is visible as a number rather than as a line nobody re-reads.

Exemption kinds:

    @except path <glob>          a write/delete to this path is forgiven
    @except tool <name>          this tool is forgiven under this clause
    @except content <regex>      content matching this is forgiven
    @except when <glob> <regex>  content forgiven only for matching paths
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from pathlib import PurePath

from .kernel import EventLog

_EXCEPT_RE = re.compile(
    r"^\s*@except\s+(?P<kind>path|tool|content|when)\s+(?P<rest>.+?)\s*$",
    re.I)

_KINDS = frozenset({"path", "tool", "content", "when"})


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
    norm, pat = _norm(path), pattern.rstrip("/")
    if fnmatch.fnmatch(norm, pat) or fnmatch.fnmatch(norm, pat + "/*"):
        return True
    if "**" in pat:
        flat = pat.replace("**/", "").replace("/**", "")
        if fnmatch.fnmatch(norm, flat) or norm.startswith(flat.rstrip("*")):
            return True
    return any(fnmatch.fnmatch(seg, pat) for seg in norm.split("/"))


@dataclass(frozen=True)
class Exemption:
    """One narrowing of one clause."""
    clause: str
    kind: str
    value: str = ""
    where: str = ""      # `when` only: the path glob the regex is scoped to

    def to_dict(self) -> dict:
        d = {"clause": self.clause, "kind": self.kind, "value": self.value}
        if self.where:
            d["where"] = self.where
        return d

    def forgives(self, violation, tool: str = "",
                 effects: list | None = None) -> bool:
        """Whether this exemption forgives `violation`. Never consulted for
        a violation of a different clause — scoping is structural, not a
        check that could be forgotten."""
        if violation.clause != self.clause:
            return False
        if self.kind == "path":
            return bool(violation.path) and _glob(violation.path, self.value)
        if self.kind == "tool":
            return tool == self.value
        if self.kind == "content":
            for e in effects or ():
                if e.path and violation.path and \
                        _norm(e.path) == _norm(violation.path) and e.content:
                    try:
                        return re.search(self.value, e.content) is not None
                    except re.error:
                        return False
            return False
        if self.kind == "when":
            if not violation.path or not _glob(violation.path, self.where):
                return False
            for e in effects or ():
                if e.path and _norm(e.path) == _norm(violation.path):
                    try:
                        return re.search(self.value, e.content or "") \
                            is not None
                    except re.error:
                        return False
            return False
        return False


def parse_exemptions(spec: str) -> tuple[list[Exemption], list[str]]:
    """Read @except lines, each bound to the clause it sits under."""
    out: list[Exemption] = []
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
        if not re.match(r"^\s*@except\b", line, re.I):
            continue
        m = _EXCEPT_RE.match(line)
        if not m:
            errors.append(f"{clause}: malformed @except — expected "
                          f"'@except path <glob>', 'tool <name>', "
                          f"'content <regex>' or 'when <glob> <regex>'")
            continue
        kind = m.group("kind").lower()
        rest = m.group("rest").strip()
        where = ""
        if kind == "when":
            bits = rest.split(None, 1)
            if len(bits) != 2:
                errors.append(f"{clause}: '@except when' needs a path glob "
                              f"and a regex")
                continue
            where, rest = bits[0], bits[1]
        if kind in ("content", "when"):
            try:
                re.compile(rest)
            except re.error as e:
                errors.append(f"{clause}: invalid @except regex ({e})")
                continue
        if not rest:
            errors.append(f"{clause}: @except {kind} needs a value")
            continue
        out.append(Exemption(clause=clause, kind=kind, value=rest,
                             where=where))
    return out, errors


class Exemptions:
    """The narrowings in force, and the record of what they forgave."""

    def __init__(self, log: EventLog, spec: str = "") -> None:
        self.log = log
        self.items: list[Exemption] = []
        self.errors: list[str] = []
        self.applied = 0
        self._hits: dict[str, int] = {}
        self.bind(spec)

    def bind(self, spec: str) -> None:
        self.items, self.errors = parse_exemptions(spec or "")

    def narrow(self, violations: list, tool: str = "",
               effects: list | None = None) -> list:
        """Return the violations that survive. Narrowing only: a call with
        no violations cannot gain permission here, because there is nothing
        to forgive."""
        if not self.items or not violations:
            return violations
        kept = []
        for v in violations:
            hit = next((x for x in self.items
                        if x.forgives(v, tool, effects)), None)
            if hit is None:
                kept.append(v)
                continue
            self.applied += 1
            key = f"{hit.clause}:{hit.kind}"
            self._hits[key] = self._hits.get(key, 0) + 1
            self.log.append("exemption.applied",
                            {**hit.to_dict(), "forgave": v.to_dict(),
                             "tool": tool},
                            actor="kernel")
        return kept

    def report(self) -> str:
        if not self.items:
            return "exemptions: none declared"
        lines = [f"exemptions: {len(self.items)} declared · "
                 f"{self.applied} applied"]
        for x in self.items:
            key = f"{x.clause}:{x.kind}"
            n = self._hits.get(key, 0)
            mark = "●" if n else "○"
            scope = f" in {x.where}" if x.where else ""
            lines.append(f"  {mark} {x.clause:<10} except {x.kind} "
                         f"{x.value[:34]}{scope} — forgave {n}")
        for e in self.errors:
            lines.append(f"  !! {e}")
        return "\n".join(lines)


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    from .covenant import Covenant

    with tempfile.TemporaryDirectory() as td:
        log = EventLog(Path(td) / "log.jsonl")

        spec = '''§1 Writes stay under src/ and tests/
@enforce confine_paths: src, tests
@except path CHANGELOG.md
@except path docs/**

§2 No secrets in source
@enforce forbid_content: (?i)api[_-]?key\\s*=\\s*["\\'][A-Za-z0-9]
@except when tests/fixtures/* SECRET_DETECTION_FIXTURE

§3 Nothing is ever deleted
@enforce forbid_effect: delete
@except tool delete_path
'''
        cov = Covenant(log, spec)
        ex = Exemptions(log, spec)
        assert len(ex.items) == 4 and not ex.errors, (ex.items, ex.errors)

        def judge(tool, args):
            from .effects import derive
            v = cov.check(tool, args)
            return ex.narrow(v, tool, derive(tool, args))

        # -- the rule still holds where no exception applies ---------------
        assert judge("write_file", {"path": "/etc/passwd", "content": "x"})
        assert judge("run_command", {"command": "echo x > /etc/y"})

        # -- and the declared exceptions are forgiven ----------------------
        assert not judge("write_file", {"path": "CHANGELOG.md",
                                        "content": "## 1.0"})
        assert not judge("write_file", {"path": "docs/guide.md",
                                        "content": "hi"})
        assert not judge("write_file", {"path": "docs/deep/nested.md",
                                        "content": "hi"})
        # by any route, because exemptions match effects like guards do
        assert not judge("run_command", {"command": "echo x > CHANGELOG.md"})

        # -- an exemption is scoped to ITS clause, never to another --------
        # a secret in CHANGELOG.md: §1 forgives the path, §2 still refuses
        left = judge("write_file", {"path": "CHANGELOG.md",
                                    "content": 'API_KEY = "sk-abc1"'})
        assert {v.clause for v in left} == {"2"}, left

        # -- `when` scopes content forgiveness to matching paths ----------
        fixture = {"path": "tests/fixtures/leak.py",
                   "content": 'SECRET_DETECTION_FIXTURE\nAPI_KEY = "sk-a1"'}
        assert not judge("write_file", fixture)
        # the same content outside the fixture directory is still refused
        elsewhere = {"path": "src/leak.py",
                     "content": 'SECRET_DETECTION_FIXTURE\nAPI_KEY = "sk-a1"'}
        assert judge("write_file", elsewhere)
        # and inside the directory WITHOUT the marker it is still refused
        unmarked = {"path": "tests/fixtures/other.py",
                    "content": 'API_KEY = "sk-a1"'}
        assert judge("write_file", unmarked)

        # -- tool exemptions ----------------------------------------------
        assert not judge("delete_path", {"path": "src/a.py"})
        assert judge("run_command", {"command": "rm -f src/a.py"})

        # -- NARROWING ONLY: exemptions never create permission ------------
        naked = Exemptions(log, "§9 x\n@except path anything/*\n")
        assert naked.narrow([], "write_file", []) == []
        bare = Covenant(log, "§9 x\n@except path anything/*\n")
        assert bare.guards == []
        assert naked.narrow(bare.check("write_file",
                                       {"path": "/etc/x", "content": "y"}),
                            "write_file", []) == []

        # -- every forgiveness is sealed -----------------------------------
        events = [e for e in log.events() if e.type == "exemption.applied"]
        assert len(events) == ex.applied and ex.applied >= 5
        assert events[0].data["clause"] and events[0].data["forgave"]

        # -- the report shows which exceptions are load-bearing ------------
        rep = ex.report()
        assert "forgave" in rep and "●" in rep

        # -- malformed exceptions are reported, never guessed at -----------
        bad = Exemptions(log, "§9 x\n@except sideways foo\n"
                              "§10 y\n@except content [unclosed\n"
                              "§11 z\n@except when onlyoneword\n")
        assert len(bad.errors) == 3, bad.errors
        assert bad.items == []

    print("EXEMPTION SELF-TEST PASS")
