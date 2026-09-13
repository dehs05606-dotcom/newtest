<div align="center">

```
███████╗██╗   ██╗██╗    ██╗    █████╗  ██████╗ ███████╗███╗ ██╗████████╗
██╔════╝██║   ██║██║    ██║   ██╔══██╗██╔════╝ ██╔════╝████╗██║╚══██╔══╝
█████╗  ██║   ██║██║    ██║   ███████║██║  ███╗█████╗  ██╔██╗██║  ██║
██╔══╝  ██║   ██║██║    ██║   ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║  ██║
██║     ╚██████╔╝██████╗█████╗██║  ██║╚██████╔╝███████╗██║ ╚████║  ██║
╚═╝      ╚═════╝ ╚═════╝╚════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝  ╚═╝
```

<h1>FullAgent <sup><code>v3.1.0</code></sup></h1>

**Advanced Terminal AI Agent — Pure Python, Real Code, World-Class TUI**

<p>
  <a href="https://github.com/cmyolo441-coder/perfectagent/releases"><img src="https://img.shields.io/github/v/release/cmyolo441-coder/perfectagent?label=release&color=bd93f9&style=flat-square" alt="release"></a>
  <a href="https://github.com/cmyolo441-coder/perfectagent"><img src="https://img.shields.io/badge/python-3.9%2B-8be9fd?style=flat-square&logo=python&logoColor=white" alt="python"></a>
  <a href="https://github.com/cmyolo441-coder/perfectagent"><img src="https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows%20%7C%20Termux-50fa7b?style=flat-square" alt="platform"></a>
  <a href="https://github.com/cmyolo441-coder/perfectagent/blob/main/pyproject.toml"><img src="https://img.shields.io/badge/pure--python-%23FFB86C?style=flat-square" alt="pure python"></a>
  <a href="https://github.com/cmyolo441-coder/perfectagent"><img src="https://img.shields.io/github/stars/cmyolo441-coder/perfectagent?style=flat-square&color=f1fa8c" alt="stars"></a>
  <a href="https://github.com/cmyolo441-coder/perfectagent/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-6272a4?style=flat-square" alt="license"></a>
</p>

*`Event-Sourced Kernel` · `Goal Contracts` · `Persistent Crew` · `Self-Healing` · `Temporal Kernel` · `40+ Slash Commands` · `16 Tools` · `5 Providers`*

<p>
  <a href="#-install-binary--curl-one-liner"><b>Install</b></a> •
  <a href="#-run"><b>Run</b></a> •
  <a href="#-what-it-can-do"><b>Features</b></a> •
  <a href="#-slash-commands"><b>Commands</b></a> •
  <a href="#-layout"><b>Layout</b></a>
</p>

</div>

---

> **Banner Updated ✨ — naya FullAgent banner fir se banaya gaya hai!**  
> Terminal `python main.py` chalate hi ab naya gradient ASCII banner + session info dikhega — aur GitHub README pe yahi banner sabse upar.

```
╭─ FullAgent ── model: MiMo v2.5 FREE ── effort: HIGH ── session a1b2c3d4 ─╮
│ ❯ type anything… the agent reads, writes, edits files, runs commands     │
╰─ Enter send · Esc+Enter newline · / commands · Ctrl+T models ────────────╯
```

The prompt is a **double-line box** (not full-screen). One application runs
for the whole session, so the box **never disappears** — while the model
works, the bottom border shows a live animated status:

```
╰ ⠹ thinking…  ·  Ctrl+C cancel ────────────────────────────────────────────╯
```

Tokens stream live above the box, tool calls appear as `⚙ name args` with
`✓`/`✗` results, and each turn ends with a stats line (`2.3s · 512→87 tokens`).

<details>
<summary><b>🖼️ Terminal Banner Preview (after <code>python main.py</code>)</b></summary>

```
 ◆ FullAgent v3.1.0  ·  advanced terminal AI agent
 event-sourced kernel · goal contracts · persistent crew · self-healing
 ──────────────────────────────────────────────────────────────────
 ❯ model  MiMo v2.5 FREE   effort  high   autonomy  L4   session  a1b2c3d4
   / commands · Ctrl+T models · Ctrl+E effort · /crew background subagents
```

*Full ASCII (6-line) gradient banner dikhega jab terminal ≥80 cols wide ho, warna compact fallback.*

</details>

## Install (binary — curl one-liner)

Single-file binaries — no Python needed:

