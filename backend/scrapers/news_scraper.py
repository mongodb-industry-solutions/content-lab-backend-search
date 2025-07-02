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

# logging setup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------1. Abstract base class for news scrapers---------    

class NewsScraper(ABC):
    """Base class"""

    """
        Initialize a news scraper.
        
        Args:
            url (str): The URL to scrape
            category (str): The category of news (e.g., 'finance', 'tech')
    """

    def __init__(self, url: str, category: str):
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
    
    def store_articles(self, db_connector: MongoDBConnector, articles: List[Dict[str, Any]]) -> None:
        """
        Store articles in the database.
        
        Args:
            db_connector (MongoDBConnector): Database connector
            articles (List[Dict[str, Any]]): Articles to store
        """
        if not articles:
            logger.warning(f"No articles to store for {self.category}")
            return
        
        # Add metadata to articles
        timestamp = datetime.datetime.utcnow()
        for article in articles:
            article['category'] = self.category
            article['source_url'] = self.url
            article['scraped_at'] = timestamp
        
        collection_name = os.getenv("NEWS_COLLECTION", "news")
        
        try:
            db_connector.insert_many(collection_name, articles)
            logger.info(f"Stored {len(articles)} {self.category} articles in the {collection_name} collection")
        except Exception as e:
            logger.error(f"Error storing {self.category} articles in database: {e}")
            
        client = db_connector.client  
        print("Databases on server:", client.list_database_names())
        db = client[db_connector.database_name]  
        print("Collections in that DB:", db.list_collection_names())
    
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
        visits_scale = 10000  # Scale for number of visits
        retention_scale = 300  # Scale for retention (in seconds)
        comments_scale = 500  # Scale for number of comments
        shares_scale = 1000   # Scale for number of shares
        
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
                
                articles = data.get("articles", [])
                if not articles:
                    break
                
                for raw in articles:
                    article_url = raw.get("url")
                    article = {
                        "url": article_url,
                        "title": raw.get("title"),
                        "description": raw.get("description"),
                        "content": raw.get("content"),
                        "author": raw.get("author"),
                        "source": raw.get("source", {}).get("name"),
                        "published_at": raw.get("publishedAt"),
                        "source_type": "newsapi", 
                        "country": self.country, 
                        "News_metrics": self.generate_metrics(article_url)
                        
                    }
                    
                    if article["url"]:  # Only add if URL exists
                        all_articles.append(article)
                
                logger.info(f"Page {page}: processed {len(articles)} articles from NewsAPI")
                sleep(1)  # Be kind to the API
        
        except Exception as e:
            logger.error(f"Error extracting articles from NewsAPI: {e}")
        
        return all_articles
    
    def run_for_multiple_categories(self, categories, db_connector):
        """
        Run the scraper for multiple categories.
        
        Args:
            categories (List[str]): List of categories to scrape
            db_connector (MongoDBConnector): Database connector
        """
        total_articles = 0
        
        for category in categories:
            logger.info(f"Fetching articles for category: {category}")
            # Update the category for this run
            self.category = category
            
            # Extract and store articles
            articles = self.extract_articles()
            self.store_articles(db_connector, articles)
            total_articles += len(articles)
        
        logger.info(f"Completed scraping from NewsAPI. Total articles: {total_articles}")


# Example run 

if __name__ == "__main__":

    try:
        # MongoDB connector
        db_connector = MongoDBConnector()

        # NewsAPI scraper
        logger.info("Running NewsAPI scraper...")
        newsapi_scraper = NewsAPIScraper()
        categories = ["technology", "health", "sports", "barcelona", "entertainment", "business"]


        categories = ["trending", "barcelona", "technology","health","sports","politics", "science", "business", "entertainment", "environment", "travel"]
        newsapi_scraper.run_for_multiple_categories(categories, db_connector)

        logger.info(f"Completed all scraping tasks.")

    except Exception as e:

        logger.error(f"An error occurred: {e}")



        