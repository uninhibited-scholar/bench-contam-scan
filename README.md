# bench-contam-scan

JSONL 评测基准的**离线污染 / 完整性扫描器**（零依赖 · 确定性 · CI 友好）。

[![CI](https://github.com/uninhibited-scholar/bench-contam-scan/actions/workflows/scan.yml/badge.svg)](https://github.com/uninhibited-scholar/bench-contam-scan/actions/workflows/scan.yml)
[![License: CC BY 4.0](https://img.shields.io/badge/license-CC%20BY%204.0-green.svg)](https://creativecommons.org/licenses/by/4.0/)

做评测的人都担心两件事：数据里有没有**重复/答案泄漏**（自己挖的坑），以及有没有和某个语料**重叠**（污染风险）。这个工具把这些检查标准化成一条命令。它从 [fraud-detect-bench-zh](https://github.com/uninhibited-scholar/fraud-detect-bench-zh) 与 [agent-endurance-bench](https://github.com/uninhibited-scholar/agent-endurance-bench) 两个基准里已经现成的基础设施（manifest 哈希、重复检测、check 回归）抽象而来。

## 诚实边界（先说）
**发现是"供人工复核的信号"，不是"训练集污染的证明"。** 真正的训练集污染无法离线证实——你没有模型的训练数据。本工具做的是数据卫生（自查重复/泄漏）与跨语料 n-gram 重叠（风险提示）。模型侧记忆启发式见 `scripts/probe_model.py`（路线图）。

## 两个工具

### 1. `scan.py` — 污染/完整性扫描
```bash
python3 scripts/scan.py bench.jsonl --text-field message --gold-field gold \
        [--against other_corpus.jsonl] [--near-threshold 0.8] [--report r.json]
```
四项检查：

| 检查 | 抓什么 | 方法 |
|---|---|---|
| `exact_dup` | 归一化后完全重复的样本 | NFKC + 去空白/标点后精确匹配 |
| `near_dup` | 高度相似样本 | 字符 5-gram Jaccard ≥ 阈值 |
| `gold_leak` | gold 答案字面出现在题面里 | 归一化子串包含 |
| `cross_overlap` | 与外部语料的 8-gram 重叠 | containment ≥ 0.5 |

退出码：0 = 无发现，1 = 有发现（可直接进 CI）。

### 2. `fingerprint.py` — 基准 PROFILE 指纹
```bash
python3 scripts/fingerprint.py bench.jsonl --label-field label --out PROFILE.json          # 生成
python3 scripts/fingerprint.py bench.jsonl --label-field label --out PROFILE.json --verify  # 校验
```
产出全文件 sha256 + 逐条哈希 + ID 集合 + schema + 标签分布。把 PROFILE 与数据一起提交；任何静默改动（删样本/翻 gold/改文案）都会改变指纹并在 git diff 中现形。`--verify` 在 CI 里用：不一致即退出 1，并列出 deleted/added/modified 的 ID。这是 fraud-detect-bench-zh 的 MANIFEST 机制的通用化。

## Dogfood：扫两个真实基准
```
fraud-detect-bench-zh (120 条): exact_dup 0 | near_dup 0 | gold_leak 0 | cross_overlap 0  ✅ 干净
agent-endurance-bench (15 ep):  near_dup 13  ← 真实且预期
```
endurance 的 13 条 near-dup 是**正确的**信号：它的开局约束（`constraints` 字段）是模板化文本，同领域近乎一致。这演示了工具的用途——**它不判断"好坏"，只标出结构相似**，由作者判断是设计使然（模板 system prompt）还是数据缺陷（真重复）。跑 `python3 scripts/scan.py` 得到的报告在 `docs/scan_*.json`。



## 3. `harness_probe.py` — 评分器公平性探针（实验 A）

机器评分被默认"客观"，但**字面匹配的评分器会把正确但表述不同的答案判成错**。本工具完全离线量化这一点：取一批**已知正确**的 gold，程序化生成语义等价变体（加解释/格式包裹/中文↔阿拉伯数字/量词增减/同义词/全半角），用目标评分器判分，统计 false-negative 率。

```bash
python3 scripts/harness_probe.py --demo --compare                 # 内置样例
python3 scripts/harness_probe.py bench.jsonl --gold-field gold --compare
```

### 实测结果（4 个真实基准 + demo）
| 基准 | gold 数 | 严格字面匹配 fnr | FSP 规范化后 fnr |
|---|---:|---:|---:|
| demo（10 条典型 gold） | 10 | **0.735** | 0.0 |
| fraud-detect-bench-zh | 144 | **0.714** | 0.0 |
| agent-endurance-bench（330 探针） | 330 | **0.741** | 0.0 |
| elderly（选择题 52） | 52 | **0.778** | 0.0 |
| elderly（槽位 24） | 24 | **0.733** | 0.0 |

**读法**：朴素字面匹配下，**约 71–78% 的"语义等价的正确答案"会被判错**。失效最重的类型是 `wrapped`（JSON/引号/code fence 包裹，100% 误判）与 `explained`（答对但附一句解释，100% 误判）——**这正是强模型最常见的输出形态**。

**Fair Scoring Protocol（FSP）**：去 code fence → 取首行/JSON 值 → 中文数字规范化 → 去标点空白 → 全角转半角 → 同义归并 → 量词容忍。应用后 fnr 全部归零（在这批变体上）。

> 边界：变体集由本工具定义，是**评分器脆弱性的下界探测**而非穷举；FSP 归零意味着"这 9 类它都能吃下"，不等于对开放式生成也公平。用它做回归测试：改评分器后重跑，fnr 不该上升。



## 4. `harness_penalty.py` — 评分器冤枉了谁（实验 B）

同一批模型的**原始输出**，用严格字面匹配与 FSP 各评一次，`harness_penalty = fsp − strict`。

### 实测（elderly 开放式槽位抽取，24 题 × 3 模型）
| 模型 | strict | FSP | harness_penalty |
|---|---:|---:|---:|
| glm-5.2 | 0.833 | **1.0** | **+0.167** |
| deepseek-v4-flash | 0.833 | 0.958 | **+0.125** |
| qwen2.5-0.5b（本地小模型） | 0.75 | 0.792 | +0.042 |

**H1 得到支持**：两个前沿模型被字面匹配扣掉 0.125–0.167，本地 0.5b 只扣 0.042（约 1/3）。强模型更爱把答案包在 JSON/解释里，因此更受害；小模型答错是真错，换评分器也救不回。

### 两个诚实的负面结果（同样重要）
1. **FSP 治不了"措辞不同"**：同一批数据的 `intent` 字段上，三个模型 penalty 全为 **0.0**——模型答"挂号"、gold 写"挂号看病"，规范化解决不了语义同义，必须靠同义词表/语义匹配。**FSP 只解决表层形式，不解决语义等价。**
2. **只取首行会造成新的不公**：初版 FSP 仅取首行，导致长推理输出中命中的答案被截断，glm 出现 **penalty = −0.042**（宽松评分反而更低）。已修：首行严判 → 回退全文包含。这条本身就是"评分器公平性很难做对"的实证。

复现：`python3 scripts/harness_penalty.py --gold <bench.jsonl> --gold-field <field> --pred name=<pred.jsonl>`

## 自测
`testdata/clean.jsonl`（0 发现，退出 0）与 `testdata/dirty.jsonl`（含蓄意的 dup + gold-leak + near-dup，退出 1）在 CI 中断言，防止扫描器自身回归。

## 诚实说明
v0、零依赖、确定性；`cross_overlap` 是 n-gram 启发式，对改写/翻译型污染不敏感；`near_dup` 为 O(n²)，超大基准需分块。许可 CC BY 4.0。
