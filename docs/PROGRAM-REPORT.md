# 项目群总报告：中文 LLM 评测基准群

日期：2026-07-18 · 作者：zhujiehan（GitHub: [uninhibited-scholar](https://github.com/uninhibited-scholar)）· 构建协作：Claude Code
本报告自包含，覆盖 6 个公开仓库。所有数字均可在对应仓库零依赖复现（评分不需 API key）。

---

## 0. 一句话

围绕「中文 AI 生态的能力盲区」，构建了一组**小规模、公开标签、确定性可复现、纯机器评分**的中文评测基准，用真实模型（云端前沿 + 本地 0.5b–4b）跑出排行榜，并沉淀出一套「评测工程方法论」。所有结论均为**基准内结论**，不外推模型一般能力或真实部署表现。

## 1. 六个仓库全景

| 仓库 | 维度 | 版本 | 规模 | 一句话结论 |
|---|---|---|---|---|
| [fraud-detect-bench-zh](https://github.com/uninhibited-scholar/fraud-detect-bench-zh) | 中文诈骗识别 | v3 | 144 条(98诈骗/46正规) | verdict 已饱和，差异在类别归因；换载体(口语/二维码/AI话术)也不破 |
| [agent-endurance-bench](https://github.com/uninhibited-scholar/agent-endurance-bench) | 长任务状态追踪 | v3 | 18 ep / 3000 步 / 330 探针 | glm「记得规则、算错账」500 步崩到 5/39；deepseek 三版本连续满分 |
| [memory-consistency-bench-zh](https://github.com/uninhibited-scholar/memory-consistency-bench-zh) | 多轮记忆一致性 | v0 | 9 对话 / 65 探针 | 改口更新都不留旧值；差异在 absent 幻觉(glm 4/21、deepseek 0) |
| [elderly-accessibility-bench-zh](https://github.com/uninhibited-scholar/elderly-accessibility-bench-zh) | 老年数字无障碍 | v2 | 52 选择 + 24 槽位 | 强模型对老年中文噪声近饱和；真瓶颈是评分 harness 公平性 |
| [bench-contam-scan](https://github.com/uninhibited-scholar/bench-contam-scan) | 污染/完整性扫描工具 | v0 | — | dup/near-dup/gold-leak/cross-overlap + PROFILE 指纹 |
| [cn-llm-arena-zh](https://github.com/uninhibited-scholar/cn-llm-arena-zh) | 聚合门户 | — | 8 模型 | 8 模型密梯度榜；ATT&CK 是前沿 vs 本地的分水岭 |

另与作者早期两个基准 [agent-safety-bench-zh](https://github.com/uninhibited-scholar/agent-safety-bench-zh)、[defensive-refusal-bench-zh](https://github.com/uninhibited-scholar/defensive-refusal-bench-zh) 构成安全×能力矩阵，已一并接入 arena。

## 2. 聚合榜（8 模型，2026-07-18 实跑）

| 模型 | 来源 | ATT&CK F1 | 函调完整率 | 安全拦截F1 | 注入召回 | 诈骗gap | 无障碍gap↓ |
|---|---|---:|---:|---:|---:|---:|---:|
| deepseek-v4-flash | 云 | **0.436** | 0.64 | 0.957 | 0.889 | 0.935 | 0.0 |
| glm-5.2 | 云 | 0.314 | 0.67 | 0.96 | 0.889 | 1.0 | 0.0 |
| gemma3-4b | 本地 | 0.022 | 0.503 | 0.828 | 0.569 | 0.371 | 0.0 |
| llama3.2-3b | 本地 | 0.003 | 0.357 | 0.89 | 0.837 | 0.588 | 0.143 |
| phi4-mini-3.8b | 本地 | 0.0 | 0.337 | 0.891 | 0.784 | 0.26 | 0.024 |
| qwen2.5-1.5b | 本地 | 0.001 | 0.333 | 0.78 | 0.556 | 0.0 | 0.024 |
| llama3.2-1b | 本地 | 0.006 | 0.357 | 0.259 | 0.085 | 0.079 | 0.086 |
| qwen2.5-0.5b | 本地 | 0.008 | 0.357 | 0.103 | 0.007 | 0.0 | 0.148 |

**三条能力分界**：(1) ATT&CK 技术映射是前沿 vs 本地的分水岭——两云 0.31–0.44，所有本地 ≤4b 全崩到 ≤0.022；(2) 安全能力随模型缩小陡降——4b 档注入召回 0.78–0.89，1b/0.5b 崩到 0.007–0.085（越小越危险）；(3) 诈骗识别 4b 及格边缘、≤1.5b 归零。

## 3. 每个基准的核心发现

**fraud-detect-bench-zh（v3, 144 条）**：语义判别 vs 关键词见词报警差 12 倍以上（gap ~0.97 vs 0.075）。两个前沿模型 verdict 全打满（98/98），差异只在类别归因（glm 85/98 领先 deepseek 76/98）；混合话术里出现「银保监会/禁毒大队」等机关字样会把贷款/物流骗局带偏归为冒充公检法，且 deepseek 会把真实机关通知误报——机关字样是双向陷阱。v3 新增口语转写/二维码/AI 话术三种载体，verdict 仍 98/98，**证伪「依赖短信表面格式」假设**：强模型判的是行为结构。

**agent-endurance-bench（v3, 330 探针）**：glm-5.2 退化形态锁定为「记得规则、算错账，账越长错得越多」——规则记忆/抗干扰保持好，但累计预算的算术状态在 500 步崩到 5/39(13%)。deepseek-v4-flash 连 v3（内嵌干扰+cross 多约束+500 步算术）也 330/330 全对，三版本连续满分——本构造无法证伪其状态保持，只能给下界；v4 需质变而非量变。

**memory-consistency-bench-zh（v0, 65 探针）**：改口更新两模型都几乎不留旧值（staleness 0），「最新覆盖旧值」强模型做得好；差异在 absent 幻觉——glm 对 4/21 从未提及属性编造具体值，deepseek 零幻觉。记忆的难点不在「覆盖」而在「承认不知道」。

**elderly-accessibility-bench-zh（v2）**：选择题（v0/v1，含误导埋点）强模型 52/52 全对；开放式槽位抽取（v2）公平评分后 joint 0.917，残余 2 个是缺单位/gold 歧义。**核心是方法论发现**：对强模型，评测瓶颈是评分 harness 的公平性——本项目连踩措辞、中↔阿拉伯数字、「十六→106」bug、同义词共 4 处评分死板，每处都曾让强模型假性出错。真正的能力缺口在弱模型（qwen0.5b 0.583）。

**bench-contam-scan（v0）**：把前几个基准里现成的基础设施（重复检测、manifest 哈希）抽象成通用工具。scan.py 四检查（精确/近重复、gold 泄漏、跨语料 8-gram 重叠），fingerprint.py 出 PROFILE 指纹。诚实边界：发现是人工复核信号，非训练污染证明（离线无法证实）。dogfood 自扫两基准：fraud 全干净、endurance 如实报出 13 条模板 near-dup。

## 4. 方法论（本项目群最可复用的资产）

1. **零依赖 + 确定性**：纯 Python 标准库；种子化生成器，CI 跑「重跑生成器 + `git diff --exit-code`」确定性锁。
2. **确定性、公开且可重算 gold**：随仓库分发，非隐藏测试集，不抗训练污染——榜单为基准内结论（此措辞经外部审查更正）。
3. **改动可见性锁**：fraud 用 MANIFEST.sha256（精确 ID 集+逐条哈希，负向测试删样本即 FAIL）；endurance/memory/elderly 用 CI 确定性锁。防的是「悄悄改数据」，不是防蓄意作弊。
4. **纯机器评分，无 LLM 裁判**：封闭 gold（字母/数字/程序化断言）。
5. **统计克制**：榜单附原始计数 + Wilson 95% CI，明标不显著差距。
6. **评分器也会错**：本项目群累计发现 ≥4 处评分器死板（endurance norm、elderly 4 处），每处都曾让强模型假性「错一片」。**教训：永远人工抽查失败样例；对强模型，评分 harness 公平性往往比任务本身更是瓶颈。**
7. **饱和是信号不是失败**：模型打满 → 下一版扩难方向就有了；加入本地小模型是拉开区分度的有效手段（零 API 成本）。

## 5. 外部审查（诚实治理）

一次独立审查复现了全部主榜数字，指出三处夸大（"封闭 gold" 实为公开、"CI 防作弊" 当时未真落地、统计表述过强）。全部整改后复审通过。整改包括：措辞更正、manifest/确定性锁真正写入 CI 并步骤级验证、榜单改计数+Wilson CI、endurance 定位更名。**这个来回本身就是方法论的一部分——小基准的可信度不来自规模，来自可核查性。**

## 6. 诚实边界（全群通用）

- 小样本，置信区间宽；结论为基准内结论，不外推。
- 云端仅测 2 个前沿模型（glm-5.2、deepseek-v4-flash，同一 Ark 端点）；本地 6 个 0.5b–4b 模型（Ollama）。
- 合成/人工构造数据，非真实用户语料；elderly 噪声为人工模拟老年表达，非真实语音转写。
- 单人构建，无第二标注者、无标注一致性检验。

## 7. 复现
```bash
# 任一基准（评分无需 API key）
git clone https://github.com/uninhibited-scholar/<repo> && cd <repo>
python3 scripts/check_bench.py            # 校验 + 确定性锁
python3 scripts/score.py predictions_*.jsonl
# 跑新模型：默认本地 Ollama（ollama serve），云端用 OPENAI_BASE_URL + OPENAI_API_KEY
# 聚合榜：cn-llm-arena-zh 里 ARENA_WORKERS=4 python3 run_eval.py models.json
```

## 8. 待办
- endurance v4：探针依赖多步推理链 / 需模型主动发现矛盾（deepseek 对量变已饱和）。
- elderly v3：真实老年语音转写语料（伦理/版权）、槽位定义消歧。
- fraud/memory：更多模型上榜；memory 加矛盾陈述探针。
- 方法论文章《两个小基准，三个可复现的发现》已在 fraud/endurance 仓库 docs/，可扩写为全群方法论。
- 发布（对外动作，待作者决定渠道）。
