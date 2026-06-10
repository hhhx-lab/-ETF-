# 既有模型回测评估报告

## 回测范围

本报告只评估仓库已有模型和策略输出，不重新训练 SPO/PtO 主模型。测试区间为 2024-01-31 to 2026-04-29，共 28 个按月调仓样本。主表同时保留扣成本前后的指标，扣成本后结果按单边交易成本 0.0010 重新计算。

## 主要结论

综合评分最优的既有模型是 `spo_plus_turnover_l2`：扣成本后年化收益 41.38%，Sharpe 2.33，最大回撤 -6.58%，Calmar 6.29。风险调整收益最高的是 `ai_low_risk`，Sharpe 为 2.82。

## 未来函数控制

审计结果：通过。本回测遵循：t 月末只使用 t 月末及以前数据，预测未来 21 个交易日收益，组合收益使用下一期真实收益；StandardScaler 只在训练集 fit，验证集和测试集只 transform。

| rule | status | evidence |
| --- | --- | --- |
| t month-end features only use data observed at or before sample date | 通过 | All features use prices, returns, and volume observed at or before sample date. |
| t month-end features predict t+1 month / forward 21-trading-day returns | 通过 | Forward 21-trading-day return and cross-sectional relative labels. |
| portfolio return uses the next-period realized return already stored as future_return_21d | 通过 | backtest_dates=2024-01-31..2026-04-29, test_label_dates=2024-01-31..2026-04-29 |
| StandardScaler is fit on train split only, then transforms validation and test | 通过 | StandardScaler is fit on train split only; valid and test are transformed. |
| split dates keep test data after training/validation period | 通过 | train_valid_end=2023-11-30, test_start=2024-01-31 |

## 交易成本口径

扣成本后收益按以下公式逐月复算：`turnover_t = sum(abs(weight_t - weight_{t-1}))`，`cost_t = turnover_t * cost_rate`，`net_return_t = gross_return_t - cost_t`。主结果使用课程建议范围内的 0.10% 单边成本；敏感性表额外给出 0%、0.05%、0.10%、0.25%、0.50%、1.00%。

## 扣成本后模型排名

| rank | strategy | strategy_group | quality_score | annual_return | annual_volatility | sharpe | calmar | max_drawdown | win_rate | average_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | spo_plus_turnover_l2 | spo_model | 0.79 | 41.38% | 17.73% | 2.33 | 6.29 | -6.58% | 78.57% | 75.00% |
| 2 | ai_low_risk | ai_risk_profile | 0.63 | 20.67% | 7.33% | 2.82 | 5.57 | -3.71% | 71.43% | 69.01% |
| 3 | ai_medium_risk | ai_risk_profile | 0.54 | 19.91% | 9.27% | 2.15 | 3.18 | -6.26% | 85.71% | 91.16% |
| 4 | ai_high_risk | ai_risk_profile | 0.29 | 17.71% | 10.17% | 1.74 | 2.02 | -8.78% | 78.57% | 103.57% |
| 5 | spo_plus_fee | spo_model | 0.27 | 28.71% | 17.87% | 1.61 | 3.09 | -9.29% | 71.43% | 132.14% |
| 6 | spo_plus | spo_model | 0.27 | 28.71% | 17.87% | 1.61 | 3.09 | -9.29% | 71.43% | 132.14% |
| 7 | pto_markowitz | predict_then_optimize | 0.01 | 15.64% | 10.84% | 1.44 | 1.17 | -13.33% | 71.43% | 126.39% |

## 策略绩效对比表（扣成本后）

