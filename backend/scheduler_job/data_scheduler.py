# data_scheduler.py

# This script schedules the scraping of news articles and Reddit posts,
# processes the scraped content, and stores it in a MongoDB database.

import os
import sys
import time
import logging
import random
import datetime as dt
from datetime import datetime, timedelta
from scheduler import Scheduler
import scheduler.trigger as trigger
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scrapers.news_scraper import NewsAPIScraper, NEWS_CATEGORIES
from scrapers.social_listening import RedditScraper, SUBREDDIT_TOPICS
from db.mdb import MongoDBConnector
from embeddings.process_embeddings import ContentEmbedder
from bedrock.llm_output import ContentAnalyzer
import pytz
from bson import ObjectId

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()  
    ]
)
logger = logging.getLogger("ScraperScheduler")

db_connector = MongoDBConnector()


# ------ 1. Cleanup Utilities ------

# a. Enforce max documents in collections

def enforce_max_docs(collection_name: str, max_docs: int = 100):
    """Ensure no more than `max_docs` in the collection, we drop the oldest if necessary."""
    coll = db_connector.get_collection(collection_name)
    total = coll.count_documents({})
    if total <= max_docs:
        return
    to_delete = total - max_docs
    # find oldest docs by _id ascending
    old_ids = coll.find({}, {"_id": 1}).sort("_id", 1).limit(to_delete)
    ids_to_delete = [doc["_id"] for doc in old_ids]
    try:
        res = coll.delete_many({"_id": {"$in": ids_to_delete}})
        logger.info(
            f"Enforced max {max_docs} docs on '{collection_name}': removed {res.deleted_count} oldest"
        )
    except Exception as e:
        logger.error(f"Error enforcing max docs for '{collection_name}': {e}")


def cleanup_suggestions(retention_days: int = 14, max_docs: int = 100):
    """Remove old content suggestions but keep at least max_docs in the collection."""
    coll = db_connector.get_collection("suggestions")
    total = coll.count_documents({})
    if total <= max_docs:
        logger.info(
            f"Skipping suggestions cleanup: "
            f"{total} suggestions ≤ minimum ({max_docs})"
        )
        return

    cutoff = datetime.now(pytz.UTC) - timedelta(days=retention_days)
    cutoff_oid = ObjectId.from_datetime(cutoff)

    old_cursor = coll.find(
        {"analyzed_at": {"$lt": cutoff}},
        {"_id": 1}
    ).sort("analyzed_at", 1)
    old_ids = [doc["_id"] for doc in old_cursor]
    older_count = len(old_ids)

    can_delete = min(older_count, total - max_docs)
    if can_delete <= 0:
        logger.info(
            "No suggestions removed: "
            "would drop below minimum count"
        )
        return

    try:
        res = coll.delete_many({"_id": {"$in": old_ids[:can_delete]}})
        logger.info(
            f"Removed {res.deleted_count} suggestions older than "
            f"{retention_days}d"
        )
    except Exception as e:
        logger.error(f"Error removing old suggestions: {e}")

def cleanup_generic(collection_name: str, retention_days: int = 14, max_docs: int = 100):
    """Remove up to (total - max_docs) docs older than retention_days, but never drop below max_docs."""
    coll = db_connector.get_collection(collection_name)
    total = coll.count_documents({})
    if total <= max_docs:
        logger.info(
            f"Skipping retention cleanup for '{collection_name}': "
            f"total docs ({total}) ≤ minimum ({max_docs})"
        )
        return

    cutoff = datetime.now(pytz.UTC) - timedelta(days=retention_days)
    cutoff_oid = ObjectId.from_datetime(cutoff)

    # Find all docs older than cutoff, sorted oldest first
    old_cursor = coll.find(
        {"_id": {"$lt": cutoff_oid}},
        {"_id": 1}
    ).sort("_id", 1)
    old_ids = [doc["_id"] for doc in old_cursor]
    older_count = len(old_ids)

    # Compute how many we can safely delete without dropping below max_docs
    can_delete = min(older_count, total - max_docs)
    if can_delete <= 0:
        logger.info(
            f"No documents deleted from '{collection_name}': "
            "deletion would drop below minimum"
        )
        return

    ids_to_delete = old_ids[:can_delete]
    try:
        res = coll.delete_many({"_id": {"$in": ids_to_delete}})
        logger.info(
            f"Removed {res.deleted_count} docs older than "
            f"{retention_days}d from '{collection_name}'"
        )
    except Exception as e:
        logger.error(f"Error cleaning up '{collection_name}': {e}")


# -------- 2. Scheduler verification function --------

def log_scheduler_status():
    """Log the scheduler status and upcoming tasks"""
    now = datetime.now(pytz.UTC)
    logger.info(f"Scheduler heartbeat at {now.isoformat()}")
    logger.info("Upcoming tasks:")
    logger.info("- News scraper: daily at 04:00  UTC")
    logger.info("- Reddit scraper: daily at 04:15 UTC")
    logger.info("- Embedding processor: daily at 04:30 UTC")
    logger.info("- Content suggestion generator: daily at 04:45 UTC")
    logger.info("- Cleanup tasks: immediately after each job")
    logger.info("- Status checks: every 4 hours (00:00, 04:00, … UTC)")

# ------ 3. Scraper Jobs ---------   

# a. News Scraper Job

