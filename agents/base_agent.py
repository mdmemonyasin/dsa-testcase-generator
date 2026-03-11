import os
import re
import time
from typing import Optional

import anthropic

MODEL = "claude-sonnet-4-6"
RETRY_MODEL = "claude-opus-4-6"
MAX_RETRIES = 2

_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY not set. Add it to your .env file or environment."
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


class BaseAgent:
    def call_model(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = MODEL,
        max_output_tokens: int = 8192,
    ) -> str:
        """Calls Anthropic API via streaming, returns full response text. Retries on transient errors."""
        client = _get_client()
        for attempt in range(MAX_RETRIES):
            try:
                with client.messages.stream(
                    model=model,
                    max_tokens=max_output_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                ) as stream:
                    final = stream.get_final_message()

                text = next(
                    (b.text for b in final.content if b.type == "text"), None
                )
                if text is None:
                    raise ValueError(
                        f"Model returned no text content "
                        f"(stop_reason={final.stop_reason})"
                    )
                return text

            except anthropic.RateLimitError as e:
                if attempt < MAX_RETRIES - 1:
                    wait = int(e.response.headers.get("retry-after", "10"))
                    print(f"[BaseAgent] Rate limited. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    raise
            except anthropic.APIStatusError as e:
                if e.status_code >= 500 and attempt < MAX_RETRIES - 1:
                    print(f"[BaseAgent] Server error {e.status_code}. Retrying in 5s...")
                    time.sleep(5)
                else:
                    raise
            except anthropic.APIConnectionError:
                if attempt < MAX_RETRIES - 1:
                    print("[BaseAgent] Connection error. Retrying in 5s...")
                    time.sleep(5)
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
