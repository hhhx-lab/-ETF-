# 基于 SPO 的多资产 ETF 组合优化复现

本仓库用于《投资学》课程 AI+投资学案例报告：**基于 Smart Predict--then--Optimize 的多资产 ETF 组合优化策略研究**。

项目目标是构建一个可复现的数据、建模与回测底座：从 Yahoo Finance 获取多资产 ETF 历史价格，生成机器学习特征和月度调仓样本，并在本地 ETF 数据集上复现 2026 年论文 **Smart Predict--then--Optimize Paradigm for Portfolio Optimization in Real Markets** 的 SPO 思路。

## 当前完成范围

已完成角色 A（数据负责人）的任务：

1. 建立项目环境和目录结构；
2. 编写 `src/download_data.py`；
3. 下载 SPY、QQQ、TLT、GLD、VNQ、DBC 六个 ETF 的日度数据；
4. 保存原始数据和复权收盘价数据；
5. 计算日收益率；
6. 生成数据质量检查表；
7. 输出数据来源与预处理说明文档。

已为角色 B（模型负责人）提前准备可训练建模数据集：

1. 编写 `src/features.py`；
2. 生成日度资产-日期建模主集；
3. 生成月末调仓子集；
4. 输出 22 个历史特征和 5 个未来 21 日标签；
5. 生成特征数据质量摘要；
6. 输出角色 B 数据集使用说明。

已完成 SPO 论文代码下载、本地 ETF 数据复现与 AI 风险组合生成：

1. 下载论文 arXiv 源码包到 `external/paper_2601_04062_source/`；
2. 确认论文源码包不包含 Python 实验代码或 GitHub 仓库链接；
3. 下载论文正文采用的 PyEPO 官方代码到 `external/PyEPO/`；
4. 新建 conda 环境 `etf-spo`；
5. 编写 `src/reproduce_spo_paper.py`；
6. 在本仓库 6 ETF 数据集上训练 PyEPO SPO+ 线性模型；
7. 输出 SPO/PtO 预测、组合权重、月度收益和回测指标；
8. 编写 `src/generate_ai_risk_profiles.py`；
9. 生成 ETF 单体风险收益指标、SPO 候选组合和低/中/高风险 AI 组合 JSON；
10. 将 AI 三档风险组合加入组合回测总表。

## 环境准备

数据下载和特征工程使用 `uv` 管理独立 Python 环境，避免污染系统 Python 或 Conda base 环境。

```bash
uv sync
```

依赖见 [pyproject.toml](pyproject.toml)，当前包括：

- `pandas`
- `numpy`
- `yfinance`

SPO 论文复现使用单独 conda 环境：

```bash
conda env create -f environment/etf-spo.yml
```

如果环境已存在：

```bash
conda create -y -n etf-spo python=3.11
conda run -n etf-spo python -m pip install pandas numpy scipy scikit-learn torch yfinance matplotlib tqdm pathos clarabel -e external/PyEPO/pkg
```

## 复现命令

```bash
git clone git@github.com:hhhx-lab/-ETF-.git
cd -ETF-
uv sync
uv run python src/download_data.py
```

`src/download_data.py` 会优先使用 `yfinance.download()`；如果当前环境出现 Yahoo/yfinance 网络或 TLS 问题，脚本会自动切换到 Yahoo Chart API 备用通道。只有数据质量检查通过后才会覆盖本地数据文件，避免失败下载把有效数据写成空表。

生成角色 B 建模数据集：

```bash
uv run python src/features.py
```

运行 SPO 论文复现：

```bash
conda run -n etf-spo python src/reproduce_spo_paper.py
```

生成 AI 三档风险组合：

```bash
conda run -n etf-spo python src/generate_ai_risk_profiles.py
```

生成课程技术报告：

```bash
conda run -n etf-spo python src/generate_technical_report.py
```

## 角色 A 交付物

| 文件 | 说明 |
|---|---|
| `src/download_data.py` | 可复现下载、预处理和质量检查脚本 |
| `data/raw/etf_prices_raw.csv` | Yahoo Finance 原始历史价格数据 |
| `data/processed/prices_adj_close.csv` | 6 个 ETF 的复权收盘价 |
| `data/processed/daily_returns.csv` | 基于复权收盘价计算的日收益率 |
| `outputs/tables/data_quality_check.csv` | 分 ETF 数据质量检查结果 |
| `outputs/tables/download_metadata.json` | 下载配置、质量摘要和文件路径 |
| `docs/data_source_and_preprocessing.md` | 数据来源与预处理说明，可用于报告数据章节 |

## 数据质量摘要

样本区间为 2018-01-02 至 2026-05-29。每个 ETF 均有 2113 条日度复权收盘价记录；6 个 ETF 日期范围一致，无重复日期、无复权价格缺失、无非正价格。日收益率每列首日有 1 个自然缺失值，来自 `pct_change()` 计算，不属于原始价格缺失。

