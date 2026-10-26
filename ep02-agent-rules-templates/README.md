# CLAUDE.md / AGENTS.md / ADR templates

Three files that kept an AI coding agent honest while I built a multiplayer card game with it. They come from episode 2 of *Making a Game with AI* (opmas game).

| File | Answers | Read by |
|---|---|---|
| `CLAUDE.md` | How do we work together? What's decided, what's only proposed? | Claude Code, at the start of every session |
| `AGENTS.md` | Where does everything live? In what order do changes flow? | Any coding agent working in the code repository |
| `ADR-0001-template.md` | Which rules can't change without a new decision? | You and the agent, before touching the foundation |

## The two labels

Every statement in a design document carries one of two labels:

- **DECIDED**: you explicitly approved it. The agent asks before changing it.
- **PROPOSED**: the agent suggested it and you haven't signed off. It can be debated or thrown away.

The rule that goes with them: **never write a proposal as if it had been approved.** A suggestion that loses its label quietly turns into a decision.

## The second rule

Until there's a prototype and running evidence, nobody writes "verified". A design that reads well is still a proposal.

## How to use them

1. Copy the three files into your repositories: `CLAUDE.md` at the root of the design repository (or of a single repo), `AGENTS.md` at the root of the code repository, the ADR under `docs/architecture/`.
2. Replace everything in `<angle brackets>`. Delete sections you don't need.
3. Keep the decided list short and real. On day one of my project it had 23 rows; everything else was proposed.
4. When the agent needs a decision, have it ask a question with a default answer, and end every document with a short list of "choices I made for you". You answer under each one.

## Where these came from

- `CLAUDE.md`: the first version was written on day 1 of the project; one line about basing the tech on an existing, working project was added on day 2.
- `AGENTS.md` and the foundation ADR: added to the code repository on day 4.

The originals are project-specific and in Chinese. These templates keep their structure and rules and drop the project details.

License: CC0. Use them however you like.

---

# CLAUDE.md / AGENTS.md / ADR 模板

我带着 AI 做一款多人卡牌游戏，这三份文件管住了 AI 别乱来。出自《用 AI 做游戏》第 2 集（opmas game）。

| 文件 | 回答什么 | 谁读 |
|---|---|---|
| `zh/CLAUDE.md` | 我们怎么合作；哪些已经定了，哪些只是提案 | Claude Code，每次开工先读 |
| `zh/AGENTS.md` | 东西都放在哪；改动按什么顺序走 | 在代码仓库里干活的任何 AI |
| `zh/ADR-0001-模板.md` | 哪些规矩，不开一个新的决策就不能改 | 你和 AI，动地基之前 |

## 两种标记

设计文档里的每一条，都标上两种标记之一：

- **【已定】**：你明确拍过板。AI 要改，先问你。
- **【提案】**：AI 提出来的，你还没逐项确认。可以讨论，也可以推翻。

配套的一条规矩：**绝不把提案写成用户批准过。** 建议一旦丢了标记，就悄悄变成了决定。

## 另一条规矩

没有原型、没有运行证据之前，谁都不写「已验证」。读起来再顺，也还是提案。

## 怎么用

1. 把三份文件拷进你的仓库：`CLAUDE.md` 放设计仓库根目录（只有一个仓库就放那个仓库），`AGENTS.md` 放代码仓库根目录，ADR 放 `docs/architecture/`。
2. 把 `<尖括号>` 里的内容换成你自己的，用不上的小节直接删。
3. 已定清单要短、要真。我的项目第一天结束时只有 23 行，其余全是提案。
4. 需要你拍板时，让 AI 用「问题 + 默认答案」的形式来问；每份文档结尾列一张「替你做的选择」小清单，你在每一条下面回一句。

## 来历

- `CLAUDE.md`：第一版写于项目第 1 天；第 2 天加了一条「技术方案参照已经跑通的工程」。
- `AGENTS.md` 和技术基座 ADR：第 4 天进的代码仓库。

原件跟项目绑得很紧，而且是中文写的。模板保留了结构和规矩，去掉了项目细节。

许可：CC0，随便用。
