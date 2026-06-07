from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf


DEFAULT_TICKERS = ["SPY", "QQQ", "TLT", "GLD", "VNQ", "DBC"]
DEFAULT_START = "2018-01-01"
DEFAULT_END = "2026-06-01"
EXPECTED_FIRST_TRADING_DAY = "2018-01-02"
EXPECTED_LAST_TRADING_DAY = "2026-05-29"


@dataclass
class DownloadConfig:
    tickers: list[str]
    start: str
    end: str
    interval: str
    auto_adjust: bool
    generated_at_utc: str
    source: str
    tool: str
    fallback_used: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download ETF price data and produce role-A quality artifacts."
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=DEFAULT_TICKERS,
        help="ETF tickers to download.",
    )
    parser.add_argument("--start", default=DEFAULT_START, help="Inclusive start date.")
    parser.add_argument(
        "--end",
        default=DEFAULT_END,
        help="Exclusive end date. Use 2026-06-01 to include 2026-05-29.",
    )
    parser.add_argument("--interval", default="1d", help="Yahoo Finance interval.")
    parser.add_argument(
        "--force-network",
        action="store_true",
        help="Fail if fresh network download cannot pass quality checks.",
    )
    return parser.parse_args()


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def normalize_download(raw: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    """Normalize yfinance output to a two-level column index: field, ticker."""
    if not isinstance(raw.columns, pd.MultiIndex):
        if len(tickers) != 1:
            raise ValueError("Expected multi-index columns for multiple tickers.")
        raw.columns = pd.MultiIndex.from_product([raw.columns, tickers])

    # yfinance can return either field/ticker or ticker/field depending on options.
    level0 = set(map(str, raw.columns.get_level_values(0)))
    expected_fields = {"Open", "High", "Low", "Close", "Adj Close", "Volume"}
    if not expected_fields.intersection(level0):
        raw = raw.swaplevel(axis=1)

    raw = raw.sort_index(axis=1, level=[0, 1])
    raw.index = pd.to_datetime(raw.index)
    raw.index.name = "Date"
    return raw


def save_multiindex_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=True)


def read_back_multiindex_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, header=[0, 1], index_col=0, parse_dates=True)
    frame.index.name = "Date"
    return frame


def extract_field(raw: pd.DataFrame, field: str, tickers: list[str]) -> pd.DataFrame:
    if field not in raw.columns.get_level_values(0):
        raise KeyError(f"Missing expected field: {field}")
    field_frame = raw[field].copy()
    field_frame = field_frame.reindex(columns=tickers)
    field_frame.index.name = "Date"
    return field_frame


def unix_timestamp(date_text: str) -> int:
    return int(pd.Timestamp(date_text, tz="UTC").timestamp())


def chart_url(ticker: str, start: str, end: str, interval: str) -> str:
    params = urllib.parse.urlencode(
        {
            "period1": unix_timestamp(start),
            "period2": unix_timestamp(end),
            "interval": interval,
            "events": "history",
            "includeAdjustedClose": "true",
        }
    )
    return f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?{params}"


