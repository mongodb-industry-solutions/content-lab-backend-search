import os
from pymongo import MongoClient
from abc import abstractmethod
from dotenv import load_dotenv
import logging
from pymongo.errors import DuplicateKeyError
# Add logging for index creation
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

class MongoDBConnector:
    """ A class to provide access to a MongoDB database.
    This class handles the connection to the database and provides methods to interact with collections and documents.

    Attributes:
        uri (str): The connection string URI for the MongoDB database.
        database_name (str): The name of the database to connect to.
        appname (str): The name of the application connecting to the database.
    """

    def __init__(self, uri=None, database_name=None, appname=None):
        """ Initialize the MongoDBConnector instance. """
        self.uri = uri or os.getenv("MONGODB_URI")
        self.database_name = database_name or os.getenv("DATABASE_NAME")
        self.appname = appname or os.getenv("APP_NAME")
        self.client = MongoClient(self.uri, appname=self.appname)
        self.db = self.client[self.database_name]

    def get_collection(self, collection_name):
        """Retrieve a collection."""
        if not collection_name:
            raise ValueError("Collection name must be provided.")
        return self.db[collection_name]

    def insert_one(self, collection_name, document):
        """Insert a single document into a collection."""
        collection = self.get_collection(collection_name)
        result = collection.insert_one(document)
        return result.inserted_id

    def insert_many(self, collection_name, documents):
        """Insert multiple documents into a collection."""
        collection = self.get_collection(collection_name)
        result = collection.insert_many(documents)
        return result.inserted_ids

    def upsert_one(self, collection_name, filter_query, document, upsert=True):
        """Upsert a single document (update if exists, insert if not)."""
        collection = self.get_collection(collection_name)
        result = collection.replace_one(filter_query, document, upsert=upsert)
        return result.upserted_id if result.upserted_id else result.modified_count

    def upsert_many(self, collection_name, documents, unique_field="url"):
        """Upsert multiple documents efficiently."""
        collection = self.get_collection(collection_name)
        upserted_count = 0
        updated_count = 0
        
        for document in documents:
            if unique_field in document:
                filter_query = {unique_field: document[unique_field]}
                result = collection.replace_one(filter_query, document, upsert=True)
                if result.upserted_id:
                    upserted_count += 1
                else:
                    updated_count += 1
        
        return {"upserted": upserted_count, "updated": updated_count}

    def find(self, collection_name, query={}, projection=None):
        """Retrieve documents from a collection."""
        collection = self.get_collection(collection_name)
        return list(collection.find(query, projection))

    def update_one(self, collection_name, query, update, upsert=False):
        """Update a single document in a collection."""
        collection = self.get_collection(collection_name)
        result = collection.update_one(query, update, upsert=upsert)
        return result.modified_count

    def update_many(self, collection_name, query, update, upsert=False):
        """Update multiple documents in a collection."""
        collection = self.get_collection(collection_name)
        result = collection.update_many(query, update, upsert=upsert)
        return result.modified_count

    def delete_one(self, collection_name, query):
        """Delete a single document from a collection."""
        collection = self.get_collection(collection_name)
        result = collection.delete_one(query)
        return result.deleted_count

    def delete_many(self, collection_name, query):
        """Delete multiple documents from a collection."""
        collection = self.get_collection(collection_name)
        result = collection.delete_many(query)
        return result.deleted_count
    
    def create_unique_indexes(self):
        """Create unique indexes to prevent duplicates at database level
        
        This method creates unique indexes for the 'news', 'reddit_posts', and 'suggestions' collections.
        It ensures that the 'url' field is unique in 'news' and 'reddit_posts', and that the combination of 'topic', 'source_query', and 'label' is unique in 'suggestions'.
        """
        logger.info("Creating unique indexes for collections...")
        indexes_config = {
            "news": [
                {"fields": [("url", 1)], "name": "unique_news_url", "unique": True, "sparse": True},
                {"fields": [("title", 1), ("source", 1)], "name": "unique_news_title_source", "unique": True, "sparse": True}
            ],
            "reddit_posts": [
                {"fields": [("url", 1)], "name": "unique_reddit_url", "unique": True, "sparse": True},
                {"fields": [("title", 1), ("subreddit", 1)], "name": "unique_reddit_title_subreddit", "unique": True, "sparse": True}
            ],
            "suggestions": [
                {"fields": [("topic", 1), ("source_query", 1), ("label", 1)], "name": "unique_suggestion_topic_query_label", "unique": True, "sparse": True},
                {"fields": [("url", 1), ("source_query", 1)], "name": "unique_suggestion_url_query", "unique": True, "sparse": True}
            ]
        }
        for collection_name, indexes in indexes_config.items():
            collection = self.get_collection(collection_name)
            
            for index_config in indexes:
                try:
                    collection.create_index(
                        index_config["fields"],
                        name=index_config["name"],
                        unique=index_config["unique"],
                        sparse=index_config["sparse"],
                        background=True
                    )
                    logger.info(f"Created unique index '{index_config['name']}' for '{collection_name}'")
                except Exception as e:
                    # Index might already exist, which is fine
                    logger.info(f"Index '{index_config['name']}' for '{collection_name}': {e}")
                    
    def create_duplicate_detection_indexes(self):
        """Create indexes for efficient duplicate detection and cleanup operations"""
        collections = ["news", "reddit_posts", "suggestions"]
        
        for collection_name in collections:
            collection = self.get_collection(collection_name)
            
            try:
                # Compound index for duplicate detection (url + title)
                collection.create_index([
                    ("url", 1),
                    ("title", 1)
                ], background=True, name="url_title_duplicate_idx")
            
                logger.info(f"Created duplicate detection indexes for '{collection_name}'")
                
            except Exception as e:
                # Index might already exist, which is fine
                logger.info(f"Index creation for '{collection_name}': {e}")

    def ensure_indexes(self):
        """Ensure all necessary indexes are created"""
        try:
            self.create_duplicate_detection_indexes()
            logger.info("All indexes ensured successfully")
        except Exception as e:
            logger.error(f"Error ensuring indexes: {e}")
    
    def get_current_timestamp(self):
        """Get current UTC timestamp"""
        from datetime import datetime
        return datetime.utcnow()