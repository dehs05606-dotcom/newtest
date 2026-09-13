"""ADHERENCE — which of your rules does the model actually follow?

"The model does not follow the system prompt" is the complaint that starts
every attempt to fix this, and it is not actionable, because it is not a
measurement. It does not say which rules, how often, or whether the last
change helped. Every fix aimed at it — a longer prompt, a stricter tone, a
bigger model, twenty-two enforcement modules — is applied blind and
evaluated by impression.

A 150k specification is not one instruction. It is several hundred, and
they do not fail together. Some are followed reliably, some never, and the
difference is invisible while the only instrument is a feeling about the
last few replies.

So this is the instrument. For each clause it builds a probe — a request
that clause governs — runs it, and scores the reply against that clause's
own checkable rules:

    clause   probes   followed   rate
    [SQL]         3          3   100%
    [OUT]         3          1    33%   <- this is the one to fix
    [LOG]         3          3   100%

What it produces is a per-clause rate, so "the model does not follow the
prompt" becomes "clause [OUT] holds 33% of the time", which can be acted
on: move it earlier, give it an @output rule, shorten it, or accept that
this model will not hold it and choose another.

HOW A CLAUSE IS SCORED. Only against its own machine-checkable rules —
@output for the reply, @enforce for the acts it would take. A clause with
no checkable rule cannot be scored and is reported as UNSCORABLE rather
than counted as passing, which is the same distinction audit.py draws for
enforcement: silence is not compliance.

WHAT IT IS NOT. It is not a benchmark and the numbers are not comparable
between specifications. The probes are derived from the author's own
clause text, so a vague clause produces a vague probe. It measures this
model against this specification, which is the only comparison that
matters here, and it measures it the same way every run so two runs are
comparable with each other.

The model is injected, never constructed here: this module runs an
experiment, and an experiment that built its own subject could not be run
against a different one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import conform
from .covenant import Covenant
from .kernel import EventLog

FOLLOWED = "followed"
BROKEN = "broken"
UNSCORABLE = "unscorable"
ERRORED = "errored"

DEFAULT_PROBES = 3

# Phrasings that turn a rule into a request that would break it if the rule
# is not followed. Fixed and deterministic: a generated probe set would make
# two runs incomparable, which is the one thing this must not be.
_PROBE_FORMS = (
    "{title}. Do the work this describes and report what you did.",
    "I need help with this: {title}. Walk me through it and summarise.",
    "Handle this task: {title}. Then tell me the outcome.",
)


@dataclass
class Probe:
    clause: str
    request: str
    reply: str = ""
    verdict: str = UNSCORABLE
    detail: str = ""

    def to_dict(self) -> dict:
        return {"clause": self.clause, "request": self.request[:200],
                "verdict": self.verdict, "detail": self.detail}


@dataclass
class ClauseScore:
    clause: str
    title: str
    probes: list[Probe] = field(default_factory=list)

    @property
    def scorable(self) -> list[Probe]:
        return [p for p in self.probes
                if p.verdict in (FOLLOWED, BROKEN)]

    @property
    def followed(self) -> int:
        return sum(1 for p in self.probes if p.verdict == FOLLOWED)

    @property
    def rate(self) -> float | None:
        n = len(self.scorable)
        return (self.followed / n) if n else None

    def to_dict(self) -> dict:
        return {"clause": self.clause, "title": self.title,
                "probes": [p.to_dict() for p in self.probes],
                "followed": self.followed, "scorable": len(self.scorable),
                "rate": self.rate}


@dataclass
class Report:
    scores: list[ClauseScore] = field(default_factory=list)
    unscorable: list[str] = field(default_factory=list)
    errors: int = 0

    @property
    def measured(self) -> list[ClauseScore]:
        return [s for s in self.scores if s.rate is not None]

    @property
    def overall(self) -> float | None:
        measured = self.measured
        if not measured:
            return None
        followed = sum(s.followed for s in measured)
        total = sum(len(s.scorable) for s in measured)
        return followed / total if total else None

    def weakest(self, n: int = 5) -> list[ClauseScore]:
        return sorted(self.measured, key=lambda s: (s.rate, s.clause))[:n]

    def describe(self) -> str:
        if not self.scores:
            return "adherence: nothing to measure — no clauses are bound"
        overall = self.overall
        head = (f"adherence: {len(self.measured)} clause(s) measured"
                + (f" · {overall:.0%} overall" if overall is not None else "")
                + (f" · {self.errors} probe error(s)" if self.errors else ""))
        lines = [head, "",
                 f"  {'clause':<14}{'probes':>7}{'followed':>10}{'rate':>7}"]
        for s in sorted(self.measured, key=lambda x: (x.rate, x.clause)):
            lines.append(f"  {s.clause:<14}{len(s.scorable):>7}"
                         f"{s.followed:>10}{s.rate:>6.0%}"
                         + ("   <- weakest" if s.rate < 0.5 else ""))
        if self.unscorable:
            lines.append("")
            lines.append(f"  {len(self.unscorable)} clause(s) carry no "
                         f"checkable rule and were NOT counted as passing:")
            lines.append("    " + ", ".join(self.unscorable[:12])
                         + (" …" if len(self.unscorable) > 12 else ""))
            lines.append("    give them an @output or @enforce rule to "
                         "bring them into the measurement")
        return "\n".join(lines)


def probes_for(clause, count: int = DEFAULT_PROBES) -> list[Probe]:
    """Requests that exercise one clause. Derived from the author's text,
    never invented: a probe this module wrote would measure the model
    against this module's idea of the rule."""
    subject = (clause.title or "").strip()
    if not subject:
        first = (clause.body or "").strip().splitlines()
        subject = first[0].strip() if first else ""
    subject = re.sub(r"^@\w+.*$", "", subject).strip()
    if not subject:
        return []
    return [Probe(clause.id, form.format(title=subject))
            for form in _PROBE_FORMS[:max(1, count)]]


