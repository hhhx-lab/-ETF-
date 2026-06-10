# 既有模型回测评估报告

## 回测范围

本报告只评估仓库已有模型和策略输出，不重新训练 SPO/PtO 主模型。测试区间为 2024-01-31 to 2026-04-29，共 28 个按月调仓样本。主表同时保留扣成本前后的指标，扣成本后结果按单边交易成本 0.0050 重新计算。

## 主要结论

综合评分最优的既有模型是 `spo_plus_turnover_l2`：扣成本后年化收益 36.41%，Sharpe 2.00，最大回撤 -7.38%，Calmar 4.93。风险调整收益最高的是 `equal_weight_6etf`，Sharpe 为 2.51。

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

扣成本后收益按以下公式逐月复算：`turnover_t = sum(abs(weight_t - weight_{t-1}))`，`cost_t = turnover_t * cost_rate`，`net_return_t = gross_return_t - cost_t`。主结果使用 0.50% 单边成本；敏感性表额外给出 0%、0.05%、0.10%、0.25%、0.50%、1.00%。

## 扣成本后模型排名

| rank | strategy | strategy_group | quality_score | annual_return | annual_volatility | sharpe | calmar | max_drawdown | win_rate | average_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | spo_plus_turnover_l2 | spo_model | 0.92 | 36.41% | 18.16% | 2.00 | 4.93 | -7.38% | 75.00% | 75.00% |
| 2 | ai_low_risk | ai_risk_profile | 0.68 | 16.78% | 7.49% | 2.24 | 2.96 | -5.66% | 67.86% | 69.01% |
| 3 | ai_medium_risk | ai_risk_profile | 0.57 | 14.83% | 9.40% | 1.58 | 1.97 | -7.52% | 75.00% | 91.16% |
| 4 | spo_plus | spo_model | 0.34 | 20.87% | 18.14% | 1.15 | 1.93 | -10.81% | 67.86% | 132.14% |
| 5 | spo_plus_fee | spo_model | 0.34 | 20.87% | 18.14% | 1.15 | 1.93 | -10.81% | 67.86% | 132.14% |
| 6 | ai_high_risk | ai_risk_profile | 0.28 | 12.03% | 10.41% | 1.16 | 1.11 | -10.86% | 67.86% | 103.57% |
| 7 | pto_markowitz | predict_then_optimize | 0.01 | 8.90% | 10.84% | 0.82 | 0.56 | -15.90% | 64.29% | 126.39% |

## 策略绩效对比表（扣成本后）

| strategy | strategy_group | total_return | annual_return | annual_volatility | sharpe | calmar | max_drawdown | win_rate | average_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| spo_plus_turnover_l2 | spo_model | 106.36% | 36.41% | 18.16% | 2.00 | 4.93 | -7.38% | 75.00% | 75.00% |
| spo_plus | spo_model | 55.63% | 20.87% | 18.14% | 1.15 | 1.93 | -10.81% | 67.86% | 132.14% |
| spo_plus_fee | spo_model | 55.63% | 20.87% | 18.14% | 1.15 | 1.93 | -10.81% | 67.86% | 132.14% |
| spy_buy_hold | benchmark | 55.60% | 20.86% | 13.74% | 1.52 | 1.95 | -10.69% | 67.86% | 3.57% |
| equal_weight_6etf | benchmark | 50.49% | 19.15% | 7.62% | 2.51 | 4.56 | -4.20% | 82.14% | 3.57% |
| ai_low_risk | ai_risk_profile | 43.62% | 16.78% | 7.49% | 2.24 | 2.96 | -5.66% | 67.86% | 69.01% |
| ai_medium_risk | ai_risk_profile | 38.08% | 14.83% | 9.40% | 1.58 | 1.97 | -7.52% | 75.00% | 91.16% |
| ai_high_risk | ai_risk_profile | 30.36% | 12.03% | 10.41% | 1.16 | 1.11 | -10.86% | 67.86% | 103.57% |
| pto_markowitz | predict_then_optimize | 22.00% | 8.90% | 10.84% | 0.82 | 0.56 | -15.90% | 64.29% | 126.39% |

## 策略绩效对比表（扣成本前）

