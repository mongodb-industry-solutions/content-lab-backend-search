# --- test_embeddings.py ---

# This file is used to test the embeddings for the news and reddit collections.

# Import the necessary libraries.
import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import time
import random

# sys.path hack to reach the modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.mdb import MongoDBConnector
from bedrock.cohere_embeddings import BedrockCohereEnglishEmbeddings
from _vector_search_idx_creator import VectorSearchIDXCreator
from embeddings.process_embeddings import ContentEmbedder
from .process_embeddings import ContentEmbedder

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

NEWS_COLLECTION = os.getenv("NEWS_COLLECTION", "news")
REDDIT_COLLECTION = os.getenv("REDDIT_COLLECTION", "reddit_posts")

class SnippetGenerator:
    """
    Using the News and Reddit results to generate concise snippets.
    """

    def __init__(self, max_sentences: int = 2, max_comments: int = 3):
        """
        Initialize the SnippetGenerator.
        Args:
            max_sentences: int, the maximum number of sentences to include in the snippet
            max_comments: int, the maximum number of comments to include in the snippet
        Returns:
            None
        """
        self.max_sentences = max_sentences
        self.max_comments = max_comments

    def _clean(self, text: str) -> str:
        """Strip whitespace and newlines.
        Args:
            text: str, the text to clean
        Returns:
            str: The cleaned text
        """
        if not text:
            return ""
        return text.strip().replace('\n', ' ')

    def _tokenize_sentences(self, text: str) -> List[str]:
        """
        Naively split text into sentences by scanning for '.', '?' or '!' 
        and ending each sentence there.
        Args:
            text: str, the text to tokenize
        Returns:
            List[str]: The tokenized text
        """
        if not text:
            return []

        sentences: List[str] = []
        current: str = ""
        for char in text:
            current += char
            if char in ('.', '?', '!'):
                stripped = current.strip()
                if stripped:
                    sentences.append(stripped)
                current = ""
        # Catch any trailing text without terminal punctuation
        if current.strip():
            sentences.append(current.strip())
        return sentences

    def news_snippet(self, article: Dict[str, Any]) -> str:
        """Generate a snippet from the news article.
        Args:
            article: Dict[str, Any], the news article to generate a snippet from
        Returns:
            str: The generated snippet
        """
        title = self._clean(article.get('title', ''))
        body = self._clean(article.get('description') or article.get('content', '') or '')
        teaser_parts = self._tokenize_sentences(body)[:self.max_sentences]
        teaser = ' '.join(teaser_parts)
        if teaser:
            return f"{title}\n{teaser}"
        return title

    def reddit_snippet(self, post: Dict[str, Any]) -> str:
        """Generate a snippet from the reddit post.
        Args:
            post: Dict[str, Any], the reddit post to generate a snippet from
        Returns:
            str: The generated snippet
        """
        title = self._clean(post.get('title', ''))
        comments: List[str] = []
        for c in post.get('comments', [])[:self.max_comments]:
            if c and isinstance(c, dict):
                body = c.get('body', '').strip()
                if body:
                    comments.append(self._clean(body))
        if comments:
            return f"{title}\n" + "\n".join(comments)
        return title

    def generate(self, results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[str]]:
        """Generate snippets from the results.
        Args:
            results: Dict[str, List[Dict[str, Any]]], the results to generate snippets from
        Returns:
            Dict[str, List[str]]: The generated snippets
        """
        return {
            'news': [self.news_snippet(a) for a in results.get('news', []) if a.get('title')],
            'reddit': [self.reddit_snippet(p) for p in results.get('reddit_posts', []) if p.get('title')]
        }

def check_embeddings():
    """Check the embeddings for the news and reddit collections.
    This is a check function for embeddings.
    """
    db = MongoDBConnector()
    news_count = db.get_collection("news").count_documents({"embedding": {"$exists": True}})
    posts_count = db.get_collection("reddit_posts").count_documents({"embedding": {"$exists": True}})
    print(f"Documents with embeddings - News: {news_count}, Reddit Posts: {posts_count}")

def convert_query_to_embedding(query_text: str):
    """Convert user query to embedding vector.
    Args:
        query_text: str, the query to convert to an embedding
    Returns:
        List[float]: The embedding vector
    """
    embedder = BedrockCohereEnglishEmbeddings()
    try:
        embedding = embedder.predict(query_text)
        logger.info(f"Generated embedding for query: '{query_text}'")
        return embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return None

