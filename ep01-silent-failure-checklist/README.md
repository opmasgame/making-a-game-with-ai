# Silent Failure Checklist (and three tools that run it)

*From episode 1 of “Making a Game with AI”: AI Wrote My Game. It Passed Every Test. Half of It Was Dead.*

Our first full simulation of The Hushed Metropolis ran 40 bots through a whole season: 122,025 commands, zero errors. Half the game never happened. Nothing crashed. Every broken piece was a rule doing exactly what it was told.

A checklist only helps if someone runs it. So each part of it now comes with a small tool that runs it for you. They are single Python files, standard library only, and they don't care what your game is written in. They read your data files, your logs and your git history.

| The problem | The tool | One line |
|---|---|---|
| Data points at things that don't exist: an enum the code doesn't know, a variable no rule can resolve, a card type nothing matches | [`refcheck.py`](refcheck.py) | `python refcheck.py spec.json` |
| “Zero errors”, but half the actions never happened, and nobody can say why | [`action_coverage.py`](action_coverage.py) | `python action_coverage.py --actions actions.csv run.jsonl` |
| The AI says “fixed, added a test, all green”, and the test would pass without the fix too | [`prove_test_fails.py`](prove_test_fails.py) | `python prove_test_fails.py -- pytest tests/test_shop.py` |

Each one exits non-zero when something is wrong, so it can stop a server from starting, a build, or a CI run. The tools are also a good thing to hand your AI assistant: “run `prove_test_fails.py` on your fix before you tell me it's done.”

## Try it in two minutes

```bash
git clone https://github.com/opmasgame/making-a-game-with-ai
cd making-a-game-with-ai/ep01-silent-failure-checklist
python refcheck.py demo/refcheck/spec.json
python action_coverage.py --actions demo/coverage/actions.csv demo/coverage/events.jsonl
```

The demo data has the same kinds of bugs we found in our game, planted in a tiny made-up one. `refcheck` finds five:

```
FAIL  recipes.main_card values are in cards.kind
      why: A recipe whose main card no card can match is never possible. Nothing crashes.
      recipes.csv:4  main_card = "Shop"   (known: Item, Itme, Person, Place, Secret, Store)
FAIL  rules.when values are in vars.name
      why: Every variable a rule mentions must resolve, or the rule is silently always false.
      rules.json[3]  when = "suspicion"   (known: gold, heat, hour)
...
refcheck: 7 checks, 5 failed, 5 problems
```

The toy simulation in [`demo/coverage/tiny_sim.py`](demo/coverage/tiny_sim.py) finishes “480 turns, 0 crashes”. `action_coverage` says otherwise:

```
3455 events, 8 designed actions, 85 errors

  4 blew up                      1
  1 never offered                1
  2 offered, never possible      2
  3 possible, never chosen       1
  ran                            3

== 2 offered, never possible: on menus, but its gate never opened. Check why.
   run-shop (Run a Shop)
      offered 260x; needs a Shop card x260
...
== resolved, but never possible on any menu: the command path skips the gate
   bribe-officer (Bribe an Officer)
      resolved 33x, possible on 0 of 480 menus

FAIL: 1 action blew up; 1 gate bypass
```

---

## The checklist

### 1. Make the whole kind of failure loud

When you find a silent failure, fix it, then add a check that catches **every** failure of that kind.

- [ ] Every enum value the data uses is one the code knows. If not, the server refuses to start. → `refcheck`: `{"column": "cards.kind", "in": "CardKind"}`, with `CardKind` read straight from your source file.
- [ ] Every variable a rule mentions resolves to something real. If not, the server refuses to start. → `refcheck`: `"extract"` pulls `$names` out of rule text.
- [ ] Every “main card” type a recipe asks for can be matched by at least one card. → `refcheck`: `{"column": "recipes.main_card", "in": "cards.kind"}`.
- [ ] Every content entry that should exist in the world actually spawns (NPCs, organizations, posts). → `refcheck`: `{"column": "spawns.npc", "covers": "npcs.id"}`.
- [ ] Rules are enforced on the command path too, not only when building the menu. → `action_coverage` flags any action that resolved although no menu ever said it was possible.

