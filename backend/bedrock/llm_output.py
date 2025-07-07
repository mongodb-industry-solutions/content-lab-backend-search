# ---- llm_output.py ----

# Process news and Reddit snippets using Claude Model from bedrock to extract structured insights.
import time
import os
import sys
import json
import re
import logging
from typing import Dict, List, Any, Optional
from json.decoder import JSONDecodeError
from bson import json_util
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from anthropic_chat_completions import BedrockAnthropicChatCompletions
from test_embeddings import SnippetGenerator, search_similar_content, convert_query_to_embedding
from db.mdb import MongoDBConnector
import datetime
import concurrent.futures

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Collection
SUGGESTION_COLLECTION = os.getenv("SUGGESTION_COLLECTION", "suggestions")

class ContentAnalyzer:
    """
    Process news and Reddit snippets using Claude to extract structured insights.
    """
    def __init__(self):
        self.llm = BedrockAnthropicChatCompletions()
        self.snippet_generator = SnippetGenerator(max_sentences=2, max_comments=3)

    def _clean_json(self, text: str) -> str:
        """Clean and extract valid JSON from LLM response."""
        # Find JSON array pattern
        json_match = re.search(r'\[\s*{.*}\s*\]', text, re.DOTALL)
        if json_match:
            text = json_match.group(0)
        
        # Fix common JSON errors
        text = re.sub(r',\s*}', '}', text)  
        text = re.sub(r',\s*\]', ']', text) 
        text = re.sub(r'\'', '"', text)      
        
        return text

    # -------- SIMPLIFIED Prompt Formatting Methods --------

    def _format_news_prompt(self, snippets: List[str], ids: List[str], urls: List[str]) -> str:
        """Simplified prompt template for news articles."""
        
        # Minimal header
        header = "Extract structured data from these news articles in JSON format."
        
        # Concise example
        example = (
            "EXAMPLE:\n"
            "Input: AI Ethics Group Warns of Risks in Healthcare Applications\n"
            "A leading AI ethics organization released concerns about AI in healthcare without proper validation.\n"
            "url: https://example.com/ai-ethics\n\n"
            "Output: [{\"topic\":\"AI ethics in healthcare\",\"keywords\":[\"AI validation\",\"medical oversight\",\"patient safety\",\"algorithmic bias\"],\"description\":\"Ethics experts warn about unvalidated AI systems in healthcare settings.\",\"label\":\"technology\",\"url\":\"https://example.com/ai-ethics\"}]"
        )

        # Format the articles to analyze
        items = []
        for idx, (_, snippet, url) in enumerate(zip(ids, snippets, urls), 1):
            items.append(f"{idx}. {snippet}\nurl: {url}")
        
        body = "\n\n".join(items)
        
        # Minimal instructions
        task = (
            "\n\nCreate a JSON array with objects containing:\n"
            "1. \"topic\": 3-5 word headline\n"
            "2. \"keywords\": EXACTLY 4 specific terms\n"
            "3. \"description\": One sentence summary (15 words max)\n"
            "4. \"label\": one of [\"technology\",\"business\",\"health\",\"culture\",\"sports\"]\n"
            "5. \"url\": source URL\n"
            "Use proper JSON format with double quotes."
        )
        
        return f"{header}\n\n{example}\n\n{body}{task}"

    def _format_reddit_prompt(self, snippets: List[str], ids: List[str], urls: List[Optional[str]]) -> str:
        """Simplified prompt template for Reddit posts."""
        
        # Minimal header
        header = "Extract structured data from these Reddit posts in JSON format."
        
        # Concise example
        example = (
            "EXAMPLE:\n"
            "Input: Will AI replace programmers?\n"
            "Comment: AI tools help but can't debug complex systems.\n"
            "Comment: GitHub Copilot saves time on boilerplate code.\n"
            "url: https://reddit.com/example\n\n"
            "Output: [{\"topic\":\"AI impact on programming\",\"keywords\":[\"job security\",\"coding assistants\",\"automation\",\"developer tools\"],\"description\":\"Mixed opinions on AI's impact on programming careers.\",\"label\":\"technology\",\"url\":\"https://reddit.com/example\"}]"
        )
        
        # Format the posts to analyze
        items = []
        for idx, (_, snippet, url) in enumerate(zip(ids, snippets, urls), 1):
            url_line = f"url: {url}" if url else "url: null"
            items.append(f"{idx}. {snippet}\n{url_line}")
        
        body = "\n\n".join(items)
        
        # Minimal instructions
        task = (
            "\n\nCreate a JSON array with objects containing:\n"
            "1. \"topic\": 3-5 word focus\n"
            "2. \"keywords\": EXACTLY 4 specific terms\n"
            "3. \"description\": One sentence on community sentiment (15 words max)\n"
            "4. \"label\": one of [\"technology\",\"business\",\"health\",\"culture\",\"sports\"]\n"
            "5. \"url\": source URL or null\n"
            "Use proper JSON format with double quotes."
        )
        
        return f"{header}\n\n{example}\n\n{body}{task}"
    
    # News Processing 

    def process_news(self, news_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        snippets, ids, urls = [], [], []
        for article in news_results:
            snippets.append(self.snippet_generator.news_snippet(article))
            ids.append(article.get('_id', ''))
            urls.append(article.get('url', ''))
        
        prompt = self._format_news_prompt(snippets, ids, urls)
        logger.info("Sending batch news prompt to Claude")
        
        response = self.llm.predict(prompt)
        logger.debug(f"Raw response (first 100 chars): {response[:100]}...")
        
        try:
            # Direct parsing
            analysis = json.loads(response)
        except JSONDecodeError as e:
            logger.warning(f"Initial JSON parsing failed: {e}")
            # Cleaning the response
            cleaned = self._clean_json(response)
            logger.debug(f"Cleaned response (first 100 chars): {cleaned[:100]}...")
            try:
                analysis = json.loads(cleaned)
            except JSONDecodeError as e:
                logger.error(f"Failed to parse JSON even after cleaning: {e}")
                logger.error(f"Response: {response}")
                return []
        
        return analysis
    
    # Reddit Processing 
    
    def process_reddit(self, reddit_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        snippets, ids, urls = [], [], []
        for post in reddit_results:
            snippets.append(self.snippet_generator.reddit_snippet(post))
            ids.append(post.get('_id', ''))
            urls.append(post.get('url'))
        
        prompt = self._format_reddit_prompt(snippets, ids, urls)
        logger.info("Sending batch Reddit prompt to Claude")
        
        response = self.llm.predict(prompt)
        logger.debug(f"Raw response (first 100 chars): {response[:100]}...")
        
        try:
            # First try direct parsing
            analysis = json.loads(response)
        except JSONDecodeError as e:
            logger.warning(f"Initial JSON parsing failed: {e}")
            # Try cleaning the response
            cleaned = self._clean_json(response)
            logger.debug(f"Cleaned response (first 100 chars): {cleaned[:100]}...")
            
            try:
                analysis = json.loads(cleaned)
            except JSONDecodeError as e:
                logger.error(f"Failed to parse JSON even after cleaning: {e}")
                logger.error(f"Response: {response}")
                return []
        
        return analysis

    def analyze_search_results(self, query: str) -> Dict[str, List[Dict[str, Any]]]:
        start_time = time.time()
    
        # Embedding generation timing
        embed_start = time.time()
        query_embedding = convert_query_to_embedding(query)
        embed_time = time.time() - embed_start
        logger.info(f"Embedding generation took {embed_time:.2f} seconds")
        
        if not query_embedding:
            logger.error("Failed to generate embedding for query")
            return {"suggestions": []} 

        search_start = time.time()
        all_results = search_similar_content(query_embedding, 1)  # Reduced from 2 to 1 for faster processing
        search_time = time.time() - search_start
        logger.info(f"Content search took {search_time:.2f} seconds")
        
        news_results = all_results.get("news", [])
        reddit_results = all_results.get("reddit_posts", [])

        # Use the threadPool here for parallel processing
        with concurrent.futures.ThreadPoolExecutor() as executor:
            news_start = time.time()
            future_news = executor.submit(self.process_news, news_results)

            reddit_start = time.time()
            future_reddit = executor.submit(self.process_reddit, reddit_results)

            news_analysis = future_news.result()
            news_time = time.time() - news_start
            logger.info(f"News analysis took {news_time:.2f} seconds")

            reddit_analysis = future_reddit.result()
            reddit_time = time.time() - reddit_start
            logger.info(f"Reddit analysis took {reddit_time:.2f} seconds")
        
        combined_results = []

        for item in news_analysis:
            item["source_type"] = "news"
            combined_results.append(item)
    
        for item in reddit_analysis:
            item["source_type"] = "reddit"
            combined_results.append(item)

        total_time = time.time() - start_time
        logger.info(f"Total analysis took {total_time:.2f} seconds")
    
        return {
            "suggestions": combined_results,
            "timing": {
                "embedding": embed_time,
                "search": search_time,
                "news_processing": news_time,
                "reddit_processing": reddit_time,
                "total": total_time
            }
        }
    
    # Save suggestions to MongoDB
    def store_analysis(self, db_connector: MongoDBConnector, analysis: Dict[str, List[Dict[str, Any]]], 
                  query: str = None) -> Dict[str, int]:
        if not analysis:
            logger.warning("No analysis results to store")
            return {"news": 0, "reddit": 0}
        
        timestamp = datetime.datetime.utcnow()
        stored_counts = {"news": 0, "reddit": 0}

        try:
            # Define content types mapping
            content_types = {
                "news": "news_analysis",
                "reddit": "reddit_analysis"
            }
            
            # Process each content type in a single loop
            for content_key, analysis_type in content_types.items():
                # Prepare documents for this content type
                docs = []
                for item in analysis.get(content_key, []):
                    doc = item.copy()
                    if "source_type" in doc:
                        del doc["source_type"]
                        
                    doc["type"] = analysis_type
                    doc["analyzed_at"] = timestamp
                    if query:
                        doc["source_query"] = query
                        
                    docs.append(doc)
                
                # Store documents if any exist
                if docs:
                    result = db_connector.insert_many(SUGGESTION_COLLECTION, docs)
                    stored_counts[content_key] = len(result)
                    logger.info(f"Stored {len(docs)} {content_key} analysis documents")
            
            return stored_counts
            
        except Exception as e:
            logger.error(f"Error storing analysis results: {e}")
            return {"news": 0, "reddit": 0}


    def analyze_and_store_search_results(self, query: str, db_connector: MongoDBConnector) -> Dict[str, Any]:
        """
        Analyze search results for a query and store them in the database.
        """
        # Get analysis results with combined structure
        analysis_start = time.time()
        result = self.analyze_search_results(query)
        analysis_time = time.time() - analysis_start
        
        # Split them back for storage
        suggested_results = {
            "news": [item for item in result["suggestions"] if item.get("source_type") == "news"],
            "reddit": [item for item in result["suggestions"] if item.get("source_type") == "reddit"]
        }
        
        # Store results in MongoDB
        storage_start = time.time()
        storage_counts = self.store_analysis(db_connector, suggested_results, query)
        storage_time = time.time() - storage_start
        logger.info(f"Database storage took {storage_time:.2f} seconds")
        
        timing = result.get("timing", {})
        timing["storage"] = storage_time
        timing["total_with_storage"] = analysis_time + storage_time
        
        return {
            "analysis": result["suggestions"],
            "stored": storage_counts,
            "timing": timing
        }
    

if __name__ == "__main__":
    analyzer = ContentAnalyzer()
    db_connector = MongoDBConnector()

    query = "What is the trending in Spain?"
    results = analyzer.analyze_and_store_search_results(query, db_connector)

    print(f"Analysis complete. Stored {results['stored']['news']} news and {results['stored']['reddit']} Reddit analysis documents.")
    print(json_util.dumps(results['analysis'], indent=2))
    
    # Print timing information
    if "timing" in results:
        print("\nTiming information:")
        for step, duration in results["timing"].items():
            print(f"  - {step}: {duration:.2f} seconds")