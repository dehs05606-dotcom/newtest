"""systemprompt.py — the ONE home of every system prompt in FullAgent.

Every prompt the model ever sees lives here and nowhere else. The rest of
the codebase only ever imports from this file — no inline prompt strings
exist in agent.py, swarm.py or team.py. That is the structural guarantee:

  * single source of truth  — edit a prompt here, it changes everywhere.
  * one delivery path       — every message list is built through
                              `with_system()`, which guarantees the right
                              system prompt sits at position 0 before the
                              request is sent. A model can never be called
                              without its prompt, and can never see a
                              stale or partial one.
  * compliance by design    — the prompts are written so that following
                              them is the path of least resistance: a
                              clear identity, a short set of prime
                              directives, and an exact output contract.
                              No threats, no "you must obey" — the
                              structure itself carries the authority.

Prompts defined:
    MAIN          the sovereign agent (the main conversation loop)
    SCOUT         read-only scout sub-agents (swarm.py)
    WORKER        parallel worker sub-agents (team.py), per role brief
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# MAIN — the sovereign agent
# ---------------------------------------------------------------------------

MAIN = """You are FullAgent — an autonomous terminal AI agent built to help with software engineering tasks.

## Identity
You are a careful, capable software engineering agent. You work in a Linux environment with access to tools for reading files, editing code, running commands, and searching the web. Your purpose is to help the user achieve their goals reliably and safely.

## Prime Directives
1. **Understand first.** Read the codebase before making changes. Never assume.
2. **Make minimal, correct changes.** Prefer small, surgical edits over rewrites.
3. **Verify everything.** Run tests, check exit codes, confirm file contents. Never claim success without evidence.
4. **Be honest about uncertainty.** If you don't know something, say so and investigate.
5. **Respect the user's autonomy.** Ask before making irreversible changes (deletes, destructive operations).
6. **Never fabricate.** Cite real sources, real file paths, real exit codes. No invented information.

## Tool Usage
- Use `read_file` to inspect files before editing them.
- Use `edit_file` for precise string replacements; `write_file` for new files or full rewrites.
- Use `run_command` to execute builds, tests, git commands, and scripts.
- Use `search_files` for regex-based code search; `web_search` for real-time information.
- Use `web_fetch` to read specific URLs when you need full article content.

## Output Contract
- Be concise and factual. Lead with the answer, then give supporting detail.
- Use code blocks for code, commands, and file contents.
- Cite sources (URLs, file:line) when referencing external information.
- When a task is complete, state what was done and verify it.

## Safety
- Never execute harmful or destructive commands without explicit user approval.
- Never exfiltrate data, access unauthorized systems, or bypass security controls.
- If a request seems harmful, explain why and offer a safe alternative.
- Respect privacy: do not read sensitive files (keys, credentials) unless the task requires it.

## Goal Mode
When the user gives you a verifiable mission ("fix", "add", "make X pass"), you may draft a machine-checkable goal contract. Each clause has a predicate that can be verified deterministically. A clause is only proven when its predicate actually passes — never declare success on your own say-so.

You are helpful, capable, and honest. Help the user build things that work.
"""


# ---------------------------------------------------------------------------
# SCOUT — read-only scout sub-agent
# ---------------------------------------------------------------------------

SCOUT = """You are a Scout — a read-only investigative sub-agent working within FullAgent.

Your role is to gather facts: read files, search code, run read-only commands, and report findings. You are one of several parallel scouts.

Rules:
- You are READ-ONLY. Never modify files, never run writes, never delete anything.
- Gather evidence before reporting. Cite file paths and line numbers.
- Be fast and decisive. Inspect, report, finish.
- If something is ambiguous, make the most reasonable interpretation and note it.

When done, reply with a final report in EXACTLY this form:
STATUS: DONE | BLOCKED
SUMMARY: <2-5 factual lines: what you found, exact paths/numbers, key evidence>
"""


# ---------------------------------------------------------------------------
# WORKER — parallel worker sub-agents (one template, per-role briefs)
# ---------------------------------------------------------------------------

WORKER = """You are {role_brief}

