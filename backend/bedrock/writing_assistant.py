# writing_assistant.py

# This file has a Writing Assistant class that helps with 
# a. refining
# b. structuring and outlining
# c. proofreading content 
# based on personalized writing styles.

import json 
import logging
from typing import Dict, Any, Optional
from .anthropic_chat_completions import BedrockAnthropicChatCompletions
from db.mdb import MongoDBConnector
import os
from dotenv import load_dotenv

# Logging 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

USER_PROFILES_COLLECTION = os.getenv("USER_PROFILES_COLLECTION", "userProfiles")
SUGGESTIONS_COLLECTION = os.getenv("SUGGESTION_COLLECTION", "suggestions")

class WritingAssistant:

    """ 
    Writing Assistant that helps with refining, structuring, 
    outlining and proofreading content based on personalized writing styles.
    """

    def __init__(self):
        self.llm = BedrockAnthropicChatCompletions(
            model_id="anthropic.claude-3-5-haiku-20241022-v1:0"
        )
        self.db = MongoDBConnector()

    def _get_style_profile(self, style_id: str) -> Optional[Dict[str, Any]]: 
        """
        Retrieve the writing style profile from the database.
        """
        profiles_collection = self.db.get_collection("userProfiles")
        profile = profiles_collection.find_one({"_id": style_id})
        return profile
    
    def _get_topic_details(self, topic_id: str) -> Optional[Dict[str, Any]]: 
        """
        Retrieve the topic details from the database. 
        """
        suggestions_collection = self.db.get_collection(SUGGESTIONS_COLLECTION)
        topic = suggestions_collection.find_one({"_id" : topic_id})
        return topic
    
    def refine_document(self, content: str, style_id: str, topic_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Refine the document content based on the user's writing style and topic.
        """
        # Get style profiles
        profile = self._get_style_profile(style_id)
        if not profile:
            return {"error": "Style profile not found."}
        
        # Get optional topic details
        topic_info = ""
        if topic_id:
            topic = self._get_topic_details(topic_id)
            if topic:
                topic_info = f"Topic: {topic.get('topic', '')}\n"
                if topic.get('description'):
                    topic_info += f"Topic Description: {topic.get('description')}\n"
        

        # 1. Prompt for Refinement
        prompt = f"""
        You are a writing assistant helping to refine a document. Please adapt the following content to match this writing style:

        WRITING STYLE:
        Persona: {profile.get('persona', '')}
        Tone: {profile.get('tone', '')}
        Style Example: {profile.get('sampleText', '')}

        {topic_info}

        ORIGINAL CONTENT:
        {content}

        Please provide:
        1. A refined version of the content that matches the specified style and tone
        2. A list of specific changes made to align with the style
        3. Suggestions for further improvements
        
        Format your response as JSON with these fields:
        - "refined_content": the rewritten text
        - "style_changes": array of specific changes made
        - "improvement_suggestions": array of suggestions for further enhancement.

        """

        try:
            response = self.llm.predict(prompt)
            try:
                result = json.loads(response)
                return result
            except json.JSONDecodeError:
                logger.error("Could not parse structured response from LLM")
                return {
                    "refined_content": response,
                    "style_changes": [],
                    "improvement_suggestions": [],
                    "parsing_error": "Could not parse structured response"
                }
        except Exception as e:
            logger.error(f"Error refining document: {e}")
            return {"error": str(e)}
    
    def create_outline(self, topic_id: str, style_id: str, brief: Optional[str] = None) -> Dict[str, Any]:
        """ 
        Create a document outline based on a topic and writing style. 
        """
        # Get style profile and topic details
        profile = self._get_style_profile(style_id)
        topic = self._get_topic_details(topic_id)
        
        if not profile:
            return {"error": "Writing style not found"}
        if not topic:
            return {"error": "Topic not found"}
            
        brief_info = f"Additional Context: {brief}\n" if brief else ""

        # Create the prompt for outline creation
        prompt = f"""
        You are a writing assistant creating an outline for a document. Use this information:
        
        TOPIC:
        Title: {topic.get('topic', '')}
        Description: {topic.get('description', '')}
        Keywords: {', '.join(topic.get('keywords', []))}
        
        WRITING STYLE:
        Persona: {profile.get('persona', '')}
        Tone: {profile.get('tone', '')}
        Style Example: {profile.get('sampleText', '')}
        
        {brief_info}
        
        Create a comprehensive document outline that follows the specified writing style. Include:
        1. A compelling title suggestion
        2. An introduction section with key points
        3. 3-5 main sections with subsections
        4. A conclusion section with key takeaways
        5. Style notes for each section
        
        Format your response as JSON with these fields:
        - "title_suggestion": proposed document title
        - "introduction": object with "key_points" array and "style_notes" string
        - "main_sections": array of sections, each with "title", "subsections" array, and "style_notes"
        - "conclusion": object with "key_takeaways" array and "style_notes" string
        - "overall_style_guidance": general writing advice for this topic and style
        """
        
        try:
            response = self.llm.predict(prompt)
            try:
                result = json.loads(response)
                return result
            except json.JSONDecodeError:
                logger.error("Failed to parse LLM response as JSON")
                return {
                    "error": "Failed to generate structured outline",
                    "raw_response": response[:500] + "..." if len(response) > 500 else response
                }
        except Exception as e:
            logger.error(f"Error creating outline: {e}")
            return {"error": str(e)}
    
    def proofread(self, content: str, style_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Proofread content and suggest improvements
        """
        # Get optional style profile
        style_info = ""
        if style_id:
            profile = self._get_style_profile(style_id)
            if profile:
                style_info = f"""
                WRITING STYLE:
                Persona: {profile.get('persona', '')}
                Tone: {profile.get('tone', '')}
                Style Example: {profile.get('sampleText', '')}
                
                Please ensure corrections maintain this style.
                """
        
        # Proofreading prompt

        prompt = f"""
        You are a professional editor proofreading a document. Review this content for:
        1. Grammar and spelling errors
        2. Clarity and readability issues
        3. Style consistency
        4. Word choice and phrasing improvements
        
        {style_info}
        
        CONTENT TO PROOFREAD:
        {content}
        
        Format your response as JSON with these fields:
        - "corrected_text": the content with all errors fixed
        - "corrections": array of objects, each with "original", "correction", and "explanation"
        - "style_suggestions": array of suggestions to improve the writing style
        - "overall_assessment": brief evaluation of the writing quality
        """
        
        try:
            response = self.llm.predict(prompt)
            try:
                result = json.loads(response)
                return result
            except json.JSONDecodeError:
                logger.error("Failed to parse LLM response as JSON")
                return {
                    "corrected_text": content,  # Return original if parsing fails
                    "corrections": [],
                    "style_suggestions": [],
                    "overall_assessment": "Unable to process proofreading request.",
                    "parsing_error": "Could not parse structured response"
                }
        except Exception as e:
            logger.error(f"Error proofreading document: {e}")
            return {"error": str(e)}


        
