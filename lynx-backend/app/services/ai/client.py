import logging
from typing import Optional
from openai import AsyncOpenAI

from ...core.config import settings

_client: Optional[AsyncOpenAI] = None


def get_client() -> Optional[AsyncOpenAI]:
    global _client
    if _client is None:
        key = settings.openai_api_key
        if not key:
            logging.warning("OPENAI_API_KEY is not set — AI features disabled")
            return None
        _client = AsyncOpenAI(api_key=key)
    return _client


async def ai_chat(
    messages: list[dict],
    model: Optional[str] = None,
    response_format: Optional[dict] = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> Optional[str]:
    client = get_client()
    if not client:
        return None

    try:
        kwargs = dict(
            model=model or settings.openai_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if response_format:
            kwargs["response_format"] = response_format

        resp = await client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content
    except Exception as e:
        logging.error(f"AI chat error: {e}")
        return None
