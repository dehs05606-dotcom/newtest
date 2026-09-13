"""CONSENT — the exception a human grants once, not the switch they leave on.

A boundary with no override is a boundary that gets turned off. Sooner or
later a clause refuses something the operator genuinely wants: a one-time
write outside the project root, a single destructive command during a
migration, a push during a release. The refusal is correct and the work is
also correct, and the system offers exactly one way through — disable the
rule, raise autonomy, edit the spec.

Each of those is unbounded in three directions at once. It applies to every
path, not the one in question. It lasts for the rest of the session, not
the moment. And it leaves no record tying the exception to the person who
wanted it. The rule survives on paper and stops holding in practice, which
is the failure mode of every security system that made the safe path
inconvenient.

So consent here is a GRANT: narrow, expiring, single-use by default, and
sealed.

    grant(clause="1", path="/etc/hosts", uses=1, ttl=300)

    * scoped     to one clause and, where given, one path or command
    * expiring   by wall-clock TTL and by number of uses
    * consumed   spending a grant is recorded; a used grant is gone
    * sealed     'consent.granted', 'consent.spent', 'consent.expired'

The effect is that "allow this once" is expressible, so nobody has to reach
for "allow everything from now on". Every grant is a bounded, auditable
hole rather than an unbounded invisible one.

WHAT A GRANT CANNOT DO. It cannot be created by the agent — grant() is
called from the approval path a human drives, never from a tool. It cannot
widen beyond the clause it names. It cannot be open-ended: a grant with no
TTL and no use limit is rejected at creation, because that is the switch
this module exists to avoid. And it is never implicit: an un-granted
refusal stays a refusal.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from .kernel import EventLog

MAX_TTL = 3600.0          # a grant may not outlive the hour it was given in
MAX_USES = 50


@dataclass
class Grant:
    """One bounded permission, given by a person."""
    id: str
    clause: str
    path: str = ""            # exact path this applies to ("" = any, in clause)
    command: str = ""         # exact command this applies to
    uses: int = 1
    used: int = 0
    expires_at: float = 0.0
    reason: str = ""
    granted_by: str = "human"
    revoked: bool = False

    def to_dict(self) -> dict:
        return {"id": self.id, "clause": self.clause, "path": self.path,
                "command": self.command, "uses": self.uses,
                "used": self.used, "expires_at": self.expires_at,
                "reason": self.reason, "granted_by": self.granted_by,
                "revoked": self.revoked}

    def live(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        return (not self.revoked
                and self.used < self.uses
                and now < self.expires_at)

    def covers(self, clause: str, path: str = "", command: str = "") -> bool:
        """Whether this grant speaks to that refusal. Scoping is by exact
        value, not by pattern: a grant is an exception to one act, and a
        glob would make it a rule change wearing an exception's clothes."""
        if clause != self.clause:
            return False
        if self.path and _same(self.path, path):
            return True
        if self.command and self.command.strip() == (command or "").strip():
            return True
        return not self.path and not self.command

    def remaining(self, now: float | None = None) -> str:
        now = time.time() if now is None else now
        left = max(0, int(self.expires_at - now))
        return f"{self.uses - self.used} use(s), {left}s"


def _same(a: str, b: str) -> bool:
    """Exact-path comparison with `.` and `..` resolved.

    A relative path is NOT considered equal to an absolute one: resolving
    it needs a working directory this module does not know, and guessing
    wrong would let a grant for one file cover a different file. Two paths
    match only when both are anchored the same way.
    """
    from pathlib import PurePath

    def norm(p: str) -> str:
        pure = PurePath(p or "")
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

    return bool(a) and norm(a) == norm(b)


class ConsentError(ValueError):
    """A grant that would not be bounded, or is not the human's to give."""


