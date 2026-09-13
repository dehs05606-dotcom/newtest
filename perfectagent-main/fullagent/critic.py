"""CRITIC — checking the clauses a regex cannot express.

conform.py checks the reply against @output rules, which are regexes. That
covers the rules with a lexical shape — a forbidden phrase, a required
citation format, a length — and it covers nothing else. Most of a
specification is not lexical:

    "prefer composition over inheritance"
    "explain the trade-off before recommending one option"
    "do not restate the user's question back to them"
    "keep the existing naming conventions"

No regex decides whether a reply follows these. distill.py reports them as
prose it cannot read, adherence.py reports them as UNSCORABLE, and they
remain exactly what they were: the majority of the specification, checked
by nothing.

The only thing that can read prose is a model. So a second pass reads the
draft against the clauses it implicates and reports which ones it breaks.
That is a real departure from the rest of this package, which is
deterministic everywhere, and it is confined deliberately:

  1. IT ONLY REPORTS. A critic verdict is never a refusal and never
     rewrites the draft. It produces findings that conform.py can ask the
     model to address, and the bounded-retry and honest-failure rules there
     still hold.
  2. IT CITES OR IT IS DISCARDED. A finding must name a clause that was
     actually sent to it and quote the draft. A finding that cites nothing,
     or cites a clause that does not exist, is dropped — a critic that can
     invent a violation is a critic that can block correct work forever.
  3. IT IS NEVER THE ONLY CHECK. Everything a regex can decide is decided
     by conform.py first. This runs on what is left, which is where a
     model's judgement is the only instrument available and where its
     errors are cheapest: a false finding costs one regeneration.

WHAT THIS COSTS, plainly: a second model call per reply, and a judgement
that is not reproducible the way the rest of this package is. Two runs can
disagree. That is the price of checking prose at all, and the alternative
is what exists today, which is not checking it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .kernel import EventLog

MAX_CLAUSES = 12          # clauses sent to one critique
MAX_DRAFT = 12_000        # chars of draft sent

_PROMPT = """You are checking one draft reply against specific clauses from \
a specification. You are not rewriting it and not answering the user.

For each clause, decide whether the draft BREAKS it. A clause is broken \
only if the draft actually conflicts with it — not if the draft is merely \
silent about it, and not if you would have written it differently.

Reply with JSON only, in this exact shape:
{"findings": [{"clause": "<id>", "quote": "<exact text from the draft>", \
"why": "<one sentence>"}]}

An empty list means the draft breaks none of them. Quote the draft \
exactly; a finding whose quote is not in the draft is discarded.

CLAUSES:
{clauses}

