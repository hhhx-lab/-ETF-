from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from scipy.optimize import minimize
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from pyepo import EPO
from pyepo.func import SPOPlus
from pyepo.model.opt import optModel


TICKERS = ["SPY", "QQQ", "TLT", "GLD", "VNQ", "DBC"]
TARGET_COL = "future_return_21d"
TRADING_DAYS_PER_YEAR = 252
MONTHS_PER_YEAR = 12
DEFAULT_COST_RATE = 0.005
DEFAULT_EPOCHS = 240


@dataclass(frozen=True)
class StrategyConfig:
    name: str
    description: str
    transaction_fee_gamma: float
    turnover_penalty_lambda: float
    l2_weight_regularization: float


STRATEGIES = [
    StrategyConfig(
        name="spo_plus",
        description="PyEPO SPO+ loss with MaxReturn optimizer",
        transaction_fee_gamma=0.0,
        turnover_penalty_lambda=0.0,
        l2_weight_regularization=0.0,
    ),
    StrategyConfig(
        name="spo_plus_fee",
        description="PyEPO SPO+ loss with proportional transaction fee in portfolio construction",
        transaction_fee_gamma=DEFAULT_COST_RATE,
        turnover_penalty_lambda=0.0,
        l2_weight_regularization=0.0,
    ),
    StrategyConfig(
        name="spo_plus_turnover_l2",
        description="PyEPO SPO+ loss with turnover and L2 weight regularization",
        transaction_fee_gamma=DEFAULT_COST_RATE,
        turnover_penalty_lambda=0.42,
        l2_weight_regularization=0.005,
    ),
]


class MaxReturnOptModel(optModel):
    """PyEPO optModel for long-only MaxReturn over ETF weights.

    The paper's baseline SPO formulation starts from MaxReturn. For this linear
    problem, the optimizer can be solved exactly without a commercial solver:
    allocate all weight to the largest objective coefficient.
    """

    modelSense = EPO.MAXIMIZE

    def __init__(self, num_assets: int):
        self._objective = np.zeros(num_assets, dtype=np.float32)
        self._num_assets = num_assets
        super().__init__()

    def _getModel(self) -> tuple[None, list[int]]:
        return None, list(range(self._num_assets))

    @property
    def num_cost(self) -> int:
        return self._num_assets

    def setObj(self, c: np.ndarray | torch.Tensor | list) -> None:
        arr = np.asarray(c, dtype=np.float32)
        if arr.shape[0] != self._num_assets:
            raise ValueError("Objective length does not match number of assets.")
        self._objective = arr

    def solve(self) -> tuple[np.ndarray, float]:
        sol = np.zeros(self._num_assets, dtype=np.float32)
        best_idx = int(np.argmax(self._objective))
        sol[best_idx] = 1.0
        obj = float(self._objective[best_idx])
        return sol, obj

    def copy(self) -> "MaxReturnOptModel":
        new_model = MaxReturnOptModel(self._num_assets)
        new_model._objective = self._objective.copy()
        return new_model

    def addConstr(self, coefs: np.ndarray | torch.Tensor | list, rhs: float) -> "MaxReturnOptModel":
        raise NotImplementedError("Closed-form MaxReturn model does not support extra constraints.")

    def relax(self) -> "MaxReturnOptModel":
        return self.copy()


class LinearReturnModel(nn.Module):
    def __init__(self, num_features: int, num_assets: int):
        super().__init__()
        self.linear = nn.Linear(num_features, num_assets)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.linear(x)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reproduce the 2026 SPO portfolio paper on the local ETF dataset."
    )
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output-dir",
        default="outputs/tables",
        help="Relative directory for reproduction artifacts.",
    )
    return parser.parse_args()


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)


def load_feature_columns(root: Path) -> list[str]:
    meta = json.loads(
        (root / "outputs" / "tables" / "feature_dataset_quality.json").read_text(
            encoding="utf-8"
        )
    )
    return meta["quality_summary"]["feature_names"]