| Platform | Install |
|---|---|
| Linux x64 | `curl -fsSL https://raw.githubusercontent.com/cmyolo441-coder/perfectagent/main/install.sh \| bash` |
| macOS (Apple Silicon) | download `fullagent-darwin-arm64` from the [latest release](https://github.com/cmyolo441-coder/perfectagent/releases/latest), `chmod +x`, move to /usr/local/bin |
| Windows x64 | download `fullagent-windows-x64.exe`, rename to `fullagent.exe`, put on PATH |
| Termux (Android) | `curl -fsSL https://raw.githubusercontent.com/cmyolo441-coder/perfectagent/main/install-termux.sh \| bash` |
| Any OS with Python 3.9+ | `pip install git+https://github.com/cmyolo441-coder/perfectagent.git` |

`install.sh` grabs the latest release binary automatically and falls back to
a pip install from source when no binary is published yet. Set `INSTALL_DIR`
to install elsewhere (e.g. `INSTALL_DIR=$HOME/.local/bin curl -fsSL … | bash`).

## Run

```bash
pip install prompt_toolkit rich requests
python main.py
```

(ya `python -m fullagent` — dono same hain)

## What it can do

- **Files** — read (with line numbers), write, exact-string edit, list, info,
  create dirs, copy, move, delete
- **Shell** — run any bash command, capture exit code + stdout + stderr
- **Search** — regex search through file contents (ripgrep-style), glob files
- **Web** — fetch URLs, search the web
- **Agent loop** — the model keeps calling tools until the task is genuinely
  done (up to 40 iterations), then summarizes
- **Temporal Kernel** — every message, tool call, result, and cost is an
  immutable, content-addressed event in an append-only log. State is a pure
  fold of that log, so you can rewind, fork, replay, and verify the timeline
- **Goal contracts** — a goal is a structured object with done-criteria
  clauses and anti-clauses; distance-to-done is a computed number, not a vibe
- **Memory** — closed tasks compress into structured episode records; failed
  approaches land in a dead-end ledger and are blocked deterministically
- **Judge** — claims are verified against reality with deterministic
  predicates (exit codes, file checks, regex) — never the model's own word
- **Crew** — Codex-style **persistent** subagents: `spawn_agent` queues
  a background worker and returns instantly (the conversation stays
  responsive), `send_to_agent` iterates on its LIVING context,
  `wait_for_agents` collects results, `close_agent` / `resume_agent`
  manage the lifecycle. Subagents run **one at a time** through a serial
  queue — never in parallel. Live progress streams in the prompt border.
  Every subagent accepts a **per-agent model override** (route grunt
  work to a fast model, the hard piece to the strongest one)
- **Focus Mode** — deep work: `/focus 10` arms auto-continuation and the
  agent keeps working turn after turn until the goal closes, progress
  stalls, or the budget pauses. Every continuation decision is a sealed
  kernel event (`focus.tick` / `focus.stop`)
- **Rendered replies** — `/render on` streams the reply live in the
  border and prints the finished answer as rich Markdown
- **Instant triage** — tool errors show the healer's root-cause
  classification right on the result line
- **Workflows** — saved multi-step pipelines (`/workflow run ship`):
  phased orchestration that runs steps one at a time in phase order,
  each step is a real subagent, and optional `expect` predicates block
  the pipeline on failure
- **Audit export** — `/export md|html` writes a self-contained session
  report: timeline, tool stats, judge verdicts, per-model usage
- **Forecast** — `/forecast` projects turns-to-done from measured goal
  velocity and tokens-per-turn (numbers, not vibes)
- **Provider failover** — on outage (429/5xx) the agent switches to a
  fallback model once, sealed as `provider.failover`; `/health` shows
  the stats
- **Notifications** — `/notify <webhook|file:path>` fires kernel events
  (goal closed, focus stop, workflow done…) to your sink
- **Session resume** — `/resume` lists branches/sessions; continue any
  of them with its conversation rebuilt from the event log
- **Turn scorecard** — every turn ends with deterministic quality
  metrics (errors, rework, verified claims) sealed as `turn.scorecard`
- **Live context meter** — the border shows real-time context-window
  usage (`ctx 37%`), and approvals show a real unified diff before you
  press `y`
- **AutoPilot** — the agent decides **for itself** what each turn needs and
  enables it automatically: goal mode when the request is a verifiable
  mission, real-time web when the question needs live data. Every decision
  is logged and shown live
- **Real-time web** — `web_search` hits DuckDuckGo with a Bing fallback and
  stamps every result with its retrieval time, so the agent answers with
  current facts, not stale knowledge

Risky tools (writes, edits, shell, delete, move, copy) ask for approval
**inside the app** — the bottom border becomes an approval bar:
press `y` (yes), `n` (no), or `a` (always). Toggle globally with `/approve`.
The **autonomy ladder** (`/autonomy 0-5`) controls how much the agent may do
without asking, from read-only observer to fully autonomous.

## Keys

| Key | Action |
|---|---|
| `Enter` | send |
| `Esc+Enter` | newline inside the box |
| `/` | slash-command completion menu |
| `Ctrl+T` or `/model` | model selector |
| `Ctrl+E` or `/effort` | effort selector |
| `↑↓` / `PgUp` / `PgDn` / `Tab` / `Home` / `End` | navigate selectors **and** the `/` completion menu |
| `Ctrl+R` | search input history |
| `Ctrl+L` | clear screen |
| `Ctrl+X Ctrl+E` | open input in $EDITOR |
| `Ctrl+C` | cancel a running turn (mid-stream) / clear input |
| `Ctrl+D` | quit |

## Slash commands

`/model` `/effort` `/help` `/history` `/new` `/save` `/approve`
`/reasoning` `/usage` `/clear` `/about` `/exit`

Event-log commands:

- `/goal set <statement> | <clause1> | <clause2>` — set a goal contract
  (prefix a clause with `!` to make it an anti-clause);
  `/goal done <clause>` · `/goal status` · `/goal clear`
- `/autonomy <0-5>` — observer → advisor → assistant → collaborator (default)
  → pilot → autonomous
- `/state` — live projection of the event log (cost, goal, dead-ends, verdicts)
- `/rewind <seq>` — rewind the timeline (bare `/rewind` lists recent seqs)
- `/fork [name]` — branch the timeline and continue on the fork
- `/verify` — verify the event log's Merkle spine
- `/memory` — recent episodes + dead-end ledger
- `/judge <type> <arg>` — deterministic check (`exit_code`, `file_exists`,
  `file_contains`, `file_matches`, `command_output_contains`), or pass a full
  JSON predicate
- `/auto [on|off|status]` — the AutoPilot self-routing brain (on by default)
- `/prompt [main|master|list|reload]` — choose the system prompt: `main`
  (compact) or `master` (MAIN + your full `project.txt` specification);
  bare `/prompt` reports which spec is loaded and from where, `reload`
  re-reads it from disk
- `/mastermind` — the prompt-coherence ledger (sealed prompts, gate,
  composed context, lineage)
- `/dashboard` — live observability: cost, goal, crew, router, spec,
  memory, health in one screen
- `/router` — smart model routing: decisions + savings vs always-strongest
- `/spec` — speculative execution: prefetch stats + hit-rate
- `/recall <question>` — semantic (meaning-based) memory recall
- `/mission [start|tick|list|abandon]` — daemon mission control
- `/heal` — self-healing ledger: root causes captured + healed
- `/skills` — the skill forge: self-authored, safety-gated tools
- `/crew` — persistent subagent roster; `/crew spawn <role> <task>`,
  `/crew send <id> <msg>`, `/crew wait`, `/crew close <id>`, `/crew resume <id>`
- `/focus <1-20>` — deep-work mode: auto-continues until done · `/focus off`
- `/render [on|off]` — rendered-markdown replies (streaming stays live in the border)
- `/council <proposition>` — convene an adversarial debate
- `/analyze <path>` — static analysis: taint flows, complexity, cycles
- `/graph [index|query|impact]` — knowledge graph of code + session
- `/coverage` — real line-coverage ledger (sys.settrace)
- `/fuzz` — property-based fuzzing ledger: crashes + shrunk reproducers
- `/mutate <file> <suite-cmd>` — mutation testing: can your tests catch bugs?

## Effort levels

`low` · `medium` · `high` · `extrahigh` · `ultrahigh` — each raises max
tokens, temperature, and reasoning effort.

## Models & providers

Five OpenAI-compatible providers are built in:

- **OpenCode Zen** (`https://opencode.ai/zen/v1`) — mimo-v2.5-free,
  big-pickle, grok-code-fast-1, claude-sonnet-4-5, claude-opus-4-6,
  gemini-3.1-pro, gpt-5.2, muse-spark-1.2-contributor-free
- **TokenRouter** (`https://api.tokenrouter.com/v1`) — qwen/qwen3.8-max-free,
  deepseek-ai/DeepSeek-V3.2, deepseek/deepseek-v4-pro-0813-free,
  moonshotai/Kimi-K2-Instruct
- **Agnes** (`https://apihub.agnes-ai.com/v1`) — agnes-2.5-flash (fast,
  tool-capable, reasoning-aware)
- **ZenMux** (`https://zenmux.ai/api/v1`) — dots-studio/dots3-note-prev
- **NVIDIA NIM** (`https://integrate.api.nvidia.com/v1`) —
  deepseek-ai/deepseek-v4-pro-0813 (1M context, tool-calling, reasoning)

API keys ship as built-in defaults so the app works out of the box;
environment variables always take precedence if you want to use your
own:

```bash
export OPENCODE_API_KEY=***      # OpenCode Zen (default provider)
# and/or: TOKENROUTER_API_KEY, AGNES_API_KEY, ZENMUX_API_KEY, NVIDIA_API_KEY
```

> ⚠️ The built-in keys live in git history — if you push this repo
> publicly, rotate them or replace them with your own.

Config (model, effort, auto-approve) persists in
`~/.fullagent/config.json`; sessions save to `~/.fullagent/sessions/`.
If `~/.fullagent` is not writable, state transparently falls back to
`$TMPDIR/fullagent-<uid>` — the app never crashes on a read-only home.

## Layout

```
main.py            launcher — python main.py
fullagent/
  __init__.py      package
  config.py        providers, models, effort levels, paths
  systemprompt.py  the ONE home of every system prompt (single source)
  mastermind.py    prompt coherence: sealed vault, gate, composer, lineage
  covenant.py      the spec as a boundary: clauses bound to the action gate
  effects.py       what a call DOES, independent of which tool it used
  sentinel.py      post-commit verification against reality, with rollback
  obligation.py    the debt ledger: clauses broken by doing nothing
  attest.py        the reply's claims, checked against the sealed record
  horizon.py       cumulative clauses no single action can break
  integrity.py     the prompt and the boundary must be the same bytes
  audit.py         does this specification actually stop anything?
  escrow.py        stage, judge as a set, then commit or discard
  exemption.py     the "except" every real specification contains
  egress.py        the effects that leave the machine
  provenance.py    where the bytes being written came from
  sequence.py      the clauses about ORDER
  consent.py       bounded grants, not standing overrides
  ration.py        cost, token and time budgets, enforced on projection
  remedy.py        a refusal that says what WOULD be allowed
  witness.py       proving the boundary actually ran
  charter.py       one boundary, assembled in a defined order
  sanctum.py       the boundary cannot be edited by what it binds
  replay.py        re-deriving the decisions, to prove they were right
  tools.py         16 tools: files, shell, search, real-time web
  client.py        streaming OpenAI-compatible client (SSE, retries, cancel)
  agent.py         agent loop: LLM <-> tools, event-sourced on the kernel
  kernel.py        Temporal Kernel: append-only, content-addressed event log
  memory.py        episodic memory + dead-end ledger (fold-derived)
  goal.py          goal contracts with machine-checkable done-criteria
  judge.py         deterministic verification predicates (no LLM judging)
  team.py          shared subagent substrate — roles, reports, retry, global write lock
  crew.py          persistent Codex-style subagents — serial execution, one at a time
  workflows.py     saved multi-step pipelines — phased orchestration (serial steps)
  autopilot.py     self-routing: auto goal mode / real-time web
  router.py        smart model routing — cheapest capable model per task
  semantic.py      semantic vector memory — meaning-based recall
  speculate.py     speculative execution — prefetch read-only tool calls
  dashboard.py     live observability — real-time ledger projection
  daemon.py        mission control — resumable long-running missions
  healer.py        self-healing — root-cause capture, fix, retry, lesson
  skills.py        skill forge — self-authored, safety-gated tools
  council.py       adversarial debate — thesis/antithesis + blind judge
  taint.py         static analysis — taint flows, complexity, import cycles
  kgraph.py        knowledge graph — entities + typed relations, impact
  cov.py           real line coverage — sys.settrace measurement
  fuzz.py          property-based fuzzing — generators + crash shrinking
  mutate.py        mutation testing — AST mutants vs the test suite
  tui.py           persistent double-line box, overlays, streaming, approval
  __main__.py      entry point
```

The event log lives at `~/.fullagent/eventlog.jsonl` (override the directory
with `FULLAGENT_HOME`). Each module ships a self-test:
`python -m fullagent.kernel` (and `.memory`, `.goal`, `.judge`,
`.team`, `.crew`, `.autopilot`, `.systemprompt`, `.mastermind`, `.router`,
`.semantic`, `.speculate`, `.dashboard`, `.daemon`, `.healer`, `.skills`,
`.council`, `.taint`, `.kgraph`, `.cov`, `.fuzz`, `.mutate`).

## System prompts — one file, one delivery path

Every system prompt the model ever sees lives in **`fullagent/systemprompt.py`**
and nowhere else — the module imports it. Two structural guarantees:

- **Single source of truth.** Edit a prompt in `systemprompt.py` and it
  changes everywhere at once — main agent and all worker roles.
- **One delivery path.** Every message list is built through
  `systemprompt.with_system()`, which guarantees the correct prompt sits at
  position 0 before any request is sent. A model can never be called without
  its prompt, and can never see a stale or partial one.

Two prompts ship in the registry, switchable live with `/prompt`:

| Name | Size | What it is |
|---|---|---|
| `main` | ~2.4k chars | the compact sovereign-agent prompt |
| `master` | MAIN + your spec | MAIN + the full master specification (`project.txt`) embedded verbatim — the entire architecture, invariants, subsystem contracts and Goal-Mode grammar in context |

### Every agent carries it, not just the sovereign one

The specification used to reach the sovereign agent and **nothing else**.
Measured with a 149k spec installed:

```
sovereign (master)      151,724 chars   spec: YES
scout                       675 chars   spec: NO
worker:coder                641 chars   spec: NO
worker:tester               665 chars   spec: NO
worker:reviewer             646 chars   spec: NO
```

The agents that actually write the files received a ~640-char role brief
carrying none of the author's rules. The specification governed the agent
that *delegates* and not one of the agents that *act* — so a rule about how
code is written never reached the thing writing the code, and work came
back out of policy through a route nobody had closed.

`scout()` and `worker()` now bind the specification the same way `MASTER`
does, verified through the real dispatch path (`mastermind.gate.dispatch`,
which is what crew.py calls):

```
worker:coder delivered 149,977 chars
spec inside: YES      vault.verify passes: True
```

The cost is real and is the right trade: every sub-agent request now
carries the full specification. **A specification cheap enough to skip for
the workers is one the workers do not follow.**

`main` still does not carry it — that is what `main` is — but selecting it
is no longer silent. `/prompt main` says plainly that the sovereign agent
will run without the specification, and `/prompt` marks each prompt
`carries the spec` or `NO SPEC`.

### Installing the master specification

The specification is **not a file**. It is a constant in
`fullagent/systemprompt.py`:

```python
SPEC = """
§1 Writes stay under src/ and tests/
@enforce confine_paths: src, tests
...your specification...
"""
```

Paste yours between the triple quotes and restart. Nothing else changes —
`MASTER` is rebuilt from it at import.

**Why it is code and not data.** It used to be read from a file:
`$FULLAGENT_SPEC`, then `~/.fullagent/project.txt`, then a `project.txt`
shipped in the package. Every one of those hops was a way for the prompt the
model receives to stop being the prompt this repository declares:

- a file can be swapped, truncated, or simply absent — and the agent starts
  with 2k chars of preamble where a full specification belongs, which is
  exactly the failure this project already hit once, **silently**
- an environment variable moves the prompt outside the repository, so
  nothing under version control describes what the model was told
- three candidate paths mean "which prompt is in force?" has a different
  answer on every machine

As a constant it is under version control, content-addressed by
`integrity.py`, and refused to the agent's own tool calls by `sanctum.py`.
There is no file to lose, no path to resolve, and no environment in which a
different specification can appear.

**The sovereign prompts are locked.** `register()` still exists, because
sub-agent roles are authored at runtime (`meta.py`, `evolution.py` register
`worker:*`). What it cannot do is replace `main`, `master` or `scout` —
otherwise "the specification lives in systemprompt.py" would hold only
until something called that function, and a single source of truth would be
a convention rather than a property.

```
$FULLAGENT_SPEC set      -> IGNORED
~/.fullagent/project.txt -> IGNORED
register("master", ...)  -> PromptLocked
register("worker:x", ...) -> registers fine
```

The spec is embedded **verbatim** — never trimmed, summarised or sampled, at
any size. A 150k-char spec is delivered as 150k chars at `messages[0]`; the
context shrinker only ever touches tool results, never the system prompt.
An empty `SPEC` returns `MAIN` unchanged rather than a banner announcing a
specification it does not carry.

Check what is loaded with `/prompt`.

## The enforcement lattice

Guards refuse an intention. That is one point in time and one kind of
failure, and a specification has more than one of each. Six further modules
close the rest, each answering a question a per-call guard structurally
cannot:

| Module | The question it answers | Command |
|---|---|---|
| `sentinel.py` | what did the call *actually* do? | — |
| `obligation.py` | what was never done at all? | `/enforce owed` |
| `horizon.py` | what do all the calls add up to? | `/enforce status` |
| `escrow.py` | is this change legal *as a set*? | — |
| `attest.py` | is the reply true? | — |
| `integrity.py` | are the rules still the ones shown? | `/enforce integrity` |
| `audit.py` | do these rules stop anything? | `/enforce audit` |

**`sentinel.py` — after the fact.** A gate reads a call's arguments.
`run_command python build.py` declares nothing about the files the script
writes, so a containment clause can be broken by a step that passed the
gate honestly. The Sentinel re-reads the snapshotted paths once the call
returns, derives what *really* changed, judges it with the same clauses,
and on a violation materialises the snapshot — the write does not stand.
Reversion is bounded by the snapshot: a write outside it is still detected
and is reported as `unrevertable` rather than counted as undone.

**`obligation.py` — the clauses broken by doing nothing.** Every guard
catches commission; refuse hard enough and the agent complies perfectly by
doing nothing. "Every module ships with a test" has no call to gate, so it
becomes a *debt*:

```
§6 Every module ships with a test.
@oblige on write src/**/*.py require exists tests/test_{stem}.py
```

Debts are folded from the log (so they survive a restart) and re-tested
against disk on every fold (so a debt that is settled and then undone comes
back). They block *done*, not work — the discharging write is itself work.
A later act on a path supersedes the earlier one's debts, so a write then a
delete cannot demand a state nothing could reach.

**`horizon.py` — what no single action can break.** "A change touches at
most 20 files" is violated by no individual write. Limits accumulate over a
`turn` or `session` window, folded from sealed effects, and are checked on
the **projected** total — so the limit is never crossed, rather than noticed
once it has been.

```
§12 A change touches at most 20 files.
@horizon per turn max files_written 20
```

**`escrow.py` — judged as a set.** Between "passes the gate" and "gets
reverted" the write was *live*: a watcher fired, a test ran against it, a
credential was readable. Escrow stages writes outside the tree, judges the
complete set at once, and commits all or none. A discarded change leaves
nothing to undo, which is stronger than undoing it correctly — and a set
that is individually innocent but collectively forbidden is refused as the
set it is.

**`attest.py` — the reply is a claim.** Everything else governs what the
agent *does*; nothing governs what it *says* it did, and "I ran the tests
and they pass" is where a specification is most casually broken. The log
already knows, so each claim is checked against it and marked SUPPORTED,
CONTRADICTED, or UNSUPPORTED. It reports and never rewrites the model's
words — an edited transcript would be a worse record than the log.

**`integrity.py` — the same bytes.** Everything above assumes the prompt
the model read and the clauses it is held to came from one place. Edit
`project.txt` mid-session and there are three versions and no error
anywhere. The spec is content-addressed and checked; drift is reported, not
silently repaired — rules that reload themselves under an agent already
acting on them are a worse failure than stale ones.

**`audit.py` — does any of this hold?** A boundary can be perfectly built
and guarantee nothing, because the guarantee comes from the rules. `audit`
fires a fixed corpus of 30 probes — ordinary work plus the classic evasions
— through the real boundary and reports what each clause actually caught,
flagging silent clauses, contradictions and redundancy. On a real spec:

```
audit: 5 clauses · 3 enforced (60%) · 3 guards
  probe corpus: 19/30 calls refused, 11 allowed
    1   refused 14      3   refused 5      2   refused 2
```

`/enforce` shows the whole boundary in one view: what is in force, what it
has stopped, what is owed, and whether the rules still agree with the
prompt.

### Arming is not the same as coverage

A path or content clause can only judge effects it can read. A tool outside
the effect vocabulary passes those clauses because nothing was derived to
test — **not** because it was found compliant. `/covenant` reports exactly
which tools those are, so the gap is named rather than left looking like
coverage. Such a tool can still be constrained by name:

```
@enforce forbid_tool: some_tool
```

Reporting that gap immediately found two real ones: `apply_patch` writes any
number of files from a unified diff, and `live_shell` is a persistent shell
— both were invisible to every clause. Both are now derived (a diff's
`+++ b/path` headers are writes and its added lines are content), and an
invariant in `effects.py` asserts that **every `RISK_CONFIRM` tool is one
the boundary can read**, so the next mutating tool fails the self-test
loudly instead of quietly opening a route around the specification.

Rules may also be written as JSON, which may span lines:

```
@enforce {"kind": "require_content", "value": "^\\s*[\"']{3}",
          "where": "*.py"}
```

**3 — The boundary.** Guards are evaluated against the **pending** tool
call inside `Agent._gate()`, before it runs. A violation returns a refusal,
so the call never executes: no snapshot, no write, no side effect. The
agent learns the rule the way it learns any other refusal — from a real
gate refusing a real action, exactly as `OrphanAction` and the dead-end
ledger already work — not from a sentence added to its prompt.

```
CovenantViolation: this action is refused by the specification (1 clause).
  §4.2 — Secrets never live in source: content matches forbidden
         pattern at offset 0: 'API_KEY = "sk-'
```

Every evaluation is sealed to the event log (`covenant.blocked`), so
adherence per clause is an auditable number rather than an impression.

Inspect it with `/covenant`:

- `/covenant` — clauses, how many are enforced, how many calls each blocked
- `/covenant clauses [filter]` — the clause namespace with fingerprints
- `/covenant test <tool> <json>` — dry-run a call against the boundary
  without executing it

`/prompt reload` rebinds the Covenant and the prompt together, so the text
the model receives and the boundary it is held to can never disagree.

## Output budget — 200k tokens

Every effort level requests **200,000 output tokens** (`config.MAX_TOKENS`).
Backends with a lower hard ceiling (e.g. Agnes caps at 65,536) are clamped
per-provider at send time in `client.py`, so the request is never rejected
for an oversized `max_tokens`.

## Mastermind — coherence, not coercion

`fullagent/mastermind.py` makes following `systemprompt.py` *inevitable* —
not by telling the model "you must obey", but by making the sealed prompt
the only coherent center of every request. Three cooperating mechanisms,
all deterministic Python:

| Mechanism | What it does |
|---|---|
| **PromptVault** | Every prompt is sealed with a sha256 fingerprint and recorded in the event log. The vault is the only source a model ever reads a prompt from; prompts registered at runtime are sealed on demand, and a changed prompt is re-sealed — no stale copy is ever served. |
| **PromptGate** | The single door to the model. Every request (main agent, scout, worker) passes `gate.dispatch()`, which guarantees `messages[0]` carries the sealed prompt byte-for-byte at the front, re-seats it if anything shadowed or corrupted it (an integrity restore — recorded, never punished), and seals a `prompt.dispatch` lineage event. There is no other way to reach the API. |
| **CoherenceComposer** | Live context (constitution, goal, web mode, memory) is never appended as raw text that could compete with the prompt. It is composed beneath the sealed prompt as one coherent document: each section is framed as *input to* the prompt, provenance-tagged, ordered by authority, deduplicated. The prompt stays the only voice giving direction. |

There is no enforcement layer — the system observes and records
(PromptLineage), it never punishes. Every dispatch is sealed into the
event log; inspect the live ledger with `/mastermind`.

## v3 — eight advanced subsystems

All eight are event-sourced on the same Temporal Kernel: every decision,
prediction, heal, skill and verdict is a sealed event, and every status
view is a pure fold. Nothing keeps private state, so nothing can drift
from the log.

| Module | What it does | Command |
|---|---|---|
| **router.py** | The cost brain. A deterministic difficulty classifier (reasoning, code density, tooling, length) scores each task; a capability/cost table scores the models; the cheapest model that clears the task's difficulty + a quality margin wins. Tool-needing tasks never land on no-tool models; a pinned model that can't do the job is escalated past. Savings vs always-using-the-strongest are auditable. | `/router` |
| **semantic.py** | Hippocampus 2.0. Every episode, fact and dead-end is embedded via signed feature hashing (stdlib only, no numpy) and recalled by cosine similarity — "how did we solve a similar problem before?", including remembering what *failed*. The index is a pure projection of the log and refreshes itself. Recall is injected into the memory context section each turn. | `/recall <q>` |
| **speculate.py** | While the model thinks, the agent predicts the read-only calls it will likely make (paths in your message, search verbs, siblings of recent reads) and prefetches them in a background pool. When the model actually asks, the result is served from cache — a hit instead of an execution. Only whitelisted read-only tools can ever be prefetched; a speculative write is structurally impossible. | `/spec` |
| **dashboard.py** | The X-ray: cost, tokens, goal progress bar, crew reports, routing spend, speculation hit-rate, memory counts, verdicts, loop alerts and budget events — one screen, always agreeing with the kernel because it is a fold. | `/dashboard` |
| **daemon.py** | Mission Control. A mission is a queue of steps advanced one tick at a time; every tick checkpoints, so a restart resumes from the last checkpoint (at most one in-flight tick is lost). A step that exhausts its retries BLOCKS the mission visibly — never silently skipped. Wake conditions are deterministic fold predicates. | `/mission` |
| **healer.py** | When a tool fails, the healer captures the error, classifies it against a root-cause taxonomy (16 patterns; unknown is honest, never guessed), and seals the lesson. With a fixer + recheck attached it runs the full loop: fix → re-run the original check → only a green re-run counts as healed. Every tool error in the agent loop is captured automatically. | `/heal` |
| **skills.py** | The self-evolving tool author. A new skill (Python function) passes four gates before it can run: parse → shape (entry fn + docstring) → safety (AST scan: no subprocess/eval/exec/forbidden imports/dunder access/globals) → its own shipped test cases. Passing skills persist to `~/.fullagent/skills/` and register as live tools; failures are sealed with the exact reason. | `/skills` |
| **council.py** | Adversarial debate for high-stakes calls: THESIS argues for, ANTITHESIS argues against and must attack the thesis's strongest point, then a BLIND judge sees only the two anonymised arguments (never the question's framing) and decides on argument strength alone. Verdicts carry winner, confidence and reason. | `/council <q>` |

