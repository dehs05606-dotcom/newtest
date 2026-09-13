"""SENTINEL — what actually happened, and undoing it when it should not have.

The boundary in covenant.py judges an INTENTION: the arguments of a pending
call, before it runs. That is the right place to refuse, and it catches
everything whose effects can be read off the call itself.

It cannot catch what a call does once it is running. `run_command` with
`python build.py` declares nothing about the files the script writes;
`make install`, a formatter, a code generator, a test that writes fixtures —
each is one opaque step whose real effects exist only after the fact. A
containment clause refuses the unreadable ones outright, but the readable
ones pass the gate honestly and may still land somewhere the specification
forbids.

So the Sentinel judges the other end: not what was asked for, but what
occurred.

    before   the snapshot the kernel already takes for every mutating
             call (A2: no write without a committed recovery path)
    after    the same paths, re-read once the call has returned
    diff     the real added / removed / modified set
    verdict  the SAME clauses, applied to observed effects instead of
             intended ones (covenant.check_effects)

and when a clause is broken, the write does not stand: the snapshot is
materialised, the tree returns to its pre-call state, and 'sentinel.reverted'
is sealed with the clauses that caused it.

That is the difference between a rule and a boundary in time. Blocking says
the agent cannot do the thing. Reverting says that even having done it, it
did not get to keep it — which is the property that survives a step whose
effects nobody could predict.

WHAT THIS DOES NOT COVER, stated plainly because a half-guarantee that
reads like a whole one is worse than none:

  * Reversion is bounded by the snapshot. The kernel snapshots the paths a
    mutating tool names, and for `run_command` a shallow scan of the cwd.
    A write outside that set is DETECTED (the clause is checked against
    every observed effect) but cannot be rolled back, because there is no
    recorded prior state to restore. review() reports those separately as
    `unrevertable` rather than counting them as undone.
  * Effects outside the filesystem — a network call, a database write, a
    spawned daemon — are neither observed nor reversible here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .effects import DELETE, WRITE, Effect
from .kernel import EventLog

_MAX_CONTENT = 200_000      # bytes of a changed file read back for matching


@dataclass
class Review:
    """The outcome of judging one call by what it actually did."""
    observed: list[Effect] = field(default_factory=list)
    violations: list = field(default_factory=list)
    reverted: bool = False
    unrevertable: list[str] = field(default_factory=list)
    detail: str = ""

    @property
    def clean(self) -> bool:
        return not self.violations

    def to_dict(self) -> dict:
        return {"observed": len(self.observed),
                "violations": [v.to_dict() for v in self.violations],
                "reverted": self.reverted,
                "unrevertable": self.unrevertable}


class Sentinel:
    """Post-commit verification against observed effects, with rollback."""

    def __init__(self, log: EventLog, covenant, store) -> None:
        self.log = log
        self.covenant = covenant
        self.store = store
        self.reviews = 0
        self.reverts = 0
        self.undetected_escapes = 0     # violations that could not be undone

    # -- observation --------------------------------------------------------

    def observe(self, tree_before: str, paths: list[str]) -> list[Effect]:
        """The effects that really occurred, read from the filesystem.

        Derived from the recorded prior tree and the current state of the
        same paths, so a write nobody declared is still seen.
        """
        before = self.store.load_tree(tree_before) or {}
        watched = sorted(set(list(before) + [str(Path(p).resolve())
                                             for p in paths]))
        effects: list[Effect] = []
        for path in watched:
            p = Path(path)
            existed = before.get(path) is not None
            exists = p.is_file()
            if not exists and existed:
                effects.append(Effect(DELETE, path=path,
                                      reason="observed after the call"))
                continue
            if not exists:
                continue
            try:
                raw = p.read_bytes()[:_MAX_CONTENT]
            except OSError:
                continue
            digest = self.store.put_blob(raw)
            if before.get(path) == digest:
                continue                      # unchanged
            try:
                text = raw.decode("utf-8", errors="replace")
            except (UnicodeError, AttributeError):
                text = ""
            effects.append(Effect(WRITE, path=path, content=text,
                                  reason="observed after the call"))
        return effects

    # -- the verdict --------------------------------------------------------

    def review(self, tool: str, tree_before: str,
               paths: list[str]) -> Review:
        """Judge a completed call by what it did, and undo it if a clause
        was broken. `tree_before` is the snapshot taken before the call."""
        self.reviews += 1
        observed = self.observe(tree_before, paths)
        violations = self.covenant.check_effects(observed)
        review = Review(observed=observed, violations=violations)
        if not violations:
            return review

        recorded = set(self.store.load_tree(tree_before) or {})
        touched = {e.path for e in observed}
        review.unrevertable = sorted(touched - recorded)

        self.log.append("sentinel.violation",
                        {"tool": tool,
                         "violations": [v.to_dict() for v in violations],
                         "observed": len(observed),
                         "unrevertable": review.unrevertable},
                        actor="kernel")

        restored = self.store.materialise(tree_before)
        review.reverted = True
        self.reverts += 1
        if review.unrevertable:
            self.undetected_escapes += 1
        self.log.append("sentinel.reverted",
                        {"tool": tool, "tree": tree_before,
                         "restored": len(restored or {}),
                         "unrevertable": review.unrevertable},
                        actor="kernel")

        lines = [f"CovenantViolation (after the fact): this call ran, broke "
                 f"{len(violations)} clause"
                 f"{'s' if len(violations) > 1 else ''}, and was reverted."]
        for v in violations:
            lines.append(f"  {v.clause}: {v.detail}")
        if review.unrevertable:
            lines.append(
                f"  NOT REVERTED (outside the snapshot, no prior state "
                f"recorded): {', '.join(review.unrevertable[:5])}")
        review.detail = "\n".join(lines)
        return review

    def stats(self) -> dict:
        return {"reviews": self.reviews, "reverts": self.reverts,
                "unrevertable": self.undetected_escapes}


if __name__ == "__main__":
    import tempfile

    from .covenant import Covenant
    from .snapshots import SnapshotStore

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        log = EventLog(root / "log.jsonl")
        store = SnapshotStore(root / "store")
        src = root / "src"
        src.mkdir()
        (src / "a.py").write_text("x = 1\n", encoding="utf-8")

        cov = Covenant(log, f'''§1 Writes stay under {src}
@enforce confine_paths: {src}

§2 No secrets in source
@enforce forbid_content: (?i)api[_-]?key\\s*=\\s*["\\'][A-Za-z0-9]
''')
        sen = Sentinel(log, cov, store)

        # -- a compliant change stands -------------------------------------
        watched = [str(src / "a.py")]
        snap = store.take(watched)
        (src / "a.py").write_text("x = 2\n", encoding="utf-8")
        r = sen.review("run_command", snap["tree"], watched)
        assert r.clean and not r.reverted, r
        assert (src / "a.py").read_text(encoding="utf-8") == "x = 2\n"
        assert any(e.kind == WRITE for e in r.observed)

        # -- a violating change made by a step that declared nothing -------
        # the gate saw only `run_command python build.py`; the clause is
        # broken by what the script wrote, which exists only afterwards
        snap = store.take(watched)
        (src / "a.py").write_text('API_KEY = "sk-abc1"\n', encoding="utf-8")
        r = sen.review("run_command", snap["tree"], watched)
        assert not r.clean and r.reverted, r
        assert "2" in {v.clause for v in r.violations}
        # the write did not get to stand
        assert (src / "a.py").read_text(encoding="utf-8") == "x = 2\n"
        assert not r.unrevertable

        # -- a deletion is observed too ------------------------------------
        gone = Covenant(log, "§3 Nothing is ever deleted\n"
                             "@enforce forbid_effect: delete\n")
        sen2 = Sentinel(log, gone, store)
        snap = store.take(watched)
        (src / "a.py").unlink()
        r = sen2.review("run_command", snap["tree"], watched)
        assert not r.clean and r.reverted
        assert any(e.kind == DELETE for e in r.observed)
        assert (src / "a.py").is_file(), "revert did not restore the file"

        # -- a write outside the snapshot is DETECTED but cannot be undone,
        # and is reported as such rather than counted as reverted ----------
        outside = root / "outside.py"
        snap = store.take(watched)
        outside.write_text('API_KEY = "sk-zzz9"\n', encoding="utf-8")
        r = sen.review("run_command", snap["tree"],
                       watched + [str(outside)])
        assert not r.clean, "an unsnapshotted write went unnoticed"
        assert str(outside.resolve()) in r.unrevertable, r.unrevertable
        assert "NOT REVERTED" in r.detail
        assert outside.is_file()          # honestly still there
        assert sen.undetected_escapes == 1

        # -- the ledger is sealed, never silent ----------------------------
        kinds = [e.type for e in log.events()]
        assert "sentinel.violation" in kinds and "sentinel.reverted" in kinds

        # -- an empty specification reverts nothing ------------------------
        quiet = Sentinel(log, Covenant(log, ""), store)
        snap = store.take(watched)
        (src / "a.py").write_text("anything at all\n", encoding="utf-8")
        r = quiet.review("write_file", snap["tree"], watched)
        assert r.clean and not r.reverted
        assert (src / "a.py").read_text(encoding="utf-8") == "anything at all\n"

    print("SENTINEL SELF-TEST PASS")
