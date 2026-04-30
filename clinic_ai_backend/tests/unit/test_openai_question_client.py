import json

import pytest

from src.adapters.external.ai.openai_client import IntakeTurnError, OpenAIQuestionClient, validate_intake_message_quality
from src.core.config import get_settings


def test_uses_universal_hardcoded_sequence_for_first_topic() -> None:
    context = {
        "chief_complaint": "I have skin cancer follow-up after chemotherapy",
        "language": "en",
        "question_number": 2,
        "previous_qa_json": [{"question": "illness", "answer": "skin cancer"}],
    }
    guidance = OpenAIQuestionClient._build_condition_guidance(context)

    result = OpenAIQuestionClient._enforce_condition_guidance(
        result={"agent1": {}, "agent2": {}, "agent4": {}, "message": "", "question_number": 2},
        context=context,
        guidance=guidance,
    )

    assert guidance["condition_category"] == "chronic_or_hereditary"
    assert result["agent1"]["priority_topics"][0] == "reason_for_visit"
    assert result["topic"] == "onset_duration"
    assert "when did this problem first start" in result["message"].lower()


def test_moves_to_next_topic_after_covered_topic() -> None:
    context = {
        "chief_complaint": "I have fever and chills for two days",
        "language": "en",
        "question_number": 3,
        "previous_qa_json": [
            {"question": "What health problem or concern brings you in today?", "answer": "fever"},
            {"question": "When did this problem first start?", "answer": "two days", "topic": "onset_duration"},
        ],
    }
    guidance = OpenAIQuestionClient._build_condition_guidance(context)

    result = OpenAIQuestionClient._enforce_condition_guidance(
        result={"agent1": {}, "agent2": {}, "agent4": {}, "message": "", "question_number": 3},
        context=context,
        guidance=guidance,
    )

    assert guidance["condition_category"] == "general_other"
    assert result["topic"] == "associated_symptoms"
    assert "other symptoms" in result["message"].lower()


def test_blocks_menstrual_topic_for_male_patient() -> None:
    guidance = OpenAIQuestionClient._build_condition_guidance(
        {
            "chief_complaint": "period problem and abdominal pain",
            "gender": "male",
            "patient_age": 32,
        }
    )

    assert "menstrual_pregnancy" not in guidance["priority_topics"]
    assert "menstrual_pregnancy" in guidance["avoid_topics"]


def test_uses_travel_history_when_recent_travel_is_true() -> None:
    guidance = OpenAIQuestionClient._build_condition_guidance(
        {
            "chief_complaint": "stomach pain",
            "has_travelled_recently": True,
        }
    )

    assert guidance["priority_topics"][6] == "travel_history"


def test_uses_family_history_branch_for_chronic_cases() -> None:
    guidance = OpenAIQuestionClient._build_condition_guidance(
        {
            "chief_complaint": "diabetes follow up",
            "has_travelled_recently": False,
        }
    )

    assert guidance["priority_topics"][7] == "family_history"
    assert guidance["priority_topics"][8] == "past_evaluation"


def test_uses_pain_assessment_branch_for_pain_cases() -> None:
    guidance = OpenAIQuestionClient._build_condition_guidance(
        {
            "chief_complaint": "severe back pain",
            "has_travelled_recently": False,
        }
    )

    assert guidance["priority_topics"][7] == "pain_assessment"


def test_infers_covered_topic_from_question_text_without_topic_field() -> None:
    context = {
        "chief_complaint": "I have fever and chills for two days",
        "language": "en",
        "question_number": 3,
        "previous_qa_json": [
            {
                "question": "When did this problem first start, and has it been continuous or on and off since then?",
                "answer": "for two days",
            }
        ],
    }

    covered = OpenAIQuestionClient._extract_covered_topics(context)

    assert covered == ["onset_duration"]


def test_merges_model_covered_topics_with_history_topics() -> None:
    context = {
        "chief_complaint": "I have fever and chills for two days",
        "language": "en",
        "question_number": 3,
        "previous_qa_json": [
            {
                "question": "When did this problem first start, and has it been continuous or on and off since then?",
                "answer": "for two days",
            }
        ],
    }
    guidance = OpenAIQuestionClient._build_condition_guidance(context)

    result = OpenAIQuestionClient._enforce_condition_guidance(
        result={
            "agent1": {},
            "agent2": {"topics_covered": ["associated_symptoms"]},
            "agent4": {},
            "message": "",
            "question_number": 3,
        },
        context=context,
        guidance=guidance,
    )

    assert result["agent2"]["topics_covered"] == ["associated_symptoms", "onset_duration"]
    assert result["topic"] == "associated_symptoms"


