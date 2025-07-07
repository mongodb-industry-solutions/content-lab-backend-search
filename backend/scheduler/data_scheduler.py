# data_scheduler.py

# This script schedules the scraping of news articles and social media posts,
# processes the scraped content, and stores it in a MongoDB database.

import os
import sys
import logging
from datetime import datetime, timedelta
from scheduler import Scheduler
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scrapers.news_scraper import NewsAPIScraper, NEWS_CATEGORIES
from scrapers.social_listening import RedditScraper, SUBREDDITS
from db.mdb import MongoDBConnector
from process_embeddings import ContentEmbedder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("scraper_scheduler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ScraperScheduler")

# Scheduler verification function
def log_scheduler_status():
    """Log the scheduler status and upcoming tasks"""
    logger.info(f"Scheduler heartbeat at {datetime.now()}")
    logger.info(f"Upcoming tasks:")
    logger.info(f"- News scraper: {scheduler.get_next_run_time(run_news_scraper)}")
    logger.info(f"- Reddit scraper: {scheduler.get_next_run_time(run_reddit_scraper)}")
    logger.info(f"- Embedding processor: {scheduler.get_next_run_time(process_embeddings)}")

# Scraper Jobs

def run_news_scraper():
    """Run the news scraper to collect articles from the categories."""
    logger.info(f"Starting news scraper job at {datetime.now()}")
    try:
        db_connector = MongoDBConnector()
        newsapi_scraper = NewsAPIScraper()
        total_articles = newsapi_scraper.run_for_multiple_categories(NEWS_CATEGORIES, db_connector)
        logger.info(f"News scraper completed for {len(NEWS_CATEGORIES)} categories: {NEWS_CATEGORIES}")
        logger.info(f"Total articles scraped: {total_articles}")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")


def run_reddit_scraper():
    """Run the Reddit scraper to collect posts from the subreddits."""
    logger.info(f"Starting Reddit scraper job at {datetime.now()}")
    try:
        db_connector = MongoDBConnector()
        total_count = 0
        for subreddit in SUBREDDITS:
            try:
                count = RedditScraper(subreddit=subreddit).store(db_connector)
                total_count += count
                logger.info(f"Scraped {count} posts from r/{subreddit}")
            except Exception as e:
                logger.error(f"Error scraping subreddit {subreddit}: {e}")
        logger.info(f"Reddit scraper completed: {total_count} total posts scraped")
    except Exception as e:
        logger.error(f"Error in Reddit scraper job: {e}")

def process_embeddings():
    """Process embeddings for newly scraped content."""
    start_time = datetime.now()
    logger.info(f"Starting embeddings processing job at {start_time}")
    try:
        db_connector = MongoDBConnector()
        # Check document counts before processing
        news_without_embeddings = db_connector.get_collection("news").count_documents({"embedding": {"$exists": False}})
        reddit_without_embeddings = db_connector.get_collection("reddit_posts").count_documents({"embedding": {"$exists": False}})
        logger.info(f"Found {news_without_embeddings} news articles and {reddit_without_embeddings} Reddit posts without embeddings")
        
        embedder = ContentEmbedder(batch_size=20)
        news_count = embedder.process_news_embeddings()
        reddit_count = embedder.process_reddit_embeddings()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"Embeddings processing completed in {duration} seconds. Processed {news_count} news articles and {reddit_count} Reddit posts")
    except Exception as e:
        logger.error(f"Error in embeddings processing job: {e}")


scheduler = Scheduler()

# Schedule the jobs

# news scraper runs at 1 PM daily
scheduler.daily(datetime.strptime("13:00", "%H:%M").time(), run_news_scraper)

# reddit scraper runs at 1.30 PM daily
scheduler.daily(datetime.strptime("13:30", "%H:%M").time(), run_reddit_scraper)

# embedding processor runs at 2 PM daily
scheduler.daily(datetime.strptime("14:00", "%H:%M").time(), process_embeddings)

# Add scheduler status check every 2 hours
scheduler.interval(timedelta(hours=2), log_scheduler_status)

if __name__ == "__main__":
    logger.info(f"Starting data scraper scheduler at {datetime.now()}")
    try:
        # Initial status display
        log_scheduler_status()
        
        # Run the scheduler
        scheduler.run()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Scheduler error: {e}")