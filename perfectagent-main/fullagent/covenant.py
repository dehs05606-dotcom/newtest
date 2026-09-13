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

Guards bind to EFFECTS, not to tool names (see effects.py). `write_file`
with path "/etc/x" and `run_command` with "echo boom > /etc/x" are the same
act, and a rule that refuses one while permitting the other constrains only
the agent's vocabulary. Every call is reduced to what it DOES — writes,
deletes, execs — and the guards judge that, so a clause written once holds
across every route to the same effect. Where a command's effects cannot be
determined before it runs, a containment clause refuses it rather than
assuming the best: an unprovable claim is not a passing one.

Guard kinds (all evaluated on the pending call, all deterministic):

    forbid_tool      this tool must not be used (names a tool, not an act)
    forbid_effect    no effect of this kind, by any route: write | delete |
                     exec | opaque
    forbid_path      no write or delete may land on these globs
    confine_paths    every write and delete must land under these roots
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
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePath

from .effects import (DELETE, EXEC, NAMED_TOOLS, OPAQUE, WRITE, Effect,
                      derive)
from .kernel import EventLog

_EFFECT_KINDS = frozenset({WRITE, DELETE, EXEC, OPAQUE})

_GUARD_KINDS = frozenset({
    "forbid_tool", "forbid_path", "confine_paths",
    "forbid_content", "require_content", "forbid_command",
    "forbid_effect",
})

# guards that make a claim about WHERE effects may land. An effect whose
# location cannot be determined before it runs (see effects.OPAQUE) cannot
# satisfy such a claim, so these refuse it rather than assuming the best.
_CONTAINMENT = frozenset({"confine_paths", "forbid_path"})

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
    if kind == "forbid_effect":
        if value not in _EFFECT_KINDS:
            return None, (f"{clause_id}: forbid_effect must be one of "
                          f"{', '.join(sorted(_EFFECT_KINDS))}")
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


def _via(effect: Effect) -> str:
    """How this effect was reached — named in the citation so a refusal on
    a shell route reads as clearly as one on a direct call."""
    return f" (via {effect.reason})" if effect.reason else ""


def evaluate(guards: list[Guard], tool: str, args: dict) -> list[Violation]:
    """Every guard this pending call collides with.

    Guards are matched against the call's EFFECTS, not its tool name, so
    the same act is judged identically however it is spelled. Pure and
    deterministic: same call, same guards, same verdict — always.
    """
    return evaluate_effects(guards, derive(tool, args), tool=tool,
                            command=str(args.get("command") or ""))


