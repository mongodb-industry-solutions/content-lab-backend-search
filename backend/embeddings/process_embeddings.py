# ---process_embeddings.py---

# This file is used to process the embeddings for the news and reddit collections.

# Import the necessary libraries.
import os
import sys
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.mdb import MongoDBConnector
from bedrock.cohere_embeddings import BedrockCohereEnglishEmbeddings
from _vector_search_idx_creator import VectorSearchIDXCreator

# Configure logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

REDDIT_COLLECTION = os.getenv("REDDIT_COLLECTION", "reddit_posts")
NEWS_COLLECTION   = os.getenv("NEWS_COLLECTION",   "news")

# Content Embeddings Class - To process and create the embeddings for the news and reddit collections.

class ContentEmbedder:
    """Class to process news and reddit collection by adding embeddings."""

    def __init__(self, batch_size: int = 10):
        """Batch size to avoid API rate limits.
        Args:
            batch_size: int, the batch size to use for the embeddings
        Returns:
            None
        """
        self.db_connector = MongoDBConnector()
        self.embedder = BedrockCohereEnglishEmbeddings()
        self.batch_size = batch_size

    def _format_fields(self, data: dict, fields: List[str]) -> List[str]:
        """Format the fields of the data.
        Args:
            data: dict, the data to format
            fields: List[str], the fields to format
        Returns:
            List[str]: The formatted fields
        """
        return [f"{key.upper()}: {data[key]}" for key in fields if data.get(key)]

    def create_article_string(self, article: dict) -> str:
        """Create a string from the article fields.
        Args:
            article: dict, the article to format
        Returns:
            str: The formatted article string
        """
        return "\n\n".join(self._format_fields(article, ["title", "description", "content", "source", "country", "category"]))

    def create_social_post_string(self, post: dict) -> str:
        """Create a string from the post fields.
        Args:
            post: dict, the post to format
        Returns:
            str: The formatted post string
        """
        parts = []
        if title := post.get("title"):
            parts.append(f"TITLE: {title}")
        
        if comments := post.get("comments"):
            comment_texts = []
            for comment in comments[:5]:  # Limit to first 5 comments
                if body := comment.get("body"):
                    comment_texts.append(body)
            
            if comment_texts:
                parts.append(f"COMMENTS: {' '.join(comment_texts)}")
        
        # Add subreddit
        if subreddit := post.get("subreddit"):
            parts.append(f"SUBREDDIT: {subreddit}")
        
        return "\n\n".join(parts)
    
    def truncate_text(self, text: str, max_length: int = 2000) -> str:
        """Truncate text to a maximum length, ensuring it ends at a word boundary.
        Args:
            text: str, the text to truncate
            max_length: int, the maximum length to truncate to
        Returns:
            str: The truncated text
        """
        if len(text) <= max_length:
            return text
        
        # log the truncation
        logger.info(f"Truncating text from {len(text)} to {max_length} characters")
        return text[:max_length] + "..."


    # ---- Collection Embeddings Processing ----

    # ---- a.  News collection Embeddings ----

    def process_news_embeddings(self):
        """Process the news collection embeddings.
        Args:
            None
        Returns:
            int: The number of embeddings processed
        """
        collection = self.db_connector.get_collection(NEWS_COLLECTION)
        query = {"$or": [
        {"embedding": {"$exists": False}},
        {"embedding": None}
        ]}
        articles = list(collection.find(query))
        logger.info(f"Found {len(articles)} news articles without embeddings")

        processed = 0
        for batch_start in range(0, len(articles), self.batch_size):
            batch = articles[batch_start:batch_start + self.batch_size]
            for article in batch:
                try:
                    article_string = self.create_article_string(article)
                    if len(article_string) < 10:
                        logger.warning(f"Article {article['_id']} has insufficient content for embedding")
                        continue
                    embedding = self.embedder.predict(article_string)
                    collection.update_one(
                        {"_id": article["_id"]},
                        {"$set": {
                            "embedding": embedding, 
                            "embedding_string": article_string
                        }}
                    )
                    processed += 1
                except Exception as e:
                    logger.error(f"Error processing article {article['_id']}: {e}")

            logger.info(f"Processed {processed}/{len(articles)} news articles")
            if batch_start + self.batch_size < len(articles):
                time.sleep(0.5)

        logger.info(f"Finished processing {processed} news articles")
        return processed
    
    # ---- b. Process reddit_posts collection embeddings ----

    def process_reddit_embeddings(self):
        """Process the reddit collection embeddings.
        Args:
            None
        Returns:
            int: The number of embeddings processed
        """
        collection = self.db_connector.get_collection(REDDIT_COLLECTION)
        query = {"$or": [
        {"embedding": {"$exists": False}},
        {"embedding": None}
        ]}
        posts = list(collection.find(query))
        logger.info(f"Found {len(posts)} social posts without embeddings")

        processed = 0
        for batch_start in range(0, len(posts), self.batch_size):
            batch = posts[batch_start:batch_start + self.batch_size]
            for post in batch:
                try:
                    post_string = self.create_social_post_string(post)
                    post_string = self.truncate_text(post_string)
                    if len(post_string) < 10:
                        logger.warning(f"Post {post['_id']} has insufficient content for embedding")
                        continue
                    embedding = self.embedder.predict(post_string)
                    collection.update_one(
                        {"_id": post["_id"]},
                        {"$set": {
                            "embedding": embedding, 
                            "embedding_string": post_string
                        }}
                    )
                    processed += 1
                except Exception as e:
                    logger.error(f"Error processing post {post['_id']}: {e}")

            logger.info(f"Processed {processed}/{len(posts)} reddit posts")
            if batch_start + self.batch_size < len(posts):
                time.sleep(0.5)

        logger.info(f"Finished processing {processed} social posts")
        return processed

    # ---- Cleaning up data in both the collections ----

    # ---a. News Articles Cleanup---

    def clean_up_news_articles(self, max_per_category: int = 100):
        """Clean up the news articles in the collection.
        Args:
            max_per_category: int, the maximum number of articles to keep per category
        Returns:
            int: The number of articles removed
        """
        collection = self.db_connector.get_collection("news")
        categories = collection.distinct("category")
        total_removed = 0

        for category in categories:
            articles = list(collection.find(
                {"category": category},
                {"_id": 1, "scraped_at": 1}
            ).sort("scraped_at", -1))

            if len(articles) > max_per_category:
                to_remove = articles[max_per_category:]
                ids_to_remove = [doc["_id"] for doc in to_remove]
                result = collection.delete_many({"_id": {"$in": ids_to_remove}})
                total_removed += result.deleted_count
                logger.info(f"Removed {result.deleted_count} old articles from category '{category}'")

        logger.info(f"Cleanup complete. Total articles removed: {total_removed}")
        return total_removed
    

    def create_vector_search_indexes(self):
        """Create the vector search indexes for the news and reddit collections.
        Args:
            None
        Returns:
            None
        """
        for collection_name in ["news", "reddit_posts"]:
            try:
                vs_creator = VectorSearchIDXCreator(collection_name=collection_name)
                result = vs_creator.create_index(
                    index_name="semantic_search_embeddings",
                    vector_field="embedding",
                    dimensions=1024,
                    similarity_metric="cosine"
                )
                logger.info(f"Vector search index for {collection_name}: {result}")
            except Exception as e:
                logger.error(f"Error creating vector search index for {collection_name}: {e}")

    def run_full_process(self):
        """Run the full process of processing the news and reddit collections.
        Args:
            None
        Returns:
            dict: The number of embeddings processed
        """
        news_count = self.process_news_embeddings()
        reddit_count = self.process_reddit_embeddings()
        self.create_vector_search_indexes()
        return {
            "news_embeddings_added": news_count,
            "reddit_embeddings_added": reddit_count
        }

# ---- Main function to run the embeddings processor -----

if __name__ == "__main__":
    processor = ContentEmbedder(batch_size=10)
    processor.run_full_process()
    





