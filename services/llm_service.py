# import os, asyncio, json
# from typing import Dict
# from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain.prompts import ChatPromptTemplate

# class LLMService:
#     def __init__(self):
#         api_key = os.getenv("GEMINI_API_KEY")
#         if not api_key:
#             raise ValueError("Missing GEMINI_API_KEY environment variable")
#         self.llm = ChatGoogleGenerativeAI(
#             model="gemini-1.5-flash",  # or gemini-1.5-pro
#             temperature=0.0,
#             google_api_key=api_key
#         )

#     async def evaluate_claim(self, claim_context: str, rules_context: str) -> Dict:
#         """Evaluate a claim using Gemini and return structured results."""
#         prompt = ChatPromptTemplate.from_template(
#             """
# You are a claims validation assistant. Evaluate the claim against these rules.
# Output **valid JSON ONLY** with this schema:
# {{
#   "has_additional_errors": bool,
#   "additional_errors": [ "string", "string" ],
#   "enhanced_explanation": "string",
#   "recommended_action": "string",
#   "confidence_score": float
# }}

# RULES:
# {rules_context}

# CLAIM:
# {claim_context}
#             """
#         )
#         chain = prompt | self.llm
#         try:
#             response = await asyncio.to_thread(chain.invoke, {})
#             raw = response.content.strip() if hasattr(response, "content") else str(response)

#             try:
#                 parsed = json.loads(raw)
#             except json.JSONDecodeError:
#                 # If parsing fails, wrap the raw output to avoid crashing the pipeline
#                 parsed = {
#                     "has_additional_errors": True,
#                     "additional_errors": [f"Could not parse JSON: {raw[:200]}..."],
#                     "enhanced_explanation": raw,
#                     "recommended_action": "Manually review claim",
#                     "confidence_score": 0.0
#                 }
#             return parsed

#         except Exception as e:
#             print(f"Gemini LLM error: {e}")
#             return {
#                 "has_additional_errors": False,
#                 "additional_errors": [],
#                 "enhanced_explanation": "",
#                 "recommended_action": "",
#                 "confidence_score": 0.0
#             }



# services/llm_service.py - REPLACE ENTIRE FILE

import os
import asyncio
import json
import re
from typing import Dict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate

class LLMService:
    def __init__(self, max_retries: int = 2):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Missing GEMINI_API_KEY environment variable")
        
        self.max_retries = max_retries
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.0,
            google_api_key=api_key
        )
        print("✅ LLM Service initialized with Gemini")

    async def evaluate_claim(self, claim_context: str, rules_context: str) -> Dict:
        """Evaluate a claim using Gemini with retry logic and better JSON parsing."""
        
        prompt = ChatPromptTemplate.from_template(
            """
You are a claims validation assistant. Evaluate the claim against these rules.
Output **ONLY valid JSON** with this exact schema (no markdown, no explanations):
{{
  "has_additional_errors": true/false,
  "additional_errors": ["error1", "error2"],
  "enhanced_explanation": "brief explanation",
  "recommended_action": "actionable recommendation",
  "confidence_score": 0.0-1.0
}}

RULES:
{rules_context}

CLAIM:
{claim_context}

JSON OUTPUT:
            """
        )
        
        chain = prompt | self.llm
        
        # Retry logic
        for attempt in range(self.max_retries):
            try:
                response = await asyncio.to_thread(
                    chain.invoke, 
                    {
                        "rules_context": rules_context,
                        "claim_context": claim_context
                    }
                )
                
                raw = response.content.strip() if hasattr(response, "content") else str(response)
                
                # Try to extract JSON from response (handle markdown code blocks)
                parsed = self._extract_and_parse_json(raw)
                
                # Validate required fields
                if self._validate_response(parsed):
                    return parsed
                else:
                    print(f"⚠️ Invalid response structure on attempt {attempt + 1}")
                    if attempt == self.max_retries - 1:
                        return self._default_response()
                    
            except Exception as e:
                print(f"⚠️ LLM error on attempt {attempt + 1}: {e}")
                if attempt == self.max_retries - 1:
                    return self._default_response()
                await asyncio.sleep(1)  # Wait before retry
        
        return self._default_response()
    
    def _extract_and_parse_json(self, raw: str) -> Dict:
        """Extract and parse JSON from various formats"""
        try:
            # Try direct parsing first
            return json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            
            # Try to find JSON object in text
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
            
            # If all fails, return error response
            return {
                "has_additional_errors": True,
                "additional_errors": [f"Could not parse LLM response"],
                "enhanced_explanation": raw[:500],
                "recommended_action": "Manual review required",
                "confidence_score": 0.0
            }
    
    def _validate_response(self, response: Dict) -> bool:
        """Validate that response has required fields with correct types"""
        required_fields = {
            "has_additional_errors": bool,
            "additional_errors": list,
            "enhanced_explanation": str,
            "recommended_action": str,
            "confidence_score": (int, float)
        }
        
        for field, expected_type in required_fields.items():
            if field not in response:
                return False
            if not isinstance(response[field], expected_type):
                return False
        
        return True
    
    def _default_response(self) -> Dict:
        """Return default response when LLM fails"""
        return {
            "has_additional_errors": False,
            "additional_errors": [],
            "enhanced_explanation": "",
            "recommended_action": "",
            "confidence_score": 0.0
        }