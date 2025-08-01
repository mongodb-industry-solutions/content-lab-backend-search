# ---topic_search.py---

# This file is used to search for recent updates related to a specific topic using Tavily Search Agent API and Bedrock LLM (as a fallback).

# Import the necessary libraries.
import os
import json
import logging
from dotenv import load_dotenv
from langchain_tavily import TavilySearch
from bedrock.anthropic_chat_completions import BedrockAnthropicChatCompletions

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def get_tavily_api_keys():
    """
    Get the Tavily API keys from the environment variables.
    """
    keys = os.getenv("TAVILY_API_KEYS", "")
    return [k.strip() for k in keys.split(",") if k.strip()]


def search_topic(topic, max_results: int = 4, max_retries: int = 2) -> dict:
    """
    Search for recent updates related to a specific topic using Tavily.
    Falls back to Bedrock LLM if all Tavily API keys fail.
    Args:
        topic: str, the topic to search for
        max_results: int, the maximum number of results to return
        max_retries: int, the maximum number of retries to try if the search fails
    Returns:
        dict: The search results
    """
    query = f"what are the recent updates on {topic}"
    logger.info(f"Searching with query: '{query}'")
    api_keys = get_tavily_api_keys()
    last_exception = None

    # Try Tavily API keys
    for api_key in api_keys:
        for attempt in range(max_retries):
            try:
                os.environ["TAVILY_API_KEY"] = api_key
                search_tool = TavilySearch(max_results=max_results)
                raw_results = search_tool.invoke({"query": query})

                if isinstance(raw_results, str):
                    parsed_results = json.loads(raw_results)
                else:
                    parsed_results = raw_results

                results_list = parsed_results.get("results", [])
                formatted_results = [
                    {
                        "title": r.get("title", "No Title"),
                        "snippet": r.get("content", "No Content")[:300] + "...",
                        "url": r.get("url", "No URL")
                    }
                    for r in results_list
                ]

                response = {
                    "topic": topic,
                    "query": query,
                    "result_count": len(formatted_results),
                    "results": formatted_results,
                    "source": "tavily"
                }
                return response

            except Exception as e:
                logger.warning(f"Attempt {attempt+1} failed for API key {api_key}: {str(e)}")
                last_exception = e
                continue

    # Fallback to Bedrock LLM if all Tavily API keys fail
    logger.info(f"All Tavily API keys failed for topic '{topic}'. Falling back to Bedrock LLM.")
    try:
        bedrock_llm = BedrockAnthropicChatCompletions()
        llm_response = bedrock_llm.predict(query)
        response = {
            "topic": topic,
            "query": query,
            "result_count": 1,
            "results": [{
                "title": "LLM Response",
                "snippet": llm_response,
                "url": None
            }],
            "source": "bedrock"
        }
        return response
    except Exception as e:
        logger.error(f"Bedrock LLM fallback also failed: {str(e)}")
        return {
            "topic": topic,
            "query": query,
            "error": f"All Tavily keys failed. Bedrock fallback failed: {str(e)}",
            "results": [],
            "source": "none"
        }

# ----Main function to run topic search------

if __name__ == "__main__":
    example_topic = "renewable energy technologies"
    results = search_topic(example_topic)
    print(json.dumps(results, indent=2))