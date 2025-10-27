#!/usr/bin/env python3
import ast
import os
import glob
import pandas as pd

DATA_DIR = 'data'

def normalize_col_name(c):
    if isinstance(c, tuple):
        return c[0]
    s = str(c)
    if (s.startswith("('") or s.startswith('("')) and s.endswith(')'):
        try:
            t = ast.literal_eval(s)
            if isinstance(t, tuple) and len(t) > 0:
                return t[0]
        except Exception:
            pass
    return s


def clean_file(path):
    print('Cleaning', path)
    df = pd.read_csv(path)
    # normalize column names
    new_cols = [normalize_col_name(c) for c in df.columns]
    df.columns = new_cols

    # ensure Date column exists; if index-like, try to recover
    if 'Date' not in df.columns:
        # assume first column is Date
        df.rename(columns={df.columns[0]: 'Date'}, inplace=True)

    # parse Date and set as index
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date'])
    df = df.sort_values('Date')
    df.set_index('Date', inplace=True)

    # coalesce duplicated OHLCV-like columns by taking first non-null across candidates
    targets = ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
    out = pd.DataFrame(index=df.index)
    for t in targets:
        candidates = [c for c in df.columns if c == t]
        # also consider common suffixes like 'Close.1' or variants
        candidates += [c for c in df.columns if c.startswith(t + '.') or c.startswith(t + '_')]
        # also check columns that may be like "Close_x" or contain the token
        candidates += [c for c in df.columns if t in c and c not in candidates]
        # deduplicate list
        candidates = list(dict.fromkeys(candidates))
        if not candidates:
            continue
        # coalesce: take first non-null across columns
        sub = df[candidates].astype(float)
        coalesced = sub.bfill(axis=1).iloc[:, 0]
        out[t] = coalesced

    # If no targets found, keep original dataframe
    if out.empty:
        print('No OHLCV-like columns found; skipping restructure for', path)
        # reset index and write original (but normalized) columns
        df_reset = df.reset_index()
        df_reset.to_csv(path, index=False)
        return

    # write back with Date as first column
    out_reset = out.reset_index()
    out_reset.to_csv(path, index=False)
    print('Wrote cleaned file', path)


if __name__ == '__main__':
    os.makedirs(DATA_DIR, exist_ok=True)
    files = glob.glob(os.path.join(DATA_DIR, '*.csv'))
    for f in files:
        try:
            clean_file(f)
        except Exception as e:
            print('Failed to clean', f, e)
