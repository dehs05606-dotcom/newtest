"""SANCTUM — the boundary cannot be edited by what it binds.

Every rule in this package is authored in the specification. That is the
right design for rules about the project, and it is a circular one for the
rule that protects the rules:

    §99 The agent never edits the enforcement code.
    @enforce forbid_path: fullagent/covenant.py

A clause lives in the specification. Editing the specification removes the
clause. So a clause that forbids editing the specification is removed by
the very act it forbids, and it protects nothing.

The same holds one level down. A guard that protects covenant.py is code
inside covenant.py. Rewrite the file and the guard goes with it. Any
protection expressed in the thing being protected is not protection; it is
a comment.

Measured, not assumed: with a specification that carries no containment
clause — `forbid_content` and `forbid_effect` only, a perfectly ordinary
specification — the agent is cleared to write to covenant.py, to
charter.py, and to its own project.txt, and to truncate any of them through
the shell. The earlier refusals came from a `confine_paths` clause that
happened to exclude those paths. The boundary was protected by accident,
and an accident is not a property.

So this invariant is NOT a clause:

  * It is not written in the specification, so editing the specification
    cannot remove it.
  * It takes no @enforce syntax, so a malformed rule cannot silently
    disable it.
  * It is not narrowable. An @except cannot forgive it and a consent grant
    cannot spend it — every other refusal in this package can be excepted,
    and this is the one where an exception is indistinguishable from the
    attack.
  * It runs FIRST, before any clause is consulted, so it holds even when
    the specification is empty, absent, or entirely malformed.

It protects two things: the enforcement modules, and the specification file
in force. Both by content address, so a change made by any route — a route
this module never anticipated — is detected on the next verify() even
though it could not be refused.

SCOPE, stated precisely. This governs the AGENT's tool calls. It is not
a filesystem permission and does not try to be: a human developing this
project edits these files directly, with an editor, and should. The claim
is narrow and exact — the agent cannot rewrite the rules that bind it while
being bound by them — and that is the claim that was false until now.

WHAT IT CANNOT DO. A process with a shell can eventually reach any file;
what it cannot do is get that write through this gate, and every route the
effect vocabulary can name goes through this gate. Routes it cannot name
are not refused, but the content addresses make the result visible rather
than silent, which is the difference between a boundary that failed and one
that was never there.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path, PurePath

from .effects import DELETE, WRITE, derive
from .kernel import EventLog

# The modules that make up the boundary. Named explicitly rather than
# globbed: a glob over the package would also protect ordinary code, and a
# protection that covers everything is one an operator will switch off.
PROTECTED_MODULES = (
    "sanctum.py",       # first, and itself
    "charter.py",
    "covenant.py",
    "effects.py",
    "exemption.py",
    "consent.py",
    "egress.py",
    "horizon.py",
    "ration.py",
    "obligation.py",
    "sequence.py",
    "provenance.py",
    "sentinel.py",
    "escrow.py",
    "integrity.py",
    "witness.py",
    "audit.py",
    "attest.py",
    "remedy.py",
    "replay.py",
    "systemprompt.py",  # the prompt's single source
)


def _digest(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _norm(path: str) -> str:
    pure = PurePath(path or "")
    anchor = "/" if pure.is_absolute() else ""
    parts: list[str] = []
    for part in pure.parts:
        if part in ("/", "\\"):
            continue
        if part == "..":
            if parts:
                parts.pop()
        elif part != ".":
            parts.append(part)
    return anchor + "/".join(parts)


@dataclass(frozen=True)
class Breach:
    """An act that would change the boundary itself."""
    what: str            # module | specification
    path: str
    effect: str

    def to_dict(self) -> dict:
        return {"what": self.what, "path": self.path, "effect": self.effect}

    def describe(self) -> str:
        return (f"{self.effect} to {self.path!r} would change the "
                f"{self.what} that is enforcing this very call")


@dataclass(frozen=True)
class Change:
    """A protected file whose content no longer matches what was sealed."""
    what: str
    path: str
    was: str
    now: str

    def describe(self) -> str:
        if not self.now:
            return f"{self.what} {self.path!r} has been removed or is unreadable"
        return (f"{self.what} {self.path!r} changed since startup "
                f"({self.was[:12]} -> {self.now[:12]})")


class Sanctum:
    """The invariant that is not a clause."""

    def __init__(self, log: EventLog, spec_source: str = "",
                 package_dir: Path | None = None) -> None:
        self.log = log
        self.dir = Path(package_dir) if package_dir \
            else Path(__file__).resolve().parent
        self.spec_source = str(spec_source or "")
        self.blocked = 0
        self._sealed: dict[str, str] = {}
        self.seal()

    # -- content addresses --------------------------------------------------

    def protected_paths(self) -> dict[str, str]:
        """path -> what it is. Absolute and normalised, so a call naming the
        same file by a different spelling is still matched."""
        out: dict[str, str] = {}
        for name in PROTECTED_MODULES:
            p = self.dir / name
            out[_norm(str(p))] = "module"
        if self.spec_source:
            out[_norm(str(Path(self.spec_source)))] = "specification"
        return out

    def seal(self) -> dict[str, str]:
        """Record the content address of everything protected."""
        self._sealed = {}
        for path, what in self.protected_paths().items():
            d = _digest(Path(path))
            if d:
                self._sealed[path] = d
        self.log.append("sanctum.sealed",
                        {"files": len(self._sealed),
                         "dir": str(self.dir),
                         "spec": self.spec_source}, actor="kernel")
        return dict(self._sealed)

    def verify(self) -> list[Change]:
        """Protected files that have changed since they were sealed."""
        protected = self.protected_paths()
        out: list[Change] = []
        for path, was in self._sealed.items():
            now = _digest(Path(path))
            if now != was:
                out.append(Change(protected.get(path, "module"), path,
                                  was, now))
        if out:
            self.log.append("sanctum.changed",
                            {"changes": [c.describe() for c in out]},
                            actor="kernel")
        return out

    # -- the gate -----------------------------------------------------------

    def _what_is(self, raw: str) -> str | None:
        """Which protected thing `raw` names, or None.

        A protected file has many true spellings: absolute, relative to the
        working directory, relative to the package, and — the one a patch
        actually uses — `fullagent/covenant.py` from the repository root.
        Matching only the absolute form would leave every other spelling a
        way in, so each is resolved, and a package-qualified tail is
        matched directly.
        """
        protected = self.protected_paths()
        candidates = {_norm(str(Path(raw).expanduser()))}
        if not PurePath(raw).is_absolute():
            candidates.add(_norm(str(Path.cwd() / raw)))
            candidates.add(_norm(str(self.dir / raw)))
            candidates.add(_norm(str(self.dir.parent / raw)))
        for key in candidates:
            what = protected.get(key)
            if what is not None:
                return what
        # `<package>/<module>` named from anywhere above it
        tail = _norm(raw)
        for name in PROTECTED_MODULES:
            if tail == f"{self.dir.name}/{name}" or \
                    tail.endswith(f"/{self.dir.name}/{name}"):
                return "module"
        if self.spec_source:
            spec_tail = _norm(str(Path(self.spec_source).name))
            if tail == spec_tail or tail.endswith("/" + spec_tail):
                # only when it really is that file, not any same-named one
                for key in candidates:
                    if key in protected:
                        return protected[key]
        return None

    def check(self, tool: str, args: dict) -> list[Breach]:
        """Acts that would change the boundary. Judged on EFFECTS, so the
        shell, a patch and a direct write are the same act here too."""
        out: list[Breach] = []
        for e in derive(tool, args or {}):
            if e.kind not in (WRITE, DELETE) or not e.path:
                continue
            what = self._what_is(e.path)
            if what is not None:
                out.append(Breach(what, e.path, e.kind))
        return out

    def gate(self, tool: str, args: dict) -> str | None:
        """Block reason, or None. Consulted before any clause, and never
        narrowed: an exception here is indistinguishable from the attack."""
        breaches = self.check(tool, args)
        if not breaches:
            return None
        self.blocked += 1
        self.log.append("sanctum.blocked",
                        {"tool": tool,
                         "breaches": [b.to_dict() for b in breaches]},
                        actor="kernel")
        lines = ["SanctumViolation: this call would change the boundary "
                 "that is enforcing it."]
        for b in breaches:
            lines.append(f"  {b.describe()}")
        lines.append("  This is not a clause and cannot be excepted or "
                     "granted. Edit these files directly if you intend to "
                     "change the rules.")
        return "\n".join(lines)

    def report(self) -> str:
        changes = self.verify()
        head = (f"sanctum: {len(self._sealed)} protected file(s) · "
                f"{self.blocked} call(s) refused")
        if not changes:
            return head + "\n  every protected file matches what was sealed"
        return head + "\n" + "\n".join(f"  !! {c.describe()}" for c in changes)


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        log = EventLog(root / "log.jsonl")
        pkg = root / "pkg"
        pkg.mkdir()
        for name in PROTECTED_MODULES:
            (pkg / name).write_text(f"# {name}\n", encoding="utf-8")
        spec = root / "project.txt"
        spec.write_text("§1 a rule\n", encoding="utf-8")

        s = Sanctum(log, str(spec), package_dir=pkg)
        assert len(s._sealed) == len(PROTECTED_MODULES) + 1

        # -- the boundary's own code cannot be written ---------------------
        for name in ("covenant.py", "charter.py", "effects.py", "sanctum.py"):
            target = str(pkg / name)
            blocked = s.gate("write_file", {"path": target, "content": "x"})
            assert blocked and "SanctumViolation" in blocked, name
            assert "cannot be excepted" in blocked

        # -- nor the specification -----------------------------------------
        assert s.gate("write_file", {"path": str(spec), "content": "x"})

        # -- by ANY route, because it judges effects -----------------------
        cov = str(pkg / "covenant.py")
        for cmd in (f"echo x > {cov}",
                    f"cp /dev/null {cov}",
                    f"rm -f {cov}",
                    f"sed -i 's/a/b/' {cov}",
                    f"mv {cov} /tmp/gone",
                    f"cat > {cov} <<'EOF'\nx\nEOF",
                    f"sed -i 's/rule/x/' {spec}"):
            assert s.gate("run_command", {"command": cmd}), cmd
        assert s.gate("live_shell", {"command": f"truncate -s 0 {cov}"})
        assert s.gate("delete_path", {"path": cov})

        # a git-style patch names it package-relative, which is the spelling
        # an agent working from the repository root actually produces
        rel = f"{pkg.name}/covenant.py"
        assert s.gate("apply_patch",
                      {"patch": f"--- a/{rel}\n+++ b/{rel}\n"
                                f"@@ -1 +1 @@\n+x\n"}), \
            "a package-relative patch reached the boundary"
        assert s.gate("write_file", {"path": rel, "content": "x"})
        assert s.gate("run_command", {"command": f"echo x > {rel}"})
        assert s.gate("run_command",
                      {"command": f"echo x > deep/nested/{rel}"})

        # -- a different spelling of the same file is still matched --------
        assert s.gate("write_file", {"path": str(pkg / "./covenant.py"),
                                     "content": "x"})
        assert s.gate("write_file", {"path": str(pkg / "sub/../covenant.py"),
                                     "content": "x"})

        # -- ordinary work is untouched ------------------------------------
        assert s.gate("write_file", {"path": str(root / "src/app.py"),
                                     "content": "x = 1"}) is None
        assert s.gate("run_command", {"command": "pytest -q"}) is None
        assert s.gate("read_file", {"path": str(pkg / "covenant.py")}) is None
        # a file in the package that is NOT part of the boundary
        (pkg / "tui.py").write_text("# tui\n", encoding="utf-8")
        assert s.gate("write_file", {"path": str(pkg / "tui.py"),
                                     "content": "x"}) is None

        # -- it holds with NO specification at all -------------------------
        bare = Sanctum(EventLog(root / "bare.jsonl"), "", package_dir=pkg)
        assert bare.gate("write_file", {"path": str(pkg / "charter.py"),
                                        "content": "x"}), \
            "the invariant needed a specification to exist"

        # -- content addresses catch a change made by any other route ------
        assert s.verify() == []
        (pkg / "covenant.py").write_text("# rewritten elsewhere\n",
                                         encoding="utf-8")
        changes = s.verify()
        assert len(changes) == 1 and changes[0].what == "module"
        assert "changed since startup" in changes[0].describe()
        assert "!!" in s.report()

        # a removed file is reported too, not silently forgotten
        (pkg / "charter.py").unlink()
        assert any("removed or is unreadable" in c.describe()
                   for c in s.verify())

        # re-sealing accepts the current state deliberately
        (pkg / "charter.py").write_text("# back\n", encoding="utf-8")
        s.seal()
        assert s.verify() == []

        # -- a spec change is a change too ---------------------------------
        spec.write_text("§1 a rule\n§2 another\n", encoding="utf-8")
        ch = s.verify()
        assert len(ch) == 1 and ch[0].what == "specification"

        # -- every refusal is sealed ---------------------------------------
        kinds = {e.type for e in log.events()}
        assert {"sanctum.sealed", "sanctum.blocked",
                "sanctum.changed"} <= kinds, kinds

    print("SANCTUM SELF-TEST PASS")
