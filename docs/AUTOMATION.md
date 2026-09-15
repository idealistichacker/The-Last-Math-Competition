# 运行手册：真实能力与设计边界

本手册适用于 idealistichacker 的 fork；不代表上游维护者政策。总计划见
`CONTRIBUTOR_AGENT_PLAN.zh-CN.md`，所有 Agent 首先遵守 `AGENTS.md`。

## 已实现的命令

在 `D:\AStudy\开源杂\LastMathC` 运行，Python 3.11+，只用标准库：

```powershell
python scripts/contributor.py doctor
python scripts/contributor.py refresh --deep
python -m unittest discover -s tests -v
python scripts/contributor.py --help
```

- `doctor`：非交互读取现有 Git Credential Manager 凭据（或进程级 GH_TOKEN / GITHUB_TOKEN），
  验证账号必须是 idealistichacker，以及 fork/upstream 权限；仅保存脱敏报告。
- `refresh`：分页读取全部状态的 PR/Issue；`--deep` 还收集 PR 文件路径和普通评论。
  文件清单按 head SHA 缓存；3000 文件 API 上限导致不完整时阻止发布。
  **不是全文数学相似度搜索，也不保证发现从未公开的研究。** inline review、外部论文和
  不带题号的相关工作仍要由 Scout 检查；不能把未命中当作原创证明。
- `hash`：计算被审材料的内容 SHA-256；排除构建缓存和顶层评审记录自身；文本CRLF统一为LF，PDF/二进制按原始字节，支持Windows/Linux复现。
- `validate`：检查完整材料、题面版本、独立评审版本；真正运行 Python、Lean、axiom audit、
  Tectonic 重编译，并比较 PDF 字节。`--static-only` 仅做静态预检，**不够发表**。
- `publish ... --execute`：有共享 Git-worktree 发布锁、身份检查、最新排重、WIP=1、
  单题目录 diff 白名单和完整验证后，自动 commit、非 force push、创建上游 PR。
  遇到自己已创建且有稳定 marker 的 PR，返回已有链接，不再建第二个。
- `issue draft.json --execute`：仅发布经过协调者审查的实质性问题；稳定 marker 防重；
  7 天内最多 1 条普通 Issue；不替每个解答再开重复 Issue。
- `status N`：读取 PR 的实际 merged 状态、reviews、普通/行内评论和 check runs。
  **不会代维护者批准或 merge 上游。**

## 第一份解答工作区

```powershell
$root = 'D:\AStudy\开源杂\LastMathC'
$wt = "$root\.local\worktrees\00000000116"
$submission = 'solutions/00000000116/idealistichacker_submission_20260915065911'
$lake = "$root\.local\tools\lean-4.33.1-windows\bin\lake.exe"
$tex = "$root\.local\tools\tectonic.exe"
python "$root\scripts\contributor.py" --repo $wt validate $submission --lake $lake --tectonic $tex
# 只有发布协调者调用；没有 --execute 不产生远端写入。
python "$root\scripts\contributor.py" --repo $wt publish $submission --lake $lake --tectonic $tex --execute
```

工具为当前任务下载到忽略目录，未修改系统 PATH。Lean 4.33.1 来自官方 release，
zip 的 SHA-256 与发布者 digest 校验；Tectonic 0.15.0 来自官方 release，
该旧发布没有 publisher digest，只记录本地哈希，不伪称供应商签名验证。
本地 `.local/tools/*.provenance.json` 记录来源。不得把 zip、工具、凭据和机器缓存提交。

## 制品契约

每个提交必须含：

```text
solutions/<11-digit-id>/idealistichacker_submission_<UTC yyyymmddHHMMSS>/
  README.md
  main.tex
  main.pdf                   # 真正由 main.tex 编译，不是伪装后缀
  reproduce.py               # 有界检查不冒充无限定理
  submission.json            # source hash/blob、定理名、形式化范围和局限
  review.json                # 真实独立Agent，明确statement/Lean bridge/PDF检查
  lean4/lean-toolchain        # 精确版本
  lean4/lakefile.toml
  lean4/Main.lean
  lean4/Check.lean            # 每个 advertised theorem 的 #print axioms
```

`review.json` 是可审计记录，不是密码学签名或“数学正确性检测器”。主进程不得
把没有发生过的评审填成通过。内容变更后 hash 失效，必须重新独立审查。

## 自动化边界（不能模糊）

1. Python 是发布/验证协调器，不是自动解数学题的模型服务。持续研究由本任务的 Agent 执行。
2. 脚本只执行本任务写出的、已经审查的文件；本机裸跑不是隔离沙箱。
   不能下载随机 PR 后直接 `lake build`/执行 Python；尤其不得带凭据运行第三方构建。
3. 当前只实现允许小型 core Lean 提交的保守 token gate；它不是通用 Lean parser。
   故意用语法扩展隐藏公理的攻击、Mathlib 依赖审计、恶意 TeX/Python 沙箱不在已实现范围。
4. `publish` 对已有 PR 仅幂等返回；修订由协调者在原分支完成，经重审、validate 后
   普通 commit/push 更新。不会自动把未审查差异 push 上去。
5. 当前账户没有上游写权限。因此上游 merge 状态是等待维护者，不是待破解的错误。
   不启用 merge bypass、不调用 admin merge、不伪造审批。
6. fork 工具 CI 只验证工具测试和 diff；不代表上游数学审查。上游没有 CI 也不能写“CI passed”。
7. 默认不产生额外付费 API、云机器或付费 CI 费用；免费额度/权限变化时停止相关执行。
8. 若配置 Codex heartbeat，它依赖本机 Codex 调度实际运行，不是安装到服务器的 24/7 服务。
   自动化 ID、有效期及最后证据见 `docs/EXECUTION_STATUS.md`；未记录不能宣称已部署。

## 恢复和故障处理

- Git helper-selector 在非交互 Python 中可能等待 UI。本工具对单次命令明确指定
  `credential.helper=manager`，不更改全局配置，不弹登录窗口。
- 网络 GET 失败可以在下轮重新读取；POST 超时先按 marker 查询远端真实结果，不能盲重发。
- `.git/tlmc-publish.lock` 存在：先读取 PID，再确认该 PID/命令/开始时间是否本任务进程。
  活进程不能删锁；确认进程终止才可删除这一个锁文件。锁不是进程仍运行的证据。
- `source hash`、review hash、PDF hash 改变：重新审核，不手改期望值绕过失败。
- 凭据缺失/失效或 SSO：不得索取明文 token，暂停外部写入，保留离线成果。
- 不改 `metadata.csv`，不把自记“首次提交时间”伪称组织者“首次成功解决时间”。
- 已发布错误：先停止新发布，复核后在原 PR 提交修复或明确撤回；上游已合并时发 correction/revert PR。
- 不为回滚执行 `reset --hard`、force-push 或删除用户学习数据；保留证据和历史。

## 为后续 Agent 提供的实际下一步

先读 `docs/EXECUTION_STATUS.md`，刷新真实 PR/Issue 状态，不按旧报告重复发表。
优先修订既有贡献。候选 #118（素数不动点）和 #154（错排数素数分类）只是
经初步数学审计的备选，不是已完成/已验证解答；#154 的排列计数与递推连接必须形式化。
30天路线图是计划，不得把未来工作写成当前测试覆盖。
