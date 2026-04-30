"""Meta WhatsApp Cloud API client module."""
from __future__ import annotations

import json
from urllib import request
from urllib.error import HTTPError

from src.core.config import get_settings


class MetaWhatsAppClient:
    """Client for sending WhatsApp text messages."""

    def send_text(self, to_number: str, message: str) -> None:
        """Send a text message via Meta WhatsApp Cloud API."""
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {"body": message},
        }
        self._post_message(payload)

    def send_template(
        self,
        to_number: str,
        template_name: str,
        language_code: str,
        body_values: list[str] | None = None,
    ) -> None:
        """Send a template message via Meta WhatsApp Cloud API."""
        parameters = [{"type": "text", "text": value} for value in (body_values or [])]
        template_payload: dict = {
            "name": template_name,
            "language": {"code": language_code},
        }
        if parameters:
            template_payload["components"] = [
                {
                    "type": "body",
                    "parameters": parameters,
                }
            ]
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "template",
            "template": template_payload,
        }
        self._post_message(payload)

    @staticmethod
    def _post_message(payload: dict) -> None:
        settings = get_settings()
        if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
            raise RuntimeError("WhatsApp credentials are missing")

        url = (
            f"https://graph.facebook.com/{settings.whatsapp_api_version}/"
            f"{settings.whatsapp_phone_number_id}/messages"
        )
        req = request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.whatsapp_access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=20):
                return
        except HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"WhatsApp API request failed: {response_body}") from exc
