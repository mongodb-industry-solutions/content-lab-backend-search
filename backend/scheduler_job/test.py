# ---- test.py ----

# This file should only be used to test the data scheduler.

# Import the necessary libraries.
import sys
import os
import logging
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from data_scheduler import run_news_scraper, run_reddit_scraper, process_embeddings, generate_content_suggestions, cleanup_duplicates
from db.mdb import MongoDBConnector
# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Test")

db_connector = MongoDBConnector()

if __name__ == "__main__":

    logger.info("Testing news scraper...")
    # run_news_scraper()
    
    logger.info("Testing Reddit scraper...")
    # run_reddit_scraper()
    
    logger.info("Testing embedding processor...")
    # process_embeddings()

    logger.info("Testing content suggestions...")
    # generate_content_suggestions()
    
    logger.info("Starting duplicate cleanup test...")
    news_before = db_connector.get_collection("news").count_documents({})
    reddit_before = db_connector.get_collection("reddit_posts").count_documents({})
    suggestions_before = db_connector.get_collection("suggestions").count_documents({})

    # cleanup_duplicates()
    # Add after cleanup_duplicates call:
    news_after = db_connector.get_collection("news").count_documents({})
    reddit_after = db_connector.get_collection("reddit_posts").count_documents({})
    suggestions_after = db_connector.get_collection("suggestions").count_documents({})

    logger.info(f"News: {news_before} → {news_after} (-{news_before - news_after})")
    logger.info(f"Reddit: {reddit_before} → {reddit_after} (-{reddit_before - reddit_after})")
    logger.info(f"Suggestions: {suggestions_before} → {suggestions_after} (-{suggestions_before - suggestions_after})")
        
    logger.info("Test completed")