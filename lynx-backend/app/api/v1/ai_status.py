from fastapi import APIRouter

router = APIRouter(tags=["ai"])


@router.get("/ai/status")
async def ai_status(check: bool = False):
    from ...core.config import settings as _cfg

    configured = bool(_cfg.openai_api_key)
    result = {"configured": configured, "responsive": None, "error_detail": None}

    if configured and check:
        try:
            from ...services.ai.client import ai_chat
            resp = await ai_chat(
                [{"role": "user", "content": "echo OK"}],
                temperature=0, max_tokens=5,
            )
            result["responsive"] = resp is not None and "OK" in resp
            if not result["responsive"]:
                result["error_detail"] = "AI ответил неожиданно"
        except Exception as e:
            result["responsive"] = False
            result["error_detail"] = str(e)[:200]

    return result
