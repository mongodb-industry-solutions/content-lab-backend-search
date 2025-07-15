import os
import json
import logging
from dotenv import load_dotenv
from langchain_tavily import TavilySearch

# Configure logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

API_KEYS = os.getenv("TAVILY_API_KEYS", "").split(",")

def _invoke_with_key(key: str, query: str, max_results: int):
    """
    Try one key—returns parsed results or raises.
    """
    # temporarily override the env var that TavilySearch will pick up
    os.environ["TAVILY_API_KEY"] = key.strip()
    logger.debug(f"Using Tavily key: {key.strip()[:6]}…")
    search_tool = TavilySearch(max_results=max_results)
    raw = search_tool.invoke({"query": query})
    return json.loads(raw) if isinstance(raw, str) else raw

def search_topic(topic: str, max_results: int = 4) -> dict:
    query = f"what are the recent updates on {topic}"
    logger.info(f"Searching with query: '{query}'")

    last_error = None
    for key in API_KEYS:
        if not key:
            continue
        try:
            parsed = _invoke_with_key(key, query, max_results)
            # success!
            results = parsed.get("results", [])
            return {
                "topic": topic,
                "query": query,
                "result_count": len(results),
                "results": [
                    {
                        "title": r.get("title", "No Title"),
                        "snippet": (r.get("content", "")[:300] + "..."),
                        "url": r.get("url", "")
                    }
                    for r in results
                ]
            }
        except Exception as e:
            last_error = e
            logger.warning(f"Key {key.strip()[:6]}… failed, trying next: {e}")

    # if we get here, all keys failed
    logger.error(f"All API keys exhausted or invalid: {last_error}")
    return {
        "topic": topic,
        "query": query,
        "error": str(last_error),
        "results": []
    }

if __name__ == "__main__":
    example = "renewable energy technologies"
    print(json.dumps(search_topic(example), indent=2))