def load_data(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    feature_cols = load_feature_columns(root)
    modeling = pd.read_csv(
        root / "data" / "processed" / "modeling_dataset.csv",
        parse_dates=["date"],
    )
    monthly = (
        modeling.sort_values("date")
        .groupby([modeling["date"].dt.to_period("M"), "ticker"])
        .tail(1)
        .sort_values(["date", "ticker"])
        .reset_index(drop=True)
    )
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
    return monthly, returns, prices, feature_cols


def panel_to_monthly_tensors(
    frame: pd.DataFrame,
    feature_cols: list[str],
    scaler: StandardScaler | None = None,
    fit_scaler: bool = False,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, StandardScaler]:
    dates = sorted(frame["date"].unique())
    rows = []
    x_list = []
    y_list = []
    for date in dates:
        group = frame[frame["date"] == date].set_index("ticker").reindex(TICKERS)
        if group[feature_cols + [TARGET_COL]].isna().any().any():
            continue
        rows.append({"date": pd.Timestamp(date), "split": group["split"].iloc[0]})
        x_list.append(group[feature_cols].to_numpy(dtype=np.float32).reshape(-1))
        y_list.append(group[TARGET_COL].to_numpy(dtype=np.float32))

    index = pd.DataFrame(rows)
    x = np.asarray(x_list, dtype=np.float32)
    y = np.asarray(y_list, dtype=np.float32)

    if scaler is None:
        scaler = StandardScaler()
    if fit_scaler:
        x = scaler.fit_transform(x).astype(np.float32)
    else:
        x = scaler.transform(x).astype(np.float32)
    return index, x, y, scaler


def true_solutions(costs: np.ndarray, optmodel: MaxReturnOptModel) -> tuple[np.ndarray, np.ndarray]:
    sols = []
    objs = []
    for c in costs:
        optmodel.setObj(c)
        sol, obj = optmodel.solve()
        sols.append(sol)
        objs.append([obj])
    return np.asarray(sols, dtype=np.float32), np.asarray(objs, dtype=np.float32)


def train_pto_ridge(
    panel: pd.DataFrame,
    feature_cols: list[str],
    monthly_index: pd.DataFrame,
    x: np.ndarray,
) -> np.ndarray:
    models: dict[str, Pipeline] = {}
    for ticker in TICKERS:
        ticker_train = panel[
            (panel["split"] == "train") & (panel["ticker"] == ticker)
        ]
        model = Pipeline([("scaler", StandardScaler()), ("ridge", Ridge(alpha=1.0))])
        model.fit(ticker_train[feature_cols], ticker_train[TARGET_COL])
        models[ticker] = model

    pred_rows = []
    for _, row in monthly_index.iterrows():
        date = row["date"]
        group = panel[panel["date"] == date].set_index("ticker").reindex(TICKERS)
        pred_rows.append(
            [
                float(models[ticker].predict(group.loc[[ticker], feature_cols])[0])
                for ticker in TICKERS
            ]
        )
    return np.asarray(pred_rows, dtype=np.float32)


def train_spo_plus(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_valid: np.ndarray,
    y_valid: np.ndarray,
    args: argparse.Namespace,
) -> tuple[LinearReturnModel, dict[str, list[float]]]:
    optmodel = MaxReturnOptModel(len(TICKERS))
    true_sol, true_obj = true_solutions(y_train, optmodel)

    model = LinearReturnModel(x_train.shape[1], len(TICKERS))
    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)
    mse = nn.MSELoss()
    spo_loss = SPOPlus(optmodel, processes=1)

    dataset = TensorDataset(
        torch.tensor(x_train, dtype=torch.float32),
        torch.tensor(y_train, dtype=torch.float32),
        torch.tensor(true_sol, dtype=torch.float32),
        torch.tensor(true_obj, dtype=torch.float32),
    )
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True)
    history = {"epoch": [], "train_loss": [], "valid_mse": [], "valid_rank_ic": []}

    for epoch in range(1, args.epochs + 1):
        model.train()
        losses = []
        for xb, yb, solb, objb in loader:
            optimizer.zero_grad()
            pred = model(xb)
            loss = spo_loss(pred, yb, solb, objb) + 0.05 * mse(pred, yb)
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach()))

        if epoch == 1 or epoch % 20 == 0 or epoch == args.epochs:
            model.eval()
            with torch.no_grad():
                valid_pred = model(torch.tensor(x_valid, dtype=torch.float32)).numpy()
            history["epoch"].append(epoch)
            history["train_loss"].append(float(np.mean(losses)))
            history["valid_mse"].append(float(mean_squared_error(y_valid.reshape(-1), valid_pred.reshape(-1))))
            history["valid_rank_ic"].append(monthly_rank_ic(y_valid, valid_pred))
    return model, history


