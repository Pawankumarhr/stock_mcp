"""
Stock Analysis Chatbot  —  RapidAPI Claude LLM  +  MCP Tool Server
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
import http.client
import re

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ── configuration ────────────────────────────────────────────────────────
RAPIDAPI_KEY  = "6b83508bd3msh714829b57afdbe3p1a7b49jsn7f6ddf4fc276"
RAPIDAPI_HOST = "open-ai21.p.rapidapi.com"
MAX_RETRIES   = 3
MCP_SERVER    = "mcp_server.py"

TOOL_DESCRIPTIONS = """\
You have access to these tools. To call a tool, reply with EXACTLY this format on its own line:
TOOL_CALL: {"name": "<tool_name>", "args": {<arguments>}}

Available tools:

1. list_companies() → List all tracked companies with ticker symbols.
2. get_stock_data(symbol) → Live stock data: price, open, high, low, volume, market cap, PE, dividend yield, beta, 52-week range, sector. Use .NS suffix for Indian NSE stocks (e.g. RELIANCE.NS).
3. get_historical_data(symbol, period="1mo") → Historical OHLCV. period: 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max.
4. get_options_chain(symbol) → Options chain (calls & puts). Indian stocks use ADR mapping.
5. calculate_greeks(symbol) → Black-Scholes Options Greeks (Delta, Gamma, Theta, Vega).
6. get_news(company_name, symbol) → Latest news from NewsAPI + Google News.
7. generate_trading_signal(symbol) → BUY/SELL/HOLD signal with confidence %.
8. detect_unusual_activity(symbol) → Volume spikes, price gaps, volatility bursts, 52-week proximity.
9. scan_market(filter_criteria="all") → Scan all companies. Filters: oversold, overbought, high_volume, bullish, bearish, near_52w_low, near_52w_high, all.
10. get_sector_heatmap() → Sector performance heatmap.
11. list_portfolio_users() → List all registered portfolio users with IDs.
12. get_portfolio_summary(user_id) → Portfolio with LIVE P&L per holding + totals. Pass numeric user_id.
13. get_transaction_history(user_id, symbol="") → Transaction history, optionally filtered by symbol.

IMPORTANT RULES:
- Only ONE TOOL_CALL per response.
- After you receive tool results, analyze them and give a clear answer with specific numbers.
- Use ₹ for Indian (.NS) stocks, $ for US stocks.
- For portfolio questions: first call list_portfolio_users, then get_portfolio_summary with the user_id.
- NEVER guess data — always use tools to fetch real data.
- If you don't need a tool, just answer directly without TOOL_CALL.
"""

SYSTEM_PROMPT = f"""\
You are an expert stock-market analyst assistant.

Available companies:
  US   : Apple (AAPL), Google (GOOGL), Microsoft (MSFT), Amazon (AMZN), Tesla (TSLA)
  India: Reliance (RELIANCE.NS), TCS (TCS.NS), Infosys (INFY.NS), HDFC Bank (HDFCBANK.NS), Wipro (WIPRO.NS)

{TOOL_DESCRIPTIONS}
"""


# ── RapidAPI Claude call ─────────────────────────────────────────────────

def _call_rapidapi(messages: list[dict]) -> str:
    """Send messages to RapidAPI Claude3 endpoint and return the response text."""
    for attempt in range(MAX_RETRIES):
        try:
            conn = http.client.HTTPSConnection(RAPIDAPI_HOST, timeout=60)
            payload = json.dumps({
                "messages": messages,
                "web_access": False,
            })
            headers = {
                "x-rapidapi-key": RAPIDAPI_KEY,
                "x-rapidapi-host": RAPIDAPI_HOST,
                "Content-Type": "application/json",
            }
            conn.request("POST", "/claude3", payload, headers)
            res = conn.getresponse()
            data = res.read().decode("utf-8")
            conn.close()

            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    return (
                        parsed.get("result")
                        or parsed.get("response")
                        or parsed.get("content")
                        or parsed.get("message")
                        or parsed.get("text")
                        or parsed.get("answer")
                        or json.dumps(parsed)
                    )
                return str(parsed)
            except json.JSONDecodeError:
                return data
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** (attempt + 1))
            else:
                raise RuntimeError(f"RapidAPI call failed after {MAX_RETRIES} retries: {e}")


async def _call_rapidapi_async(messages: list[dict]) -> str:
    """Async wrapper around the synchronous HTTP call."""
    return await asyncio.to_thread(_call_rapidapi, messages)


def _parse_tool_call(text: str) -> tuple[dict | None, str]:
    """Extract TOOL_CALL from LLM response.
    Returns (tool_call_dict, remaining_text) or (None, full_text)."""
    pattern = r'TOOL_CALL:\s*(\{[^}]*\})'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            call = json.loads(match.group(1))
            if "name" in call:
                remaining = text[:match.start()].strip()
                return call, remaining
        except json.JSONDecodeError:
            pass
    return None, text


# ── main loop ────────────────────────────────────────────────────────────

async def run_chatbot():
    print("\n" + "━" * 65)
    print("  🤖 Stock Analysis Chatbot  (RapidAPI Claude + MCP)")
    print("     Type your question, or 'quit' to exit")
    print("━" * 65)

    # Connect to MCP server
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

            # Conversation history — prime with system context
            messages = [
                {"role": "user", "content": SYSTEM_PROMPT + "\nAcknowledge briefly that you understand your role and available tools."}
            ]
            print("  ⏳ Initializing AI...")
            init_reply = await _call_rapidapi_async(messages)
            messages.append({"role": "assistant", "content": init_reply})
            print("  ✅ AI ready!\n")

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
                        print("  ⏳ Thinking..." if round_num == 0 else "  ⏳ AI is analyzing the data...")
                        t0 = time.time()
                        reply = await _call_rapidapi_async(messages)
                        print(f"  ✓ AI responded in {time.time()-t0:.1f}s")

                        tool_call, remaining_text = _parse_tool_call(reply)

                        if tool_call is None:
                            # Final answer
                            messages.append({"role": "assistant", "content": reply})
                            print(f"\n  🤖 Assistant:\n{reply}\n")
                            break

                        # Execute tool via MCP
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
                            print("  ⚠️  Tool timed out after 90s")
                        except Exception as te:
                            text = json.dumps({"error": str(te)})
                            print(f"  ⚠️  Tool error: {te}")

                        # Truncate very large results
                        if len(text) > 8000:
                            text = text[:8000] + "\n...(truncated)"

                        messages.append({"role": "assistant", "content": reply})
                        messages.append({
                            "role": "user",
                            "content": f"TOOL_RESULT for {tool_name}:\n{text}\n\nNow analyze this data and give a clear, detailed answer with specific numbers. Do NOT call another tool unless absolutely necessary."
                        })
                    else:
                        print("  ⚠️  Max tool rounds reached.")

                except Exception as e:
                    print(f"\n  ❌ Error: {e}\n")

                # Keep conversation manageable
                if len(messages) > 30:
                    messages = messages[:2] + messages[-24:]


# ── entry ────────────────────────────────────────────────────────────────
def main():
    asyncio.run(run_chatbot())

if __name__ == "__main__":
    main()
