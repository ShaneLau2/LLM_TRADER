# ai_agent.py
import os
import json
import time
import pandas as pd
from datetime import datetime
from utils.api_helper import call_deepseek_api
from config import AI_MODEL, AGENT_SYSTEM_PROMPT, DATA_PATH
# ai_agent.py (新增部分)
from signal_validator import SignalValidator
from config import Signals_path
from config import API_LOG_PATH

def _write_api_log(request_payload, response_text):
    import json
    from datetime import datetime

    entry = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "request": request_payload,
        "response": response_text
    }

    os.makedirs(os.path.dirname(API_LOG_PATH), exist_ok=True)
    with open(API_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, indent=2) + "\n")


class AIAgent:
    def __init__(self):
        self.model = AI_MODEL
        self.prompt = AGENT_SYSTEM_PROMPT
        # Use the centralized Signals_path as the single file for both logs and executor input
        self.log_path = Signals_path
        # ensure directory exists for Signals_path
        dirpath = os.path.dirname(Signals_path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)

    # ------------------------------------------------------
# 🤖 AI 智能交易 Agent
# ==========================================================
class AIAgent:
    def __init__(self):
        self.model = AI_MODEL
        self.prompt = AGENT_SYSTEM_PROMPT
        # Use the centralized Signals_path as the single file for both logs and executor input
        self.log_path = Signals_path
        # ensure directory exists for Signals_path
        dirpath = os.path.dirname(Signals_path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)

    # ------------------------------------------------------
    # 每日生成交易信号
    # ------------------------------------------------------

        
    def generate_signals(self, daily_data: dict, positions: dict):
        """
        daily_data: {symbol: {指标...}}
        positions: 当前持仓信息
        """
        print("🤖 正在调用 AI 模型生成交易信号...")
        # normalize today to a string to avoid Timestamp serialization issues
        today = list(daily_data.values())[0]["daily"]["Date"]
        if isinstance(today, (pd.Timestamp, datetime)):
            today = today.strftime("%Y-%m-%d")
        else:
            try:
                # if it's an array-like (e.g. numpy), try to convert
                today = str(today)
            except Exception:
                today = ""

        formatted = {}
        for sym, data in daily_data.items():
            formatted[sym] = {
                "daily": {k: v for k, v in data["daily"].items() if k not in ["Open", "High", "Low"]},
                "weekly": data["weekly"],
                "monthly": data["monthly"],
            }

        # JSON can't serialize pandas.Timestamp/datetime objects by default.
        # Recursively convert any Timestamp/datetime/numpy types to strings or scalars.
        def _make_serializable(obj):
            # pandas Timestamp
            if isinstance(obj, (pd.Timestamp, datetime)):
                return obj.strftime("%Y-%m-%d")
            # numpy scalar types
            try:
                import numpy as _np

                if isinstance(obj, _np.generic):
                    return obj.item()
            except Exception:
                pass
            # dict -> recurse
            if isinstance(obj, dict):
                return {k: _make_serializable(v) for k, v in obj.items()}
            # list/tuple -> recurse
            if isinstance(obj, (list, tuple)):
                return [_make_serializable(v) for v in obj]
            # fallback: leave as-is
            return obj

        formatted_safe = _make_serializable(formatted)
        positions_safe = _make_serializable(positions)

        formatted_data = json.dumps(formatted_safe, indent=2, ensure_ascii=False)
        formatted_positions = json.dumps(positions_safe, indent=2, ensure_ascii=False)

        # Build the user prompt without using an f-string to avoid accidental
        # interpolation of literal JSON braces in the sample output block.
        user_prompt = (
            "Here is the information you need:\n"
            "Today is "
            + str(today)
            + ".\nBelow is today's stock data (read from the processed CSV files):\n\n"
            + formatted_data
            + "\n\nCurrent positions are as follows:\n"
            + formatted_positions
            + "\n\nPlease analyze the short-term and mid-term trends for each stock and output BUY/SELL/HOLD signals.\n"
            + "Only output valid JSON arrays, do not explain your thinking process\n"
            + "          such as:\n"
            + "          [\n"
            + "            {\"symbol\": \"QQQ\", \"action\": \"HOLD\", \"confidence\": 0.70, \"reason\": \"Strong uptrend but RSI approaching overbought, MACD momentum slowing\"},\n"
            + "            {\"symbol\": \"TMUS\", \"action\": \"BUY\", \"confidence\": 0.65, \"reason\": \"Oversold daily RSI, potential reversal setup with price below EMA20\"},\n"
            + "            {\"symbol\": \"GLD\", \"action\": \"SELL\", \"confidence\": 0.75, \"reason\": \"Extremely overbought RSI on weekly and daily, high risk of pullback\"},\n"
            + "            {\"symbol\": \"NVO\", \"action\": \"BUY\", \"confidence\": 0.60, \"reason\": \"Neutral RSI with potential bottoming pattern, MACD turning positive\"}\n"
            + "          ]\n"
        )

        # ❌ 不再打印 verbose
        response = call_deepseek_api(
            model=self.model,
            system_prompt=self.prompt,
            user_prompt=user_prompt,
            timeout=300,
            retries=3,
            verbose=False
        )

        # ✅ 写入 API 输入 & 输出日志
        _write_api_log(
            request_payload={
                "model": self.model,
                "system_prompt": self.prompt,
                "user_prompt": user_prompt
            },
            response_text=response
        )


        # 如果响应为空字符串或仅包含空白，给出更明确的诊断并跳过解析
        if not response or (isinstance(response, str) and response.strip() == ""):
            print("❌ API 返回空响应（长度为0或仅空白）。这可能表示模型返回了空内容，或服务器返回了空体。")
            df = pd.DataFrame(columns=["symbol", "action", "confidence", "reason", "Date"])
        else:
            # 尝试解析 API 返回的 JSON；若解析失败（例如 API 错误或余额不足），创建空的 signals DataFrame
            try:
                parsed = json.loads(response)
                df = pd.DataFrame(parsed)
                df["Date"] = today
                print("✅ AI 决策输出 (parsed JSON raw):")
                try:
                    # print the parsed JSON array in full
                    print(json.dumps(parsed, ensure_ascii=False, indent=2))
                except Exception:
                    print(repr(parsed))

                # print("✅ AI 决策输出 (DataFrame, full):")
                # try:
                #     # print full dataframe without pandas truncation
                #     print(df.to_string(index=False))
                # except Exception:
                #     print(df)
            except Exception as e:
                print("❌ AI 输出解析失败:", e)
                # 打印原始响应全文以便排查
                df = pd.DataFrame(columns=["symbol", "action", "confidence", "reason", "Date"])

        # === 验证信号 ===
        validator = SignalValidator(positions)
        df_valid = validator.validate_signals(df)

        print("✅ 最终可执行信号:")
        print(df_valid)
        return df_valid

    # ------------------------------------------------------
    # 保存信号日志
    # ------------------------------------------------------
    def save_signals(self, df):
        # If nothing to save, skip
        if df.empty:
            return

        # Build executor-ready rows from incoming df (which is the validated signals)
        out_rows = []
        for _, row in df.iterrows():
            symbol = str(row.get("symbol", "")).upper()
            action = str(row.get("action", "")).upper()
            try:
                confidence = float(row.get("confidence", 0) or 0)
            except Exception:
                confidence = 0.0
            reason = row.get("reason", "") or ""
            date = row.get("Date", "")

            price = None
            # Try to fetch Close price for the given date from processed CSV
            try:
                proc_path = os.path.join("processed", f"{symbol.lower()}_daily_clean.csv")
                if os.path.exists(proc_path):
                    dfp = pd.read_csv(proc_path, parse_dates=["Date"]) 
                    # match by date; allow date string or Timestamp
                    if isinstance(date, str):
                        match_date = pd.to_datetime(date).date()
                    elif hasattr(date, "date"):
                        match_date = pd.to_datetime(date).date()
                    else:
                        match_date = None

                    if match_date is not None:
                        rowp = dfp[dfp["Date"].dt.date == match_date]
                        if not rowp.empty and "Close" in rowp.columns:
                            price = float(rowp.iloc[-1]["Close"])
            except Exception:
                price = None

            out_rows.append({
                "Symbol": symbol,
                "Action": action,
                "Confidence": confidence,
                "Reason": reason,
                "Date": date,
                "Price": price
            })

        df_signals = pd.DataFrame(out_rows)

        # Normalize text columns
        if not df_signals.empty:
            df_signals["Symbol"] = df_signals["Symbol"].astype(str).str.upper()
            df_signals["Action"] = df_signals["Action"].astype(str).str.upper()

        # Merge with existing Signals_path (single source of truth) and dedupe by Symbol/Action/Date keeping latest
        try:
            if os.path.exists(Signals_path):
                existing = pd.read_csv(Signals_path)
                combined = pd.concat([existing, df_signals], ignore_index=True)
            else:
                combined = df_signals

            # Normalize before dedupe
            if not combined.empty:
                if "Symbol" in combined.columns:
                    combined["Symbol"] = combined["Symbol"].astype(str).str.upper()
                if "Action" in combined.columns:
                    combined["Action"] = combined["Action"].astype(str).str.upper()

                # Drop duplicates keeping the latest occurrence
                combined = combined.drop_duplicates(subset=["Symbol", "Action", "Date"], keep="last")

            combined.to_csv(Signals_path, index=False)
            written = len(combined)
        except Exception:
            # On any failure, fallback to writing only the new batch
            df_signals.to_csv(Signals_path, index=False)
            written = len(df_signals)

        print(f"📝 已写入合并信号文件: {Signals_path} (共 {written} 条)")


