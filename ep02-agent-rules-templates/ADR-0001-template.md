# ADR-0001 · <Technical foundation>

Status: <Proposed | Accepted | Superseded by ADR-NNNN>. Day: <N>. Supersedes: <none>.

<One paragraph: where the design lives, what this record covers, and where the full reasoning is.>

## Decision

- <Engine / client: what it does and doesn't do.>
- **<Which side is the single authority for game rules.>** The other side doesn't copy rule formulas.
- <Transport and protocol.>
- <Server shape and storage. What you are deliberately *not* adding yet.>
- <Config data: the single hand-written source and the pipeline from it.>

## Constraints (changing one needs a new ADR)

- <A rule that keeps the core testable, with a way to check it, e.g. a grep that must return nothing.>
- <A rule about determinism: randomness and clocks are injected, never global.>
- <A rule about what never ships to the client.>
- **Don't pass off a placeholder, a mock or a partial test as the implementation.** Unimplemented features fail loudly (for example, return `NOT_IMPLEMENTED`) and change no state.

## Non-goals

Not in this stage: <list>. Write them down so nobody "helpfully" builds them.

## Review record

- v0.1 (day <N>): <what was decided, and who approved it>.
