# ---social_listening.py---
# This module contains the RedditScraper and TwitterScraper class to scrape posts from Reddit and Twitter.


import os
import sys
import time
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv
import praw
import tweepy
from time import sleep
from tweepy.errors import TooManyRequests
from requests.exceptions import RequestException
from collections import Counter

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.mdb import MongoDBConnector

load_dotenv()

REDDIT_COLLECTION = os.getenv("REDDIT_COLLECTION", "reddit_posts")

SUBREDDITS = [
    "technology",   
    "health",       
    "sports",       
    "politics",      
    "science",      
    "business",     
    "entertainment", 
    "travel",       
    "education",   
    "barcelona"  
]
LIST_TYPE     = "hot"
POST_LIMIT    = 15
COMMENT_LIMIT = 5

# ------a. Reddit Scraper------

# RedditScraper class to scrape posts from a specified subreddit

class RedditScraper:

    def __init__(self, subreddit: str):
        self.subreddit = subreddit
        self.reddit = praw.Reddit(
            client_id     = os.getenv("REDDIT_CLIENT_ID"),
            client_secret = os.getenv("REDDIT_SECRET"),
            user_agent    = os.getenv("REDDIT_USER_AGENT"),
        )

    def extract_posts(self) -> List[Dict[str, Any]]:
        sub = self.reddit.subreddit(self.subreddit)
        subscribers = sub.subscribers
        posts: List[Dict[str, Any]] = []

        for submission in getattr(sub, LIST_TYPE)(limit=POST_LIMIT):
            doc = {
                "_id":        submission.id,
                "url":        None if submission.is_self else submission.url,
                "title":      submission.title,
                "body":       submission.selftext or None,
                "author":     str(submission.author) if submission.author else None,
                "created_at": datetime.utcfromtimestamp(submission.created_utc),
                "subreddit":  self.subreddit,
                "source":     "Reddit",
                "reddit_metrics": {
                    "score":           submission.score,
                    "upvote_ratio":    submission.upvote_ratio,
                    "num_comments":    submission.num_comments,
                    "total_awards":    sum(a["count"] for a in submission.all_awardings),
                    "is_crosspostable": submission.is_crosspostable,
                    "subscribers":     subscribers
                },
                "hashtags":        [],
                "topics":          [],
                "language":        None
            }

            submission.comments.replace_more(limit=0)
            comments = []
            for c in submission.comments[:COMMENT_LIMIT]:
                comments.append({
                    "body":          c.body,
                    "author":        str(c.author) if c.author else None,
                    "created_at":    datetime.utcfromtimestamp(c.created_utc),
                    "score":         c.score,
                    "depth":         c.depth,
                    "distinguished": c.distinguished,
                    "gildings":      c.gildings
                })
            doc["comments"] = comments
            posts.append(doc)

        return posts

    def store(self, db: MongoDBConnector) -> int:
        col = db.get_collection(REDDIT_COLLECTION)
        posts = self.extract_posts()
        inserted = 0
        for p in posts:
            col.replace_one({"_id": p["_id"]}, p, upsert=True)
            inserted += 1
        return inserted

    
# ------c. Main function to run scrapers------

if __name__ == "__main__":
    db = MongoDBConnector()
    
    # Reddit scraping
    for sr in SUBREDDITS:
        count = RedditScraper(subreddit=sr).store(db)
        print(f"r/{sr}: stored {count} posts")
    