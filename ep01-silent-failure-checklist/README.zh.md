# 静默失效检查清单（附三个替你跑清单的工具）

*出自《用 AI 做游戏》第 1 期：AI 写的游戏零报错，可一半是死的。*

我们第一次完整模拟《缄默都会》，40 个机器人打完一整季：十二万两千条命令，零报错。可游戏有一半根本没发生。什么都没崩，每一处坏掉的地方，都是规则在一丝不苟地照着写好的做。

清单只有真有人去跑才有用。所以现在清单的每一部分都配了一个小工具，替你去跑。每个工具就是一个 Python 文件，只用标准库，不管你的游戏用什么语言写：它们读的是你的数据表、日志和 git 记录。

| 要解决的问题 | 工具 | 一行命令 |
|---|---|---|
| 数据指向不存在的东西：代码不认识的枚举值、规则里对不上的变量、没有任何牌能匹配的主牌类型 | [`refcheck.py`](refcheck.py) | `python refcheck.py spec.json` |
| 「零报错」，可一半的行动从没发生过，也没人说得清为什么 | [`action_coverage.py`](action_coverage.py) | `python action_coverage.py --actions actions.csv run.jsonl` |
| AI 说「修好了，加了测试，全绿」，可那个测试没有修复也照样能过 | [`prove_test_fails.py`](prove_test_fails.py) | `python prove_test_fails.py -- pytest tests/test_shop.py` |

出了问题，三个工具都以非零状态退出，所以能直接拦住服务器启动、拦住构建、拦住 CI。也很适合交给你的 AI 助手用：「说做完之前，先拿 `prove_test_fails.py` 跑一遍你的修复。」

## 两分钟试一下

```bash
git clone https://github.com/opmasgame/making-a-game-with-ai
cd making-a-game-with-ai/ep01-silent-failure-checklist
python refcheck.py demo/refcheck/spec.json
python action_coverage.py --actions demo/coverage/actions.csv demo/coverage/events.jsonl
```

演示数据是一个编出来的小游戏，里面埋的就是我们在自己游戏里踩过的那几类坑。`refcheck` 找出五处，比如：

```
FAIL  recipes.main_card values are in cards.kind
      recipes.csv:4  main_card = "Shop"   (known: Item, Itme, Person, Place, Secret, Store)
FAIL  rules.when values are in vars.name
      rules.json[3]  when = "suspicion"   (known: gold, heat, hour)
```

配方要一张「Shop」当主牌，可牌里只有「Store」；规则里写了 `$suspicion`，可根本没有这个变量。两处都不会崩，只会让那条配方、那条规则永远不生效。

[`demo/coverage/tiny_sim.py`](demo/coverage/tiny_sim.py) 是一个玩具模拟，跑完自报「480 回合，0 次崩溃」。`action_coverage` 的结论是：一个行动一做就出错（85 次全错，只是被吞掉了），一个从没出现在选项里，两个出现了但从来做不了，还有一个「贿赂」明明在选项里从没可做过，却被执行了 33 次：执行命令时根本没查门槛。

---

## 清单

### 一、让这一整类失败大声报出来

发现一个静默失效，修掉它之后，再加一道检查，把**这一类**的失败全拦住。

- [ ] 数据里用到的每个枚举值，代码都认识；不认识，服务器就拒绝启动。→ `refcheck`：`{"column": "cards.kind", "in": "CardKind"}`，`CardKind` 直接从你的源代码里读。
- [ ] 规则里写到的每个变量，都能对上真东西；对不上，服务器就拒绝启动。→ `refcheck`：用 `"extract"` 从规则文本里抽出 `$变量名`。
- [ ] 每条配方要的主牌类型，至少有一张牌能匹配。→ `refcheck`：`{"column": "recipes.main_card", "in": "cards.kind"}`。
- [ ] 表里该出现在世界里的东西（NPC、组织、职位），开局真的生成了。→ `refcheck`：`{"column": "spawns.npc", "covers": "npcs.id"}`。
- [ ] 规则在执行命令时也要查，不能只在生成选项时查一次。→ `action_coverage` 会揪出「选项里从没可做过、却被执行了」的行动。

### 二、证明每个测试真的会红

- [ ] 每个修复配一个测试。
- [ ] 把修复撤掉，看着测试变红。
- [ ] 再放回去，看着它变绿。

→ `prove_test_fails` 三步一次做完，做完一定把你的文件放回原样。

从来没红过的测试，什么也没证明过。

### 三、别信「零报错」

要问的是：我设计的那件事，真的发生了吗？把每一个没用上的行动分进四个桶：

| 桶 | 意思 | 怎么办 |
|---|---|---|
| 1. 从没出现在选项里 | 没人拿到过能驱动它的牌 | 牌流问题，多半是设计漏洞 |
| 2. 出现了，但做不了 | 牌有了，门槛从没过 | 查门槛为什么过不去 |
| 3. 能做，没人选 | 做得了，只是没人挑 | 没关系，那是策略 |
| 4. 一做就出错 | 有人做了，结算时出错 | 必须修 |

