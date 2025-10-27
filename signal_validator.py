# signal_validator.py
import pandas as pd
from config import Min_confidence
VALID_ACTIONS = ["BUY", "SELL", "HOLD"]

class SignalValidator:
    def __init__(self, positions, allow_sell_without_position=True, min_confidence=Min_confidence):
        """
        positions: 当前持仓字典，例如 {"AAPL": 100, "MSFT": 0}
        allow_sell_without_position: 若为 True，则允许在无仓位时仍执行 SELL（例如做空或强制平仓），否则会被过滤掉。
        min_confidence: 置信度阈值，低于该值的信号会被过滤。
        """
        # normalize position keys to uppercase for case-insensitive matching
        self.positions = {k.upper(): v for k, v in (positions or {}).items()}
        self.allow_sell_without_position = allow_sell_without_position
        self.min_confidence = min_confidence

    def validate_signals(self, df: pd.DataFrame):
        """
        检查AI输出信号的合理性
        返回过滤后的DataFrame
        """
        if df.empty:
            print("⚠️ 没有信号可验证。")
            return df

        valid_rows = []
        for _, row in df.iterrows():
            # normalize and validate fields
            symbol = row.get("symbol")
            if symbol is None:
                print(f"❌ 无效信号（缺少 symbol）：{row}")
                continue
            symbol = str(symbol).upper()

            action = str(row.get("action", "")).upper()

            # confidence may be string/NaN -> coerce
            try:
                confidence = float(row.get("confidence", 0) or 0)
            except Exception:
                confidence = 0.0

            reason = row.get("reason", "") or ""
            date = row.get("Date", "")

            # 1️⃣ 基本检查
            if action not in VALID_ACTIONS:
                print(f"❌ 无效信号动作：{row}")
                continue

            # 2️⃣ 信心过滤
            if confidence < float(self.min_confidence):
                print(f"⚠️ 信心不足 {symbol}: {confidence} < {self.min_confidence}")
                continue

            # 3️⃣ 仓位冲突检查
            pos = self.positions.get(symbol, 0)
            if action == "SELL" and pos == 0 and not self.allow_sell_without_position:
                print(f"⚠️ 无仓位却触发 SELL: {symbol} (已过滤)")
                continue

            # 4️⃣ 忽略 HOLD
            if action == "HOLD":
                # HOLD 不会产生交易
                continue

            valid_rows.append({
                "symbol": symbol,
                "action": action,
                "confidence": confidence,
                "reason": reason,
                "Date": date
            })

        df_valid = pd.DataFrame(valid_rows)
        print(f"✅ {len(df_valid)} 个信号通过验证")
        return df_valid
