"""PROVENANCE — where the bytes being written came from.

Guards judge WHAT is written and WHERE. Neither question reaches the one
that matters for a whole class of clauses: what is the ORIGIN of this
content?

    "code fetched from the web is never committed unreviewed"
    "nothing from a tool's error output ends up in a source file"
    "a credential read from the environment never lands on disk"
    "generated fixtures stay under tests/"

Each of these is invisible to a content rule, because the bytes themselves
are unremarkable. `def parse(s): ...` is fine; the same line copied
verbatim out of a `web_fetch` five turns ago may not be. The difference is
not in the text — it is in where the text came from, which only the event
log knows.

So this module tracks lineage. Every tool result is a SOURCE with a kind
(web, file, command, env). Its content is shingled into rolling hashes, and
a pending write is matched against those shingles. A substantial overlap
means the content is derived from that source, and the clause that cares
about that origin can finally be written:

    §14 Web content is never written to source unreviewed.
    @origin forbid web -> src/**

    §15 Command output does not become code.
    @origin forbid command -> **/*.py

Matching is by SHINGLE OVERLAP, not exact equality, because content is
rarely copied byte-for-byte: it is reindented, renamed, trimmed. A rule
that only caught exact copies would catch nothing real. The threshold is
explicit and reported, so a near-miss is a number you can see rather than a
silent pass.

WHAT THIS IS NOT. This is not information-flow analysis and does not claim
soundness. It detects reuse of recorded content above a threshold. Content
that is heavily rewritten, or that passed through a transformation this
module never saw, is not detected — and `report()` says so rather than
implying coverage it does not have. It is a strong detector of copying,
not a proof of non-copying.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from .effects import WRITE, derive
from .kernel import EventLog

WEB = "web"
FILE = "file"
COMMAND = "command"
ENV = "env"
KINDS = (WEB, FILE, COMMAND, ENV)

# Window size is the sensitivity dial. Measured against a 700-char sample:
# 48/16 yields 13 fingerprints and misses a rename-plus-reindent at 0.23,
# while 32/8 yields 27 and catches it at 0.30, with unrelated content still
# at 0.00. Going finer (24/6) does not improve the rename case further and
# starts matching on common code idioms, so 32/8 is the floor worth taking.
_SHINGLE = 32            # characters per rolling window
_STRIDE = 8              # window step
_MIN_SOURCE = 120        # ignore sources too short to fingerprint usefully
_DEFAULT_THRESHOLD = 0.25

_ORIGIN_RE = re.compile(
    r"^\s*@origin\s+forbid\s+(?P<kind>web|file|command|env)\s*->\s*"
    r"(?P<glob>\S+)(?:\s+over\s+(?P<threshold>[0-9.]+))?\s*$", re.I)

_WS = re.compile(r"\s+")

# which tools produce which kind of source
_SOURCE_KIND = {
    "web_fetch": WEB, "web_search": WEB,
    "read_file": FILE, "search_files": FILE, "list_dir": FILE,
    "run_command": COMMAND, "live_shell": COMMAND, "bg_shell": COMMAND,
}


def _normalise(text: str) -> str:
    """Collapse whitespace so reindentation does not defeat matching."""
    return _WS.sub(" ", (text or "").strip()).lower()


def shingles(text: str) -> set[str]:
    """Rolling content fingerprints."""
    norm = _normalise(text)
    if len(norm) < _SHINGLE:
        return set()
    out = set()
    for i in range(0, len(norm) - _SHINGLE + 1, _STRIDE):
        window = norm[i:i + _SHINGLE]
        out.add(hashlib.blake2b(window.encode("utf-8"),
                                digest_size=8).hexdigest())
    return out


@dataclass(frozen=True)
class Rule:
    clause: str
    kind: str
    glob: str
    threshold: float = _DEFAULT_THRESHOLD

    def to_dict(self) -> dict:
        return {"clause": self.clause, "kind": self.kind,
                "glob": self.glob, "threshold": self.threshold}


@dataclass
class Source:
    """One recorded origin of content."""
    kind: str
    label: str                       # url, path, or command
    marks: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class Taint:
    clause: str
    kind: str
    path: str
    label: str
    overlap: float
    threshold: float

    def to_dict(self) -> dict:
        return {"clause": self.clause, "kind": self.kind, "path": self.path,
                "label": self.label, "overlap": round(self.overlap, 3),
                "threshold": self.threshold}

    def describe(self) -> str:
        return (f"{self.clause}: {self.path!r} reuses {self.overlap:.0%} of "
                f"content from {self.kind} source {self.label!r} "
                f"(threshold {self.threshold:.0%})")


def parse_rules(spec: str) -> tuple[list[Rule], list[str]]:
    rules: list[Rule] = []
    errors: list[str] = []
    clause = "preamble"
    for line in (spec or "").splitlines():
        head = re.match(r"^\s{0,3}§\s*([\d.]+[a-z]?)", line)
        if head:
            clause = head.group(1)
            continue
        tag = re.match(r"^\s{0,3}\[([A-Za-z0-9_.\-]+)\]", line)
        if tag:
            clause = tag.group(1)
            continue
        if not re.match(r"^\s*@origin\b", line, re.I):
            continue
        m = _ORIGIN_RE.match(line)
        if not m:
            errors.append(f"{clause}: malformed @origin — expected "
                          f"'@origin forbid web -> src/**' "
                          f"(optionally 'over 0.3')")
            continue
        raw = m.group("threshold")
        try:
            threshold = float(raw) if raw else _DEFAULT_THRESHOLD
        except ValueError:
            errors.append(f"{clause}: threshold {raw!r} is not a number")
            continue
        if not 0 < threshold <= 1:
            errors.append(f"{clause}: threshold must be between 0 and 1")
            continue
        rules.append(Rule(clause, m.group("kind").lower(), m.group("glob"),
                          threshold))
    return rules, errors


def _matches(path: str, glob: str) -> bool:
    import fnmatch
    from pathlib import PurePath
    parts: list[str] = []
    for part in PurePath(path or "").parts:
        if part == "..":
            if parts:
                parts.pop()
        elif part != ".":
            parts.append(part)
    norm = "/".join(parts)
    if fnmatch.fnmatch(norm, glob):
        return True
    if "**" in glob:
        flat = glob.replace("**/", "").replace("/**", "")
        if fnmatch.fnmatch(norm, flat):
            return True
        head = glob.split("**")[0].rstrip("/")
        if head and norm.startswith(head + "/"):
            return True
    return False


class Lineage:
    """Recorded sources, and the writes that reuse them."""

    def __init__(self, log: EventLog, spec: str = "") -> None:
        self.log = log
        self.rules: list[Rule] = []
        self.errors: list[str] = []
        self.sources: list[Source] = []
        self.blocked = 0
        self.bind(spec)

    def bind(self, spec: str) -> None:
        self.rules, self.errors = parse_rules(spec or "")

    # -- recording ----------------------------------------------------------

    def observe(self, tool: str, args: dict, result: str) -> Source | None:
        """Record a tool result as a source of content."""
        kind = _SOURCE_KIND.get(tool)
        if kind is None or not result or len(result) < _MIN_SOURCE:
            return None
        a = args or {}
        label = str(a.get("url") or a.get("path") or a.get("command")
                    or a.get("query") or tool)
        marks = shingles(result)
        if not marks:
            return None
        src = Source(kind=kind, label=label, marks=marks)
        self.sources.append(src)
        self.log.append("provenance.source",
                        {"kind": kind, "label": label[:200],
                         "marks": len(marks)}, actor="kernel")
        return src

    # -- the boundary -------------------------------------------------------

    def check(self, tool: str, args: dict) -> list[Taint]:
        """Origin clauses this pending write would break."""
        if not self.rules or not self.sources:
            return []
        out: list[Taint] = []
        for e in derive(tool, args):
            if e.kind != WRITE or not e.content or not e.path:
                continue
            marks = shingles(e.content)
            if not marks:
                continue
            for rule in self.rules:
                if not _matches(e.path, rule.glob):
                    continue
                for src in self.sources:
                    if src.kind != rule.kind:
                        continue
                    shared = marks & src.marks
                    if not shared:
                        continue
                    overlap = len(shared) / len(marks)
                    if overlap >= rule.threshold:
                        out.append(Taint(rule.clause, rule.kind, e.path,
                                         src.label, overlap, rule.threshold))
                        break
        return out

    def gate(self, tool: str, args: dict) -> str | None:
        taints = self.check(tool, args)
        if not taints:
            return None
        self.blocked += 1
        self.log.append("provenance.blocked",
                        {"tool": tool, "taints": [t.to_dict()
                                                  for t in taints]},
                        actor="kernel")
        lines = [f"OriginRefused: this write reuses content from a source "
                 f"{len(taints)} clause"
                 f"{'s' if len(taints) > 1 else ''} forbid as an origin."]
        for t in taints:
            lines.append(f"  {t.describe()}")
        return "\n".join(lines)

    def report(self) -> str:
        if not self.rules:
            return "provenance: no @origin rules — content lineage is untracked"
        by_kind: dict[str, int] = {}
        for s in self.sources:
            by_kind[s.kind] = by_kind.get(s.kind, 0) + 1
        breakdown = ", ".join(f"{k}:{n}" for k, n in sorted(by_kind.items()))
        lines = [f"provenance: {len(self.rules)} rule(s) · "
                 f"{len(self.sources)} source(s) recorded "
                 f"({breakdown or 'none'}) · {self.blocked} refused"]
        for r in self.rules:
            lines.append(f"  {r.clause:<10} no {r.kind:<8} content in "
                         f"{r.glob} (over {r.threshold:.0%})")
        lines.append("  detects reuse above the threshold; heavily rewritten "
                     "content is not detected")
        for e in self.errors:
            lines.append(f"  !! {e}")
        return "\n".join(lines)


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        log = EventLog(Path(td) / "log.jsonl")

        spec = '''§14 Web content is never written to source unreviewed
@origin forbid web -> src/**

§15 Command output does not become code
@origin forbid command -> **/*.py over 0.4
'''
        lin = Lineage(log, spec)
        assert len(lin.rules) == 2 and not lin.errors
        assert lin.rules[1].threshold == 0.4

        fetched = (
            "def parse_config(path):\n"
            "    with open(path) as fh:\n"
            "        return json.load(fh)\n"
            "\n"
            "def merge_defaults(cfg, defaults):\n"
            "    out = dict(defaults)\n"
            "    out.update(cfg)\n"
            "    return out\n"
            "\n"
            "def validate(cfg):\n"
            "    if 'name' not in cfg:\n"
            "        raise ValueError('name is required')\n"
            "    return True\n"
        )

        # nothing recorded yet: nothing to match against
        assert lin.check("write_file", {"path": "src/a.py",
                                        "content": fetched}) == []

        lin.observe("web_fetch", {"url": "https://example.test/snippet"},
                    fetched)
        assert len(lin.sources) == 1 and lin.sources[0].kind == WEB

        # -- verbatim reuse into src/ is refused ---------------------------
        blocked = lin.gate("write_file", {"path": "src/config.py",
                                          "content": fetched})
        assert blocked and "14" in blocked, blocked
        assert "example.test" in blocked

        # -- reindented and renamed content is still caught ----------------
        edited = fetched.replace("cfg", "conf").replace("    ", "\t")
        assert lin.gate("write_file", {"path": "src/config.py",
                                       "content": edited}), "reuse missed"

        # -- the same content OUTSIDE the rule's scope is allowed ----------
        assert lin.gate("write_file", {"path": "vendor/config.py",
                                       "content": fetched}) is None

        # -- unrelated content is allowed ----------------------------------
        assert lin.gate("write_file",
                        {"path": "src/other.py",
                         "content": "class Widget:\n    pass\n" * 8}) is None

        # -- the shell route is judged the same way ------------------------
        assert lin.gate("run_command",
                        {"command": f"cat > src/c.py <<'EOF'\n{fetched}\nEOF"})

        # -- kind is respected: a FILE source does not trip a WEB rule -----
        lin2 = Lineage(log, "§14 no web in src\n@origin forbid web -> src/**\n")
        lin2.observe("read_file", {"path": "other/local.py"}, fetched)
        assert lin2.gate("write_file", {"path": "src/x.py",
                                        "content": fetched}) is None

        # -- threshold is honoured -----------------------------------------
        lin3 = Lineage(log, "§16 strict\n@origin forbid web -> src/** over 0.9\n")
        lin3.observe("web_fetch", {"url": "https://e.test/a"}, fetched)
        half = fetched[:len(fetched) // 2] + "\n" + "def unrelated():\n    pass\n" * 6
        assert lin3.gate("write_file", {"path": "src/h.py",
                                        "content": half}) is None
        assert lin3.gate("write_file", {"path": "src/h.py",
                                        "content": fetched})

        # -- short results are not fingerprinted (noise, not lineage) ------
        lin4 = Lineage(log, spec)
        assert lin4.observe("web_fetch", {"url": "x"}, "ok") is None
        assert lin4.sources == []

        # -- no rules means no interference --------------------------------
        quiet = Lineage(log, "")
        quiet.observe("web_fetch", {"url": "x"}, fetched)
        assert quiet.gate("write_file", {"path": "src/a.py",
                                         "content": fetched}) is None
        assert "untracked" in quiet.report()

        # -- refusals are sealed, and the report states its limits ---------
        assert any(e.type == "provenance.blocked" for e in log.events())
        assert any(e.type == "provenance.source" for e in log.events())
        assert "not detected" in lin.report()

        # -- malformed rules are reported, never guessed at ----------------
        bad = Lineage(log, "§17 x\n@origin forbid sideways -> src/**\n"
                           "§18 y\n@origin forbid web\n"
                           "§19 z\n@origin forbid web -> src/** over 9\n")
        assert len(bad.errors) == 3, bad.errors
        assert bad.rules == []

    print("PROVENANCE SELF-TEST PASS")
