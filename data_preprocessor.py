# data_preprocessor.py
import os
import pandas as pd
import numpy as np
import yfinance as yf
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from config import SYMBOLS, DATA_PATH

PROCESSED_PATH = "processed/"


# ------------------------------ #
# 技术指标计算函数
# ------------------------------ #
def add_technical_indicators(df, period="daily"):
    df = df.copy()
    n = len(df)

    # EMA20 (require at least 20 periods)
    if n >= 20:
        ema = EMAIndicator(close=df["Close"], window=20)
        df["EMA20"] = ema.ema_indicator()
    else:
        df["EMA20"] = np.nan

    # RSI (require at least 14 periods)
    if n >= 14:
        rsi = RSIIndicator(close=df["Close"], window=14)
        df["RSI"] = rsi.rsi()
    else:
        df["RSI"] = np.nan

    # MACD (requires a reasonable number of periods; default slow=26)
    if n >= 26:
        macd = MACD(close=df["Close"])
        df["MACD"] = macd.macd()
        df["MACD_Signal"] = macd.macd_signal()
        df["MACD_Hist"] = macd.macd_diff()
    else:
        df["MACD"] = np.nan
        df["MACD_Signal"] = np.nan
        df["MACD_Hist"] = np.nan

    # ATR（波动率） (require at least 14 periods)
    if n >= 14:
        atr = AverageTrueRange(high=df["High"], low=df["Low"], close=df["Close"], window=14)
        df["ATR"] = atr.average_true_range()
    else:
        df["ATR"] = np.nan

    # 布林带 (require at least 20 periods)
    if n >= 20:
        bb = BollingerBands(close=df["Close"], window=20, window_dev=2)
        df["BB_Upper"] = bb.bollinger_hband()
        df["BB_Lower"] = bb.bollinger_lband()
        df["BB_Width"] = df["BB_Upper"] - df["BB_Lower"]
    else:
        df["BB_Upper"] = np.nan
        df["BB_Lower"] = np.nan
        df["BB_Width"] = np.nan
        
    # VIX is injected separately after preprocessing of all daily files.
    # This keeps indicator computation focused and prevents repeated VIX
    # downloads during per-symbol processing. Processed daily files will
    # be updated with VIX by a separate utility (scripts/fetch_and_inject_vix.py).
    if period != "daily":
        # Ensure monthly/weekly do not contain a VIX column
        if "VIX" in df.columns:
            df = df.drop(columns=["VIX"])

    return df


# ------------------------------ #
# 清洗与时间格式化
# ------------------------------ #
def clean_dataframe(df):
    # Normalize possible malformed CSVs (extra header rows or missing 'Date' column)
    df = df.copy()

    # If file was saved with a proper 'Date' column, use it. Otherwise try to detect/repair.
    if "Date" not in df.columns:
        # Try to find a column that contains parseable dates
        date_col = None
        for col in df.columns:
            sample_vals = df[col].dropna().astype(str)
            if len(sample_vals) == 0:
                continue
            sample = sample_vals.iloc[0]
            try:
                pd.to_datetime(sample, errors="raise")
                date_col = col
                break
            except Exception:
                continue

        if date_col:
            df = df.rename(columns={date_col: "Date"})
        else:
            # If no date-like column found, drop a few top rows that may contain extra headers
            drop_n = 0
            max_drop = min(5, len(df) - 1)
            while drop_n < max_drop:
                candidate = str(df.iloc[drop_n, 0])
                try:
                    pd.to_datetime(candidate)
                    break
                except Exception:
                    drop_n += 1
            if drop_n > 0:
                df = df.drop(index=range(0, drop_n)).reset_index(drop=True)
            # Rename first column to Date
            df = df.rename(columns={df.columns[0]: "Date"})

    # Ensure Date column is datetime
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])  # drop rows where Date couldn't be parsed
    df = df.sort_values("Date")
    df = df.drop_duplicates(subset=["Date"])

    # Forward/backward fill using recommended APIs
    df = df.ffill().bfill()

    # Set Date as index
    df.set_index("Date", inplace=True)

    # Coerce common numeric columns to numeric types to avoid rolling errors inside indicator libs
    numeric_cols = [c for c in ["Open", "High", "Low", "Close", "Adj Close", "Volume"] if c in df.columns]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


# ------------------------------ #
# 处理单个周期的数据
# ------------------------------ #
def process_single(symbol, period):
    file_path = os.path.join(DATA_PATH, f"{symbol}_{period}.csv")
    if not os.path.exists(file_path):
        print(f"⚠️ 找不到 {symbol}_{period}.csv，跳过。")
        return

    df = pd.read_csv(file_path)
    df = clean_dataframe(df)
    df = add_technical_indicators(df, period)

    os.makedirs(PROCESSED_PATH, exist_ok=True)
    save_path = os.path.join(PROCESSED_PATH, f"{symbol}_{period}_clean.csv")
    df.to_csv(save_path)
    print(f"✅ 已处理并保存 {symbol}_{period}_clean.csv ({len(df)} 条)")


# ------------------------------ #
# 主函数
# ------------------------------ #
def preprocess_all():
    for symbol in SYMBOLS:
        for period in ["daily", "weekly", "monthly"]:
            process_single(symbol, period)


if __name__ == "__main__":
    preprocess_all()
