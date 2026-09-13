"""COVENANT — the specification as an enforced boundary, not as advice.

A system prompt cannot make a model comply. Text is probabilistic: every
"you MUST", every restated rule, every reminder re-injected into context is
a request the model is free to lose under load, length or distraction. The
longer the specification, the weaker each individual line's pull — a 150k
spec is exactly the case where prompt-level compliance fails worst.

So compliance is not asked for here. It is made structural:

    a clause the agent can violate in its output is advice.
    a clause the agent cannot violate in its EFFECT is a boundary.

This module moves the specification from the first category to the second.
Nothing here writes a single character into the prompt. The model is never
told to obey, never reminded, never nagged — the specification's text is
delivered once, verbatim, by systemprompt.py, and that is all. What this
module does is make non-compliant ACTIONS fail to commit.

Three mechanisms, all deterministic, none textual:

  1. ADDRESSING — the specification stops being a wall of text and becomes
     a namespace. parse_clauses() splits it into stable, content-hashed
     clauses with ids (§4.2, "no-secrets", …). A clause can now be cited,
     counted, and bound to — which is what makes 2 and 3 possible at all.

  2. BINDING — a clause becomes enforceable when it carries a machine-
     checkable rule. The author writes it directly in the spec:

         §4.2 Secrets never live in source.
         @enforce forbid_content: (?i)api[_-]?key\\s*=\\s*["'][A-Za-z0-9]

     The rule is authored by the human, in their own specification, next
     to the prose it enforces. Nothing is inferred from the prose and
     nothing is invented: a clause with no @enforce is unenforced, and
     says so, rather than being silently approximated.

  3. THE BOUNDARY — guards are evaluated against the PENDING tool call,
     before it runs. A violation returns a block reason to Agent._gate(),
     so the call never executes: no snapshot, no write, no side effect.
     The agent learns the rule the same way it learns any other refusal —
     from a real gate refusing a real action, exactly as OrphanAction and
     the dead-end ledger already work — not from a sentence added to its
     prompt.

Every evaluation is sealed to the event log ('covenant.blocked',
'covenant.cleared'), so adherence per clause is an auditable number rather
than an impression.

Guard kinds (all evaluated on the pending call, all deterministic):

    forbid_tool      tool name must not be used at all
    forbid_path      call must not touch paths matching these globs
    confine_paths    mutating calls must stay under these roots
    forbid_content   written content must not match this regex
    require_content  written content MUST match this regex (scoped by
                     `where`, a path glob — an unscoped require would fire
                     on every unrelated write)
    forbid_command   run_command's command string must not match this regex
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePath

from .kernel import EventLog

# tools whose arguments carry a filesystem path, and under which keys
_PATH_ARGS: dict[str, tuple[str, ...]] = {
    "write_file": ("path",), "edit_file": ("path",),
    "create_directory": ("path",), "delete_path": ("path",),
    "copy_path": ("src", "dst"), "move_path": ("src", "dst"),
}
# tools that write caller-supplied content, and under which keys
_CONTENT_ARGS: dict[str, tuple[str, ...]] = {
    "write_file": ("content",),
    "edit_file": ("new_string",),
}
_MUTATING = set(_PATH_ARGS)

_GUARD_KINDS = frozenset({
    "forbid_tool", "forbid_path", "confine_paths",
    "forbid_content", "require_content", "forbid_command",
})

# a clause header: "§4.2 Title", "4.2 Title", "## Title", "[no-secrets] Title"
_CLAUSE_RE = re.compile(
    r"^(?:\s{0,3})(?:"
    r"§\s*(?P<sec>[\d.]+[a-z]?)"          # §4.2
    r"|\[(?P<tag>[A-Za-z0-9_.\-]+)\]"     # [no-secrets]
    r"|(?P<hashes>\#{1,6})\s+"            # ## Heading
    r")\s*(?P<title>.*)$"
)
_ENFORCE_RE = re.compile(r"^\s*@enforce\s+(?P<rest>.+)$", re.I)


@dataclass(frozen=True)
class Guard:
    """One deterministic constraint on a pending tool call."""
    clause: str                  # clause id this guard belongs to
    kind: str
    value: str = ""              # regex / glob / tool name, per kind
    roots: tuple[str, ...] = ()  # confine_paths
    globs: tuple[str, ...] = ()  # forbid_path
    where: str = ""              # require_content scope (path glob)

    def to_dict(self) -> dict:
        d = {"clause": self.clause, "kind": self.kind}
        if self.value:
            d["value"] = self.value
        if self.roots:
            d["roots"] = list(self.roots)
        if self.globs:
            d["globs"] = list(self.globs)
        if self.where:
            d["where"] = self.where
        return d


@dataclass
class Clause:
    """One addressable unit of the specification."""
    id: str
    title: str
    body: str
    line: int
    guards: list[Guard] = field(default_factory=list)

    @property
    def fingerprint(self) -> str:
        """Content address — changes the moment the clause's text changes."""
        return hashlib.sha256(
            (self.id + "\x00" + self.title + "\x00" + self.body)
            .encode("utf-8")).hexdigest()[:16]

    @property
    def enforced(self) -> bool:
        return bool(self.guards)