def monthly_rank_ic(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    values = []
    for true_row, pred_row in zip(y_true, y_pred, strict=False):
        if np.unique(true_row).size <= 1 or np.unique(pred_row).size <= 1:
            continue
        values.append(pd.Series(pred_row).corr(pd.Series(true_row), method="spearman"))
    return float(np.nanmean(values)) if values else 0.0


def prediction_metrics(y_true: np.ndarray, y_pred: np.ndarray, model_name: str, split: str) -> dict[str, Any]:
    return {
        "model_name": model_name,
        "split": split,
        "rmse": float(np.sqrt(mean_squared_error(y_true.reshape(-1), y_pred.reshape(-1)))),
        "mae": float(mean_absolute_error(y_true.reshape(-1), y_pred.reshape(-1))),
        "r2": float(r2_score(y_true.reshape(-1), y_pred.reshape(-1))),
        "rank_ic": monthly_rank_ic(y_true, y_pred),
    }


def realized_scores(index: pd.DataFrame, y_true: np.ndarray, predictions: dict[str, np.ndarray]) -> pd.DataFrame:
    rows = []
    for i, row in index.iterrows():
        for j, ticker in enumerate(TICKERS):
            out = {
                "date": row["date"],
                "split": row["split"],
                "ticker": ticker,
                "actual_future_return_21d": float(y_true[i, j]),
                "actual_rank": int(pd.Series(y_true[i]).rank(ascending=False, method="first").iloc[j]),
            }
            for name, pred in predictions.items():
                ranks = pd.Series(pred[i]).rank(ascending=False, method="first")
                out[f"{name}_predicted_return_21d"] = float(pred[i, j])
                out[f"{name}_predicted_rank"] = int(ranks.iloc[j])
            rows.append(out)
    return pd.DataFrame(rows)


def long_only_optimize(
    expected: np.ndarray,
    prev_weight: np.ndarray,
    config: StrategyConfig,
) -> np.ndarray:
    n = len(expected)
    if config.transaction_fee_gamma == 0 and config.turnover_penalty_lambda == 0 and config.l2_weight_regularization == 0:
        weight = np.zeros(n)
        weight[int(np.argmax(expected))] = 1.0
        return weight

    x0 = prev_weight.copy() if prev_weight.sum() > 0 else np.full(n, 1.0 / n)
    bounds = [(0.0, 1.0) for _ in range(n)]
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

    def objective(w: np.ndarray) -> float:
        gross = float(expected @ w)
        turnover = float(np.abs(w - prev_weight).sum())
        l2 = float(np.sum(w**2))
        return -gross + config.transaction_fee_gamma * turnover + config.turnover_penalty_lambda * turnover + config.l2_weight_regularization * l2

    result = minimize(
        objective,
        x0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 500, "ftol": 1e-10},
    )
    if not result.success:
        return np.full(n, 1.0 / n)
    weight = np.clip(result.x, 0, None)
    return weight / weight.sum()


def markowitz_weights(expected: np.ndarray, returns_history: pd.DataFrame) -> np.ndarray:
    cov = returns_history.cov().reindex(index=TICKERS, columns=TICKERS).fillna(0.0).to_numpy()
    cov = cov * TRADING_DAYS_PER_YEAR
    cov += np.eye(len(TICKERS)) * 1e-8
    annual_expected = expected * MONTHS_PER_YEAR
    n = len(TICKERS)
    x0 = np.full(n, 1.0 / n)
    bounds = [(0.0, 1.0) for _ in range(n)]
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

    def objective(w: np.ndarray) -> float:
        ret = float(annual_expected @ w)
        vol = float(np.sqrt(max(w @ cov @ w, 0.0)))
        return -(ret / vol) if vol > 0 else 0.0

    result = minimize(objective, x0, method="SLSQP", bounds=bounds, constraints=constraints)
    if not result.success:
        return x0
    weight = np.clip(result.x, 0, None)
    return weight / weight.sum()


