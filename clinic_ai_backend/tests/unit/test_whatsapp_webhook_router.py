from fastapi.testclient import TestClient

from src.app import create_app


class _FakeIntakeService:
    calls: list[dict] = []

    def handle_patient_reply(self, *, from_number: str, message_text: str, message_id: str | None = None) -> None:
        self.calls.append(
            {
                "from_number": from_number,
                "message_text": message_text,
                "message_id": message_id,
            }
        )


def _payload(message: dict) -> dict:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [message],
                        }
                    }
                ]
            }
        ]
    }


def test_webhook_legacy_path_dispatches_text_reply(monkeypatch) -> None:
    from src.api.routers import whatsapp as whatsapp_router

    _FakeIntakeService.calls = []
    monkeypatch.setattr(whatsapp_router, "IntakeChatService", _FakeIntakeService)
    client = TestClient(create_app())

    response = client.post(
        "/webhooks/whatsapp",
        json=_payload({"id": "wamid-1", "from": "919999999999", "type": "text", "text": {"body": "fever"}}),
    )

    assert response.status_code == 200
    assert _FakeIntakeService.calls
    assert _FakeIntakeService.calls[0]["message_text"] == "fever"


def test_webhook_api_prefixed_path_dispatches_text_reply(monkeypatch) -> None:
    from src.api.routers import whatsapp as whatsapp_router

    _FakeIntakeService.calls = []
    monkeypatch.setattr(whatsapp_router, "IntakeChatService", _FakeIntakeService)
    client = TestClient(create_app())

    response = client.post(
        "/api/webhooks/whatsapp",
        json=_payload({"id": "wamid-2", "from": "919888888888", "type": "text", "text": {"body": "cough"}}),
    )

    assert response.status_code == 200
    assert _FakeIntakeService.calls
    assert _FakeIntakeService.calls[0]["message_text"] == "cough"


def test_webhook_non_text_message_still_triggers_intake(monkeypatch) -> None:
    from src.api.routers import whatsapp as whatsapp_router
    from src.application.services.intake_chat_service import NON_TEXT_MESSAGE_TRIGGER

    _FakeIntakeService.calls = []
    monkeypatch.setattr(whatsapp_router, "IntakeChatService", _FakeIntakeService)
    client = TestClient(create_app())

    response = client.post(
        "/api/webhooks/whatsapp",
        json=_payload({"id": "wamid-3", "from": "919777777777", "type": "sticker"}),
    )

    assert response.status_code == 200
    assert _FakeIntakeService.calls
    assert _FakeIntakeService.calls[0]["message_text"] == NON_TEXT_MESSAGE_TRIGGER
