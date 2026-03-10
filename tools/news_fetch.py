import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

NEWSAPI_KEY = "490fbe4931ab47799228bff5c48f13c8"


def fetch_newsapi(query: str, max_results: int = 5) -> list:
    """Fetch news from NewsAPI.org."""
    from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    url = (
        f"https://newsapi.org/v2/everything?"
        f"q={query}&from={from_date}&sortBy=popularity"
        f"&pageSize={max_results}&apiKey={NEWSAPI_KEY}"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "ok":
            return [{"error": data.get("message", "Unknown error")}]
        articles = []
        for a in data.get("articles", [])[:max_results]:
            articles.append({
                "title": a.get("title", "N/A"),
                "description": a.get("description", ""),
                "source": a.get("source", {}).get("name", "N/A"),
                "url": a.get("url", "N/A"),
                "published": a.get("publishedAt", "N/A"),
            })
        return articles
    except Exception as e:
        return [{"error": str(e)}]


def fetch_google_news(query: str, max_results: int = 5) -> list:
    """Scrape Google News RSS for headlines related to a stock/company."""
    url = f"https://news.google.com/rss/search?q={query}+stock+market&hl=en&gl=US&ceid=US:en"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "xml")
        items = soup.find_all("item", limit=max_results)
        news = []
        for item in items:
            news.append({
                "title": item.title.text if item.title else "N/A",
                "link": item.link.text if item.link else "N/A",
                "published": item.pubDate.text if item.pubDate else "N/A",
                "source": item.source.text if item.source else "N/A",
            })
        return news
    except Exception as e:
        return [{"error": str(e)}]


def fetch_news(company_name: str, symbol: str) -> dict:
    """Fetch news from NewsAPI + Google News RSS."""
    clean_symbol = symbol.replace(".NS", "").replace(".BO", "")

    newsapi_news = fetch_newsapi(f"{company_name} stock")
    google_news = fetch_google_news(company_name)

    return {
        "company": company_name,
        "symbol": symbol,
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "newsapi": newsapi_news,
        "google_news": google_news,
    }


def display_news(news_data: dict):
    """Pretty-print news in the terminal."""
    print(f"\n{'═' * 60}")
    print(f"  📰 NEWS & MARKET UPDATES — {news_data['company']}")
    print(f"{'═' * 60}")

    # NewsAPI results
    if news_data.get("newsapi"):
        print(f"\n  ── NewsAPI (Top Headlines) ──")
        for i, n in enumerate(news_data["newsapi"], 1):
            if "error" in n:
                print(f"  ❌ NewsAPI Error: {n['error']}")
                break
            print(f"  {i}. {n['title']}")
            desc = n.get('description', '')
            if desc:
                print(f"     {desc[:100]}...")
            print(f"     Source: {n['source']}  |  {n['published']}")
            print(f"     🔗 {n['url'][:80]}")

    # Google News results
    if news_data.get("google_news"):
        print(f"\n  ── Google News ──")
        for i, n in enumerate(news_data["google_news"], 1):
            if "error" in n:
                print(f"  ❌ Error: {n['error']}")
                break
            print(f"  {i}. {n['title']}")
            print(f"     Source: {n['source']}  |  {n['published']}")
            print(f"     🔗 {n['link'][:80]}")
    else:
        print(f"\n  No Google News found.")

    print(f"{'═' * 60}")
