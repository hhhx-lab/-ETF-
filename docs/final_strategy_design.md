# 最终策略设计：基于 SPO 与 AI 提示决策的多风险 ETF 组合优化

本文档作为课程报告的方法章节依据，记录本项目最终设计和已经落地的实现口径。

## 1. 项目定位

项目目标是“运用 AI 技术进行优化投资组合配置，构建最优资产配置策略，进行风险评估和收益预测，提高投资组合的整体绩效”。最终设计不再把普通分类准确率作为主线，而是采用 **Smart Predict--then--Optimize, SPO** 思路：预测模型直接服务于后续组合优化决策，评价指标也以组合收益、波动、夏普比率、最大回撤和换手率为核心。

理论依据为 Wang Yi 和 Takashi Hasuike 的 2026 年论文 *Smart Predict--then--Optimize Paradigm for Portfolio Optimization in Real Markets*。本仓库已下载 arXiv 源码包到 `external/paper_2601_04062_source/`。该源码包没有 Python 实验代码或 GitHub 链接，正文说明采用 PyEPO 实现 SPO loss，因此本项目下载 PyEPO 官方代码到 `external/PyEPO/`，并在本项目 6 ETF 数据集上复现 SPO+ 核心路径。

本项目仅用于课程案例研究，不构成投资建议。

## 2. 数据层

资产池沿用当前 6 只 ETF：

| ETF | 资产类别 | 组合作用 |
|---|---|---|
| SPY | 美国大盘股票 | 权益市场基准 |
| QQQ | 科技成长股票 | 高成长、高波动资产 |
| TLT | 长期美国国债 | 防御和利率敏感资产 |
| GLD | 黄金 | 避险和通胀对冲 |
| VNQ | 房地产 REITs | 房地产和利率周期暴露 |
| DBC | 大宗商品 | 商品周期和通胀暴露 |

数据来源为 Yahoo Finance，样本区间为 2018-01-02 至 2026-05-29。特征工程生成 22 个历史特征，包括动量、波动率、下行波动率、回撤、均线比率、成交量变化、风险调整收益和横截面排名。标签使用未来 21 个交易日收益，月度调仓使用每月最后一个可交易日。

核心数据文件：

| 文件 | 说明 |
|---|---|
| `data/processed/modeling_dataset.csv` | 日度资产-日期建模主集 |
| `data/processed/modeling_dataset_monthly_rebalance.csv` | 月末调仓样本 |
| `outputs/tables/feature_dataset_quality.json` | 特征和标签质量摘要 |

## 3. SPO 预测-优化层

SPO 层的主线是“预测服务于优化”。预测模型不只追求未来收益点预测误差最小，而是让预测结果在下游组合优化器中产生更好的权重决策。

当前实现位于：

```bash
src/reproduce_spo_paper.py
```

实现内容：

1. 使用 `train + valid` 月度样本训练，`test` 月度样本回测；
2. 使用 PyEPO 的 `SPOPlus` loss 训练线性 PyTorch 收益预测模型；
3. 自定义 `MaxReturnOptModel`，闭式求解长仓 MaxReturn 优化问题，避免依赖商业求解器；
4. 输出 SPO 预测分数、预测排名、组合权重和月度回测结果；
5. 与普通 PtO Ridge + Markowitz、6 ETF 等权组合、SPY 买入持有组合对照。

主要输出：

| 文件 | 说明 |
|---|---|
| `outputs/tables/spo_prediction_scores.csv` | 每月每只 ETF 的 SPO/PtO 预测、排名和真实未来收益 |
| `outputs/tables/spo_portfolio_weights.csv` | SPO、PtO 和基准组合月度权重 |
| `outputs/tables/spo_backtest_returns.csv` | 月度毛收益、净收益、换手和交易成本 |
| `outputs/tables/portfolio_backtest_metrics.csv` | 组合绩效总表 |
| `outputs/tables/spo_model_metrics.csv` | 预测层指标 |
| `outputs/tables/spo_training_history.csv` | SPO+ 训练过程 |

## 4. ETF 单体风险收益层

为支持 AI 提示决策，本项目对每只 ETF 计算单体风险收益指标：

| 指标 | 含义 |
|---|---|
| `expected_return_21d_pto` | PtO 模型预测未来 21 日收益 |
| `spo_decision_score` | SPO+ 决策分数 |
| `historical_annual_return` | 历史年化收益 |
| `annual_volatility` | 历史年化波动率 |
| `max_drawdown` | 历史最大回撤 |
| `sharpe` | 历史夏普比率 |
| `momentum_21d` / `momentum_60d` / `momentum_120d` | 多窗口动量 |
| `downside_volatility` | 年化下行波动率 |

