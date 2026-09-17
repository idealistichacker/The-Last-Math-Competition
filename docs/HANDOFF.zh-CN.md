# 低成本模型接手说明（先读本文件）

**本文件保留 2026-09-15 的历史交接证据。自 2026-09-17 起，以下“当前续作覆盖”与 `docs/EXECUTION_STATUS.md`、`docs/AUTOMATION.md` 优先于全部历史命令和状态。**

## 当前续作覆盖（2026-09-17；先执行本节）

用户之后要求暂停 `tlmc` heartbeat：实际本地自动化存储中没有 `tlmc/automation.toml`，未创建替代调度任务，**不得宣称监控正在运行或自行恢复 heartbeat**。

截至 `2026-09-17T07:48:51.026927+00:00` 的只读 GitHub API 深度刷新：上游 PR #101 为 open、未合并，head `86c597834807a0f9d6a64d10e0b38168ed2b4c99`；PR #102 为 open、未合并，head `3fe264456cb6b639dea17d6fe4f64297f966e53b`；`00000000118` 在快照中没有匹配。用户已明确允许在不违反当前上游规则的前提下并行多PR：默认仍为1，超过1须显式传正整数 `--max-open-solution-prs` 并让每条独立完成排重、题面、独立审稿、Lean、PDF和复现门槛。仍禁止重复 Issue、催审、force push或重复推送 #102。

#2617 已完成不可变包、PDF、独立审稿和完整协调器验证，归档提交 `b6d111966715abe2e4d4af8998453bb2fa948d2d` 已推送至用户 fork 的 `solution/00000002617`；它只建立固定 `ℚ` 系数域的标准 incidence algebra 反例，不泛称所有系数环、半单性或 Möbius 结论。#118 已完成经独立终审和完整验证的本地包，fork commit `526ed3cd` 已回读一致。用户现允许符合当前上游规则的显式并行多PR，但任何 PR仍逐条满足排重、题面对齐、Lean、PDF、复现与独立审稿门槛。#405 因题面术语/量词不明确和审稿证据链冲突降为高风险 research-only；#5397 仅在未固定的离散时间解释下有条件性反例，维持 P3/research-only。

协调器根分支为 `contribution-ops-network-recovery`。写入本交接覆盖前的最后实现提交为 `c25c6b4a3d9ff85a716767da1b5491bca3ffa533`，其中包含精确依赖复现、传递 `--repo`、120 秒非 force solution-push 熔断以及状态修正；本交接覆盖自身是其后的本地提交。根分支曾有一次普通 fork push 卡住，已终止并由 `git ls-remote` 对账确认**没有远端分支被写入**；当前禁止自动重试任何 push。后续若用户明确恢复外部写入，必须先重新核验 transport、fork ref、最新上游状态和排重，且只做一次非 force 操作。

运行本地校验时，最新工具测试为 `115` 项，其中 `112` 通过、`3` 项因 Windows symlink 权限跳过。阅读顺序固定为：本节 → `AGENTS.md` → `docs/EXECUTION_STATUS.md` → `docs/AUTOMATION.md`；下面所有 2026-09-15 段落均为历史审计材料，不能直接执行。

## 节省上下文的阅读顺序

1. 本文件（状态、下一步、禁止重复动作）。
2. `D:\AStudy\开源杂\LastMathC\AGENTS.md`（硬约束）。
3. `D:\AStudy\开源杂\LastMathC\docs\AUTOMATION.md`（实际命令与能力边界）。
4. 按当前任务选择性阅读 `CONTRIBUTOR_AGENT_PLAN.zh-CN.md` 对应章节，不必每轮重读846行。
5. 新选题才读 `docs\CANDIDATES.zh-CN.md`；状态汇总在 `docs\EXECUTION_STATUS.md`。

## 2026-09-15 历史远端操作快照（已被当前续作覆盖）

| 对象 | 最后实测状态 |
|---|---|
| 上游普通Issue #100 | 已创建，标题 `Clarify attribution, AI disclosure, and first-solution timestamps`；最后查询open、0评论 |
| 用户fork PR #1 | 已merge；merge commit `85c7611a1595bd5712a09dfaf1a29015d28542ff` |
| fork工具分支 | `contribution-ops` 已push，头提交 `81964f9032f584ab92a44a4c6933c32e7b898e08` |
| 上游数学解答PR | **本账号本轮尚未创建**，不要把fork PR #1误报成数学贡献被上游接受 |
| 定时执行 | automation `tlmc` 已暂停，不会按原6小时周期继续执行 |

fork PR #1集成的是计划/工具，不是数学成果。上游没有公开确认“最佳贡献者”标准；
Issue #100询问署名与记录口径，不要求奖项或催审。

## 现有代码、权限与测试