### 2. Prove every test can fail

- [ ] For each fix, write a test.
- [ ] Remove the fix and watch the test go red.
- [ ] Put the fix back and watch it go green.

→ `prove_test_fails` does all three, and always puts your files back.

A test that has never failed has never proven anything.

### 3. Don't trust “zero errors”

Ask instead: did the thing I designed actually happen? Sort every unused action into four buckets:

| Bucket | Meaning | What to do |
|---|---|---|
| 1. Never offered | Nobody ever had the cards to see it | Card flow bug, usually a design hole |
| 2. Offered, never possible | It showed up, but the gate was never passed | Check why the gate fails |
| 3. Possible, never chosen | It could be done, nobody picked it | Fine. That's strategy |
| 4. Blew up | It was tried and failed at resolution | Must fix |

- [ ] Count from the menu the players actually saw, not from a second copy of the rules. → log the menu where you build it (see below).
- [ ] Report errors separately from failures. A failed roll is a rule; an error is a hole. → `"outcome": "failure"` vs `"error"`.
- [ ] Make errors fail the tool, not just print a line in a report. → any bucket-4 action makes `action_coverage` exit 1.
- [ ] Check that your diagnostic tool knows every way a thing can appear before you trust its numbers. Its blind spots create fake top-priority bugs. → actions in the log that aren't in your list are reported, and fail the run. A `refcheck` check that looked at 0 values fails too.

### 4. Don't freeze exact numbers into tests

