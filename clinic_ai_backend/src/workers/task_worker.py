"""Background worker entrypoint for transcription jobs."""
from __future__ import annotations

import asyncio

from src.workers.transcription_worker import TranscriptionWorker


async def run_transcription_worker(poll_interval_sec: float = 1.0) -> None:
    """Continuously poll queue and process transcription jobs."""
    worker = TranscriptionWorker()
    while True:
        worked = await worker.process_next_async()
        if not worked:
            await asyncio.sleep(poll_interval_sec)


def main() -> None:
    """CLI entrypoint."""
    asyncio.run(run_transcription_worker())


if __name__ == "__main__":
    main()
