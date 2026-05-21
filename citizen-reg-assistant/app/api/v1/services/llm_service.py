import json
import re
from google import genai
from google.genai import types
from app.core.config import settings

_client = None


def get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


async def chat(
    messages: list[dict],
    system_prompt: str = None,
    temperature: float = 0.1,
) -> str:
    """
    Send a chat request to Gemini.
    messages: [{"role": "user"|"assistant", "content": "..."}]
    """
    client = get_client()

    # Convert to Gemini format
    gemini_messages = []
    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        gemini_messages.append(
            types.Content(
                role=role,
                parts=[types.Part(text=msg["content"])]
            )
        )

    config = types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=4096,
        system_instruction=system_prompt or ""
    )

    response = client.models.generate_content(
        model=settings.GEMINI_LLM_MODEL,
        contents=gemini_messages,
        config=config
    )
    return response.text


async def chat_json(
    messages: list[dict],
    system_prompt: str = None,
    temperature: float = 0.1,
) -> dict:
    """
    Same as chat() but forces JSON output.
    Used for document risk analysis.
    """
    client = get_client()

    gemini_messages = []
    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        gemini_messages.append(
            types.Content(
                role=role,
                parts=[types.Part(text=msg["content"])]
            )
        )

    config = types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=4096,
        system_instruction=system_prompt or "",
        response_mime_type="application/json",
    )

    response = client.models.generate_content(
        model=settings.GEMINI_LLM_MODEL,
        contents=gemini_messages,
        config=config
    )

    try:
        return json.loads(response.text)
    except json.JSONDecodeError:
        clean = re.sub(r"```json|```", "", response.text).strip()
        return json.loads(clean)


async def detect_language(text: str) -> str:
    """
    Detect the language of uploaded contract or user query.
    Returns: 'English', 'Amharic', 'Oromiffa', 'Tigrinya', etc.
    """
    messages = [
        {
            "role": "user",
            "content": (
                "Detect the language of this text. "
                "Return only the language name in English "
                "(e.g. 'English', 'Amharic', 'Oromiffa', 'Tigrinya', 'Somali'). "
                f"Nothing else.\n\n{text[:500]}"
            )
        }
    ]
    lang = await chat(messages=messages, temperature=0.0)
    return lang.strip()