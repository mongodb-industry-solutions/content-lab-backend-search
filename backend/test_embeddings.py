# --- test_embeddings.py ---


import os
import sys
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import time

import spacy
nlp = spacy.load("en_core_web_sm")
print("Using spaCy")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.mdb import MongoDBConnector
from bedrock.cohere_embeddings import BedrockCohereEnglishEmbeddings
from _vector_search_idx_creator import VectorSearchIDXCreator
from process_embeddings import ContentEmbedder

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

NEWS_COLLECTION = os.getenv("NEWS_COLLECTION", "news")
REDDIT_COLLECTION = os.getenv("REDDIT_COLLECTION", "reddit_posts")

# --- SnippetGenerator class ---- 
# ----- Generating snippets from search results -----

class SnippetGenerator:
    """
    Using the News and Reddit results to generate concise snippets.
    """

    def __init__(self, max_sentences: int = 3, max_comments: int = 4):
        self.max_sentences = max_sentences
        self.max_comments = max_comments

    def _clean(self, text: str) -> str:
        """Strip whitespace and newlines."""
        if not text:
            return ""
        return text.strip().replace('\n', ' ')

    def _tokenize_sentences(self, text: str) -> List[str]:
        """Tokenize text into sentences using spaCy if available."""
        if not text:
            return []
            
        if nlp:
            # Use spaCy for tokenization
            doc = nlp(text)
            return [sent.text for sent in doc.sents]
        else:
            # Very simple fallback
            return [text]

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
        comments = []
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

# -----Check if embeddings exist in the collections -----

def check_embeddings():
    db = MongoDBConnector()
    news_count = db.get_collection("news").count_documents({"embedding": {"$exists": True}})
    posts_count = db.get_collection("reddit_posts").count_documents({"embedding": {"$exists": True}})
    print(f"Documents with embeddings - News: {news_count}, Reddit Posts: {posts_count}")


# 1. Function to convert user query to embedding

def convert_query_to_embedding(query_text):
    """Convert user query to embedding vector."""
    embedder = BedrockCohereEnglishEmbeddings()
    try:
        embedding = embedder.predict(query_text)
        logger.info(f"Generated embedding for query: '{query_text}'")
        return embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return None

# 2. Function to search for similar content using vector search

def search_similar_content(query_embedding, limit=3):
    db = MongoDBConnector()
    all_results = {}
    collection_names = ["news", "reddit_posts"]

    for collection_name in collection_names:
        collection = db.get_collection(collection_name)

        pipeline = [
            {
                "$vectorSearch": {
                    "index": "semantic_search_embeddings",
                    "queryVector":   query_embedding,
                    "path":     "embedding",
                    "limit":        limit,
                    "numCandidates": limit * 3
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


# 3. Function to display search results

def display_results(results, query, collection_type):
    """
    Display search results in a readable format.
    
    Args:
        results: List of search results
        query: The original search query
        collection_type: Type of collection (news or reddit)
    """
    if not results:
        print(f"No results found for query: '{query}'")
        return
    
    print(f"\n--- {collection_type.upper()} results for '{query}' ---\n")
    for i, doc in enumerate(results, 1):
        # Display common fields
        title = doc.get('title', 'No title')
        score = doc.get('score', 0)
        url = doc.get('url', 'No URL')
        
        print(f"{i}. {title} (Score: {score:.4f})")
        
        # For news articles
        if collection_type == "news":
            if "description" in doc:
                desc = doc['description']
                print(f"   {desc[:100]}..." if len(desc) > 100 else f"   {desc}")
            if "category" in doc:
                print(f"   Category: {doc.get('category', 'Unknown')}")
        
        # For reddit posts
        else:
            if "subreddit" in doc:
                print(f"   Subreddit: r/{doc.get('subreddit', 'Unknown')}")
            if "comments" in doc and doc["comments"]:
                print("   Comments:")
                # Upto 3 comments to keep output readable
                for j, comment in enumerate(doc["comments"][:3], 1):
                    body = comment.get("body", "")
                    if body:
                        # Truncate long comments
                        comment_preview = body[:100] + "..." if len(body) > 100 else body
                        print(f"      {j}. {comment_preview}")
                # If there are more comments, indicate it
                if len(doc["comments"]) > 3:
                    print(f"      ... and {len(doc['comments'])-3} more comments")
        
                
        print(f"   URL: {url}")
        print()

def display_clean_snippets(snippets):
    """Display the cleaned snippets in a readable format."""
    
    print("\nCleaned Snippets (from News):")
    for i, snippet in enumerate(snippets['news'], 1):
        print(f"\Snippet {i}:\n{snippet}")
        print("-" * 50)
    
    print("\nCleaned Snippets (from Reddit):")
    for i, snippet in enumerate(snippets['reddit'], 1):
        print(f"\Snippet {i}:\n{snippet}")
        print("-" * 50)
 
if __name__ == "__main__":
    check_embeddings()
    # Example search
    query = "What is trendy in Spain?"
    print(f"\nExample search: '{query}'")
    query_embedding = convert_query_to_embedding(query)

    if query_embedding: 
        all_search_results = search_similar_content(query_embedding, 5)
        news_results = all_search_results.get("news", [])
        social_results = all_search_results.get("reddit_posts", [])

        print("\nNews Collection: ")
        # display_results(news_results, query, "news")

        print("\Reddit posts: ")
        # display_results(social_results, query, "reddit_posts")

        generator = SnippetGenerator(max_sentences=2, max_comments=3)
        snippets = generator.generate({'news': news_results, 'reddit_posts': social_results})
        display_clean_snippets(snippets)
