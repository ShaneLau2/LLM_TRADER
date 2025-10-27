# portfolio_manager.py
import os
import pandas as pd
from datetime import datetime

# ==========================================================
# 🧩 PortfolioManager 类
# ==========================================================
class PortfolioManager:
    def __init__(self, initial_cash=100000, log_path="logs/"):
        self.cash = initial_cash
        self.positions = {}  # {symbol: {"qty": 0, "avg_price": 0}}
        self.total_value = initial_cash
        self.log_path = log_path

        os.makedirs(log_path, exist_ok=True)
        self.trades_log_file = os.path.join(log_path, "trades_log.csv")
        self.positions_log_file = os.path.join(log_path, "positions_log.csv")

        # 初始化日志文件
        if not os.path.exists(self.trades_log_file):
            pd.DataFrame(columns=[
                "Time", "Symbol", "Action", "Price", "Quantity", "Cost", "Cash_Balance"
            ]).to_csv(self.trades_log_file, index=False)

        if not os.path.exists(self.positions_log_file):
            pd.DataFrame(columns=[
                "Time", "Symbol", "Quantity", "Avg_Price", "Market_Price",
                "Market_Value", "Cash", "Total_Value"
            ]).to_csv(self.positions_log_file, index=False)

    # ----------------------------------------------------------
    # 💰 买入函数
    # ----------------------------------------------------------
    def buy(self, symbol, price, qty):
        cost = price * qty
        if cost > self.cash:
            print(f"❌ 现金不足，无法买入 {symbol}。")
            return False

        # 更新持仓
        if symbol not in self.positions:
            self.positions[symbol] = {"qty": 0, "avg_price": 0}

        pos = self.positions[symbol]
        new_qty = pos["qty"] + qty
        pos["avg_price"] = (pos["avg_price"] * pos["qty"] + price * qty) / new_qty
        pos["qty"] = new_qty
        self.cash -= cost

        self._write_trade_log(symbol, "BUY", price, qty, cost)
        self._write_position_log(symbol, price)
        print(f"✅ 买入 {symbol} {qty} 股 @ {price:.2f}, 现金余额 {self.cash:.2f}")
        return True

    # ----------------------------------------------------------
    # 💵 卖出函数
    # ----------------------------------------------------------
    def sell(self, symbol, price, qty):
        if symbol not in self.positions or self.positions[symbol]["qty"] < qty:
            print(f"❌ 持仓不足，无法卖出 {symbol}。")
            return False

        pos = self.positions[symbol]
        pos["qty"] -= qty
        proceeds = price * qty
        self.cash += proceeds

        # 如果清仓则删除持仓记录
        if pos["qty"] == 0:
            del self.positions[symbol]

        self._write_trade_log(symbol, "SELL", price, qty, proceeds)
        self._write_position_log(symbol, price)
        print(f"✅ 卖出 {symbol} {qty} 股 @ {price:.2f}, 现金余额 {self.cash:.2f}")
        return True

    # ----------------------------------------------------------
    # 📓 写入交易日志
    # ----------------------------------------------------------
    def _write_trade_log(self, symbol, action, price, qty, cost):
        time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_log = pd.DataFrame([{
            "Time": time_now,
            "Symbol": symbol,
            "Action": action,
            "Price": price,
            "Quantity": qty,
            "Cost": cost,
            "Cash_Balance": self.cash
        }])
        new_log.to_csv(self.trades_log_file, mode="a", header=False, index=False)

    # ----------------------------------------------------------
    # 📊 写入持仓日志
    # ----------------------------------------------------------
    def _write_position_log(self, symbol, market_price):
        time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = []
        total_value = self.cash

        for sym, pos in self.positions.items():
            mkt_value = pos["qty"] * market_price if sym == symbol else pos["qty"] * pos["avg_price"]
            total_value += mkt_value
            rows.append({
                "Time": time_now,
                "Symbol": sym,
                "Quantity": pos["qty"],
                "Avg_Price": pos["avg_price"],
                "Market_Price": market_price if sym == symbol else pos["avg_price"],
                "Market_Value": mkt_value,
                "Cash": self.cash,
                "Total_Value": total_value
            })

        if rows:
            pd.DataFrame(rows).to_csv(self.positions_log_file, mode="a", header=False, index=False)

    # ----------------------------------------------------------
    # 📈 查看当前持仓
    # ----------------------------------------------------------
    def summary(self):
        print("\n💼 当前持仓:")
        total_value = self.cash
        for sym, pos in self.positions.items():
            market_value = pos["qty"] * pos["avg_price"]
            total_value += market_value
            print(f"{sym}: {pos['qty']} 股, 均价 {pos['avg_price']:.2f}, 市值 {market_value:.2f}")
        print(f"现金余额: {self.cash:.2f}")
        print(f"账户总资产: {total_value:.2f}")
        return total_value


# ==========================================================
# 🧪 示例用法
# ==========================================================
if __name__ == "__main__":
    portfolio = PortfolioManager(initial_cash=100000)
    portfolio.summary()
