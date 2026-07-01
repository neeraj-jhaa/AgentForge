"""
Zero-API-key web search tool.

Uses DuckDuckGo's HTML endpoint so the whole project runs without
requiring the user to sign up for a search API just to try it out.
Swap this for Tavily / Brave / SerpAPI in production by keeping the
same `run(query) -> list[dict]` contract.
"""
import httpx
from bs4 import BeautifulSoup

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the public web for up-to-date information and return the top results (title, snippet, url).",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query."}
            },
            "required": ["query"],
        },
    },
}


def run(query: str, max_results: int = 5) -> list[dict]:
    try:
        resp = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (AgentForge/1.0)"},
            timeout=8.0,
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for r in soup.select(".result")[:max_results]:
            title_el = r.select_one(".result__a")
            snippet_el = r.select_one(".result__snippet")
            if not title_el:
                continue
            results.append(
                {
                    "title": title_el.get_text(strip=True),
                    "url": title_el.get("href", ""),
                    "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                }
            )
        return results or [{"title": "No results", "url": "", "snippet": ""}]
    except Exception as e:  # network may be unavailable in sandboxed envs
        return [{"title": "search_error", "url": "", "snippet": str(e)}]
