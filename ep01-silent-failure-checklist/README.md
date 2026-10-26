# Silent Failure Checklist

*From episode 1 of “Making a Game with AI”: Zero Errors, Half Dead.*

Our first full simulation of The Hushed Metropolis ran 40 bots through a whole season: 122,025 commands, zero errors. Half the game never happened. Nothing crashed. Every broken piece was a rule doing exactly what it was told. This is the list we use now.

## 1. Make the whole kind of failure loud

When you find a silent failure, fix it, then add a check that catches **every** failure of that kind.

- [ ] Every enum value the data uses is one the code knows. If not, the server refuses to start.
- [ ] Every variable a rule mentions resolves to something real. If not, the server refuses to start.
- [ ] Every “main card” type a recipe asks for can be matched by at least one card.
- [ ] Every content entry that should exist in the world actually spawns (NPCs, organizations, posts).
- [ ] Rules are enforced on the command path too, not only when building the menu.

## 2. Prove every test can fail

- [ ] For each fix, write a test.
- [ ] Remove the fix and watch the test go red.
- [ ] Put the fix back and watch it go green.

A test that has never failed has never proven anything.

## 3. Don't trust “zero errors”

Ask instead: did the thing I designed actually happen? Sort every unused action into four buckets:

| Bucket | Meaning | What to do |
|---|---|---|
| 1. Never offered | Nobody ever had the cards to see it | Card flow bug, usually a design hole |
| 2. Offered, never possible | It showed up, but the gate was never passed | Check why the gate fails |
| 3. Possible, never chosen | It could be done, nobody picked it | Fine. That's strategy |
| 4. Blew up | It was tried and failed at resolution | Must fix |

- [ ] Count from the menu the players actually saw, not from a second copy of the rules.
- [ ] Report errors separately from failures. A failed roll is a rule; an error is a hole.
- [ ] Make errors fail the tool, not just print a line in a report.
- [ ] Check that your diagnostic tool knows every way a thing can appear before you trust its numbers. Its blind spots create fake top-priority bugs.

## 4. Don't freeze exact numbers into tests

- [ ] Replace “must be exactly 14” with “every group the code uses exists and is non-empty”.
- [ ] Use lower bounds that catch real accidents (a table that didn't load, or loaded half).

If an exact count turns red every time you reasonably edit the spreadsheet, people learn to just bump the number. Then it's only noise.

---

*The game: The Hushed Metropolis, coming to Steam. The channel: opmas game, one person, many AIs.*

中文版：[README.zh.md](README.zh.md)
