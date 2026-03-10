"""
Stock Analysis Chatbot  —  ChatGPT (gpt-4o-mini)  +  MCP Tool Server
Ask natural-language questions; the LLM automatically calls the right
stock-market tools via the MCP server running as a subprocess.

Usage:
    python chatbot.py
"""

import asyncio
import json
import sys
import os
import time
import re
import base64
import requests

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ── configuration ────────────────────────────────────────────────────────
_ENCODED_KEY   = "c2stcHJvai1xUmo2eG9YY0YtdjZ5RUQ2dnpmcWFyVGlTTm9fWWV6QUNDMWpvbWhGVkh1dWtKcTRIXzBRUVBmV3B2MUtDTGdPWXZCdmpjb0FBUlQzQmxia0ZKU3dZdkVlb19LWVVvNUY3VWdIQlZ4ZVVGbUdfaklLZ0NHYVpwTGhJWm5RVWZiRWhiNjJlSndyT1hKRHdRT19JRmt6RWMyanFUMEE="
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or base64.b64decode(_ENCODED_KEY).decode()
OPENAI_URL     = "https://api.openai.com/v1/chat/completions"
MODEL          = "gpt-4o-mini"
MAX_RETRIES    = 3
MCP_SERVER     = "mcp_server.py"

SYSTEM_PROMPT = """\
You are an expert stock analyst assistant with live market tools.

Companies: AAPL, GOOGL, MSFT, AMZN, TSLA (US); RELIANCE.NS, TCS.NS, INFY.NS, HDFCBANK.NS, WIPRO.NS (India).

To fetch data, reply with EXACTLY (one per message):
TOOL_CALL: {"name": "<tool>", "args": {<arguments>}}

Tools:
1. list_companies()
2. get_stock_data(symbol) — live price, volume, PE, 52w range. Use .NS for Indian stocks.
3. get_historical_data(symbol, period="1mo") — OHLCV history.
4. get_options_chain(symbol) — calls & puts.
5. calculate_greeks(symbol) — Black-Scholes Greeks.
6. get_news(company_name, symbol) — latest headlines.
7. generate_trading_signal(symbol) — BUY/SELL/HOLD with confidence %.
8. detect_unusual_activity(symbol) — volume spikes, price gaps.
9. scan_market(filter_criteria="all") — filters: oversold,overbought,high_volume,bullish,bearish,near_52w_low,near_52w_high,all.
10. get_sector_heatmap() — sector performance.
11. list_portfolio_users() — registered users.
12. get_portfolio_summary(user_id) — holdings with live P&L.
13. get_transaction_history(user_id, symbol="") — buy/sell history.

Rules:
- ONE TOOL_CALL per reply. After receiving TOOL_RESULT, analyze it thoroughly.
- Use ₹ for .NS stocks, $ for US stocks.
- Never fabricate data — always use a tool.
- For portfolio: first list_portfolio_users, then get_portfolio_summary.
- Give confident, specific answers with numbers, comparison and actionable insights.
"""


# ── ChatGPT API call ─────────────────────────────────────────────────────

def _call_llm(messages: list[dict]) -> str:
    """Call OpenAI ChatGPT (gpt-4o-mini) with retry + robust error handling."""
    last_err = "Unknown error"
    for attempt in range(MAX_RETRIES):
        resp = None
        try:
            resp = requests.post(
                OPENAI_URL,
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL,
                    "messages": messages,
                    "temperature": 0.4,
                    "max_tokens": 2048,
                },
                timeout=60,
            )
            if resp.status_code == 429:
                last_err = "Rate-limited (429)"
                wait = 2 ** (attempt + 1)
                print(f"  ⚠️  Rate-limited, retrying in {wait}s...")
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                last_err = f"HTTP {resp.status_code}: {resp.text[:300]}"
                print(f"  ⚠️  {last_err}")
                if resp.status_code in (401, 403):
                    break  # auth errors are non-retryable
                continue  # retry on 500/502/503
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise ValueError(f"No choices in response: {json.dumps(data)[:300]}")
            content = choices[0].get("message", {}).get("content", "")
            if not content:
                raise ValueError(f"Empty content in response")
            return content
        except requests.exceptions.Timeout:
            last_err = "Request timed out (60s)"
            print(f"  ⚠️  Timeout on attempt {attempt+1}/{MAX_RETRIES}")
        except requests.exceptions.ConnectionError:
            last_err = "Connection error — check internet"
            print(f"  ⚠️  Connection error on attempt {attempt+1}/{MAX_RETRIES}")
        except ValueError as e:
            raise RuntimeError(str(e))
        except Exception as e:
            last_err = str(e)
            print(f"  ⚠️  Error on attempt {attempt+1}/{MAX_RETRIES}: {last_err}")
        if attempt < MAX_RETRIES - 1:
            time.sleep(2)
    raise RuntimeError(f"ChatGPT API failed after {MAX_RETRIES} attempts: {last_err}")


