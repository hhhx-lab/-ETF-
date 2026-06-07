# 基于机器学习收益预测的多资产 ETF 组合优化

本仓库用于《投资学》课程 AI+投资学案例报告：**基于机器学习收益预测的多资产 ETF 组合优化策略研究**。

项目目标是构建一个可复现的数据与建模底座：从 Yahoo Finance 获取多资产 ETF 历史价格，完成数据质量检查，生成日度资产-日期建模面板和月末调仓样本，为后续逻辑回归、随机森林和投资组合回测做准备。

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

## 环境准备

本项目使用 `uv` 管理独立 Python 环境，避免污染系统 Python 或 Conda base 环境。

```bash
uv sync
```

依赖见 [pyproject.toml](pyproject.toml)，当前包括：

- `pandas`
- `numpy`
- `yfinance`

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
│   ├── data_source_and_preprocessing.md
│   └── role_b_dataset_guide.md
├── outputs/
│   └── tables/
│       ├── data_quality_check.csv
│       ├── download_metadata.json
│       └── feature_dataset_quality.json
└── src/
    ├── download_data.py
    └── features.py
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
```

检查结果会写入：

- [outputs/tables/data_quality_check.csv](outputs/tables/data_quality_check.csv)
- [outputs/tables/download_metadata.json](outputs/tables/download_metadata.json)
- [outputs/tables/feature_dataset_quality.json](outputs/tables/feature_dataset_quality.json)

当前审计结果：

- 原始复权价格无缺失、无重复日期、无非正价格；
- 日度主建模数据集有 11832 行；
- 月末调仓数据集有 390 行；
- 22 个历史特征无缺失；
- 5 个未来 21 日标签无缺失；
- 训练/验证/测试切分写入 `split` 列。

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
