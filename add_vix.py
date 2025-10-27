# 获取vixdaily数据, 并存储在本地, 然后注入到每个股票的processed_daily文件中
import os
import pandas as pd
from data_fetcher import get_price_data 
from config import DATA_PATH, SYMBOLS, START_DATE
import os
import re
from pathlib import Path
import pandas as pd
from data_fetcher import get_price_data
from config import DATA_PATH, SYMBOLS, START_DATE


def fetch_vix_data(start_date=START_DATE):
    """Fetch VIX daily data via existing data_fetcher helper.

    Returns a DataFrame indexed by Date (DatetimeIndex).
    """
    vix_symbol = "^VIX"
    vix_data = get_price_data(vix_symbol, start=start_date, interval="1d")
    return vix_data


def save_vix_data(vix_data, data_dir=DATA_PATH):
    """Save cleaned VIX to canonical filename `VIX_daily.csv` in data_dir."""
    os.makedirs(data_dir, exist_ok=True)
    out = Path(data_dir) / "VIX_daily.csv"
    # ensure index name
    if vix_data is not None and not vix_data.empty:
        # ensure datetime index
        vix = vix_data.copy()
        vix.index = pd.to_datetime(vix.index, errors="coerce")
        vix = vix[~vix.index.isna()]
        vix = vix.sort_index()

        # flatten MultiIndex columns if present (e.g., (Price, Ticker)) -> use Price level
        if hasattr(vix.columns, "nlevels") and vix.columns.nlevels > 1:
            try:
                vix.columns = vix.columns.get_level_values(0)
            except Exception:
                # fallback: convert to strings
                vix.columns = ["_".join(map(str, c)) for c in vix.columns]

        # choose close-like column
        close_col = None
        for c in ["Adj Close", "Close", "Price"]:
            if c in vix.columns:
                close_col = c
                break
        if close_col is None and vix.shape[1] > 0:
            close_col = vix.columns[0]

        # build canonical dataframe with exact columns and order
        df_out = pd.DataFrame(index=vix.index)
        # robustly extract close-like series
        if close_col is not None:
            try:
                close_series = vix[close_col]
            except Exception:
                # fallback to first column
                close_series = vix.iloc[:, 0]
            df_out["Close"] = pd.to_numeric(close_series, errors="coerce")
        else:
            df_out["Close"] = pd.NA
        for col in ["High", "Low", "Open", "Volume"]:
            if col in vix.columns:
                df_out[col] = pd.to_numeric(vix[col], errors="coerce")
            else:
                # missing column -> create NA column
                df_out[col] = pd.NA

        # write with explicit Date index label and canonical column order
        df_out.index.name = "Date"
        df_out = df_out[["Close", "High", "Low", "Open", "Volume"]]
        df_out.to_csv(out, index_label="Date")
    else:
        print("⚠️ vix_data empty, nothing saved")


def _read_vix_file(path: Path) -> pd.DataFrame:
    """Robustly read a VIX CSV that may contain extra header/metadata rows.

    Returns a DataFrame indexed by Date with numeric columns.
    """
    text = path.read_text()
    lines = text.splitlines()
    date_re = re.compile(r"^\s*\d{4}-\d{2}-\d{2}")
    start_row = None
    for i, ln in enumerate(lines):
        if date_re.match(ln):
            start_row = i
            break

    if start_row is None:
        # fallback: try read normally and coerce
        df = pd.read_csv(path, engine="python", on_bad_lines="skip")
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.dropna(subset=["Date"])
            df = df.set_index("Date")
        else:
            # try first column as date
            df = pd.read_csv(path, parse_dates=True, index_col=0, engine="python", on_bad_lines="skip")
            if df.index.name is None:
                df.index.name = "Date"
        return df

    # read from first date-like row
    df = pd.read_csv(path, skiprows=range(0, start_row), parse_dates=[0], index_col=0, engine="python", on_bad_lines="skip")
    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df[~df.index.isna()]
    # coerce numeric columns
    for c in df.columns:
        try:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        except Exception:
            pass
    return df


def update_processed_with_vix(processed_dir="processed", data_dir=DATA_PATH):
    """Inject VIX values into processed daily CSVs in-place.

    - Reads `data/VIX_daily.csv` (robust to messy headers).
    - Picks column preference: 'Adj Close' -> 'Close' -> 'Price' -> first numeric.
    - Aligns by date (date-only), forward-fills, writes back processed files.
    """
    vix_path = Path(data_dir) / "VIX_daily.csv"
    if not vix_path.exists():
        print("⚠️ VIX 数据文件不存在 (VIX_daily.csv)。请先运行数据获取。")
        return

    vix_df = _read_vix_file(vix_path)
    if vix_df is None or vix_df.empty:
        print("⚠️ 无法读取 VIX 数据或数据为空。")
        return

    # choose column
    vix_col = None
    for c in ["Adj Close", "Close", "Price"]:
        if c in vix_df.columns:
            vix_col = c
            break
    if vix_col is None:
        numeric_cols = vix_df.select_dtypes(include=["number"]).columns.tolist()
        if numeric_cols:
            vix_col = numeric_cols[0]

    if vix_col is None:
        print("⚠️ 找不到可用的 VIX 数值列。文件列名：", vix_df.columns.tolist())
        return

    # create a date->value mapping (date objects)
    vix_series = vix_df[vix_col].copy()
    vix_series.index = pd.to_datetime(vix_series.index).date

    processed_p = Path(processed_dir)
    if not processed_p.exists():
        print(f"⚠️ 目录 {processed_dir} 不存在。")
        return

    for f in sorted(processed_p.glob("*_daily_clean.csv")):
        try:
            df = pd.read_csv(f, parse_dates=[0], engine="python", on_bad_lines="skip")
        except Exception:
            df = pd.read_csv(f, engine="python", on_bad_lines="skip")
        if "Date" not in df.columns:
            print(f"⚠️ 文件 {f.name} 缺少 Date 列，跳过。")
            continue

        dates = df["Date"].dt.date
        # map vix values; use ffill on the mapped series
        mapped = pd.Series([vix_series.get(d, pd.NA) for d in dates], index=df.index)
        mapped = mapped.ffill()
        df["VIX"] = mapped.values
        df.to_csv(f, index=False)
        print(f"✅ 已更新 {f.name}，共 {len(df)} 行，VIX 注入完成。")


def add_allVix():
    vix_data = fetch_vix_data()
    save_vix_data(vix_data)
    update_processed_with_vix(processed_dir="processed", data_dir=DATA_PATH)


if __name__ == "__main__":
    add_allVix()