# AGENTS.md · <code repository name>

The code project. **The design isn't here.** It lives in <design repository path> (a separate git repository). Concept, rules, numbers and the technical plan follow that repository's `docs/`. This repository only implements them.

## Where things live

| Repository | What goes there |
|---|---|
| <design repository> | Design documents, **the source spreadsheet (the only hand-written source of config data)**, document audit scripts |
| <this repository> | Client, server, protocol, config pipeline, generated files |

To change the design: change the document first, then the spreadsheet, then run the pipeline. **Never the other way round.** Don't edit generated files to make the code run.

## Hard constraints

All of them are in `docs/architecture/ADR-0001-<foundation>.md`. The ones most likely to be broken:

1. <e.g. "The rules core is pure: no network, database, clock or system random inside it.">
2. <e.g. "The client doesn't compute rules. It renders views and sends commands.">
3. <e.g. "Generated files are committed but never edited by hand.">
4. Don't pass off a placeholder, a mock or a partial test as the implementation.

## Entry points

```
<command>   # spreadsheet → generated config
<command>   # protocol
<command>   # start local services
<command>   # run tests
```

## Commits

- One commit does one thing. A change that runs through the pipeline (sheet → generated files → code) can share a commit if the message spells out the chain.
- Generated files and their source go in the same commit.
