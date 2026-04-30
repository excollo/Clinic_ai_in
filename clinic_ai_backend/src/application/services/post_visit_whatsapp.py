"""WhatsApp: generated post-visit summary vs short follow-up template pings."""
from __future__ import annotations

import logging

from src.adapters.external.whatsapp.meta_whatsapp_client import MetaWhatsAppClient
from src.application.services.follow_up_whatsapp_templates import (
    default_follow_up_body_line,
    follow_up_meta_template_param_count,
    follow_up_template_body_values,
    follow_up_template_language_code,
    resolve_follow_up_template_name,
)
from src.application.services.intake_chat_service import IntakeChatService
from src.application.utils.follow_up_dates import parse_next_visit_at
from src.core.config import get_settings
from src.core.language_support import build_template_language_candidates

logger = logging.getLogger(__name__)


def _language_candidates(preferred_language: str, settings) -> list[str]:
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


def send_post_visit_summary_whatsapp(*, patient: dict, whatsapp_payload: str) -> bool:
    """
    Send the generated post-visit text (emoji summary line) on its own template channel.

    Uses WHATSAPP_POST_VISIT_TEMPLATE_NAME only. If template delivery fails, falls back to
    plain text message delivery with the generated summary payload.
    """
    settings = get_settings()
    if not (settings.whatsapp_access_token or "").strip() or not (settings.whatsapp_phone_number_id or "").strip():
        logger.info("post_visit_whatsapp_skipped reason=no_meta_credentials")
        return False
    primary_template = (settings.whatsapp_post_visit_template_name or "").strip()
    raw_phone = str(patient.get("phone_number") or "").strip()
    to_number = IntakeChatService._normalize_phone_number(raw_phone)
    if not to_number:
        logger.info("post_visit_whatsapp_skipped reason=no_patient_phone")
        return False
    language_codes = build_template_language_candidates(
        str(patient.get("preferred_language") or "en"),
        hindi_codes=(
            settings.whatsapp_post_visit_template_lang_hi,
            settings.whatsapp_intake_template_lang_hi,
            "hi_IN",
            "hi",
        ),
        english_codes=(
            settings.whatsapp_post_visit_template_lang_en,
            settings.whatsapp_intake_template_lang_en,
            "en_US",
            "en",
        ),
    )
    param_count = max(0, int(settings.whatsapp_post_visit_template_param_count))
    body = (whatsapp_payload or "").strip()
    body_values = [body[:900]] if param_count > 0 and body else []
    candidate_templates: list[str] = []
    if primary_template:
        candidate_templates.append(primary_template)

    body_variants: list[list[str]] = [body_values]
    if body_values:
        # Some templates don't define body params; retry without params.
        body_variants.append([])

    if candidate_templates:
        for template_name in candidate_templates:
            for lang_code in language_codes:
                for body_variant in body_variants:
                    try:
                        MetaWhatsAppClient().send_template(
                            to_number=to_number,
                            template_name=template_name,
                            language_code=lang_code,
                            body_values=body_variant,
                        )
                        return True
                    except Exception as exc:
                        logger.warning(
                            "post_visit_whatsapp_failed template=%s lang=%s params=%d error=%s",
                            template_name,
                            lang_code,
                            len(body_variant),
                            exc,
                        )

    # Never fall back to intake/opening_msg template here.
    # If post-visit template isn't configured or fails, send plain text summary directly.
    text_payload = (whatsapp_payload or "").strip()
    if not text_payload:
        logger.info("post_visit_whatsapp_skipped reason=empty_summary_payload")
        return False
    try:
        MetaWhatsAppClient().send_text(to_number=to_number, message=text_payload[:3500])
        return True
    except Exception as exc:
        logger.warning("post_visit_whatsapp_text_fallback_failed error=%s", exc)
        return False


def send_immediate_follow_up_template_whatsapp(*, patient: dict, payload: dict, preferred_language: str) -> bool:
    """
    Short follow-up line on the reminder template (same as T-3d / day-before cron).

    Sent right after the generated post-visit template so the patient gets both the
    detailed summary and a fixed-format follow-up ping.
    """
    settings = get_settings()
    if not (settings.whatsapp_access_token or "").strip() or not (settings.whatsapp_phone_number_id or "").strip():
        logger.info("follow_up_immediate_whatsapp_skipped reason=no_meta_credentials")
        return False
    primary_template = resolve_follow_up_template_name(settings)
    fallback_template = (settings.whatsapp_intake_template_name or "").strip()
    if not primary_template and not fallback_template:
        logger.info("follow_up_immediate_whatsapp_skipped reason=no_template_configured")
        return False
    raw_phone = str(patient.get("phone_number") or "").strip()
    to_number = IntakeChatService._normalize_phone_number(raw_phone)
    if not to_number:
        logger.info("follow_up_immediate_whatsapp_skipped reason=no_patient_phone")
        return False
    language_code = follow_up_template_language_code(settings, preferred_language)
    param_count = follow_up_meta_template_param_count(settings)
    follow_up_text = str(payload.get("follow_up") or "").strip() or "Follow your doctor's advice."
    nv = parse_next_visit_at(payload.get("next_visit_date"))
    synthetic = {"follow_up_text": follow_up_text}
    if nv is not None:
        body_values = follow_up_template_body_values(
            reminder_kind="immediate",
            next_visit_at=nv,
            follow_up_text=follow_up_text,
        )
        if param_count > 0 and not body_values:
            body_values = [default_follow_up_body_line("immediate", nv, synthetic)]
    else:
        body_values = [f"Your visit summary is ready. {follow_up_text}".strip()[:900]] if param_count > 0 else []
    candidate_templates: list[str] = []
    if primary_template:
        candidate_templates.append(primary_template)
    if fallback_template and fallback_template not in candidate_templates:
        candidate_templates.append(fallback_template)

    for template_name in candidate_templates:
        body_primary = body_values[:param_count] if param_count else body_values
        body_variants: list[list[str]] = [body_primary]
        if body_primary:
            body_variants.append([])
        for lang_code in _language_candidates(preferred_language, settings):
            for body_variant in body_variants:
                try:
                    MetaWhatsAppClient().send_template(
                        to_number=to_number,
                        template_name=template_name,
                        language_code=lang_code,
                        body_values=body_variant,
                    )
                    return True
                except Exception as exc:
                    logger.warning(
                        "follow_up_immediate_whatsapp_failed template=%s lang=%s params=%d error=%s",
                        template_name,
                        lang_code,
                        len(body_variant),
                        exc,
                    )
    return False
