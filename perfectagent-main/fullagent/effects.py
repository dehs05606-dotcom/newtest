"""EFFECTS — what a call DOES, independent of which tool it used.

A guard bound to a tool name is a guard bound to spelling. `write_file`
with path "/etc/cron.d/x" and `run_command` with "echo boom > /etc/cron.d/x"
are the same act; a rule that refuses the first and permits the second does
not constrain the agent, it constrains its vocabulary. Any model — not
maliciously, just by picking a different tool for the same job — routes
straight around it.

So guards must not see tool calls. They must see EFFECTS:

    write   this path's bytes change (and, when known, to what)
    delete  this path stops existing
    exec    a process runs
    opaque  SOMETHING happens that cannot be named ahead of time

derive() reduces every tool call to that vocabulary, shell commands
included: redirections, heredocs, rm/mv/cp/tee/dd/sed -i/truncate/ln,
and pipelines. Two different tools producing one effect produce one
identical Effect, so a clause written once holds across every route to it.

THE OPAQUE CASE — the part that makes this airtight rather than merely
broad. Some commands cannot be analysed before they run: `eval "$X"`,
`bash -c "$CMD"`, `python -c ...`, `curl … | sh`, a redirect whose target
is `$DIR/f`. Their effects are unknowable, so no containment claim about
them can be proven.

An unprovable claim is not treated as a passing one. An opaque effect
satisfies no containment clause: under a `confine_paths` or `forbid_path`
clause it is refused, because "all writes stay under src/" is exactly the
guarantee such a command breaks. Where the author declared no containment,
opaque commands run normally — the boundary only ever refuses what its
clauses actually claim.

That asymmetry is deliberate. A guard that fails OPEN when it cannot see is
decorative: it holds only for actions transparent enough not to need it.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass

# effect kinds
WRITE = "write"
DELETE = "delete"
EXEC = "exec"
OPAQUE = "opaque"

# shell splitters: sequencing and pipes both start a new simple command
_SPLIT_RE = re.compile(r"\s*(?:\|\||&&|;|\||\n)\s*")

# a redirect target that cannot be resolved before the command runs
_DYNAMIC_RE = re.compile(r"[$`]|\$\(")

# interpreter forms that can perform arbitrary effects
_EVAL_CMDS = frozenset({"eval", "source", "."})
_SHELLS = frozenset({"sh", "bash", "zsh", "ksh", "dash", "fish"})
_INTERPRETERS = frozenset({
    "python", "python3", "perl", "ruby", "node", "php", "lua",
})
_ARBITRARY = frozenset({"xargs", "find"})  # -exec / -delete reach anywhere

# commands whose filesystem effects are known
_DELETERS = frozenset({"rm", "rmdir", "unlink", "shred"})
_CREATORS = frozenset({"touch", "mkdir", "mkfifo"})


@dataclass(frozen=True)
class Effect:
    """One consequence of a call, named independently of the tool used."""
    kind: str
    path: str = ""
    content: str = ""
    command: str = ""
    reason: str = ""      # why this effect was derived (for the citation)

    def to_dict(self) -> dict:
        d = {"kind": self.kind}
        for k in ("path", "content", "command", "reason"):
            v = getattr(self, k)
            if v:
                d[k] = v[:200] if k == "content" else v
        return d


# ---------------------------------------------------------------------------
# shell analysis
# ---------------------------------------------------------------------------


def _strip_flags(tokens: list[str]) -> list[str]:
    return [t for t in tokens if not t.startswith("-")]


def _heredoc_bodies(command: str) -> dict[str, str]:
    """Map heredoc delimiter -> body, so `cat > f <<EOF … EOF` is a write
    whose content is known and can be pattern-checked like any other."""
    out: dict[str, str] = {}
    for m in re.finditer(r"<<-?\s*[\"']?([A-Za-z_][A-Za-z0-9_]*)[\"']?",
                         command):
        delim = m.group(1)
        body = re.search(
            r"<<-?\s*[\"']?" + re.escape(delim) + r"[\"']?\s*\n(.*?)\n\s*"
            + re.escape(delim) + r"\s*(?:\n|$)",
            command, re.S)
        if body:
            out[delim] = body.group(1)
    return out


def _redirect_effects(segment: str, heredocs: dict[str, str],
                      ) -> tuple[list[Effect], str]:
    """Writes implied by redirection. Returns (effects, segment-without-
    redirects) so the remaining tokens can be read as a plain command."""
    effects: list[Effect] = []
    content = ""
    for delim, body in heredocs.items():
        if re.search(r"<<-?\s*[\"']?" + re.escape(delim), segment):
            content = body
            break

    def _take(m: re.Match) -> str:
        target = m.group("target")
        if _DYNAMIC_RE.search(target):
            effects.append(Effect(
                OPAQUE, command=segment.strip(),
                reason=f"redirect target {target!r} is resolved at run time"))
        else:
            effects.append(Effect(
                WRITE, path=target.strip("\"'"), content=content,
                reason="shell redirection"))
        return " "

    cleaned = re.sub(r"\d?>>?\s*(?P<target>[^\s;|&<>]+)", _take, segment)
    return effects, cleaned


def _command_effects(segment: str, heredocs: dict[str, str]) -> list[Effect]:
    """Effects of one simple command (no pipes, no sequencing)."""
    seg = segment.strip()
    if not seg:
        return []

    effects, cleaned = _redirect_effects(seg, heredocs)

    try:
        tokens = shlex.split(cleaned, comments=True)
    except ValueError:
        # unbalanced quotes — the command cannot be read, so it cannot be
        # shown to respect anything
        return effects + [Effect(OPAQUE, command=seg,
                                 reason="command could not be parsed")]
    if not tokens:
        return effects

    # strip leading VAR=value assignments
    while tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):
        tokens.pop(0)
    if not tokens:
        return effects

    name = tokens[0].rsplit("/", 1)[-1]
    rest = tokens[1:]

    # `echo secret > f` writes content as surely as write_file does; without
    # this, a content rule would be blind to the commonest shell write.
    if name in ("echo", "printf") and not any(e.content for e in effects):
        said = " ".join(_strip_flags(rest))
        if said:
            effects = [
                Effect(e.kind, e.path, said, e.command, e.reason)
                if e.kind == WRITE else e
                for e in effects
            ]

    effects.append(Effect(EXEC, command=seg, reason=f"runs {name!r}"))

    # -- forms whose effects cannot be known ahead of time ------------------
    if name in _EVAL_CMDS:
        return effects + [Effect(OPAQUE, command=seg,
                                 reason=f"{name} executes constructed text")]
    if name in _SHELLS and any(t == "-c" for t in rest):
        return effects + [Effect(OPAQUE, command=seg,
                                 reason=f"{name} -c executes constructed text")]
    if name in _INTERPRETERS and any(t in ("-c", "-e") for t in rest):
        return effects + [Effect(
            OPAQUE, command=seg,
            reason=f"{name} runs inline code that may write anywhere")]
    if name in _ARBITRARY:
        return effects + [Effect(
            OPAQUE, command=seg,
            reason=f"{name} can execute further commands")]

    args = _strip_flags(rest)

    # -- known filesystem effects ------------------------------------------
    if name in _DELETERS:
        effects += [Effect(DELETE, path=a, reason=f"{name} removes it")
                    for a in args]
    elif name in _CREATORS:
        effects += [Effect(WRITE, path=a, reason=f"{name} creates it")
                    for a in args]
    elif name == "mv" and len(args) >= 2:
        effects += [Effect(DELETE, path=a, reason="mv moves it away")
                    for a in args[:-1]]
        effects.append(Effect(WRITE, path=args[-1], reason="mv target"))
    elif name in ("cp", "install", "rsync") and len(args) >= 2:
        effects.append(Effect(WRITE, path=args[-1], reason=f"{name} target"))
    elif name == "ln" and len(args) >= 2:
        effects.append(Effect(WRITE, path=args[-1], reason="ln creates it"))
    elif name == "tee":
        effects += [Effect(WRITE, path=a, reason="tee writes it")
                    for a in args]
    elif name == "dd":
        for t in rest:
            if t.startswith("of="):
                effects.append(Effect(WRITE, path=t[3:], reason="dd output"))
    elif name == "truncate":
        effects += [Effect(WRITE, path=a, reason="truncate resizes it")
                    for a in args]
    elif name in ("chmod", "chown", "chgrp"):
        effects += [Effect(WRITE, path=a, reason=f"{name} alters it")
                    for a in args[1:]]
    elif name == "sed" and any(t == "-i" or t.startswith("-i.")
                               or (t.startswith("-") and "i" in t
                                   and not t.startswith("--"))
                               for t in rest):
        # sed -i edits in place; the first non-flag arg is the script
        effects += [Effect(WRITE, path=a, reason="sed -i edits in place")
                    for a in args[1:]]
    return effects


def derive_command_effects(command: str) -> list[Effect]:
    """Every effect a shell command line may have."""
    heredocs = _heredoc_bodies(command)
    # a heredoc body is data, not commands — remove it before splitting
    stripped = command
    for delim, body in heredocs.items():
        stripped = stripped.replace(body, "")
    out: list[Effect] = []
    for segment in _SPLIT_RE.split(stripped):
        out.extend(_command_effects(segment, heredocs))
    return out


# ---------------------------------------------------------------------------
# tool calls -> effects
# ---------------------------------------------------------------------------

_SHELL_TOOLS = frozenset({"run_command", "bg_shell", "shell", "bash"})


def derive(tool: str, args: dict) -> list[Effect]:
    """Reduce any tool call to the effects it would have. Unknown tools
    yield no effects: the boundary constrains what it can name, and a tool
    it cannot name is left to the other gates."""
    a = args or {}
    if tool in _SHELL_TOOLS:
        return derive_command_effects(str(a.get("command") or ""))
    if tool == "write_file":
        return [Effect(WRITE, path=str(a.get("path") or ""),
                       content=str(a.get("content") or ""),
                       reason="write_file")]
    if tool == "edit_file":
        return [Effect(WRITE, path=str(a.get("path") or ""),
                       content=str(a.get("new_string") or ""),
                       reason="edit_file")]
    if tool == "create_directory":
        return [Effect(WRITE, path=str(a.get("path") or ""),
                       reason="create_directory")]
    if tool == "delete_path":
        return [Effect(DELETE, path=str(a.get("path") or ""),
                       reason="delete_path")]
    if tool == "move_path":
        return [Effect(DELETE, path=str(a.get("src") or ""),
                       reason="move_path source"),
                Effect(WRITE, path=str(a.get("dst") or ""),
                       reason="move_path target")]
    if tool == "copy_path":
        return [Effect(WRITE, path=str(a.get("dst") or ""),
                       reason="copy_path target")]
    return []


if __name__ == "__main__":
    # -- equivalence: the same act derives the same effect ------------------
    direct = derive("write_file", {"path": "/etc/x", "content": "boom"})
    via_sh = derive("run_command", {"command": "echo boom > /etc/x"})
    assert [e.kind for e in direct] == [WRITE]
    assert any(e.kind == WRITE and e.path == "/etc/x" for e in via_sh)

    assert any(e.kind == DELETE and e.path == "src/core.py"
               for e in derive("run_command",
                               {"command": "rm -f src/core.py"}))
    assert any(e.kind == DELETE and e.path == "src/core.py"
               for e in derive("delete_path", {"path": "src/core.py"}))

    # -- redirection forms --------------------------------------------------
    for cmd in ("echo x > a.txt", "echo x >> a.txt", "echo x 2> a.txt"):
        assert any(e.kind == WRITE and e.path == "a.txt"
                   for e in derive_command_effects(cmd)), cmd

    # content survives a redirect, so forbid_content still applies
    hd = derive_command_effects("cat > src/c.py <<'EOF'\nAPI_KEY = \"sk-1\"\nEOF")
    assert any(e.kind == WRITE and e.path == "src/c.py"
               and "API_KEY" in e.content for e in hd), hd

    # echo/printf carry their content too
    for cmd in ('echo API_KEY=sk-1 > src/c.py',
                'printf "API_KEY=sk-1" >> src/c.py'):
        effs = derive_command_effects(cmd)
        assert any(e.kind == WRITE and "API_KEY" in e.content
                   for e in effs), cmd

    # -- known writers ------------------------------------------------------
    cases = {
        "mv a b": [(DELETE, "a"), (WRITE, "b")],
        "cp a b": [(WRITE, "b")],
        "touch f": [(WRITE, "f")],
        "mkdir -p d": [(WRITE, "d")],
        "tee out.txt": [(WRITE, "out.txt")],
        "dd if=x of=y": [(WRITE, "y")],
        "truncate -s 0 f": [(WRITE, "f")],
        "ln -s a b": [(WRITE, "b")],
        "sed -i 's/a/b/' f.py": [(WRITE, "f.py")],
        "chmod +x f": [(WRITE, "f")],
    }
    for cmd, expected in cases.items():
        got = {(e.kind, e.path) for e in derive_command_effects(cmd)}
        for pair in expected:
            assert pair in got, (cmd, pair, got)

    # -- pipelines and sequencing are split -------------------------------
    multi = derive_command_effects("mkdir -p d && touch d/f ; rm old")
    got = {(e.kind, e.path) for e in multi}
    assert (WRITE, "d") in got and (WRITE, "d/f") in got
    assert (DELETE, "old") in got

    # -- the opaque case ----------------------------------------------------
    for cmd in ('eval "$CMD"',
                'bash -c "rm -rf /"',
                'python3 -c "open(\'/etc/x\',\'w\')"',
                'echo x > $DIR/f',
                'cat f | xargs rm',
                'echo "unbalanced'):
        effs = derive_command_effects(cmd)
        assert any(e.kind == OPAQUE for e in effs), cmd

    # reads stay transparent — no opaque, no write
    for cmd in ("ls -la", "pytest -q", "grep -rn foo src/", "git status"):
        effs = derive_command_effects(cmd)
        assert not any(e.kind in (OPAQUE, WRITE, DELETE) for e in effs), cmd
        assert any(e.kind == EXEC for e in effs), cmd

    # env assignments do not hide the command
    assert any(e.kind == DELETE and e.path == "f"
               for e in derive_command_effects("FOO=1 rm f"))

    # a path-shaped binary is read by its basename
    assert any(e.kind == DELETE for e in derive_command_effects("/bin/rm f"))

    # -- unknown tools yield nothing, rather than a false all-clear --------
    assert derive("read_file", {"path": "x"}) == []
    assert derive("web_search", {"query": "x"}) == []

    print("EFFECTS SELF-TEST PASS")
