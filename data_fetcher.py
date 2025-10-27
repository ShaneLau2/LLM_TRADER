# data_fetcher.py
import os
import ast
import pandas as pd
import yfinance as yf
import finnhub
from datetime import datetime, timedelta
from config import SYMBOLS, START_DATE, DATA_PATH, FINNHUB_API_KEY

# 初始化 finnhub 客户端
finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)


# ---------------------- #
# 从 yfinance 获取 K 线数据
# ---------------------- #
def get_price_data(symbol: str, start: str, interval: str):
    """从 Yahoo Finance 获取指定周期的K线"""
    df = yf.download(symbol, start=start, interval=interval, progress=False)
    if df.empty:
        print(f"⚠️ 无法获取 {symbol} {interval} 数据")
        return pd.DataFrame()
    df.index.name = "Date"
    return df


# ---------------------- #
# 从 Finnhub 获取基本面数据
# ---------------------- #
def get_finnhub_metrics(symbol):
    shares_outstanding = None
    long_short_ratio = None
    option_events = None

    try:
        metrics = finnhub_client.company_basic_financials(symbol, 'all')
        shares_outstanding = metrics['metric'].get('shares_outstanding', None)
    except:
        pass

    try:
        sentiment = finnhub_client.news_sentiment(symbol)
        long_short_ratio = sentiment["sentiment"].get("bullishPercent", 0) / 100
    except:
        pass

    try:
        option_data = finnhub_client.stock_option_expiration(symbol)
        option_events = len(option_data.get("expirationDates", []))
    except:
        pass

    return shares_outstanding, long_short_ratio, option_events


def _normalize_columns(df, symbol=None):
    """Normalize/flatten DataFrame column names.

    - If columns are tuples (MultiIndex), take the first level (e.g. ('Close','SOFI') -> 'Close').
    - If column names are stringified tuples like "('Close', 'SOFI')", parse and extract.
    - Ensures common OHLCV columns are present and returns cleaned df.
    """
    if df is None or df.empty:
        return df

    new_cols = []
    for c in df.columns:
        # MultiIndex tuple
        if isinstance(c, tuple):
            new_cols.append(c[0])
            continue

        s = str(c)
        # strings that look like tuple representations
        if (s.startswith("('") or s.startswith('("')) and s.endswith(')'):
            try:
                t = ast.literal_eval(s)
                if isinstance(t, tuple) and len(t) > 0:
                    new_cols.append(t[0])
                    continue
            except Exception:
                pass

        new_cols.append(s)

    df = df.copy()
    df.columns = new_cols

    # If there are duplicate columns after normalization (e.g., Close repeated), keep the first
    df = df.loc[:, ~df.columns.duplicated()]

    # Ensure numeric columns are numeric
    for c in ["Open", "High", "Low", "Close", "Adj Close", "Volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


# ---------------------- #
# 保存或更新数据
# ---------------------- #
def save_data(symbol, interval,name, df):
    os.makedirs(DATA_PATH, exist_ok=True)
    file_path = os.path.join(DATA_PATH, f"{symbol}_{name}.csv")

    today = datetime.now().date()
    start_date = START_DATE

    if os.path.exists(file_path):
        # Try reading existing file with a couple of common parse strategies to be robust
        try:
            df_old = pd.read_csv(file_path, parse_dates=["Date"], index_col="Date")
        except ValueError:
            # Fallback: parse the first column as dates and use it as index
            df_old = pd.read_csv(file_path, parse_dates=True, index_col=0)
            # ensure index is named 'Date'
            df_old.index.name = "Date"
        # Ensure index is datetime-like
        try:
            df_old.index = pd.to_datetime(df_old.index, errors="coerce")
        except Exception:
            df_old.index = pd.to_datetime(df_old.index.astype(str), errors="coerce")
        # Drop rows where index couldn't be parsed as datetime
        df_old = df_old[~df_old.index.isna()]
        last_date = df_old.index[-1].date()

        if last_date < today:
            print(f"🔄 更新 {symbol} {name} 从 {last_date} 到 {today}")
            df_new = get_price_data(symbol, start=(last_date + timedelta(days=1)).strftime("%Y-%m-%d"), interval=interval)
            # 判断last_date和df_new是否有重叠日期,如果重叠则替换旧数据
            if not df_new.empty:
                # Remove overlapping dates from old data
                df_old = df_old[~df_old.index.isin(df_new.index)]
                df = pd.concat([df_old, df_new]).sort_index()
            else:
                df = df_old
        else:
            print(f"✅ {symbol} {name} 已是最新数据")
            df = df_old
    else:
        print(f"⬇️ 下载 {symbol} {name} 从 {start_date} 到 {today}")
        df = get_price_data(symbol, start=start_date, interval=interval)

    # Normalize columns to avoid malformed headers like "('Close', 'SOFI')" and duplicated groups
    try:
        df = _normalize_columns(df, symbol=symbol)
    except Exception:
        pass

    # Write CSV with Date as first column (index may be DatetimeIndex)
    try:
        # ensure index has a name
        if df.index.name is None:
            df.index.name = "Date"
        df.to_csv(file_path)
    except Exception:
        # Fallback: reset index and write
        df.reset_index().to_csv(file_path, index=False)
    print(f"✅ {symbol} {name} 数据已保存 ({len(df)} 条)")
    return df


# ---------------------- #
# 主入口函数
# ---------------------- #
def initialize_all_data():
    for symbol in SYMBOLS:
        # 获取 finnhub 数据
        shares_outstanding, long_short_ratio, option_events = get_finnhub_metrics(symbol)

        # 获取日、周、月线
        for interval, name in [("1d", "daily"), ("1wk", "weekly"), ("1mo", "monthly")]:
            df = get_price_data(symbol, START_DATE, interval)
            if df.empty:
                continue

            # 计算换手率、多空比、期权活动
            if shares_outstanding:
                df["Turnover"] = df["Volume"] / shares_outstanding
            else:
                df["Turnover"] = None

            df["LongShortRatio"] = long_short_ratio
            df["OptionEvents"] = option_events

            # ✅ 保存时传入 interval，而不是 name
            save_data(symbol, interval,name, df)

            # # ✅ 另外保存一份文件名友好的版本
            # renamed_path = os.path.join(DATA_PATH, f"{symbol}_{name}.csv")
            # df.to_csv(renamed_path)
            # print(f"📁 {symbol} {name} 数据已保存 ({len(df)} 条)")


if __name__ == "__main__":
    initialize_all_data()
