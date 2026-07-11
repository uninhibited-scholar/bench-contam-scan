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

## 自测
`testdata/clean.jsonl`（0 发现，退出 0）与 `testdata/dirty.jsonl`（含蓄意的 dup + gold-leak + near-dup，退出 1）在 CI 中断言，防止扫描器自身回归。

## 诚实说明
v0、零依赖、确定性；`cross_overlap` 是 n-gram 启发式，对改写/翻译型污染不敏感；`near_dup` 为 O(n²)，超大基准需分块。许可 CC BY 4.0。