def trailing_history(returns: pd.DataFrame, date: pd.Timestamp, window: int = 60) -> pd.DataFrame:
    history = returns.loc[returns.index < date, TICKERS].dropna(how="all").tail(window)
    if history.shape[0] < 20:
        history = returns.loc[returns.index < date, TICKERS].dropna(how="all")
    return history.fillna(0.0)


def build_strategy_weights(
    index: pd.DataFrame,
    y_true: np.ndarray,
    pto_pred: np.ndarray,
    spo_pred: np.ndarray,
    returns: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    prev: dict[str, np.ndarray] = {}
    strategy_predictions = {
        "pto_markowitz": pto_pred,
        "spo_plus": spo_pred,
        "spo_plus_fee": spo_pred,
        "spo_plus_turnover_l2": spo_pred,
    }
    strategy_configs = {config.name: config for config in STRATEGIES}

    for i, row in index.reset_index(drop=True).iterrows():
        date = pd.Timestamp(row["date"])
        history = trailing_history(returns, date)
        for strategy, pred in strategy_predictions.items():
            previous = prev.get(strategy, np.zeros(len(TICKERS)))
            if strategy == "pto_markowitz":
                weight = markowitz_weights(pred[i], history)
                config_note = "PtO Ridge prediction with Markowitz max-Sharpe optimization"
            else:
                weight = long_only_optimize(pred[i], previous, strategy_configs[strategy])
                config_note = strategy_configs[strategy].description
            prev[strategy] = weight
            for ticker, ticker_weight in zip(TICKERS, weight, strict=False):
                rows.append(
                    {
                        "date": date,
                        "strategy": strategy,
                        "ticker": ticker,
                        "weight": float(ticker_weight),
                        "predicted_return_21d": float(pred[i, TICKERS.index(ticker)]),
                        "actual_future_return_21d": float(y_true[i, TICKERS.index(ticker)]),
                        "strategy_note": config_note,
                    }
                )

        for benchmark in ["equal_weight_6etf", "spy_buy_hold"]:
            weight = np.full(len(TICKERS), 1.0 / len(TICKERS))
            if benchmark == "spy_buy_hold":
                weight = np.zeros(len(TICKERS))
                weight[TICKERS.index("SPY")] = 1.0
            for ticker, ticker_weight in zip(TICKERS, weight, strict=False):
                rows.append(
                    {
                        "date": date,
                        "strategy": benchmark,
                        "ticker": ticker,
                        "weight": float(ticker_weight),
                        "predicted_return_21d": np.nan,
                        "actual_future_return_21d": float(y_true[i, TICKERS.index(ticker)]),
                        "strategy_note": "benchmark",
                    }
                )
    return pd.DataFrame(rows)


def max_drawdown(return_series: pd.Series) -> float:
    wealth = (1.0 + return_series.fillna(0.0)).cumprod()
    if wealth.empty:
        return 0.0
    drawdown = wealth / wealth.cummax() - 1.0
    return float(drawdown.min())


def evaluate_returns(returns: pd.Series, turnover: pd.Series) -> dict[str, Any]:
    returns = returns.fillna(0.0)
    n = len(returns)
    wealth = float((1.0 + returns).prod()) if n else 1.0
    annual_return = wealth ** (MONTHS_PER_YEAR / n) - 1.0 if n else 0.0
    annual_vol = float(returns.std(ddof=1) * np.sqrt(MONTHS_PER_YEAR)) if n > 1 else 0.0
    sharpe = annual_return / annual_vol if annual_vol > 0 else 0.0
    downside = returns[returns < 0]
    downside_vol = float(downside.std(ddof=1) * np.sqrt(MONTHS_PER_YEAR)) if len(downside) > 1 else 0.0
    sortino = annual_return / downside_vol if downside_vol > 0 else 0.0
    return {
        "months": int(n),
        "total_return": wealth - 1.0,
        "annual_return": annual_return,
        "annual_volatility": annual_vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_drawdown(returns),
        "win_rate": float((returns > 0).mean()) if n else 0.0,
        "average_turnover": float(turnover.mean()) if len(turnover) else 0.0,
        "final_wealth": wealth,
    }


def backtest(weights: pd.DataFrame, cost_rate: float = DEFAULT_COST_RATE) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    metrics = []
    for strategy, strategy_frame in weights.groupby("strategy", sort=True):
        prev = pd.Series(0.0, index=TICKERS)
        for date, group in strategy_frame.groupby("date", sort=True):
            current = group.set_index("ticker")["weight"].reindex(TICKERS).fillna(0.0)
            realized = group.set_index("ticker")["actual_future_return_21d"].reindex(TICKERS).fillna(0.0)
            gross = float((current * realized).sum())
            turnover = float(np.abs(current - prev).sum())
            net = gross - cost_rate * turnover
            rows.append(
                {
                    "date": pd.Timestamp(date),
                    "strategy": strategy,
                    "gross_return": gross,
                    "turnover": turnover,
                    "transaction_cost_rate": cost_rate,
                    "transaction_cost": cost_rate * turnover,
                    "net_return": net,
                }
            )
            prev = current
    returns = pd.DataFrame(rows).sort_values(["strategy", "date"])
    for strategy, group in returns.groupby("strategy", sort=True):
        metrics.append(
            {
                "strategy": strategy,
                "return_type": "gross",
                "transaction_cost_rate": 0.0,
                **evaluate_returns(group["gross_return"], group["turnover"]),
            }
        )
        metrics.append(
            {
                "strategy": strategy,
                "return_type": "net",
                "transaction_cost_rate": cost_rate,
                **evaluate_returns(group["net_return"], group["turnover"]),
            }
        )
    return returns, pd.DataFrame(metrics).sort_values(["strategy", "return_type"])


def validate_outputs(scores: pd.DataFrame, weights: pd.DataFrame, metrics: pd.DataFrame) -> dict[str, Any]:
    dates = scores["date"].nunique()
    prediction_ok = len(scores) == dates * len(TICKERS)
    weight_checks = []
    for (date, strategy), group in weights.groupby(["date", "strategy"]):
        weight_checks.append(
            {
                "date": pd.Timestamp(date).strftime("%Y-%m-%d"),
                "strategy": strategy,
                "sum_ok": bool(abs(group["weight"].sum() - 1.0) <= 1e-6),
                "long_only_ok": bool(group["weight"].min() >= -1e-8),
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
        "prediction_rows_ok": bool(prediction_ok),
        "expected_prediction_rows": int(dates * len(TICKERS)),
        "actual_prediction_rows": int(len(scores)),
        "weight_checks_ok": bool(all(x["sum_ok"] and x["long_only_ok"] for x in weight_checks)),
        "metrics_finite_ok": bool(np.isfinite(metrics[numeric_cols].to_numpy(dtype=float)).all()),
        "weight_checks": weight_checks,
    }


def main() -> None:
    args = parse_args()
    set_seed(args.seed)
    root = project_root()
    output_dir = root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    monthly_panel, returns, _, feature_cols = load_data(root)
    train_panel = monthly_panel[monthly_panel["split"] == "train"]
    valid_panel = monthly_panel[monthly_panel["split"] == "valid"]
    test_panel = monthly_panel[monthly_panel["split"] == "test"]

    train_index, x_train, y_train, scaler = panel_to_monthly_tensors(
        train_panel,
        feature_cols,
        fit_scaler=True,
    )
    test_index, x_test, y_test, _ = panel_to_monthly_tensors(
        test_panel,
        feature_cols,
        scaler=scaler,
        fit_scaler=False,
    )
    valid_index, x_valid, y_valid, _ = panel_to_monthly_tensors(
        valid_panel,
        feature_cols,
        scaler=scaler,
        fit_scaler=False,
    )

    pto_pred_test = train_pto_ridge(monthly_panel, feature_cols, test_index, x_test)
    pto_pred_valid = train_pto_ridge(monthly_panel, feature_cols, valid_index, x_valid)

    spo_model, training_history = train_spo_plus(x_train, y_train, x_valid, y_valid, args)
    spo_model.eval()
    with torch.no_grad():
        spo_pred_test = spo_model(torch.tensor(x_test, dtype=torch.float32)).numpy()
        spo_pred_valid = spo_model(torch.tensor(x_valid, dtype=torch.float32)).numpy()

    model_metrics = pd.DataFrame(
        [
            prediction_metrics(y_valid, pto_pred_valid, "pto_ridge_markowitz", "valid"),
            prediction_metrics(y_valid, spo_pred_valid, "pyepo_spo_plus_linear", "valid"),
            prediction_metrics(y_test, pto_pred_test, "pto_ridge_markowitz", "test"),
            prediction_metrics(y_test, spo_pred_test, "pyepo_spo_plus_linear", "test"),
        ]
    )
    scores = realized_scores(
        test_index,
        y_test,
        {
            "pto": pto_pred_test,
            "spo_plus": spo_pred_test,
        },
    )
    weights = build_strategy_weights(test_index, y_test, pto_pred_test, spo_pred_test, returns)
    monthly_returns, backtest_metrics = backtest(weights)
    validation = validate_outputs(scores, weights, backtest_metrics)

    artifacts = {
        "paper_source_manifest": "external/paper_2601_04062_source_manifest.json",
        "downloaded_codebase": "external/PyEPO",
        "spo_prediction_scores": "outputs/tables/spo_prediction_scores.csv",
        "spo_portfolio_weights": "outputs/tables/spo_portfolio_weights.csv",
        "spo_backtest_returns": "outputs/tables/spo_backtest_returns.csv",
        "portfolio_backtest_metrics": "outputs/tables/portfolio_backtest_metrics.csv",
        "spo_model_metrics": "outputs/tables/spo_model_metrics.csv",
        "spo_training_history": "outputs/tables/spo_training_history.csv",
        "spo_reproduction_metadata": "outputs/tables/spo_reproduction_metadata.json",
    }

    scores.to_csv(root / artifacts["spo_prediction_scores"], index=False)
    weights.to_csv(root / artifacts["spo_portfolio_weights"], index=False)
    monthly_returns.to_csv(root / artifacts["spo_backtest_returns"], index=False)
    backtest_metrics.to_csv(root / artifacts["portfolio_backtest_metrics"], index=False)
    model_metrics.to_csv(root / artifacts["spo_model_metrics"], index=False)
    pd.DataFrame(training_history).to_csv(root / artifacts["spo_training_history"], index=False)

    paper_manifest = {
        "paper": "Smart Predict--then--Optimize Paradigm for Portfolio Optimization in Real Markets",
        "arxiv_id": "2601.04062v3",
        "authors": ["Wang Yi", "Takashi Hasuike"],
        "paper_source_downloaded_from": "https://arxiv.org/e-print/2601.04062",
        "paper_source_contents": [
            "00README.json",
            "main.tex",
            "ref.bib",
            "figures/*.pdf",
            "figures/*.png",
        ],
        "official_experiment_code_status": (
            "No Python experiment code or GitHub repository link was included in the arXiv source package. "
            "The paper states that PyEPO is used to implement SPO loss, so this reproduction uses the official PyEPO codebase."
        ),
        "pyepo_source": "https://github.com/khalil-research/PyEPO",
    }
    (root / "external" / "paper_2601_04062_source_manifest.json").write_text(
        json.dumps(paper_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "conda_environment": "etf-spo",
        "command": "conda run -n etf-spo python src/reproduce_spo_paper.py",
        "paper": paper_manifest,
        "implementation": {
            "codebase": "PyEPO installed editable from external/PyEPO/pkg",
            "optimizer": "MaxReturn long-only LP solved exactly by custom PyEPO optModel",
            "loss": "PyEPO SPOPlus",
            "predictor": "linear PyTorch model",
            "baselines": [
                "Ridge predict-then-Markowitz",
                "6 ETF equal weight",
                "SPY buy-and-hold",
            ],
            "transaction_cost_rate": DEFAULT_COST_RATE,
            "monthly_rebalancing": True,
        },
        "data": {
            "tickers": TICKERS,
            "feature_count": len(feature_cols),
            "train_months": int(len(train_index)),
            "valid_months": int(len(valid_index)),
            "train_valid_months": int(len(train_index) + len(valid_index)),
            "test_months": int(len(test_index)),
            "test_start": str(test_index["date"].min().date()),
            "test_end": str(test_index["date"].max().date()),
            "scaler_fit_rule": "StandardScaler is fit on train split only; valid and test are transformed.",
            "model_fit_rule": "PtO Ridge and SPO+ are fit on train split only; valid is used for diagnostics.",
        },
        "validation": validation,
        "artifacts": artifacts,
        "disclaimer": "本项目仅用于课程案例研究，不构成任何投资建议。",
    }
    (root / artifacts["spo_reproduction_metadata"]).write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
