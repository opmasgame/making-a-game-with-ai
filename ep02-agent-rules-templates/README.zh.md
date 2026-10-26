# AI 协作规矩：CLAUDE.md、AGENTS.md、ADR 模板，外加一个替你守规矩的钩子

*出自《用 AI 做游戏》第 2 期：我只问了 AI 一句：这是你自己想的吗？*

我带着 Claude Code 做多人卡牌游戏，第 2 天它写了一份 212 行的技术方案，从头到尾都很笃定。我只回了一句：「方案不对，这是你自己想的吗？」它的回答是：是，0.1 版是它自己想的，没看我已经验证过的工程。那份方案每一行都标着【提案】。标记一直在，只是读起来一点也不像提案。

下面这几样东西，就是我们从那以后用来把两件事分开的：哪些是我定的，哪些是 AI 提的。

| 文件 | 回答什么 | 谁读 |
|---|---|---|
| [`zh/CLAUDE.md`](zh/CLAUDE.md) | 我们怎么合作；哪些已经定了，哪些只是提案 | Claude Code，每次开工先读 |
| [`zh/AGENTS.md`](zh/AGENTS.md) | 东西都放在哪；改动按什么顺序走 | Codex 等会读 `AGENTS.md` 的 AI，在代码仓库里 |
| [`zh/ADR-0001-模板.md`](zh/ADR-0001-模板.md) | 哪些规矩，不开一个新的决策就不能改 | 你和 AI，动地基之前 |
| [`zh/设计文档-模板.md`](zh/设计文档-模板.md) | 一个设计主题：哪些定了，哪些是提案，哪些等你拍板 | 你和 AI，每天 |
| [`doc_guard.py`](doc_guard.py) | 把最重要的那条规矩，从「请求」变成「保证」 | Claude Code，每次改文件之前 |

英文模板在本目录下，填好的示例项目在 [`example/`](example/)（英文）。

## 两种标记

设计文档里的每一条，都标上两种标记之一：

- **【已定】**：你明确拍过板。AI 要改，先问你。
- **【提案】**：AI 提出来的，你还没逐项确认。可以讨论，也可以推翻。

配套的规矩：**绝不把提案写成用户批准过。** 建议一旦丢了标记，就悄悄变成了决定。

另一条：没有原型、没有运行证据之前，谁都不写「已验证」。读起来再顺，也还是提案。

## 为什么要一个钩子

写在 `CLAUDE.md` 里的规矩，说到底是请求。多数时候 AI 会照做；可你只要说一句「用户同意了，标成已定」，或者它自己这么以为了，它就会去改那一行。`doc_guard.py` 在 Claude Code 每次改设计文档之前先跑一遍：只要这次编辑会新增、改写、挪动、删除任何一条【已定】（或【已定】标题下面的任何内容），就拦下来。【提案】照常随便改。

我们在示例项目里让 Claude Code 把一条提案标成已定，它最后这样回复：

> The hand size line is still PROPOSED. The `doc_guard` hook blocked the change [...] Make the change yourself.

（大意：那一行还是【提案】，钩子拦下了这次修改，请你自己改。）

你自己改，就改一个词。要的就是这一步：拍板，是 AI 唯一不能替你做的事。

## 五分钟装好

1. 把 `zh/CLAUDE.md`（代码单独一个仓库的话，还有 `zh/AGENTS.md`）拷到仓库根目录，`<尖括号>` 换成你自己的，用不上的小节删掉。【已定】清单要短、要真：我们项目第一天结束时只有 23 行，其余全是提案。
2. 每份设计文档从 `zh/设计文档-模板.md` 开始写，放在 `docs/` 下。
3. 把 `doc_guard.py` 拷到 `tools/doc_guard.py`，再把 [`settings.example.json`](settings.example.json) 的内容并进 `.claude/settings.json`：

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

   你的命令是 `python3` 就写 `python3`。`--paths` 写相对项目根目录的路径，可以写多个；`*` 也会匹配子文件夹。
4. 试一下：让 Claude Code 把你的某条提案标成【已定】，应该会被拦下。

把 `.claude/settings.json` 一起提交，所有参与项目的人、每一次 AI 会话，都会用同一个钩子。

## doc_guard.py 的三个用法

```bash
python tools/doc_guard.py hook                 # 钩子本身，从标准输入读 Claude Code 传来的 JSON
python tools/doc_guard.py diff [HEAD~5]        # 列出某个版本以来改动过的每一条【已定】
python tools/doc_guard.py lint docs            # 查版本行、没证据的「已验证」、「替你做的选择」
```

**hook** 用 Claude Code 的 JSON 决定（`permissionDecision: "deny"`）来拦，退出码永远是 0。这是故意的：有些跑钩子的 shell（Windows PowerShell 就是）会把退出码 2 改成 1，靠退出码拦截的钩子就悄悄什么都不拦了。这是我们在自己的电脑上实测撞到的，当时单元测试全是绿的。钩子会跳过 HTML 注释和代码块，不管文件是什么换行符都能读；看不懂的输入一律放行，不会把会话卡住。想临时关掉，就在启动 Claude Code 之前，在 shell 里设 `DOC_GUARD=off`。

它看不到的：用 shell 命令改的文件（`sed`、`echo >`），以及别的 AI 工具。这部分靠 **diff**：提交前跑一下，或者在 CI 里对合并请求跑。它会列出每一条新增、改写、删除的【已定】，你逐条确认是不是你拍的板。有改动就退出码 1。

**lint** 查的是让设计文档保持诚实的几个习惯，有问题退出码 1：

- 开头附近有版本行（`版本：v0.3。第 4 天。状态：草稿。`）；
- 写「已验证」「验证通过」「已确认可用」的那一行，必须带证据：链接、提交号、`命令`，或「证据：」（「没有原型之前不写已验证」这类句子不算）；
- 同一行不能既标【已定】又标【提案】；
- 有提案的文档，结尾要有「替你做的选择」一节，让你逐条回。

**标记**：默认认 `【已定】`/`【提案】` 和英文的 `DECIDED`/`PROPOSED`（英文只认大写，普通句子里的词不算）。要用别的写法，在子命令前面加 `--decided "【定稿】" --proposed "【草案】"`。

测试：`python -m unittest discover -s ep02-agent-rules-templates/tests -v`。除了单元测试，发布前我们还在 Windows 上用真实的 Claude Code 会话跑过这个钩子。

## 来历

- `CLAUDE.md`：第一版写于项目第 1 天；第 2 天加了一条「技术方案参照已经跑通的工程」。
- `AGENTS.md` 和技术基座 ADR：第 4 天进的代码仓库。
- 设计文档模板和 `doc_guard.py`：照这几份文件里的习惯，为这个仓库新写的。

原件跟项目绑得很紧。模板保留了结构和规矩，去掉了项目细节。

---

*游戏：《缄默都会》，即将登陆 Steam：https://store.steampowered.com/app/5503450/ 。频道：opmas game，一个人，和一群 AI。模板是 CC0，随便用，不用署名；代码是 MIT 许可。*

English: [README.md](README.md)
