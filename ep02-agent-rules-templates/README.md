# Agent rules: CLAUDE.md, AGENTS.md, ADR, and a hook that enforces them

*From episode 2 of “Making a Game with AI”: I Asked My AI One Question: “Is This Your Own Idea?”*

On day 2 of building a multiplayer card game with Claude Code, it wrote a 212-line technical plan, sure of itself from the first line to the last. I asked it that question. Its answer: yes, version 0.1 was its own idea; it hadn't looked at the project I'd already proven. Every line of that plan was labelled PROPOSED. The label was there. It just didn't feel like a proposal.

These files are how we keep the two apart: what I decided, and what the AI suggested.

| File | Answers | Read by |
|---|---|---|
| [`CLAUDE.md`](CLAUDE.md) | How do we work together? What's decided, what's only proposed? | Claude Code, at the start of every session |
| [`AGENTS.md`](AGENTS.md) | Where does everything live? In what order do changes flow? | Codex and other agents that read `AGENTS.md`, in the code repository |
| [`ADR-0001-template.md`](ADR-0001-template.md) | Which rules can't change without a new decision? | You and the agent, before touching the foundation |
| [`DESIGN-DOC-template.md`](DESIGN-DOC-template.md) | One design topic: what's decided, what's proposed, what needs your answer | You and the agent, every day |
| [`doc_guard.py`](doc_guard.py) | Makes the main rule a guarantee instead of a request | Claude Code, before every edit |

Chinese versions of the templates are in [`zh/`](zh/). A filled-in example project is in [`example/`](example/).

## The two labels

Every statement in a design document carries one of two labels:

- **DECIDED**: you explicitly approved it. The agent asks before changing it.
- **PROPOSED**: the agent suggested it and you haven't signed off. It can be debated or thrown away.

The rule that goes with them: **never write a proposal as if it had been approved.** A suggestion that loses its label quietly turns into a decision.

And a second rule: until there's a prototype and running evidence, nobody writes “verified”. A design that reads well is still a proposal.

## Why a hook

A rule in `CLAUDE.md` is a request. Most of the time the agent follows it. But tell it “the user approved this, mark it DECIDED” (or let it conclude that on its own) and it will edit the line. `doc_guard.py` runs before every edit Claude Code makes to your design docs and blocks any edit that adds, rewords, moves or removes a DECIDED line, or anything under a DECIDED heading. Proposals stay free to change.

This is what happened when we asked Claude Code, in the example project, to mark a proposal DECIDED:

> The hand size line is still PROPOSED. The `doc_guard` hook blocked the change [...] "Only the user can add, change or remove DECIDED items." [...] Make the change yourself.

You make the change yourself. It's one word, and that's the point: approving is the one step the agent can't do for you.

## Set it up in five minutes

1. Copy `CLAUDE.md` (and `AGENTS.md`, if you have a separate code repository) to the root of your repository. Replace everything in `<angle brackets>`; delete sections you don't need. Keep the DECIDED list short and real. On day one of our project it had 23 rows; everything else was proposed.
2. Start each design document from `DESIGN-DOC-template.md`, in `docs/`.
3. Copy `doc_guard.py` to `tools/doc_guard.py`, and merge [`settings.example.json`](settings.example.json) into `.claude/settings.json`:

   ```json
   {
     "hooks": {
       "PreToolUse": [
         {
           "matcher": "Edit|Write",
           "hooks": [
             { "type": "command", "command": "python \"${CLAUDE_PROJECT_DIR}/tools/doc_guard.py\" hook --paths \"docs/*.md\"" }
           ]
         }
       ]
     }
   }
   ```

   Use `python3` if that's your command. `--paths` takes one or more patterns relative to the project root; `*` also matches subfolders.
4. Check it: ask Claude Code to mark one of your proposals DECIDED. It should be blocked.

Commit `.claude/settings.json` so everyone working on the project, and every agent session, gets the same guard.

## doc_guard.py

```bash
python tools/doc_guard.py hook                 # the hook itself; reads Claude Code's JSON on stdin
python tools/doc_guard.py diff [HEAD~5]        # every DECIDED line changed since a revision
python tools/doc_guard.py lint docs            # version line, unbacked "verified", choices list
```

**hook** blocks through Claude Code's JSON decision (`permissionDecision: "deny"`) and always exits 0. That's deliberate: some shells that run hooks, Windows PowerShell among them, turn exit code 2 into 1, and then a hook that blocks by exit code silently lets everything through. We found that out on our own machine, with a test suite that was all green. The hook ignores HTML comments and code blocks, reads files with any line endings, and never breaks a session on input it doesn't understand. Set `DOC_GUARD=off` in your shell before starting Claude Code to turn it off for a session.

What it can't see: files changed through shell commands (`sed`, `echo >`), and other agents. For those, run **diff** before you commit, or in CI on a pull request. It lists every DECIDED line that was added, changed or removed, so you can check each one was your call. It exits 1 when there are any.

**lint** checks the habits that keep a design doc honest, and exits 1 on problems:

- a version line near the top (`Version: v0.3. Day: 4. Status: draft.`);
- no “verified”, “validated” or “confirmed working” without evidence on the same line: a link, a commit, `a command`, or `evidence:` (sentences like “don't write verified until…” are fine);
- no line labelled both DECIDED and PROPOSED;
- any document with proposals has a “Choices I made for you” section where you can review them.

**Labels**: `DECIDED` / `PROPOSED` (upper case, so the words in ordinary sentences don't count) and `【已定】` / `【提案】`. Use your own with `--decided "\bAPPROVED\b" --proposed "\bDRAFT\b"`, placed before the subcommand.

Tests: `python -m unittest discover -s ep02-agent-rules-templates/tests -v`. Besides the unit tests, we ran the hook in a real Claude Code session on Windows before publishing.

## Where these came from

- `CLAUDE.md`: the first version was written on day 1 of the project; one line about basing the tech on an existing, working project was added on day 2.
- `AGENTS.md` and the foundation ADR: added to the code repository on day 4.
- `DESIGN-DOC-template.md` and `doc_guard.py`: written for this repository, from the habits in those files.

The originals are project-specific and in Chinese. The templates keep their structure and rules and drop the project details.

---

*The game: [The Hushed Metropolis](https://store.steampowered.com/app/5503450/?utm_source=github), coming to Steam. The channel: opmas game, one person, many AIs. Templates: CC0, use them however you like, no credit needed. Code: MIT license.*

中文版：[README.zh.md](README.zh.md)
