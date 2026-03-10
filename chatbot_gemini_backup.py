"""
Stock Analysis Chatbot  —  Google Gemini LLM  +  MCP Tool Server
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

from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ── configuration ────────────────────────────────────────────────────────
GEMINI_API_KEY = "AIzaSyAChauWygpcsp1kr36SMhCWr6gzrpe25rg"
MODEL_NAME     = "gemini-flash-latest"        # tested & working
MAX_RETRIES    = 3
RETRY_BASE     = 2                            # exponential backoff base (secs)
MCP_SERVER     = "mcp_server.py"

SYSTEM_PROMPT = """\
You are an expert stock-market analyst assistant.
You have live tools to fetch real market data — always use them instead of guessing.

Available companies
  US   : Apple (AAPL), Google (GOOGL), Microsoft (MSFT), Amazon (AMZN), Tesla (TSLA)
  India: Reliance (RELIANCE.NS), TCS (TCS.NS), Infosys (INFY.NS),
         HDFC Bank (HDFCBANK.NS), Wipro (WIPRO.NS)

Tool-selection guide
  • Price / info          → get_stock_data
  • OHLCV history         → get_historical_data
  • Options chain         → get_options_chain
  • Greeks (Black-Scholes)→ calculate_greeks
  • News                  → get_news  (pass company_name AND symbol)
  • BUY/SELL/HOLD signal  → generate_trading_signal
  • Unusual activity      → detect_unusual_activity
  • Multi-stock scan      → scan_market  (filters: oversold, overbought,
                            high_volume, bullish, bearish, near_52w_low,
                            near_52w_high, all)
  • Sector heatmap        → get_sector_heatmap
  • List companies        → list_companies

  PORTFOLIO tools (saved in SQLite — users buy/sell via the portfolio menu):
  • List portfolio users         → list_portfolio_users
  • Portfolio P&L summary        → get_portfolio_summary  (pass user_id)
  • Transaction history          → get_transaction_history (pass user_id, optional symbol)

When the user asks about their portfolio, P&L, profit/loss, or holdings:
  1. First call list_portfolio_users to find the user_id.
  2. Then call get_portfolio_summary with that user_id.
  3. Provide a clear, detailed analysis:
     - Per-stock breakdown: shares owned, buy price vs current price, profit/loss
     - Overall totals: total invested, current value, net P&L, % return
     - Actionable recommendations: which stocks to hold, sell, or buy more of
     - Use get_stock_data or generate_trading_signal for deeper insight if needed

Always cite specific numbers from tool output.
Use ₹ for Indian stocks, $ for US stocks.
Be concise, but thorough when the user asks for detailed analysis.
"""


# ── helpers ──────────────────────────────────────────────────────────────

def _mcp_to_gemini_type(json_type: str) -> str:
    """Map JSON-Schema type string → Gemini Type enum string."""
    return {
        "string": "STRING", "number": "NUMBER", "integer": "INTEGER",
        "boolean": "BOOLEAN", "array": "ARRAY", "object": "OBJECT",
    }.get(json_type, "STRING")


def _build_gemini_tools(mcp_tools) -> list[types.Tool]:
    """Convert MCP tool definitions into google-genai Tool objects."""
    declarations = []
    for tool in mcp_tools:
        schema = tool.inputSchema or {}
        props = schema.get("properties", {})
        required = schema.get("required", [])

        # Build Gemini-compatible parameter schema
        gemini_props = {}
        for pname, pinfo in props.items():
            gemini_props[pname] = types.Schema(
                type=_mcp_to_gemini_type(pinfo.get("type", "string")),
                description=pinfo.get("description", pname),
            )

        params = None
        if gemini_props:
            params = types.Schema(
                type="OBJECT",
                properties=gemini_props,
                required=required,
            )

        declarations.append(
            types.FunctionDeclaration(
                name=tool.name,
                description=tool.description or tool.name,
                parameters=params,
            )
        )

    return [types.Tool(function_declarations=declarations)]


def _parse_tool_result(text: str):
    """Try to parse JSON text from MCP tool, fall back to plain string."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {"text": str(text)}


