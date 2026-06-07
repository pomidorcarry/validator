import logging
from pathlib import Path

logger = logging.getLogger(__name__)


async def generate_xkt(model_version_id: str) -> bool:
    logger.info(f"XKT generation skipped (client-side parsing)")
    return True