You are one of up to {max_workers} workers running IN PARALLEL on the same machine. Rules:
- Complete ONLY your assigned task; other workers handle the rest.
- Work fast and decisively: inspect, act, verify, finish.
- Use your tools to gather real evidence before claiming anything.
- If your task is ambiguous, do the most reasonable interpretation and note it.

When done, reply with a final report in EXACTLY this form:
STATUS: DONE | BLOCKED
SUMMARY: <2-5 factual lines: what you did, what you found, exact paths/numbers>"""

# Role briefs slot into the WORKER template. Kept here (not in team.py) so
# every word the model reads is defined in this one file.
ROLE_BRIEFS: dict[str, str] = {
    "researcher": ("a RESEARCH specialist. Gather facts from the web and "
                   "the codebase. Cite sources (URLs, file:line). Never "
                   "modify anything."),
    "coder": ("a senior SOFTWARE ENGINEER. Read before you write; make "
              "minimal, correct changes; keep existing style and "
              "conventions."),
    "tester": ("a QA / TEST engineer. Run builds, tests and checks; report "
               "exact exit codes, failures and the minimal reproduction. "
               "Never modify source files."),
    "reviewer": ("a CODE REVIEWER. Inspect the code and report bugs, risks "
                 "and style problems with file:line evidence. Never modify "
                 "anything."),
    "analyst": ("a DATA / SYSTEMS analyst. Combine local evidence and live "
                "web data into numbers, comparisons and a verdict. Never "
                "modify anything."),
}


# ---------------------------------------------------------------------------
# Builders — the only functions the rest of the code calls
# ---------------------------------------------------------------------------

def _bind_spec(prompt: str) -> str:
    """Append the specification to a sub-agent's prompt.

    The specification used to reach the sovereign agent and nothing else.
    Every sub-agent — the coder, the tester, the refactorer, the one that
    actually writes the files — received a ~640-char role brief carrying
    none of the author's rules, so the rules governed the agent that
    delegates and not one of the agents that act.

    That is the whole specification failing quietly. A rule about how code
    is written does not reach the thing writing the code, and the work
    comes back out of policy through a route nobody closed.

    The cost is real and is the right trade: every sub-agent request now
    carries the full specification. A specification cheap enough to skip
    for the workers is one the workers do not follow.
    """
    if not SPEC.strip():
        return prompt
    return (
        prompt
        + "\n\n"
        + "=" * 72
        + "\nFULL MASTER SPECIFICATION — binding on you exactly as it is on "
          "the agent that dispatched you. Every invariant and contract "
          "below applies to your work.\n"
        + "=" * 72
        + "\n\n"
        + SPEC
    )


def main() -> str:
    """The sovereign agent's system prompt."""
    return MAIN


def scout() -> str:
    """A scout sub-agent's system prompt."""
    return _bind_spec(SCOUT)


def worker(role: str, max_workers: int) -> str:
    """A worker sub-agent's system prompt for the given role."""
    brief = ROLE_BRIEFS.get(role, ROLE_BRIEFS["coder"])
    return _bind_spec(WORKER.format(role_brief=brief,
                                    max_workers=max_workers))


def with_system(messages: list[dict], system: str) -> list[dict]:
    """Guarantee the system prompt is present and first.

    This is the single delivery path: every request to a model is built
    through here. If messages[0] is not already the system prompt, it is
    (re)placed — so the model always sees the full, current prompt from
    this file, and nothing upstream can accidentally drop or shadow it."""
    if messages and messages[0].get("role") == "system":
        messages[0] = {"role": "system", "content": system}
    else:
        messages.insert(0, {"role": "system", "content": system})
    return messages


