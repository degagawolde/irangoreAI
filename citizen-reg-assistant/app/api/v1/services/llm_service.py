import json
import re
import time
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
    retries: int = 3,
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
        max_output_tokens=65536,    # ← increased from 8192
        system_instruction=system_prompt or ""
    )

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            response = client.models.generate_content(
                model=settings.GEMINI_LLM_MODEL,
                contents=gemini_messages,
                config=config
            )
            return response.text
        except Exception as e:
            last_error = e
            err_str    = str(e)
            if "503" in err_str or "UNAVAILABLE" in err_str:
                wait = attempt * 5   # 5s, 10s, 15s
                print(f"[LLM-GEMINI] 503 on attempt {attempt} — retrying in {wait}s...")
                time.sleep(wait)
                continue
            raise e

    raise last_error


async def _chat_json_gemini(
    messages: list[dict],
    system_prompt: str = None,
    temperature: float = 0.1,
    retries: int = 3,
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
        max_output_tokens=65536,    # ← increased from 8192
        system_instruction=system_prompt or "",
        response_mime_type="application/json",
    )

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            response = client.models.generate_content(
                model=settings.GEMINI_LLM_MODEL,
                contents=gemini_messages,
                config=config
            )

            print(f"[LLM-GEMINI] Response: {len(response.text):,} chars "
                  f"(attempt {attempt})")

            try:
                return json.loads(response.text)
            except json.JSONDecodeError as e:
                print(f"[LLM-GEMINI] JSON parse failed: {e}")
                print(f"[LLM-GEMINI] Raw (first 500): {response.text[:500]}")

                # Try cleaning markdown fences
                clean = re.sub(r"```json|```", "", response.text).strip()
                try:
                    return json.loads(clean)
                except json.JSONDecodeError:
                    # Try extracting JSON block
                    match = re.search(r'\{.*\}', clean, re.DOTALL)
                    if match:
                        try:
                            return json.loads(match.group())
                        except json.JSONDecodeError:
                            pass

                    # If still failing — likely truncated, retry
                    if attempt < retries:
                        print(f"[LLM-GEMINI] JSON truncated — retrying "
                              f"with shorter prompt (attempt {attempt + 1})")
                        last_error = ValueError(
                            f"JSON truncated at {len(response.text)} chars"
                        )
                        continue

                    raise ValueError(
                        f"Gemini returned invalid JSON after {retries} attempts. "
                        f"Response: {response.text[:300]}"
                    )

        except Exception as e:
            last_error = e
            err_str    = str(e)
            if "503" in err_str or "UNAVAILABLE" in err_str:
                wait = attempt * 5
                print(f"[LLM-GEMINI] 503 on attempt {attempt} — retrying in {wait}s...")
                time.sleep(wait)
                continue
            if "JSON" not in err_str:
                raise e

    raise last_error


async def _chat_ollama(
    messages: list[dict],
    system_prompt: str = None,
    temperature: float = 0.1,
) -> str:
    payload = {
        "model":    settings.OLLAMA_LLM_MODEL,
        "messages": messages,
        "stream":   False,
        "options":  {
            "temperature": temperature,
            "num_ctx":     8192,
        }
    }
    if system_prompt:
        payload["messages"] = [
            {"role": "system", "content": system_prompt},
            *messages
        ]

    async with httpx.AsyncClient(timeout=300.0) as client:
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
        "model":    settings.OLLAMA_LLM_MODEL,
        "messages": messages,
        "stream":   False,
        "format":   "json",
        "options":  {
            "temperature": temperature,
            "num_ctx":     8192,
        }
    }
    if system_prompt:
        payload["messages"] = [
            {"role": "system", "content": system_prompt},
            *messages
        ]

    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json=payload
        )
        response.raise_for_status()
        content = response.json()["message"]["content"]

    print(f"[LLM-OLLAMA] Response: {len(content):,} chars")
    print(f"[LLM-OLLAMA] First 300: {content[:300]}")

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"[LLM-OLLAMA] JSON parse failed: {e}")
        print(f"[LLM-OLLAMA] Full response: {content[:1000]}")
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        clean = re.sub(r"```json|```", "", content).strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            raise ValueError(
                f"Ollama returned invalid JSON.\n"
                f"Response: {content[:500]}"
            )


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
    """Detect language with retry on 503."""
    messages = [
        {
            "role": "user",
            "content": (
                "Detect the language of this text. "
                "Return only the language name in English. "
                "Examples: 'English', 'Amharic', 'Oromiffa', 'Tigrinya', 'Somali'. "
                f"Nothing else.\n\n{text[:500]}"
            )
        }
    ]
    lang = await chat(messages=messages, temperature=0.0)
    return lang.strip()