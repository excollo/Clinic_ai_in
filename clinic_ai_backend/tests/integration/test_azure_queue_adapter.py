from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import os
from uuid import uuid4

import pytest
import pytest_asyncio

from src.adapters.transcription.factory import clear_transcription_adapter_cache, get_queue_adapter
from src.adapters.transcription.types import TranscriptionQueueJob
from src.core import config as config_module

AZURITE_CONN = (
    "DefaultEndpointsProtocol=http;"
    "AccountName=devstoreaccount1;"
    "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
    "QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1;"
)

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_AZURITE_TESTS", "false").lower() != "true",
    reason="Set RUN_AZURITE_TESTS=true with Azurite running to execute Azure queue integration tests.",
)


@pytest.fixture
def azure_queue_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = config_module.get_settings()
    settings.transcription_queue_backend = "azure"
    settings.azure_queue_connection_string = AZURITE_CONN
    settings.azure_queue_name = f"transcription-jobs-{uuid4().hex[:8]}"
    settings.azure_queue_poison_name = f"transcription-jobs-poison-{uuid4().hex[:8]}"
    monkeypatch.setattr("src.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("src.adapters.transcription.factory.get_settings", lambda: settings)
    clear_transcription_adapter_cache()


@pytest_asyncio.fixture
async def adapter(azure_queue_settings):
    try:
        queue = get_queue_adapter()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Azurite queue bootstrap failed: {exc}")
    if not await queue.health_check():
        pytest.skip("Azurite queue endpoint is not reachable on 127.0.0.1:10001")
    yield queue
    clear_transcription_adapter_cache()


def _job(job_id: str = "job-1") -> TranscriptionQueueJob:
    return TranscriptionQueueJob(
        job_id=job_id,
        patient_id="patient-1",
        visit_id="visit-1",
        queued_at=datetime.now(timezone.utc),
        language_mix="hi-en",
    )


@pytest.mark.asyncio
async def test_enqueue_dequeue_roundtrip(adapter):
    await adapter.enqueue(_job("job-roundtrip"))
    item = await adapter.dequeue(visibility_timeout=30)
    assert item is not None
    assert item.job.job_id == "job-roundtrip"


@pytest.mark.asyncio
async def test_visibility_timeout(adapter):
    await adapter.enqueue(_job("job-visibility"))
    first = await adapter.dequeue(visibility_timeout=1)
    assert first is not None
    await asyncio.sleep(2)
    second = await adapter.dequeue(visibility_timeout=1)
    assert second is not None
    assert second.job.job_id == "job-visibility"
    assert second.dequeue_count >= 2


@pytest.mark.asyncio
async def test_acknowledge_removes_message(adapter):
    await adapter.enqueue(_job("job-ack"))
    item = await adapter.dequeue(visibility_timeout=10)
    assert item is not None
    await adapter.acknowledge(item.job.job_id, item.receipt)
    await asyncio.sleep(1)
    assert await adapter.dequeue(visibility_timeout=1) is None


@pytest.mark.asyncio
async def test_dequeue_count_increments(adapter):
    await adapter.enqueue(_job("job-dequeue-count"))
    first = await adapter.dequeue(visibility_timeout=1)
    assert first is not None
    assert first.dequeue_count >= 1
    await asyncio.sleep(2)
    second = await adapter.dequeue(visibility_timeout=1)
    assert second is not None
    assert second.dequeue_count >= first.dequeue_count + 1


@pytest.mark.asyncio
async def test_move_to_poison(adapter):
    await adapter.enqueue(_job("job-poison"))
    item = await adapter.dequeue(visibility_timeout=10)
    assert item is not None
    await adapter.move_to_poison(item.job.job_id, "forced_test", item.receipt)
    assert await adapter.get_poison_queue_depth() >= 1


@pytest.mark.asyncio
async def test_poison_queue_persistence(adapter):
    await adapter.enqueue(_job("job-poison-persist"))
    item = await adapter.dequeue(visibility_timeout=10)
    assert item is not None
    await adapter.move_to_poison(item.job.job_id, "persist_test", item.receipt)
    await asyncio.sleep(1)
    assert await adapter.get_poison_queue_depth() >= 1


@pytest.mark.asyncio
async def test_health_check_when_queue_exists(adapter):
    assert await adapter.health_check() is True


@pytest.mark.asyncio
async def test_health_check_when_queue_missing(adapter):
    # Force a missing queue by deleting it directly.
    adapter.queue.delete_queue()
    assert await adapter.health_check() is False


@pytest.mark.asyncio
async def test_concurrent_dequeues(adapter):
    await adapter.enqueue(_job("job-a"))
    await adapter.enqueue(_job("job-b"))

    first, second = await asyncio.gather(
        adapter.dequeue(visibility_timeout=30),
        adapter.dequeue(visibility_timeout=30),
    )
    assert first is not None and second is not None
    assert first.job.job_id != second.job.job_id


@pytest.mark.asyncio
async def test_message_ttl(adapter):
    # Direct low-TTL message to validate expiry behavior in Azurite.
    adapter.queue.send_message(adapter._encode_message({"job_id": "job-ttl"}), time_to_live=1)  # noqa: SLF001
    await asyncio.sleep(2)
    assert await adapter.dequeue(visibility_timeout=1) is None