# ---------------------------------------------------------------------------
# SPEC — the master specification, and the ONLY place it lives
# ---------------------------------------------------------------------------
# The specification used to be read from a file: $FULLAGENT_SPEC, then
# ~/.fullagent/project.txt, then a project.txt shipped in the package. That
# is one indirection too many, and every one of those hops was a way for the
# prompt the model receives to stop being the prompt this file declares:
#
#   * a file can be swapped, truncated, or simply absent, and the agent
#     starts with 2k chars of preamble where a full specification belongs —
#     which is exactly the failure this project already hit once, silently
#   * an environment variable moves the prompt outside the repository, so
#     nothing under version control describes what the model was told
#   * three candidate paths mean the answer to "which prompt is in force?"
#     depends on the machine it is asked on
#
# So the specification is no longer data that is loaded. It is CODE that
# ships: a constant in this module, under version control, content-addressed
# by integrity.py and protected from the agent's own tool calls by
# sanctum.py. There is no file to lose, no path to resolve, and no
# environment in which a different specification can appear.
#
# TO INSTALL YOUR SPECIFICATION: paste it between the triple quotes below.
# Nothing else needs changing — MASTER is rebuilt from it at import.

SPEC = """"""

SPEC_CHARS = len(SPEC)
_SPEC = SPEC          # kept as the name the rest of the package imports


def spec_status() -> str:
    """One-line report of the specification compiled into this module."""
    if not SPEC.strip():
        return ("master spec is EMPTY — MASTER carries no specification.\n"
                "  Paste it into the SPEC constant in systemprompt.py; "
                "there is no file to place.")
    return (f"master spec: {SPEC_CHARS:,} chars, compiled into "
            f"systemprompt.py")


def _build_master(spec: str) -> str:
    """MAIN + the specification, verbatim. The spec is never trimmed,
    summarised or sampled — a partially-delivered specification is worse
    than none, because the model cannot tell which half it is missing.

    An empty spec returns MAIN unchanged rather than MAIN plus a banner:
    a MASTER that announces a specification it does not carry is how a
    missing spec stayed invisible here once already.
    """
    if not spec.strip():
        return MAIN
    return (
        MAIN
        + "\n\n"
        + "=" * 72
        + "\nFULL MASTER SPECIFICATION — the architecture you operate "
          "within. Treat every invariant, subsystem contract and Goal-Mode "
          "rule below as binding.\n"
        + "=" * 72
        + "\n\n"
        + spec
    )


MASTER = _build_master(SPEC)


# ---------------------------------------------------------------------------
# Prompt registry — add more system prompts here later
# ---------------------------------------------------------------------------
# Every selectable system prompt lives in this one map. To add another
# prompt later, either drop a new constant above and register it here, or
# call register() at runtime. get() resolves a name to its prompt, falling
# back to MAIN so an unknown name can never leave the model promptless.

PROMPTS: dict[str, str] = {
    "main": MAIN,
    "master": MASTER,
}


def get(name: str) -> str:
    """Resolve a prompt name to its text (falls back to MAIN)."""
    return PROMPTS.get(name, MAIN)


# The prompts this module DECLARES. They are the single source of truth and
# cannot be replaced at runtime — see register().
SOVEREIGN = frozenset({"main", "master", "scout"})


class PromptLocked(RuntimeError):
    """Raised when something tries to replace a sovereign prompt."""


def register(name: str, prompt: str) -> None:
    """Add a named system prompt at runtime.

    Sub-agent roles are registered here legitimately (meta.py and
    evolution.py author `worker:*` prompts), so this door has to stay open.
    What it must not be is a way to replace the sovereign prompts: if
    `master` could be overwritten at runtime, "the specification lives in
    systemprompt.py" would be true only until something called this
    function, and the single source of truth would be a convention rather
    than a property.
    """
    if name in SOVEREIGN:
        raise PromptLocked(
            f"{name!r} is declared in systemprompt.py and cannot be replaced "
            f"at runtime — edit the module, which is version-controlled, "
            f"content-addressed and protected from the agent's own writes")
    PROMPTS[name] = prompt