def fetch_chart_ticker(ticker: str, start: str, end: str, interval: str) -> pd.DataFrame:
    request = urllib.request.Request(
        chart_url(ticker, start, end, interval),
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    chart = payload.get("chart", {})
    if chart.get("error"):
        raise RuntimeError(f"Yahoo chart error for {ticker}: {chart['error']}")
    result = (chart.get("result") or [None])[0]
    if not result:
        raise RuntimeError(f"Yahoo chart returned no result for {ticker}")

    timestamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    adjclose = (result.get("indicators", {}).get("adjclose") or [{}])[0].get(
        "adjclose"
    )
    if not timestamps or adjclose is None:
        raise RuntimeError(f"Yahoo chart missing timestamps or adjusted close for {ticker}")

    dates = [
        datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")
        for ts in timestamps
    ]
    frame = pd.DataFrame(
        {
            ("Open", ticker): quote.get("open"),
            ("High", ticker): quote.get("high"),
            ("Low", ticker): quote.get("low"),
            ("Close", ticker): quote.get("close"),
            ("Adj Close", ticker): adjclose,
            ("Volume", ticker): quote.get("volume"),
        },
        index=pd.to_datetime(dates),
    )
    frame.index.name = "Date"
    return frame


def download_with_chart_api(
    tickers: list[str], start: str, end: str, interval: str
) -> pd.DataFrame:
    frames = [fetch_chart_ticker(ticker, start, end, interval) for ticker in tickers]
    raw = pd.concat(frames, axis=1).sort_index(axis=1, level=[0, 1])
    raw.index.name = "Date"
    return raw


def download_with_yfinance(
    tickers: list[str], start: str, end: str, interval: str
) -> pd.DataFrame:
    raw = yf.download(
        tickers,
        start=start,
        end=end,
        interval=interval,
        auto_adjust=False,
        progress=False,
        group_by="column",
        threads=True,
    )
    return normalize_download(raw, tickers)


def prepare_outputs(
    raw: pd.DataFrame, tickers: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    raw = normalize_download(raw, tickers)
    adj_close = extract_field(raw, "Adj Close", tickers)
    daily_returns = adj_close.pct_change()
    quality, summary = quality_checks(raw, adj_close, daily_returns, tickers)
    return adj_close, daily_returns, quality, summary


def load_existing_if_valid(
    root: Path, tickers: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]] | None:
    raw_path = root / "data" / "raw" / "etf_prices_raw.csv"
    if not raw_path.exists():
        return None
    try:
        raw = read_back_multiindex_csv(raw_path)
        adj_close, daily_returns, quality, summary = prepare_outputs(raw, tickers)
    except Exception:
        return None
    if summary.get("quality_pass"):
        return raw, adj_close, daily_returns, quality, summary
    return None


def max_drawdown(series: pd.Series) -> float:
    wealth = (1 + series.dropna()).cumprod()
    if wealth.empty:
        return np.nan
    drawdown = wealth / wealth.cummax() - 1
    return float(drawdown.min())


def quality_checks(
    raw: pd.DataFrame,
    adj_close: pd.DataFrame,
    daily_returns: pd.DataFrame,
    tickers: list[str],
) -> tuple[pd.DataFrame, dict[str, object]]:
    duplicate_dates = int(adj_close.index.duplicated().sum())
    shared_row_count = int(adj_close.dropna(how="any").shape[0])

    rows = []
    row_counts = {}
    missing_counts = {}
    first_dates = {}
    last_dates = {}

    for ticker in tickers:
        price = adj_close[ticker]
        returns = daily_returns[ticker]
        valid_price = price.dropna()

        row_count = int(valid_price.shape[0])
        row_counts[ticker] = row_count
        missing_count = int(price.isna().sum())
        missing_counts[ticker] = missing_count
        first_date = valid_price.index.min()
        last_date = valid_price.index.max()
        first_dates[ticker] = first_date.strftime("%Y-%m-%d") if pd.notna(first_date) else ""
        last_dates[ticker] = last_date.strftime("%Y-%m-%d") if pd.notna(last_date) else ""

        non_positive_prices = int((valid_price <= 0).sum())
        extreme_return_count = int((returns.abs() > 0.20).sum())
        max_abs_return = float(returns.abs().max(skipna=True))

        rows.append(
            {
                "ticker": ticker,
                "first_date": first_dates[ticker],
                "last_date": last_dates[ticker],
                "price_rows": row_count,
                "missing_adj_close": missing_count,
                "non_positive_adj_close": non_positive_prices,
                "daily_return_rows": int(returns.dropna().shape[0]),
                "missing_daily_returns": int(returns.isna().sum()),
                "extreme_abs_return_gt_20pct": extreme_return_count,
                "max_abs_daily_return": max_abs_return,
                "min_adj_close": float(valid_price.min()) if not valid_price.empty else np.nan,
                "max_adj_close": float(valid_price.max()) if not valid_price.empty else np.nan,
                "period_total_return": float(valid_price.iloc[-1] / valid_price.iloc[0] - 1)
                if row_count >= 2
                else np.nan,
                "period_max_drawdown": max_drawdown(returns),
            }
        )

    quality = pd.DataFrame(rows)
    summary = {
        "tickers": tickers,
        "all_row_counts_equal": len(set(row_counts.values())) == 1,
        "row_counts": row_counts,
        "missing_counts": missing_counts,
        "first_dates": first_dates,
        "last_dates": last_dates,
        "expected_first_trading_day": EXPECTED_FIRST_TRADING_DAY,
        "expected_last_trading_day": EXPECTED_LAST_TRADING_DAY,
        "all_start_dates_match_expected": all(
            d == EXPECTED_FIRST_TRADING_DAY for d in first_dates.values()
        ),
        "all_end_dates_match_expected": all(
            d == EXPECTED_LAST_TRADING_DAY for d in last_dates.values()
        ),
        "duplicate_dates": duplicate_dates,
        "shared_complete_price_rows": shared_row_count,
        "raw_shape": list(raw.shape),
        "adj_close_shape": list(adj_close.shape),
        "daily_returns_shape": list(daily_returns.shape),
        "quality_pass": bool(
            len(set(row_counts.values())) == 1
            and all(v == 0 for v in missing_counts.values())
            and all(d == EXPECTED_FIRST_TRADING_DAY for d in first_dates.values())
            and all(d == EXPECTED_LAST_TRADING_DAY for d in last_dates.values())
            and duplicate_dates == 0
            and int(quality["non_positive_adj_close"].sum()) == 0
        ),
    }
    return quality, summary


def main() -> None:
    args = parse_args()
    tickers = [ticker.upper() for ticker in args.tickers]
    root = project_root()
    fallback_used = False

    config = DownloadConfig(
        tickers=tickers,
        start=args.start,
        end=args.end,
        interval=args.interval,
        auto_adjust=False,
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        source="Yahoo Finance historical market data",
        tool="yfinance.download",
        fallback_used=False,
    )

    raw_path = root / "data" / "raw" / "etf_prices_raw.csv"
    adj_close_path = root / "data" / "processed" / "prices_adj_close.csv"
    daily_returns_path = root / "data" / "processed" / "daily_returns.csv"
    quality_path = root / "outputs" / "tables" / "data_quality_check.csv"
    metadata_path = root / "outputs" / "tables" / "download_metadata.json"

    download_errors: list[str] = []
    raw: pd.DataFrame | None = None
    for tool_name, downloader in [
        ("yfinance.download", download_with_yfinance),
        ("Yahoo Chart API", download_with_chart_api),
    ]:
        try:
            candidate = downloader(tickers, args.start, args.end, args.interval)
            adj_close, daily_returns, quality, summary = prepare_outputs(candidate, tickers)
            if summary["quality_pass"]:
                raw = candidate
                config.tool = tool_name
                fallback_used = tool_name != "yfinance.download"
                break
            download_errors.append(
                f"{tool_name} returned data that failed quality checks: {summary}"
            )
        except Exception as error:
            download_errors.append(f"{tool_name} failed: {type(error).__name__}: {error}")

    if raw is None:
        existing = None if args.force_network else load_existing_if_valid(root, tickers)
        if existing is None:
            raise RuntimeError(
                "Fresh download failed and no valid existing dataset is available. "
                + " | ".join(download_errors)
            )
        raw, adj_close, daily_returns, quality, summary = existing
        config.tool = "existing local validated CSV"
        fallback_used = True
    else:
        adj_close, daily_returns, quality, summary = prepare_outputs(raw, tickers)

    config.fallback_used = fallback_used

    save_multiindex_csv(raw, raw_path)

    adj_close.to_csv(adj_close_path, index=True)
    daily_returns.to_csv(daily_returns_path, index=True)

    quality.to_csv(quality_path, index=False)

    metadata = {
        "download_config": asdict(config),
        "quality_summary": summary,
        "artifacts": {
            "raw_prices": str(raw_path.relative_to(root)),
            "adj_close": str(adj_close_path.relative_to(root)),
            "daily_returns": str(daily_returns_path.relative_to(root)),
            "quality_check": str(quality_path.relative_to(root)),
        },
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