- [ ] 统计走玩家真正看见的那份选项，不要另写一套规则来算。→ 在生成选项的地方记日志（见下文）。
- [ ] 报错和失败分开报：判定没过是规则，报错是漏洞。→ `"outcome": "failure"` 和 `"error"` 分开。
- [ ] 有报错就让工具失败退出，不要只在报告里印一行。→ 只要有一个行动进了第 4 桶，`action_coverage` 就退出码 1。
- [ ] 诊断工具的数字，先确认它认得全部来路再信。工具自己的盲区会造出假的头号漏洞。→ 日志里出现了行动清单里没有的行动，会单独列出并判失败；`refcheck` 里一条检查一个值都没看到，也判失败。

### 四、别在测试里写死精确的数

- [ ] 把「必须正好 14 组」改成「代码要用的那几组都在，而且不是空的」。→ `refcheck`：`{"column": "cards.kind", "covers": "CardKind"}`。
- [ ] 用下限挡真正的事故：整张表没读进来，或者只读了一半。→ `refcheck`：`{"rows": "cards", "min": 100}`。

精确的数每次正常改表都会红，红几次之后，大家就学会了直接把数字改大。到那时候，它就只剩噪音了。

---

## 三个工具怎么用

完整参数见[英文说明](README.md)，这里只说要点。

### refcheck.py：数据引用检查

写一个 `spec.json`：要读哪些表（CSV、TSV、JSON；Excel 先导出成 UTF-8 的 CSV），有哪些名字是「真的」（直接列出来、取某一列、或者从源代码的枚举里读），要跑哪些检查。可以照着 [`demo/refcheck/spec.json`](demo/refcheck/spec.json) 改。

- `in`：值必须在某个枚举或某一列里；`covers`：某个枚举或某一列的每个值，都得在这一列出现过；`unique`：不能重复；`required`：不能为空；`{"rows": "表", "min": N}`：至少 N 行。
- 单元格里是 `a;b;c` 这种列表，加 `"split": ";"`；只查规则文本里的变量，加 `"extract": "\\$(\\w+)"`。
- 每条检查可以写 `"why"`，失败时一起打印，看报告的人知道为什么要查这个。
- 列名写错、文件不存在，算 spec 本身出错，退出码 2，绝不悄悄跳过；一条检查一个值都没看到，也判失败（确实该是空的，加 `"allow_empty": true`）。

想让服务器「拒绝启动」，就在启动脚本里先跑它：`python refcheck.py data/spec.json && ./server`。

### action_coverage.py：四个桶

`--actions` 是你设计过的全部行动（带 `id` 列的 CSV，或一行一个 id 的文本）。没有这份清单，就数不出「从没出现过」的行动，因为日志只记得发生过的事。

游戏里加两行日志就够了：生成选项的地方一行，结算的地方一行。

```json
{"type": "menu", "options": [{"action": "run-shop", "possible": false, "reason": "缺一张店铺牌"}, {"action": "odd-jobs", "possible": true}]}
{"type": "resolved", "action": "odd-jobs", "outcome": "success"}
```

`outcome` 填 `success`、`failure`（规则说不行：判定没过、竞价输了）或 `error`（异常、取不到值：漏洞）。日志里其它行、其它字段都会被忽略，写进现有的日志就行。C# 和 Go 的写法见英文说明。

`--strict` 让第 1、2 桶也判失败，`--allow` 列出允许暂时用不上的行动（比如后期内容）。设计稳定之后再打开。

### prove_test_fails.py：证明测试会红

```bash
python prove_test_fails.py -- pytest -q tests/test_shop.py      # 有未提交的改动就查它，没有就查上一个提交
python prove_test_fails.py --commit a1b2c3d -- go test ./rules/...
python prove_test_fails.py --dry-run -- npm test                # 只看哪些文件会被拿掉，不跑
```

看起来像测试的文件（`tests/`、`test_*.py`、`*_test.go`、`*.test.ts`、`ShopTests.cs` 等）留在原处，其余改动在第 2 步被临时拿掉。退出码：0 证明成立；1 没有修复测试也能过，说明它没测到这个修复；2 有修复也不过，或放回后又不过（可能不稳定）；3 用法或 git 出错。如果第 2 步变红只是因为代码编译不过、导入失败，它会提醒你：这是红了，但红的原因不对。

中途按 Ctrl+C 也会把文件放回去；进程被强杀的话，运行 `python prove_test_fails.py --restore`。

## 测试

```bash
python -m unittest discover -s ep01-silent-failure-checklist/tests -v
```

每次推送都会在 Linux 和 Windows、Python 3.9 和 3.13 上跑一遍。

---

*游戏：《缄默都会》，即将登陆 Steam：https://store.steampowered.com/app/5503450/ 。频道：opmas game，一个人，和一群 AI。MIT 许可。*

English: [README.md](README.md)
