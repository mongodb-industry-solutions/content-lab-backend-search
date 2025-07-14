from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from bson import ObjectId

from db.mdb import MongoDBConnector

router = APIRouter(
    prefix="/api/drafts",
    tags=["drafts"],
    responses={404: {"description": "Not found"}},
)

# Initialize database connection
db = MongoDBConnector()

class DraftRequest(BaseModel):
    userId: str
    title: str
    category: str
    content: str
    keywords: Optional[List[str]] = None
    topicId: Optional[str] = None

@router.get("")
async def get_drafts(
    userId: str
):
    """
    Get the drafts documents from a specific user by userId
    """
    try:
        collection = db.get_collection("drafts")
        saved = list(collection.find({"userId": userId}))

        # Convert to string for JSON serialization
        for result in saved:
            if "_id" in result:
                result["_id"] = str(result["_id"])

        return saved
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{draft_id}")
async def get_draft_by_id(
    draft_id: str,
    userId: str
):
    """
    Get a single draft by ID, ensuring it belongs to the requesting user
    """
    try:
        collection = db.get_collection("drafts")
        draft = collection.find_one({
            "_id": ObjectId(draft_id),
            "userId": userId
        })

        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found or access denied")

        # Convert to string for JSON serialization
        draft["_id"] = str(draft["_id"])

        return draft
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/by-topic/{topic_id}")
async def get_draft_by_topic(
    topic_id: str,
    userId: str
):
    """
    Get an existing draft for a specific topic and user
    """
    try:
        collection = db.get_collection("drafts")
        draft = collection.find_one({
            "topicId": topic_id,
            "userId": userId
        })

        if not draft:
            return None

        # Convert to string for JSON serialization
        draft["_id"] = str(draft["_id"])

        return draft
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("")
async def save_draft(
    request: DraftRequest
):
    """
    Save a draft document to the drafts collection
    """
    try:
        collection = db.get_collection("drafts")
        
        # Create draft document
        draft_data = {
            "userId": request.userId,
            "title": request.title,
            "category": request.category,
            "content": request.content,
            "keywords": request.keywords,
            "topicId": request.topicId,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Insert the draft
        result = collection.insert_one(draft_data)
        
        # Get the created draft and return it
        created_draft = collection.find_one({"_id": result.inserted_id})
        created_draft["_id"] = str(created_draft["_id"])
        
        return created_draft
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{draft_id}")
async def update_draft(
    draft_id: str,
    request: DraftRequest
):
    """
    Update a draft document in the drafts collection
    """
    try:
        collection = db.get_collection("drafts")
        
        # Update data (allow changing title, category, content, and topicId)
        update_data = {
            "title": request.title,
            "category": request.category,
            "content": request.content,
            "keywords": request.keywords,
            "topicId": request.topicId,
            "updated_at": datetime.utcnow()
        }
        
        # Update the draft
        result = collection.update_one(
            {"_id": ObjectId(draft_id)}, 
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Draft not found")
        
        # Get the updated draft and return it
        updated_draft = collection.find_one({"_id": ObjectId(draft_id)})
        updated_draft["_id"] = str(updated_draft["_id"])
        
        return updated_draft
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 