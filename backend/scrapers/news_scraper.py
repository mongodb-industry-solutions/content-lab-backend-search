# ---news_scraper.py---

# This file is used to scrape news articles from the NewsAPI.

# Import the necessary libraries.
import requests
from bs4 import BeautifulSoup
import logging
from abc import ABC, abstractmethod
import datetime
from typing import List, Dict, Any
import sys
import os
import feedparser
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from time import sleep
import numpy as np
import hashlib

# Add the parent directory to the system path to import config_loader
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.mdb import MongoDBConnector

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# News_Categories Global Variable
NEWS_CATEGORIES = ["technology", "health", "sports", "politics",
               "science", "business", "entertainment", "general"]

# ---------1. Abstract base class for news scrapers---------    

class NewsScraper(ABC):
    """Base class for news scrapers"""
    
    def __init__(self, url: str, category: str):
        """
        Initialize a news scraper.
        Args:
            url (str): The URL to scrape
            category (str): The category of news (e.g., 'finance', 'tech')
        """
        self.url = url
        self.category = category
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def _fetch_page(self) -> BeautifulSoup:
        """
        Fetch the webpage and return a BeautifulSoup object.
        
        Returns:
            BeautifulSoup: Parsed HTML content
            
        Raises:
            RequestException: If the request fails
        """
        try:
            response = requests.get(self.url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except requests.RequestException as e:
            logger.error(f"Error fetching {self.url}: {e}")
            raise
    
    @abstractmethod
    def extract_articles(self) -> List[Dict[str, Any]]:
        """
        Extract articles from the webpage.
        
        Returns:
            List[Dict[str, Any]]: List of article dictionaries with title, summary, url, etc.
        """
        pass
    
    def store_articles(self, db_connector: MongoDBConnector, articles: List[Dict[str, Any]]) -> int:
        """
        Store articles in the database using upsert pattern to prevent duplicates.
        
        Args:
            db_connector (MongoDBConnector): Database connector
            articles (List[Dict[str, Any]]): Articles to store
        Returns:
            int: Number of articles actually stored/updated
        """
        if not articles:
            logger.warning(f"No articles to store for {self.category}")
            return 0
        
        # Add metadata to articles
        timestamp = datetime.datetime.utcnow()
        processed_articles = []
        
        for article in articles:
            # Skip articles without URL (required for deduplication)
            if not article.get('url'):
                logger.warning(f"Skipping article without URL: {article.get('title', 'No title')}")
                continue
                
            processed_article = article.copy()
            processed_article.update({
                'category': self.category,
                'source_url': self.url,
                'scraped_at': timestamp,
                'type': 'news'  # Add type for consistency
            })
            
            # Ensure required fields exist
            if not processed_article.get('title'):
                processed_article['title'] = 'No title available'
            if not processed_article.get('source'):
                processed_article['source'] = 'Unknown'
            
            processed_articles.append(processed_article)
        
        if not processed_articles:
            logger.warning(f"No valid articles to store for {self.category}")
            return 0
        
        collection_name = os.getenv("NEWS_COLLECTION", "news")
        
        try:
            # Use upsert_many method to prevent duplicates
            result = db_connector.upsert_many(collection_name, processed_articles, unique_field="url")
            total_stored = result["upserted"] + result["updated"]
            
            logger.info(f"Stored {total_stored} {self.category} articles in the {collection_name} collection "
                       f"(New: {result['upserted']}, Updated: {result['updated']})")
            
            return total_stored
            
        except Exception as e:
            logger.error(f"Error storing {self.category} articles in database: {e}")
            return 0
    
    def generate_metrics(self, url: str) -> Dict[str, int]:
        """
        Provide consistent metrics for an article based on its URL.

        Args:
            url (str): The article URL to use as seed
            
        Returns:
            Dict[str, int]: Dictionary containing the generated metrics
        """
        if not url:
            return {
                "Total_visits": 0,
                "Total_retention": 0, 
                "total_Comments": 0,
                "Total_shares": 0
            }
        # Create a seed from the URL
        url_hash = int(hashlib.md5(url.encode('utf-8')).hexdigest(), 16) % (2**32)
        np.random.seed(url_hash)

        # Generate log-normal distribution values (centered at 1.0, σ=0.5)
        base_value = np.random.lognormal(mean=0.0, sigma=0.5)

        # Scale to reasonable ranges for each metric type
        visits_scale = 10000  
        retention_scale = 300 
        comments_scale = 500  
        shares_scale = 1000  

        visit_factor = np.random.lognormal(mean=0.0, sigma=0.3)
        retention_factor = np.random.lognormal(mean=0.0, sigma=0.3)
        comment_factor = np.random.lognormal(mean=0.0, sigma=0.4)
        share_factor = np.random.lognormal(mean=0.0, sigma=0.35)

        return {
            "Total_visits": int(base_value * visits_scale * visit_factor),
            "Total_retention": int(base_value * retention_scale * retention_factor),
            "total_Comments": int(base_value * comments_scale * comment_factor),
            "Total_shares": int(base_value * shares_scale * share_factor)
        }

# ----------------a. NewsAPI Example-----------------------

class NewsAPIScraper(NewsScraper):
    """Using the NewsAPI to fetch articles about a specific topic."""

    def __init__(self, category='technology', page_size=20, max_pages=2, country='us', language='en'):
        self.api_key = os.getenv("NEWSAPI_KEY")
        if not self.api_key:
            raise ValueError("NEWSAPI_KEY not found in environment variables")
        
        self.category = category
        self.page_size = page_size
        self.max_pages = max_pages
        self.country = country
        self.language = language
        
        # Base URL for NewsAPI
        url = "https://newsapi.org/v2/top-headlines"
        super().__init__(url, category)
    
    def extract_articles(self) -> List[Dict[str, Any]]:
        """
        Extract articles from NewsAPI.
    
        Returns:
            List[Dict[str, Any]]: List of articles from NewsAPI
        """
        all_articles = []
        
        try:
            for page in range(1, self.max_pages + 1):
                params = {
                    "apiKey": self.api_key,
                    "category": self.category,
                    "pageSize": self.page_size,
                    "page": page,
                    "language": self.language,
                    "country": self.country
                }
                
                response = requests.get(self.url, params=params)
                response.raise_for_status()
                data = response.json()
                
                # Check if API request was successful
                if data.get('status') != 'ok':
                    logger.error(f"NewsAPI error: {data.get('message', 'Unknown error')}")
                    continue
                
                articles = data.get("articles", [])
                if not articles:
                    logger.info(f"No more articles found for {self.category} on page {page}")
                    break
                
                processed_articles = []
                for raw in articles:
                    # Skip articles without URL or title
                    if not raw.get('url') or not raw.get('title'):
                        continue
                    
                    # Skip articles with '[Removed]' content (NewsAPI removes some content)
                    if raw.get('title') == '[Removed]' or raw.get('description') == '[Removed]':
                        continue
                    
                    article_url = raw.get("url")

                    def safe_strip(value):
                        return value.strip() if value and isinstance(value, str) else ""

                    article = {
                    "url": safe_strip(article_url),
                    "title": safe_strip(raw.get("title")),
                    "description": safe_strip(raw.get("description")),
                    "content": safe_strip(raw.get("content")),
                    "author": safe_strip(raw.get("author")) or "Unknown",
                    "source": raw.get("source", {}).get("name") or "NewsAPI",
                    "published_at": raw.get("publishedAt") or "",
                    "url_to_image": raw.get("urlToImage") or "",
                    "source_type": "newsapi", 
                    "country": self.country, 
                    "News_metrics": self.generate_metrics(article_url)
                    }
                    if article["url"] and article["title"]:
                        processed_articles.append(article)
                
                all_articles.extend(processed_articles)
                logger.info(f"Page {page}: processed {len(processed_articles)} articles from NewsAPI")
                
                # Add delay between requests to be respectful to the API
                if page < self.max_pages:
                    sleep(1)
        
        except requests.RequestException as e:
            logger.error(f"Error fetching articles from NewsAPI: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in NewsAPI scraper: {e}")
        
        return all_articles
    
    def run_for_multiple_categories(self, categories: List[str], db_connector: MongoDBConnector) -> int:
        """
        Run the scraper for multiple categories.
        
        Args:
            categories (List[str]): List of categories to scrape
            db_connector (MongoDBConnector): Database connector
        Returns:
            int: Total number of articles stored
        """
        total_articles = 0
        
        for category in categories:
            logger.info(f"Fetching articles for category: {category}")
            
            # Update the category for this run
            self.category = category
            
            # Extract and store articles
            articles = self.extract_articles()
            stored_count = self.store_articles(db_connector, articles)
            total_articles += stored_count
            
            # Add delay between categories to be respectful to the API
            sleep(2)
        
        logger.info(f"Completed scraping from NewsAPI. Total articles: {total_articles}")
        return total_articles

# ----Main function to run news scraper------

if __name__ == "__main__":
    try:
        # MongoDB connector
        db_connector = MongoDBConnector()
        
        # Ensure indexes are created
        db_connector.ensure_indexes()

        # NewsAPI scraper
        logger.info("Running NewsAPI scraper...")
        newsapi_scraper = NewsAPIScraper()
        total_stored = newsapi_scraper.run_for_multiple_categories(NEWS_CATEGORIES, db_connector)
        logger.info(f"Completed all scraping tasks. Total articles stored: {total_stored}")

    except Exception as e:
        logger.error(f"An error occurred: {e}")