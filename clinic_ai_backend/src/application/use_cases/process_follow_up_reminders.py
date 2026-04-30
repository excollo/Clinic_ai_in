"""Send WhatsApp template reminders at T-3 days and the calendar day before next visit."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from src.adapters.external.whatsapp.meta_whatsapp_client import MetaWhatsAppClient
from src.application.services.intake_chat_service import IntakeChatService
from src.application.services.follow_up_whatsapp_templates import (
    default_follow_up_body_line,
    follow_up_meta_template_param_count,
    follow_up_template_body_values,
    follow_up_template_language_code,
    resolve_follow_up_template_name,
)
from src.core.config import get_settings
from src.core.language_support import build_template_language_candidates

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _language_candidates(settings: Any, preferred_language: str) -> list[str]:
    return build_template_language_candidates(
        preferred_language,
        hindi_codes=(
            settings.whatsapp_followup_template_lang_hi,
            settings.whatsapp_intake_template_lang_hi,
            "hi_IN",
            "hi",
        ),
        english_codes=(
            settings.whatsapp_followup_template_lang_en,
            settings.whatsapp_intake_template_lang_en,
            "en_US",
            "en",
        ),
    )


class ProcessFollowUpRemindersUseCase:
    """Scan scheduled follow-ups and send due Meta template messages."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.whatsapp = MetaWhatsAppClient()

    @staticmethod
    def _resolve_to_number(*, db: Any, doc: dict) -> str:
        """
        Resolve target WhatsApp number from reminder doc; fallback to patient profile phone.

        This keeps cron route input-free and resilient when older reminder rows lack `to_number`.
        """
        to_number = str(doc.get("to_number") or "").strip()
        if to_number:
            return to_number
        patient_id = str(doc.get("patient_id") or "").strip()
        if not patient_id:
            return ""
        patient = db.patients.find_one({"patient_id": patient_id}) or {}
        raw_phone = str(patient.get("phone_number") or "").strip()
        normalized = IntakeChatService._normalize_phone_number(raw_phone)
        if normalized:
            rid = doc.get("reminder_id")
            db.follow_up_reminders.update_one(
                {"reminder_id": rid},
                {"$set": {"to_number": normalized, "updated_at": _utc_now()}},
            )
        return normalized

    def execute(self, *, db: Any, now: datetime | None = None) -> dict[str, Any]:
        now_utc = now or _utc_now()
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)
        else:
            now_utc = now_utc.astimezone(timezone.utc)

        sent_immediate = 0
        sent_3d = 0
        sent_24h = 0
        skipped = 0
        debug: dict[str, int] = {
            "scanned": 0,
            "skipped_no_next_visit": 0,
            "skipped_bad_next_visit": 0,
            "skipped_past_visit": 0,
            "skipped_no_number": 0,
            "send_failures": 0,
            "not_due": 0,
        }
        last_error: str | None = None

        if not (self.settings.whatsapp_access_token or "").strip() or not (
            self.settings.whatsapp_phone_number_id or ""
        ).strip():
            skipped = len(list(db.follow_up_reminders.find({})))
            debug["scanned"] = skipped
            return {"sent_immediate": 0, "sent_3d": 0, "sent_24h": 0, "skipped": skipped, "debug": debug}

        template_name = resolve_follow_up_template_name(self.settings)
        if not template_name:
            skipped = len(list(db.follow_up_reminders.find({})))
            debug["scanned"] = skipped
            return {"sent_immediate": 0, "sent_3d": 0, "sent_24h": 0, "skipped": skipped, "debug": debug}

        param_count = follow_up_meta_template_param_count(self.settings)

        for doc in list(db.follow_up_reminders.find({})):
            debug["scanned"] += 1
            nv = doc.get("next_visit_at")
            if nv is None:
                skipped += 1
                debug["skipped_no_next_visit"] += 1
                continue
            if isinstance(nv, datetime):
                if nv.tzinfo is None:
                    nv = nv.replace(tzinfo=timezone.utc)
                nv = nv.astimezone(timezone.utc)
            else:
                skipped += 1
                debug["skipped_bad_next_visit"] += 1
                continue
            if nv <= now_utc:
                skipped += 1
                debug["skipped_past_visit"] += 1
                continue

            to_number = self._resolve_to_number(db=db, doc=doc)
            if not to_number:
                skipped += 1
                debug["skipped_no_number"] += 1
                continue

            lang = str(doc.get("preferred_language") or "en").strip().lower()
            language_code = follow_up_template_language_code(self.settings, lang)
            language_codes = _language_candidates(self.settings, lang)
            if language_code and language_code not in language_codes:
                language_codes.insert(0, language_code)

            t3 = nv - timedelta(days=3)
            # Second ping: one calendar day before visit (same clock as next_visit_at), not only "24h" wall literal.
            t1d = nv - timedelta(days=1)
            rid = doc.get("reminder_id")
            sent_any = False
            due_any = False

            if doc.get("remind_3d_sent_at") is None and now_utc >= t3 and now_utc < nv:
                due_any = True
                body_values = follow_up_template_body_values(
                    reminder_kind="3d",
                    next_visit_at=nv,
                    follow_up_text=str(doc.get("follow_up_text") or ""),
                )
                if param_count > 0 and not body_values:
                    body_values = [default_follow_up_body_line("3d", nv, doc)]
                try:
                    body_primary = body_values[:param_count] if param_count else body_values
                    body_variants: list[list[str]] = [body_primary]
                    if body_primary:
                        body_variants.append([])
                    sent_ok = False
                    last_send_error: str | None = None
                    for lang_code in language_codes:
                        for body_variant in body_variants:
                            try:
                                self.whatsapp.send_template(
                                    to_number=to_number,
                                    template_name=template_name,
                                    language_code=lang_code,
                                    body_values=body_variant,
                                )
                                sent_ok = True
                                break
                            except Exception as exc:
                                last_send_error = str(exc)
                                logger.warning(
                                    "follow_up_reminder_try_failed reminder_kind=3d reminder_id=%s to=%s lang=%s params=%d error=%s",
                                    rid,
                                    to_number,
                                    lang_code,
                                    len(body_variant),
                                    exc,
                                )
                        if sent_ok:
                            break
                    if not sent_ok:
                        raise RuntimeError(last_send_error or "Unable to send follow-up template")
                    db.follow_up_reminders.update_one(
                        {"reminder_id": rid},
                        {"$set": {"remind_3d_sent_at": now_utc, "updated_at": now_utc}},
                    )
                    sent_3d += 1
                    sent_any = True
                except Exception as exc:
                    logger.warning(
                        "follow_up_reminder_send_failed reminder_kind=3d reminder_id=%s to=%s error=%s",
                        rid,
                        to_number,
                        exc,
                    )
                    skipped += 1
                    debug["send_failures"] += 1
                    if last_error is None:
                        last_error = str(exc)[:300]

            fresh = db.follow_up_reminders.find_one({"reminder_id": rid}) or doc
            if fresh.get("remind_24h_sent_at") is None and now_utc >= t1d and now_utc < nv:
                due_any = True
                body_values = follow_up_template_body_values(
                    reminder_kind="1d",
                    next_visit_at=nv,
                    follow_up_text=str(doc.get("follow_up_text") or ""),
                )
                if param_count > 0 and not body_values:
                    body_values = [default_follow_up_body_line("1d", nv, fresh)]
                try:
                    body_primary = body_values[:param_count] if param_count else body_values
                    body_variants: list[list[str]] = [body_primary]
                    if body_primary:
                        body_variants.append([])
                    sent_ok = False
                    last_send_error: str | None = None
                    for lang_code in language_codes:
                        for body_variant in body_variants:
                            try:
                                self.whatsapp.send_template(
                                    to_number=to_number,
                                    template_name=template_name,
                                    language_code=lang_code,
                                    body_values=body_variant,
                                )
                                sent_ok = True
                                break
                            except Exception as exc:
                                last_send_error = str(exc)
                                logger.warning(
                                    "follow_up_reminder_try_failed reminder_kind=1d reminder_id=%s to=%s lang=%s params=%d error=%s",
                                    rid,
                                    to_number,
                                    lang_code,
                                    len(body_variant),
                                    exc,
                                )
                        if sent_ok:
                            break
                    if not sent_ok:
                        raise RuntimeError(last_send_error or "Unable to send follow-up template")
                    db.follow_up_reminders.update_one(
                        {"reminder_id": rid},
                        {"$set": {"remind_24h_sent_at": now_utc, "updated_at": now_utc}},
                    )
                    sent_24h += 1
                    sent_any = True
                except Exception as exc:
                    logger.warning(
                        "follow_up_reminder_send_failed reminder_kind=1d reminder_id=%s to=%s error=%s",
                        rid,
                        to_number,
                        exc,
                    )
                    skipped += 1
                    debug["send_failures"] += 1
                    if last_error is None:
                        last_error = str(exc)[:300]
            if not due_any:
                debug["not_due"] += 1

        out: dict[str, Any] = {
            "sent_immediate": sent_immediate,
            "sent_3d": sent_3d,
            "sent_24h": sent_24h,
            "skipped": skipped,
            "debug": debug,
        }
        if last_error:
            out["last_error"] = last_error
        return out
