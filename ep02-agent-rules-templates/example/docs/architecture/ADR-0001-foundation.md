# ADR-0001 · Technical foundation

Version: v0.1. Day: 3. Status: Proposed. Supersedes: none.

Lantern Market's design lives in `docs/`. This record fixes the technical foundation for the first prototype: what goes where, and the rules that can't be broken without a new ADR. It follows the setup of my last finished game and only lists what's different.

## Decision

- **Godot 4 client.** It draws the table and sends commands. It never computes a rule.
- **The Go server is the only authority for game rules.** The client doesn't copy any formula, not even "to make it feel faster".
- WebSocket with JSON messages for the prototype. A binary protocol only if a measurement says we need one.
- One server process, game state in memory, a match log on disk. No database yet.
- Card data has one hand-written source: `cards.csv`. A script turns it into the server's config and the client's display data.

## Constraints (changing one needs a new ADR)

- The rules package imports no network, clock, file or random code. Check: `grep -rE '"(net|time|os|math/rand)"' server/rules` returns nothing.
- Randomness and time are passed in, so every match can be replayed from its seed and its command log.
- Generated config is committed but never edited by hand. Check: CI regenerates it and fails on any diff.
- **Don't pass off a placeholder, a mock or a partial test as the implementation.** An unimplemented command returns `NOT_IMPLEMENTED` and changes no state.

## Non-goals

Not in this stage: accounts, matchmaking, spectators, reconnecting, mobile builds.

## Choices I made for you

- JSON over WebSocket instead of HTTP polling **PROPOSED**. Turns are short; polling adds a second of lag to every move.
- No database in the prototype **PROPOSED**. Matches are short and nothing needs to survive a restart yet.

## Review record

- v0.1 (day 3): first draft, written from the concept doc and the old project's setup. Waiting for your review.