def run_news_scraper():
    """Run the news scraper to collect articles from the categories."""
    now = datetime.now(pytz.UTC)
    logger.info(f"Starting news scraper job at {now.isoformat()}")
    try:
        newsapi_scraper = NewsAPIScraper()
        total_articles = newsapi_scraper.run_for_multiple_categories(NEWS_CATEGORIES, db_connector)
        logger.info(f"News scraper completed: {total_articles} articles from {len(NEWS_CATEGORIES)} categories")
    except Exception as e:
        logger.error(f"Error in news scraper job: {e}")
    # cleanup old news
    cleanup_generic("news")

# b. Reddit Scraper Job

def run_reddit_scraper():
    """Run the Reddit scraper to collect posts from the SUBREDDIT_TOPICS."""
    now = datetime.now(pytz.UTC)
    logger.info(f"Starting Reddit scraper job at {now.isoformat()}")
    total_count = 0
    for subreddit in SUBREDDIT_TOPICS:
        try:
            count = RedditScraper(subreddit=subreddit).store(db_connector)
            total_count += count
            logger.info(f"Scraped {count} posts from r/{subreddit}")
        except Exception as e:
            logger.error(f"Error scraping subreddit {subreddit}: {e}")
    logger.info(f"Reddit scraper completed: {total_count} total posts")
    # cleanup old reddit posts
    cleanup_generic("reddit_posts")

# c. Embedding Processor Job

def process_embeddings():
    """Process the embeddings for newly scraped content."""
    start_time = datetime.now(pytz.UTC)
    logger.info(f"Starting embeddings processing job at {start_time.isoformat()}")
    try:
        news_without = db_connector.get_collection("news").count_documents({"embedding": {"$exists": False}})
        reddit_without = db_connector.get_collection("reddit_posts").count_documents({"embedding": {"$exists": False}})
        logger.info(f"Found {news_without} news & {reddit_without} Reddit without embeddings")

        embedder = ContentEmbedder(batch_size=20)
        news_count = embedder.process_news_embeddings()
        reddit_count = embedder.process_reddit_embeddings()
        duration = (datetime.now(pytz.UTC) - start_time).total_seconds()
        logger.info(f"Embeddings done in {duration}s: {news_count} news & {reddit_count} reddit")

    except Exception as e:
        logger.error(f"Error in embeddings processing job: {e}")


# ------ 4. Targeted Queries --------- 

def generate_targeted_query(subreddit):
    """Generate a more targeted and specific query for a subreddit."""
    if subreddit in SUBREDDIT_TOPICS:
        topics = SUBREDDIT_TOPICS[subreddit]
        selected = random.sample(topics, min(2, len(topics)))
        return f"Trending discussions about {' and '.join(selected)} in r/{subreddit}"
    return f"Current discussions in r/{subreddit}"


# --------- 5. Content Suggestion Generation ---------

def generate_content_suggestions():
    """
    Give topic suggestions using LLMs for each news and subreddit category,
    then clean up old suggestions and enforce limits.
    """
    start = datetime.now(pytz.UTC)
    logger.info(f"Starting content suggestion job at {start.isoformat()}")
    analyzer = ContentAnalyzer()
    total_generated = 0

    # news categories
    for category in NEWS_CATEGORIES:
        try:
            results = analyzer.analyze_and_store_search_results(
                f"Latest {category} news and developments", db_connector
            )
            count = sum(results["stored"].values())
            total_generated += count
            logger.info(f"Generated {count} suggestions for news category '{category}'")
        except Exception as e:
            logger.error(f"Error suggestions for news '{category}': {e}")

    # subreddit categories
    for subreddit in SUBREDDIT_TOPICS:
        q = generate_targeted_query(subreddit)
        try:
            results = analyzer.analyze_and_store_search_results(q, db_connector)
            count = sum(results["stored"].values())
            total_generated += count
            logger.info(f"Generated {count} suggestions for r/{subreddit}")
        except Exception as e:
            logger.error(f"Error suggestions for r/{subreddit}: {e}")

    # cleanup old suggestions + enforce cap
    cleanup_suggestions()

    end = datetime.now(pytz.UTC)
    logger.info(f"Content suggestions done in {(end - start).total_seconds()}s: generated {total_generated}")

# Scheduler setup

schedule = Scheduler()

# news scraper runs
schedule.daily(datetime.strptime("04:00", "%H:%M").time(), run_news_scraper)

# reddit scraper runs 
schedule.daily(datetime.strptime("04:15", "%H:%M").time(), run_reddit_scraper)

# embedding processor
schedule.daily(datetime.strptime("04:30", "%H:%M").time(), process_embeddings)

# content suggestion generator 
schedule.daily(datetime.strptime("04:45", "%H:%M").time(), generate_content_suggestions)

# status checks every 4 hours
for hour in range(0, 24, 4):
    schedule.daily(datetime.strptime(f"{hour:02d}:00", "%H:%M").time(), log_scheduler_status)

def test_scheduler_job():
    now = datetime.now(pytz.UTC)
    logger.info(f"Test scheduler job triggered at {now.isoformat()}")

# Schedule the test job to run every hour
schedule.hourly(dt.time(minute=0, second=0), test_scheduler_job)

if __name__ == "__main__":
    start = datetime.now(pytz.UTC)
    logger.info(f"Starting data scraper scheduler at {start.isoformat()}")
    try:
        # Test MongoDB connection
        db_connector.get_collection("test").find_one()
        logger.info("MongoDB connection successful")

        log_scheduler_status()
        logger.info(f"Scheduler overview: {schedule}")

        while True:
            schedule.exec_jobs()
            time.sleep(1)
    except Exception as e:
        logger.error(f"Scheduler error: {e}")
        if "MongoDB" in str(e):
            logger.error("Failed to connect to MongoDB. Please check your connection settings.")
        sys.exit(1)