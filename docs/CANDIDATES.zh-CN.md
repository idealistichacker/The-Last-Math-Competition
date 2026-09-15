# 候选队列（研究判断，不是官方评分）

基线：上游 `95acb520ec5607c826b8a997b1ef2fc82d6f7c57`。
2026-09-15 已对97个PR的标题、正文和文件路径，以及99个issue/PR的普通评论做排重。
三个ID均未命中；发布前必须重新读取，不宣称其他人没有私下研究。

| ID | 下一步 | 数学价值与审稿风险 |
|---|---|---|
| 00000000116 | 当前端到端校准样板；恒等解+交换1/3的非恒等解 | 结论简单、非新数学；用于验证完整交付能力，不能据此宣称领先贡献者 |
| 00000000118 | 备用：f(x)=x²−2x+2，0→2→2；证明任意正迭代为素数 | 原题未要求互异；必须解释 f(0)/f¹(0) 重复以及 M=0；先确认按迭代理解，不以乘法幂偷换 |
| 00000000154 | 优先研究更实质的候选：错排数为素数当且仅当 n=3 | 算术递推很简单，但必须形式化递推数列与实际无不动点排列计数的桥梁；桥梁未实现前不得发布“完整Lean证明” |

## 给下一轮 Agent 的具体任务

### Statement Auditor
读取题面双语文本并保存源blob/hash；展开自然数/正整数约定、素数、双射、绝对差、
迭代/多项式幂、错排数的定义；列出“原文允许但容易误解”的情形。
任何对齐缺口优先于编译进度，不把原题弱化到容易证明的命题。

### Formalizer（118）
Int上的二次多项式系数1,-2,2；最高次系数非零；递归迭代；归纳证明所有 k+1 次
迭代为2；推得任意M条件。明确0次迭代不是首项。允许有限Python测试做回归，不能
用有限样本作为无限命题证明。此候选难度/重要性低，不优先刷多个类似简单题PR。

### Formalizer（154）
优先调查现有Lean/Mathlib derangements API，并读取官方源定义。可以采用现成的计数
定理，但必须固定依赖提交并打印公理闭包。若没有现成桥梁，形式化按1的像j分拆
二循环/非二循环的组合双射。仅有递推定义D并证明非素数，计为部分形式化，不发布。

### Independent Reviewer
从原题独立推导，不复述作者答案；检查 0,1,2,3 边界、无限量词、计数对象、负面测试。
出具明确 pass/revise，保存准确文件hash。PDF逐页看图，LaTeX/PDF/Lean结论一致。

### Coordinator
优先维护现有PR；在WIP=1上限内排队。首次样板后转向有意义的证明/计数引理、
对其他投稿的实质审查和生成质量反馈，不批量提交平凡答案或自行设定排行榜。

## 2026-09-15 补充：#154 不必从零实现计数桥梁

已实际查阅 Mathlib 官方生成文档及其链接到的固定源提交
`29ea5de9cb981cb62dfa7979aaff0851f50c603a`，文件
`Mathlib/Combinatorics/Derangements/Finite.lean`。

已存在的API：
- `numDerangements_zero` / `numDerangements_one`：初值1、0。
- `numDerangements_add_two`：二阶乘积递推。
- `card_derangements_fin_eq_numDerangements`：`Fin n`上实际无不动点排列数等于递推数列。
- `card_derangements_eq_numDerangements`：一般有限类型的计数连接。

因此下一位Formalizer可以：选择与其Lean兼容的固定Mathlib提交并复核这些声明，
证明 `Nat.Prime (numDerangements n) ↔ n = 3`，再用已证明的cardinality桥梁转成
`Fintype.card (derangements (Fin n))`版本，最后推出偶数指标解集为空而非无穷。
这只是经源码支持的实现路线，**尚未安装对应Mathlib或编译#154**，不计为已完成证明。

来源（文档会更新，以固定源码版本及实际构建为准）：
- https://leanprover-community.github.io/mathlib4_docs/Mathlib/Combinatorics/Derangements/Finite.html
- https://github.com/leanprover-community/mathlib4/blob/29ea5de9cb981cb62dfa7979aaff0851f50c603a/Mathlib/Combinatorics/Derangements/Finite.lean

## 2026-09-15 并行原型状态

- `00000000154`、`00000000118`、`00000000405` 已各自有本地独立原型；详见执行状态。它们不是已提交或已接受解答。
- `00000000159` 在本次实时查询中已有上游 PR #13，禁止以“未命中本地候选表”为由重复投稿。
- 发布槽仍由 #101 占用；在它open期间，后续题目只可研究、审稿和准备材料。

### 2026-09-15 实际队列更新

- **#154（P1，发布就绪/等待WIP）**：最终声明桥梁、Mathlib固定依赖、PDF、独立AI审稿和协调器验证已完成；仅因#101未关闭而不发布。
- **#118（P2）**：独立语义/Lean审稿通过，但构造非常直接；不应靠批量简单投稿替代更有价值贡献。
- **#405（条件P1）**：ordinary-Kostka标准读法的固定反例已补齐实际基数桥梁，并通过修复后独立审稿；必须保持“非唯一题面解释”的限制，后续才可制作正式包。

### 2026-09-15 探索筛选结果

- `#477`：明确 adjacent-toggle convention 下的反例数学正确，但题面promotion未定义且Lean硬编码orbit/card，**REVISE，不包装**。
- `#2617`：固定两点链的标准incidence algebra纸面反例强，但现有Lean缺标准`IncidenceAlgebra`/`Ideal.jacobson`桥，**BLOCKED，不包装**。
- `#5397`：手工反例依赖无理性与环面拓扑，Lean未覆盖，**research only**。
- 审计结果应优先于“找到反例”的数量；目前#154仍是唯一发布就绪的后续候选。
