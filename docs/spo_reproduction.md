# SPO 论文代码下载与本地 ETF 数据复现说明

本文档记录 `Smart Predict--then--Optimize Paradigm for Portfolio Optimization in Real Markets` 在本仓库 ETF 数据集上的复现方式。

## 1. 论文与代码来源

论文信息：

| 项目 | 内容 |
|---|---|
| 题目 | Smart Predict--then--Optimize Paradigm for Portfolio Optimization in Real Markets |
| arXiv | `2601.04062v3` |
| 作者 | Wang Yi, Takashi Hasuike |
| arXiv 页面 | https://arxiv.org/abs/2601.04062 |

已下载论文 arXiv 源码包：

```text
external/paper_2601_04062_source/
```

源码包中包含 `main.tex`、`ref.bib` 和图表文件，但没有 Python 实验代码，也没有 GitHub 仓库链接。正文第 2.2 节写明该研究采用 PyEPO 实现 SPO loss。因此，本复现下载并使用 PyEPO 官方代码：

```text
external/PyEPO/
```

复现元数据写入：

```text
external/paper_2601_04062_source_manifest.json
outputs/tables/spo_reproduction_metadata.json
```

## 2. Conda 环境

本复现使用独立 conda 环境，不依赖项目的 `uv` 环境。

创建环境：

```bash
conda env create -f environment/etf-spo.yml
```

如果环境已存在，可直接安装依赖：

```bash
conda create -y -n etf-spo python=3.11
conda run -n etf-spo python -m pip install pandas numpy scipy scikit-learn torch yfinance matplotlib tqdm pathos clarabel -e external/PyEPO/pkg
```

验证：

```bash
conda run -n etf-spo python -c "import torch, pyepo, pandas; print(torch.__version__)"
```

## 3. 复现命令

先生成基础数据和特征：

```bash
uv run python src/download_data.py
uv run python src/features.py
```

运行 SPO 复现：

```bash
conda run -n etf-spo python src/reproduce_spo_paper.py
```

生成 ETF 单体风险指标、SPO 候选组合和 AI 三档风险组合：

```bash
conda run -n etf-spo python src/generate_ai_risk_profiles.py
```

运行独立回测与审计：

```bash
conda run -n etf-spo python test/backtest_existing_models.py --cost-rate 0.005
```

可调参数：

```bash
conda run -n etf-spo python src/reproduce_spo_paper.py --epochs 240 --batch-size 16 --learning-rate 0.01
```

## 4. 复现方法

本仓库复现论文的核心思想，而不是复刻论文全部实验资产池。

当前实现：

1. 使用本仓库 6 只 ETF：`SPY`、`QQQ`、`TLT`、`GLD`、`VNQ`、`DBC`。
2. 使用已有 22 个历史特征。
3. 从日度建模主集按每月最后一个可交易日重建月度调仓样本。
4. 使用 `train + valid` 月份训练，`test` 月份回测。
5. 使用 PyEPO 的 `SPOPlus` loss 训练线性预测器。
6. 自定义 `MaxReturnOptModel` 作为 PyEPO 优化模型，长仓 MaxReturn 问题可闭式求解，无需 Gurobi 等商业求解器。
7. 对比策略：
   - `spo_plus`
   - `spo_plus_fee`
   - `spo_plus_turnover_l2`
   - `pto_markowitz`
   - `equal_weight_6etf`
   - `spy_buy_hold`

交易成本按论文设置使用 `0.005` 的比例成本，净收益按换手率扣除。

## 5. 输出文件