## 角色 B 建模数据

| 文件 | 说明 |
|---|---|
| `src/features.py` | 特征工程和标签构造脚本 |
| `data/processed/modeling_dataset.csv` | 实施计划要求的主建模数据集，11832 行 |
| `data/processed/modeling_dataset_daily.csv` | 日度资产-日期主建模数据集，11832 行 |
| `data/processed/modeling_dataset_monthly_rebalance.csv` | 月末调仓子集，390 行 |
| `data/processed/daily_features.csv` | 日度特征表 |
| `data/processed/daily_labels.csv` | 日度标签表 |
| `data/processed/monthly_features.csv` | 月末特征表，符合原计划文件名 |
| `data/processed/monthly_labels.csv` | 月末标签表，符合原计划文件名 |
| `outputs/tables/feature_dataset_quality.json` | 特征数据质量摘要 |
| `docs/role_b_dataset_guide.md` | 角色 B 数据集使用说明 |

角色 B 推荐使用 `modeling_dataset.csv` 训练模型；该文件与 `modeling_dataset_daily.csv` 内容一致，是日度资产-日期主建模面板。随后用 `modeling_dataset_monthly_rebalance.csv` 输出月末预测分数供回测使用。

## SPO 论文复现结果

论文信息：

| 项目 | 内容 |
|---|---|
| 题目 | Smart Predict--then--Optimize Paradigm for Portfolio Optimization in Real Markets |
| arXiv | `2601.04062v3` |
| 作者 | Wang Yi, Takashi Hasuike |
| 论文源码 | `external/paper_2601_04062_source/` |
| SPO 代码基础 | `external/PyEPO/` |
| 复现说明 | `docs/spo_reproduction.md` |
| 最终策略设计 | `docs/final_strategy_design.md` |
| AI 提示词设计 | `docs/ai_prompt_design.md` |

当前复现使用本仓库 6 ETF 数据，按每月最后一个可交易日调仓。测试区间为 2024-01-31 至 2026-04-29，共 28 个月。

| 策略 | 口径 | 总收益 | 年化收益 | 年化波动 | Sharpe | 最大回撤 |
|---|---|---:|---:|---:|---:|---:|
| `ai_low_risk` | net | 58.40% | 21.79% | 7.41% | 2.94 | -2.99% |
| `ai_medium_risk` | net | 70.59% | 25.72% | 9.32% | 2.76 | -4.04% |
| `ai_high_risk` | net | 66.35% | 24.37% | 10.65% | 2.29 | -6.13% |
| `spo_plus_turnover_l2` | gross | 61.04% | 22.65% | 14.63% | 1.55 | -5.33% |
| `spo_plus_turnover_l2` | net | 39.59% | 15.37% | 14.56% | 1.06 | -6.31% |
| `spo_plus` | gross | 45.53% | 17.45% | 14.42% | 1.21 | -10.10% |
| `pto_markowitz` | gross | 60.32% | 22.42% | 12.16% | 1.84 | -12.55% |
| `equal_weight_6etf` | gross | 51.23% | 19.40% | 7.65% | 2.54 | -4.20% |
| `spy_buy_hold` | gross | 56.34% | 21.11% | 13.81% | 1.53 | -10.69% |

完整结果见：

| 文件 | 说明 |
|---|---|
| `outputs/tables/spo_prediction_scores.csv` | SPO/PtO 预测收益、排名和真实未来 21 日收益 |
| `outputs/tables/spo_portfolio_weights.csv` | 每月各策略 ETF 权重 |
| `outputs/tables/spo_backtest_returns.csv` | 每月毛收益、净收益、换手率和交易成本 |
| `outputs/tables/portfolio_backtest_metrics.csv` | 年化收益、波动率、Sharpe、Sortino、最大回撤、胜率、换手率 |
| `outputs/tables/spo_model_metrics.csv` | PtO 与 SPO+ 预测层指标 |
| `outputs/tables/spo_reproduction_metadata.json` | 复现环境、配置、校验结果和文件路径 |
| `outputs/tables/etf_risk_return_metrics.csv` | ETF 单体收益、风险、回撤和动量指标 |
| `outputs/tables/spo_candidate_portfolios.csv` | SPO/PtO/基准候选组合摘要 |
| `outputs/tables/ai_prompt_payload.json` | 可直接投喂外部大模型的提示词载荷 |
| `outputs/tables/ai_risk_profile_portfolios.json` | AI 生成的低/中/高风险组合 |
| `outputs/tables/ai_risk_profile_validation.json` | AI 组合权重与风险约束校验结果 |
| `docs/technical_report.md` | 算法预测与 AI 投资建议完整技术报告 |

## 目录结构

