# Existing Model Backtest

This folder is an independent backtest layer for the existing models and strategy
outputs in this repository. It does not retrain models. It reads the current
tables under `outputs/tables/`, recomputes portfolio metrics, compares models
against benchmarks, and writes a standalone evaluation report.

## Inputs

Required files:

- `outputs/tables/spo_backtest_returns.csv`
- `outputs/tables/ai_risk_profile_backtest_returns.csv`
- `outputs/tables/spo_model_metrics.csv`

Optional validation/context files:

- `outputs/tables/spo_reproduction_metadata.json`
- `outputs/tables/ai_risk_profile_validation.json`

The evaluated existing strategies are:

- `spo_plus`
- `spo_plus_fee`
- `spo_plus_turnover_l2`
- `pto_markowitz`
- `ai_low_risk`
- `ai_medium_risk`
- `ai_high_risk`
- Benchmarks: `equal_weight_6etf`, `spy_buy_hold`

## Run

From the repository root:

```bash
python test/backtest_existing_models.py
```

Optional arguments:

```bash
python test/backtest_existing_models.py \
  --input-dir outputs/tables \
  --output-dir test/backtest_outputs \
  --benchmark equal_weight_6etf \
  --cost-rate 0.005
```

## Outputs

The script writes these files to `test/backtest_outputs/`:

- `combined_model_backtest_returns.csv`
- `strategy_backtest_metrics.csv`
- `strategy_equity_curves.csv`
- `strategy_drawdown_curves.csv`
- `strategy_excess_returns.csv`
- `transaction_cost_sensitivity.csv`
- `model_quality_ranking.csv`
- `model_assessment.csv`
- `lookahead_audit.json`
- `random_forest_feature_importance.csv`
- `backtest_summary.json`
- `existing_model_backtest_report.md`
- `plots/etf_price_index.png`
- `plots/strategy_cumulative_returns.png`
- `plots/strategy_drawdowns.png`
- `plots/ai_monthly_weight_heatmap.png`
- `plots/random_forest_feature_importance.png`
- `plots/strategy_performance_table.png`

## Evaluation Logic

Metrics are recomputed from monthly gross and net returns. The model scorecard
uses only non-benchmark strategies and combines:

- annualized net return
- Sharpe ratio
- max drawdown
- Calmar ratio
- win rate
- turnover penalty

This creates a repeatable ranking for the current repository outputs while
keeping benchmarks visible in the full metrics table.

## Look-Ahead Controls

The script emits `lookahead_audit.json` and reports these checks:

- month `t` features use prices, returns, and volume observed at or before `t`
- month `t` features map to the forward 21-trading-day return label
- backtested monthly returns align with the test label dates
- `StandardScaler` is fit before test transformation, not on the full sample
- train/validation dates end before test dates begin

Random forest feature importance is fit on the `train` split only and is used as
a diagnostic chart, not as an input to the existing SPO/PtO backtest.
