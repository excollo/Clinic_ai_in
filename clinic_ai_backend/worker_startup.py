"""Worker startup module."""
from __future__ import annotations

import asyncio
import logging

from src.workers.transcription_worker import start_background_workers, stop_background_workers

logger = logging.getLogger(__name__)


async def _main() -> None:
    logging.basicConfig(level=logging.INFO)
    start_background_workers()
    logger.info("Transcription worker service started")
    try:
        while True:
            await asyncio.sleep(1)
    finally:
        await stop_background_workers()
        logger.info("Transcription worker service stopped")


if __name__ == "__main__":
    asyncio.run(_main())
