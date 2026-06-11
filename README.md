# AI 投资学课程案例：SPO 多资产 ETF 组合优化

本仓库用于《投资学》课程案例研究：**基于 Smart Predict--then--Optimize 的多资产 ETF 组合优化策略研究**。项目从 Yahoo Finance 获取 ETF 历史行情，构建机器学习特征和月度调仓样本，复现 SPO+ 决策导向学习流程，并输出数据、模型、组合和回测结果。

本项目仅用于课程研究和方法复现，不构成任何投资建议。

## 当前交付物

课程案例报告成品保存在：

| 文件 | 说明 |
|---|---|
| `docs/案例报告/AI投资学课程案例报告.md` | 报告源稿 |
| `docs/案例报告/AI投资学课程案例报告.docx` | Word 报告文件 |
| `docs/案例报告/AI投资学课程案例报告.pdf` | PDF 报告文件 |

说明：仓库不再保留案例报告自动化处理脚本；报告文件作为课程交付物保存，项目复现流水线只覆盖数据、模型、组合和回测。

支撑文档位于 `docs/`：

| 文件 | 说明 |
|---|---|
| `docs/project_deep_dive.md` | 项目代码、数据和结果事实沉淀 |
| `docs/spo_theory_and_literature_foundation.md` | SPO 理论、文献和算法基础 |
| `docs/empirical_results_and_dataset_quality.md` | 数据质量、回测和组合结果沉淀 |
| `docs/case_report_structure_redesign.md` | 案例报告结构重构说明 |
| `docs/data_source_and_preprocessing.md` | 数据来源与预处理说明 |
| `docs/role_b_dataset_guide.md` | 建模数据集使用说明 |
| `docs/spo_reproduction.md` | SPO 复现说明 |
| `docs/final_strategy_design.md` | 最终策略设计说明 |
| `docs/ai_prompt_design.md` | AI 风险组合提示词与结构化输出设计 |

## 项目结构

```text
.
├── data/
│   ├── raw/                         # Yahoo Finance 原始价格
│   └── processed/                   # 复权价格、收益率、特征、标签和建模面板
├── docs/                            # 研究说明、案例报告和支撑文档
├── environment/
│   └── etf-spo.yml                  # SPO 复现实验 Conda 环境
├── external/
│   ├── PyEPO/pkg/                   # 精简保留的 PyEPO editable 安装包
│   └── paper_2601_04062_source/     # SPO 论文 arXiv 源码材料
├── outputs/tables/                  # 数据、模型、组合和 AI 风险组合输出表
├── src/
│   ├── download_data.py             # 数据下载和质量检查
│   ├── features.py                  # 特征工程和标签构造
│   ├── reproduce_spo_paper.py       # PtO / SPO+ 训练和组合回测
│   └── generate_ai_risk_profiles.py # 三档 AI 风险组合生成和校验
└── test/
    ├── backtest_existing_models.py  # 独立回测、审计和图表生成
    └── backtest_outputs/            # 回测指标、图表和审计输出
```

说明：`external/PyEPO/` 已精简为本项目实际运行所需的 `pkg/` 包代码，删除了上游 CI、文档站、notebook、slides 和测试样例等冗余内容。

## 环境准备

基础数据下载和特征工程可使用 `uv`：

```bash
uv sync
```

SPO 训练、AI 风险组合和独立回测使用独立 Conda 环境：

```bash
conda env create -f environment/etf-spo.yml
```

如果环境已存在，可直接更新 PyEPO editable 安装：

```bash
conda run -n etf-spo python -m pip install -e external/PyEPO/pkg
```

不要使用 `sudo pip`，也不要混用系统 Python、Homebrew Python 与本项目环境。

## 完整复现流程

从仓库根目录运行：

```bash
conda run -n etf-spo python src/download_data.py
conda run -n etf-spo python src/features.py
conda run -n etf-spo python src/reproduce_spo_paper.py
conda run -n etf-spo python src/generate_ai_risk_profiles.py
conda run -n etf-spo python test/backtest_existing_models.py --cost-rate 0.005
```

## 数据集摘要

资产池覆盖 6 只代表性 ETF：

| ETF | 资产类别 | 组合含义 |
|---|---|---|
| SPY | 美国大盘股票 | S&P 500 大盘权益代表 |
| QQQ | 科技成长股票 | Nasdaq-100 成长股暴露 |
| TLT | 长期美国国债 | 久期和利率风险暴露 |
| GLD | 黄金 | 贵金属和避险资产 |
| VNQ | 房地产 REITs | 房地产权益风险 |
| DBC | 大宗商品 | 商品周期和通胀相关暴露 |

当前数据质量摘要：

| 项目 | 结果 |
|---|---|
| 样本区间 | 2018-01-02 至 2026-05-29 |
| 每只 ETF 价格行数 | 2113 |
| 复权价格缺失 | 0 |
| 重复日期 | 0 |
| 日度建模样本 | 11832 行 |
| 月末调仓样本 | 390 行 |
| 特征数量 | 22 |
| 标签数量 | 5 |

## 模型与回测

核心脚本：

| 脚本 | 作用 |
|---|---|
| `src/download_data.py` | 下载 Yahoo Finance 数据，输出复权价格、收益率和质量检查 |
| `src/features.py` | 构造 22 个历史特征、5 个未来 21 日标签和月末样本 |
| `src/reproduce_spo_paper.py` | 训练 Ridge PtO、PyEPO SPO+，生成策略权重和回测收益 |
| `src/generate_ai_risk_profiles.py` | 生成低、中、高三档 AI 风险组合并程序化校验 |
| `test/backtest_existing_models.py` | 独立复算净值、回撤、成本敏感性、特征重要性和未来函数审计 |

测试期为 2024-01-31 至 2026-04-29，共 28 个按月调仓样本。主报告采用 0.5% 单边交易成本。当前独立回测的主要结论是：`spo_plus_turnover_l2` 为综合评分最高的非基准策略，净总收益 106.36%、年化收益 36.41%、Sharpe 2.00、最大回撤 -7.38%；6ETF 等权组合仍是最强风险调整基准，净 Sharpe 2.51。

## 主要输出

| 路径 | 说明 |
|---|---|
| `outputs/tables/data_quality_check.csv` | ETF 数据质量明细 |
| `outputs/tables/feature_dataset_quality.json` | 特征、标签和样本切分摘要 |
| `outputs/tables/spo_prediction_scores.csv` | PtO / SPO+ 预测分数和真实未来收益 |
| `outputs/tables/spo_portfolio_weights.csv` | PtO / SPO+ / 基准组合权重 |
| `outputs/tables/spo_backtest_returns.csv` | SPO/PtO/基准策略逐月收益 |
| `outputs/tables/spo_model_metrics.csv` | 预测层 RMSE、MAE、R2 和 Rank IC |
| `outputs/tables/ai_risk_profile_portfolios.json` | 最新三档 AI 风险组合 JSON |
| `outputs/tables/ai_risk_profile_validation.json` | AI 组合权重和风险约束校验 |
| `test/backtest_outputs/backtest_summary.json` | 独立回测总摘要 |
| `test/backtest_outputs/model_quality_ranking.csv` | 策略质量评分排序 |
| `test/backtest_outputs/plots/` | 累计收益、回撤、热力图、特征重要性和绩效图 |

## 注意事项

- 本仓库包含数据、模型输出和课程报告，适合复现实验结果，不适合直接实盘交易。
- Yahoo Finance / yfinance 适合课程级复现，正式投资研究应使用交易所、基金公司或专业数据供应商数据复核。
- 历史回测结果不代表未来收益。