```text
.
├── data/
│   ├── raw/
│   │   └── etf_prices_raw.csv
│   └── processed/
│       ├── prices_adj_close.csv
│       ├── daily_returns.csv
│       ├── modeling_dataset.csv
│       ├── modeling_dataset_daily.csv
│       ├── modeling_dataset_monthly_rebalance.csv
│       ├── daily_features.csv
│       ├── daily_labels.csv
│       ├── monthly_features.csv
│       └── monthly_labels.csv
├── docs/
│   ├── ai_prompt_design.md
│   ├── data_source_and_preprocessing.md
│   ├── final_strategy_design.md
│   ├── role_c_implementation_summary.md
│   ├── role_b_dataset_guide.md
│   ├── spo_reproduction.md
│   └── technical_report.md
├── environment/
│   └── etf-spo.yml
├── external/
│   ├── PyEPO/
│   ├── paper_2601_04062_source/
│   └── paper_2601_04062_source_manifest.json
├── outputs/
│   └── tables/
│       ├── data_quality_check.csv
│       ├── download_metadata.json
│       ├── feature_dataset_quality.json
│       ├── spo_prediction_scores.csv
│       ├── spo_portfolio_weights.csv
│       ├── spo_backtest_returns.csv
│       ├── spo_candidate_portfolios.csv
│       ├── spo_model_metrics.csv
│       ├── spo_training_history.csv
│       ├── spo_reproduction_metadata.json
│       ├── etf_risk_return_metrics.csv
│       ├── ai_prompt_payload.json
│       ├── ai_risk_profile_weights.csv
│       ├── ai_risk_profile_backtest_returns.csv
│       ├── ai_risk_profile_portfolios.json
│       ├── ai_risk_profile_validation.json
│       └── portfolio_backtest_metrics.csv
└── src/
    ├── download_data.py
    ├── features.py
    ├── generate_ai_risk_profiles.py
    ├── generate_technical_report.py
    └── reproduce_spo_paper.py
```

## 数据集说明

ETF 池覆盖多资产配置中的主要资产：

| ETF | 资产类别 | 作用 |
|---|---|---|
| SPY | 美国大盘股票 | 买入持有基准和权益市场代表 |
| QQQ | 科技成长股票 | 高成长、高波动权益资产 |
| TLT | 长期美国国债 | 利率敏感型债券资产 |
| GLD | 黄金 | 避险和通胀对冲资产 |
| VNQ | 房地产 REITs | 房地产与利率周期暴露 |
| DBC | 大宗商品 | 商品周期和通胀暴露 |

核心建模标签是 `label_outperform_median_21d`：某 ETF 未来 21 个交易日收益是否跑赢当日 6 个 ETF 的横截面中位数。这个标签用于相对资产选择，适合后续构建 Top 3 ETF 月度调仓组合。

## 质量检查

可复现运行：

```bash
uv run python src/download_data.py
uv run python src/features.py
conda run -n etf-spo python src/reproduce_spo_paper.py
conda run -n etf-spo python src/generate_ai_risk_profiles.py
conda run -n etf-spo python src/generate_technical_report.py
```

检查结果会写入：

- [outputs/tables/data_quality_check.csv](outputs/tables/data_quality_check.csv)
- [outputs/tables/download_metadata.json](outputs/tables/download_metadata.json)
- [outputs/tables/feature_dataset_quality.json](outputs/tables/feature_dataset_quality.json)
- [outputs/tables/spo_reproduction_metadata.json](outputs/tables/spo_reproduction_metadata.json)
- [outputs/tables/ai_risk_profile_validation.json](outputs/tables/ai_risk_profile_validation.json)

当前审计结果：

- 原始复权价格无缺失、无重复日期、无非正价格；
- 日度主建模数据集有 11832 行；
- 月末调仓数据集有 390 行；
- 22 个历史特征无缺失；
- 5 个未来 21 日标签无缺失；
- 训练/验证/测试切分写入 `split` 列。
- SPO 复现输出 28 个测试期真实交易月末、168 条 ETF 月度预测；
- 各回测策略权重均为非负且每月权重和为 1；
- AI 三档风险组合权重和为 1、非负，并满足各自单只 ETF 权重上限；低风险档在 2 个历史调仓月触发最低波动回退并已标注；
- 回测指标均为可复算有限数值。

## 后续建模入口

角色 B 可以直接参考：

[docs/role_b_dataset_guide.md](docs/role_b_dataset_guide.md)

最小读取示例：

```python
import json
import pandas as pd
from pathlib import Path

root = Path(".")
data = pd.read_csv(root / "data/processed/modeling_dataset.csv", parse_dates=["date"])
meta = json.loads((root / "outputs/tables/feature_dataset_quality.json").read_text())

feature_cols = meta["quality_summary"]["feature_names"]
target_col = "label_outperform_median_21d"

train = data[data["split"] == "train"]
valid = data[data["split"] == "valid"]
test = data[data["split"] == "test"]
```

## 注意事项

本项目仅用于课程案例研究，不构成任何投资建议。历史表现不代表未来收益。Yahoo Finance / yfinance 适合课程项目复现，正式投资研究应以交易所、基金公司或专业数据供应商数据为准。
