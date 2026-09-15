# 执行状态：已恢复自动贡献计划

更新时间：2026-09-15 15:54（Asia/Shanghai）。

## 当前控制状态

用户已明确要求低成本模型接管并开始执行。因此：
- 历史暂停指令已被本次恢复指令取代；`tlmc` heartbeat 将按本计划恢复。
- 所有新外部写入仍需经过版本、排重、独立审稿、真实构建与权限门槛。
- 当前上游解答PR WIP 上限为 1；维护 PR #101 优先于新投稿。

## 已交付

1. `CONTRIBUTOR_AGENT_PLAN.zh-CN.md`：完整30天计划、角色交接、质量gate、预算与权限边界。
2. `AGENTS.md`：多Agent工作契约。
3. `scripts/contributor.py`：防重复、版本/评审检查、真实编译及非交互发布协调器。
4. `docs/AUTOMATION.md`：实际能力与未实现项；`docs/CANDIDATES.zh-CN.md`：后续候选。
5. `docs/HANDOFF.zh-CN.md`：历史停机和精确恢复入口。

## 已发生的外部操作

- 上游 Issue #100 已创建，澄清署名、AI披露、首个有效解答时间；最后读取状态 open、0 条评论。
- fork PR #1 已合并，merge SHA `85c7611a1595bd5712a09dfaf1a29015d28542ff`。这是 fork 工具集成，不是数学采纳。
- **上游 PR #101 已创建：** `Prove conjecture 00000000116: identity and an explicit nonidentity involution`，head `86c597834807a0f9d6a64d10e0b38168ed2b4c99`，当前 open、未合并。
- #101 在创建前执行了即时深度排重，未发现同 ID 公开投稿；发布器再次刷新后才开PR。

## #116 的真实验证证据

- 原始题面、blob和审稿hash在发布前均匹配上游 `95acb520ec5607c826b8a997b1ef2fc82d6f7c57`。
- Python复现、Lean 4.33.1 build、直接源码重放和17个公开定理的空公理依赖审计通过。
- Tectonic 0.15.0 + `SOURCE_DATE_EPOCH=0` 重建的PDF与提交PDF字节一致。
- 独立AI审稿Gauss通过，制品内容hash：`6c836e2e6c1d85aca1d6679829efccc18c114658af14f624510f6049306e7b17`。
- 这是一个明确标注为初级的校准样板；不声称数学新颖性、组织者采纳或获奖。

## 限制与下一步

- 当前账号对上游没有写入/合并权限；PR #101 只能等待维护者审查。
- PAT 仍缺workflow scope，GitHub Actions/Linus CI均未运行；工作流仅有文档模板。
- 工具测试104个：101通过、3个Windows symlink权限跳过。
- 持续流程应先跟进 #101/#100；研究 #154 的错排计数桥梁可并行进行，但 WIP 内不提交第二个上游解答PR。

## 并行研究线（2026-09-15）

以下内容均为本地原型，尚未开第二个上游解答PR：

| ID | 真实进展 | 发布状态与边界 |
|---|---|---|
| `00000000154` | Mathlib `v4.33.1` 源码构建后，定理 `TLMC154.fin_even_derangements_card_not_prime` 证明 `∀ k, ¬ Prime(card(derangements(Fin(2k))))`；协调者已复跑构建和公理审计。 | 与实际错排排列计数存在正式桥梁；仍缺独立审稿、LaTeX/PDF、正式submission包，且 #101 占用WIP。 |
| `00000000118` | 固定二次 `x²-2x+2` 的 `f(0)=f(2)=2` 形式化，协调者已复跑 Lean build/audit。 | 原题不要求迭代值互异；但仍缺独立审稿、LaTeX/PDF和正式提交包。 |
| `00000000405` | 对普通 Kostka 数标准读法，`n=3, λ=(2,1)` 的两个表给出 `4∤6`；协调者已复跑 Python、Lean、审计。 | 题面“spin-pairing”及量词范围有语义歧义，尚不能说解决组织者意图；必须先完成 statement-alignment 审稿。 |

- `00000000159` 已有上游 PR #13，因此未重复分配。
- 对上述任何题发布前必须重新深度排重和重核上游基线；历史快照不替代发布时核查。
- 发布协调器现接受 `lean4/lakefile.toml` **或** `lean4/lakefile.lean`，以支持有固定 Mathlib 依赖的合规Lean项目；测试覆盖此分支。
