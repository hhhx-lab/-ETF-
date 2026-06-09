from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize


TICKERS = ["SPY", "QQQ", "TLT", "GLD", "VNQ", "DBC"]
TRADING_DAYS_PER_YEAR = 252
MONTHS_PER_YEAR = 12
DEFAULT_COST_RATE = 0.005

RISK_PROFILES = {
    "low_risk": {
        "label_zh": "低风险",
        "annual_volatility_max": 0.10,
        "single_etf_weight_max": 0.35,
        "risk_preference": "优先控制波动和回撤，偏向 TLT、GLD 等防御资产。",
    },
    "medium_risk": {
        "label_zh": "中风险",
        "annual_volatility_max": 0.15,
        "single_etf_weight_max": 0.45,
        "risk_preference": "在权益、债券、黄金、房地产和商品之间均衡配置。",
    },
    "high_risk": {
        "label_zh": "高风险",
        "annual_volatility_max": 0.22,
        "single_etf_weight_max": 0.60,
        "risk_preference": "允许提高 SPY、QQQ 等权益和成长资产权重。",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate ETF risk-return metrics and AI-style risk profile portfolios."
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/tables",
        help="Relative directory for generated tables and JSON artifacts.",
    )
    parser.add_argument(
        "--cost-rate",
        type=float,
        default=DEFAULT_COST_RATE,
        help="One-way proportional transaction cost used in net-return backtests.",
    )
    return parser.parse_args()


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_inputs(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    returns = (
        pd.read_csv(root / "data" / "processed" / "daily_returns.csv", parse_dates=["Date"])
        .rename(columns={"Date": "date"})
        .set_index("date")
        .reindex(columns=TICKERS)
    )
    prices = (
        pd.read_csv(root / "data" / "processed" / "prices_adj_close.csv", parse_dates=["Date"])
        .rename(columns={"Date": "date"})
        .set_index("date")
        .reindex(columns=TICKERS)
    )
    scores = pd.read_csv(root / "outputs" / "tables" / "spo_prediction_scores.csv", parse_dates=["date"])
    weights = pd.read_csv(root / "outputs" / "tables" / "spo_portfolio_weights.csv", parse_dates=["date"])
    return returns, prices, scores, weights


def max_drawdown(return_series: pd.Series) -> float:
    wealth = (1.0 + return_series.fillna(0.0)).cumprod()
    if wealth.empty:
        return 0.0
    drawdown = wealth / wealth.cummax() - 1.0
    return float(drawdown.min())


def annualized_return(return_series: pd.Series, periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    returns = return_series.dropna()
    if returns.empty:
        return 0.0
    wealth = float((1.0 + returns).prod())
    return wealth ** (periods_per_year / len(returns)) - 1.0


def annualized_volatility(return_series: pd.Series) -> float:
    returns = return_series.dropna()
    if len(returns) <= 1:
        return 0.0
    return float(returns.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))


def downside_volatility(return_series: pd.Series) -> float:
    downside = return_series.dropna()
    downside = downside[downside < 0]
    if len(downside) <= 1:
        return 0.0
    return float(downside.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))


def window_return(prices: pd.Series, window: int) -> float:
    values = prices.dropna()
    if len(values) <= window:
        return 0.0
    return float(values.iloc[-1] / values.iloc[-window - 1] - 1.0)


def trailing_slice(returns: pd.DataFrame, date: pd.Timestamp, window: int = 252) -> pd.DataFrame:
    history = returns.loc[returns.index < date, TICKERS].dropna(how="all").tail(window)
    if len(history) < 60:
        history = returns.loc[returns.index < date, TICKERS].dropna(how="all")
    return history.fillna(0.0)


def covariance_for_date(returns: pd.DataFrame, date: pd.Timestamp, window: int = 252) -> np.ndarray:
    history = trailing_slice(returns, date, window)
    cov = history.cov().reindex(index=TICKERS, columns=TICKERS).fillna(0.0).to_numpy()
    return cov * TRADING_DAYS_PER_YEAR + np.eye(len(TICKERS)) * 1e-8


def portfolio_volatility(weights: np.ndarray, cov: np.ndarray) -> float:
    return float(np.sqrt(max(weights @ cov @ weights, 0.0)))


def latest_etf_metrics(
    returns: pd.DataFrame,
    prices: pd.DataFrame,
    scores: pd.DataFrame,
    decision_date: pd.Timestamp,
) -> pd.DataFrame:
    latest_scores = scores[scores["date"] == decision_date].set_index("ticker").reindex(TICKERS)
    rows = []
    for ticker in TICKERS:
        ticker_returns = returns.loc[returns.index <= decision_date, ticker].dropna()
        ticker_prices = prices.loc[prices.index <= decision_date, ticker].dropna()
        hist_ann_return = annualized_return(ticker_returns)
        ann_vol = annualized_volatility(ticker_returns)
        sharpe = hist_ann_return / ann_vol if ann_vol > 0 else 0.0
        row = {
            "decision_date": decision_date.date().isoformat(),
            "ticker": ticker,
            "expected_return_21d_pto": float(latest_scores.loc[ticker, "pto_predicted_return_21d"]),
            "spo_decision_score": float(latest_scores.loc[ticker, "spo_plus_predicted_return_21d"]),
            "spo_predicted_rank": int(latest_scores.loc[ticker, "spo_plus_predicted_rank"]),
            "historical_annual_return": hist_ann_return,
            "annual_volatility": ann_vol,
            "max_drawdown": max_drawdown(ticker_returns),
            "sharpe": sharpe,
            "momentum_21d": window_return(ticker_prices, 21),
            "momentum_60d": window_return(ticker_prices, 60),
            "momentum_120d": window_return(ticker_prices, 120),
            "downside_volatility": downside_volatility(ticker_returns),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def zscore(values: np.ndarray) -> np.ndarray:
    values = values.astype(float)
    std = values.std(ddof=0)
    if std <= 1e-12:
        return np.zeros_like(values)
    return (values - values.mean()) / std


def expected_annual_returns_for_date(
    returns: pd.DataFrame,
    scores: pd.DataFrame,
    date: pd.Timestamp,
) -> np.ndarray:
    score_group = scores[scores["date"] == date].set_index("ticker").reindex(TICKERS)
    history = trailing_slice(returns, date, 252)
    hist_annual = np.array(
        [annualized_return(history[ticker], TRADING_DAYS_PER_YEAR) for ticker in TICKERS],
        dtype=float,
    )
    pto_annual = score_group["pto_predicted_return_21d"].to_numpy(dtype=float) * MONTHS_PER_YEAR
    spo_tilt = zscore(score_group["spo_plus_predicted_return_21d"].to_numpy(dtype=float)) * 0.06
    momentum = np.array(
        [
            float((1.0 + history[ticker].tail(60)).prod() - 1.0)
            if history[ticker].tail(60).notna().any()
            else 0.0
            for ticker in TICKERS
        ],
        dtype=float,
    )
    momentum_annual = momentum * (TRADING_DAYS_PER_YEAR / 60)
    expected = 0.40 * pto_annual + 0.30 * hist_annual + 0.20 * momentum_annual + 0.10 * spo_tilt
    return np.clip(expected, -0.50, 0.80)


def min_volatility_weights(cov: np.ndarray, max_weight: float) -> np.ndarray:
    n = len(TICKERS)
    x0 = np.full(n, 1.0 / n)
    bounds = [(0.0, max_weight) for _ in range(n)]
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

    def objective(w: np.ndarray) -> float:
        return portfolio_volatility(w, cov)

    result = minimize(objective, x0, method="SLSQP", bounds=bounds, constraints=constraints)
    if not result.success:
        weight = np.minimum(x0, max_weight)
        return weight / weight.sum()
    weight = np.clip(result.x, 0, max_weight)
    return weight / weight.sum()


def optimize_profile(
    expected_annual: np.ndarray,
    cov: np.ndarray,
    profile: dict[str, Any],
) -> tuple[np.ndarray, bool, str]:
    n = len(TICKERS)
    max_weight = float(profile["single_etf_weight_max"])
    vol_cap = float(profile["annual_volatility_max"])
    x0 = min_volatility_weights(cov, max_weight)
    bounds = [(0.0, max_weight) for _ in range(n)]
    constraints = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
        {"type": "ineq", "fun": lambda w: vol_cap - portfolio_volatility(w, cov)},
    ]

    def objective(w: np.ndarray) -> float:
        diversification_penalty = 0.005 * float(np.sum(w**2))
        return -float(expected_annual @ w) + diversification_penalty

    result = minimize(
        objective,
        x0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 1000, "ftol": 1e-12},
    )
    if result.success:
        weight = np.clip(result.x, 0.0, max_weight)
        weight = weight / weight.sum()
        if portfolio_volatility(weight, cov) <= vol_cap + 1e-5:
            return weight, True, "risk_constraint_satisfied"

    fallback = x0
    feasible = portfolio_volatility(fallback, cov) <= vol_cap + 1e-5
    return fallback, feasible, "fallback_to_minimum_volatility"


