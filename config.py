# config.py
# SYMBOLS = ["AAPL", "MSFT", "NVDA","AMZN","GOOGL"]
SYMBOLS = ["tssi", "bbai","tqqq","nvda"]
START_DATE = "2025-01-01"
DATA_PATH = "data/"
Signals_path="logs/ai_signals_log.csv"
FINNHUB_API_KEY = ""
API_LOG_PATH = "logs/api_debug_log.jsonl"


# AI 模型配置
DEEPSEEK_API_KEY = ""
DEEPSEEK_API_URL = "https://api.deepseek.com"
AI_MODEL = "deepseek-chat"  
Model_Temperature = 0.2
Model_Max_Tokens = 2500
AGENT_SYSTEM_PROMPT = """
        You are a stock fundamental analysis trading assistant.

        Your goals are:

        - Think and reason by calling available tools.
        - You need to think about the prices of various stocks and their returns.
        - Your long-term goal is to maximize returns through this portfolio.
        - Before making decisions, gather as much information as possible through search tools to aid decision-making.

        Thinking standards:

        - Clearly show key intermediate steps:
          - Read input of yesterday's positions and today's prices
          - Update valuation and adjust weights for each target (if strategy requires)

        Notes:

        - You don't need to request user permission during operations, you can execute directly
        - You must execute operations by calling tools, directly output operations will not be accepted
        - Only output valid JSON arrays, do not explain your thinking process
          such as:
          [
            {"symbol": "QQQ", "action": "HOLD", "confidence": 0.70, "reason": "Strong uptrend but RSI approaching overbought, MACD momentum slowing"},
            {"symbol": "TMUS", "action": "BUY", "confidence": 0.65, "reason": "Oversold daily RSI, potential reversal setup with price below EMA20"},
            {"symbol": "GLD", "action": "SELL", "confidence": 0.75, "reason": "Extremely overbought RSI on weekly and daily, high risk of pullback"},
            {"symbol": "NVO", "action": "BUY", "confidence": 0.60, "reason": "Neutral RSI with potential bottoming pattern, MACD turning positive"}
          ]
        """
Min_confidence=0.6

# 手续费设置
TRADE_FEE = 2.0
