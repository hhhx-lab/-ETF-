# 角色 B 建模数据集使用说明

本文档用于给角色 B（模型负责人）铺路，说明如何直接使用现有数据集进行机器学习模型训练，并避免“月度样本太少”和“未来信息泄漏”两个核心问题。

## 1. 为什么需要升级数据集

原计划中“月度调仓样本”只有约 600 条资产-月份观测，其中训练集更少。如果直接用这个样本训练随机森林，模型容易出现以下问题：

1. 样本量不足，模型不稳定；
2. 树模型容易过拟合；
3. 特征重要性波动大；
4. 验证集和测试集结果容易受个别月份影响；
5. 很难支撑“AI 真正利用数据学习资产阶段性机会”的论证。

因此，现已为角色 B 准备两层数据：

1. **日度建模主集**：用于模型训练，样本量更充足；
2. **月末调仓子集**：用于组合回测，保持投资组合月度调仓逻辑。

## 2. 核心交付文件

| 文件 | 用途 | 建议使用阶段 |
|---|---|---|
| `data/processed/modeling_dataset.csv` | 与实施计划一致的主建模数据集，内容等同日度主训练集 | 模型训练、验证、测试 |
| `data/processed/modeling_dataset_daily.csv` | 日度资产-日期面板，角色 B 主训练集 | 模型训练、验证、测试 |
| `data/processed/modeling_dataset_monthly_rebalance.csv` | 从日度面板中筛出的月末样本 | 月度调仓回测 |
| `data/processed/daily_features.csv` | 日度主面板特征 | 训练特征输入 |
| `data/processed/daily_labels.csv` | 日度主面板标签 | 训练标签输入 |
| `data/processed/monthly_features.csv` | 月末调仓样本特征，符合实施计划文件名 | 月度调仓预测 |
| `data/processed/monthly_labels.csv` | 月末调仓样本标签，符合实施计划文件名 | 月度回测校验 |
| `outputs/tables/feature_dataset_quality.json` | 特征数据集质量摘要 | 检查样本量、特征名、标签名 |

## 3. 数据集规模

| 数据集 | 行数 | 列数 | 说明 |
|---|---:|---:|---|
| `modeling_dataset.csv` | 11832 | 31 | 实施计划要求的主建模数据集 |
| `modeling_dataset_daily.csv` | 11832 | 31 | 主建模面板 |
| `modeling_dataset_monthly_rebalance.csv` | 390 | 31 | 月末调仓面板 |
| `daily_features.csv` | 11832 | 26 | 日度特征表 |
| `daily_labels.csv` | 11832 | 7 | 日度标签表 |
| `monthly_features.csv` | 390 | 26 | 月末特征表 |
| `monthly_labels.csv` | 390 | 7 | 月末标签表 |

样本区间：

| 项目 | 日期 |
|---|---|
| 首个可用特征日期 | 2018-06-25 |
| 最后可用标签日期 | 2026-04-29 |
| 月末调仓样本区间 | 2018-07-31 至 2026-03-31 |

说明：前 120 个交易日用于计算长期动量和均线特征，因此第一个可用特征日期晚于原始数据起点；最后 21 个交易日无法计算未来 21 日收益标签，因此被自然剔除。

## 4. 训练/验证/测试切分

切分已经在数据集中用 `split` 列标记：

| split | 日期规则 | 日度样本数 | 月末样本数 |
|---|---|---:|---:|
| train | date <= 2022-12-31 | 6834 | 228 |
| valid | 2023-01-01 <= date <= 2023-12-31 | 1500 | 54 |
| test | date >= 2024-01-01 | 3498 | 108 |

角色 B 训练时必须按 `split` 列切分，不要随机打乱全样本后再划分训练测试集。

## 5. 特征列

现有特征全部只使用样本日期当天及以前的数据计算，不使用未来收益。

| 特征 | 含义 |
|---|---|
| `ret_5d` | 过去 5 个交易日收益率 |
| `ret_20d` | 过去 20 个交易日收益率 |
| `ret_60d` | 过去 60 个交易日收益率 |
| `ret_120d` | 过去 120 个交易日收益率 |
| `vol_20d` | 过去 20 日波动率 |
| `vol_60d` | 过去 60 日波动率 |
| `downside_vol_60d` | 过去 60 日下行波动率 |
| `drawdown_20d` | 过去 20 日最大回撤 |
| `drawdown_60d` | 过去 60 日最大回撤 |
| `ma_ratio_20_60` | 20 日均价 / 60 日均价 - 1 |
| `ma_ratio_60_120` | 60 日均价 / 120 日均价 - 1 |
| `volume_chg_20d` | 20 日平均成交量 / 60 日平均成交量 - 1 |
| `risk_adj_ret_20d` | 20 日收益率 / 20 日波动率 |
| `risk_adj_ret_60d` | 60 日收益率 / 60 日波动率 |
| `asset_mean_ret_60d` | 过去 60 日日均收益 |
| `rank_ret_20d` | 当日 6 个 ETF 中 20 日收益率横截面排名百分位 |
| `rank_ret_60d` | 当日 6 个 ETF 中 60 日收益率横截面排名百分位 |
| `rank_vol_60d` | 当日 6 个 ETF 中 60 日波动率横截面排名百分位 |
| `rank_drawdown_60d` | 当日 6 个 ETF 中 60 日回撤横截面排名百分位 |
| `z_ret_20d` | 20 日收益率横截面标准化值 |
| `z_ret_60d` | 60 日收益率横截面标准化值 |
| `z_vol_60d` | 60 日波动率横截面标准化值 |