@dataclass(frozen=True)
class Violation:
    """A pending call's collision with one clause."""
    clause: str
    kind: str
    detail: str

    def to_dict(self) -> dict:
        return {"clause": self.clause, "kind": self.kind,
                "detail": self.detail}


# ---------------------------------------------------------------------------
# Parsing — specification text -> addressable clauses
# ---------------------------------------------------------------------------


def _parse_guard(clause_id: str, rest: str) -> tuple[Guard | None, str]:
    """Parse one @enforce line. Returns (guard, error). A malformed rule is
    reported, never guessed at and never silently dropped — an enforcement
    rule that quietly does nothing is worse than no rule, because the
    author believes they are covered."""
    rest = rest.strip()
    if rest.startswith("{"):
        try:
            spec = json.loads(rest)
        except ValueError as e:
            return None, f"{clause_id}: malformed @enforce JSON ({e})"
        if not isinstance(spec, dict):
            return None, f"{clause_id}: @enforce JSON must be an object"
        kind = str(spec.get("kind", "")).strip()
        value = str(spec.get("value", "") or spec.get("pattern", "")).strip()
        roots = tuple(str(r) for r in spec.get("roots", []) or ())
        globs = tuple(str(g) for g in spec.get("globs", []) or ())
        where = str(spec.get("where", "")).strip()
    else:
        head, _, tail = rest.partition(":")
        kind, value = head.strip(), tail.strip()
        roots = globs = ()
        where = ""
        if kind in ("confine_paths", "forbid_path"):
            parts = tuple(p.strip() for p in value.split(",") if p.strip())
            if kind == "confine_paths":
                roots, value = parts, ""
            else:
                globs, value = parts, ""

    if kind not in _GUARD_KINDS:
        return None, (f"{clause_id}: unknown @enforce kind {kind!r} — "
                      f"known: {', '.join(sorted(_GUARD_KINDS))}")
    if kind in ("forbid_content", "require_content", "forbid_command"):
        if not value:
            return None, f"{clause_id}: {kind} needs a regex"
        try:
            re.compile(value)
        except re.error as e:
            return None, f"{clause_id}: {kind} regex is invalid ({e})"
    if kind == "require_content" and not where:
        # an unscoped require_content would block every unrelated write
        return None, (f"{clause_id}: require_content needs `where` "
                      f"(a path glob) so it scopes to the files it means")
    if kind == "forbid_tool" and not value:
        return None, f"{clause_id}: forbid_tool needs a tool name"
    if kind == "confine_paths" and not roots:
        return None, f"{clause_id}: confine_paths needs at least one root"
    if kind == "forbid_path" and not globs:
        return None, f"{clause_id}: forbid_path needs at least one glob"

    return Guard(clause=clause_id, kind=kind, value=value,
                 roots=roots, globs=globs, where=where), ""


