# ---social_listening.py---

# This file contains the RedditScraper and TwitterScraper class to scrape posts from Reddit and Twitter.

# Import the necessary libraries.
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

# Simple mapping of SUBREDDIT_TOPICS to relevant topics for better queries

SUBREDDIT_TOPICS = {

    "technology": [
        "emerging tech trends",
        "AI developments",
        "software engineering",
        "tech innovations"
    ],
    "health": [
        "medical research",
        "wellness trends",
        "mental health",
        "fitness advice"
    ],
    "sports": [
        "sports events",
        "athlete performances",
        "team updates",
        "league standings"
    ],
    "politics": [
        "policy developments",
        "election news",
        "political debates",
        "government actions"
    ],
    "science": [
        "scientific discoveries",
        "research findings",
        "space exploration",
        "scientific studies"
    ],
    "business": [
        "market trends",
        "company news",
        "economic updates",
        "startup developments"
    ],
    "entertainment": [
        "movie releases",
        "TV show updates",
        "celebrity news",
        "media industry"
    ],
    "travel": [
        "destination guides",
        "travel experiences",
        "tourism trends",
        "travel tips"
    ],
    "education": [
        "learning methods",
        "academic resources",
        "education technology",
        "student issues"
    ],
    "barcelona": [
        "Barcelona events",
        "FC Barcelona updates",
        "Barcelona tourism",
        "city developments"
    ]
}

POST_LIMIT = 15
COMMENT_LIMIT = 5

# ------a. Reddit Scraper------

class RedditScraper:
    """
    RedditScraper class to scrape posts from a specified subreddit.
    """
    def __init__(self, subreddit: str):
        self.subreddit = subreddit
        self.reddit = praw.Reddit(
            client_id     = os.getenv("REDDIT_CLIENT_ID"),
            client_secret = os.getenv("REDDIT_SECRET"),
            user_agent    = os.getenv("REDDIT_USER_AGENT"),
        )

        self.sort_methods = ["hot", "new", "rising", "top"]

    def extract_posts_with_diverse_sorting(self) -> List[Dict[str, Any]]:
        """Extract posts using multiple sorting methods with API limit awareness"""
        all_posts = []
        sub = self.reddit.subreddit(self.subreddit)
        subscribers = sub.subscribers
        
        day_of_week = datetime.now().weekday()
        
        if day_of_week % 2 == 0:  
            sorts_to_use = ["hot", "new"]  # Default sorts
            time_filter = "week"  # Use weekly filter for top
        else:  
            sorts_to_use = ["rising", "top"]  
            time_filter = "month" 
        
        # Process each selected sort method
        for sort_method in sorts_to_use:
            try:
                # Reduce posts per sort to stay within limits
                posts_per_sort = POST_LIMIT // 2  
                # Half of original limit to accommodate multiple sorts
                
                if sort_method == "top":
                    submissions = sub.top(limit=posts_per_sort, time_filter=time_filter)
                else:
                    submissions = getattr(sub, sort_method)(limit=posts_per_sort)
                
                # Process submissions
                for submission in submissions:
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
                            "subscribers":     subscribers,
                            "sort_method":     sort_method,
                            "time_filter":     time_filter if sort_method == "top" else None
                        },
                        "hashtags":        [],
                        "topics":          [],
                        "language":        None
                    }
                    
                    # Get comments
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
                    all_posts.append(doc)
                    
            except Exception as e:
                print(f"Error getting {sort_method} posts for r/{self.subreddit}: {str(e)}")
                # If one sort method fails, continue with others
                continue
        
        # Remove duplicates based on post ID
        unique_posts = {}
        for post in all_posts:
            unique_posts[post["_id"]] = post
            
        return list(unique_posts.values())

    def extract_posts(self) -> List[Dict[str, Any]]:
        """not used for now"""
        return self.extract_posts_with_diverse_sorting()

    def store(self, db: MongoDBConnector) -> int:
        """Store posts in the database
        Args:
            db: MongoDBConnector object
        Returns:
            int: Number of posts stored
        """
        col = db.get_collection(REDDIT_COLLECTION)
        # Using the new diverse sorting method
        posts = self.extract_posts_with_diverse_sorting()
        inserted = 0
        for p in posts:
            col.replace_one({"_id": p["_id"]}, p, upsert=True)
            inserted += 1
        return inserted

    def store(self, db: MongoDBConnector) -> int:
        """Store posts in the database
        Args:
            db: MongoDBConnector object
        Returns:
            int: Number of posts stored
        """
        col = db.get_collection(REDDIT_COLLECTION)
        posts = self.extract_posts()
        inserted = 0
        for p in posts:
            col.replace_one({"_id": p["_id"]}, p, upsert=True)
            inserted += 1
        return inserted

    
# ----- Main function to run social listening scraper ------

if __name__ == "__main__":

    # MongoDB connector
    db = MongoDBConnector()
    
    # Reddit scraper
    for sr in SUBREDDIT_TOPICS:
        count = RedditScraper(subreddit=sr).store(db)
        print(f"r/{sr}: stored {count} posts")
    