def test_select_intake_message_uses_llm_when_flag_enabled_and_valid() -> None:
    settings = get_settings()
    settings.intake_use_llm_message = True

    selection = OpenAIQuestionClient._select_intake_message(
        llm_message="Can you describe all symptoms you noticed with this issue?",
        llm_topic="associated_symptoms",
        enforced_topic="associated_symptoms",
        language="en",
        allow_llm_message=settings.intake_use_llm_message,
    )

    assert selection["message"] == "Can you describe all symptoms you noticed with this issue?"
    assert selection["source"] == "llm"
    assert selection["fallback_reason"] == ""


def test_select_intake_message_falls_back_when_topic_changes() -> None:
    settings = get_settings()
    settings.intake_use_llm_message = True

    selection = OpenAIQuestionClient._select_intake_message(
        llm_message="When did this start for you?",
        llm_topic="onset_duration",
        enforced_topic="associated_symptoms",
        language="en",
        allow_llm_message=settings.intake_use_llm_message,
    )

    assert selection["message"] == OpenAIQuestionClient._topic_message("associated_symptoms", "en")
    assert selection["source"] == "template_fallback"
    assert selection["fallback_reason"] == "topic_mismatch"


def test_select_intake_message_keeps_llm_message_when_flag_disabled() -> None:
    settings = get_settings()
    settings.intake_use_llm_message = False

    selection = OpenAIQuestionClient._select_intake_message(
        llm_message="Can you describe all symptoms you noticed with this issue?",
        llm_topic="associated_symptoms",
        enforced_topic="associated_symptoms",
        language="en",
        allow_llm_message=settings.intake_use_llm_message,
    )

    assert selection["message"] == "Can you describe all symptoms you noticed with this issue?"
    assert selection["source"] == "llm"
    assert selection["fallback_reason"] == ""


