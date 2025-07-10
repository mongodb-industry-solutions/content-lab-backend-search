# --- test_embeddings.py ---

import os
import sys
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import time

# sys.path hack to reach your modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.mdb import MongoDBConnector
from bedrock.cohere_embeddings import BedrockCohereEnglishEmbeddings
from _vector_search_idx_creator import VectorSearchIDXCreator
from embeddings.process_embeddings import ContentEmbedder

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
        self.max_sentences = max_sentences
        self.max_comments = max_comments

    def _clean(self, text: str) -> str:
        """Strip whitespace and newlines."""
        if not text:
            return ""
        return text.strip().replace('\n', ' ')

    def _tokenize_sentences(self, text: str) -> List[str]:
        """
        Naively split text into sentences by scanning for '.', '?' or '!' 
        and ending each sentence there.
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
        # catch any trailing text without terminal punctuation
        if current.strip():
            sentences.append(current.strip())
        return sentences

    def news_snippet(self, article: Dict[str, Any]) -> str:
        title = self._clean(article.get('title', ''))
        body = self._clean(article.get('description') or article.get('content', '') or '')
        teaser_parts = self._tokenize_sentences(body)[:self.max_sentences]
        teaser = ' '.join(teaser_parts)
        if teaser:
            return f"{title}\n{teaser}"
        return title

    def reddit_snippet(self, post: Dict[str, Any]) -> str:
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
        return {
            'news': [self.news_snippet(a) for a in results.get('news', []) if a.get('title')],
            'reddit': [self.reddit_snippet(p) for p in results.get('reddit_posts', []) if p.get('title')]
        }

def check_embeddings():
    db = MongoDBConnector()
    news_count = db.get_collection("news").count_documents({"embedding": {"$exists": True}})
    posts_count = db.get_collection("reddit_posts").count_documents({"embedding": {"$exists": True}})
    print(f"Documents with embeddings - News: {news_count}, Reddit Posts: {posts_count}")

def convert_query_to_embedding(query_text: str):
    """Convert user query to embedding vector."""
    embedder = BedrockCohereEnglishEmbeddings()
    try:
        embedding = embedder.predict(query_text)
        logger.info(f"Generated embedding for query: '{query_text}'")
        return embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return None

def search_similar_content(query_embedding, limit: int = 5):
    db = MongoDBConnector()
    all_results: Dict[str, List[Dict[str, Any]]] = {}
    collection_names = ["news", "reddit_posts"]

    for collection_name in collection_names:
        collection = db.get_collection(collection_name)
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "semantic_search_embeddings",
                    "queryVector": query_embedding,
                    "path": "embedding",
                    "limit": limit,
                    "numCandidates": limit * 4
                }
            },
            {
                "$project": {
                   "_id": 1,
                   "title": 1,
                   "description": 1,
                   "content": 1,
                   "url": 1,
                   "category": 1,
                   "subreddit": 1,
                   "comments": 1,
                   "score": { "$meta": "vectorSearchScore" }
                }
            }
        ]
        try:
            results = list(collection.aggregate(pipeline))
            logger.info(f"Found {len(results)} results in {collection_name}")
            all_results[collection_name] = results
        except Exception as e:
            logger.error(f"Error searching {collection_name}: {e}")
            all_results[collection_name] = []
    return all_results

def display_results(results, query: str, collection_type: str):
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
    print("\nCleaned Snippets (from News):")
    for i, snippet in enumerate(snippets['news'], 1):
        print(f"\nSnippet {i}:\n{snippet}")
        print("-" * 50)
    print("\nCleaned Snippets (from Reddit):")
    for i, snippet in enumerate(snippets['reddit'], 1):
        print(f"\nSnippet {i}:\n{snippet}")
        print("-" * 50)

if __name__ == "__main__":
    check_embeddings()
    query = "What is the trendy in Europe"
    print(f"\nExample search: '{query}'")
    query_embedding = convert_query_to_embedding(query)
    if query_embedding:
        all_search_results = search_similar_content(query_embedding, 5)
        news_results = all_search_results.get("news", [])
        social_results = all_search_results.get("reddit_posts", [])
        generator = SnippetGenerator(max_sentences=2, max_comments=3)
        snippets = generator.generate({'news': news_results, 'reddit_posts': social_results})
        display_clean_snippets(snippets)