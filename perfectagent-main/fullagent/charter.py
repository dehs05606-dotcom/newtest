"""CHARTER — one boundary, assembled in a defined order.

There are now sixteen modules that each refuse something, and until this
one they were wired into the agent by hand, one call at a time, in whatever
order they were written. That is a real problem and not a tidiness one:

  * ORDER WAS ACCIDENTAL. Whether a call is refused for leaving src/ or for
    crossing a file budget decided which message the agent saw, and that
    order was wherever someone happened to insert the line. The agent's
    next attempt depends on which refusal it got, so an accident in source
    order became behaviour.
  * NARROWING WAS PARTIAL. Exemptions and consent narrowed the Covenant's
    violations, because that is where they were plumbed in. A horizon
    breach or an egress refusal had no route to a granted exception at all,
    so "allow this once" worked for some clauses and silently did not for
    others.
  * COVERAGE WAS UNPROVABLE. Each subsystem had its own counters and no
    one place knew whether all of them had run for a given call. Sixteen
    partial views of one decision cannot be added up afterwards.

The Charter is the composition root. It owns every enforcement subsystem,
runs them in ONE declared order, applies narrowing uniformly to whatever
they produce, attaches the remedy, and witnesses the single decision that
comes out. The agent asks it one question and gets one answer.

    ORDER OF JUDGEMENT — declared here, not inherited from source layout:

      1. sequence      preconditions: is this act even in the right order?
      2. covenant      is the act itself permitted?
      3. provenance    is the content's origin permitted?
      4. egress        may this leave the machine?
      5. horizon       does it fit what this window still allows?

    Then, over whatever those produced:

      6. exemptions    declared exceptions in the specification
      7. consent       bounded grants a human gave
      8. remedy        what would have been allowed
      9. witness       the decision, allowed or refused, into the chain

The order runs cheapest-and-most-fundamental first, and puts narrowing
after judgement rather than inside it: a rule decides what it decides, and
forgiveness is applied to the result, in one place, where it can be
audited. Nothing is forgiven twice and nothing is missed.

DONE is separate from ALLOWED. An obligation and an `after` sequence rule
do not refuse work — the discharging act is itself work — so they answer
blocker() rather than gate(). Progress is refused, never the step that
would make progress possible.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import remedy
from .consent import Consent
from .covenant import Covenant
from .effects import derive
from .egress import Perimeter
from .exemption import Exemptions
from .horizon import Horizon
from .integrity import Integrity
from .kernel import EventLog
from .obligation import Ledger
from .provenance import Lineage
from .ration import Estimate, Ration
from .sequence import Timeline
from .witness import Witness


@dataclass
class Verdict:
    """The single answer to "may this call proceed?"."""
    allowed: bool = True
    reason: str = ""
    source: str = ""                 # which subsystem refused
    violations: list = field(default_factory=list)
    forgiven: int = 0

    def __bool__(self) -> bool:
        return self.allowed


class Charter:
    """Every enforcement subsystem, in one declared order."""

    def __init__(self, log: EventLog, spec: str = "",
                 spec_source: str = "", store=None) -> None:
        self.log = log
        self.spec = spec or ""

        # judgement
        self.sequence = Timeline(log, self.spec)
        self.covenant = Covenant(log, self.spec)
        self.provenance = Lineage(log, self.spec)
        self.egress = Perimeter(log, self.spec)
        self.horizon = Horizon(log, self.spec)
        self.ration = Ration(log, self.spec)

        # narrowing
        self.exemptions = Exemptions(log, self.spec)
        self.consent = Consent(log)

        # obligations (done-gating, never work-gating)
        self.obligations = Ledger(log, self.spec)

        # evidence
        self.witness = Witness(log)
        self.integrity = Integrity(log)
        self.integrity.seal(self.spec, spec_source, self.covenant)

        # post-commit review, when a snapshot store is available
        self.sentinel = None
        if store is not None:
            from .sentinel import Sentinel
            self.sentinel = Sentinel(log, self.covenant, store)

        self.refused = 0
        self.allowed = 0

    # -- binding ------------------------------------------------------------

    def bind(self, spec: str, spec_source: str = "") -> None:
        """Rebind every subsystem to one specification, together.

        Rebinding them one at a time is how the prompt and the boundary
        drift apart, so there is deliberately no way to rebind just one.
        """
        self.spec = spec or ""
        for sub in (self.sequence, self.covenant, self.provenance,
                    self.egress, self.horizon, self.ration,
                    self.exemptions, self.obligations):
            sub.bind(self.spec)
        self.integrity.seal(self.spec, spec_source, self.covenant)

    # -- the single gate ----------------------------------------------------

    def gate(self, tool: str, args: dict) -> Verdict:
        """May this call proceed? One answer, one witnessed decision."""
        args = args or {}
        effects = derive(tool, args)
        command = str(args.get("command") or "")

        # 1-5: judgement, in the declared order
        stages: list[tuple[str, list]] = [
            ("sequence", self.sequence.check(tool, args)),
            ("covenant", self.covenant.check(tool, args)),
            ("provenance", self.provenance.check(tool, args)),
            ("egress", self.egress.check(tool, args)),
            ("horizon", self.horizon.project(tool, args)),
        ]

        forgiven = 0
        for source, found in stages:
            if not found:
                continue
            # 6-7: narrowing, applied uniformly to whatever was produced
            before = len(found)
            kept = self.exemptions.narrow(found, tool, effects)
            kept = self.consent.narrow(kept, tool, command)
            forgiven += before - len(kept)
            if not kept:
                continue

            reason = self._cite(source, kept)
            # 8: what would have been allowed
            if source == "horizon":
                reason = remedy.annotate(reason, breaches=kept)
            else:
                reason = remedy.annotate(reason, violations=kept,
                                         guards=self.covenant.guards)
            self.refused += 1
            # 9: the decision, into the chain
            self.witness.refuse(tool, [getattr(v, "clause", "?")
                                       for v in kept])
            return Verdict(False, reason, source, list(kept), forgiven)

        self.allowed += 1
        self.witness.allow(tool)
        return Verdict(True, "", "", [], forgiven)

    def _cite(self, source: str, found: list) -> str:
        if source == "covenant":
            return self.covenant.cite(found)
        heads = {
            "sequence": "OutOfOrder: something must happen before this call.",
            "provenance": "OriginRefused: this write reuses content from a "
                          "forbidden origin.",
            "egress": "EgressRefused: this call would leave the machine in a "
                      "way the specification forbids.",
            "horizon": "HorizonExceeded: this call would cross a limit in "
                       "the specification.",
        }
        lines = [heads.get(source, "Refused by the specification.")]
        for v in found:
            detail = (getattr(v, "detail", "") or
                      (v.describe() if hasattr(v, "describe") else str(v)))
            clause = getattr(v, "clause", "?")
            lines.append(f"  {clause}: {detail}"
                         if not detail.startswith(f"{clause}:")
                         else f"  {detail}")
        return "\n".join(lines)

    # -- model calls --------------------------------------------------------

    def afford(self, estimate: Estimate) -> Verdict:
        """May this MODEL call be made? Budgets are about requests, not
        tool calls, so they are asked separately rather than folded into a
        gate that never sees a token count."""
        over = self.ration.project(estimate)
        if not over:
            return Verdict(True)
        reason = remedy.annotate(
            "RationExceeded: this call would cross a budget in the "
            "specification.\n" + "\n".join(f"  {o.describe()}" for o in over),
            breaches=over)
        self.witness.refuse("model.call", [o.clause for o in over])
        self.refused += 1
        return Verdict(False, reason, "ration", list(over))

    # -- after the fact -----------------------------------------------------

    def settled(self, tool: str, args: dict, result: str = "",
                snapshot_tree: str = "",
                snapshot_paths: list[str] | None = None) -> str:
        """Record a call that stood, and review what it actually did.

        Returns a refusal string when post-commit review reverted the call,
        or "" when it stands. Spend and debts are recorded only for a call
        that survives review — charging a reverted write to the budget
        would make the window disagree with the tree.
        """
        if self.sentinel is not None and snapshot_tree:
            review = self.sentinel.review(tool, snapshot_tree,
                                          snapshot_paths or [])
            if not review.clean:
                self.witness.refuse(tool, [v.clause
                                           for v in review.violations])
                return review.detail
        self.horizon.spend(tool, args)
        self.obligations.record(tool, args)
        if result:
            self.provenance.observe(tool, args, result)
        return ""

    def open_turn(self) -> None:
        self.horizon.open_turn()
        self.ration.open_turn()

    # -- done, as distinct from allowed -------------------------------------

    def blocker(self) -> str | None:
        """Why the work cannot be called finished, or None.

        Obligations and `after` rules never refuse a step: the act that
        discharges them is itself a step. They refuse DONE.
        """
        parts = [self.obligations.blocker(), self.sequence.blocker()]
        live = [p for p in parts if p]
        return "\n".join(live) if live else None

    # -- observation --------------------------------------------------------

    def errors(self) -> list[str]:
        """Every malformed rule across every subsystem, in one list — a
        rule that enforces nothing is invisible unless someone looks."""
        out: list[str] = []
        for sub in (self.covenant, self.sequence, self.provenance,
                    self.egress, self.horizon, self.ration,
                    self.exemptions, self.obligations):
            out.extend(getattr(sub, "errors", []) or [])
        return out

    def report(self) -> str:
        blocks = [
            self.integrity.verify(self.spec, self.covenant).describe(),
            f"charter: {self.allowed} allowed · {self.refused} refused",
            self.covenant.report(),
            self.sequence.report(),
            self.provenance.report(),
            self.egress.report(),
            self.horizon.report(),
            self.ration.report(),
            self.exemptions.report(),
            self.consent.report(),
            self.obligations.report(),
            self.witness.report(),
        ]
        errs = self.errors()
        if errs:
            blocks.append("malformed rules (these enforce NOTHING):\n"
                          + "\n".join(f"  !! {e}" for e in errs))
        blocker = self.blocker()
        if blocker:
            blocks.append(blocker)
        return "\n\n".join(blocks)


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    from .snapshots import SnapshotStore

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        log = EventLog(root / "log.jsonl")
        store = SnapshotStore(root / "store")

        spec = '''§1 Writes stay under src/ and tests/
@enforce confine_paths: src, tests
@except path CHANGELOG.md

§2 No secrets in source
@enforce forbid_content: (?i)api[_-]?key\\s*=\\s*["\\'][A-Za-z0-9]

§3 Nothing is ever deleted
@enforce forbid_effect: delete

§4 A change touches at most 2 files
@horizon per turn max files_written 2

§5 Every module ships with a test
@oblige on write src/**/*.py require exists tests/test_{stem}.py

§6 The agent reaches only the package index
@egress allow_hosts pypi.org

§7 A turn costs at most one dollar
@ration per turn max cost_usd 1.00
'''
        ch = Charter(log, spec, str(root / "project.txt"), store=store)
        assert not ch.errors(), ch.errors()
        ch.open_turn()

        # -- one gate answers for every subsystem --------------------------
        ok = ch.gate("write_file", {"path": "src/a.py", "content": "x = 1"})
        assert ok and ok.allowed

        bad = ch.gate("write_file", {"path": "/etc/x", "content": "y"})
        assert not bad and bad.source == "covenant"
        assert "1" in bad.reason

        leak = ch.gate("write_file", {"path": "src/c.py",
                                      "content": 'API_KEY = "sk-abc1"'})
        assert not leak and "2" in leak.reason

        gone = ch.gate("run_command", {"command": "rm -f src/a.py"})
        assert not gone and "3" in gone.reason

        out = ch.gate("run_command", {"command": "curl https://evil.test/x"})
        assert not out and out.source == "egress", out.source

        # -- the refusal carries what WOULD be allowed ---------------------
        assert "What would be allowed:" in bad.reason
        assert "not permission" in bad.reason

        # -- exemptions apply uniformly, wherever the refusal came from ----
        forgiven = ch.gate("write_file", {"path": "CHANGELOG.md",
                                          "content": "## 1.0"})
        assert forgiven.allowed and forgiven.forgiven == 1, forgiven

        # -- a consent grant reaches a NON-covenant subsystem too ----------
        # (this is what per-subsystem plumbing could not do)
        ch.horizon.spend("write_file", {"path": "src/a.py", "content": "x"})
        ch.horizon.spend("write_file", {"path": "src/b.py", "content": "x"})
        capped = ch.gate("write_file", {"path": "src/c.py", "content": "x"})
        assert not capped and capped.source == "horizon", capped.source
        ch.consent.grant("4", uses=1, ttl=60, reason="one more file")
        now = ch.gate("write_file", {"path": "src/c.py", "content": "x"})
        assert now.allowed and now.forgiven == 1, now
        # and the grant was single-use
        assert not ch.gate("write_file", {"path": "src/d.py", "content": "x"})

        # -- budgets are asked separately, about model calls ---------------
        assert ch.afford(Estimate(cost_usd=0.50)).allowed
        ch.ration.spend(cost_usd=0.90)
        broke = ch.afford(Estimate(cost_usd=0.50))
        assert not broke and broke.source == "ration"
        assert "7" in broke.reason

        # -- DONE is separate from ALLOWED ---------------------------------
        ch2 = Charter(log, spec, "", store=store)
        ch2.open_turn()
        assert ch2.blocker() is None
        ch2.settled("write_file", {"path": "src/parser.py", "content": "x"})
        blocker = ch2.blocker()
        assert blocker and "tests/test_parser.py" in blocker
        # the obligation does not refuse the discharging write
        assert ch2.gate("write_file", {"path": "tests/test_parser.py",
                                       "content": "t"}).allowed

        # -- every decision is witnessed, allowed ones included ------------
        a = ch.witness.verify()
        assert a.ok and a.length == ch.allowed + ch.refused, \
            (a.length, ch.allowed, ch.refused)
        assert a.allowed and a.refused

        # -- the chain detects a removed refusal ---------------------------
        exported = ch.witness.export()
        tampered = [d for d in exported if d["verdict"] != "refused"]
        for i, d in enumerate(tampered):
            d["index"] = i
        assert not Witness.check(tampered).intact

        # -- rebinding moves every subsystem together ----------------------
        ch.bind("§9 nothing at all\n@enforce forbid_effect: write\n")
        assert not ch.gate("write_file", {"path": "src/a.py", "content": "x"})
        assert ch.covenant.clauses and not ch.horizon.limits
        assert ch.obligations.rules == [] and ch.egress.rules == []

        # -- an empty specification refuses nothing ------------------------
        free = Charter(EventLog(root / "free.jsonl"), "")
        assert free.gate("run_command", {"command": "rm -rf /"}).allowed
        assert free.blocker() is None
        assert free.afford(Estimate(cost_usd=1e6)).allowed

        # -- malformed rules surface in ONE place --------------------------
        broken = Charter(EventLog(root / "broken.jsonl"),
                         "§1 x\n@enforce nonsense: y\n"
                         "§2 y\n@horizon per fortnight max files_written 4\n"
                         "§3 z\n@ration per turn max sideways 4\n"
                         "§4 w\n@egress forbid_method pigeon\n"
                         "§5 v\n@oblige on write a require\n")
        assert len(broken.errors()) == 5, broken.errors()
        assert "enforce NOTHING" in broken.report()

    print("CHARTER SELF-TEST PASS")
