# ---- llm_output.py ----

# Process news and Reddit snippets using Claude Model from bedrock to extract structured insights.

# Import the necessary libraries.
import os
import sys
import json
import re
import logging
import hashlib
from typing import Dict, List, Any, Optional
from json.decoder import JSONDecodeError
from bson import json_util
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from .anthropic_chat_completions import BedrockAnthropicChatCompletions # this is an import from the same directory
from embeddings.test_embeddings import SnippetGenerator, search_similar_content, convert_query_to_embedding
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
    Process news and Reddit snippets using LLMs to extract structured insights.
    """
    def __init__(self):
        """
        Initialize the ContentAnalyzer.
        Args:
            None
        Returns:
            None
        """
        self.llm = BedrockAnthropicChatCompletions()
        self.snippet_generator = SnippetGenerator(max_sentences=2, max_comments=3)

    def _clean_json(self, text: str) -> str:
        """
        Clean and extract valid JSON from LLM response.
        Args:
            text: str, the text to clean
        Returns:
            str: The cleaned text
        """
        # Find JSON array pattern
        json_match = re.search(r'\[\s*{.*}\s*\]', text, re.DOTALL)
        if json_match:
            text = json_match.group(0)
        
        # Fix common JSON errors
        text = re.sub(r',\s*}', '}', text)  
        text = re.sub(r',\s*\]', ']', text) 
        text = re.sub(r'\'', '"', text)      
        
        return text
    
    # -------- Deduplication Logic Methods --------

    def _generate_suggestion_id(self, topic: str, url: str, source_query: str) -> str:
        """
        Generate a consistent ID for a suggestion based on topic, URL, and query.
        This helps identify duplicate suggestions.
        
        Args:
            topic: str, the topic of the suggestion
            url: str, the URL of the source content
            source_query: str, the query that generated this suggestion
        Returns:
            str: A unique identifier for this suggestion
        """
        # Create a consistent hash from key fields
        content = f"{topic.lower().strip()}|{url}|{source_query.lower().strip()}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def _check_suggestion_exists(self, db_connector: MongoDBConnector, suggestion_id: str) -> bool:
        """
        Check if a suggestion with the given ID already exists in the database.
        
        Args:
            db_connector: MongoDBConnector, the database connector
            suggestion_id: str, the ID to check for
        Returns:
            bool: True if suggestion exists, False otherwise
        """
        collection = db_connector.get_collection(SUGGESTION_COLLECTION)
        existing = collection.find_one({"suggestion_id": suggestion_id})
        return existing is not None

    def _is_similar_suggestion(self, db_connector: MongoDBConnector, topic: str, label: str, source_query: str) -> bool:
        """
        Check if a similar suggestion already exists based on topic similarity.
        
        Args:
            db_connector: MongoDBConnector, the database connector
            topic: str, the topic to check
            label: str, the label/category
            source_query: str, the source query
        Returns:
            bool: True if similar suggestion exists, False otherwise
        """
        collection = db_connector.get_collection(SUGGESTION_COLLECTION)
        
        # Check for exact topic match with same query and label
        similar = collection.find_one({
            "topic": {"$regex": f"^{re.escape(topic)}$", "$options": "i"},
            "label": label,
            "source_query": source_query
        })
        
        return similar is not None


    # -------- Prompt Formatting Methods --------

    def _format_news_prompt(self, snippets: List[str], ids: List[str], urls: List[str]) -> str:
        header = (
            "You are a precise news analyst trained to extract structured information. "
            "Analyze the news articles contextually and extract specific fields in a consistent JSON format."
        )
        example = (
            "EXAMPLE INPUT:\n"
            "1. AI Ethics Group Warns of Risks in Healthcare Applications\n"
            "A leading AI ethics organization released a report highlighting concerns about rapid deployment "
            "of AI systems in healthcare without proper validation or oversight.\n"
            "url: https://example.com/ai-ethics-healthcare\n\n"
            "EXAMPLE OUTPUT:\n"
            "[\n"
            "  {\n"
            "    \"topic\": \"AI ethics in healthcare\",\n"
            "    \"keywords\": [\"AI validation\", \"medical oversight\", \"patient safety\", \"algorithmic bias\", \"regulatory gaps\"],\n"
            "    \"description\": \"Ethics experts warn that deploying unvalidated AI systems in healthcare settings poses significant risks to patient outcomes and data privacy.\",\n"
            "    \"label\": \"technology\",\n"
            "    \"url\": \"https://example.com/ai-ethics-healthcare\"\n"
            "  }\n"
            "]\n"
            "---END OF EXAMPLE---\n"
        )
        items = []
        for idx, (_, snippet, url) in enumerate(zip(ids, snippets, urls), 1):
            items.append(f"{idx}. {snippet}\nurl: {url}")
        body = "\n\n".join(items)
        task = (
            "\n\nIMPORTANT:\n"
            "- Do NOT use any URLs or content from the example above. Only use the URLs and content from the articles provided below.\n"
            "- Your output MUST be a single valid JSON array of objects, and NOTHING ELSE.\n"
            "- Do NOT include any explanation, introductory text, or comments before or after the JSON array.\n"
            "- Do NOT repeat the example in your output.\n"
            "- Use double quotes (\") for all keys and string values in the JSON.\n"
            "- If a string value contains double quotes, escape them with a backslash (e.g., \"some \\\"quoted\\\" text\").\n"
            "- Ensure the JSON is properly formatted with correct commas and brackets.\n"
            "- The output should be directly parsable by Python's json.loads().\n"
            "\nFor each article above, create a JSON object with these fields:\n"
            "1. \"topic\": A precise 3-5 word headline capturing the core subject\n"
            "2. \"keywords\": An array of EXACTLY 4 specific, relevant terms (avoid generic words like 'technology' or 'health')\n"
            "3. \"description\": One clear, information-dense sentence summarizing the key insight and indicating why the user should write about this topic (aim for 15-20 words)\n"
            "4. \"label\": EXACTLY one of [\"technology\", \"business\", \"health\", \"culture\", \"sports\"] - choose the MOST specific match\n"
            "5. \"url\": The source URL\n"
        )
        return f"{header}\n\n{example}\n{body}{task}"

    def _format_reddit_prompt(self, snippets: List[str], ids: List[str], urls: List[Optional[str]]) -> str:
        header = (
            "You are a community insights analyst specializing in Reddit discourse analysis. "
            "Analyze the Reddit posts contextually and extract specific fields in a consistent JSON format."
        )
        example = (
            "EXAMPLE INPUT:\n"
            "1. Will AI replace programmers in the next 5 years?\n"
            "Comment: As someone working in ML for 8 years, no chance. AI tools are great assistants but terrible at "
            "understanding real-world constraints and debugging complex systems.\n"
            "Comment: My company is already using GitHub Copilot and it's saved me hours of boilerplate coding. "
            "I think junior dev roles will definitely change.\n"
            "url: https://reddit.com/r/programming/example\n\n"
            "EXAMPLE OUTPUT:\n"
            "[\n"
            "  {\n"
            "    \"topic\": \"AI impact on programming\",\n"
            "    \"keywords\": [\"job security\", \"coding assistants\", \"skill evolution\", \"industry perspective\", \"junior developers\"],\n"
            "    \"description\": \"The community has mixed opinions on AI's impact on programming careers, with experienced developers emphasizing AI's limitations while acknowledging its usefulness for routine tasks.\",\n"
            "    \"label\": \"technology\",\n"
            "    \"url\": \"https://reddit.com/r/programming/example\"\n"
            "  }\n"
            "]\n"
            "---END OF EXAMPLE---\n"
        )
        items = []
        for idx, (_, snippet, url) in enumerate(zip(ids, snippets, urls), 1):
            url_line = f"url: {url}" if url else "url: null"
            items.append(f"{idx}. {snippet}\n{url_line}")
        body = "\n\n".join(items)
        task = (
            "\nREAL INPUT:\n"
            f"{body}\n"
            "\nIMPORTANT:\n"
            "- For each output object, the \"url\" field MUST be set to the exact URL provided for that Reddit post. Do NOT invent or reuse any example URLs.\n"
            "- If the input does not provide a URL, set \"url\": null.\n"
            "- Your output MUST be a single valid JSON array of objects, and NOTHING ELSE.\n"
            "- Do NOT include any explanation, introductory text, or comments before or after the JSON array.\n"
            "- Do NOT repeat the example in your output.\n"
            "- Use double quotes (\") for all keys and string values in the JSON.\n"
            "- If a string value contains double quotes, escape them with a backslash (e.g., \"some \\\"quoted\\\" text\").\n"
            "- Ensure the JSON is properly formatted with correct commas and brackets.\n"
            "- The output should be directly parsable by Python's json.loads().\n"
            "\nFor each Reddit post above, create a JSON object with these fields:\n"
            "1. \"topic\": A precise 3-5 word phrase capturing the community's focus\n"
            "2. \"keywords\": An array of EXACTLY 4 terms reflecting community perspectives (be specific, avoid generic terms)\n"
            "3. \"description\": One sentence capturing the primary community sentiment, opinion, or concern and indicating why the user should write about this topic\n"
            "4. \"label\": EXACTLY one of [\"technology\", \"business\", \"health\", \"sports\", \"politics\", \"science\", \"general\", \"entertainment\"] - choose the MOST specific match\n"
            "5. \"url\": The source URL or null if unavailable\n"
        )
        return f"{header}\n\n{example}\n{body}{task}"
    
    # News Processing 

    def process_news(self, news_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process the news results.
        Args:
            news_results: List[Dict[str, Any]], the news results to process
        Returns:
            List[Dict[str, Any]]: The processed news results
        """
        snippets, ids, urls = [], [], []
        for article in news_results:
            snippets.append(self.snippet_generator.news_snippet(article))
            ids.append(article.get('_id', ''))
            urls.append(article.get('url', ''))
        
        prompt = self._format_news_prompt(snippets, ids, urls)
        logger.info("Sending batch news prompt")
        
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
        """
        Process the reddit results.
        Args:
            reddit_results: List[Dict[str, Any]], the reddit results to process
        Returns:
            List[Dict[str, Any]]: The processed reddit results
        """
        snippets, ids, urls = [], [], []
        for post in reddit_results:
            snippets.append(self.snippet_generator.reddit_snippet(post))
            ids.append(post.get('_id', ''))
            urls.append(post.get('url'))
        
        prompt = self._format_reddit_prompt(snippets, ids, urls)
        logger.info("Sending batch Reddit prompt")
        
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
    
    # Analyze the search results

    def analyze_search_results(self, query: str, enable_diversity: bool = True) -> Dict[str, List[Dict[str, Any]]]:
        """
        Analyze the search results with simple diversity option.
        Args:
            query: str, the query to analyze
            enable_diversity: bool, whether to enable diverse results
        Returns:
            Dict[str, List[Dict[str, Any]]]: The analyzed search results
        """
        query_embedding = convert_query_to_embedding(query)
        if not query_embedding:
            logger.error("Failed to generate embedding for query")
            return {"suggestions": []} 

        # Use simple diversity parameter
        all_results = search_similar_content(query_embedding, 2, enable_diversity)
        news_results = all_results.get("news", [])
        reddit_results = all_results.get("reddit_posts", [])

        # Use the threadPool here for parallel processing
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_news = executor.submit(self.process_news, news_results)
            future_reddit = executor.submit(self.process_reddit, reddit_results)

            news_analysis = future_news.result()
            reddit_analysis = future_reddit.result()
        
        combined_results = []

        for item in news_analysis:
            item["source_type"] = "news"
            combined_results.append(item)
    
        for item in reddit_analysis:
            item["source_type"] = "reddit"
            combined_results.append(item)

        return {"suggestions": combined_results}
    
    # Save suggestions to MongoDB
    def store_analysis(self, db_connector: MongoDBConnector, analysis: Dict[str, List[Dict[str, Any]]], 
                  query: str = None) -> Dict[str, int]:
        """
        Store the analysis results in MongoDB with deduplication logic.
        Args:
            db_connector: MongoDBConnector, the database connector
            analysis: Dict[str, List[Dict[str, Any]]], the analysis results to store
            query: str, the query that was used to generate the analysis
        Returns:
            Dict[str, int]: The number of documents stored (new vs updated)
        """
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
            # Helper function for safe string processing
            def safe_strip(value):
                return value.strip() if value and isinstance(value, str) else ""
        
            # Process each content type
            for content_key, analysis_type in content_types.items():
                new_suggestions = []
                skipped_count = 0
                
                for item in analysis.get(content_key, []):
                    topic = safe_strip(item.get("topic"))
                    url = safe_strip(item.get("url")) if item.get("url") is not None else ""
                    label = safe_strip(item.get("label"))
                
                    # Skip if missing required fields
                    if not topic:
                        logger.warning(f"Skipping suggestion with missing topic: {item}")
                        continue

                    url_for_id = url if url else f"reddit_post_{item.get('_id', 'unknown')}"
                    # Generate unique suggestion ID
                    suggestion_id = self._generate_suggestion_id(topic, url, query or "")
                    
                    # Check for exact duplicate
                    if self._check_suggestion_exists(db_connector, suggestion_id):
                        logger.debug(f"Skipping duplicate suggestion: {topic}")
                        skipped_count += 1
                        continue
                    
                    # Check for similar suggestions
                    if self._is_similar_suggestion(db_connector, topic, label, query or ""):
                        logger.debug(f"Skipping similar suggestion: {topic}")
                        skipped_count += 1
                        continue
                    
                    # Prepare document for storage
                    doc = item.copy()
                    if "source_type" in doc:
                        del doc["source_type"]
                    
                    doc.update({
                        "suggestion_id": suggestion_id,
                        "type": analysis_type,
                        "analyzed_at": timestamp,
                        "source_query": query or "",
                        "created_at": timestamp,
                        "updated_at": timestamp
                    })
                    
                    new_suggestions.append(doc)
                
                # Store only new, unique suggestions
                if new_suggestions:
                    try:
                        # Use upsert_many to handle any remaining edge cases
                        result = db_connector.upsert_many(
                            SUGGESTION_COLLECTION, 
                            new_suggestions, 
                            unique_field="suggestion_id"
                        )
                        stored_counts[content_key] = result["upserted"] + result["updated"]
                        logger.info(f"Stored {len(new_suggestions)} {content_key} analysis documents "
                                   f"(New: {result['upserted']}, Updated: {result['updated']}, Skipped: {skipped_count})")
                    except Exception as e:
                        logger.error(f"Error storing {content_key} suggestions: {e}")
                        stored_counts[content_key] = 0
                else:
                    logger.info(f"No new {content_key} suggestions to store (Skipped: {skipped_count})")
            
            return stored_counts
            
        except Exception as e:
            logger.error(f"Error storing analysis results: {e}")
            return {"news": 0, "reddit": 0}

    def analyze_and_store_search_results(self, query: str, db_connector: MongoDBConnector, label: Optional[str] = None, enable_diversity: bool = True) -> Dict[str, Any]:
        """
        Analyze search results for a query and store them in the database.
        Args:
            query: str, the query to analyze
            db_connector: MongoDBConnector, the database connector
            label: Optional[str], the label to filter the results by
        Returns:
            Dict[str, Any]: The analysis results
        """
        # Get analysis results with combined structure
        result = self.analyze_search_results(query, enable_diversity)
        
        # Split them back for storage
        suggested_results = {
            "news": [item for item in result["suggestions"] if item.get("source_type") == "news" and (not label or item.get("label") == label)],
            "reddit": [item for item in result["suggestions"] if item.get("source_type") == "reddit" and (not label or item.get("label") == label)]
        }
        
        # Store results in MongoDB with deduplication
        storage_counts = self.store_analysis(db_connector, suggested_results, query)

        # Filter results based on label
        if label:
            result["suggestions"] = [item for item in result["suggestions"] if item.get("label") == label]
        
        return {
            "analysis": result["suggestions"],  # Return combined list
            "stored": storage_counts
        }
    
# ---- Main function to run the content analyzer -----

if __name__ == "__main__":
    # Initialize the ContentAnalyzer
    analyzer = ContentAnalyzer()
    db_connector = MongoDBConnector()

    # Ensure indexes are created
    db_connector.ensure_indexes()

    # Analyze and store the search results for a query
    query = "What is trending in Spain?"
    results = analyzer.analyze_and_store_search_results(query, db_connector)

    # Display the analysis results
    print(f"Analysis complete. Stored {results['stored']['news']} news and {results['stored']['reddit']} Reddit analysis documents.")
    print(json_util.dumps(results['analysis'], indent=2))