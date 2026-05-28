from fastapi import APIRouter

router = APIRouter(tags=["ai"])


@router.get("/ai/status")
async def ai_status(check: bool = False):
    from ...core.config import settings as _cfg

    configured = bool(_cfg.openai_api_key)
    result = {"configured": configured, "responsive": None, "error_detail": None}

    if configured and check:
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=_cfg.openai_api_key)
            await client.models.list()
            result["responsive"] = True
        except openai.PermissionDeniedError as e:
            result["responsive"] = False
            result["error_detail"] = "Регион не поддерживается (403)"
        except openai.AuthenticationError as e:
            result["responsive"] = False
            result["error_detail"] = "Неверный API-ключ"
        except Exception as e:
            result["responsive"] = False
            result["error_detail"] = str(e)[:200]

    return result
