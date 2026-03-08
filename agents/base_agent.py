import os
import re
import time
from typing import Optional

from google import genai
from google.genai import types

MODEL = "gemini-2.0-flash"
RETRY_MODEL = "gemini-2.5-pro"
MAX_RETRIES = 2

_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY not set. Add it to your .env file or environment."
            )
        _client = genai.Client(api_key=api_key)
    return _client


class BaseAgent:
    def call_model(self, system_prompt: str, user_prompt: str, model: str = MODEL, max_output_tokens: int = 8192) -> str:
        """Calls Gemini API, returns response text. Retries on transient errors."""
        client = _get_client()
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
            max_output_tokens=max_output_tokens,
        )
        for attempt in range(MAX_RETRIES):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=user_prompt,
                    config=config,
                )
                if response.text is None:
                    raise ValueError(
                        f"Model returned empty response (finish_reason="
                        f"{response.candidates[0].finish_reason if response.candidates else 'unknown'})"
                    )
                return response.text
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    print(f"[BaseAgent] Error: {e}. Retrying in 3s...")
                    time.sleep(3)
                else:
                    raise

    def extract_code_block(self, response: str, language: str) -> str:
        """
        Extracts first ```<language> ... ``` block.
        Falls back to any fenced block. Raises ValueError if nothing found.
        """
        pattern = rf"```{language}\s*(.*?)```"
        match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        match = re.search(r"```\s*(.*?)```", response, re.DOTALL)
        if match:
            return match.group(1).strip()
        raise ValueError(
            f"No {language} code block found in model response.\n"
            f"Response preview: {response[:400]}"
        )