async def _call_llm_async(messages: list[dict]) -> str:
    return await asyncio.to_thread(_call_llm, messages)


def _parse_tool_call(text: str) -> tuple[dict | None, str]:
    """Extract TOOL_CALL from LLM response.
    Handles nested braces like {"args": {"symbol": "TCS.NS"}}."""
    marker = re.search(r'TOOL_CALL:\s*\{', text)
    if not marker:
        return None, text
    start = marker.end() - 1
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                json_str = text[start:i + 1]
                try:
                    call = json.loads(json_str)
                    if "name" in call:
                        remaining = text[:marker.start()].strip()
                        return call, remaining
                except json.JSONDecodeError:
                    break
    return None, text


# ── main loop ────────────────────────────────────────────────────────────

async def run_chatbot():
    print("\n" + "━" * 65)
    print("  🤖 Stock Analysis Chatbot  (ChatGPT gpt-4o-mini + MCP Tools)")
    print("     Type your question, or 'quit' to exit")
    print("━" * 65)

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[MCP_SERVER],
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            print(f"\n  ✅ MCP server connected — {len(tool_names)} tools loaded")
            for tn in tool_names:
                print(f"     • {tn}")
            print()

            # Conversation with proper system message
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
            ]

            # Interactive loop
            while True:
                try:
                    user_input = await asyncio.to_thread(input, "  📝 You: ")
                except (EOFError, KeyboardInterrupt):
                    print("\n  👋 Goodbye!\n")
                    break

                user_input = user_input.strip()
                if not user_input:
                    continue
                if user_input.lower() in ("quit", "exit", "bye", "q"):
                    print("\n  👋 Goodbye!\n")
                    break

                messages.append({"role": "user", "content": user_input})

                try:
                    MAX_ROUNDS = 8
                    for round_num in range(MAX_ROUNDS):
                        print("  ⏳ Thinking..." if round_num == 0 else "  ⏳ Analyzing data...")
                        t0 = time.time()
                        reply = await _call_llm_async(messages)
                        elapsed = time.time() - t0
                        print(f"  ✓ AI responded in {elapsed:.1f}s")

                        tool_call, remaining_text = _parse_tool_call(reply)

                        if tool_call is None:
                            messages.append({"role": "assistant", "content": reply})
                            print(f"\n  🤖 Assistant:\n{reply}\n")
                            break

                        tool_name = tool_call["name"]
                        tool_args = tool_call.get("args", {})
                        tool_args_str = {k: str(v) if not isinstance(v, str) else v for k, v in tool_args.items()}

                        if remaining_text:
                            print(f"  💭 {remaining_text}")
                        print(f"  🔧 Calling: {tool_name}({json.dumps(tool_args, default=str)})")

                        t1 = time.time()
                        try:
                            result = await asyncio.wait_for(
                                session.call_tool(tool_name, tool_args_str),
                                timeout=90,
                            )
                            text = result.content[0].text if result.content else "{}"
                            print(f"  ✓ Tool returned in {time.time()-t1:.1f}s ({len(text)} chars)")
                        except asyncio.TimeoutError:
                            text = json.dumps({"error": "Tool timed out after 90s"})
                            print("  ⚠️  Tool timed out")
                        except Exception as te:
                            text = json.dumps({"error": str(te)})
                            print(f"  ⚠️  Tool error: {te}")

                        if len(text) > 12000:
                            text = text[:12000] + "\n...(truncated)"

                        messages.append({"role": "assistant", "content": reply})
                        messages.append({
                            "role": "user",
                            "content": f"TOOL_RESULT for {tool_name}:\n{text}\n\nAnalyze this data thoroughly. Provide specific numbers, comparisons, and a clear recommendation."
                        })
                    else:
                        print("  ⚠️  Max tool rounds reached.")

                except Exception as e:
                    print(f"\n  ❌ Error: {e}\n")

                # Keep conversation manageable — keep system + last 28 messages
                if len(messages) > 32:
                    messages = messages[:1] + messages[-28:]


# ── entry ────────────────────────────────────────────────────────────────
def main():
    asyncio.run(run_chatbot())

if __name__ == "__main__":
    main()
