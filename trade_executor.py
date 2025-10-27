# trade_executor.py
import os
import pandas as pd
from datetime import datetime
from portfolio_manager import PortfolioManager
from config import Min_confidence
from config import Signals_path

class TradeExecutor:
    def __init__(self, portfolio: PortfolioManager, min_confidence=Min_confidence, signals_path=Signals_path):
        self.portfolio = portfolio
        self.min_confidence = min_confidence
        self.signals_path = signals_path

    # --------------------------------------------------------
    # 🔍 读取AI信号
    # --------------------------------------------------------
    def load_signals(self):
        if not os.path.exists(self.signals_path):
            print(f"⚠️ 找不到信号文件：{self.signals_path}")
            return pd.DataFrame()

        df = pd.read_csv(self.signals_path)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        # df = df[df["Confidence"] >= self.min_confidence]  # 筛选高置信度信号
        today = datetime.now().date()
        df = df[df["Date"].dt.date <= today]  # 只执行今天及之前的信号
        return df

    # --------------------------------------------------------
    # ⚙️ 执行单条交易
    # --------------------------------------------------------
    def execute_signal(self, symbol, action, price):
        qty = self._calculate_quantity(symbol, price)

        if qty <= 0:
            print(f"⚠️ {symbol} 交易数量为 0，跳过。")
            return

        if action == "BUY":
            self.portfolio.buy(symbol, price, qty)
        elif action == "SELL":
            self.portfolio.sell(symbol, price, qty)
        else:
            print(f"❌ 未知交易动作: {action}")

    # --------------------------------------------------------
    # 💰 动态仓位管理
    # --------------------------------------------------------
    def _calculate_quantity(self, symbol, price):
        """
        简单仓位管理逻辑：
        - 每次买入不超过总现金的 10%
        - 每次卖出全部持仓
        """
        cash = self.portfolio.cash
        if symbol in self.portfolio.positions:
            pos = self.portfolio.positions[symbol]
        else:
            pos = {"qty": 0, "avg_price": 0}

        max_allocation = 0.20  # 每次买入最多20%现金
        qty = 0

        if cash > 0:
            qty = int((cash * max_allocation) / price)

        # 如果是卖出信号 -> 卖出全部持仓
        if pos["qty"] > 0:
            qty = pos["qty"]

        return qty

    # --------------------------------------------------------
    # 🚀 执行所有信号
    # --------------------------------------------------------
    def run(self):
        df = self.load_signals()
        if df.empty:
            print("⚠️ 无有效交易信号。")
            return

        print(f"📈 检测到 {len(df)} 个交易信号，开始执行...")
        for _, row in df.iterrows():
            self.execute_signal(row["Symbol"], row["Action"], row["Price"])

        print("\n✅ 所有信号执行完毕！")
        self.portfolio.summary()


# ==========================================================
# 🧪 示例运行
# ==========================================================
if __name__ == "__main__":
    executor = TradeExecutor(portfolio, min_confidence)
    executor.run()
