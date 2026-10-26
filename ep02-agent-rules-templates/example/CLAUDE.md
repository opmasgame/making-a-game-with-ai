# CLAUDE.md · Lantern Market

<!-- A filled-in example. Lantern Market is made up; the habits are the ones we use. -->

Reply in English.

## What this is

Lantern Market is a two-player card game about running stalls in a night market: buy at dusk, sell before the lanterns go out. One developer, building it with Claude Code. Pitch: "a 20-minute trading duel you can learn in one game".

Current state: design documents only. No code, no prototype yet.

## Progress (day 3)

- `docs/00-concept.md` v0.4. Player count, length and the four card types are DECIDED. Turn structure and the scoring numbers are still PROPOSED.
- Next: answer the three questions at the end of 00; then write `01-turn.md`.

## Document rules

- File names `NN-topic.md`. Every document starts with `Version: v0.x. Day: N. Status: …`. Bump the version on every change and log what changed in a review record at the end.
- **Mark the source.** What I explicitly approved is **DECIDED**. What you suggest is **PROPOSED**. Never write a proposal as if I approved it. A hook (`tools/doc_guard.py`) blocks edits that add, change or remove DECIDED lines; when it blocks you, keep the idea as PROPOSED and ask.
- **Keep design and implementation apart.** Until there's a prototype and running evidence, don't write "verified". Numbers without evidence are examples, and say so.
- **Ask with a default.** When you need a decision, ask it as a question with a default answer I can accept or reject. End every document with "Choices I made for you".
- **Scope check.** Solo developer, evenings only. Ask of every design: can one person build and balance this in three months?

## Tech

- Base the tech on my last finished game (a Godot 4 project with a small Go server). Don't invent a stack; only write down what's different.

## Key files

| Path | Purpose |
|---|---|
| `docs/00-concept.md` | Concept, what's DECIDED, open questions |
| `docs/architecture/ADR-0001-foundation.md` | The technical foundation and its hard constraints |

## Working rules

- Ask before changing anything I have already confirmed.
- Commit before large changes.
- Card names and flavour text are mine. Leave `<name>` placeholders instead of inventing them.
