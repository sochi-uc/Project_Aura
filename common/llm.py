import os
import asyncio
import logging
import random
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AuraLLM")

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    logger.error("GEMINI_API_KEY not found in environment!")

client = genai.Client(api_key=api_key)

async def call_gemini(prompt: str, system_instruction: str = None, max_tokens: int = 4096, temperature: float = 0.2, is_json: bool = False) -> str:
    model = "gemini-3.6-flash"
    
    config_args = {
        "temperature": temperature,
        "max_output_tokens": max_tokens,
    }
    
    if system_instruction:
        config_args["system_instruction"] = system_instruction
        
    if is_json:
        config_args["response_mime_type"] = "application/json"
        
    config = types.GenerateContentConfig(**config_args)

    for attempt in range(5):
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=model,
                contents=prompt,
                config=config
            )
            try:
                finish_reason = response.candidates[0].finish_reason
                logger.info(f"Gemini finish_reason: {finish_reason}")
            except:
                pass
            return response.text
            
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "quota" in err_str or "503" in err_str:
                wait_time = (2 ** attempt) + random.uniform(1, 3)
                logger.warning(f"Gemini API rate limit/overload. Retrying in {wait_time:.2f}s... (Attempt {attempt+1}/5)")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Fatal Gemini Error: {e}")
                raise e
                
    raise Exception("Failed to get response from Gemini after 5 attempts.")