def build_candidate_portfolios(
    returns: pd.DataFrame,
    weights: pd.DataFrame,
    scores: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    prev_by_strategy: dict[str, pd.Series] = {}
    score_lookup = scores.set_index(["date", "ticker"])
    for (date, strategy), group in weights.groupby(["date", "strategy"], sort=True):
        date = pd.Timestamp(date)
        cov = covariance_for_date(returns, date)
        expected = expected_annual_returns_for_date(returns, scores, date)
        current = group.set_index("ticker")["weight"].reindex(TICKERS).fillna(0.0)
        actual = group.set_index("ticker")["actual_future_return_21d"].reindex(TICKERS).fillna(0.0)
        previous = prev_by_strategy.get(strategy, pd.Series(0.0, index=TICKERS))
        turnover = float(np.abs(current - previous).sum())
        prev_by_strategy[strategy] = current
        score_values = [
            float(score_lookup.loc[(date, ticker), "spo_plus_predicted_return_21d"])
            for ticker in TICKERS
        ]
        rows.append(
            {
                "date": date.date().isoformat(),
                "candidate_strategy": strategy,
                "expected_annual_return": float(expected @ current.to_numpy(dtype=float)),
                "expected_annual_volatility": portfolio_volatility(current.to_numpy(dtype=float), cov),
                "actual_future_return_21d": float(current @ actual),
                "spo_weighted_decision_score": float(current @ np.asarray(score_values, dtype=float)),
                "max_single_weight": float(current.max()),
                "dominant_etf": str(current.idxmax()),
                "turnover": turnover,
                "weights_json": json.dumps(
                    {ticker: round(float(current.loc[ticker]), 6) for ticker in TICKERS},
                    ensure_ascii=False,
                ),
            }
        )
    return pd.DataFrame(rows)


def build_ai_weights(
    returns: pd.DataFrame,
    scores: pd.DataFrame,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    rows = []
    decisions = []
    for date in sorted(scores["date"].unique()):
        date = pd.Timestamp(date)
        cov = covariance_for_date(returns, date)
        expected = expected_annual_returns_for_date(returns, scores, date)
        actual = (
            scores[scores["date"] == date]
            .set_index("ticker")
            .reindex(TICKERS)["actual_future_return_21d"]
            .fillna(0.0)
            .to_numpy(dtype=float)
        )
        for profile_name, profile in RISK_PROFILES.items():
            weight, feasible, fallback_reason = optimize_profile(expected, cov, profile)
            for ticker, ticker_weight, ticker_expected, ticker_actual in zip(
                TICKERS,
                weight,
                expected,
                actual,
                strict=False,
            ):
                rows.append(
                    {
                        "date": date,
                        "strategy": f"ai_{profile_name}",
                        "risk_profile": profile_name,
                        "ticker": ticker,
                        "weight": float(ticker_weight),
                        "expected_annual_return_asset": float(ticker_expected),
                        "actual_future_return_21d": float(ticker_actual),
                        "risk_constraint_met": bool(feasible),
                        "fallback_reason": fallback_reason,
                    }
                )
            decisions.append(
                {
                    "date": date.date().isoformat(),
                    "risk_profile": profile_name,
                    "risk_constraint_met": bool(feasible),
                    "fallback_reason": fallback_reason,
                    "expected_annual_return": float(expected @ weight),
                    "expected_annual_volatility": portfolio_volatility(weight, cov),
                    "weights": {ticker: float(value) for ticker, value in zip(TICKERS, weight, strict=False)},
                }
            )
    return pd.DataFrame(rows), decisions


def backtest_ai_weights(
    ai_weights: pd.DataFrame,
    cost_rate: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    metrics = []
    for strategy, strategy_frame in ai_weights.groupby("strategy", sort=True):
        prev = pd.Series(0.0, index=TICKERS)
        for date, group in strategy_frame.groupby("date", sort=True):
            current = group.set_index("ticker")["weight"].reindex(TICKERS).fillna(0.0)
            realized = group.set_index("ticker")["actual_future_return_21d"].reindex(TICKERS).fillna(0.0)
            gross = float(current @ realized)
            turnover = float(np.abs(current - prev).sum())
            net = gross - cost_rate * turnover
            rows.append(
                {
                    "date": pd.Timestamp(date).date().isoformat(),
                    "strategy": strategy,
                    "gross_return": gross,
                    "turnover": turnover,
                    "transaction_cost_rate": cost_rate,
                    "transaction_cost": cost_rate * turnover,
                    "net_return": net,
                }
            )
            prev = current
    returns = pd.DataFrame(rows)
    for strategy, group in returns.groupby("strategy", sort=True):
        for return_type, column, tx_rate in [
            ("gross", "gross_return", 0.0),
            ("net", "net_return", cost_rate),
        ]:
            metrics.append(
                {
                    "strategy": strategy,
                    "return_type": return_type,
                    "transaction_cost_rate": tx_rate,
                    **evaluate_monthly_returns(group[column], group["turnover"]),
                }
            )
    return returns, pd.DataFrame(metrics)


def evaluate_monthly_returns(returns: pd.Series, turnover: pd.Series) -> dict[str, Any]:
    returns = returns.fillna(0.0)
    n = len(returns)
    wealth = float((1.0 + returns).prod()) if n else 1.0
    annual_return = wealth ** (MONTHS_PER_YEAR / n) - 1.0 if n else 0.0
    annual_vol = float(returns.std(ddof=1) * np.sqrt(MONTHS_PER_YEAR)) if n > 1 else 0.0
    downside = returns[returns < 0]
    downside_vol = float(downside.std(ddof=1) * np.sqrt(MONTHS_PER_YEAR)) if len(downside) > 1 else 0.0
    return {
        "months": int(n),
        "total_return": wealth - 1.0,
        "annual_return": annual_return,
        "annual_volatility": annual_vol,
        "sharpe": annual_return / annual_vol if annual_vol > 0 else 0.0,
        "sortino": annual_return / downside_vol if downside_vol > 0 else 0.0,
        "max_drawdown": max_drawdown(returns),
        "win_rate": float((returns > 0).mean()) if n else 0.0,
        "average_turnover": float(turnover.mean()) if len(turnover) else 0.0,
        "final_wealth": wealth,
    }


def portfolio_historical_summary(
    returns: pd.DataFrame,
    decision_date: pd.Timestamp,
    weights: dict[str, float],
) -> dict[str, float]:
    vector = np.asarray([weights[ticker] for ticker in TICKERS], dtype=float)
    history = returns.loc[returns.index <= decision_date, TICKERS].fillna(0.0)
    port = history @ vector
    ann_return = annualized_return(port, TRADING_DAYS_PER_YEAR)
    ann_vol = annualized_volatility(port)
    return {
        "historical_annual_return": ann_return,
        "historical_annual_volatility": ann_vol,
        "historical_sharpe": ann_return / ann_vol if ann_vol > 0 else 0.0,
        "historical_max_drawdown": max_drawdown(port),
    }


def build_ai_json(
    returns: pd.DataFrame,
    scores: pd.DataFrame,
    candidate_portfolios: pd.DataFrame,
    ai_decisions: list[dict[str, Any]],
    decision_date: pd.Timestamp,
) -> dict[str, Any]:
    latest_decisions = [item for item in ai_decisions if item["date"] == decision_date.date().isoformat()]
    latest_candidates = candidate_portfolios[candidate_portfolios["date"] == decision_date.date().isoformat()]
    score_group = scores[scores["date"] == decision_date].set_index("ticker").reindex(TICKERS)
    risk_profiles = []
    for item in latest_decisions:
        profile = RISK_PROFILES[item["risk_profile"]]
        weights = {ticker: round(float(value), 6) for ticker, value in item["weights"].items()}
        historical = portfolio_historical_summary(returns, decision_date, weights)
        overweight = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:3]
        top_spo = (
            score_group["spo_plus_predicted_rank"]
            .sort_values()
            .head(3)
            .index.tolist()
        )
        risk_profiles.append(
            {
                "profile": item["risk_profile"],
                "profile_label": profile["label_zh"],
                "objective": "在风险约束可控前提下最大化预期收益",
                "constraints": {
                    "annual_volatility_max": profile["annual_volatility_max"],
                    "single_etf_weight_max": profile["single_etf_weight_max"],
                    "long_only": True,
                    "weight_sum": 1.0,
                },
                "weights": weights,
                "expected_annual_return": round(float(item["expected_annual_return"]), 6),
                "expected_annual_volatility": round(float(item["expected_annual_volatility"]), 6),
                "expected_sharpe": round(
                    float(item["expected_annual_return"] / item["expected_annual_volatility"])
                    if item["expected_annual_volatility"] > 0
                    else 0.0,
                    6,
                ),
                "historical_risk_check": {
                    key: round(float(value), 6) for key, value in historical.items()
                },
                "constraint_validation": {
                    "weight_sum_ok": abs(sum(weights.values()) - 1.0) <= 1e-5,
                    "long_only_ok": min(weights.values()) >= -1e-8,
                    "single_etf_cap_ok": max(weights.values()) <= profile["single_etf_weight_max"] + 1e-6,
                    "volatility_cap_ok": bool(item["risk_constraint_met"]),
                    "fallback_reason": item["fallback_reason"],
                },
                "risk_note": risk_note(item["risk_profile"], item["risk_constraint_met"]),
                "allocation_reason": allocation_reason(item["risk_profile"], overweight, top_spo),
            }
        )
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "decision_date": decision_date.date().isoformat(),
        "ai_generation_mode": (
            "structured_prompt_decision_with_programmatic_optimizer_fallback; "
            "all weights are validated and risk metrics are recomputed by code"
        ),
        "source_files": [
            "outputs/tables/spo_prediction_scores.csv",
            "outputs/tables/spo_portfolio_weights.csv",
            "outputs/tables/spo_candidate_portfolios.csv",
            "outputs/tables/etf_risk_return_metrics.csv",
        ],
        "prompt_inputs_summary": {
            "spo_candidates": latest_candidates[
                [
                    "candidate_strategy",
                    "expected_annual_return",
                    "expected_annual_volatility",
                    "actual_future_return_21d",
                    "max_single_weight",
                    "dominant_etf",
                ]
            ].to_dict(orient="records"),
            "spo_top_ranked_assets": top_spo,
            "risk_profiles": RISK_PROFILES,
        },
        "risk_profiles": risk_profiles,
        "validation_policy": (
            "如果权重和、非负约束、单 ETF 权重上限或波动率上限校验失败，"
            "系统回退到同一约束下的最低波动组合，并在 JSON 中标注。"
        ),
        "disclaimer": "本项目仅用于课程案例研究，不构成任何投资建议。",
    }


def build_prompt_payload(
    etf_metrics: pd.DataFrame,
    candidate_portfolios: pd.DataFrame,
    ai_json: dict[str, Any],
    decision_date: pd.Timestamp,
) -> dict[str, Any]:
    latest_candidates = candidate_portfolios[
        candidate_portfolios["date"] == decision_date.date().isoformat()
    ].copy()
    latest_candidates["weights"] = latest_candidates["weights_json"].apply(json.loads)
    latest_candidates = latest_candidates.drop(columns=["weights_json"])
    return {
        "generated_for_decision_date": decision_date.date().isoformat(),
        "system_prompt": (
            "你是投资组合优化助手。你必须基于给定的 SPO 候选组合、ETF 单体风险收益指标和"
            "风险档位约束生成 ETF 组合建议。输出只能是 JSON，不能给出无法复算的主观建议。"
        ),
        "user_prompt_template": (
            "请为 SPY、QQQ、TLT、GLD、VNQ、DBC 生成低风险、中风险、高风险三档 ETF 组合。"
            "低风险年化波动率不超过 10%、单 ETF 权重不超过 35%；中风险年化波动率不超过 15%、"
            "单 ETF 权重不超过 45%；高风险年化波动率不超过 22%、单 ETF 权重不超过 60%。"
            "每个组合必须给出权重、预期收益、预期波动、最大回撤风险说明和配置理由。"
            "如果风险约束不可完全满足，请使用同档位最低波动组合并说明。"
        ),
        "structured_inputs": {
            "spo_candidate_portfolios": latest_candidates.to_dict(orient="records"),
            "etf_risk_return_metrics": etf_metrics.to_dict(orient="records"),
            "risk_profiles": RISK_PROFILES,
        },
        "required_output_schema": {
            "decision_date": "YYYY-MM-DD",
            "risk_profiles": [
                {
                    "profile": "low_risk | medium_risk | high_risk",
                    "profile_label": "低风险 | 中风险 | 高风险",
                    "weights": {ticker: "float, non-negative" for ticker in TICKERS},
                    "expected_annual_return": "float",
                    "expected_annual_volatility": "float",
                    "expected_sharpe": "float",
                    "historical_risk_check": {
                        "historical_annual_return": "float",
                        "historical_annual_volatility": "float",
                        "historical_sharpe": "float",
                        "historical_max_drawdown": "float",
                    },
                    "constraint_validation": {
                        "weight_sum_ok": "boolean",
                        "long_only_ok": "boolean",
                        "single_etf_cap_ok": "boolean",
                        "volatility_cap_ok": "boolean",
                        "fallback_reason": "string",
                    },
                    "risk_note": "string",
                    "allocation_reason": "string",
                }
            ],
            "disclaimer": "本项目仅用于课程案例研究，不构成任何投资建议。",
        },
        "reference_validated_output": ai_json,
        "validation_policy": (
            "模型输出后必须由程序校验权重和、非负约束、单 ETF 上限和波动率约束；"
            "校验失败时重新提示或回退到程序化优化器结果。"
        ),
    }


def risk_note(profile_name: str, feasible: bool) -> str:
    if not feasible:
        return "该档位风险约束不可完全满足，已使用同一权重上限下的最低波动组合。"
    notes = {
        "low_risk": "组合以降低波动和回撤为主，收益目标服从风险约束。",
        "medium_risk": "组合在收益资产和防御资产之间折中，追求风险调整后收益。",
        "high_risk": "组合允许更高权益暴露，以换取更高预期收益和更大净值波动。",
    }
    return notes[profile_name]


def allocation_reason(profile_name: str, overweight: list[tuple[str, float]], top_spo: list[str]) -> str:
    top_weights = "、".join(f"{ticker} {weight:.1%}" for ticker, weight in overweight if weight > 1e-6)
    top_spo_text = "、".join(top_spo)
    profile_text = RISK_PROFILES[profile_name]["risk_preference"]
    return (
        f"{profile_text} 当前 SPO 排名前三资产为 {top_spo_text}；"
        f"最终权重集中在 {top_weights}，并通过程序化约束校验。"
    )


def update_backtest_metrics(root: Path, ai_metrics: pd.DataFrame) -> pd.DataFrame:
    metrics_path = root / "outputs" / "tables" / "portfolio_backtest_metrics.csv"
    existing = pd.read_csv(metrics_path)
    existing = existing[~existing["strategy"].astype(str).str.startswith("ai_")]
    combined = pd.concat([existing, ai_metrics], ignore_index=True)
    combined = combined.sort_values(["strategy", "return_type"]).reset_index(drop=True)
    combined.to_csv(metrics_path, index=False)
    return combined


def validate_ai_outputs(
    ai_weights: pd.DataFrame,
    ai_json: dict[str, Any],
    metrics: pd.DataFrame,
) -> dict[str, Any]:
    weight_checks = []
    for (date, strategy), group in ai_weights.groupby(["date", "strategy"]):
        risk_profile = strategy.replace("ai_", "")
        max_weight = RISK_PROFILES[risk_profile]["single_etf_weight_max"]
        weight_checks.append(
            {
                "date": pd.Timestamp(date).date().isoformat(),
                "strategy": strategy,
                "sum_ok": bool(abs(group["weight"].sum() - 1.0) <= 1e-6),
                "long_only_ok": bool(group["weight"].min() >= -1e-8),
                "single_weight_cap_ok": bool(group["weight"].max() <= max_weight + 1e-8),
                "volatility_cap_ok": bool(group["risk_constraint_met"].all()),
                "fallback_reason": str(group["fallback_reason"].iloc[0]),
            }
        )
    numeric_cols = [
        "total_return",
        "annual_return",
        "annual_volatility",
        "sharpe",
        "sortino",
        "max_drawdown",
        "win_rate",
        "average_turnover",
    ]
    return {
        "ai_weight_checks_ok": bool(
            all(
                x["sum_ok"] and x["long_only_ok"] and x["single_weight_cap_ok"]
                for x in weight_checks
            )
        ),
        "ai_risk_constraints_all_met": bool(all(x["volatility_cap_ok"] for x in weight_checks)),
        "ai_risk_constraints_or_fallbacks_ok": bool(
            all(x["volatility_cap_ok"] or x["fallback_reason"] == "fallback_to_minimum_volatility" for x in weight_checks)
        ),
        "risk_constraint_fallback_count": int(sum(not x["volatility_cap_ok"] for x in weight_checks)),
        "ai_json_profiles": [profile["profile"] for profile in ai_json["risk_profiles"]],
        "metrics_finite_ok": bool(np.isfinite(metrics[numeric_cols].to_numpy(dtype=float)).all()),
        "weight_checks": weight_checks,
    }


def main() -> None:
    args = parse_args()
    root = project_root()
    output_dir = root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    returns, prices, scores, weights = read_inputs(root)
    decision_date = pd.Timestamp(scores["date"].max())

    risk_metrics = latest_etf_metrics(returns, prices, scores, decision_date)
    candidate_portfolios = build_candidate_portfolios(returns, weights, scores)
    ai_weights, ai_decisions = build_ai_weights(returns, scores)
    ai_returns, ai_metrics = backtest_ai_weights(ai_weights, args.cost_rate)
    all_metrics = update_backtest_metrics(root, ai_metrics)
    ai_json = build_ai_json(returns, scores, candidate_portfolios, ai_decisions, decision_date)
    prompt_payload = build_prompt_payload(risk_metrics, candidate_portfolios, ai_json, decision_date)
    validation = validate_ai_outputs(ai_weights, ai_json, all_metrics)

    artifacts = {
        "etf_risk_return_metrics": "outputs/tables/etf_risk_return_metrics.csv",
        "spo_candidate_portfolios": "outputs/tables/spo_candidate_portfolios.csv",
        "ai_prompt_payload": "outputs/tables/ai_prompt_payload.json",
        "ai_risk_profile_weights": "outputs/tables/ai_risk_profile_weights.csv",
        "ai_risk_profile_backtest_returns": "outputs/tables/ai_risk_profile_backtest_returns.csv",
        "ai_risk_profile_portfolios": "outputs/tables/ai_risk_profile_portfolios.json",
        "ai_risk_profile_validation": "outputs/tables/ai_risk_profile_validation.json",
        "portfolio_backtest_metrics": "outputs/tables/portfolio_backtest_metrics.csv",
    }

    risk_metrics.to_csv(root / artifacts["etf_risk_return_metrics"], index=False)
    candidate_portfolios.to_csv(root / artifacts["spo_candidate_portfolios"], index=False)
    ai_weights.to_csv(root / artifacts["ai_risk_profile_weights"], index=False)
    ai_returns.to_csv(root / artifacts["ai_risk_profile_backtest_returns"], index=False)
    (root / artifacts["ai_prompt_payload"]).write_text(
        json.dumps(prompt_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (root / artifacts["ai_risk_profile_portfolios"]).write_text(
        json.dumps(ai_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (root / artifacts["ai_risk_profile_validation"]).write_text(
        json.dumps(
            {
                "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "artifacts": artifacts,
                "validation": validation,
                "disclaimer": "本项目仅用于课程案例研究，不构成任何投资建议。",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "decision_date": decision_date.date().isoformat(),
                "artifacts": artifacts,
                "validation": validation,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