def parse_clauses(spec: str) -> tuple[list[Clause], list[str]]:
    """Split a specification into addressable clauses. Returns
    (clauses, errors). Text before the first header becomes the preamble
    clause so no byte of the specification is unaddressable."""
    clauses: list[Clause] = []
    errors: list[str] = []
    cur: Clause | None = None
    buf: list[str] = []
    seen: dict[str, int] = {}

    def _flush() -> None:
        if cur is not None:
            cur.body = "\n".join(buf).strip()
            clauses.append(cur)

    lines = spec.splitlines()
    n = 0
    while n < len(lines):
        line = lines[n]
        n += 1
        m = _CLAUSE_RE.match(line)
        if m and (m.group("sec") or m.group("tag") or m.group("title")):
            _flush()
            raw = m.group("sec") or m.group("tag") or ""
            title = (m.group("title") or "").strip()
            if not raw:
                # a markdown heading: slugify its title into an id
                raw = re.sub(r"[^a-z0-9]+", "-",
                             title.lower()).strip("-") or f"clause-{n}"
            # ids must be unique to be citable
            if raw in seen:
                seen[raw] += 1
                raw = f"{raw}#{seen[raw]}"
            else:
                seen[raw] = 1
            cur = Clause(id=raw, title=title, body="", line=n)
            buf = []
            continue
        if cur is None:
            cur = Clause(id="preamble", title="preamble", body="", line=1)
            seen["preamble"] = 1
            buf = []
        buf.append(line)
        em = _ENFORCE_RE.match(line)
        if em:
            rest = em.group("rest").strip()
            # a JSON rule may span lines — long regexes need the room.
            # Consume until the braces balance (or the clause ends), so an
            # unterminated block reports as malformed instead of eating the
            # rest of the specification.
            if rest.startswith("{") and rest.count("{") > rest.count("}"):
                while n < len(lines):
                    nxt = lines[n]
                    if _CLAUSE_RE.match(nxt) or _ENFORCE_RE.match(nxt):
                        break
                    n += 1
                    buf.append(nxt)
                    rest += "\n" + nxt.strip()
                    if rest.count("{") <= rest.count("}"):
                        break
            guard, err = _parse_guard(cur.id, rest)
            if guard is not None:
                cur.guards.append(guard)
            else:
                errors.append(err)
    _flush()
    return clauses, errors


# ---------------------------------------------------------------------------
# Evaluation — guards against a pending call
# ---------------------------------------------------------------------------


def _norm(path: str) -> str:
    """Posix-normalised path for glob matching; keeps matching stable
    across platforms and collapses '..' so a traversal cannot slip a
    confine_paths root."""
    try:
        p = PurePath(Path(path).expanduser())
    except (OSError, ValueError):
        return str(path)
    parts: list[str] = []
    for part in p.parts:
        if part == "..":
            if parts:
                parts.pop()
            continue
        if part == ".":
            continue
        parts.append(part)
    return "/".join(parts)


def _matches_glob(path: str, pattern: str) -> bool:
    norm = _norm(path)
    pat = pattern.rstrip("/")
    if fnmatch.fnmatch(norm, pat) or fnmatch.fnmatch(norm, pat + "/*"):
        return True
    # a bare directory name confines/forbids everything beneath it
    return any(fnmatch.fnmatch(seg, pat) for seg in norm.split("/"))


def _under_root(path: str, root: str) -> bool:
    norm, r = _norm(path), _norm(root).rstrip("/")
    return norm == r or norm.startswith(r + "/") if r else True


def call_paths(tool: str, args: dict) -> list[str]:
    return [str(args[k]) for k in _PATH_ARGS.get(tool, ()) if args.get(k)]


def call_content(tool: str, args: dict) -> str:
    return "\n".join(str(args.get(k) or "")
                     for k in _CONTENT_ARGS.get(tool, ()))


def evaluate(guards: list[Guard], tool: str, args: dict) -> list[Violation]:
    """Every guard this pending call collides with. Pure and deterministic:
    same call, same guards, same verdict — always."""
    out: list[Violation] = []
    paths = call_paths(tool, args)
    content = call_content(tool, args)
    command = str(args.get("command") or "") if tool in (
        "run_command", "bg_shell", "shell") else ""

    for g in guards:
        if g.kind == "forbid_tool":
            if tool == g.value:
                out.append(Violation(g.clause, g.kind,
                                     f"tool {tool!r} is forbidden"))
        elif g.kind == "forbid_path":
            for p in paths:
                hit = next((x for x in g.globs if _matches_glob(p, x)), None)
                if hit:
                    out.append(Violation(g.clause, g.kind,
                                         f"path {p!r} matches forbidden "
                                         f"pattern {hit!r}"))
        elif g.kind == "confine_paths":
            if tool in _MUTATING:
                for p in paths:
                    if not any(_under_root(p, r) for r in g.roots):
                        out.append(Violation(
                            g.clause, g.kind,
                            f"path {p!r} is outside the permitted roots "
                            f"{list(g.roots)}"))
        elif g.kind == "forbid_content":
            if content:
                m = re.search(g.value, content)
                if m:
                    out.append(Violation(
                        g.clause, g.kind,
                        f"content matches forbidden pattern at offset "
                        f"{m.start()}: {m.group(0)[:60]!r}"))
        elif g.kind == "require_content":
            if tool in _CONTENT_ARGS and content:
                scoped = [p for p in paths if _matches_glob(p, g.where)]
                if scoped and not re.search(g.value, content):
                    out.append(Violation(
                        g.clause, g.kind,
                        f"{scoped[0]!r} must contain a match for "
                        f"{g.value!r} and does not"))
        elif g.kind == "forbid_command":
            if command:
                m = re.search(g.value, command)
                if m:
                    out.append(Violation(
                        g.clause, g.kind,
                        f"command matches forbidden pattern: "
                        f"{m.group(0)[:60]!r}"))
    return out


