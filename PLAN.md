# PLAN · bench-contam-scan

## 目标
JSONL 评测基准的离线污染/完整性扫描器。把 fraud/endurance 两基准里现成的
基础设施（manifest 哈希、重复检测、check 回归）抽象成通用工具。诚实边界：
发现是人工复核信号，非训练污染证明。

## v0（已达成 ✅）
- [x] scan.py：exact_dup / near_dup(5-gram Jaccard) / gold_leak / cross_overlap(8-gram containment)，退出码 CI 友好
- [x] fingerprint.py：全文件+逐条 sha256 + ID 集 + schema + 标签分布，--verify 校验
- [x] 自测 testdata（clean 退 0 / dirty 退 1）+ CI 断言
- [x] Dogfood 两真实基准：fraud 全干净、endurance near_dup 13（模板 system，预期）
- [x] 零依赖、确定性、CC BY 4.0

## v1（已达成 ✅ 2026-07-19）
- [x] harness_probe.py：评分器公平性探针（9 类语义等价变体注入，纯离线）
- [x] 实测 4 真实基准 + demo：严格字面匹配 fnr 0.714–0.778 → FSP 后 0.0
- [x] 最脆类型：wrapped(JSON/引号/fence) 与 explained(答对带解释) 均 100% 误判——正是强模型常见输出形态
- [x] Fair Scoring Protocol 参考实现（score_fsp）

## 路线图
- v1：probe_model.py（模型侧记忆启发式：给题面前半让模型续写，比对后半——高相似=疑似记忆）
- v1：near_dup 分块/LSH，支持大基准；cross_overlap 支持目录批量 --against
- v2：接入 HF datasets 直接扫；输出 SARIF 供 code scanning
