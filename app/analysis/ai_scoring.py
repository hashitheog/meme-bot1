import json
import asyncio
from typing import Dict, Any, Optional
from app.config import settings
from app.utils.logging_config import logger

# Conditional imports to avoid hard crashes if packages missing
try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

try:
    from google import genai
except ImportError:
    genai = None

class AIScoringEngine:
    """
    Analyzes token metadata and social signals using LLM (OpenAI or Gemini) to detect scams and rate quality.
    """
    def __init__(self):
        self.provider = settings.AI_PROVIDER.lower()
        self.openai_client = None
        self.gemini_client = None

        if self.provider == "openai" and settings.OPENAI_API_KEY:
             if AsyncOpenAI:
                self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        elif self.provider == "deepseek" and settings.DEEPSEEK_API_KEY:
            if AsyncOpenAI:
                self.openai_client = AsyncOpenAI(
                    api_key=settings.DEEPSEEK_API_KEY, 
                    base_url="https://api.deepseek.com"
                )
            else:
                logger.error("openai package not installed (required for deepseek).")

        elif self.provider == "gemini" and settings.GEMINI_API_KEY:
            if genai:
                self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
            else:
                logger.error("google-genai package not installed.")

    async def analyze_token(self, token_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sends sanitized token data to LLM and expects structured JSON response.
        """
        if (self.provider == "openai" or self.provider == "deepseek") and not self.openai_client:
             logger.warning(f"{self.provider.capitalize()} Client missing. Skipping AI analysis.")
             return self._fallback_result(f"NO_{self.provider.upper()}_KEY")
        
        if self.provider == "gemini" and not self.gemini_client:
             logger.warning("Gemini Client missing. Skipping AI analysis.")
             return self._fallback_result("NO_GEMINI_KEY")

        prompt = f"""
        You are a crypto risk analyst. Analyze this meme coin for rug pull risks and viral potential.
        
        DATA:
        {json.dumps(token_data, indent=2)}
        
        TASK:
        Return a valid JSON object strictly following this schema:
        {{
          "ai_risk_score": <0-100 integer, where 0=Safe/Good, 100=Scam/Bad>,
          "ai_confidence": <0-1 float>,
          "risk_flags": ["<short_string>", ...],
          "positive_signals": ["<short_string>", ...],
          "summary": "<max 3 lines>",
          "verdict": "<PASS|CAUTION|FAIL>"
        }}
        
        CRITERIA:
        - High Risk (60-100): Fake team, botted social, copy-paste website, no unique art.
        - Low Risk (0-30): High effort, organic community, original art.
        - Medium (31-59): Unknowns or mixed signals.
        """

        try:
            if self.provider == "openai" or self.provider == "deepseek":
                response = await self.openai_client.chat.completions.create(
                    model=settings.AI_MODEL,
                    messages=[
                        {"role": "system", "content": "You are a JSON-only API. Output ONLY raw JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    response_format={ "type": "json_object" } 
                )
                content = response.choices[0].message.content
                
            elif self.provider == "gemini":
                # Using the new SDK's async generation
                # Note: google-genai SDK uses 'models.generate_content'
                # To enforce JSON, newer models support config, but prompting is still robust.
                response = await self.gemini_client.aio.models.generate_content(
                    model=settings.AI_MODEL,
                    contents=f"Output strictly VALID JSON. {prompt}",
                    config={"response_mime_type": "application/json"}
                )
                content = response.text
            
            # Cleaning content if markdown is present (common with Gemini)
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
            
            result = json.loads(content)
            
            # Simple validation
            if "ai_risk_score" not in result:
                raise ValueError("Missing 'ai_risk_score'")
                
            return result
            
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                logger.warning(f"AI Quota Exceeded. Waiting 30s to retry... ({token_data.get('symbol')})")
                await asyncio.sleep(30)
                # Retry recursively (simple) or just fail if deep
                # For safety, let's just retry ONCE or TWICE here by calling self.analyze_token again?
                # Better: Use a simple loop structure outside the try/except if possible, or just one retry.
                # Let's try a recursive call with a decreased counter? 
                # Actually, simpler: just return self.analyze_token(token_data) 
                # But infinite recursion risk.
                # Let's just return a fallback for now with a note, OR since user demanded it:
                # We will just retry continuously in the wrapper or here?
                # Let's fail loudly if user wants, but better to retry.
                
                # RE-ATTEMPT 1
                try:
                    logger.info(f"Retrying AI for {token_data.get('symbol')}...")
                    if self.provider == "gemini":
                         response = await self.gemini_client.aio.models.generate_content(
                            model=settings.AI_MODEL,
                            contents=f"Output strictly VALID JSON. {prompt}",
                            config={"response_mime_type": "application/json"}
                        )
                         content = response.text
                         # ... parse ...
                         if content.startswith("```json"):
                             content = content.replace("```json", "").replace("```", "").strip()
                         elif content.startswith("```"):
                             content = content.replace("```", "").strip()
                         return json.loads(content)
                except Exception as retry_e:
                     logger.error(f"Retry failed too: {retry_e}")
                     return self._fallback_result("AI_QUOTA_LIMIT_RETRY_FAIL")

            logger.error(f"AI Analysis Failed ({self.provider})", error=err_str)
            return self._fallback_result("AI_ERROR")

    def _fallback_result(self, reason: str) -> Dict[str, Any]:
        return {
            "ai_risk_score": 50,
            "ai_confidence": 0,
            "risk_flags": [reason],
            "positive_signals": [],
            "summary": f"AI analysis skipped: {reason}",
            "verdict": "CAUTION"
        }

ai_engine = AIScoringEngine()