# Search for similar content in the news and reddit collections.
def search_similar_content(query_embedding, limit: int = 5, enable_diversity: bool = True):
    """
    Search for similar content with optional simple diversity.
    
    Args:
        query_embedding: The query embedding vector
        limit: Number of results per collection
        enable_diversity: Whether to enable diversity (True) or just return most similar (False)
    Returns:
        Dict containing search results from each collection
    """
    db = MongoDBConnector()
    all_results = {}
    collection_names = ["news", "reddit_posts"]
    
    # Get more candidates if diversity is enabled
    search_limit = limit * 3 if enable_diversity else limit
    
    for collection_name in collection_names:
        try:
            collection = db.get_collection(collection_name)
            
            # Get more results than needed
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "vector_index",
                        "path": "embedding",
                        "queryVector": query_embedding,
                        "numCandidates": search_limit * 2,
                        "limit": search_limit
                    }
                },
                {
                    "$addFields": {
                        "similarity_score": {"$meta": "vectorSearchScore"}
                    }
                },
                {
                    "$match": {
                        "embedding": {"$exists": True},
                        "title": {"$exists": True, "$ne": ""}
                    }
                }
            ]
            
            candidates = list(collection.aggregate(pipeline))
            logger.info(f"Found {len(candidates)} candidates in {collection_name}")
            
            # Super simple diversity implementation:
            if enable_diversity and len(candidates) > limit:
                # Take top result to ensure relevance
                top_result = candidates[0]
                
                # Randomly sample from the rest (excluding the top result)
                remaining = random.sample(candidates[1:], min(limit-1, len(candidates)-1))
                
                # Combine top result with random sample
                results = [top_result] + remaining
            else:
                # Just return top results by similarity
                results = candidates[:limit]
                
            all_results[collection_name] = results
            logger.info(f"Selected {len(results)} results from {collection_name}")
            
        except Exception as e:
            logger.error(f"Error searching {collection_name}: {e}")
            all_results[collection_name] = []
    
    return all_results

def display_results(results, query: str, collection_type: str):
    """Display the results of the search.
    Args:
        results: Dict[str, List[Dict[str, Any]]], the results to display
        query: str, the query that was used to search
        collection_type: str, the type of collection that was searched
    Returns:
        None
    """
    if not results:
        print(f"No results found for query: '{query}'")
        return

    print(f"\n--- {collection_type.upper()} results for '{query}' ---\n")
    for i, doc in enumerate(results, 1):
        title = doc.get('title', 'No title')
        score = doc.get('score', 0)
        url = doc.get('url', 'No URL')
        print(f"{i}. {title} (Score: {score:.4f})")
        if collection_type == "news":
            desc = doc.get('description', '')
            print(f"   {desc[:100]}..." if len(desc) > 100 else f"   {desc}")
            print(f"   Category: {doc.get('category', 'Unknown')}")
        else:
            print(f"   Subreddit: r/{doc.get('subreddit', 'Unknown')}")
            if doc.get('comments'):
                print("   Comments:")
                for j, comment in enumerate(doc["comments"][:3], 1):
                    body = comment.get("body", "")
                    preview = body[:100] + "..." if len(body) > 100 else body
                    print(f"      {j}. {preview}")
                if len(doc["comments"]) > 3:
                    print(f"      ... and {len(doc['comments'])-3} more comments")
        print(f"   URL: {url}\n")

def display_clean_snippets(snippets):
    """Display the cleaned snippets.
    Args:
        snippets: Dict[str, List[str]], the snippets to display
    Returns:
        None
    """
    print("\nCleaned Snippets (from News):")
    for i, snippet in enumerate(snippets['news'], 1):
        print(f"\nSnippet {i}:\n{snippet}")
        print("-" * 50)
    print("\nCleaned Snippets (from Reddit):")
    for i, snippet in enumerate(snippets['reddit'], 1):
        print(f"\nSnippet {i}:\n{snippet}")
        print("-" * 50)

# ---- Main function to run the embeddings test -----

if __name__ == "__main__":
    check_embeddings()
    query = "What is the trendy in Europe"
    print(f"\nExample search: '{query}'")
    query_embedding = convert_query_to_embedding(query)
    if query_embedding:
        """
        This is a test function for embeddings.
        It will:
        - Search for similar content in the news and reddit collections.
        - It takes the top 5 results from the search and generates snippets from them.
        - It displays the cleaned snippets.
        Args:
            query_embedding: List[float], the query embedding to search for
            limit: int, the maximum number of results to return
        Returns:
            Dict[str, List[Dict[str, Any]]]: The search results
        """
        # It looks for 5 results in the news and reddit collections.
        all_search_results = search_similar_content(query_embedding, 5)
        news_results = all_search_results.get("news", [])
        social_results = all_search_results.get("reddit_posts", [])
        generator = SnippetGenerator(max_sentences=2, max_comments=3)
        snippets = generator.generate({'news': news_results, 'reddit_posts': social_results})
        # Display the cleaned snippets.
        display_clean_snippets(snippets)