| strategy | strategy_group | total_return | annual_return | annual_volatility | sharpe | calmar | max_drawdown | win_rate | average_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| spo_plus_turnover_l2 | spo_model | 124.35% | 41.38% | 17.73% | 2.33 | 6.29 | -6.58% | 78.57% | 75.00% |
| spo_plus | spo_model | 80.19% | 28.71% | 17.87% | 1.61 | 3.09 | -9.29% | 71.43% | 132.14% |
| spo_plus_fee | spo_model | 80.19% | 28.71% | 17.87% | 1.61 | 3.09 | -9.29% | 71.43% | 132.14% |
| spy_buy_hold | benchmark | 56.19% | 21.06% | 13.79% | 1.53 | 1.97 | -10.69% | 67.86% | 3.57% |
| ai_low_risk | ai_risk_profile | 55.03% | 20.67% | 7.33% | 2.82 | 5.57 | -3.71% | 71.43% | 69.01% |
| ai_medium_risk | ai_risk_profile | 52.77% | 19.91% | 9.27% | 2.15 | 3.18 | -6.26% | 85.71% | 91.16% |
| equal_weight_6etf | benchmark | 51.08% | 19.35% | 7.64% | 2.53 | 4.61 | -4.20% | 82.14% | 3.57% |
| ai_high_risk | ai_risk_profile | 46.29% | 17.71% | 10.17% | 1.74 | 2.02 | -8.78% | 78.57% | 103.57% |
| pto_markowitz | predict_then_optimize | 40.38% | 15.64% | 10.84% | 1.44 | 1.17 | -13.33% | 71.43% | 126.39% |

## 策略绩效对比表（扣成本前）

| strategy | strategy_group | total_return | annual_return | annual_volatility | sharpe | calmar | max_drawdown | win_rate | average_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| spo_plus_turnover_l2 | spo_model | 129.06% | 42.65% | 17.63% | 2.42 | 6.68 | -6.38% | 78.57% | 75.00% |
| spo_plus | spo_model | 86.88% | 30.73% | 17.82% | 1.72 | 3.45 | -8.91% | 71.43% | 132.14% |
| spo_plus_fee | spo_model | 86.88% | 30.73% | 17.82% | 1.72 | 3.45 | -8.91% | 71.43% | 132.14% |
| ai_low_risk | ai_risk_profile | 58.02% | 21.66% | 7.30% | 2.97 | 6.74 | -3.22% | 75.00% | 69.01% |
| ai_medium_risk | ai_risk_profile | 56.66% | 21.22% | 9.25% | 2.29 | 3.54 | -5.98% | 85.71% | 91.16% |
| spy_buy_hold | benchmark | 56.34% | 21.11% | 13.81% | 1.53 | 1.98 | -10.69% | 67.86% | 3.57% |
| equal_weight_6etf | benchmark | 51.23% | 19.40% | 7.65% | 2.54 | 4.62 | -4.20% | 82.14% | 3.57% |
| ai_high_risk | ai_risk_profile | 50.55% | 19.17% | 10.12% | 1.89 | 2.29 | -8.36% | 78.57% | 103.57% |
| pto_markowitz | predict_then_optimize | 45.37% | 17.39% | 10.86% | 1.60 | 1.36 | -12.81% | 71.43% | 126.39% |

## 相对 `equal_weight_6etf` 的超额表现

| strategy | annual_excess_return | tracking_error | information_ratio | excess_win_rate | cumulative_excess_return |
| --- | --- | --- | --- | --- | --- |
| spo_plus_turnover_l2 | 18.47% | 0.18 | 1.03 | 50.00% | 48.32% |
| spo_plus | 8.86% | 0.1808 | 0.49 | 42.86% | 18.75% |
| spo_plus_fee | 8.86% | 0.1808 | 0.49 | 42.86% | 18.75% |
| spy_buy_hold | 2.08% | 0.0864 | 0.24 | 57.14% | 4.08% |
| ai_low_risk | 1.10% | 0.0421 | 0.26 | 50.00% | 2.39% |
| ai_medium_risk | 0.62% | 0.0495 | 0.12 | 53.57% | 1.16% |
| ai_high_risk | -1.19% | 0.0609 | -0.19 | 46.43% | -3.14% |
| pto_markowitz | -2.91% | 0.0761 | -0.38 | 35.71% | -7.18% |

## 既有模型优劣评价

