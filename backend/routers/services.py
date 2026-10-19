# ---- services.py ----

# This file is used to create the services router.

# Import the necessary libraries.
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from starlette.concurrency import run_in_threadpool
from embeddings.test_embeddings import convert_query_to_embedding, search_similar_content
from grove.llm_output import ContentAnalyzer
from db.mdb import MongoDBConnector
from search_topics.topic_search import search_topic

# Create the router
router = APIRouter(
    prefix="/api/services",
    tags=["services"],
    responses={500: {"description": "Internal server error"}},
)

# Initialize database connection
db = MongoDBConnector()

# SearchRequest class to define the search request.
class SearchRequest(BaseModel):
    query: str
    limit: int = 5
    label: Optional[str] = None

# TopicRequest class to define the topic request.
class TopicRequest(BaseModel):
    topic: str

# Analyze search results and generate content suggestions
@router.post("/analyze")
async def analyze_content(request: SearchRequest):
    """
    Analyze search results and generate content suggestions
    """
    try:
        analyzer = ContentAnalyzer()
        # Embedding + Atlas vector search + the Grove calls are all synchronous and
        # take seconds. Running them inline would block the event loop for every
        # other request, so hand them to the threadpool.
        results = await run_in_threadpool(
            analyzer.analyze_and_store_search_results, request.query, db, request.label
        )

        return {
            "query": request.query,
            "suggestions": results["analysis"],
            "stored_count": results["stored"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Research a topic and get 4 key points for content creation
@router.post("/research")
async def research_topic(request: TopicRequest):
    """
    Research a topic and get 4 key points for content creation
    """
    if not request.topic or not request.topic.strip():
        raise HTTPException(status_code=400, detail="topic must not be empty")
    try:
        # Use the topic_search function to get recent updates
        results = await run_in_threadpool(search_topic, request.topic, 4)

        # `result_count` is present on both the success and failure shapes; fall back
        # to the list length defensively so a shape change can't 500 the endpoint.
        key_points = results.get("results") or []
        response = {
            "topic": request.topic,
            "keyPoints": key_points,
            "resultCount": results.get("result_count", len(key_points)),
            "source": results.get("source"),
        }
        if results.get("error"):
            response["error"] = results["error"]
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))