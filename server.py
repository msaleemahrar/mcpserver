import os
import httpx
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.dataforseo.com"
AUTH = (os.environ["DATAFORSEO_LOGIN"], os.environ["DATAFORSEO_PASSWORD"])

PORT = int(os.environ.get("PORT", 8000))

mcp = FastMCP("Keyword Research")


def _post(path: str, payload: list) -> dict:
    resp = httpx.post(f"{BASE_URL}{path}", auth=AUTH, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ── 1. Keyword Volume + Difficulty ───────────────────────────────────────────

@mcp.tool()
def keyword_volume(keywords: list[str], location_code: int = 2840) -> dict:
    """
    Returns monthly search volume for a list of keywords.
    location_code: DataForSEO location code (default 2840 = United States).
    """
    payload = [{"keywords": keywords, "location_code": location_code, "language_code": "en"}]
    data = _post("/v3/keywords_data/google/search_volume/live", payload)
    results = {}
    for item in data.get("tasks", [{}])[0].get("result", []) or []:
        results[item["keyword"]] = {
            "volume": item.get("search_volume"),
            "competition": item.get("competition"),
            "cpc": item.get("cpc"),
            "monthly_searches": item.get("monthly_searches"),
        }
    return results


@mcp.tool()
def keyword_difficulty(keywords: list[str], location_code: int = 2840) -> dict:
    """
    Returns SEO keyword difficulty (0–100) for a list of keywords.
    location_code: DataForSEO location code (default 2840 = United States).
    """
    payload = [{"keywords": keywords, "location_code": location_code, "language_code": "en"}]
    data = _post("/v3/dataforseo_labs/google/keyword_difficulty/live", payload)
    results = {}
    for item in data.get("tasks", [{}])[0].get("result", []) or []:
        results[item["keyword"]] = {"difficulty": item.get("keyword_difficulty")}
    return results


# ── 2. Volume by Region ───────────────────────────────────────────────────────

@mcp.tool()
def keyword_volume_by_region(keyword: str, location_codes: list[int] = None) -> dict:
    """
    Returns search volume for a single keyword across multiple regions.
    location_codes: list of DataForSEO location codes.
    Defaults to US, UK, CA, AU, DE, FR, IN.
    """
    if location_codes is None:
        location_codes = [2840, 2826, 2124, 2036, 2276, 2250, 2356]

    payload = [
        {"keywords": [keyword], "location_code": code, "language_code": "en"}
        for code in location_codes
    ]
    results = {}
    # DataForSEO accepts up to 100 tasks per request
    data = _post("/v3/keywords_data/google/search_volume/live", payload)
    for task in data.get("tasks", []):
        for item in task.get("result", []) or []:
            loc = task.get("data", {}).get("location_code")
            results[str(loc)] = {
                "volume": item.get("search_volume"),
                "cpc": item.get("cpc"),
            }
    return results


# ── 3. Topic Clustering ───────────────────────────────────────────────────────

@mcp.tool()
def topic_cluster(seed_keyword: str, location_code: int = 2840, limit: int = 100) -> dict:
    """
    Expands a seed keyword into related keywords and groups them by topic/intent.
    Returns clusters keyed by topic label with keyword lists.
    """
    payload = [{
        "keyword": seed_keyword,
        "location_code": location_code,
        "language_code": "en",
        "limit": limit,
        "include_seed_keyword": True,
    }]
    data = _post("/v3/dataforseo_labs/google/keyword_ideas/live", payload)

    raw = data.get("tasks", [{}])[0].get("result", []) or []
    clusters: dict[str, list] = {}

    for item in raw:
        keyword = item.get("keyword", "")
        # Group by broad category using the keyword's top-level search intent tag
        intent = (item.get("search_intent_info") or {}).get("main_intent", "informational")
        topic = intent.capitalize()
        clusters.setdefault(topic, []).append({
            "keyword": keyword,
            "volume": (item.get("keyword_info") or {}).get("search_volume"),
            "difficulty": (item.get("keyword_properties") or {}).get("keyword_difficulty"),
        })

    return clusters


# ── 4. Backlinks Summary ──────────────────────────────────────────────────────

@mcp.tool()
def backlinks_summary(target: str) -> dict:
    """
    Returns a backlink summary for a domain or URL.
    target: domain (e.g. 'example.com') or full URL.
    """
    payload = [{"target": target, "include_subdomains": True}]
    data = _post("/v3/backlinks/summary/live", payload)
    result = (data.get("tasks", [{}])[0].get("result", []) or [{}])[0]
    return {
        "external_links_count": result.get("external_links_count"),
        "referring_domains": result.get("referring_domains"),
        "referring_ips": result.get("referring_ips"),
        "domain_rank": result.get("rank"),
        "backlinks_spam_score": result.get("backlinks_spam_score"),
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=PORT)
