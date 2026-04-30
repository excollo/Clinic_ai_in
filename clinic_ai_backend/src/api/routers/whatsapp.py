"""WhatsApp webhook routes module."""
import logging

from fastapi import APIRouter, HTTPException, Query, Request, Response

from src.application.services.intake_chat_service import IntakeChatService
from src.application.services.intake_chat_service import NON_TEXT_MESSAGE_TRIGGER
from src.core.config import get_settings

# Support both paths to avoid production misconfiguration drift:
# - /webhooks/whatsapp (legacy)
# - /api/webhooks/whatsapp (common with API-prefixed routes)
router = APIRouter(tags=["Workflow"])
logger = logging.getLogger(__name__)


def _verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> str:
    """Verify WhatsApp webhook endpoint."""
    settings = get_settings()
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Webhook verification failed")


@router.get("/webhooks/whatsapp")
def verify_webhook_legacy(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> str:
    return _verify_webhook(hub_mode=hub_mode, hub_verify_token=hub_verify_token, hub_challenge=hub_challenge)


@router.get("/api/webhooks/whatsapp")
def verify_webhook_api(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> str:
    return _verify_webhook(hub_mode=hub_mode, hub_verify_token=hub_verify_token, hub_challenge=hub_challenge)


async def _receive_webhook(request: Request) -> dict:
    """Receive incoming WhatsApp messages and continue intake flow."""
    body = await request.json()
    entries = body.get("entry", [])
    service = IntakeChatService()
    logger.info("WhatsApp webhook received entries=%s", len(entries))

    for entry in entries:
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                from_number = message.get("from")
                message_id = message.get("id")
                text = _extract_message_text(message)
                logger.info(
                    "WhatsApp inbound message id=%s from=%s type=%s text_present=%s",
                    message_id,
                    from_number,
                    message.get("type"),
                    bool(text),
                )
                # Intake should start even if user replies with non-text (emoji-only, sticker, reaction, media, etc.).
                if from_number:
                    service.handle_patient_reply(
                        from_number=from_number,
                        message_text=text or NON_TEXT_MESSAGE_TRIGGER,
                        message_id=message_id,
                    )

    return {"received": True}


@router.post("/webhooks/whatsapp")
async def receive_webhook_legacy(request: Request) -> dict:
    return await _receive_webhook(request)


@router.post("/api/webhooks/whatsapp")
async def receive_webhook_api(request: Request) -> dict:
    return await _receive_webhook(request)


def _extract_message_text(message: dict) -> str:
    """Extract user-entered text across common WhatsApp message types."""
    text_body = (message.get("text") or {}).get("body")
    if isinstance(text_body, str) and text_body.strip():
        return text_body.strip()

    button_text = (message.get("button") or {}).get("text")
    if isinstance(button_text, str) and button_text.strip():
        return button_text.strip()

    interactive = message.get("interactive") or {}
    interactive_button = (interactive.get("button_reply") or {}).get("title")
    if isinstance(interactive_button, str) and interactive_button.strip():
        return interactive_button.strip()

    interactive_list = (interactive.get("list_reply") or {}).get("title")
    if isinstance(interactive_list, str) and interactive_list.strip():
        return interactive_list.strip()

    return ""