def evaluate_effects(guards: list[Guard], effects: list[Effect],
                     tool: str = "", command: str = "") -> list[Violation]:
    """Judge effects directly.

    evaluate() derives effects from a pending call — an intention. Effects
    can also be observed AFTER the fact, from what actually changed on
    disk (see sentinel.py), and the same clauses must judge both. Keeping
    the rule in one place is what makes an intended write and a realised
    one impossible to judge differently.
    """
    out: list[Violation] = []
    mutations = [e for e in effects if e.kind in (WRITE, DELETE)]
    opaque = [e for e in effects if e.kind == OPAQUE]

    for g in guards:
        if g.kind == "forbid_tool":
            if tool == g.value:
                out.append(Violation(g.clause, g.kind,
                                     f"tool {tool!r} is forbidden"))

        elif g.kind == "forbid_effect":
            for e in effects:
                if e.kind == g.value:
                    where = f" on {e.path!r}" if e.path else ""
                    out.append(Violation(
                        g.clause, g.kind,
                        f"{e.kind} effect{where} is forbidden{_via(e)}"))

        elif g.kind == "forbid_path":
            for e in mutations:
                hit = next((x for x in g.globs
                            if e.path and _matches_glob(e.path, x)), None)
                if hit:
                    out.append(Violation(
                        g.clause, g.kind,
                        f"{e.kind} to {e.path!r} matches forbidden pattern "
                        f"{hit!r}{_via(e)}"))
            for e in opaque:
                out.append(Violation(
                    g.clause, g.kind,
                    f"effects cannot be determined before running, so this "
                    f"call cannot be shown to avoid {list(g.globs)} — "
                    f"{e.reason}"))

        elif g.kind == "confine_paths":
            for e in mutations:
                if e.path and not any(_under_root(e.path, r)
                                      for r in g.roots):
                    out.append(Violation(
                        g.clause, g.kind,
                        f"{e.kind} to {e.path!r} is outside the permitted "
                        f"roots {list(g.roots)}{_via(e)}"))
            for e in opaque:
                out.append(Violation(
                    g.clause, g.kind,
                    f"effects cannot be determined before running, so this "
                    f"call cannot be shown to stay under {list(g.roots)} — "
                    f"{e.reason}"))

        elif g.kind == "forbid_content":
            for e in mutations:
                if not e.content:
                    continue
                m = re.search(g.value, e.content)
                if m:
                    out.append(Violation(
                        g.clause, g.kind,
                        f"content written to {e.path!r} matches forbidden "
                        f"pattern: {m.group(0)[:60]!r}{_via(e)}"))

        elif g.kind == "require_content":
            for e in mutations:
                if e.kind != WRITE or not e.content:
                    continue
                if e.path and _matches_glob(e.path, g.where) \
                        and not re.search(g.value, e.content):
                    out.append(Violation(
                        g.clause, g.kind,
                        f"{e.path!r} must contain a match for {g.value!r} "
                        f"and does not{_via(e)}"))

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

    def check_effects(self, effects: list[Effect]) -> list[Violation]:
        """Evaluate effects observed rather than intended — the same
        clauses, applied to what actually happened."""
        return evaluate_effects(self.guards, effects)

    def cite(self, violations: list[Violation]) -> str:
        """The refusal text — every clause that refused, by id and title."""
        lines = [f"CovenantViolation: this action is refused by the "
                 f"specification ({len(violations)} clause"
                 f"{'s' if len(violations) > 1 else ''})."]
        for v in violations:
            clause = self._by_id.get(v.clause)
            title = f" — {clause.title}" if clause and clause.title else ""
            lines.append(f"  {v.clause}{title}: {v.detail}")
        return "\n".join(lines)

    def _record(self, event: str, tool: str,
                violations: list[Violation]) -> None:
        self.blocked += 1
        for v in violations:
            self._hits[v.clause] = self._hits.get(v.clause, 0) + 1
        self.log.append(event,
                        {"tool": tool,
                         "violations": [v.to_dict() for v in violations]},
                        actor="kernel")

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
        self._record("covenant.blocked", tool, violations)
        return self.cite(violations)

    # -- arming: the boundary as the only route to a handler ---------------

    def arm(self, registry: dict) -> dict:
        """Return `registry` with every handler wrapped in the boundary.

        Calling the gate from each tool loop is a convention, and a
        convention is only as good as every future executor remembering
        it — crew.py already ran its subagents' tools by calling
        `tool.handler(**args)` directly, so the specification bound the
        sovereign agent and nothing else.

        Arming removes the thing that has to be remembered: the unguarded
        handler is no longer reachable from the registry, so any executor —
        this one, a subagent, one written later — passes the boundary
        because there is no other way to invoke the tool.

        A call refused here ALSO seals 'covenant.bypassed', because
        reaching this wrapper without having been refused by gate() means
        some executor skipped the gate. The backstop holds the line and
        reports the gap rather than hiding it.
        """
        armed: dict = {}
        for name, tool in registry.items():
            armed[name] = self.arm_one(name, tool)
        return armed

    def arm_one(self, name: str, tool):
        """Wrap a single tool. Idempotent — an armed tool is returned as is."""
        if getattr(tool, "guarded", False):
            return tool
        return replace(tool, handler=self._wrap(name, tool.handler),
                       guarded=True)

    def registry(self, initial: dict | None = None) -> "ArmedRegistry":
        """A tool registry that arms on insertion.

        arm() secures the tools that exist when it runs, but the agent
        registers a further two dozen directly into its registry as the
        advanced subsystems come up. Those would arrive unguarded, which is
        the same convention problem one level higher: someone must remember.

        This container holds the invariant instead — an unguarded tool
        cannot be put in, whenever or wherever it is registered.
        """
        return ArmedRegistry(self, initial)

    def _wrap(self, name: str, handler):
        def guarded(**args) -> str:
            violations = self.check(name, args)
            if not violations:
                return handler(**args)
            self._record("covenant.bypassed", name, violations)
            return "ERROR: " + self.cite(violations)
        guarded.__name__ = f"guarded_{name}"
        guarded.__doc__ = getattr(handler, "__doc__", "")
        return guarded

    # -- observation --------------------------------------------------------

    @staticmethod
    def unnamed_tools(registry: dict) -> list[str]:
        """Armed tools whose effects effects.derive() cannot name.

        Arming routes every tool through the boundary, but a path or
        content clause can only judge effects it can read. A tool outside
        the effect vocabulary passes those clauses because nothing was
        derived to test — not because it was found compliant.

        That gap is reported instead of being left to look like coverage,
        so the author can see exactly which tools their containment clauses
        do not reach and name them directly with forbid_tool if they must.
        """
        return sorted(set(registry) - NAMED_TOOLS)

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


