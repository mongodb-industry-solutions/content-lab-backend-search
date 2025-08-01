# ---- services.py ----

# This file is used to create the services router.

# Import the necessary libraries.
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from embeddings.test_embeddings import convert_query_to_embedding, search_similar_content
from bedrock.llm_output import ContentAnalyzer
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
        results = analyzer.analyze_and_store_search_results(request.query, db, request.label)
        
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
    try:
        # Use the topic_search function to get recent updates
        results = search_topic(request.topic, max_results=4)
        
        return {
            "topic": request.topic,
            "keyPoints": results["results"],
            "resultCount": results["result_count"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 