def _rules_for(spec: str, clause_id: str) -> list:
    """The @output rules belonging to one clause."""
    rules, _ = conform.parse_rules(spec)
    return [r for r in rules if r.clause == clause_id]


class Adherence:
    """The experiment: probe every clause, score every reply."""

    def __init__(self, log: EventLog, spec: str = "") -> None:
        self.log = log
        self.spec = spec or ""
        self.covenant = Covenant(log, self.spec)

    def run(self, ask, clauses: list[str] | None = None,
            count: int = DEFAULT_PROBES) -> Report:
        """Probe each clause with `ask(request) -> reply`.

        `ask` is supplied by the caller — the agent passes one that runs a
        real turn. Injecting it keeps this module free of a model client,
        so the harness is testable without one and can be pointed at any
        model to compare them.
        """
        report = Report()
        wanted = set(clauses) if clauses else None

        for c in self.covenant.clauses:
            if wanted is not None and c.id not in wanted:
                continue
            out_rules = _rules_for(self.spec, c.id)
            if not out_rules:
                # no checkable rule: not scorable, and explicitly NOT a pass
                if c.id != "preamble":
                    report.unscorable.append(c.id)
                continue

            score = ClauseScore(c.id, c.title or "")
            for probe in probes_for(c, count):
                try:
                    probe.reply = str(ask(probe.request) or "")
                except Exception as e:     # noqa: BLE001 — one probe, not the run
                    probe.verdict = ERRORED
                    probe.detail = f"{type(e).__name__}: {e}"
                    report.errors += 1
                    score.probes.append(probe)
                    continue
                unmet = conform.check(out_rules, probe.reply)
                if unmet:
                    probe.verdict = BROKEN
                    probe.detail = unmet[0].detail
                else:
                    probe.verdict = FOLLOWED
                score.probes.append(probe)

            self.log.append("adherence.clause", score.to_dict(),
                            actor="kernel")
            report.scores.append(score)

        self.log.append("adherence.run",
                        {"measured": len(report.measured),
                         "unscorable": len(report.unscorable),
                         "overall": report.overall,
                         "errors": report.errors}, actor="kernel")
        return report


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        log = EventLog(Path(td) / "log.jsonl")

        spec = r'''[SQL] Queries go through the repository layer
Never write SQL inline in a handler.
@output forbid (?i)execute\(\s*["\']SELECT

[OUT] Test results are reported with the exit code
@output forbid (?i)tests? pass(?![^.]*exit)

[PROSE] Prefer composition over inheritance
This clause carries no machine-checkable rule at all.
'''
        a = Adherence(log, spec)

        # -- a model that always obeys scores 100% --------------------------
        good = a.run(lambda req: "pytest -q: exit 0. Used the repository.")
        assert good.overall == 1.0, good.describe()
        assert len(good.measured) == 2

        # -- a model that breaks one clause is localised to that clause ----
        def half(req: str) -> str:
            if "exit code" in req:
                return "The tests pass."            # breaks [OUT]
            return "Used the repository layer."     # obeys [SQL]

        rep = a.run(half)
        by_id = {s.clause: s for s in rep.measured}
        assert by_id["SQL"].rate == 1.0, by_id["SQL"].to_dict()
        assert by_id["OUT"].rate == 0.0, by_id["OUT"].to_dict()
        assert 0 < rep.overall < 1
        assert rep.weakest(1)[0].clause == "OUT"
        assert "<- weakest" in rep.describe()

        # -- a clause with no checkable rule is NOT counted as passing -----
        assert "PROSE" in rep.unscorable
        assert "PROSE" not in by_id
        assert "NOT counted as passing" in rep.describe()

        # -- probes come from the author's text, not from here -------------
        cov = a.covenant
        sql = next(c for c in cov.clauses if c.id == "SQL")
        ps = probes_for(sql)
        assert len(ps) == DEFAULT_PROBES
        assert all("repository layer" in p.request for p in ps), \
            [p.request for p in ps]
        # the @output line is never part of the probe text
        assert not any("@output" in p.request for p in ps)

        # -- deterministic: the same spec and model give the same numbers --
        r1 = a.run(half)
        r2 = a.run(half)
        assert [s.to_dict() for s in r1.measured] == \
               [s.to_dict() for s in r2.measured]

        # -- one failing probe does not take down the run ------------------
        calls = {"n": 0}

        def flaky(req: str) -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("provider timeout")
            return "pytest -q: exit 0. Used the repository."

        rep = a.run(flaky)
        assert rep.errors == 1 and rep.measured, rep.describe()
        assert "probe error" in rep.describe()

        # -- a single clause can be measured on its own --------------------
        one = a.run(half, clauses=["OUT"])
        assert [s.clause for s in one.measured] == ["OUT"]

        # -- an empty specification measures nothing, and says so ----------
        empty = Adherence(log, "").run(lambda r: "anything")
        assert empty.overall is None
        assert "nothing to measure" in empty.describe()

        # -- every run is sealed -------------------------------------------
        kinds = {e.type for e in log.events()}
        assert {"adherence.clause", "adherence.run"} <= kinds, kinds

    print("ADHERENCE SELF-TEST PASS")
