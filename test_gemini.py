"""
Quick Gemini API test — tries multiple models to find what works.
Usage:  python test_gemini.py
"""

from google import genai

API_KEY = "AIzaSyAC1k-OsiFQYWfyY1Z8b3HP2vzu-Og-Cms"
MODELS_TO_TEST = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-flash-latest",
    "gemini-2.5-flash-preview-04-17",
    "gemini-2.5-pro-preview-03-25",
]

PROMPT = "Say hello in one sentence."

def main():
    client = genai.Client(api_key=API_KEY)

    print(f"\n{'━' * 55}")
    print(f"  🧪 Gemini API Key Test")
    print(f"  Key: {API_KEY[:12]}...{API_KEY[-4:]}")
    print(f"{'━' * 55}\n")

    # 1. List available models
    print("  📋 Listing available models (first 20)...\n")
    try:
        models = list(client.models.list())
        for i, m in enumerate(models[:20]):
            print(f"     {i+1:>2}. {m.name}")
        if len(models) > 20:
            print(f"     ... and {len(models) - 20} more")
        print()
    except Exception as e:
        print(f"  ❌ Could not list models: {e}\n")

    # 2. Test each model
    working = []
    for model in MODELS_TO_TEST:
        print(f"  Testing {model}...", end=" ")
        try:
            r = client.models.generate_content(model=model, contents=PROMPT)
            text = r.text.strip()[:80]
            print(f"✅  → {text}")
            working.append(model)
        except Exception as e:
            err = str(e).split("\n")[0][:80]
            print(f"❌  → {err}")

    # 3. Summary
    print(f"\n{'━' * 55}")
    if working:
        print(f"  ✅ Working models: {', '.join(working)}")
        print(f"  👉 Recommended for chatbot: {working[0]}")
    else:
        print("  ❌ No models worked — check API key / billing.")
    print(f"{'━' * 55}\n")


if __name__ == "__main__":
    main()
