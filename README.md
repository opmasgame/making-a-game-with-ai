![opmas game: one person, many AIs](.github/banner.jpg)

# Making a Game with AI

[![tests](https://github.com/opmasgame/making-a-game-with-ai/actions/workflows/tests.yml/badge.svg)](https://github.com/opmasgame/making-a-game-with-ai/actions/workflows/tests.yml)

Tools and templates for building software with AI coding agents, from the video series *Making a Game with AI* by **opmas game** (one person, many AIs). One developer is building a multiplayer card game, *The Hushed Metropolis*, with Claude Code, Codex and other AI tools. The series tells it from the real chat logs, commits and test reports, including the parts that went wrong.

Each folder here comes from one of those failures. It isn't specific to our game or to games: single Python files, standard library only, tested on Linux and Windows.

## What's here

| You have this problem | Use | From |
|---|---|---|
| Your data points at things that don't exist (an enum value the code doesn't know, a variable no rule defines), and nothing crashes | [`refcheck.py`](ep01-silent-failure-checklist/#refcheckpy) checks every reference and refuses to go on | [Episode 1](ep01-silent-failure-checklist/) |
| Bots or playtests report “0 errors”, but you can't tell which parts of the game never happened | [`action_coverage.py`](ep01-silent-failure-checklist/#action_coveragepy) sorts every designed action into four buckets | [Episode 1](ep01-silent-failure-checklist/) |
| The AI says “fixed, test added, all green” | [`prove_test_fails.py`](ep01-silent-failure-checklist/#prove_test_failspy) takes the fix out and checks the test goes red | [Episode 1](ep01-silent-failure-checklist/) |
| You can't tell which parts of your design you decided and which the AI just wrote | [`CLAUDE.md`, `AGENTS.md`, ADR and design-doc templates](ep02-agent-rules-templates/) with DECIDED / PROPOSED labels | [Episode 2](ep02-agent-rules-templates/) |
| The AI marks its own proposals as decided | [`doc_guard.py`](ep02-agent-rules-templates/#doc_guardpy), a Claude Code hook that blocks it | [Episode 2](ep02-agent-rules-templates/) |

## Try it

```bash
git clone https://github.com/opmasgame/making-a-game-with-ai
cd making-a-game-with-ai/ep01-silent-failure-checklist
python refcheck.py demo/refcheck/spec.json
python action_coverage.py --actions demo/coverage/actions.csv demo/coverage/events.jsonl
```

Both demos find the bugs planted in a small made-up game. To use a tool in your project, copy its one file.

## The episodes

| Ep | Title | Files |
|---|---|---|
| 1 | AI Wrote My Game. It Passed Every Test. Half of It Was Dead. | [`ep01-silent-failure-checklist/`](ep01-silent-failure-checklist/) |
| 2 | I Asked My AI One Question: "Is This Your Own Idea?" | [`ep02-agent-rules-templates/`](ep02-agent-rules-templates/) |
| 3 | I Hired 30 AI Players. The Richest One Quit on Monday. | — |
| 4 | AI Drew Every Picture in My Game. One Man Had Three Arms. | — |
| 5 | My AI Finished Nearly 2,000 Games Before a Human Finished One | — |
| 6 | Every Test Passed. Then a Human Played the Game My AI Built. | — |
| 7 | "Are You Just Not Able to Do This Job?" I Asked My AI | — |
| 8 | My AI Tools Used $5,000 of Tokens in 8 Days. 98% Was Rereading. | — |
| 9 | I Designed a Game for 1,000 Players With AI. Then I Cut It to 9. | — |
| 10 | The Trailer My AI Couldn't Fake | — |

Watch on YouTube: [@opmasgame](https://www.youtube.com/@opmasgame). The narration is an AI voice.

## Run the tests

```bash
python -m unittest discover -s ep01-silent-failure-checklist/tests
python -m unittest discover -s ep02-agent-rules-templates/tests
```

Found a bug, or a case a tool gets wrong? Open an issue with the input that shows it.

---

The game is coming to Steam: [wishlist The Hushed Metropolis](https://store.steampowered.com/app/5503450/?utm_source=github).

Code: MIT. Templates in `ep02-agent-rules-templates/`: CC0.

中文说明见 [README.zh.md](README.zh.md)。
