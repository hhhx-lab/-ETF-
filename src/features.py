from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_HORIZON_DAYS = 21
TICKERS = ["SPY", "QQQ", "TLT", "GLD", "VNQ", "DBC"]
TRAIN_END = "2022-12-31"
VALID_END = "2023-12-31"


@dataclass
class FeatureConfig:
    horizon_days: int
    tickers: list[str]
    generated_at_utc: str
    split_rule: str
    feature_lag_rule: str
    label_rule: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build daily and monthly modeling datasets for role B."
    )
    parser.add_argument(
        "--horizon-days",
        type=int,
        default=DEFAULT_HORIZON_DAYS,
        help="Forward trading-day horizon for labels.",
    )
    return parser.parse_args()


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_prices(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    adj = pd.read_csv(
        root / "data" / "processed" / "prices_adj_close.csv",
        index_col=0,
        parse_dates=True,
    )
    returns = pd.read_csv(
        root / "data" / "processed" / "daily_returns.csv",
        index_col=0,
        parse_dates=True,
    )
    raw = pd.read_csv(
        root / "data" / "raw" / "etf_prices_raw.csv",
        header=[0, 1],
        index_col=0,
        parse_dates=True,
    )
    adj.index.name = "date"
    returns.index.name = "date"
    raw.index.name = "date"
    return adj[TICKERS], returns[TICKERS], raw


def field_from_raw(raw: pd.DataFrame, field: str) -> pd.DataFrame:
    if field not in raw.columns.get_level_values(0):
        raise KeyError(f"Missing raw field: {field}")
    frame = raw[field].copy().reindex(columns=TICKERS)
    frame.index.name = "date"
    return frame


def rolling_max_drawdown(returns: pd.DataFrame, window: int) -> pd.DataFrame:
    def calc(values: np.ndarray) -> float:
        wealth = np.cumprod(1 + values)
        peak = np.maximum.accumulate(wealth)
        drawdown = wealth / peak - 1
        return float(np.min(drawdown))

    return returns.rolling(window=window, min_periods=window).apply(calc, raw=True)


def zscore_cross_section(frame: pd.DataFrame) -> pd.DataFrame:
    mean = frame.mean(axis=1)
    std = frame.std(axis=1).replace(0, np.nan)
    return frame.sub(mean, axis=0).div(std, axis=0)


def rank_pct(frame: pd.DataFrame, ascending: bool) -> pd.DataFrame:
    return frame.rank(axis=1, pct=True, ascending=ascending)


def build_wide_features(
    adj: pd.DataFrame,
    returns: pd.DataFrame,
    raw: pd.DataFrame,
    horizon_days: int,
) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    volume = field_from_raw(raw, "Volume")

    ret_5d = adj.pct_change(5)
    ret_20d = adj.pct_change(20)
    ret_60d = adj.pct_change(60)
    ret_120d = adj.pct_change(120)

    vol_20d = returns.rolling(20, min_periods=20).std()
    vol_60d = returns.rolling(60, min_periods=60).std()
    downside_vol_60d = returns.mask(returns > 0, 0).rolling(60, min_periods=60).std()

    drawdown_20d = rolling_max_drawdown(returns.fillna(0), 20)
    drawdown_60d = rolling_max_drawdown(returns.fillna(0), 60)

    ma_20 = adj.rolling(20, min_periods=20).mean()
    ma_60 = adj.rolling(60, min_periods=60).mean()
    ma_120 = adj.rolling(120, min_periods=120).mean()
    ma_ratio_20_60 = ma_20 / ma_60 - 1
    ma_ratio_60_120 = ma_60 / ma_120 - 1

    volume_ma_20 = volume.rolling(20, min_periods=20).mean()
    volume_ma_60 = volume.rolling(60, min_periods=60).mean()
    volume_chg_20d = volume_ma_20 / volume_ma_60 - 1

    risk_adj_ret_20d = ret_20d / vol_20d.replace(0, np.nan)
    risk_adj_ret_60d = ret_60d / vol_60d.replace(0, np.nan)

    asset_mean_ret_60d = returns.rolling(60, min_periods=60).mean()

    wide_features = {
        "ret_5d": ret_5d,
        "ret_20d": ret_20d,
        "ret_60d": ret_60d,
        "ret_120d": ret_120d,
        "vol_20d": vol_20d,
        "vol_60d": vol_60d,
        "downside_vol_60d": downside_vol_60d,
        "drawdown_20d": drawdown_20d,
        "drawdown_60d": drawdown_60d,
        "ma_ratio_20_60": ma_ratio_20_60,
        "ma_ratio_60_120": ma_ratio_60_120,
        "volume_chg_20d": volume_chg_20d,
        "risk_adj_ret_20d": risk_adj_ret_20d,
        "risk_adj_ret_60d": risk_adj_ret_60d,
        "asset_mean_ret_60d": asset_mean_ret_60d,
        "rank_ret_20d": rank_pct(ret_20d, ascending=False),
        "rank_ret_60d": rank_pct(ret_60d, ascending=False),
        "rank_vol_60d": rank_pct(vol_60d, ascending=True),
        "rank_drawdown_60d": rank_pct(drawdown_60d, ascending=False),
        "z_ret_20d": zscore_cross_section(ret_20d),
        "z_ret_60d": zscore_cross_section(ret_60d),
        "z_vol_60d": zscore_cross_section(vol_60d),
    }

    future_return = adj.shift(-horizon_days) / adj - 1
    future_rank = future_return.rank(axis=1, ascending=False, method="first")
    cross_section_median = future_return.median(axis=1)

    wide_labels = {
        "future_return_21d": future_return,
        "future_rank_21d": future_rank,
        "label_outperform_median_21d": (future_return.gt(cross_section_median, axis=0)).astype(
            "Int64"
        ),
        "label_top2_21d": (future_rank <= 2).astype("Int64"),
        "label_positive_21d": (future_return > 0).astype("Int64"),
    }
    return wide_features, wide_labels


def wide_to_panel(frames: dict[str, pd.DataFrame], value_names: list[str]) -> pd.DataFrame:
    pieces = []
    for name in value_names:
        frame = frames[name]
        stacked = frame.stack(future_stack=True).rename(name).reset_index()
        stacked.columns = ["date", "ticker", name]
        pieces.append(stacked)

    panel = pieces[0]
    for piece in pieces[1:]:
        panel = panel.merge(piece, on=["date", "ticker"], how="left")
    return panel


def add_splits(panel: pd.DataFrame) -> pd.DataFrame:
    dates = pd.to_datetime(panel["date"])
    panel["split"] = np.select(
        [
            dates <= pd.Timestamp(TRAIN_END),
            dates <= pd.Timestamp(VALID_END),
        ],
        ["train", "valid"],
        default="test",
    )
    return panel


def add_month_end_flag(panel: pd.DataFrame, adj: pd.DataFrame) -> pd.DataFrame:
    month_end_dates = set(adj.resample("ME").last().index)
    panel["is_month_end_sample"] = pd.to_datetime(panel["date"]).isin(month_end_dates)
    return panel


def build_datasets(horizon_days: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    root = project_root()
    adj, returns, raw = read_prices(root)
    wide_features, wide_labels = build_wide_features(adj, returns, raw, horizon_days)

    feature_names = list(wide_features)
    label_names = list(wide_labels)
    features_panel = wide_to_panel(wide_features, feature_names)
    labels_panel = wide_to_panel(wide_labels, label_names)

    panel = features_panel.merge(labels_panel, on=["date", "ticker"], how="left")
    panel = panel.sort_values(["date", "ticker"]).reset_index(drop=True)
    panel = add_splits(panel)
    panel = add_month_end_flag(panel, adj)

    panel["date"] = pd.to_datetime(panel["date"])
    first_feature_date = panel.dropna(subset=feature_names)["date"].min()
    last_label_date = panel.dropna(subset=["future_return_21d"])["date"].max()

    modeling = panel.dropna(subset=feature_names + ["future_return_21d"]).copy()
    modeling[label_names[1:]] = modeling[label_names[1:]].astype(int)

    monthly = modeling[modeling["is_month_end_sample"]].copy()

    features_only = modeling[["date", "ticker", "split", "is_month_end_sample"] + feature_names]
    labels_only = modeling[["date", "ticker"] + label_names]

    summary = {
        "horizon_days": horizon_days,
        "tickers": TICKERS,
        "feature_names": feature_names,
        "label_names": label_names,
        "first_feature_available_date": first_feature_date.strftime("%Y-%m-%d"),
        "last_label_available_date": last_label_date.strftime("%Y-%m-%d"),
        "daily_modeling_shape": list(modeling.shape),
        "monthly_rebalance_shape": list(monthly.shape),
        "features_shape": list(features_only.shape),
        "labels_shape": list(labels_only.shape),
        "split_counts_daily": modeling["split"].value_counts().to_dict(),
        "split_counts_monthly": monthly["split"].value_counts().to_dict(),
        "ticker_counts_daily": modeling["ticker"].value_counts().to_dict(),
        "ticker_counts_monthly": monthly["ticker"].value_counts().to_dict(),
        "label_positive_rates": {
            col: float(modeling[col].mean()) for col in label_names if col.startswith("label_")
        },
        "monthly_label_positive_rates": {
            col: float(monthly[col].mean()) for col in label_names if col.startswith("label_")
        },
        "no_missing_features_in_modeling": bool(modeling[feature_names].isna().sum().sum() == 0),
        "no_missing_labels_in_modeling": bool(modeling[label_names].isna().sum().sum() == 0),
    }
    return modeling, monthly, features_only, labels_only, summary


def main() -> None:
    args = parse_args()
    root = project_root()
    modeling, monthly, features_only, labels_only, summary = build_datasets(args.horizon_days)

    processed_dir = root / "data" / "processed"
    tables_dir = root / "outputs" / "tables"
    processed_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    modeling_path = processed_dir / "modeling_dataset_daily.csv"
    monthly_path = processed_dir / "modeling_dataset_monthly_rebalance.csv"
    modeling_plan_path = processed_dir / "modeling_dataset.csv"
    daily_features_path = processed_dir / "daily_features.csv"
    daily_labels_path = processed_dir / "daily_labels.csv"
    monthly_features_path = processed_dir / "monthly_features.csv"
    monthly_labels_path = processed_dir / "monthly_labels.csv"
    summary_path = tables_dir / "feature_dataset_quality.json"

    modeling.to_csv(modeling_path, index=False)
    modeling.to_csv(modeling_plan_path, index=False)
    monthly.to_csv(monthly_path, index=False)
    features_only.to_csv(daily_features_path, index=False)
    labels_only.to_csv(daily_labels_path, index=False)
    monthly[["date", "ticker", "split", "is_month_end_sample"] + summary["feature_names"]].to_csv(
        monthly_features_path, index=False
    )
    monthly[["date", "ticker"] + summary["label_names"]].to_csv(
        monthly_labels_path, index=False
    )

    config = FeatureConfig(
        horizon_days=args.horizon_days,
        tickers=TICKERS,
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        split_rule="train <= 2022-12-31, valid <= 2023-12-31, test >= 2024-01-01",
        feature_lag_rule="All features use prices, returns, and volume observed at or before sample date.",
        label_rule="Forward 21-trading-day return and cross-sectional relative labels.",
    )

    metadata = {
        "feature_config": asdict(config),
        "quality_summary": summary,
        "artifacts": {
            "daily_modeling_dataset": str(modeling_path.relative_to(root)),
            "plan_modeling_dataset": str(modeling_plan_path.relative_to(root)),
            "monthly_rebalance_dataset": str(monthly_path.relative_to(root)),
            "daily_features": str(daily_features_path.relative_to(root)),
            "daily_labels": str(daily_labels_path.relative_to(root)),
            "monthly_features": str(monthly_features_path.relative_to(root)),
            "monthly_labels": str(monthly_labels_path.relative_to(root)),
        },
    }
    summary_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
