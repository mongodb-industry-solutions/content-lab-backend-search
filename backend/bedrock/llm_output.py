# ---- llm_output.py ----

# Process news and Reddit snippets using Claude Model from bedrock to extract structured insights.

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

    # -------- Prompt Formatting Methods --------

    def _format_news_prompt(self, snippets: List[str], ids: List[str], urls: List[str]) -> str:
        """Prompt template with few-shot example for news articles."""
        
        # Clear system context
        
        header = (
            "You are a precise news analyst trained to extract structured information. "
            "I need you to analyze, understand the news articles contexually and extract specific fields in a consistent JSON format."
        )
        
        # A few-shot example
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
            "]\n\n"
            "NOW ANALYZE THESE ARTICLES:"
        )
        
        # Format the articles to analyze
        items = []
        for idx, (_, snippet, url) in enumerate(zip(ids, snippets, urls), 1):
            items.append(f"{idx}. {snippet}\nurl: {url}")
        
        body = "\n\n".join(items)
        
        # Detailed instructions
        task = (
            "\n\nFor each article above, create a JSON object with these fields:\n"
            "1. \"topic\": A precise 3-5 word headline capturing the core subject\n"
            "2. \"keywords\": An array of EXACTLY 4 specific, relevant terms (avoid generic words like 'technology' or 'health')\n"
            "3. \"description\": One clear, information-dense sentence summarizing the key insight and indicating why the user should write about this topic (aim for 15-20 words)\n"
            "4. \"label\": EXACTLY one of [\"technology\", \"business\", \"health\", \"culture\", \"sports\"] - choose the MOST specific match\n"
            "5. \"url\": The source URL\n\n"
            
            "FORMAT REQUIREMENTS:\n"
            "- Return a JSON array of objects with structure exactly like the example\n"
            "- Use double quotes for all keys and string values\n"
            "- **IMPORTANT: If a string value contains double quotes, they MUST be escaped with a backslash (e.g., \"some \\\"quoted\\\" text\").**\n"
            "- Include NO explanatory text outside the JSON array\n"
            "- Ensure proper JSON formatting with correct commas and brackets\n"
        )
        
        return f"{header}\n\n{example}\n\n{body}{task}"

    def _format_reddit_prompt(self, snippets: List[str], ids: List[str], urls: List[Optional[str]]) -> str:
        """The prompt template with few-shot example for Reddit posts."""
        
        # Start with a clear system context
        header = (
            "You are a community insights analyst specializing in Reddit discourse analysis. "
            "Your expertise lies in identifying collective sentiment patterns, recognizing consensus vs. disagreement, "
            "and extracting key perspectives from online communities. "
            "Reddit discussions often contain diverse viewpoints, emotional undertones, and specialized terminology. "
            "Your task is to analyze these posts with nuance, capturing both explicit statements and implicit community values. "
            "Focus on what makes each discussion unique - the specific concerns, terminology, and sentiment that "
            "characterize this particular community's approach to the topic. "
            "Extract structured information that preserves the authentic voice of the community while "
            "organizing it into consistent, comparable data fields."
        )
        
        # Add a few-shot example

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
            "]\n\n"
            "NOW ANALYZE THESE REDDIT POSTS:"
        )
        
        # Format the posts to analyze
        items = []
        for idx, (_, snippet, url) in enumerate(zip(ids, snippets, urls), 1):
            url_line = f"url: {url}" if url else "url: null"
            items.append(f"{idx}. {snippet}\n{url_line}")
        
        body = "\n\n".join(items)
        
        # Detailed instructions
        task = (
            "\n\nFor each Reddit post above, create a JSON object with these fields:\n"
            "1. \"topic\": A precise 3-5 word phrase capturing the community's focus\n"
            "2. \"keywords\": An array of EXACTLY 4 terms reflecting community perspectives (be specific, avoid generic terms)\n"
            "3. \"description\": One sentence capturing the primary community sentiment, opinion, or concern and indicating why the user should write about this topic  \n"
            "4. \"label\": EXACTLY one of [\"technology\", \"business\", \"health\", \"culture\", \"sports\"] - choose the MOST specific match\n"
            "5. \"url\": The source URL or null if unavailable\n\n"
            
            "FORMAT REQUIREMENTS:\n"
            "- Return a JSON array of objects with structure exactly like the example\n"
            "- Use double quotes for all keys and string values\n"
            "- **IMPORTANT: If a string value contains double quotes, they MUST be escaped with a backslash (e.g., \"some \\\"quoted\\\" text\").**\n"
            "- Include NO explanatory text outside the JSON array\n"
            "- Ensure proper JSON formatting with correct commas and brackets\n"
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
        query_embedding = convert_query_to_embedding(query)
        if not query_embedding:
            logger.error("Failed to generate embedding for query")
            return {"news": [], "reddit": []}

        all_results = search_similar_content(query_embedding, 3)
        news_results = all_results.get("news", [])
        reddit_results = all_results.get("reddit_posts", [])

        return {
            "news": self.process_news(news_results),
            "reddit": self.process_reddit(reddit_results)
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
            # Process and store news analysis
            news_docs = []
            for item in analysis.get("news", []):
                doc = item.copy()
                doc["type"] = "news_analysis"
                doc["analyzed_at"] = timestamp
                if query:
                    doc["source_query"] = query
                news_docs.append(doc)
            
            if news_docs:
                result = db_connector.insert_many(SUGGESTION_COLLECTION, news_docs)
                stored_counts["news"] = len(result)
                logger.info(f"Stored {len(news_docs)} news analysis documents")
            
            # Process and store reddit analysis
            reddit_docs = []
            for item in analysis.get("reddit", []):
                doc = item.copy()
                doc["type"] = "reddit_analysis"
                doc["analyzed_at"] = timestamp
                if query:
                    doc["source_query"] = query
                reddit_docs.append(doc)
            
            if reddit_docs:
                result = db_connector.insert_many(SUGGESTION_COLLECTION, reddit_docs)
                stored_counts["reddit"] = len(result)
                logger.info(f"Stored {len(reddit_docs)} Reddit analysis documents")
            
            return stored_counts
        
        except Exception as e:
            logger.error(f"Error storing analysis results: {e}")
            return {"news": 0, "reddit": 0}


    def analyze_and_store_search_results(self, query: str, db_connector: MongoDBConnector) -> Dict[str, Any]:
        """
        Analyze search results for a query and store them in the database.
        """
        # Get analysis results
        suggested_results = self.analyze_search_results(query)
        
        # Store results in MongoDB
        storage_counts = self.store_analysis(db_connector, suggested_results, query)
        
        return {
            "analysis": suggested_results,
            "stored": storage_counts
        }


if __name__ == "__main__":
    analyzer = ContentAnalyzer()
    db_connector = MongoDBConnector()

    query = "What is the trending news in Europe?"
    # Use analyze_and_store_search_results instead of analyze_search_results
    results = analyzer.analyze_and_store_search_results(query, db_connector)

    print(f"Analysis complete. Stored {results['stored']['news']} news and {results['stored']['reddit']} Reddit analysis documents.")
    print(json_util.dumps(results['analysis'], indent=2))