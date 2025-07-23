from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from typing import Optional
from bson import ObjectId

from db.mdb import MongoDBConnector

router = APIRouter(
    prefix="/api/content",
    tags=["content"],
    responses={404: {"description": "Not found"}},
)

# Initialize database connection
db = MongoDBConnector()

@router.get("/suggestions")
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

# Get the 4 most recent news documents from the last 3 days - news collection
@router.get("/news")
async def get_news():
    """
    Get up to 4 most recent news documents from the last 3 days
    """
    try:
        collection = db.get_collection("news")
        cutoff_date = datetime.utcnow() - timedelta(days=3)

        # 1. get the news from the last three days. 
        recent_news = list(
            collection.find({"scraped_at": {"$gte": cutoff_date}})
            .sort("scraped_at", -1)
            .limit(4)
        )
        count = len(recent_news)
        if count < 4:
            older_news = list(
                collection.find({"scraped_at": {"$lt": cutoff_date}})
                .sort("scraped_at", -1)
                .limit(4 - count)
            )
            news = recent_news + older_news
        else:
            news = recent_news

        # Convert to string for JSON serialization
        for result in news:
            if "_id" in result:
                result["_id"] = str(result["_id"])
        return news

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Get the 10 most recent reddit posts from the last 3 days - reddit_posts collection
@router.get("/reddit")
async def get_reddit():
    """
    Get 10 documents from the reddit collection from the last 3 days
    """
    try:
        collection = db.get_collection("reddit_posts")
        cutoff_date = datetime.utcnow() - timedelta(days=3)
        recent_reddit = list(
            collection.find({"scraped_at": {"$gte": cutoff_date}})
            .sort("scraped_at", -1)
            .limit(10)
        )

        count = len(recent_reddit)
        if count < 10:
            older_reddit = list(
                collection.find({"scraped_at": {"$lt": cutoff_date}})
                .sort("scraped_at", -1)
                .limit(10 - count)
            )
            reddit = recent_reddit + older_reddit
        else:
            reddit = recent_reddit

        # Convert to string for JSON serialization
        for result in reddit:
            if "_id" in result:
                result["_id"] = str(result["_id"])
        return reddit
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Get the user profile by userId from the userProfiles collection
@router.get("/profile")
async def get_user_profile(
    userId: str
):
    """
    Get the user profile by userId from the userProfiles collection
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