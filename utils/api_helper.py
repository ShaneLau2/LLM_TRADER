# utils/api_helper.py
import requests
import json
import time
from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, AI_MODEL, Model_Temperature, Model_Max_Tokens
from requests.exceptions import Timeout, RequestException


def call_deepseek_api(model: str, system_prompt: str, user_prompt: str, timeout: int = 300, retries: int = 3, verbose: bool = False):
    """调用 DeepSeek API 并返回模型输出。

    Parameters:
    - model: 模型名称（目前未使用函数参数里的 model，而是使用 config 中的 AI_MODEL）。
    - system_prompt: 系统提示词
    - user_prompt: 用户提示词
    - timeout: 单次请求超时时间（秒）
    - retries: 重试次数
    - verbose: 若为 True，打印要发送的 payload 和响应信息到命令行

    返回: 成功时返回模型输出字符串；失败时返回字符串 "[]"。
    """
    url = f"{DEEPSEEK_API_URL}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": Model_Temperature,
        "max_tokens": Model_Max_Tokens,
        "stream": False       # ✅ 确保不是流式输出
    }

    # 将 payload 字符串化以便打印（不包含 Authorization）
    payload_str = json.dumps(payload, ensure_ascii=False)

    for attempt in range(1, retries + 1):
        try:
            if verbose:
                # 打印简洁的信息：URL、payload（不打印完整 API KEY）和 attempt
                masked_key = DEEPSEEK_API_KEY[:4] + "..." if DEEPSEEK_API_KEY else "(no-key)"
                print(f"[API] POST {url}  attempt={attempt}/{retries}")
                print(f"[API] Authorization: Bearer {masked_key}")
                print("[API] Payload:")
                print(payload_str)

            start = time.time()
            resp = requests.post(url, headers=headers, data=payload_str.encode('utf-8'), timeout=timeout)
            elapsed = time.time() - start

            if verbose:
                print(f"[API] Response status: {resp.status_code}  elapsed={elapsed:.2f}s")

            if resp.status_code == 200:
                try:
                    resp_json = resp.json()
                    # When verbose, print the returned JSON keys and a truncated dump to diagnose empty content cases
                    if verbose:
                        try:
                            import pprint
                            print("[API] Full response JSON (truncated):")
                            pprint.pprint(resp_json)
                        except Exception:
                            print("[API] (unable to pretty-print full JSON)")

                    # Persist full response to logs for post-mortem (only when verbose)
                    try:
                        import os
                        from datetime import datetime
                        os.makedirs("logs", exist_ok=True)
                        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
                        fname = f"logs/api_response_{ts}.json"
                        with open(fname, "w", encoding="utf-8") as f:
                            json.dump(resp_json, f, ensure_ascii=False, indent=2)
                        print(f"[API] Full response saved to: {fname}")
                    except Exception as _:
                        if verbose:
                            print("[API] 无法将完整响应写入日志文件：", _)

                    # extract content if present
                    message = resp_json.get("choices", [{}])[0].get("message", {})
                    result = message.get("content", "")
                    print("[API] Model output (full):")
                    print(result)  # ✅ 原样打印，不截断
                    return result
                except Exception as e:
                    print("[API] JSON 解析模型输出失败:", e)
                    return "[]"
            else:
                # 非 200 响应：打印并按重试策略继续
                print(f"⚠️ API返回错误 {resp.status_code}: {resp.text}")
        except Timeout:
            print(f"⚠️ 请求超时 (timeout={timeout}s) on attempt {attempt}/{retries}")
        except RequestException as e:
            print(f"⚠️ 请求异常 on attempt {attempt}/{retries}: {e}")

        # 简单退避
        time.sleep(2 * attempt)

    return "[]"


def ping_deepseek_api(timeout: int = 20, verbose: bool = True):
    """发送一个非常小的请求以确认 API 可达性并测量响应时间。

    返回一个字典，包含 status_code、text（或 error）、elapsed_seconds。
    """
    url = f"{DEEPSEEK_API_URL}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    # 使用最小化的请求以尽量少消耗配额
    ping_payload = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": "ping"},
            {"role": "user", "content": "ping"}
        ],
        "temperature": 0.0,
        "max_tokens": 1
    }

    payload_str = json.dumps(ping_payload, ensure_ascii=False)

    try:
        if verbose:
            masked_key = DEEPSEEK_API_KEY[:4] + "..." if DEEPSEEK_API_KEY else "(no-key)"
            print(f"[PING] POST {url}")
            print(f"[PING] Authorization: Bearer {masked_key}")
            print("[PING] Payload:")
            print(payload_str)

        start = time.time()
        resp = requests.post(url, headers=headers, data=payload_str.encode('utf-8'), timeout=timeout)
        elapsed = time.time() - start

        if verbose:
            print(f"[PING] status={resp.status_code} elapsed={elapsed:.2f}s")
            print("[PING] resp:", resp.text[:5000])

        return {"status_code": resp.status_code, "text": resp.text, "elapsed": elapsed}
    except Timeout:
        print(f"[PING] 请求超时 (timeout={timeout}s)")
        return {"error": "timeout", "elapsed": timeout}
    except RequestException as e:
        print(f"[PING] 请求异常: {e}")
        return {"error": str(e)}
