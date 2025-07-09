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

def search_topic(topic, max_results: int = 4) -> dict:
    """
    Search for recent updates related to a specific topic using Tavily.
    
    Args:
        topic (str): The topic to search for
        max_results (int): Maximum number of results to return
        
    Returns:
        dict: JSON-formatted search results
    """
    # Format query to get recent updates on the topic
    query = f"what are the recent updates on {topic}"
    logger.info(f"Searching with query: '{query}'")
    
    try:
        # Initialize Tavily search tool
        search_tool = TavilySearch(max_results=max_results)
        
        # Use Tavily to search with the formatted query
        raw_results = search_tool.invoke({"query": query})
        
        # Parse the response - TavilySearch returns either a string or dict
        if isinstance(raw_results, str):
            parsed_results = json.loads(raw_results)
        else:
            parsed_results = raw_results
            
        # Extract the results list
        results_list = parsed_results.get("results", [])
        
        # Format the results to ensure consistent structure
        formatted_results = []
        for result in results_list:
            formatted_results.append({
                "title": result.get("title", "No Title"),
                "snippet": result.get("content", "No Content")[:300] + "...", # Truncate for readability
                "url": result.get("url", "No URL")
            })
        
        # Create response object
        response = {
            "topic": topic,
            "query": query,
            "result_count": len(formatted_results),
            "results": formatted_results
        }
        
        return response
        
    except Exception as e:
        logger.error(f"Error searching for topic '{topic}': {str(e)}")
        logger.exception("Detailed exception")
        return {
            "topic": topic,
            "query": query,
            "error": str(e),
            "results": []
        }

if __name__ == "__main__":
    # Example topic - this would come from the frontend in actual use
    example_topic = "renewable energy technologies"
    results = search_topic(example_topic)
    
    # Print results as formatted JSON
    print(json.dumps(results, indent=2))