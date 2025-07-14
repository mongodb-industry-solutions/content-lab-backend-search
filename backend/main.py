# ---- main.py ----
# This file sets up the FastAPI application and includes CORS middleware.

# FastAPI imports

from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi import APIRouter
from bson import json_util
import json
import logging
from dotenv import load_dotenv
from typing import Optional, List
from pydantic import BaseModel

from embeddings.test_embeddings import convert_query_to_embedding, search_similar_content
from bedrock.llm_output import ContentAnalyzer
from db.mdb import MongoDBConnector
from bson import ObjectId
from langchain_tavily import TavilySearch
from pydantic import BaseModel
from search_topics.topic_search import search_topic

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# db connection

db = MongoDBConnector()

class SearchRequest(BaseModel):
    query: str
    limit: int = 5

class SuggestionFilter(BaseModel):
    query: Optional[str] = None
    label: Optional[str] = None
    days: int = 7

class TopicRequest(BaseModel):
    topic: str


router = APIRouter()

@app.get("/")
async def read_root(request: Request):
    return {"message":"Server is running"}


@app.post("/api/analyze")
async def analyze_content(request: SearchRequest):
    """
    Analyze search results and generate content suggestions
    """
    try:
        analyzer = ContentAnalyzer()
        results = analyzer.analyze_and_store_search_results(request.query, db)
        
        return {
            "query": request.query,
            "suggestions": results["analysis"],
            "stored_count": results["stored"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/suggestions")
async def get_suggestions(
    query: Optional[str] = None,
    label: Optional[str] = None,
    type: Optional[str] = None,
    days: int = 7,
    limit: int = 20
):
    """
    Get content suggestions from the database with optional filtering
    """
    try:
        from datetime import datetime, timedelta
        
        collection = db.get_collection("suggestions")
        
        # Build filter query
        filter_query = {}
        if query:
            filter_query["source_query"] = {"$regex": query, "$options": "i"}
        if label:
            filter_query["label"] = label
        if type and type in ["news_analysis", "reddit_analysis"]:
            filter_query["type"] = type
            
        # Add time filter
        if days > 0:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            filter_query["analyzed_at"] = {"$gte": cutoff_date}
        
        # Fetch results
        results = list(collection.find(filter_query).sort("analyzed_at", -1).limit(limit))
        
        # Convert to string for JSON serialization
        for result in results:
            if "_id" in result:
                result["_id"] = str(result["_id"])
        
        return {
            "count": len(results),
            "suggestions": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/news")
async def get_news():
    """
    Get 4 documents from the news collection
    """
    try:
        collection = db.get_collection("news")
        news = list(collection.find({}).limit(4))

        # Convert to string for JSON serialization
        for result in news:
            if "_id" in result:
                result["_id"] = str(result["_id"])

        return news
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reddit")
async def get_reddit():
    """
    Get 10 documents from the reddit collection
    """
    try:
        collection = db.get_collection("reddit_posts")
        reddit = list(collection.find({}).limit(10))

        # Convert to string for JSON serialization
        for result in reddit:
            if "_id" in result:
                result["_id"] = str(result["_id"])

        return reddit
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/profile")
async def get_user_profiles(
    userId: str
):
    """
    Get the users profile by userId from the userProfiles collection
    """
    try:
        collection = db.get_collection("userProfiles")
        userProfile = collection.find_one({"_id": ObjectId(userId)})

        # Convert to string for JSON serialization
        if userProfile:
            userProfile["_id"] = str(userProfile["_id"])

        return userProfile
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/research")
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



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)