| rank | strategy | strategy_group | strengths | weaknesses | recommended_use |
| --- | --- | --- | --- | --- | --- |
| 1 | spo_plus_turnover_l2 | spo_model | 年化收益领先；风险调整收益强；正则化显著改善基础 SPO+ 的净值表现 | 主要风险来自样本期较短 | 适合作为 SPO 类策略的生产化起点，但需要继续降低换手。 |
| 2 | ai_low_risk | ai_risk_profile | 年化收益领先；风险调整收益强；回撤控制好；换手相对可控；风险约束让波动和回撤更平滑 | 主要风险来自样本期较短 | 适合作为低波动核心组合或防守档位。 |
| 3 | ai_medium_risk | ai_risk_profile | 年化收益中等偏稳；风险调整收益强；风险约束让波动和回撤更平滑 | 主要风险来自样本期较短 | 适合作为当前样本下的主组合候选，收益和风险比较均衡。 |
| 4 | ai_high_risk | ai_risk_profile | 年化收益中等偏稳；风险约束让波动和回撤更平滑 | 换手高且交易成本敏感 | 适合愿意承受更高波动、追求更高收益弹性的配置。 |
| 5 | spo_plus_fee | spo_model | 年化收益领先 | 换手高且交易成本敏感；当前输出与基础 SPO+ 几乎重合，费用项没有形成有效约束 | 更适合保留为消融实验基线，而非直接实盘化。 |
| 6 | spo_plus | spo_model | 年化收益领先 | 换手高且交易成本敏感 | 更适合保留为消融实验基线，而非直接实盘化。 |
| 7 | pto_markowitz | predict_then_optimize | 年化收益中等偏稳 | 回撤压力大；换手高且交易成本敏感 | 适合作为传统 PtO/Markowitz 对照模型，不宜忽略成本。 |

## 预测层诊断

| model_name | split | rmse | mae | r2 | rank_ic |
| --- | --- | --- | --- | --- | --- |
| pto_ridge_markowitz | valid | 0.0634 | 0.0534 | -0.6168 | -0.0952 |
| pyepo_spo_plus_linear | valid | 1.4209 | 1.0903 | -811.646 | -0.2048 |
| pto_ridge_markowitz | test | 0.0547 | 0.0407 | -0.4967 | -0.0041 |
| pyepo_spo_plus_linear | test | 1.6039 | 1.2697 | -1285.5028 | -0.0041 |

## 图表输出

- ETF 价格或净值走势：`plots/etf_price_index.png`
- 各策略累计收益曲线：`plots/strategy_cumulative_returns.png`
- 各策略最大回撤曲线：`plots/strategy_drawdowns.png`
- AI 组合月度权重热力图：`plots/ai_monthly_weight_heatmap.png`
- 随机森林特征重要性图：`plots/random_forest_feature_importance.png`
- 策略绩效对比表：`plots/strategy_performance_table.png`

## 结果解释

- AI 风险画像组合在本样本中领先，因为它把 SPO/PtO 信号与波动率、单资产上限等组合约束结合，净值路径比原始 SPO 更平滑。
- 原始 `spo_plus` 能体现决策导向训练思路，但仓位集中、换手偏高；加入 turnover/L2 的 `spo_plus_turnover_l2` 明显改善净收益和回撤。
- `pto_markowitz` 扣成本前表现有竞争力，但换手和回撤压力较大，扣成本后优势明显下降。
- 等权组合仍是很强的基准。可交付模型不仅要扣成本前领先，也要在扣成本后超过等权基准。

## 生成文件

- `strategy_backtest_metrics.csv`: recomputed gross/net metrics for every strategy.
- `strategy_equity_curves.csv`: monthly gross and net wealth curves.
- `strategy_drawdown_curves.csv`: monthly gross and net drawdown curves.
- `strategy_excess_returns.csv`: net excess diagnostics versus the selected benchmark.
- `transaction_cost_sensitivity.csv`: metrics under several cost assumptions.
- `model_quality_ranking.csv`: standalone scorecard for non-benchmark models.
- `model_assessment.csv`: Chinese strengths, weaknesses, and usage recommendations.
- `lookahead_audit.json`: machine-readable look-ahead-bias audit.
- `random_forest_feature_importance.csv`: RF feature importance fit on train split only.
- `backtest_summary.json`: machine-readable summary and validation snapshot.

本项目仅用于课程案例研究，不构成任何投资建议。
