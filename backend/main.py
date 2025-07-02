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

from test_embeddings import convert_query_to_embedding, search_similar_content
from bedrock.llm_output import ContentAnalyzer
from db.mdb import MongoDBConnector

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


router = APIRouter()

@app.get("/")
async def read_root(request: Request):
    return {"message":"Server is running"}

def json_serialize(data):
    return json.loads(json_util.dumps(data))

@app.post("/api/search")
async def search(request: SearchRequest):
    """
    Search endpoint that takes a query and returns relevant content
    """
    try:
        # Convert query to embedding
        query_embedding = convert_query_to_embedding(request.query)
        if not query_embedding:
            raise HTTPException(status_code=500, detail="Failed to generate query embedding")
        
        # Search for similar content
        results = search_similar_content(query_embedding, request.limit)
        serialized_results = json_serialize(results)
        return {
            "query": request.query,
            "results": serialized_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        
        # Convert ObjectId to string for JSON serialization
        for result in results:
            if "_id" in result:
                result["_id"] = str(result["_id"])
        
        return {
            "count": len(results),
            "suggestions": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)