async def _send_with_retry(chat, message):
    """Send message to Gemini with exponential backoff on 429 rate-limit.
    Runs in a thread so the sync SDK call doesn't block the event loop."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            return await asyncio.to_thread(chat.send_message, message)
        except Exception as e:
            if "429" in str(e) and attempt < MAX_RETRIES:
                wait = RETRY_BASE ** (attempt + 1)
                print(f"  ⏳ Rate-limited — retrying in {wait}s (attempt {attempt + 1}/{MAX_RETRIES})...")
                await asyncio.sleep(wait)
            else:
                raise


# ── main loop ────────────────────────────────────────────────────────────

async def run_chatbot():
    print("\n" + "━" * 65)
    print("  🤖 Stock Analysis Chatbot  (Gemini + MCP)")
    print("     Type your question, or 'quit' to exit")
    print("━" * 65)

    # 1. Create Gemini client
    client = genai.Client(api_key=GEMINI_API_KEY)

    # 2. Connect to MCP server (stdio subprocess)
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[MCP_SERVER],
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 3. Discover tools from MCP server
            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            print(f"\n  ✅ MCP server connected — {len(tool_names)} tools loaded")
            for tn in tool_names:
                print(f"     • {tn}")
            print()

            # 4. Build Gemini tools + config
            gemini_tools = _build_gemini_tools(tools_result.tools)

            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=gemini_tools,
            )

            # 5. Start chat session
            chat = client.chats.create(model=MODEL_NAME, config=config)

            # 6. Interactive loop
            while True:
                try:
                    user_input = await asyncio.to_thread(
                        input, "  📝 You: "
                    )
                except (EOFError, KeyboardInterrupt):
                    print("\n  👋 Goodbye!\n")
                    break

                user_input = user_input.strip()
                if not user_input:
                    continue
                if user_input.lower() in ("quit", "exit", "bye", "q"):
                    print("\n  👋 Goodbye!\n")
                    break

                try:
                    print("  ⏳ Thinking...")
                    t0 = time.time()
                    response = await _send_with_retry(chat, user_input)
                    print(f"  ✓ LLM responded in {time.time()-t0:.1f}s")

                    # Iteratively resolve tool calls
                    MAX_ROUNDS = 10
                    for _ in range(MAX_ROUNDS):
                        # Collect function_call parts
                        fn_calls = []
                        if response.candidates and response.candidates[0].content:
                            for part in response.candidates[0].content.parts:
                                if part.function_call and part.function_call.name:
                                    fn_calls.append(part)

                        if not fn_calls:
                            break

                        # Execute each via MCP, build function_response parts
                        fn_response_parts = []
                        for part in fn_calls:
                            fc = part.function_call
                            args = dict(fc.args) if fc.args else {}
                            print(
                                f"  🔧 Calling: {fc.name}"
                                f"({json.dumps(args, default=str)})"
                            )

                            t1 = time.time()
                            try:
                                result = await asyncio.wait_for(
                                    session.call_tool(fc.name, args),
                                    timeout=90,
                                )
                                text = (
                                    result.content[0].text
                                    if result.content
                                    else "{}"
                                )
                                print(f"  ✓ Tool returned in {time.time()-t1:.1f}s ({len(text)} chars)")
                            except asyncio.TimeoutError:
                                text = json.dumps({"error": "Tool timed out after 90s"})
                                print(f"  ⚠️  Tool timed out after 90s")
                            except Exception as te:
                                text = json.dumps({"error": str(te)})
                                print(f"  ⚠️  Tool error: {te}")

                            parsed = _parse_tool_result(text)

                            fn_response_parts.append(
                                types.Part.from_function_response(
                                    name=fc.name,
                                    response={"result": parsed},
                                )
                            )

                        # Send function results back to Gemini
                        print("  ⏳ AI is analyzing the data...")
                        t2 = time.time()
                        response = await _send_with_retry(chat, fn_response_parts)
                        print(f"  ✓ Analysis complete in {time.time()-t2:.1f}s")

                    # Print final answer
                    if response.text:
                        print(f"\n  🤖 Assistant:\n{response.text}\n")
                    else:
                        print("\n  🤖 (no text response)\n")

                except Exception as e:
                    print(f"\n  ❌ Error: {e}\n")


# ── entry ────────────────────────────────────────────────────────────────
def main():
    asyncio.run(run_chatbot())

if __name__ == "__main__":
    main()