- [ ] Replace “must be exactly 14” with “every group the code uses exists and is non-empty”. → `refcheck`: `{"column": "cards.kind", "covers": "CardKind"}`.
- [ ] Use lower bounds that catch real accidents (a table that didn't load, or loaded half). → `refcheck`: `{"rows": "cards", "min": 100}`.

If an exact count turns red every time you reasonably edit the spreadsheet, people learn to just bump the number. Then it's only noise.

---

## refcheck.py

```bash
python refcheck.py path/to/spec.json      # -q to print failures only
```

Paths in the spec are relative to the spec file. Every problem is listed, not just the first. Exit 0 = clean, 1 = data problems, 2 = the spec itself is wrong (a missing file or a misspelled column is never silently skipped).

**Tables**: `"name": "file.csv"`, or an object:

| Key | Meaning |
|---|---|
| `file` | CSV, TSV or JSON. Export spreadsheets to CSV (UTF-8). |
| `key` | JSON only: where the list lives, e.g. `"data.cards"`. An object of objects becomes rows, with its keys in `_key`. |
| `delimiter` | CSV only, e.g. `";"`. |

**Enums**: a list, or names read out of source code:

```json
"CardKind": {"file": "../src/CardKind.cs", "after": "enum CardKind", "until": "}"}
```

`after` and `until` cut out the enum's body; comments, attributes, values and payloads are skipped, so C#, C++, TypeScript and Rust enums work with `"until": "}"` (Rust with struct variants: `"until": "\n}"`), Java with `"until": ";"`. For anything else set `"pattern"`, a regex with one group, applied line by line. Go constants: `{"file": "kinds.go", "after": "const (", "until": ")", "pattern": "^\\s*(Kind\\w+)"}`.

**Checks** (all accept `"why"`, printed with failures; `split` and `extract` shape the values):

| Check | Fails when |
|---|---|
| `{"column": "t.c", "in": "Enum or t.c"}` | a value isn't in the enum or that column |
| `{"column": "t.c", "covers": "Enum or t.c"}` | a value of the target never appears in this column |
| `{"column": "t.c", "unique": true}` | a value repeats |
| `{"column": "t.c", "required": true}` | a cell is empty |
| `{"rows": "t", "min": 100}` | the table has fewer rows |
| `"split": ";"` | cells hold lists like `a;b;c` |
| `"extract": "\\$(\\w+)"` | check only what the regex captures, e.g. variables in rule text |

An `in` or `unique` check that inspects 0 values fails, because a check that sees nothing passes silently. Add `"allow_empty": true` where that's expected.

**Make the server refuse to start**: run it before the server in your start script (`python refcheck.py data/spec.json && ./server`), or as the first step of the build. In CI:

```yaml
- run: python tools/refcheck.py data/spec.json
```

## action_coverage.py

```bash
python action_coverage.py --actions actions.csv run1.jsonl run2.jsonl [--csv report.csv] [--strict] [--allow late-game-1,late-game-2]
```

`--actions` is the list of every action you designed: a CSV with an `id` column (and optional `name`), or a text file with one id per line. Without it, “never offered” can't be counted: the log only knows what happened.

Log one JSON line where you build the menu and one where you resolve the action. Extra fields and other lines are ignored, so this can go into the log you already write.

```json
{"type": "menu", "options": [{"action": "run-shop", "possible": false, "reason": "needs a Shop card"}, {"action": "odd-jobs", "possible": true}]}
{"type": "resolved", "action": "odd-jobs", "outcome": "success"}
```

`outcome` is `success`, `failure` (a rule said no: a failed roll, a lost bid) or `error` (an exception, a missing key: a hole). An `offered` line per option works too: `{"type": "offered", "action": "...", "possible": true}`.

In C#:

```csharp
log.WriteLine(JsonSerializer.Serialize(new { type = "menu", options = menu.Select(o => new { action = o.Id, possible = o.Possible, reason = o.BlockedBy }) }));
log.WriteLine(JsonSerializer.Serialize(new { type = "resolved", action = cmd.Id, outcome = result.Outcome, detail = result.Error }));
```

In Go:

```go
enc := json.NewEncoder(logFile)
enc.Encode(map[string]any{"type": "menu", "options": options}) // []struct{Action string `json:"action"`; Possible bool `json:"possible"`; Reason string `json:"reason,omitempty"`}
enc.Encode(map[string]any{"type": "resolved", "action": cmd.ID, "outcome": outcome, "detail": errText})
```

Exit 1 when an action blew up, when an action resolved without ever being possible (the command path skips the gate), when the log names an action that isn't in your list, or when the log has no events at all. `--strict` also fails on buckets 1 and 2, minus anything in `--allow`; turn it on once the design settles.

## prove_test_fails.py

```bash
python prove_test_fails.py -- pytest -q tests/test_shop.py      # uncommitted changes, else the last commit
python prove_test_fails.py --commit a1b2c3d -- go test ./rules/...
python prove_test_fails.py --cmd "dotnet test --filter Shop"
python prove_test_fails.py --dry-run -- npm test                # only show which files would be taken out
```

What counts as a test file stays in place: `tests/`, `__tests__/`, `spec/`, `test_*.py`, `*_test.go`, `*.test.ts`, `*.spec.js`, `ShopTests.cs`, and so on. Add your own with `--tests "src/**/Checks/*"`. Everything else in the fix is taken out for step 2: changed files go back to their old version, new files are moved aside.

```
  ok   1. with the fix                        passed  [0.1s]
  XX   2. without the fix                     passed  [0.1s]
  ok   3. fix put back                        passed  [0.1s]

NOT PROVEN: the test passes without the fix, so it doesn't test this fix.
```

Exit 0 = proven, 1 = the test passes without the fix, 2 = it fails even with the fix (or fails again after it was put back: flaky?), 3 = usage or git problem. If step 2 failed only because the code no longer built or imported, it says so, because that's red for the wrong reason.

Your files are put back even on Ctrl+C. Until then a copy sits in `.git/prove-test-fails/`; if the process is killed outright, `python prove_test_fails.py --restore` puts them back. With `--commit`, your working tree must be clean.

## Tests

```bash
python -m unittest discover -s ep01-silent-failure-checklist/tests -v
```

They run on Linux and Windows, Python 3.9 and 3.13, on every push.

---

*The game: [The Hushed Metropolis](https://store.steampowered.com/app/5503450/?utm_source=github), coming to Steam. The channel: opmas game, one person, many AIs. MIT license.*

中文版：[README.zh.md](README.zh.md)
