"""Azure Storage Queue adapter for transcription jobs."""
from __future__ import annotations

import asyncio
import base64
import json
from datetime import datetime, timezone

from azure.core.exceptions import AzureError, ResourceExistsError
from azure.storage.queue import QueueClient

from src.adapters.transcription.types import DequeuedJob, TranscriptionQueueJob
from src.core.config import get_settings
from src.core.errors import ConfigurationError


class AzureQueueAdapter:
    """Queue adapter backed by Azure Storage Queue + poison queue."""

    def __init__(self) -> None:
        settings = get_settings()
        self.connection_string = settings.azure_queue_connection_string.strip()
        self.queue_name = settings.azure_queue_name.strip()
        self.poison_queue_name = settings.azure_queue_poison_name.strip()
        if (
            not self.connection_string
            or not self.queue_name
            or not self.poison_queue_name
            or "AccountName=" not in self.connection_string
            or "AccountKey=" not in self.connection_string
        ):
            raise ConfigurationError(
                "Azure queue backend requires AZURE_QUEUE_CONNECTION_STRING, AZURE_QUEUE_NAME, and "
                "AZURE_QUEUE_POISON_NAME with a valid Azure Storage connection string."
            )
        self.queue = QueueClient.from_connection_string(
            self.connection_string,
            self.queue_name,
            connection_timeout=3,
            read_timeout=3,
        )
        self.poison_queue = QueueClient.from_connection_string(
            self.connection_string,
            self.poison_queue_name,
            connection_timeout=3,
            read_timeout=3,
        )
        self._ensure_queues()

    def _ensure_queues(self) -> None:
        for client in (self.queue, self.poison_queue):
            try:
                client.create_queue()
            except ResourceExistsError:
                pass

    @staticmethod
    def _encode_message(payload: dict) -> str:
        return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")

    @staticmethod
    def _decode_message(content: str) -> dict:
        raw = base64.b64decode(content.encode("utf-8")).decode("utf-8")
        return json.loads(raw)

    async def enqueue(self, job: TranscriptionQueueJob) -> str:
        body = {
            "job_id": job.job_id,
            "audio_storage_ref": job.audio_storage_ref,
            "patient_id": job.patient_id,
            "visit_id": job.visit_id,
            "doctor_id": job.doctor_id,
            "noise_environment": job.noise_environment,
            "language_mix": job.language_mix,
            "queued_at": (job.queued_at or datetime.now(timezone.utc)).isoformat(),
        }

        def _send() -> str:
            msg = self.queue.send_message(self._encode_message(body), time_to_live=86400)
            return str(msg.id)

        return await asyncio.to_thread(_send)

    async def dequeue(self, visibility_timeout: int = 600) -> DequeuedJob | None:
        def _receive() -> DequeuedJob | None:
            pages = self.queue.receive_messages(messages_per_page=1, visibility_timeout=visibility_timeout).by_page()
            for page in pages:
                for msg in page:
                    data = self._decode_message(msg.content)
                    dequeue_count = int(getattr(msg, "dequeue_count", 1) or 1)
                    if dequeue_count > 5:
                        poison_payload = {
                            "job_id": str(data.get("job_id", "")),
                            "reason": "max_dequeue_exceeded",
                            "dequeue_count": dequeue_count,
                            "moved_to_poison_at": datetime.now(timezone.utc).isoformat(),
                        }
                        self.poison_queue.send_message(self._encode_message(poison_payload), time_to_live=86400 * 7)
                        self.queue.delete_message(message_id=str(msg.id), pop_receipt=str(msg.pop_receipt))
                        return None
                    return DequeuedJob(
                        job=TranscriptionQueueJob(
                            job_id=str(data.get("job_id", "")),
                            audio_storage_ref=data.get("audio_storage_ref"),
                            patient_id=data.get("patient_id"),
                            visit_id=data.get("visit_id"),
                            doctor_id=data.get("doctor_id"),
                            noise_environment=data.get("noise_environment"),
                            language_mix=data.get("language_mix"),
                            queued_at=datetime.fromisoformat(data["queued_at"]) if data.get("queued_at") else None,
                        ),
                        message_id=str(msg.id),
                        receipt=f"{msg.id}::{msg.pop_receipt}",
                        dequeue_count=dequeue_count,
                    )
            return None

        return await asyncio.to_thread(_receive)

    async def acknowledge(self, job_id: str, receipt: str) -> None:  # noqa: ARG002
        def _delete() -> None:
            if not receipt or "::" not in receipt:
                return
            message_id, pop_receipt = receipt.split("::", 1)
            self.queue.delete_message(message_id=message_id, pop_receipt=pop_receipt)

        await asyncio.to_thread(_delete)

    async def move_to_poison(self, job_id: str, reason: str, receipt: str = "") -> None:
        payload = {
            "job_id": job_id,
            "reason": reason,
            "moved_to_poison_at": datetime.now(timezone.utc).isoformat(),
        }

        def _send() -> None:
            self.poison_queue.send_message(self._encode_message(payload), time_to_live=86400 * 7)
            if receipt and "::" in receipt:
                message_id, pop_receipt = receipt.split("::", 1)
                self.queue.delete_message(message_id=message_id, pop_receipt=pop_receipt)

        await asyncio.to_thread(_send)

    async def get_queue_depth(self) -> int:
        def _depth() -> int:
            props = self.queue.get_queue_properties()
            return int(getattr(props, "approximate_message_count", 0) or 0)

        return await asyncio.to_thread(_depth)

    async def get_poison_queue_depth(self) -> int:
        def _depth() -> int:
            props = self.poison_queue.get_queue_properties()
            return int(getattr(props, "approximate_message_count", 0) or 0)

        return await asyncio.to_thread(_depth)

    async def health_check(self) -> bool:
        def _ping() -> bool:
            try:
                self.queue.get_queue_properties()
                return True
            except AzureError:
                return False

        return await asyncio.to_thread(_ping)