class ArmedRegistry(dict):
    """A tool registry whose every member is bound to the boundary.

    Subclasses dict so it drops into the places a plain registry already
    goes, but no insertion route leaves a handler unguarded.
    """

    def __init__(self, covenant: Covenant, initial: dict | None = None):
        super().__init__()
        self._covenant = covenant
        if initial:
            for name, tool in initial.items():
                self[name] = tool

    def __setitem__(self, name, tool) -> None:
        super().__setitem__(name, self._covenant.arm_one(name, tool))

    def setdefault(self, name, default=None):
        if name not in self:
            self[name] = default
        return self[name]

    def update(self, other=(), /, **kw) -> None:  # type: ignore[override]
        items = other.items() if hasattr(other, "items") else other
        for name, tool in items:
            self[name] = tool
        for name, tool in kw.items():
            self[name] = tool


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

        # 3. EFFECT EQUIVALENCE — the same act is refused however it is
        # spelled. Each pair below is one act by two routes; before guards
        # bound to effects, the shell route walked straight through.
        escapes = [
            ("1", ("write_file", {"path": "/etc/cron.d/x", "content": "b"}),
                  ("run_command", {"command": "echo b > /etc/cron.d/x"})),
            # single-quoted so the shell preserves the inner quotes, i.e.
            # the bytes that actually land in the file
            ("2", ("write_file", {"path": "src/c.py",
                                  "content": 'API_KEY = "sk-ab1"'}),
                  ("run_command",
                   {"command": "echo 'API_KEY=\"sk-ab1\"' > src/c.py"})),
            ("1", ("write_file", {"path": "/etc/y", "content": "b"}),
                  ("run_command", {"command": "cp src/a.py /etc/y"})),
            ("1", ("write_file", {"path": "/etc/z", "content": "b"}),
                  ("run_command", {"command": "mv src/a.py /etc/z"})),
        ]
        for clause_id, direct, indirect in escapes:
            d = {v.clause for v in cov.check(*direct)}
            i = {v.clause for v in cov.check(*indirect)}
            assert clause_id in d, (direct, d)
            assert clause_id in i, ("escape still open", indirect, i)

        # heredocs carry content, so a content rule reaches them too
        assert cov.gate("run_command", {
            "command": "cat > src/c.py <<'EOF'\nAPI_KEY = \"sk-9\"\nEOF"})

        # a sequenced command is judged segment by segment
        assert cov.gate("run_command",
                        {"command": "pytest -q && echo x > /etc/w"})

        # in-policy shell work is untouched
        for ok in ("pytest -q", "ls -la src", "grep -rn foo src/",
                   "echo hello > src/note.txt", "mkdir -p tests/unit"):
            assert cov.gate("run_command", {"command": ok}) is None, ok

        # 3b. the opaque case: a call whose effects cannot be read cannot
        # satisfy a containment clause, so it is refused rather than waved
        # through on the assumption that it behaves.
        for blind in ('eval "$CMD"', 'bash -c "rm -rf /"',
                      'echo x > $DIR/f', 'cat f | xargs rm'):
            r = cov.gate("run_command", {"command": blind})
            assert r and "cannot be determined" in r, (blind, r)

        # 3c. forbid_effect refuses an act by ANY route, tool or shell
        eff_log = EventLog(Path(td) / "eff.jsonl")   # own log: see (5) below
        eff = Covenant(eff_log, "§7 Nothing is ever deleted\n"
                                "@enforce forbid_effect: delete\n")
        assert eff.gate("delete_path", {"path": "a"})
        assert eff.gate("run_command", {"command": "rm -f a"})
        assert eff.gate("run_command", {"command": "mv a b"})
        assert eff.gate("run_command", {"command": "ls"}) is None
        bad_eff = Covenant(log, "§8 x\n@enforce forbid_effect: sideways\n")
        assert bad_eff.errors and "forbid_effect" in bad_eff.errors[0]

        # 4. determinism: the same call always gets the same verdict
        call = ("write_file", {"path": "/etc/passwd", "content": "x"})
        assert cov.check(*call) == cov.check(*call)

        # 5. every block is sealed, and never silently swallowed (cov is
        # the only Covenant writing to this log — eff has its own)
        events = [e for e in log.events() if e.type == "covenant.blocked"]
        assert len(events) == cov.blocked, (len(events), cov.blocked)
        assert cov.blocked >= 6
        assert events[0].data["violations"][0]["clause"]

        # 6. malformed rules are reported, never guessed at
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

        # 7. ARMING — the unguarded handler is not reachable
        from .tools import Tool

        calls: list[tuple] = []

        def _writer(**kw) -> str:
            calls.append(kw)
            return "OK wrote"

        registry = {"write_file": Tool("write_file", "w", {}, _writer),
                    "delete_path": Tool("delete_path", "d", {}, _writer)}
        assert not any(t.guarded for t in registry.values())

        arm_log = EventLog(Path(td) / "arm.jsonl")
        armed_cov = Covenant(arm_log, spec)
        armed = armed_cov.arm(registry)
        assert all(t.guarded for t in armed.values())

        # an in-policy call reaches the real handler
        assert armed["write_file"].handler(
            path="src/a.py", content='"""d."""') == "OK wrote"
        assert len(calls) == 1

        # a refused call never reaches it, even though nothing asked a gate
        out = armed["write_file"].handler(path="/etc/passwd", content="x")
        assert out.startswith("ERROR: CovenantViolation"), out
        assert len(calls) == 1, "handler ran despite the refusal"

        # …and the same act through the shell is refused identically
        registry2 = {"run_command": Tool("run_command", "r", {}, _writer)}
        armed2 = armed_cov.arm(registry2)
        assert armed2["run_command"].handler(
            command="echo x > /etc/passwd").startswith("ERROR:")
        assert len(calls) == 1

        # reaching the backstop means an executor skipped the gate, and
        # that is recorded rather than passed over in silence
        bypassed = [e for e in arm_log.events()
                    if e.type == "covenant.bypassed"]
        assert len(bypassed) == 2, bypassed
        assert bypassed[0].data["violations"][0]["clause"] == "1"

        # arming is idempotent: re-arming does not double-wrap
        assert armed_cov.arm(armed)["write_file"] is armed["write_file"]

        # 7b. the registry arms on insertion, so a tool registered later —
        # as the agent's advanced subsystems do, long after arm() ran —
        # cannot arrive unguarded
        live = armed_cov.registry(registry)
        assert all(t.guarded for t in live.values())
        live["late_tool"] = Tool("late_tool", "registered later", {}, _writer)
        assert live["late_tool"].guarded
        live.update({"later_still": Tool("later_still", "x", {}, _writer)})
        assert live["later_still"].guarded
        live.setdefault("latest", Tool("latest", "x", {}, _writer))
        assert live["latest"].guarded
        # and it enforces, not merely marks
        before = len(calls)
        assert live["write_file"].handler(
            path="/etc/shadow", content="x").startswith("ERROR:")
        assert len(calls) == before

        # 7c. arming is not the same as coverage, and the difference is
        # reported: a tool outside the effect vocabulary passes path and
        # content clauses because nothing was derived to test, not because
        # it was found compliant.
        blind = Covenant.unnamed_tools(live)
        assert "late_tool" in blind and "write_file" not in blind, blind
        assert live["late_tool"].guarded          # armed…
        assert live["late_tool"].handler(path="/etc/anything") == "OK wrote"
        # …but nameable directly, which does reach it
        byname = Covenant(EventLog(Path(td) / "byname.jsonl"),
                          "§20 that tool is not used here\n"
                          "@enforce forbid_tool: late_tool\n")
        reg3 = byname.registry({"late_tool": Tool("late_tool", "x", {},
                                                  _writer)})
        assert reg3["late_tool"].handler(path="/etc/x").startswith("ERROR:")

        # 8. the report distinguishes bound clauses from prose
        rep = cov.report()
        # preamble and §6 carry prose only
        assert "2 clause(s) carry no @enforce rule" in rep
        assert "blocked" in rep

    print("COVENANT SELF-TEST PASS")
