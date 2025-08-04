# ---- test.py ----

# This file is only be used to test the data scheduler.

# Import the necessary libraries.
import sys
import os
import logging

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from data_scheduler import run_news_scraper, run_reddit_scraper, process_embeddings, generate_content_suggestions
from data_scheduler import cleanup_duplicates

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Test")

if __name__ == "__main__":

    logger.info("Testing news scraper...")
    # run_news_scraper()
    logger.info("Testing Reddit scraper...")
    # run_reddit_scraper()
    
    logger.info("Testing embedding processor...")
    # process_embeddings()
    
    logger.info("Testing content suggestions...")
    # generate_content_suggestions()

    logger.info("Testing duplicate cleanup...")
    # cleanup_duplicates()

    logger.info("Test completed")