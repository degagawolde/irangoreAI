import json
import re
import httpx
from google import genai
from google.genai import types
from app.core.config import settings

_gemini_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _gemini_client


async def _chat_gemini(
    messages: list[dict],
    system_prompt: str = None,
    temperature: float = 0.1,
) -> str:
    client = _get_gemini_client()
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


async def _chat_json_gemini(
    messages: list[dict],
    system_prompt: str = None,
    temperature: float = 0.1,
) -> dict:
    client = _get_gemini_client()
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


async def _chat_ollama(
    messages: list[dict],
    system_prompt: str = None,
    temperature: float = 0.1,
) -> str:
    payload = {
        "model":   settings.OLLAMA_LLM_MODEL,
        "messages": messages,
        "stream":  False,
        "options": {"temperature": temperature}
    }
    if system_prompt:
        payload["messages"] = [
            {"role": "system", "content": system_prompt},
            *messages
        ]
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json=payload
        )
        response.raise_for_status()
        return response.json()["message"]["content"]


async def _chat_json_ollama(
    messages: list[dict],
    system_prompt: str = None,
    temperature: float = 0.1,
) -> dict:
    payload = {
        "model":   settings.OLLAMA_LLM_MODEL,
        "messages": messages,
        "stream":  False,
        "format":  "json",
        "options": {"temperature": temperature}
    }
    if system_prompt:
        payload["messages"] = [
            {"role": "system", "content": system_prompt},
            *messages
        ]
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json=payload
        )
        response.raise_for_status()
        content = response.json()["message"]["content"]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"Model did not return valid JSON: {content[:200]}")


# ── Public API ────────────────────────────────────────────────────────────────

async def chat(
    messages: list[dict],
    system_prompt: str = None,
    temperature: float = 0.1,
) -> str:
    if settings.LLM_PROVIDER == "gemini":
        return await _chat_gemini(messages, system_prompt, temperature)
    return await _chat_ollama(messages, system_prompt, temperature)


async def chat_json(
    messages: list[dict],
    system_prompt: str = None,
    temperature: float = 0.1,
) -> dict:
    if settings.LLM_PROVIDER == "gemini":
        return await _chat_json_gemini(messages, system_prompt, temperature)
    return await _chat_json_ollama(messages, system_prompt, temperature)


async def detect_language(text: str) -> str:
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