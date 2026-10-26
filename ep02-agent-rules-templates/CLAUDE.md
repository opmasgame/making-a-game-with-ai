# CLAUDE.md · <project name>

<!-- Claude Code reads this file at the start of every session. Keep it short; link out for details. -->

Reply in <language>.

## What this is

<One paragraph: what the project is, who builds it, and the one-line pitch.>

Current state: <e.g. "design documents only. No code, no prototype yet.">

## Progress (<day N>)

- <Document or milestone>: <version>. <What's decided, what's still proposed.>
- Next: <the next one or two steps>.

## Document rules

- File names `NN-topic.md`. Every document starts with `Version: v0.x. Day: N. Status: …`. Bump the version on every change and log what changed in a review record at the end.
- **Mark the source.** What the user explicitly approved is **DECIDED**. What the assistant suggests is **PROPOSED**. Never write a proposal as if the user approved it.
- **Keep design and implementation apart.** Until there's a prototype and running evidence, don't write "verified". Numbers without evidence are examples, and say so.
- **Ask with a default.** When a decision is needed, ask it as a question with a default answer the user can accept or reject. End every document with a short list of "choices I made for you".
- **Scope check.** <Your hard limit, e.g. "Solo developer: ask of every design: can one person build this?">

## Tech

- Base the tech on <an existing project that already runs, with its path>. Don't invent a stack; only write down what's different.

## Key files

| Path | Purpose |
|---|---|
| `docs/00-<concept>.md` | Concept, the DECIDED table, open questions |
| `docs/01-<core>.md` | <…> |

## Working rules

- Ask before changing anything the user has already confirmed.
- Commit before large changes.
- <Anything else that must hold in every session.>
