import os, asyncio, json
from typing import Dict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate

class LLMService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Missing GEMINI_API_KEY environment variable")
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",  # or gemini-1.5-pro
            temperature=0.0,
            google_api_key=api_key
        )

    async def evaluate_claim(self, claim_context: str, rules_context: str) -> Dict:
        """Evaluate a claim using Gemini and return structured results."""
        prompt = ChatPromptTemplate.from_template(
            """
You are a claims validation assistant. Evaluate the claim against these rules.
Output **valid JSON ONLY** with this schema:
{{
  "has_additional_errors": bool,
  "additional_errors": [ "string", "string" ],
  "enhanced_explanation": "string",
  "recommended_action": "string",
  "confidence_score": float
}}

RULES:
{rules_context}

CLAIM:
{claim_context}
            """
        )
        chain = prompt | self.llm
        try:
            response = await asyncio.to_thread(chain.invoke, {})
            raw = response.content.strip() if hasattr(response, "content") else str(response)

            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                # If parsing fails, wrap the raw output to avoid crashing the pipeline
                parsed = {
                    "has_additional_errors": True,
                    "additional_errors": [f"Could not parse JSON: {raw[:200]}..."],
                    "enhanced_explanation": raw,
                    "recommended_action": "Manually review claim",
                    "confidence_score": 0.0
                }
            return parsed

        except Exception as e:
            print(f"Gemini LLM error: {e}")
            return {
                "has_additional_errors": False,
                "additional_errors": [],
                "enhanced_explanation": "",
                "recommended_action": "",
                "confidence_score": 0.0
            }