def names() -> list[str]:
    """The registered prompt names."""
    return sorted(PROMPTS)


if __name__ == "__main__":
    # sanity: every builder returns a non-empty prompt, and with_system
    # always leaves the system prompt at position 0.
    assert main() and scout()
    for role in ROLE_BRIEFS:
        assert worker(role, 8)
    msgs = [{"role": "user", "content": "hi"}]
    with_system(msgs, main())
    assert msgs[0]["role"] == "system" and msgs[0]["content"] == MAIN
    with_system(msgs, scout())  # replaces, never duplicates
    assert len([m for m in msgs if m["role"] == "system"]) == 1
    assert msgs[0]["content"] == SCOUT

    assert get("master") == MASTER
    assert get("main") == MAIN
    assert get("nope") == MAIN  # unknown name falls back, never empty
    register("custom", "hello prompt")
    assert get("custom") == "hello prompt"
    assert "master" in names() and "main" in names()

    # The specification is a constant in this module, so MASTER is a pure
    # function of it. The old test loaded a file through $FULLAGENT_SPEC;
    # there is no longer a file, an env var, or a path to load from.
    assert _build_master("") == MAIN, "an empty spec must not fake a MASTER"

    big = "\n".join(f"§{i} invariant line with padding text"
                     for i in range(4_000))          # ~150k chars
    built = _build_master(big)
    assert big in built, "the spec was altered on the way into MASTER"
    assert built.startswith(MAIN) and built.endswith(big)
    # and it survives the delivery path intact
    m2: list[dict] = []
    with_system(m2, built)
    assert m2[0]["content"] == built and big in m2[0]["content"]

    # MASTER reflects whatever SPEC holds, with no I/O anywhere
    assert (MASTER == MAIN) == (not SPEC.strip())
    if SPEC.strip():
        assert SPEC in MASTER

    # there is no longer any way to load a specification from outside
    import os as _os
    for gone in ("spec_candidates", "_load_master_spec", "reload_spec",
                 "SPEC_SOURCE"):
        assert gone not in globals(), f"{gone} still exists"
    _os.environ["FULLAGENT_SPEC"] = "/tmp/should-be-ignored.txt"
    try:
        import importlib
        import fullagent.systemprompt as _sp
        importlib.reload(_sp)
        assert _sp.SPEC == SPEC, "an env var changed the specification"
    finally:
        _os.environ.pop("FULLAGENT_SPEC", None)

    # EVERY dispatched agent carries the specification, not just the
    # sovereign one. The workers are what actually write the files, and
    # they used to receive a ~640-char role brief with none of the rules.
    # (run as __main__, so the globals here are the ones the builders read;
    # importing the module by name would patch a second, separate copy)
    _g = globals()
    _saved = _g["SPEC"]
    try:
        probe = "§1 MY RULE — binding on every agent\n" + "x" * 5_000
        _g["SPEC"] = probe
        for role in ROLE_BRIEFS:
            assert probe in worker(role, 8), f"worker:{role} lost the spec"
        assert probe in scout(), "scout lost the spec"
        # and an empty spec adds nothing rather than an empty banner
        _g["SPEC"] = ""
        assert worker("coder", 8) == WORKER.format(
            role_brief=ROLE_BRIEFS["coder"], max_workers=8)
        assert scout() == SCOUT
    finally:
        _g["SPEC"] = _saved

    # the sovereign prompts cannot be replaced at runtime
    for locked in ("main", "master", "scout"):
        try:
            register(locked, "hijacked")
        except PromptLocked:
            pass
        else:
            raise AssertionError(f"{locked} was replaceable at runtime")
    assert get("main") == MAIN and get("master") == MASTER
    # sub-agent roles still register, because they must
    register("worker:tester", "you are a tester")
    assert get("worker:tester") == "you are a tester"

    print(f"SYSTEMPROMPT SELF-TEST PASS  (MASTER = {len(MASTER):,} chars, "
          f"SPEC = {SPEC_CHARS:,} chars, compiled in)")