class Consent:
    """The ledger of grants, and the spending of them."""

    def __init__(self, log: EventLog) -> None:
        self.log = log
        self.grants: list[Grant] = []
        self.spent = 0

    # -- granting -----------------------------------------------------------

    def grant(self, clause: str, *, path: str = "", command: str = "",
              uses: int = 1, ttl: float = 300.0, reason: str = "",
              granted_by: str = "human") -> Grant:
        """Record a bounded exception. Called from the human approval path.

        An unbounded grant is refused at creation rather than accepted and
        quietly capped: an operator who asked for "forever" and received
        "an hour" would believe the wrong thing about their own system.
        """
        if not clause:
            raise ConsentError("a grant must name the clause it excepts")
        if uses < 1 or uses > MAX_USES:
            raise ConsentError(f"uses must be between 1 and {MAX_USES}")
        if ttl <= 0 or ttl > MAX_TTL:
            raise ConsentError(f"ttl must be between 0 and {MAX_TTL:.0f}s — "
                               f"a grant that does not expire is the "
                               f"standing override this exists to replace")
        g = Grant(id=uuid.uuid4().hex[:12], clause=clause, path=path,
                  command=command, uses=uses, used=0,
                  expires_at=time.time() + ttl, reason=reason,
                  granted_by=granted_by)
        self.grants.append(g)
        self.log.append("consent.granted", g.to_dict(), actor="human")
        return g

    def revoke(self, grant_id: str) -> bool:
        for g in self.grants:
            if g.id == grant_id and not g.revoked:
                g.revoked = True
                self.log.append("consent.revoked", {"id": g.id},
                                actor="human")
                return True
        return False

    def revoke_all(self) -> int:
        """Revoke every LIVE grant. A grant that already expired or was
        spent is left as it is: restamping it as revoked would rewrite why
        it ended, and the ledger's value is that it says what happened."""
        live = [g for g in self.grants if g.live()]
        for g in live:
            g.revoked = True
        if live:
            self.log.append("consent.revoked_all", {"count": len(live)},
                            actor="human")
        return len(live)

    # -- spending -----------------------------------------------------------

    def find(self, clause: str, path: str = "",
             command: str = "") -> Grant | None:
        """A live grant covering this refusal, or None. Read-only."""
        now = time.time()
        for g in self.grants:
            if g.live(now) and g.covers(clause, path, command):
                return g
        return None

    def spend(self, clause: str, path: str = "",
              command: str = "") -> Grant | None:
        """Consume one use of a covering grant, if there is one."""
        g = self.find(clause, path, command)
        if g is None:
            return None
        g.used += 1
        self.spent += 1
        self.log.append("consent.spent",
                        {"id": g.id, "clause": clause, "path": path,
                         "command": command, "used": g.used,
                         "uses": g.uses}, actor="kernel")
        if g.used >= g.uses:
            self.log.append("consent.exhausted", {"id": g.id},
                            actor="kernel")
        return g

    def narrow(self, violations: list, tool: str = "",
               command: str = "") -> list:
        """Return the violations no live grant covers.

        Narrowing only, like an exemption: with nothing refused there is
        nothing to forgive, so a grant can never create permission.
        """
        if not violations or not self.grants:
            return violations
        kept = []
        for v in violations:
            if self.spend(getattr(v, "clause", ""),
                          getattr(v, "path", ""), command) is None:
                kept.append(v)
        return kept

    # -- observation --------------------------------------------------------

    def live(self) -> list[Grant]:
        now = time.time()
        return [g for g in self.grants if g.live(now)]

    def report(self) -> str:
        live = self.live()
        if not self.grants:
            return "consent: no grants have been given"
        lines = [f"consent: {len(live)} live · {len(self.grants)} total · "
                 f"{self.spent} spent"]
        for g in self.grants:
            state = ("live" if g.live() else
                     "revoked" if g.revoked else
                     "exhausted" if g.used >= g.uses else "expired")
            scope = g.path or g.command or "(whole clause)"
            lines.append(f"  {g.id}  §{g.clause:<6} {state:<9} "
                         f"{scope[:34]:<36} {g.remaining()}"
                         + (f"  — {g.reason}" if g.reason else ""))
        return "\n".join(lines)


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        log = EventLog(Path(td) / "log.jsonl")
        con = Consent(log)

        # -- an unbounded grant is refused at creation ---------------------
        for bad in ({"ttl": 0}, {"ttl": MAX_TTL + 1}, {"uses": 0},
                    {"uses": MAX_USES + 1}):
            try:
                con.grant("1", **bad)
            except ConsentError:
                pass
            else:
                raise AssertionError(f"unbounded grant accepted: {bad}")
        try:
            con.grant("")
        except ConsentError:
            pass
        else:
            raise AssertionError("a grant with no clause was accepted")
        assert con.grants == []

        # -- a scoped, single-use grant ------------------------------------
        g = con.grant("1", path="/etc/hosts", uses=1, ttl=300,
                      reason="one-time migration")
        assert g.live() and con.find("1", "/etc/hosts") is g

        # it does not cover a different path…
        assert con.find("1", "/etc/passwd") is None
        # …nor a different clause
        assert con.find("2", "/etc/hosts") is None
        # dots are resolved, so an equivalent spelling of the SAME path matches
        assert con.find("1", "/etc/./hosts") is not None
        assert con.find("1", "/etc/sub/../hosts") is not None
        # but a relative path is not assumed to be that absolute one —
        # resolving it needs a cwd, and guessing would let this grant
        # cover a different file entirely
        assert con.find("1", "etc/hosts") is None

        # -- spending consumes it ------------------------------------------
        assert con.spend("1", "/etc/hosts") is g
        assert g.used == 1 and not g.live()
        assert con.spend("1", "/etc/hosts") is None, "a used grant was reused"

        # -- multi-use grants count down -----------------------------------
        g2 = con.grant("3", command="rm -rf build", uses=2, ttl=300)
        assert con.spend("3", command="rm -rf build") is g2
        assert con.spend("3", command="rm -rf build") is g2
        assert con.spend("3", command="rm -rf build") is None
        # and an unmatching command never touched it
        g3 = con.grant("3", command="rm -rf build", uses=1, ttl=300)
        assert con.spend("3", command="rm -rf dist") is None
        assert g3.used == 0

        # -- expiry is real -------------------------------------------------
        g4 = con.grant("4", uses=5, ttl=300)
        g4.expires_at = time.time() - 1
        assert not g4.live() and con.find("4") is None

        # -- revocation ----------------------------------------------------
        g5 = con.grant("5", uses=5, ttl=300)
        assert con.revoke(g5.id) and not g5.live()
        assert con.revoke("nonexistent") is False
        con.grant("6", uses=5, ttl=300)
        assert con.revoke_all() >= 1 and con.live() == []

        # -- narrowing: forgives only what a grant covers -------------------
        from .covenant import Violation
        con2 = Consent(log)
        con2.grant("1", path="/etc/hosts", uses=1, ttl=300)
        vs = [Violation("1", "confine_paths", "outside", path="/etc/hosts"),
              Violation("2", "forbid_content", "secret", path="/etc/hosts")]
        left = con2.narrow(vs, "write_file")
        assert [v.clause for v in left] == ["2"], left

        # narrowing can never CREATE permission
        assert con2.narrow([], "write_file") == []

        # -- a whole-clause grant covers any path in that clause -----------
        con3 = Consent(log)
        con3.grant("7", uses=3, ttl=300, reason="release window")
        assert con3.find("7", "/anywhere") is not None
        assert con3.find("8", "/anywhere") is None

        # -- every grant and every spend is sealed -------------------------
        kinds = {e.type for e in log.events()}
        assert {"consent.granted", "consent.spent", "consent.exhausted",
                "consent.revoked", "consent.revoked_all"} <= kinds, kinds
        granted = [e for e in log.events() if e.type == "consent.granted"]
        assert granted[0].actor == "human", "a grant was not attributed"

        # -- the report distinguishes every state --------------------------
        rep = con.report()
        for state in ("exhausted", "expired", "revoked"):
            assert state in rep, (state, rep)

    print("CONSENT SELF-TEST PASS")