DRAFT:
{draft}
"""


@dataclass(frozen=True)
class Finding:
    clause: str
    quote: str
    why: str

    def to_dict(self) -> dict:
        return {"clause": self.clause, "quote": self.quote[:200],
                "why": self.why}

    def describe(self) -> str:
        return f"{self.clause}: {self.why} — {self.quote[:80]!r}"


@dataclass
class Critique:
    findings: list[Finding] = field(default_factory=list)
    considered: list[str] = field(default_factory=list)
    discarded: int = 0
    error: str = ""

    @property
    def clean(self) -> bool:
        return not self.findings and not self.error

    def describe(self) -> str:
        if self.error:
            return f"critic: not run ({self.error})"
        if not self.considered:
            return "critic: no prose clause was implicated by this reply"
        head = (f"critic: {len(self.considered)} clause(s) read · "
                f"{len(self.findings)} finding(s)"
                + (f" · {self.discarded} discarded" if self.discarded else ""))
        if not self.findings:
            return head + "\n  the draft breaks none of them"
        return head + "\n" + "\n".join(f"  {f.describe()}"
                                       for f in self.findings)


def _prose_clauses(clauses, output_rule_clauses: set[str]) -> list:
    """Clauses with no machine-checkable rule — the ones left over.

    A clause conform.py already decides is not sent: paying for a model's
    opinion about a question a regex has answered is waste, and a
    disagreement between them would have no principled resolution.
    """
    return [c for c in clauses
            if not getattr(c, "enforced", False)
            and c.id not in output_rule_clauses
            and (c.body or c.title)]


def build_prompt(clauses, draft: str) -> str:
    blocks = []
    for c in clauses:
        body = ((c.title or "") + "\n" + (c.body or "")).strip()
        blocks.append(f"[{c.id}] {body}")
    return (_PROMPT
            .replace("{clauses}", "\n\n".join(blocks))
            .replace("{draft}", (draft or "")[:MAX_DRAFT]))


def parse(raw: str, draft: str, allowed: set[str]) -> tuple[list[Finding],
                                                            int]:
    """Read the critic's reply. Returns (findings, discarded).

    Every guard here exists because the failure it prevents is worse than
    a missed finding: an invented clause id, a quote that is not in the
    draft, or a wall of prose instead of JSON would each let the critic
    manufacture work that the model can never satisfy.
    """
    text = (raw or "").strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return [], 0
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return [], 0
    items = data.get("findings") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return [], 0

    out: list[Finding] = []
    discarded = 0
    for it in items:
        if not isinstance(it, dict):
            discarded += 1
            continue
        clause = str(it.get("clause", "")).strip().strip("[]")
        quote = str(it.get("quote", "")).strip()
        why = str(it.get("why", "")).strip()
        if clause not in allowed:
            discarded += 1          # a clause it was never shown
            continue
        if not quote or quote not in draft:
            discarded += 1          # a quote that is not in the draft
            continue
        if not why:
            discarded += 1
            continue
        out.append(Finding(clause, quote, why))
    return out, discarded


class Critic:
    """A second pass over the clauses a regex cannot decide."""

    def __init__(self, log: EventLog, spec: str = "") -> None:
        self.log = log
        self.spec = spec or ""
        self.runs = 0
        self.findings = 0
        self.discarded = 0

    def bind(self, spec: str) -> None:
        self.spec = spec or ""

    def review(self, draft: str, clauses, ask,
               output_rule_clauses: set[str] | None = None,
               limit: int = MAX_CLAUSES) -> Critique:
        """Critique `draft` against prose clauses using `ask(prompt) -> str`.

        `ask` is injected, so this module holds no model client: it can be
        tested without one, pointed at a cheaper model than the agent's,
        and cannot call a model on its own.
        """
        prose = _prose_clauses(clauses, output_rule_clauses or set())
        if not prose or not (draft or "").strip():
            return Critique()

        # the ones this draft plausibly touches, so the critique is about
        # a handful of clauses rather than the whole specification
        from . import salience
        picked = salience.select(prose, draft, limit=limit)
        chosen = [c for c in prose
                  if c.id in {s.clause_id for s in picked}] or prose[:limit]

        crit = Critique(considered=[c.id for c in chosen])
        self.runs += 1
        try:
            raw = ask(build_prompt(chosen, draft))
        except Exception as e:      # noqa: BLE001 — a critique is not the turn
            crit.error = f"{type(e).__name__}: {e}"
            self.log.append("critic.error", {"error": crit.error},
                            actor="kernel")
            return crit

        findings, discarded = parse(str(raw or ""), draft,
                                    {c.id for c in chosen})
        crit.findings = findings
        crit.discarded = discarded
        self.findings += len(findings)
        self.discarded += discarded
        self.log.append("critic.review",
                        {"considered": crit.considered,
                         "findings": [f.to_dict() for f in findings],
                         "discarded": discarded}, actor="kernel")
        return crit

    def instruction(self, crit: Critique) -> str:
        """What to hand conform.py's retry. Names the clause and quotes the
        draft; never writes the replacement."""
        lines = [f"Your draft conflicts with {len(crit.findings)} clause"
                 f"{'s' if len(crit.findings) > 1 else ''} of the "
                 f"specification. Rewrite it so that it does not. "
                 f"Change nothing else."]
        for f in crit.findings:
            lines.append(f"  {f.clause}: {f.why}")
            lines.append(f"    in your draft: {f.quote[:120]!r}")
        return "\n".join(lines)

    def report(self) -> str:
        if not self.runs:
            return "critic: not run yet"
        return (f"critic: {self.runs} review(s) · {self.findings} finding(s) "
                f"· {self.discarded} discarded as uncited or invented")


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    from .covenant import Covenant

    with tempfile.TemporaryDirectory() as td:
        log = EventLog(Path(td) / "log.jsonl")

        spec = '''[COMP] Prefer composition over inheritance
Deep class hierarchies are harder to change than composed parts.

[TRADE] Explain the trade-off before recommending one option
A recommendation without its cost is not a recommendation.

[ECHO] Do not restate the user's question back to them
Answer it.

[HASRULE] Secrets never appear in source
@enforce forbid_content: (?i)api[_-]?key
'''
        cov = Covenant(log, spec)
        c = Critic(log, spec)
        draft = ("You asked how to structure the parser. Subclass BaseParser "
                 "and override run().")

        # -- a clause with a machine rule is never sent to the critic ------
        prose = _prose_clauses(cov.clauses, set())
        assert "HASRULE" not in {x.id for x in prose}
        # nor is one conform.py already checks
        assert "ECHO" not in {x.id for x in
                              _prose_clauses(cov.clauses, {"ECHO"})}

        # -- a well-formed critique is read --------------------------------
        def ask_good(prompt: str) -> str:
            assert "[COMP]" in prompt and "[HASRULE]" not in prompt
            assert draft in prompt
            return json.dumps({"findings": [
                {"clause": "COMP", "quote": "Subclass BaseParser",
                 "why": "it recommends inheritance where composition fits"}]})

        crit = c.review(draft, cov.clauses, ask_good)
        assert len(crit.findings) == 1 and not crit.clean
        assert crit.findings[0].clause == "COMP"
        assert "COMP" in crit.describe()
        note = c.instruction(crit)
        assert "COMP" in note and "Subclass BaseParser" in note
        # it names the problem and never writes the replacement
        assert "composition" in note.lower()
        assert "class Parser" not in note

        # -- an INVENTED clause is discarded -------------------------------
        def ask_invent(prompt: str) -> str:
            return json.dumps({"findings": [
                {"clause": "NOPE", "quote": "Subclass BaseParser",
                 "why": "made up"}]})

        crit = c.review(draft, cov.clauses, ask_invent)
        assert crit.findings == [] and crit.discarded == 1

        # -- a quote that is not in the draft is discarded -----------------
        def ask_misquote(prompt: str) -> str:
            return json.dumps({"findings": [
                {"clause": "COMP", "quote": "text that never appeared",
                 "why": "hallucinated"}]})

        crit = c.review(draft, cov.clauses, ask_misquote)
        assert crit.findings == [] and crit.discarded == 1

        # -- prose instead of JSON yields nothing, not a crash -------------
        for junk in ("I think the draft is fine, honestly.", "", "{", "null",
                     json.dumps({"findings": "not a list"})):
            crit = c.review(draft, cov.clauses, lambda p, j=junk: j)
            assert crit.findings == [], junk

        # -- a clean verdict is clean --------------------------------------
        crit = c.review(draft, cov.clauses,
                        lambda p: json.dumps({"findings": []}))
        assert crit.clean and "breaks none of them" in crit.describe()

        # -- a failing critic never takes down the turn --------------------
        def boom(prompt: str) -> str:
            raise RuntimeError("critic model unavailable")

        crit = c.review(draft, cov.clauses, boom)
        assert crit.error and not crit.findings
        assert "not run" in crit.describe()
        assert any(e.type == "critic.error" for e in log.events())

        # -- nothing to critique -------------------------------------------
        assert c.review("", cov.clauses, ask_good).considered == []
        assert Critic(log, "").review(
            draft, Covenant(log, "").clauses, ask_good).considered == []

        # -- every review is sealed ----------------------------------------
        assert any(e.type == "critic.review" for e in log.events())
        assert "discarded" in c.report()

    print("CRITIC SELF-TEST PASS")
