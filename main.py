# main.py
import os
import pandas as pd
from datetime import datetime
from ai_agent import AIAgent
from portfolio_manager import PortfolioManager
from trade_executor import TradeExecutor
from config import SYMBOLS, TRADE_FEE
from data_fetcher import initialize_all_data
from data_preprocessor import preprocess_all
from add_vix import add_allVix

# ==========================================================
# 🧩 回测控制器
# ==========================================================
class BacktestController:
    def __init__(self, start_date=None, end_date=None):
        self.start_date = start_date
        self.end_date = end_date
        self.portfolio = PortfolioManager(initial_cash=100000)
        self.agent = AIAgent()
        self.executor = TradeExecutor(self.portfolio)

    # ------------------------------------------------------
    # 初始化数据
    # ------------------------------------------------------
    def initialize_data(self):
        print("\n🚀 正在初始化数据...")
        initialize_all_data()
        preprocess_all()
        add_allVix()
        print("✅ 数据初始化完成！")

    # ------------------------------------------------------
    # 读取所有股票数据
    # ------------------------------------------------------
    def load_all_data(self):
        all_data = {}
        for sym in SYMBOLS:
            daily_path = f"processed/{sym}_daily_clean.csv"
            weekly_path = f"processed/{sym}_weekly_clean.csv"
            monthly_path = f"processed/{sym}_monthly_clean.csv"

            if os.path.exists(daily_path):
                df_daily = pd.read_csv(daily_path, parse_dates=["Date"]).sort_values("Date")
            else:
                print(f"⚠️ 缺少 {sym} 日线数据")
                continue

            df_weekly = pd.read_csv(weekly_path, parse_dates=["Date"]).sort_values("Date") if os.path.exists(weekly_path) else pd.DataFrame()
            df_monthly = pd.read_csv(monthly_path, parse_dates=["Date"]).sort_values("Date") if os.path.exists(monthly_path) else pd.DataFrame()

            all_data[sym] = {
                "daily": df_daily,
                "weekly": df_weekly,
                "monthly": df_monthly
            }
        return all_data

    # ------------------------------------------------------
    # 获取所有交易日
    # ------------------------------------------------------
    def get_trading_days(self, all_data):
        dates = set()
        for df in all_data.values():
            dates.update(df["Date"].dt.date)
        all_days = sorted(list(dates))
        if self.start_date:
            all_days = [d for d in all_days if d >= pd.to_datetime(self.start_date).date()]
        if self.end_date:
            all_days = [d for d in all_days if d <= pd.to_datetime(self.end_date).date()]
        return all_days

    # ------------------------------------------------------
    # 主回测循环
    # ------------------------------------------------------
    def run(self):
        self.initialize_data()
        all_data = self.load_all_data()
        all_days = self.get_trading_days({sym: d["daily"] for sym, d in all_data.items()})

        for current_day in all_days:
            print(f"\n📅 日期: {current_day} --------------------")

            # 组合多周期数据
            daily_data = {}
            for sym, dfs in all_data.items():
                df_d = dfs["daily"]
                df_w = dfs["weekly"]
                df_m = dfs["monthly"]

                # 获取当日行
                row_d = df_d[df_d["Date"].dt.date == current_day]
                if row_d.empty:
                    continue
                row_d = row_d.iloc[-1].to_dict()

                # 获取最新周/月线（不晚于当天）
                row_w = df_w[df_w["Date"].dt.date <= current_day]
                row_w = row_w.iloc[-1].to_dict() if not row_w.empty else {}
                row_m = df_m[df_m["Date"].dt.date <= current_day]
                row_m = row_m.iloc[-1].to_dict() if not row_m.empty else {}

                # 打包传入 agent
                daily_data[sym] = {
                    "daily": row_d,
                    "weekly": row_w,
                    "monthly": row_m,
                }

            if not daily_data:
                continue

            # === AI 生成信号 ===
            signals = self.agent.generate_signals(daily_data, self.portfolio.positions)
            if signals.empty:
                continue
            self.agent.save_signals(signals)

            # === 执行交易 ===
            self.executor.run()

            # === 扣手续费 ===
            trades_path = "logs/trades_log.csv"
            if os.path.exists(trades_path):
                trades = pd.read_csv(trades_path)
                daily_trades = trades[trades["Time"].str.contains(str(current_day))]
                if not daily_trades.empty:
                    fee = len(daily_trades) * TRADE_FEE
                    self.portfolio.cash -= fee
                    print(f"💸 扣除手续费 {TRADE_FEE}/笔，共 {fee:.2f} 美元")

            # === 每日汇总 ===
            self.portfolio.summary()

        print("\n✅ 回测完成！")
        self.final_report()

    # ------------------------------------------------------
    # 绩效汇总
    # ------------------------------------------------------
    def final_report(self):
        trades_path = "logs/trades_log.csv"
        if not os.path.exists(trades_path):
            print("⚠️ 无交易记录。")
            return

        trades = pd.read_csv(trades_path)
        print(f"\n📊 总交易次数: {len(trades)}")
        print(f"💰 最终现金: {self.portfolio.cash:.2f}")
        self.portfolio.summary()


# ==========================================================
# 🧪 运行主程序
# ==========================================================
if __name__ == "__main__":
    backtest = BacktestController(start_date="2025-10-01", end_date="2025-10-25")
    backtest.run()