推荐角色 B 主模型使用全部 22 个特征。若模型表现不稳，可以先用以下简化特征组：

```text
ret_20d, ret_60d, ret_120d,
vol_20d, vol_60d,
drawdown_60d,
ma_ratio_20_60,
risk_adj_ret_60d,
rank_ret_60d,
rank_vol_60d
```

## 6. 标签列

标签统一使用未来 21 个交易日表现，约等于未来 1 个月。

| 标签 | 含义 | 建议用途 |
|---|---|---|
| `future_return_21d` | 未来 21 个交易日实际收益率 | 回测实际收益 |
| `future_rank_21d` | 未来 21 日收益率在 6 个 ETF 中的排名，1 为最高 | 排名分析 |
| `label_outperform_median_21d` | 是否跑赢当日 6 个 ETF 未来收益中位数 | 主分类标签 |
| `label_top2_21d` | 未来收益是否进入前 2 名 | 更激进的 Top 资产标签 |
| `label_positive_21d` | 未来收益是否为正 | 方向预测标签 |

推荐主模型：

```text
y = label_outperform_median_21d
```

原因：该标签每天正负样本比例稳定为 50% / 50%，比预测绝对正收益更平衡，也更贴合“在资产池中选择相对更好的资产”的组合配置任务。

## 7. 推荐建模流程

角色 B 可以直接按以下流程做：

```python
import json
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score

root = Path("/Users/hwaigc/workspace/投资学/ai_investment_case")
data = pd.read_csv(root / "data/processed/modeling_dataset.csv", parse_dates=["date"])
meta = json.loads((root / "outputs/tables/feature_dataset_quality.json").read_text())

feature_cols = meta["quality_summary"]["feature_names"]
target_col = "label_outperform_median_21d"

train = data[data["split"] == "train"]
valid = data[data["split"] == "valid"]
test = data[data["split"] == "test"]

X_train, y_train = train[feature_cols], train[target_col]
X_valid, y_valid = valid[feature_cols], valid[target_col]
X_test, y_test = test[feature_cols], test[target_col]

model = RandomForestClassifier(
    n_estimators=300,
    max_depth=4,
    min_samples_leaf=50,
    random_state=42,
    n_jobs=-1,
)
model.fit(X_train, y_train)

valid_proba = model.predict_proba(X_valid)[:, 1]
test_proba = model.predict_proba(X_test)[:, 1]
```

注意：树模型不强制要求标准化。如果使用逻辑回归，应只在训练集上 fit scaler，再 transform 验证集和测试集。

## 8. 月度调仓如何使用

角色 C 回测月度组合时，建议读取：

```text
data/processed/modeling_dataset_monthly_rebalance.csv
```

角色 B 可以先在日度主集训练模型，再对月末调仓子集输出预测概率：

```python
monthly = pd.read_csv(
    root / "data/processed/modeling_dataset_monthly_rebalance.csv",
    parse_dates=["date"],
)
monthly["rf_score"] = model.predict_proba(monthly[feature_cols])[:, 1]
```

之后角色 C 可以每个月选择 `rf_score` 最高的 3 个 ETF 进入组合。

## 9. 必须避免的错误

1. 不要随机划分训练集和测试集。
2. 不要用 `future_return_21d` 或任何 `label_` 列作为特征。
3. 不要在全样本上做标准化后再切分。
4. 不要用测试集调参。
5. 不要让同一天的 6 个资产在交叉验证中被拆到不同时间方向。
6. 不要把模型准确率写成投资成功率；最终仍需用组合收益回测评价。

## 10. 质量检查结果

| 检查项 | 结果 |
|---|---|
| 日度建模样本 | 11832 条 |
| 月末调仓样本 | 390 条 |
| 每个 ETF 日度样本 | 1972 条 |
| 每个 ETF 月末样本 | 65 条 |
| 特征缺失 | 0 |
| 标签缺失 | 0 |
| 主标签正样本比例 | 50.00% |
| Top2 标签正样本比例 | 33.33% |
| 正收益标签正样本比例 | 60.40% |

## 11. 给报告方法部分的写法

报告中可以这样写：

> 为避免月度样本过少导致模型训练不稳定，本文先构建日度资产-日期面板作为机器学习训练数据。对每个交易日和每个 ETF，本文计算过去 5 日、20 日、60 日和 120 日收益率，过去 20 日和 60 日波动率，过去 60 日最大回撤，均线比率、成交量变化和横截面排名等特征。所有特征均只使用样本日期及以前的信息。标签设定为未来 21 个交易日收益是否跑赢当日 6 个 ETF 的横截面中位数。该标签能够体现资产配置中“选择相对更优资产”的目标，同时保持正负样本平衡。模型训练使用日度面板，组合回测则使用月末样本进行调仓，从而兼顾训练样本量和投资组合可执行性。
