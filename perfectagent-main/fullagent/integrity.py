"""INTEGRITY — the specification the model reads and the one it is held to
must be the same bytes.

Every mechanism in this package rests on one unstated assumption: that the
text delivered as the system prompt and the text parsed into clauses came
from the same place and still agree. Nothing so far checks it, and there
are ordinary ways for them to diverge with no error anywhere:

  * The Covenant is bound to one text and the prompt carries another.
    Rebinding one without the other leaves the agent reading rules it is
    not held to, or held to rules it was never shown.
  * A clause is added to the spec but carries no @enforce. It reads as
    binding and enforces nothing.
  * A caller passes a spec that is not the one in systemprompt.SPEC, so the
    boundary silently governs something other than what shipped.

The specification is now a constant in systemprompt.py rather than a file,
which removes the worst of these on its own: there is no path to resolve,
no environment variable, and nothing to swap between reads. The module's
own bytes are content-addressed and refused to the agent by sanctum.py, so
"has the specification changed under us?" is that module's question, not
this one. What remains here is whether the text the model received and the
clauses it is held to are the same text — which no amount of file
protection can answer.

Each of these is quiet. The system keeps working; only its guarantee is
gone. A guarantee that fails silently is the most expensive kind, because
the belief it created outlives it.

So the specification is content-addressed and its identity checked, not
assumed:

    source      where the bytes came from
    digest      sha256 of the exact bytes
    clauses     how many were parsed, and how many bind
    agreement   prompt bytes == boundary bytes == file on disk

verify() answers all four and names precisely which one broke. It never
repairs anything on its own: a specification that silently reloaded itself
mid-session would be a worse failure than a stale one, because the rules
would change under an agent already part-way through acting on them.
Drift is REPORTED and the reconciliation is an explicit act (/prompt
reload), which is itself sealed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from .kernel import EventLog

OK = "ok"
DRIFTED = "drifted"      # disk no longer matches what is loaded
SPLIT = "split"          # prompt and boundary disagree with each other
ABSENT = "absent"        # no specification at all


def digest(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def short(text: str) -> str:
    return digest(text)[:16]


@dataclass
class Seal:
    """The identity of a specification at a moment in time."""
    source: str = ""
    digest: str = ""
    chars: int = 0
    clauses: int = 0
    enforced: int = 0

    def to_dict(self) -> dict:
        return {"source": self.source, "digest": self.digest,
                "chars": self.chars, "clauses": self.clauses,
                "enforced": self.enforced}


@dataclass
class Report:
    state: str
    seal: Seal
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        # Anything worth reporting means the guarantee is not intact. A
        # report that read "ok" while carrying problems would be the exact
        # silent-failure this module exists to remove.
        return self.state == OK and not self.problems

    def describe(self) -> str:
        if self.state == ABSENT:
            return ("integrity: no specification is loaded — the boundary "
                    "governs nothing and 'master' is the compact prompt")
        head = (f"integrity: {self.seal.chars:,} chars · {self.seal.clauses} "
                f"clauses ({self.seal.enforced} enforced) · "
                f"{self.seal.digest[:16]} · {self.seal.source}")
        if self.ok:
            return head + "\n  prompt, boundary and file on disk agree"
        return head + "\n  " + "\n  ".join(self.problems)


class Integrity:
    """Content-addressed identity for the live specification."""

    def __init__(self, log: EventLog) -> None:
        self.log = log
        self.sealed: Seal | None = None

    # -- sealing ------------------------------------------------------------

    def seal(self, spec: str, source: str, covenant=None) -> Seal:
        """Record the identity of the specification now in force."""
        s = Seal(source=source or "", digest=digest(spec), chars=len(spec))
        if covenant is not None:
            s.clauses = len(covenant.clauses)
            s.enforced = len(covenant.enforced_clauses)
        self.sealed = s
        self.log.append("integrity.sealed", s.to_dict(), actor="kernel")
        return s

    # -- verification -------------------------------------------------------

    def verify(self, prompt_spec: str, covenant=None,
               source: str = "") -> Report:
        """Check that the prompt's bytes, the boundary's clauses and the
        file on disk are still one specification."""
        src = source or (self.sealed.source if self.sealed else "")
        s = Seal(source=src, digest=digest(prompt_spec),
                 chars=len(prompt_spec))
        if covenant is not None:
            s.clauses = len(covenant.clauses)
            s.enforced = len(covenant.enforced_clauses)

        if not prompt_spec.strip():
            return Report(ABSENT, s)

        problems: list[str] = []
        state = OK

        # 1. does the boundary hold the same text the prompt carries?
        if covenant is not None:
            rebuilt = _covenant_digest(covenant)
            if rebuilt and rebuilt != _clause_digest(prompt_spec, covenant):
                problems.append(
                    "the boundary's clauses were not parsed from the "
                    "prompt's bytes — reload both with /prompt reload")
                state = SPLIT

        # 2. does the file on disk still match what is loaded?
        if src:
            p = Path(src)
            try:
                on_disk = p.read_text(encoding="utf-8")
            except OSError as e:
                problems.append(f"the specification file is unreadable "
                                f"({e.__class__.__name__}) — the loaded copy "
                                f"is still in force")
                state = DRIFTED if state == OK else state
            else:
                if digest(on_disk) != s.digest:
                    problems.append(
                        f"{src} has changed since it was loaded "
                        f"({len(on_disk):,} chars on disk vs "
                        f"{s.chars:,} in force) — the agent is being held "
                        f"to the loaded copy, not the edited one")
                    state = DRIFTED if state == OK else state

        # 3. did it change identity since it was sealed?
        if self.sealed and self.sealed.digest != s.digest:
            problems.append(
                f"the specification changed within this session "
                f"({self.sealed.digest[:16]} -> {s.digest[:16]})")
            state = DRIFTED if state == OK else state

        # 4. a specification that binds nothing is worth saying out loud
        if covenant is not None and s.clauses and not s.enforced:
            problems.append(
                f"{s.clauses} clauses are loaded and none carries an "
                f"@enforce rule — the specification is prose to the "
                f"boundary")

        report = Report(state, s, problems)
        if not report.ok:
            self.log.append("integrity.drift",
                            {**s.to_dict(), "state": state,
                             "problems": problems}, actor="kernel")
        return report


def _clause_digest(spec: str, covenant) -> str:
    """What the boundary WOULD hold if it were parsed from `spec`."""
    from .covenant import parse_clauses
    clauses, _ = parse_clauses(spec)
    return _digest_clauses(clauses)


def _covenant_digest(covenant) -> str:
    return _digest_clauses(covenant.clauses)


def _digest_clauses(clauses) -> str:
    h = hashlib.sha256()
    for c in clauses:
        h.update(c.fingerprint.encode("utf-8"))
        for g in c.guards:
            h.update(repr(sorted(g.to_dict().items())).encode("utf-8"))
    return h.hexdigest()


if __name__ == "__main__":
    import tempfile

    from .covenant import Covenant

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        log = EventLog(root / "log.jsonl")
        spec_file = root / "project.txt"
        spec = ("§1 Writes stay under src\n"
                "@enforce confine_paths: src\n"
                "§2 Prose only, no rule here.\n")
        spec_file.write_text(spec, encoding="utf-8")

        cov = Covenant(log, spec)
        integ = Integrity(log)
        sealed = integ.seal(spec, str(spec_file), cov)
        assert sealed.clauses == 2 and sealed.enforced == 1
        assert len(sealed.digest) == 64

        # -- everything agrees ---------------------------------------------
        r = integ.verify(spec, cov, str(spec_file))
        assert r.ok, r.describe()
        assert "agree" in r.describe()

        # -- the file is edited mid-session: drift, reported not repaired --
        spec_file.write_text(spec + "§3 A new rule nobody loaded.\n",
                             encoding="utf-8")
        r = integ.verify(spec, cov, str(spec_file))
        assert r.state == DRIFTED, r.describe()
        assert "has changed since it was loaded" in r.describe()
        # the loaded copy is untouched — nothing reloaded itself
        assert len(cov.clauses) == 2

        # after an explicit reconcile, they agree again
        newspec = spec_file.read_text(encoding="utf-8")
        cov.bind(newspec)
        integ.seal(newspec, str(spec_file), cov)
        assert integ.verify(newspec, cov, str(spec_file)).ok

        # -- prompt and boundary parsed from different bytes ---------------
        other = Covenant(log, "§9 something else entirely\n"
                              "@enforce forbid_effect: delete\n")
        r = integ.verify(newspec, other, str(spec_file))
        assert r.state == SPLIT, r.describe()
        assert "not parsed from the prompt's bytes" in r.describe()

        # -- a specification that binds nothing says so --------------------
        prose = "§1 Be careful.\n§2 Write good code.\n"
        pf = root / "prose.txt"
        pf.write_text(prose, encoding="utf-8")
        pcov = Covenant(log, prose)
        pin = Integrity(log)
        pin.seal(prose, str(pf), pcov)
        r = pin.verify(prose, pcov, str(pf))
        assert not r.ok and "prose to the boundary" in r.describe()

        # -- no specification at all ---------------------------------------
        r = Integrity(log).verify("", Covenant(log, ""), "")
        assert r.state == ABSENT
        assert "governs nothing" in r.describe()

        # -- a missing file is reported, and the loaded copy stays in force
        spec_file.unlink()
        r = integ.verify(newspec, cov, str(spec_file))
        assert r.state == DRIFTED and "unreadable" in r.describe()
        assert len(cov.clauses) == 3, "the boundary lost clauses on an error"

        # -- drift is sealed, never silent ---------------------------------
        assert any(e.type == "integrity.drift" for e in log.events())
        assert any(e.type == "integrity.sealed" for e in log.events())

    print("INTEGRITY SELF-TEST PASS")
