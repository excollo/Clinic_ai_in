"""Short follow-up reminder lines for Meta templates (T-3d, day-before, and immediate ping)."""
from __future__ import annotations

from datetime import datetime

from src.core.config import Settings
from src.core.language_support import uses_hindi_template_family


def resolve_follow_up_template_name(settings: Settings) -> str | None:
    """Follow-up/reminder Meta template name (default: ``follow_up_1``)."""
    name = (settings.whatsapp_followup_template_name or "").strip()
    if name:
        return name
    # Safety fallback for older deployments that only configured intake template.
    return (settings.whatsapp_intake_template_name or "").strip() or None


def follow_up_template_language_code(settings: Settings, preferred_language: str) -> str:
    """Language code for follow-up sends (uses follow-up template language envs)."""
    if uses_hindi_template_family(preferred_language):
        return settings.whatsapp_followup_template_lang_hi
    return settings.whatsapp_followup_template_lang_en


def follow_up_meta_template_param_count(settings: Settings) -> int:
    """Body parameter count for follow-up template (uses follow-up template env)."""
    return max(0, int(settings.whatsapp_followup_template_param_count))


def follow_up_template_body_values(
    *,
    reminder_kind: str,
    next_visit_at: datetime,
    follow_up_text: str,
) -> list[str]:
    """One body parameter for templates like opening_msg (single {{1}})."""
    date_s = next_visit_at.strftime("%Y-%m-%d")
    if reminder_kind in {"24h", "1d"}:
        return [f"Follow-up visit tomorrow ({date_s}). {follow_up_text}".strip()[:900]]
    if reminder_kind == "immediate":
        return [f"Follow-up visit scheduled on {date_s}. {follow_up_text}".strip()[:900]]
    return [f"Follow-up visit in 3 days on {date_s}. {follow_up_text}".strip()[:900]]


def default_follow_up_body_line(kind: str, next_visit_at: datetime, doc: dict) -> str:
    date_s = next_visit_at.strftime("%Y-%m-%d %H:%M UTC")
    ft = str(doc.get("follow_up_text", "") or "")
    if kind in {"24h", "1d"}:
        return f"Reminder: your follow-up visit is tomorrow ({date_s}). {ft}".strip()
    if kind == "immediate":
        return f"Follow-up visit scheduled ({date_s}). {ft}".strip()
    return f"Reminder: your follow-up visit is in 3 days ({date_s}). {ft}".strip()
