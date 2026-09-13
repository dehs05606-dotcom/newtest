"""ESCROW — a write reaches the tree only after it has been judged.

The Covenant refuses an intention. The Sentinel reverts a realised
violation. Between them sits a window that neither closes: a call that
passes the gate honestly, writes, and is then reverted was nonetheless
LIVE for the duration. During that window another process compiles the
file, a watcher fires, a test runs against it, a daemon reads the
credential. Reversion restores the bytes; it does not un-observe them.

For a multi-file change the window is worse than an instant. Files land one
at a time, so a change that is only coherent as a set is briefly half
applied. If the third write is refused, the first two are already real, and
"revert" now means undoing work that was itself permissible.

Escrow removes the window instead of shortening it:

    stage    writes go to a private directory, not the tree
    judge    the complete set is evaluated as one unit, against the same
             clauses, with the real content that would land
    commit   only if every member passes — then all at once
    discard  otherwise nothing was ever in the tree to undo

This is what makes a multi-file change atomic with respect to the
specification. The unit of judgement becomes the change rather than the
file, so a set that is individually innocent and collectively forbidden —
twenty files that together cross a horizon limit, a credential split across
two writes — is refused as the set it is.

Nothing is written outside the staging directory before commit(), so a
discarded change leaves no trace in the tree and needs no snapshot to
undo: there is nothing to restore, which is a stronger property than
restoring correctly.

LIMIT, stated plainly: escrow governs writes made THROUGH it. A command
that writes directly to the tree bypasses staging entirely — that is the
Sentinel's job, and the two are complementary rather than alternatives.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .effects import WRITE, Effect
from .kernel import EventLog


@dataclass
class Staged:
    """One pending write, held outside the tree."""
    path: str                 # the real destination
    content: str
    staged_at: str = ""       # where it actually lives until commit

    def effect(self) -> Effect:
        return Effect(WRITE, path=self.path, content=self.content,
                      reason="staged for commit")


@dataclass
class Outcome:
    committed: list[str] = field(default_factory=list)
    discarded: list[str] = field(default_factory=list)
    violations: list = field(default_factory=list)
    detail: str = ""

    @property
    def ok(self) -> bool:
        return not self.violations

    def to_dict(self) -> dict:
        return {"committed": self.committed, "discarded": self.discarded,
                "violations": [v.to_dict() for v in self.violations]}


class Escrow:
    """Stage, judge as a set, then commit or discard."""

    def __init__(self, log: EventLog, covenant, root: Path | None = None,
                 horizon=None) -> None:
        self.log = log
        self.covenant = covenant
        self.horizon = horizon
        self._dir = Path(tempfile.mkdtemp(prefix="fullagent-escrow-"))
        self._root = Path(root) if root else None
        self.pending: list[Staged] = []
        self.commits = 0
        self.discards = 0

    # -- staging ------------------------------------------------------------

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if not p.is_absolute() and self._root:
            p = self._root / p
        return p

    def stage(self, path: str, content: str) -> Staged:
        """Hold a write outside the tree. Nothing on disk changes here."""
        blob = self._dir / f"{len(self.pending):04d}.blob"
        blob.write_text(content, encoding="utf-8")
        item = Staged(path=path, content=content, staged_at=str(blob))
        self.pending.append(item)
        self.log.append("escrow.staged",
                        {"path": path, "chars": len(content)}, actor="kernel")
        return item

    # -- judgement ----------------------------------------------------------

    def judge(self) -> list:
        """Evaluate the WHOLE pending set against the clauses, at once.

        Judging the set rather than each member is the point: a change can
        be forbidden as a unit while every individual write in it is
        permitted.
        """
        effects = [s.effect() for s in self.pending]
        violations = list(self.covenant.check_effects(effects))
        if self.horizon is not None and self.pending:
            # the set also has to fit inside whatever the horizon allows
            for s in self.pending:
                breach = self.horizon.project("write_file",
                                              {"path": s.path,
                                               "content": s.content})
                if breach:
                    violations.extend(breach)
                    break
        return violations

    # -- resolution ---------------------------------------------------------

    def commit(self) -> Outcome:
        """Judge, then either land every write or none of them."""
        if not self.pending:
            return Outcome()
        violations = self.judge()
        paths = [s.path for s in self.pending]

        if violations:
            self.discards += 1
            self.log.append("escrow.discarded",
                            {"paths": paths,
                             "violations": [v.to_dict() for v in violations]},
                            actor="kernel")
            detail = [f"CovenantViolation: this change of {len(paths)} file"
                      f"{'s' if len(paths) > 1 else ''} was judged as a set "
                      f"and refused. Nothing reached the tree."]
            for v in violations:
                detail.append(f"  {getattr(v, 'clause', '?')}: "
                              f"{getattr(v, 'detail', v)}")
            out = Outcome(discarded=paths, violations=violations,
                          detail="\n".join(detail))
            self.clear()
            return out

        landed: list[str] = []
        for s in self.pending:
            dest = self._resolve(s.path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(s.staged_at, dest)
            landed.append(s.path)
        self.commits += 1
        self.log.append("escrow.committed", {"paths": landed}, actor="kernel")
        self.clear()
        return Outcome(committed=landed)

    def discard(self) -> Outcome:
        """Abandon the pending set. Nothing was in the tree to undo."""
        paths = [s.path for s in self.pending]
        if paths:
            self.discards += 1
            self.log.append("escrow.discarded",
                            {"paths": paths, "violations": []},
                            actor="kernel")
        self.clear()
        return Outcome(discarded=paths)

    def clear(self) -> None:
        for s in self.pending:
            try:
                Path(s.staged_at).unlink()
            except OSError:
                pass
        self.pending = []

    def close(self) -> None:
        self.clear()
        shutil.rmtree(self._dir, ignore_errors=True)

    def stats(self) -> dict:
        return {"pending": len(self.pending), "commits": self.commits,
                "discards": self.discards}


if __name__ == "__main__":
    from .covenant import Covenant
    from .horizon import Horizon

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        log = EventLog(root / "log.jsonl")
        cov = Covenant(log, '''§1 Writes stay under src
@enforce confine_paths: src

§2 No secrets in source
@enforce forbid_content: (?i)api[_-]?key\\s*=\\s*["\\'][A-Za-z0-9]
''')
        esc = Escrow(log, cov, root=root)

        # -- a clean set commits atomically --------------------------------
        esc.stage("src/a.py", "x = 1\n")
        esc.stage("src/b.py", "y = 2\n")
        # nothing has touched the tree yet
        assert not (root / "src").exists(), "staging wrote to the tree"
        out = esc.commit()
        assert out.ok and out.committed == ["src/a.py", "src/b.py"]
        assert (root / "src" / "a.py").read_text(encoding="utf-8") == "x = 1\n"
        assert (root / "src" / "b.py").is_file()
        assert esc.pending == []

        # -- one bad member discards the WHOLE set -------------------------
        esc.stage("src/c.py", "z = 3\n")          # innocent
        esc.stage("/etc/evil.py", "boom\n")        # outside src
        out = esc.commit()
        assert not out.ok
        assert set(out.discarded) == {"src/c.py", "/etc/evil.py"}
        # the innocent member never landed either — that is the atomicity
        assert not (root / "src" / "c.py").exists(), \
            "a permitted member landed from a refused set"
        assert not Path("/etc/evil.py").exists()
        assert "judged as a set" in out.detail

        # -- content rules see the real bytes that would land --------------
        esc.stage("src/conf.py", 'API_KEY = "sk-abc123"\n')
        out = esc.commit()
        assert not out.ok and "2" in {v.clause for v in out.violations}
        assert not (root / "src" / "conf.py").exists()

        # -- a discarded set leaves nothing to undo ------------------------
        esc.stage("src/d.py", "d = 1\n")
        out = esc.discard()
        assert out.discarded == ["src/d.py"]
        assert not (root / "src" / "d.py").exists()
        assert esc.pending == []

        # -- committing nothing is a no-op ---------------------------------
        assert esc.commit().committed == []

        # -- the set is judged against a horizon too -----------------------
        hz = Horizon(log, "§3 A change touches at most 2 files\n"
                          "@horizon per turn max files_written 2\n")
        hz.open_turn()
        esc2 = Escrow(log, cov, root=root, horizon=hz)
        esc2.stage("src/e.py", "e = 1\n")
        esc2.stage("src/f.py", "f = 1\n")
        out = esc2.commit()
        assert out.ok, out.detail
        hz.spend("write_file", {"path": "src/e.py", "content": "e = 1\n"})
        hz.spend("write_file", {"path": "src/f.py", "content": "f = 1\n"})
        esc2.stage("src/g.py", "g = 1\n")         # would be the third
        out = esc2.commit()
        assert not out.ok, "the horizon limit was crossed through escrow"
        assert not (root / "src" / "g.py").exists()
        esc2.close()

        # -- the ledger records both outcomes ------------------------------
        kinds = {e.type for e in log.events()}
        assert {"escrow.staged", "escrow.committed",
                "escrow.discarded"} <= kinds, kinds

        # -- an empty specification stages and commits freely --------------
        free = Escrow(log, Covenant(log, ""), root=root)
        free.stage("anywhere/h.py", "h = 1\n")
        out = free.commit()
        assert out.ok and (root / "anywhere" / "h.py").is_file()
        free.close()

        esc.close()

    print("ESCROW SELF-TEST PASS")
