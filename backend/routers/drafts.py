# ---- drafts.py ----

# This file is used to create the drafts router.

# Import the necessary libraries.
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from bson import ObjectId
from bson.errors import InvalidId

from db.mdb import MongoDBConnector


def _to_object_id(value: str, field: str = "id") -> ObjectId:
    """Parse a user-supplied id.

    Raises a 400 rather than letting bson's InvalidId surface as a 500.
    """
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail=f"{field} is not a valid id")

# Create the router
router = APIRouter(
    prefix="/api/drafts",
    tags=["drafts"],
    responses={404: {"description": "Not found"}},
)

# Initialize database connection
db = MongoDBConnector()

# DraftRequest class to define the draft request. 
class DraftRequest(BaseModel):
    userId: str
    title: str
    category: str
    content: str
    keywords: Optional[List[str]] = None
    topicId: Optional[str] = None

# Get the drafts documents from a specific user by userId
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

# Get a single draft by ID, ensuring it belongs to the requesting user
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
            "_id": _to_object_id(draft_id, "draft_id"),
            "userId": userId
        })

        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found or access denied")

        # Convert to string for JSON serialization
        draft["_id"] = str(draft["_id"])

        return draft
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Get an existing draft for a specific topic and user
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

# Save a draft document to the drafts collection

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

# Update a draft document in the drafts collection
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
        oid = _to_object_id(draft_id, "draft_id")

        # Update data (allow changing title, category, content, and topicId)
        update_data = {
            "title": request.title,
            "category": request.category,
            "content": request.content,
            "keywords": request.keywords,
            "topicId": request.topicId,
            "updated_at": datetime.utcnow()
        }

        # Scope the update to the owning user, matching GET and DELETE. Without the
        # userId filter any caller could overwrite another user's draft.
        result = collection.update_one(
            {"_id": oid, "userId": request.userId},
            {"$set": update_data}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Draft not found or access denied")

        # Get the updated draft and return it
        updated_draft = collection.find_one({"_id": oid})
        updated_draft["_id"] = str(updated_draft["_id"])

        return updated_draft
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Delete a draft document by ID and userId
@router.delete("/{draft_id}")
async def delete_draft(
    draft_id: str,
    userId: str
):
    """
    Delete a draft document by ID and userId
    """
    try:
        collection = db.get_collection("drafts")
        result = collection.delete_one({
            "_id": _to_object_id(draft_id, "draft_id"),
            "userId": userId
        })
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Draft not found or access denied")
        return {"message": "Draft deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Publish a draft document to the preview collection

@router.post("/publish")
async def publish_draft(
    request: DraftRequest
):
    """
    Publish a draft document to the preview collection
    """
    try:
        collection = db.get_collection("preview")
        
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

        preview_link = f"https://ist.media/post?preview={created_draft['_id']}"
        # created_draft["preview_link"] = preview_link

        return preview_link
    
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