# ---------------------------------------------------------------------------
# Covenant — the bound specification
# ---------------------------------------------------------------------------


class Covenant:
    """The specification, parsed into clauses and bound to the action
    boundary. Holds no prompt text and never contributes any."""

    def __init__(self, log: EventLog, spec: str = "") -> None:
        self.log = log
        self.clauses: list[Clause] = []
        self.errors: list[str] = []
        self.blocked = 0
        self.cleared = 0
        self._hits: dict[str, int] = {}
        self.bind(spec)

    # -- binding ------------------------------------------------------------

    def bind(self, spec: str) -> None:
        """(Re)parse a specification. Safe to call on every reload."""
        self.clauses, self.errors = parse_clauses(spec or "")
        self._by_id = {c.id: c for c in self.clauses}

    @property
    def guards(self) -> list[Guard]:
        return [g for c in self.clauses for g in c.guards]

    @property
    def enforced_clauses(self) -> list[Clause]:
        return [c for c in self.clauses if c.enforced]

    # -- the boundary -------------------------------------------------------

    def check(self, tool: str, args: dict) -> list[Violation]:
        """Evaluate the pending call. Returns the violations; the caller
        (Agent._gate) turns a non-empty list into a refusal."""
        return evaluate(self.guards, tool, args)

    def gate(self, tool: str, args: dict) -> str | None:
        """Block reason for a pending call, or None to let it proceed.

        Shaped for Agent._gate(): a returned string blocks the call before
        it executes — no snapshot, no write, no side effect. The citation
        names the clause so the refusal is traceable to the specification
        rather than to a rule invented here.
        """
        violations = self.check(tool, args)
        if not violations:
            if self.guards:
                self.cleared += 1
            return None
        self.blocked += 1
        for v in violations:
            self._hits[v.clause] = self._hits.get(v.clause, 0) + 1
        self.log.append("covenant.blocked",
                        {"tool": tool,
                         "violations": [v.to_dict() for v in violations]},
                        actor="kernel")
        lines = [f"CovenantViolation: this action is refused by the "
                 f"specification ({len(violations)} clause"
                 f"{'s' if len(violations) > 1 else ''})."]
        for v in violations:
            clause = self._by_id.get(v.clause)
            title = f" — {clause.title}" if clause and clause.title else ""
            lines.append(f"  {v.clause}{title}: {v.detail}")
        return "\n".join(lines)

    # -- observation --------------------------------------------------------

    def stats(self) -> dict:
        return {
            "clauses": len(self.clauses),
            "enforced": len(self.enforced_clauses),
            "guards": len(self.guards),
            "errors": len(self.errors),
            "blocked": self.blocked,
            "cleared": self.cleared,
        }

    def report(self) -> str:
        """Human-readable adherence report — what is bound, what is not,
        and which clauses actually caught something."""
        s = self.stats()
        if not self.clauses:
            return "covenant: no specification bound"
        lines = [
            f"covenant: {s['clauses']:,} clauses · {s['enforced']} enforced "
            f"· {s['guards']} guards · {s['blocked']} blocked / "
            f"{s['cleared']} cleared"
        ]
        for c in self.enforced_clauses:
            hits = self._hits.get(c.id, 0)
            kinds = ",".join(sorted({g.kind for g in c.guards}))
            mark = "●" if hits else "○"
            lines.append(f"  {mark} {c.id:<16} {kinds:<32} "
                         f"{hits} block{'' if hits == 1 else 's'}")
        unenforced = len(self.clauses) - len(self.enforced_clauses)
        if unenforced:
            lines.append(f"  {unenforced:,} clause(s) carry no @enforce rule "
                         f"— prose only, not bound to the boundary")
        for e in self.errors:
            lines.append(f"  !! {e}")
        return "\n".join(lines)


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        log = EventLog(Path(td) / "log.jsonl")

        spec = '''
Preamble text that belongs to no numbered clause.

§1 Source layout
Application code lives under src/ and tests under tests/.
@enforce confine_paths: src, tests

§2 Secrets never appear in source
@enforce forbid_content: (?i)api[_-]?key\\s*=\\s*["\\'][A-Za-z0-9]

§3 Destructive shell forms are never used
@enforce forbid_command: rm\\s+-rf\\s+/

§4 Deleting files is not this agent's job
@enforce forbid_tool: delete_path

§5 Python modules carry a docstring
@enforce {"kind": "require_content", "value": "^\\\\s*[\\"']{3}",
          "where": "*.py"}

§6 A prose-only clause with no machine-checkable rule.
It is documentation, and the report says so rather than pretending.
'''
        cov = Covenant(log, spec)

        # 1. addressing: every clause is citable, nothing is unaddressable
        ids = [c.id for c in cov.clauses]
        assert ids == ["preamble", "1", "2", "3", "4", "5", "6"], ids
        assert not cov.errors, cov.errors
        assert len(cov.enforced_clauses) == 5
        assert cov.clauses[1].title == "Source layout"

        # fingerprints are content addresses — editing a clause changes it
        fp = cov.clauses[1].fingerprint
        cov2 = Covenant(log, spec.replace("src/ and tests", "lib/ and tests"))
        assert cov2.clauses[1].fingerprint != fp

        # 2. the boundary refuses; it does not advise
        # §1 confine_paths
        assert cov.gate("write_file", {"path": "src/app.py",
                                       "content": '"""ok."""'}) is None
        blocked = cov.gate("write_file", {"path": "/etc/passwd",
                                          "content": '"""x."""'})
        assert blocked and "CovenantViolation" in blocked and "1" in blocked

        # traversal cannot slip the root
        assert cov.gate("write_file", {"path": "src/../../etc/x.py",
                                       "content": '"""x."""'})

        # §2 forbid_content
        leak = cov.gate("write_file",
                        {"path": "src/c.py",
                         "content": '"""d."""\nAPI_KEY = "sk-abc123"'})
        assert leak and "2" in leak, leak

        # §3 forbid_command
        assert cov.gate("run_command", {"command": "rm -rf /"})
        assert cov.gate("run_command", {"command": "ls -la"}) is None

        # §4 forbid_tool
        assert cov.gate("delete_path", {"path": "src/a.py"})

        # §5 require_content, scoped: .py needs a docstring, .md does not
        assert cov.gate("write_file", {"path": "src/no_doc.py",
                                       "content": "x = 1"})
        assert cov.gate("write_file", {"path": "src/doc.py",
                                       "content": '"""has one."""'}) is None
        # (inside the confined roots, so only §5's scope is under test)
        assert cov.gate("write_file", {"path": "src/README.md",
                                       "content": "no docstring here"}) is None
        # and §1 independently refuses a path outside the roots
        assert cov.gate("write_file", {"path": "README.md",
                                       "content": "x"})

        # 3. determinism: the same call always gets the same verdict
        call = ("write_file", {"path": "/etc/passwd", "content": "x"})
        assert cov.check(*call) == cov.check(*call)

        # 4. a violation is sealed, and never silently swallowed
        events = [e for e in log.events() if e.type == "covenant.blocked"]
        assert len(events) == cov.blocked and cov.blocked >= 6
        assert events[0].data["violations"][0]["clause"]

        # 5. malformed rules are reported, never guessed at
        bad = Covenant(log, "§9 x\n@enforce nonsense: y\n"
                            "§10 y\n@enforce forbid_content: [unclosed\n"
                            "§11 z\n@enforce require_content: x\n")
        assert len(bad.errors) == 3, bad.errors
        assert any("unknown @enforce kind" in e for e in bad.errors)
        assert any("invalid" in e for e in bad.errors)
        assert any("needs `where`" in e for e in bad.errors)
        # and a clause whose rule failed to parse is NOT reported as enforced
        assert bad.enforced_clauses == []

        # 6. an empty specification binds cleanly and gates nothing
        empty = Covenant(log, "")
        assert empty.gate("delete_path", {"path": "anything"}) is None
        assert "no specification bound" in empty.report()

        # 7. the report distinguishes bound clauses from prose
        rep = cov.report()
        # preamble and §6 carry prose only
        assert "2 clause(s) carry no @enforce rule" in rep
        assert "blocked" in rep

    print("COVENANT SELF-TEST PASS")