- 仓库原始猜想10000个，研究基线 `95acb520ec5607c826b8a997b1ef2fc82d6f7c57`。
- `origin` = idealistichacker/The-Last-Math-Competition；`upstream` = 官方同名仓库。
- 非交互Git Credential Manager身份已验证为idealistichacker；fork admin/push=true，上游push/admin=false。
- 凭据缺少 `workflow` scope，GitHub曾明确拒绝工作流push。没有扩大scope或绕过。
- `.github/workflows` **没有部署**。YAML只在 `docs/workflow-templates/contributor-tooling.yml` 作非执行模板。
- 含工作流的原提交 `37b44c5f` 保留在本地 `contribution-ops-workflow-pending`，没有push成功。
- 实跑104个本机工具测试：101通过、3个symlink测试因Windows权限跳过。Linux和托管CI未运行。
- fork上成功状态名为 `local/windows-tooling-verification`，真实绑定81964f90，不冒充托管CI。
- 这些工具单测大量使用mock，不能拿它们证明数学；下述Lean/PDF另有真实运行证据。
- 凭据不要输出/落盘；Git helper-selector曾等待UI，工具使用单命令manager覆盖，不改全局配置。

## 已准备但未提交的 #116 数学样板

工作树：
`D:\AStudy\开源杂\LastMathC\.local\worktrees\00000000116`

分支：`solution/00000000116`，从upstream/main建立。

提交目录：
`solutions/00000000116/idealistichacker_submission_20260915065911`

包含README、main.tex、真实2页main.pdf、reproduce.py、submission.json、review.json及Lean4项目。
证明原题，并给交换1和3的非恒等双射；这是简单校准题，不声称新数学。

已实测：
- Lean 4.33.1 build、直接源码重放、17个公开定理的依赖审计全部通过且公理列表为空。
- Python完整复现通过；有限枚举只计回归，无限命题由Lean证明。
- Tectonic 0.15.0、`SOURCE_DATE_EPOCH=0`两次实际编译PDF字节一致。
- 两页PNG由协调者及独立Agent审阅；溢出版式已修复。
- 独立审稿Gauss真实写入review.json，五项检查通过。
- 停止前最后检查review hash匹配：
  `6c836e2e6c1d85aca1d6679829efccc18c114658af14f624510f6049306e7b17`。
- **完整发布协调器validate/publish尚未在最终评审之后执行；解答目录仍untracked，未commit/push。**

工具路径：
- Lean/Lake：`D:\AStudy\开源杂\LastMathC\.local\tools\lean-4.33.1-windows\bin\lake.exe`
- TeX：`D:\AStudy\开源杂\LastMathC\.local\tools\tectonic.exe`
- Lean官方zip SHA已和发布者digest一致；旧Tectonic发布无publisher digest，仅记录本地hash。
- 所有工具/工作树在忽略的.local内，尚未重置/清理；不要删掉后声称交接没有成果。

## 2026-09-15 历史命令范例（不得按当前状态执行）

先检查Git状态、源文件、最新权限和重复投稿，不必重新克隆或重装已有工具：

```powershell
$root = 'D:\AStudy\开源杂\LastMathC'
$wt = "$root\.local\worktrees\00000000116"
$s = 'solutions/00000000116/idealistichacker_submission_20260915065911'
$lake = "$root\.local\tools\lean-4.33.1-windows\bin\lake.exe"
$tex = "$root\.local\tools\tectonic.exe"
python "$root\scripts\contributor.py" doctor
python "$root\scripts\contributor.py" refresh --deep
python "$root\scripts\contributor.py" --repo $wt validate $s --lake $lake --tectonic $tex
# 上述全部通过、复核无重复且用户已恢复执行时，再调用：
python "$root\scripts\contributor.py" --repo $wt publish $s --lake $lake --tectonic $tex --execute
```

发布工具会再查重、只提交该题目录、正常push并开上游PR。不要手动改hash绕过失败。
不要把上游无merge权限当成需要破解的错误；维护者完成review后才可能merge。
如需恢复定时器，必须确认当前任务已使用用户选择的执行模型，并经用户明确恢复执行；
不要在此交接阶段恢复。

## 后续高价值工作

#118只是另一个低难度备用，不建议刷相同类型简单题。#154的更实质路线已更新：
Mathlib已有 `card_derangements_fin_eq_numDerangements` 等计数桥梁，可复用，不必重写。
具体固定源提交、声明名与未验证边界见候选文档。必须选择兼容版本并实际编译，
不要把已有递推引理误报为已完成该题。

## 2026-09-15 历史未提交交接改动（已过期）

本次最后只更新计划/交接文档，没有再commit/push：
- docs/CANDIDATES.zh-CN.md（补充Mathlib路线）；
- docs/EXECUTION_STATUS.md（最终停机状态）；
- docs/HANDOFF.zh-CN.md（本文件）；
- AGENTS.md和总计划开头（添加本次用户要求的暂停入口）。

请保留这些改动，以及样板工作树和本地拒绝工作流分支。不要reset --hard、force-push、
重发Issue #100或重做fork PR #1。根目录出现过 `%SystemDrive%/` 缓存，来源未确认，
已仅作本地忽略处理，未删除也未提交。