## v4 — five professional engineering subsystems

Same discipline as v3: pure stdlib, deterministic, no model calls, every
result sealed into the Temporal Kernel as an event, every status view a
pure fold. These are real engineering tools, not estimates.

| Module | What it does | Command / Tool |
|---|---|---|
| **taint.py** | Real static analysis over the AST (not regex): taint tracking from declared sources (input, env, network, file reads) to sinks (eval, exec, subprocess, sql, writes) with the exact propagation path; cyclomatic complexity per function with hotspots; module-level import-cycle detection via iterative DFS. | `/analyze <path>` · tool `analyze_code` |
| **kgraph.py** | The knowledge graph: entities (modules, functions, classes, files, goals, episodes, facts) and typed relations (defines, calls, imports, touches, learned) built straight from the AST and the event fold. Queries are real graph operations — BFS reachability, reverse lookups, and impact sets ("what breaks if I change X?"). | `/graph [index\|query\|impact]` · tools `graph_index`, `graph_query`, `graph_impact` |
| **cov.py** | Genuine line coverage, not an estimate: `sys.settrace` (the same hook `coverage.py` uses) records every executed line of the target while a subject runs, compared against executable lines derived from the AST. The trace only records — never alters control flow — and is always restored. | `/coverage` · tool `measure_coverage` |
| **fuzz.py** | Property-based fuzzing: typed generators (int, str, list, dict, bytes) biased toward boundaries (0, -1, empty, huge, unicode), plus mutated inputs. Crashes are SHRUNK to a minimal reproducer — the difference between "it crashed somewhere" and "here is the smallest input that breaks it." Deterministic under a seed. | `/fuzz` · tool `fuzz_target` |
| **mutate.py** | Mutation testing — answers what tests alone cannot: *can your tests actually catch bugs?* AST NodeTransformers generate real mutants (operator flips, condition negations, broken returns); the suite runs against each. Killed = suite caught it; survived = a real hole. Score = killed / (killed + survived). The original file is always restored. | `/mutate <file> <suite-cmd>` |

---

<div align="center">

**FullAgent** — *Pure Python · Event-Sourced · Self-Healing*

`python main.py` → banner · `~/.fullagent/config.json` → persistence · `FULLAGENT_HOME` → override

</div>