| 文件 | 说明 |
|---|---|
| `outputs/tables/spo_prediction_scores.csv` | 测试期每月每只 ETF 的 PtO/SPO 预测收益、排名和真实未来 21 日收益 |
| `outputs/tables/spo_portfolio_weights.csv` | 每月各策略 ETF 权重 |
| `outputs/tables/spo_backtest_returns.csv` | 每月各策略毛收益、净收益、换手率和交易成本 |
| `outputs/tables/portfolio_backtest_metrics.csv` | 各策略年化收益、波动率、夏普、Sortino、最大回撤、胜率、换手率 |
| `outputs/tables/spo_model_metrics.csv` | PtO 与 SPO+ 预测层指标 |
| `outputs/tables/spo_training_history.csv` | SPO+ 训练过程摘要 |
| `outputs/tables/spo_reproduction_metadata.json` | 复现配置、环境、校验结果和文件路径 |
| `outputs/tables/etf_risk_return_metrics.csv` | ETF 单体收益、风险、回撤和动量指标 |
| `outputs/tables/spo_candidate_portfolios.csv` | SPO/PtO/基准候选组合摘要 |
| `outputs/tables/ai_prompt_payload.json` | 可直接投喂外部大模型的提示词载荷 |
| `outputs/tables/ai_risk_profile_weights.csv` | AI 三档风险组合月度权重 |
| `outputs/tables/ai_risk_profile_backtest_returns.csv` | AI 三档风险组合月度回测收益 |
| `outputs/tables/ai_risk_profile_portfolios.json` | AI 输出的低/中/高风险组合 JSON |
| `outputs/tables/ai_risk_profile_validation.json` | AI 输出校验结果 |

## 6. 当前复现结果摘要

当前测试区间为 2024-01-31 至 2026-04-29，共 28 个真实交易月末。

| 策略 | 口径 | 总收益 | 年化收益 | 年化波动 | Sharpe | 最大回撤 | 平均换手 |
|---|---|---:|---:|---:|---:|---:|---:|
| `ai_low_risk` | net | 58.40% | 21.79% | 7.41% | 2.94 | -2.99% | 0.51 |
| `ai_medium_risk` | net | 70.59% | 25.72% | 9.32% | 2.76 | -4.04% | 0.62 |
| `ai_high_risk` | net | 66.35% | 24.37% | 10.65% | 2.29 | -6.13% | 0.79 |
| `spo_plus_turnover_l2` | gross | 61.04% | 22.65% | 14.63% | 1.55 | -5.33% | 1.04 |
| `spo_plus_turnover_l2` | net | 39.59% | 15.37% | 14.56% | 1.06 | -6.31% | 1.04 |
| `spo_plus` | gross | 45.53% | 17.45% | 14.42% | 1.21 | -10.10% | 1.32 |
| `spo_plus` | net | 21.12% | 8.56% | 14.50% | 0.59 | -11.99% | 1.32 |
| `pto_markowitz` | gross | 60.32% | 22.42% | 12.16% | 1.84 | -12.55% | 1.36 |
| `pto_markowitz` | net | 32.58% | 12.85% | 12.69% | 1.01 | -17.81% | 1.36 |
| `equal_weight_6etf` | gross | 51.23% | 19.40% | 7.65% | 2.54 | -4.20% | 0.04 |
| `spy_buy_hold` | gross | 56.34% | 21.11% | 13.81% | 1.53 | -10.69% | 0.04 |

解释要点：

- 预测层面，SPO+ 的点预测误差明显高于 PtO Ridge，但验证期 rank IC 更高。
- 组合层面，`spo_plus_turnover_l2` 相比普通 `spo_plus` 显著降低回撤并提高净收益。
- AI 三档风险组合在 SPO 候选组合和 ETF 单体风险收益指标基础上生成，并由程序化校验器复算权重、单资产上限和风险指标。
- 这体现了 SPO 论文的核心观点：预测误差不是最终目标，组合决策质量才是评价重点。

## 7. 局限性

1. 论文 arXiv 源码没有提供 Python 实验代码，因此本复现使用论文正文声明的 PyEPO 官方实现作为 SPO 代码基础。
2. 本仓库资产池为 6 只 ETF，论文使用的是更大的美国 ETF 数据集，结果不能直接与论文表格数值比较。
3. 本实现复现 MaxReturn/SPO+ 核心路径，未完整复现论文中的 RobustSPO、SoftmaxDFL 和 Optuna 滚动调参。
4. AI 组合层当前采用“结构化提示词决策 + 程序化优化器兜底”的可复现实现；若后续接入外部大模型，仍应保留程序化校验和回退逻辑。
5. 本项目仅用于课程案例研究，不构成任何投资建议。