输出文件：

```text
outputs/tables/etf_risk_return_metrics.csv
```

## 5. AI 提示决策层

AI 决策层接收三类结构化输入：

1. SPO 候选组合：来自 `outputs/tables/spo_candidate_portfolios.csv`；
2. ETF 单体风险收益表：来自 `outputs/tables/etf_risk_return_metrics.csv`；
3. 风险档位约束：低风险、中风险、高风险。

AI 的任务是针对不同风险偏好生成最终 ETF 权重建议。为了保证输出不是纯文本解释，系统要求 AI 输出结构化 JSON，并由程序重新校验权重和风险指标。如果 AI 输出不满足约束，则回退到同一约束下的程序化优化器结果。

当前实现位于：

```bash
src/generate_ai_risk_profiles.py
```

由于课程项目本地环境没有固定外部大模型 API，本实现采用“结构化提示词决策 + 程序化优化器兜底”的方式生成可复算 JSON。报告中可表述为：AI 层负责把 SPO 候选组合、ETF 风险收益指标和风险偏好转化为最终配置建议；所有权重由代码校验，不能只依赖 AI 文本解释。

输出文件：

| 文件 | 说明 |
|---|---|
| `outputs/tables/spo_candidate_portfolios.csv` | SPO/PtO/基准候选组合的收益、风险和权重摘要 |
| `outputs/tables/ai_prompt_payload.json` | 可直接投喂外部大模型的提示词载荷 |
| `outputs/tables/ai_risk_profile_portfolios.json` | AI 三档风险组合 JSON |
| `outputs/tables/ai_risk_profile_weights.csv` | AI 三档风险组合月度权重 |
| `outputs/tables/ai_risk_profile_backtest_returns.csv` | AI 三档风险组合月度回测收益 |
| `outputs/tables/ai_risk_profile_validation.json` | AI 输出校验结果 |

## 6. 风险档位

| 风险档位 | 目标 | 年化波动率上限 | 单只 ETF 权重上限 | 配置倾向 |
|---|---|---:|---:|---|
| 低风险 | 在波动率不超过 10% 的前提下最大化预期收益 | 10% | 35% | 提高 TLT、GLD 等防御资产权重 |
| 中风险 | 在波动率不超过 15% 的前提下最大化预期收益 | 15% | 45% | 在权益、债券、黄金、商品间均衡配置 |
| 高风险 | 在波动率不超过 22% 的前提下最大化预期收益 | 22% | 60% | 允许提高 SPY、QQQ 等权益资产权重 |

若某档位不可行，系统采用该档位权重上限下的最低波动组合，并在 JSON 和报告中标注“风险约束不可完全满足”。

## 7. 复现命令

从仓库根目录运行：

```bash
uv run python src/download_data.py
uv run python src/features.py
conda env create -f environment/etf-spo.yml
conda run -n etf-spo python src/reproduce_spo_paper.py
conda run -n etf-spo python src/generate_ai_risk_profiles.py
conda run -n etf-spo python test/backtest_existing_models.py --cost-rate 0.005
```

如果 `etf-spo` 环境已存在，可跳过 `conda env create`。

## 8. 评价指标

最终报告以组合绩效为核心：

1. 年化收益；
2. 年化波动率；
3. 夏普比率；
4. Sortino 比率；
5. 最大回撤；
6. 胜率；
7. 平均换手率；
8. 交易成本后的净收益。

对照基准包括：

1. 6 ETF 等权组合；
2. SPY 买入持有；
3. 传统 PtO Ridge + Markowitz 组合；
4. 普通 SPO+ 组合；
5. 带交易成本、换手和 L2 正则的 SPO+ 组合。

## 9. 测试与校验

当前实现包含以下程序化校验：

1. `spo_prediction_scores.csv` 每个测试月必须包含 6 只 ETF；
2. 所有组合每月权重和必须为 1；
3. 所有组合必须为非负权重；
4. AI 三档组合必须满足对应单只 ETF 权重上限；
5. AI 风险指标由代码基于协方差矩阵复算；
6. `portfolio_backtest_metrics.csv` 必须同时包含 AI 组合、SPO 组合和基准组合；
7. 若风险约束不可完全满足，校验文件必须标注最低波动回退；
8. `ai_prompt_payload.json` 必须包含提示词、结构化输入、输出 schema 和参考校验输出；
9. 所有绩效指标必须为有限数值。
