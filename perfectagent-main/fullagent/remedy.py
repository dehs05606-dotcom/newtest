"""REMEDY — a refusal that says what WOULD be allowed.

A boundary that only ever says no produces a predictable failure, and it is
not disobedience. The agent tries a write, is refused, tries a near-variant,
is refused, tries another. Each attempt is individually reasonable — it has
been told that this act is forbidden, never what a permitted act looks like
— and the loop burns the turn without a single line of useful work. Every
refusal was correct and the outcome is still a failure.

Compilers solved this decades ago. `undefined name 'lenght'` is a bad
error; `undefined name 'lenght' — did you mean 'length'?` is a good one,
and the difference is not politeness. It is that the second one carries the
information needed to act, so the next attempt is informed rather than a
guess.

So every refusal is paired with the nearest compliant act, computed from
the clause that refused, NOT suggested by a model:

    confine_paths   the same filename under the nearest permitted root
    forbid_path     the same filename outside the forbidden glob
    require_content what is missing, and where it must go
    forbid_content  which span offends, so it can be removed rather than
                    the whole write abandoned
    forbid_tool     the tool that does the same job and is permitted
    forbid_effect   the closest act that does not have that effect
    horizon/ration  what the window allows, and when it resets

Two properties keep this from becoming a hole:

  1. A REMEDY IS NOT PERMISSION. It is a sentence. The suggested act goes
     through the same gate as any other, and is refused in turn if some
     other clause objects. Nothing here can approve anything.
  2. IT IS DERIVED, NEVER GUESSED. Each remedy is computed from the guard's
     own parameters — its roots, its globs, its regex. When a clause gives
     nothing to compute from, this module says so instead of inventing a
     plausible-sounding suggestion, which would be worse than silence
     because the agent would act on it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePath


@dataclass(frozen=True)
class Suggestion:
    """The nearest compliant act, derived from the clause that refused."""
    clause: str
    action: str          # a concrete, checkable next step
    rationale: str = ""

    def to_dict(self) -> dict:
        return {"clause": self.clause, "action": self.action,
                "rationale": self.rationale}


def _basename(path: str) -> str:
    return PurePath(path or "").name or "file"


def _norm(path: str) -> str:
    parts: list[str] = []
    for part in PurePath(path or "").parts:
        if part in ("/", "\\"):
            continue
        if part == "..":
            if parts:
                parts.pop()
        elif part != ".":
            parts.append(part)
    return "/".join(parts)


def _nearest_root(path: str, roots: list[str]) -> str:
    """The permitted root that shares most with the refused path, so the
    suggestion lands where the author most plausibly meant."""
    if not roots:
        return ""
    norm = _norm(path)
    best, score = roots[0], -1
    for r in roots:
        rn = _norm(r)
        shared = 0
        for a, b in zip(norm.split("/"), rn.split("/")):
            if a != b:
                break
            shared += 1
        # a root whose name appears anywhere in the path is a better guess
        if rn and rn in norm.split("/"):
            shared += 2
        if shared > score:
            best, score = r, shared
    return best


def for_violation(v, guards: list | None = None) -> Suggestion | None:
    """The compliant alternative to one covenant violation."""
    kind = getattr(v, "kind", "")
    clause = getattr(v, "clause", "?")
    path = getattr(v, "path", "")
    guard = next((g for g in (guards or ())
                  if g.clause == clause and g.kind == kind), None)

    if kind == "confine_paths":
        roots = list(getattr(guard, "roots", ()) or ())
        if not roots:
            return None
        root = _nearest_root(path, roots)
        return Suggestion(
            clause,
            f"write to {root.rstrip('/')}/{_basename(path)} instead",
            f"this clause permits only {', '.join(roots)}")

    if kind == "forbid_path":
        globs = list(getattr(guard, "globs", ()) or ())
        return Suggestion(
            clause,
            f"choose a path for {_basename(path)!r} outside "
            f"{', '.join(globs) or 'the forbidden pattern'}",
            "the filename is fine; the location is not")

    if kind == "require_content":
        value = getattr(guard, "value", "")
        where = getattr(guard, "where", "")
        return Suggestion(
            clause,
            f"add the required content to {path or where!r} before writing "
            f"it — the clause requires a match for {value!r}",
            f"applies to files matching {where!r}" if where else "")

    if kind == "forbid_content":
        detail = getattr(v, "detail", "")
        m = re.search(r"pattern: '([^']*)'", detail)
        span = m.group(1) if m else ""
        return Suggestion(
            clause,
            (f"remove {span!r} from the content and write the rest"
             if span else "remove the offending span and write the rest"),
            "only that span is refused, not the whole write")

    if kind == "forbid_tool":
        value = getattr(guard, "value", "")
        swap = {"delete_path": "leave the file in place, or move it with "
                               "move_path if it must go",
                "run_command": "use write_file / edit_file for file changes",
                "apply_patch": "make the same edits with edit_file"}
        return Suggestion(clause, swap.get(value,
                                           f"use a tool other than {value!r}"),
                          f"{value!r} is forbidden by this clause")

    if kind == "forbid_effect":
        detail = getattr(v, "detail", "")
        effect = detail.split()[0] if detail else ""
        swap = {"delete": "leave the file in place; if it must stop being "
                          "used, empty it or move it aside",
                "write": "read-only work only under this clause",
                "opaque": "use a command whose effects can be read ahead of "
                          "time — a literal redirect rather than eval or "
                          "a shell -c"}
        return Suggestion(clause,
                          swap.get(effect,
                                   f"avoid the {effect or 'forbidden'} effect"),
                          "the act is refused by any route, not just this one")

    if kind == "forbid_command":
        return Suggestion(
            clause,
            "rewrite the command without the forbidden form",
            "the pattern is matched against the command text")

    return None


def for_breach(b) -> Suggestion | None:
    """The compliant alternative to a horizon or ration breach."""
    clause = getattr(b, "clause", "?")
    measure = getattr(b, "measure", "")
    window = getattr(b, "window", "")
    limit = getattr(b, "limit", 0)
    spent = getattr(b, "current", getattr(b, "spent", 0))
    room = limit - spent
    if room <= 0:
        return Suggestion(
            clause,
            (f"this {window} has no {measure} left — "
             + ("start a new turn" if window == "turn"
                else "the limit is for the whole session")),
            f"{measure} is capped at {limit:g} per {window}")
    return Suggestion(
        clause,
        f"reduce this call to at most {room:g} more {measure}, "
        f"or split it across turns",
        f"{spent:g} of {limit:g} {measure} already used this {window}")


def annotate(refusal: str, violations: list | None = None,
             guards: list | None = None, breaches: list | None = None) -> str:
    """Append the compliant alternatives to a refusal message.

    A refusal with no derivable remedy is returned unchanged rather than
    padded with a generic line: "try something else" is noise, and noise in
    an error message is how error messages stop being read.
    """
    out: list[Suggestion] = []
    for v in violations or ():
        s = for_violation(v, guards)
        if s:
            out.append(s)
    for b in breaches or ():
        s = for_breach(b)
        if s:
            out.append(s)
    if not out:
        return refusal

    seen: set[str] = set()
    lines = [refusal, "", "What would be allowed:"]
    for s in out:
        if s.action in seen:
            continue
        seen.add(s.action)
        tail = f"  ({s.rationale})" if s.rationale else ""
        lines.append(f"  {s.clause}: {s.action}{tail}")
    lines.append("  — a suggestion, not permission: it is gated like any "
                 "other call")
    return "\n".join(lines)


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    from .covenant import Covenant
    from .horizon import Horizon
    from .kernel import EventLog

    with tempfile.TemporaryDirectory() as td:
        log = EventLog(Path(td) / "log.jsonl")
        spec = '''§1 Writes stay under src/ and tests/
@enforce confine_paths: src, tests

§2 No secrets in source
@enforce forbid_content: (?i)api[_-]?key\\s*=\\s*["\\'][A-Za-z0-9]

§3 Nothing is ever deleted
@enforce forbid_effect: delete

§4 Python modules carry a docstring
@enforce {"kind": "require_content", "value": "^\\\\s*[\\"']{3}",
          "where": "*.py"}

§5 Never delete_path
@enforce forbid_tool: delete_path
'''
        cov = Covenant(log, spec)

        # -- confine_paths suggests the nearest permitted root -------------
        vs = cov.check("write_file", {"path": "/etc/app.py",
                                      "content": '"""x."""'})
        s = for_violation(vs[0], cov.guards)
        assert s and "app.py" in s.action, s
        assert s.action.startswith("write to src/") or \
            s.action.startswith("write to tests/"), s.action

        # the nearest root is chosen, not just the first
        vs = cov.check("write_file", {"path": "/elsewhere/tests/unit.py",
                                      "content": '"""x."""'})
        s = for_violation(vs[0], cov.guards)
        assert "tests/unit.py" in s.action, s.action

        # -- forbid_content names the offending span -----------------------
        vs = cov.check("write_file", {"path": "src/c.py",
                                      "content": '"""d."""\nAPI_KEY = "sk-1"'})
        s = for_violation(next(v for v in vs if v.kind == "forbid_content"),
                          cov.guards)
        assert s and "remove" in s.action and "API_KEY" in s.action, s
        assert "not the whole write" in s.rationale

        # -- require_content says what is missing --------------------------
        vs = cov.check("write_file", {"path": "src/nodoc.py",
                                      "content": "x = 1"})
        s = for_violation(next(v for v in vs if v.kind == "require_content"),
                          cov.guards)
        assert s and "required content" in s.action, s

        # -- forbid_tool names the alternative -----------------------------
        vs = cov.check("delete_path", {"path": "src/a.py"})
        s = for_violation(next(v for v in vs if v.kind == "forbid_tool"),
                          cov.guards)
        assert s and "move_path" in s.action, s

        # -- forbid_effect explains the route is irrelevant ----------------
        vs = cov.check("run_command", {"command": "rm -f src/a.py"})
        s = for_violation(next(v for v in vs if v.kind == "forbid_effect"),
                          cov.guards)
        assert s and "any route" in s.rationale, s

        # -- opaque commands get the concrete alternative ------------------
        conf = Covenant(log, "§9 no unreadable effects\n"
                             "@enforce forbid_effect: opaque\n")
        vs = conf.check("run_command", {"command": 'eval "$CMD"'})
        s = for_violation(vs[0], conf.guards)
        assert s and "literal redirect" in s.action, s

        # -- horizon breaches say how much room is left --------------------
        hz = Horizon(log, "§12 at most 3 files\n"
                          "@horizon per turn max files_written 3\n")
        hz.open_turn()
        for i in range(2):
            hz.spend("write_file", {"path": f"f{i}.py", "content": "x"})
        br = hz.project("run_command",
                        {"command": "touch a && touch b && touch c"})
        s = for_breach(br[0])
        assert s and "at most 1 more files_written" in s.action, s.action

        # a full window says to start a new turn
        hz.spend("write_file", {"path": "f2.py", "content": "x"})
        br = hz.project("write_file", {"path": "f3.py", "content": "x"})
        s = for_breach(br[0])
        assert "start a new turn" in s.action, s.action

        # -- annotate() composes them onto a real refusal ------------------
        vs = cov.check("write_file", {"path": "/etc/x.py", "content": "x = 1"})
        text = annotate(cov.cite(vs), vs, cov.guards)
        assert "What would be allowed:" in text
        assert "not permission" in text
        assert text.startswith("CovenantViolation")

        # -- a refusal with nothing to derive stays unchanged --------------
        plain = "SomeOtherRefusal: no clause information here"
        assert annotate(plain, [], []) == plain

        # -- duplicate suggestions are collapsed ---------------------------
        dupe = annotate(cov.cite(vs), vs + vs, cov.guards)
        assert dupe.count("write to src/") <= 1

        # -- a remedy is only ever a sentence ------------------------------
        # nothing in this module can clear a violation
        assert cov.check("write_file", {"path": "/etc/x.py",
                                        "content": "x = 1"}), \
            "remedy must not affect enforcement"

    print("REMEDY SELF-TEST PASS")
