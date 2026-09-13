"""SALIENCE — putting the rules that matter where the model actually reads.

Every module before this one governs what the agent DOES. None of them
makes it more likely the model follows the specification in the first
place, and that is the thing the author actually asked for. A boundary that
refuses non-compliant actions and a model that complies are different
goods: the first produces a refused call and a wasted turn, the second
produces the right work.

The mechanism this addresses is not a defect in the model and cannot be
fixed by asking harder. Attention over a long context is not uniform. A
specification delivered as one 150k-char block puts most of its rules in
the middle, which is measurably the weakest position — with 400 clauses the
three that govern the current request sit around the 50% mark, exactly
where recall is worst. The prompt is complete, correct, delivered
verbatim, and the rules the turn needs are the least visible part of it.

So: deliver the specification whole, as before — and ALSO restate, at the
end of the context where attention is strongest, the small number of
clauses this particular request implicates.

    150k specification, verbatim, once     (systemprompt.SPEC)
    + the 3-8 clauses this turn touches    (here, at the end)

This is not a reminder to obey and not a re-injected instruction. No
sentence is invented: the text is the author's own clauses, selected by
term overlap with the request and by which clauses carry enforceable rules,
and reproduced unchanged. If nothing is relevant, nothing is added.

WHY SELECTION IS CONSERVATIVE. A clause wrongly left out is a rule the
model is less likely to follow; a clause wrongly included costs tokens and
dilutes the rest. Recall matters more than precision here, so scoring
favours inclusion: an enforceable clause with any real term overlap gets
in, and the budget — not the threshold — is what bounds the block.

WHAT THIS IS NOT. It does not summarise, paraphrase, or rank the
specification for the model, and it never replaces delivering it in full.
A selection that stood in for the whole specification would be this module
deciding which of the author's rules matter, which is not a judgement it is
entitled to make.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")

# terms that appear in almost every clause and so separate nothing
_STOP = frozenset({
    "the", "and", "for", "with", "that", "this", "from", "must", "never",
    "always", "should", "every", "each", "any", "all", "not", "are", "was",
    "has", "have", "will", "can", "may", "use", "used", "using", "when",
    "then", "than", "its", "their", "there", "here", "into", "out", "via",
    "you", "your", "our", "one", "two", "only", "also", "but", "own",
    "clause", "rule", "rules", "section", "agent", "code", "file", "files",
})

DEFAULT_BUDGET = 6_000      # chars of restated clauses
DEFAULT_MAX = 8             # clauses, however much budget is left

_HEADER = (
    "CLAUSES THIS REQUEST TOUCHES — reproduced verbatim from the "
    "specification above, restated here because the specification is long "
    "and these are the ones in play. The specification as a whole remains "
    "binding; nothing here narrows it."
)


def terms(text: str) -> set[str]:
    """Content words, lowercased, stopwords dropped."""
    return {w.lower() for w in _WORD.findall(text or "")
            if w.lower() not in _STOP}


@dataclass(frozen=True)
class Scored:
    clause_id: str
    title: str
    text: str
    score: float
    shared: tuple[str, ...]

    def to_dict(self) -> dict:
        return {"clause": self.clause_id, "score": round(self.score, 3),
                "shared": list(self.shared[:8])}


def score_clauses(clauses, request: str, tools: list[str] | None = None
                  ) -> list[Scored]:
    """Rank clauses by how much this request implicates them.

    Scoring is deliberately simple and deterministic: term overlap, plus a
    weight for clauses that carry an enforceable rule, plus a small weight
    for a title match. A learned or model-based ranker would put a second
    model's judgement between the author's rules and the agent, which is
    the thing this package exists to avoid.
    """
    want = terms(request)
    for t in tools or ():
        want |= terms(t)
    if not want:
        return []

    out: list[Scored] = []
    for c in clauses:
        body = (c.title or "") + "\n" + (c.body or "")
        have = terms(body)
        if not have:
            continue
        shared = want & have
        if not shared:
            continue
        # overlap normalised by the clause's own vocabulary, so a long
        # clause does not win simply by containing more words
        overlap = len(shared) / (len(have) ** 0.5)
        score = overlap
        if getattr(c, "enforced", False):
            # a clause with a machine-checkable rule is one the agent will
            # be refused on; surfacing it early turns a refusal into work
            score *= 1.6
        if want & terms(c.title or ""):
            score *= 1.3
        out.append(Scored(c.id, c.title or "", body.strip(), score,
                          tuple(sorted(shared))))
    out.sort(key=lambda s: (-s.score, s.clause_id))
    return out


def select(clauses, request: str, tools: list[str] | None = None,
           budget: int = DEFAULT_BUDGET, limit: int = DEFAULT_MAX
           ) -> list[Scored]:
    """The clauses to restate, within a character budget."""
    chosen: list[Scored] = []
    spent = 0
    for s in score_clauses(clauses, request, tools):
        if len(chosen) >= limit:
            break
        cost = len(s.text) + 8
        if spent + cost > budget:
            continue          # a long clause must not starve shorter ones
        chosen.append(s)
        spent += cost
    return chosen


def block(clauses, request: str, tools: list[str] | None = None,
          budget: int = DEFAULT_BUDGET, limit: int = DEFAULT_MAX) -> str:
    """The text to place at the end of the context, or "" for nothing.

    Returns "" rather than an empty header when no clause is implicated:
    a block that says "no rules apply here" is a sentence this module
    invented, and it would be read as permission.
    """
    picked = select(clauses, request, tools, budget, limit)
    if not picked:
        return ""
    parts = [_HEADER, ""]
    for s in picked:
        parts.append(s.text)
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def report(clauses, request: str, tools: list[str] | None = None) -> str:
    picked = select(clauses, request, tools)
    if not picked:
        return "salience: no clause is implicated by this request"
    lines = [f"salience: {len(picked)} of {len(list(clauses))} clauses "
             f"restated at the end of context"]
    for s in picked:
        lines.append(f"  {s.clause_id:<12} {s.score:>6.2f}  "
                     f"{', '.join(s.shared[:6])}")
    return "\n".join(lines)


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    from .covenant import Covenant
    from .kernel import EventLog

    with tempfile.TemporaryDirectory() as td:
        log = EventLog(Path(td) / "log.jsonl")

        # a realistic long specification: many clauses, few relevant
        filler = "\n".join(
            f"§{i} Rule about subsystem {i}\n" + ("background prose. " * 24)
            for i in range(300))
        # alphabetic ids use the [tag] form; "§" takes digits
        real = '''[SQL] Database access goes through the repository layer
Queries are never written inline in a handler; every read and write goes
through a repository class so the schema has one owner.
@enforce forbid_content: (?i)execute\\(\\s*["\\']SELECT

[MIG] A schema change ships with a migration
Any change under db/schema requires a matching file in db/migrations.

[LOG] Secrets never reach the logs
Credentials, tokens and keys are redacted before any logging call.
@enforce forbid_content: (?i)log\\w*\\(.*(password|token|secret)

[UI] Buttons use the design tokens
No raw hex colours in components; use the token names.
'''
        spec = filler + "\n" + real
        cov = Covenant(log, spec)
        assert len(cov.clauses) > 300

        # -- the relevant clauses are selected, the filler is not ----------
        picked = select(cov.clauses,
                        "add a repository method that runs a SELECT for "
                        "the orders table and log the query")
        ids = [s.clause_id for s in picked]
        assert "SQL" in ids, ids
        assert "LOG" in ids, ids
        assert "UI" not in ids, ids
        # none of the 300 filler clauses beat a genuinely relevant one
        assert ids[0] in ("SQL", "LOG"), ids

        # -- the block is the author's own text, unchanged -----------------
        text = block(cov.clauses, "write a SELECT in the repository")
        assert "Queries are never written inline" in text
        assert "@enforce forbid_content" in text, "the rule was stripped"
        assert _HEADER in text
        # nothing invented: every non-header line comes from the spec
        for line in text.splitlines():
            if not line.strip() or line in _HEADER or line in _HEADER.split("\n"):
                continue
            if line.startswith(("CLAUSES THIS REQUEST", "specification")):
                continue
            assert line in spec or line in _HEADER, f"invented line: {line!r}"

        # -- an unrelated request restates nothing, and says nothing -------
        assert block(cov.clauses, "what time is it") == ""
        assert "no clause is implicated" in report(cov.clauses, "hello")

        # -- enforceable clauses outrank prose at equal overlap ------------
        two = Covenant(log, '''[A] Tokens must be redacted
@enforce forbid_content: token

[B] Tokens must be redacted
''')
        ranked = score_clauses(two.clauses, "redact the token please")
        assert ranked[0].clause_id == "A", [r.clause_id for r in ranked]

        # -- the budget bounds the block, and one long clause cannot
        # starve the rest ---------------------------------------------------
        fat = Covenant(log, "[BIG] a giant clause\n" + ("word " * 4000)
                            + "\n[SMALL] a small one about tokens\n"
                              "tokens are redacted\n")
        picked = select(fat.clauses, "tokens word", budget=500)
        assert [s.clause_id for s in picked] == ["SMALL"], \
            [s.clause_id for s in picked]
        assert len(block(fat.clauses, "tokens word", budget=500)) < 1200

        # -- limits are honoured --------------------------------------------
        many = select(cov.clauses, "rule subsystem background prose", limit=3)
        assert len(many) <= 3

        # -- tool names participate in relevance ---------------------------
        with_tools = select(cov.clauses, "make the change",
                            tools=["write_file", "migrations", "schema"])
        assert any(s.clause_id == "MIG" for s in with_tools), \
            [s.clause_id for s in with_tools]

        # -- deterministic: the same request always selects the same set ---
        a = [s.clause_id for s in select(cov.clauses, "SELECT repository log")]
        b = [s.clause_id for s in select(cov.clauses, "SELECT repository log")]
        assert a == b

        # -- an empty specification produces nothing -----------------------
        assert block(Covenant(log, "").clauses, "anything") == ""

    print("SALIENCE SELF-TEST PASS")
