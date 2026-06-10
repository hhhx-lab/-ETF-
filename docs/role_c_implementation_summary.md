# 角色 C 实现总结：SPO 回测与 AI 风险组合

本文档汇总角色 C 当前已完成的组合优化、回测评估、AI 风险档位输出和 conda 环境信息。

## 1. 已完成内容

角色 C 已完成以下实现：

1. 下载论文 arXiv 源码包到 `external/paper_2601_04062_source/`；
2. 核验源码包内容，确认其中包含 `main.tex`、`ref.bib` 和图表文件，但不包含 Python 实验代码或 GitHub 仓库链接；
3. 下载论文正文使用的 PyEPO 官方代码到 `external/PyEPO/`；
4. 新建 conda 环境 `etf-spo`；
5. 编写 `src/reproduce_spo_paper.py`，在本仓库 6 ETF 数据上复现 SPO+ 核心训练和月度回测；
6. 编写 `src/generate_ai_risk_profiles.py`，生成 ETF 单体风险收益指标、SPO 候选组合、AI 低/中/高风险组合；
7. 输出组合回测指标并完成程序化校验。

## 2. Conda 环境

环境文件：

```text
environment/etf-spo.yml
```

创建命令：

```bash
conda env create -f environment/etf-spo.yml
```

当前环境名：

```text
etf-spo
```

核心依赖：

| 依赖 | 用途 |
|---|---|
| pandas / numpy | 数据处理和矩阵计算 |
| scipy | 组合优化求解 |
| scikit-learn | Ridge / 标准化 / 预测指标 |
| torch | SPO+ 线性预测模型训练 |
| PyEPO | SPO+ loss 和 predict-then-optimize 框架 |
| yfinance | 数据下载备用依赖 |

## 3. 运行命令

从仓库根目录运行完整流水线：

```bash
uv run python src/download_data.py
uv run python src/features.py
conda run -n etf-spo python src/reproduce_spo_paper.py
conda run -n etf-spo python src/generate_ai_risk_profiles.py
conda run -n etf-spo python test/backtest_existing_models.py --cost-rate 0.005
conda run -n etf-spo python scripts/generate_case_report.py
codex-docx-to-pdf docs/案例报告/AI投资学课程案例报告.docx docs/案例报告
```

## 4. 核心输出

| 文件 | 说明 |
|---|---|
| `outputs/tables/spo_prediction_scores.csv` | 测试期每月每只 ETF 的 SPO/PtO 预测收益、排名和真实未来收益 |
| `outputs/tables/spo_portfolio_weights.csv` | SPO/PtO/基准组合月度权重 |
| `outputs/tables/spo_backtest_returns.csv` | SPO/PtO/基准组合月度毛收益、净收益、换手和成本 |
| `outputs/tables/etf_risk_return_metrics.csv` | ETF 单体收益、风险、回撤和动量指标 |
| `outputs/tables/spo_candidate_portfolios.csv` | 候选组合收益、风险、换手和权重摘要 |
| `outputs/tables/ai_prompt_payload.json` | 可直接投喂外部大模型的提示词载荷 |
| `outputs/tables/ai_risk_profile_portfolios.json` | AI 低/中/高风险组合 JSON |
| `outputs/tables/ai_risk_profile_weights.csv` | AI 低/中/高风险组合月度权重 |
| `outputs/tables/portfolio_backtest_metrics.csv` | 全部组合和基准的回测指标总表 |
| `outputs/tables/ai_risk_profile_validation.json` | AI 组合校验结果 |
| `docs/案例报告/AI投资学课程案例报告.md` | 正式案例报告 Markdown 源稿 |
| `docs/案例报告/AI投资学课程案例报告.docx` | 正式案例报告 Word 可编辑稿 |
| `docs/案例报告/AI投资学课程案例报告.pdf` | 正式案例报告 PDF 交付稿 |

## 5. 当前回测结果

测试区间为 2024-01-31 至 2026-04-29，共 28 个真实交易月末。

| 策略 | 口径 | 总收益 | 年化收益 | 年化波动 | Sharpe | 最大回撤 |
|---|---|---:|---:|---:|---:|---:|
| `ai_low_risk` | net | 58.40% | 21.79% | 7.41% | 2.94 | -2.99% |
| `ai_medium_risk` | net | 70.59% | 25.72% | 9.32% | 2.76 | -4.04% |
| `ai_high_risk` | net | 66.35% | 24.37% | 10.65% | 2.29 | -6.13% |
| `spo_plus_turnover_l2` | net | 39.59% | 15.37% | 14.56% | 1.06 | -6.31% |
| `equal_weight_6etf` | net | 50.49% | 19.15% | 7.62% | 2.51 | -4.20% |
| `spy_buy_hold` | net | 55.60% | 20.86% | 13.74% | 1.52 | -10.69% |

## 6. 校验结果

已通过的校验：

1. `spo_prediction_scores.csv` 包含 28 个测试月，每月 6 只 ETF，共 168 条预测；
2. SPO/PtO/基准组合权重均非负，且每月权重和为 1；
3. AI 低/中/高风险组合权重均非负，且每月权重和为 1；
4. AI 组合满足各自单只 ETF 权重上限；
5. AI 组合风险指标由代码基于协方差矩阵复算；
6. 低风险档在 2025-04-30 和 2025-05-30 两个历史调仓月无法完全满足 10% 年化波动率约束，系统已按设计回退到最低波动组合并在校验文件中标注；
7. `ai_prompt_payload.json` 已包含提示词、结构化输入、输出 schema 和参考校验输出；
8. 回测指标均为有限数值；
9. `portfolio_backtest_metrics.csv` 同时包含 AI 组合、SPO 组合和基准组合。

## 7. 报告表述建议

报告中可写：

> 本项目采用 Smart Predict--then--Optimize 范式训练预测模型，使预测目标直接服务于投资组合决策质量。由于论文 arXiv 源码包未提供 Python 实验代码，本文根据论文方法和其采用的 PyEPO 框架，在本项目 6 ETF 数据集上复现 SPO+ 训练与月度回测。随后，本文将 SPO 候选组合、ETF 单体风险收益指标和风险偏好约束输入 AI 决策层，生成低风险、中风险、高风险三类配置建议。所有 AI 权重均通过程序化校验，确保权重和、非负约束、单资产上限和风险指标可复算；若风险约束不可完全满足，则回退到同档位最低波动组合并在结果中标注。

本项目仅用于课程案例研究，不构成任何投资建议。