def test_generate_intake_turn_raises_for_missing_agent_block(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAIQuestionClient()
    payload = {
        "agent1": {"condition_category": "general_other", "priority_topics": ["onset_duration"]},
        "agent2": {"topics_covered": [], "information_gaps": ["onset_duration"]},
        "message": "When did this problem first start?",
        "topic": "onset_duration",
        "is_complete": False,
    }
    monkeypatch.setattr(client, "_chat_completion", lambda **_: json.dumps(payload))

    with pytest.raises(IntakeTurnError) as exc_info:
        client.generate_intake_turn(
            {
                "chief_complaint": "fever",
                "language": "en",
                "question_number": 2,
                "previous_qa_json": [{"question": "illness", "answer": "fever"}],
            }
        )

    assert exc_info.value.reason_code == "agent_blocks_missing"


def test_generate_intake_turn_keeps_llm_message_even_if_validation_flags_it(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    settings.intake_use_llm_message = True
    client = OpenAIQuestionClient()
    payload = {
        "agent1": {"condition_category": "general_other", "priority_topics": ["associated_symptoms"]},
        "agent2": {"topics_covered": ["onset_duration"], "information_gaps": ["associated_symptoms"]},
        "agent4": {"next_topic": "associated_symptoms", "stop_intake": False, "reason": "Continue"},
        "message": "Tell me symptoms now",
        "topic": "associated_symptoms",
        "is_complete": False,
    }
    monkeypatch.setattr(client, "_chat_completion", lambda **_: json.dumps(payload))

    result = client.generate_intake_turn(
        {
            "chief_complaint": "fever",
            "language": "en",
            "question_number": 3,
            "previous_qa_json": [
                {"question": "illness", "answer": "fever"},
                {"question": "When did this problem first start?", "answer": "2 days", "topic": "onset_duration"},
            ],
        }
    )

    assert result["message"] == "Tell me symptoms now"
    assert result["last_message_source"] == "llm"
    assert result["last_fallback_reason"] == ""
    assert result["llm_message_valid"] is False


def test_generate_intake_turn_normalizes_topic_alias_to_canonical(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    settings.intake_use_llm_message = True
    client = OpenAIQuestionClient()
    payload = {
        "agent1": {"condition_category": "general_other", "priority_topics": ["current_symptoms"]},
        "agent2": {"topics_covered": ["onset_duration"], "information_gaps": ["current_symptoms"]},
        "agent4": {"next_topic": "current_symptoms", "stop_intake": False, "reason": "Continue"},
        "message": "What other symptoms are you noticing right now?",
        "topic": "current_symptoms",
        "is_complete": False,
    }
    monkeypatch.setattr(client, "_chat_completion", lambda **_: json.dumps(payload))

    result = client.generate_intake_turn(
        {
            "chief_complaint": "fever",
            "language": "en",
            "question_number": 3,
            "previous_qa_json": [
                {"question": "illness", "answer": "fever"},
                {"question": "When did this problem first start?", "answer": "2 days", "topic": "onset_duration"},
            ],
        }
    )

    assert result["last_model_topic"] == "associated_symptoms"
    assert result["topic"] == "associated_symptoms"


def test_select_intake_message_keeps_closing_deterministic() -> None:
    selection = OpenAIQuestionClient._select_intake_message(
        llm_message="Anything from model",
        llm_topic="closing",
        enforced_topic="closing",
        language="en",
        allow_llm_message=True,
    )

    assert selection["source"] == "template_fallback"
    assert selection["fallback_reason"] == ""
    assert "thank you" in selection["message"].lower()


def test_hindi_message_sanity_check_rejects_non_devanagari() -> None:
    validation = validate_intake_message_quality(
        "What symptoms are you feeling?",
        topic="associated_symptoms",
        language="hi",
    )

    assert validation["valid"] is False
    assert validation["reason"] == "language_mismatch"


def test_topic_message_uses_selected_language_templates() -> None:
    assert "அறிகுறிகளை" in OpenAIQuestionClient._topic_message("associated_symptoms", "ta")
    assert "లక్షణాలు" in OpenAIQuestionClient._topic_message("associated_symptoms", "te")
    assert "উপসর্গ" in OpenAIQuestionClient._topic_message("associated_symptoms", "bn")
    assert "लक्षणे" in OpenAIQuestionClient._topic_message("associated_symptoms", "mr")
    assert "ಲಕ್ಷಣ" in OpenAIQuestionClient._topic_message("associated_symptoms", "kn")


def test_script_validation_rejects_wrong_script_for_new_languages() -> None:
    assert validate_intake_message_quality("What symptoms are you feeling?", topic="associated_symptoms", language="ta")[
        "reason"
    ] == "language_mismatch"
    assert validate_intake_message_quality("What symptoms are you feeling?", topic="associated_symptoms", language="te")[
        "reason"
    ] == "language_mismatch"
    assert validate_intake_message_quality("What symptoms are you feeling?", topic="associated_symptoms", language="bn")[
        "reason"
    ] == "language_mismatch"
    assert validate_intake_message_quality("What symptoms are you feeling?", topic="associated_symptoms", language="mr")[
        "reason"
    ] == "language_mismatch"
    assert validate_intake_message_quality("What symptoms are you feeling?", topic="associated_symptoms", language="kn")[
        "reason"
    ] == "language_mismatch"


def test_detect_patient_opt_out_returns_structured_response(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAIQuestionClient()
    monkeypatch.setattr(
        client,
        "_chat_completion",
        lambda **_: json.dumps({"is_opt_out": True, "confidence": 0.91, "reason": "patient asked to stop"}),
    )

    result = client.detect_patient_opt_out(message_text="please stop now", language="en")

    assert result["is_opt_out"] is True
    assert result["confidence"] == pytest.approx(0.91)
    assert result["reason"] == "patient asked to stop"


def test_detect_patient_opt_out_raises_for_invalid_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAIQuestionClient()
    monkeypatch.setattr(
        client,
        "_chat_completion",
        lambda **_: json.dumps({"is_opt_out": "yes", "confidence": 0.5, "reason": "bad"}),
    )

    with pytest.raises(RuntimeError, match="opt_out_detection_schema_invalid"):
        client.detect_patient_opt_out(message_text="stop", language="en")