| strategy | strategy_group | total_return | annual_return | annual_volatility | sharpe | calmar | max_drawdown | win_rate | average_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| spo_plus_turnover_l2 | spo_model | 129.06% | 42.65% | 17.63% | 2.42 | 6.68 | -6.38% | 78.57% | 75.00% |
| spo_plus | spo_model | 86.88% | 30.73% | 17.82% | 1.72 | 3.45 | -8.91% | 71.43% | 132.14% |
| spo_plus_fee | spo_model | 86.88% | 30.73% | 17.82% | 1.72 | 3.45 | -8.91% | 71.43% | 132.14% |
| ai_low_risk | ai_risk_profile | 58.01% | 21.66% | 7.30% | 2.97 | 6.74 | -3.22% | 75.00% | 69.01% |
| ai_medium_risk | ai_risk_profile | 56.66% | 21.22% | 9.25% | 2.29 | 3.54 | -5.98% | 85.71% | 91.16% |
| spy_buy_hold | benchmark | 56.34% | 21.11% | 13.81% | 1.53 | 1.98 | -10.69% | 67.86% | 3.57% |
| equal_weight_6etf | benchmark | 51.23% | 19.40% | 7.65% | 2.54 | 4.62 | -4.20% | 82.14% | 3.57% |
| ai_high_risk | ai_risk_profile | 50.55% | 19.17% | 10.12% | 1.89 | 2.29 | -8.36% | 78.57% | 103.57% |
| pto_markowitz | predict_then_optimize | 45.37% | 17.39% | 10.86% | 1.60 | 1.36 | -12.81% | 71.43% | 126.39% |

## 相对 `equal_weight_6etf` 的超额表现

| strategy | annual_excess_return | tracking_error | information_ratio | excess_win_rate | cumulative_excess_return |
| --- | --- | --- | --- | --- | --- |
| spo_plus_turnover_l2 | 15.04% | 0.1844 | 0.82 | 46.43% | 36.80% |
| spo_plus | 2.69% | 0.1843 | 0.15 | 35.71% | 2.73% |
| spo_plus_fee | 2.69% | 0.1843 | 0.15 | 35.71% | 2.73% |
| spy_buy_hold | 2.08% | 0.0864 | 0.24 | 57.14% | 4.08% |
| ai_low_risk | -2.04% | 0.0422 | -0.48 | 42.86% | -4.85% |
| ai_medium_risk | -3.59% | 0.051 | -0.70 | 42.86% | -8.32% |
| ai_high_risk | -5.99% | 0.0639 | -0.94 | 35.71% | -13.47% |
| pto_markowitz | -8.81% | 0.076 | -1.16 | 32.14% | -19.17% |

## 既有模型优劣评价

| rank | strategy | strategy_group | strengths | weaknesses | recommended_use |
| --- | --- | --- | --- | --- | --- |
| 1 | spo_plus_turnover_l2 | spo_model | 年化收益领先；风险调整收益强；正则化显著改善基础 SPO+ 的净值表现 | 主要风险来自样本期较短 | 适合作为 SPO 类策略的生产化起点，但需要继续降低换手。 |
| 2 | ai_low_risk | ai_risk_profile | 年化收益中等偏稳；风险调整收益强；换手相对可控；风险约束让波动和回撤更平滑 | 主要风险来自样本期较短 | 适合作为低波动核心组合或防守档位。 |
| 3 | ai_medium_risk | ai_risk_profile | 年化收益中等偏稳；风险约束让波动和回撤更平滑 | 主要风险来自样本期较短 | 适合作为当前样本下的主组合候选，收益和风险比较均衡。 |
| 4 | spo_plus | spo_model | 年化收益领先 | 回撤压力大；换手高且交易成本敏感 | 更适合保留为消融实验基线，而非直接实盘化。 |
| 5 | spo_plus_fee | spo_model | 年化收益领先 | 回撤压力大；换手高且交易成本敏感；当前输出与基础 SPO+ 几乎重合，费用项没有形成有效约束 | 更适合保留为消融实验基线，而非直接实盘化。 |
| 6 | ai_high_risk | ai_risk_profile | 年化收益中等偏稳；风险约束让波动和回撤更平滑 | 回撤压力大；换手高且交易成本敏感 | 适合愿意承受更高波动、追求更高收益弹性的配置。 |
| 7 | pto_markowitz | predict_then_optimize | 没有明显优势 | 净收益不足；Sharpe 偏低；回撤压力大；换手高且交易成本敏感 | 适合作为传统 PtO/Markowitz 对照模型，不宜忽略成本。 |

## 预测层诊断

| model_name | split | rmse | mae | r2 | rank_ic |
| --- | --- | --- | --- | --- | --- |
| pto_ridge_markowitz | valid | 0.0634 | 0.0534 | -0.6168 | -0.0952 |
| pyepo_spo_plus_linear | valid | 1.4209 | 1.0903 | -811.6444 | -0.2048 |
| pto_ridge_markowitz | test | 0.0547 | 0.0407 | -0.4967 | -0.0041 |
| pyepo_spo_plus_linear | test | 1.6039 | 1.2697 | -1285.5018 | -0.0041 |

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
