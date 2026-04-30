# Backend Stop-Intent Detection (LLM opt-out) — Full Green Code

## `clinic_ai_backend/src/adapters/external/ai/openai_client.py`
```diff
+    def detect_patient_opt_out(self, *, message_text: str, language: str, recent_answers: list[dict] | None = None) -> dict:
+        """Detect whether the patient is asking to stop the intake flow."""
+        template_path = Path(__file__).resolve().parent / "prompt_templates" / "opt_out_prompt.txt"
+        template = template_path.read_text(encoding="utf-8")
+        prompt = (
+            template.replace("{{language}}", normalize_intake_language(str(language or "en"))).replace(
+                "{{message_text}}", str(message_text or "")
+            ).replace("{{recent_answers_json}}", json.dumps(recent_answers or [], ensure_ascii=True))
+        )
+        try:
+            content = self._chat_completion(
+                prompt=prompt,
+                system_role=(
+                    "You are a clinical intake stop-intent classifier. "
+                    "Return strict JSON only with the required schema."
+                ),
+            )
+        except (error.HTTPError, error.URLError, TimeoutError) as exc:
+            raise RuntimeError("opt_out_detection_http_error") from exc
+
+        try:
+            result = json.loads(content)
+        except json.JSONDecodeError as exc:
+            raise RuntimeError("opt_out_detection_json_parse_error") from exc
+        if not isinstance(result, dict):
+            raise RuntimeError("opt_out_detection_schema_invalid")
+        if not isinstance(result.get("is_opt_out"), bool):
+            raise RuntimeError("opt_out_detection_schema_invalid")
+        if not isinstance(result.get("confidence"), (int, float)):
+            raise RuntimeError("opt_out_detection_schema_invalid")
+        if not isinstance(result.get("reason"), str):
+            raise RuntimeError("opt_out_detection_schema_invalid")
+
+        result["confidence"] = float(result["confidence"])
+        return result
```

## `clinic_ai_backend/src/application/services/intake_chat_service.py`
```diff
+    def handle_patient_reply(self, from_number: str, message_text: str, message_id: str | None = None) -> None:
+        """Handle incoming WhatsApp reply and continue intake."""
+        normalized_from = self._normalize_phone_number(from_number)
+        session = self.db.intake_sessions.find_one(
+            {
+                "to_number": normalized_from,
+                "status": {"$in": ["awaiting_conversation_start", "awaiting_illness", "in_progress"]},
+            },
+            sort=[("updated_at", -1)],
+        )
+        if not session and normalized_from:
+            # Backward compatibility for older records saved with + prefix.
+            session = self.db.intake_sessions.find_one(
+                {
+                    "to_number": f"+{normalized_from}",
+                    "status": {"$in": ["awaiting_conversation_start", "awaiting_illness", "in_progress"]},
+                },
+                sort=[("updated_at", -1)],
+            )
+        if not session:
+            return
+
+        if message_id and not self._claim_message(session["_id"], message_id):
+            return
+
+        cleaned = (message_text or "").strip()
+        if not cleaned:
+            return
+        if self._is_probable_duplicate_reply(session, cleaned):
+            return
+        self._remember_inbound_text(session["_id"], cleaned)
+        stop_detection = self._detect_stop_request(
+            message_text=cleaned,
+            language=str(session.get("language", "en") or "en"),
+            answers=list(session.get("answers", [])),
+        )
+        if bool(stop_detection.get("detected", False)):
+            logger.info(
+                "intake_stop_detected visit_id=%s session_id=%s source=%s confidence=%s reason=%s",
+                str(session.get("visit_id", "") or ""),
+                str(session.get("_id", "") or ""),
+                str(stop_detection.get("source", "") or ""),
+                str(stop_detection.get("confidence", "") or ""),
+                str(stop_detection.get("reason", "") or ""),
+            )
+            self.db.intake_sessions.update_one(
+                {"_id": session["_id"]},
+                {"$set": {"status": "stopped", "updated_at": datetime.now(timezone.utc)}},
+            )
+            end_msg = self._closing_message(
+                session.get("language", "en"),
+                session.get("patient_name"),
+            )
+            self._safe_send_text(from_number, end_msg)
+            self._auto_generate_pre_visit_summary(session)
+            return
+
+        status = session.get("status")
+        if status == "awaiting_conversation_start":
+            self.db.intake_sessions.update_one(
+                {"_id": session["_id"], "status": "awaiting_conversation_start"},
+                {
+                    "$set": {
+                        "status": "awaiting_illness",
+                        "updated_at": datetime.now(timezone.utc),
+                    }
+                },
+            )
+            self._safe_send_text(
+                session["to_number"],
+                self._chief_complaint_question(session.get("language", "en")),
+            )
+            return
+
+        if status == "awaiting_illness":
+            self._save_illness_and_generate_questions(session, cleaned)
+            return
+
+        if status == "in_progress":
+            if self._should_treat_as_illness_correction(session, cleaned):
+                self._replace_illness_and_regenerate(session, cleaned)
+                return
+            self._save_answer_and_ask_next(session, cleaned)
```

```diff
+    @staticmethod
+    def _is_stop_request(message_text: str) -> bool:
+        normalized = " ".join(str(message_text or "").strip().lower().split())
+        if not normalized:
+            return False
+        if normalized in STOP_WORDS:
+            return True
+        stop_phrases = {
+            "please stop",
+            "stop it",
+            "stop now",
+            "i want to stop",
+            "dont continue",
+            "do not continue",
+            "mat karo",
+            "aage mat badho",
+            "ruk jao",
+            "ruk jaiye",
+            "रोक दो",
+            "मत करो",
+            "आगे मत बढ़ो",
+            "ఆపండి",
+            "ఇక్కడ ఆపు",
+            "நிறுத்துங்கள்",
+            "இங்கே நிறுத்துங்கள்",
+            "বন্ধ করুন",
+            "এখানেই বন্ধ করুন",
+            "थांब",
+            "थांबा",
+            "इथेच थांब",
+            "इथेच थांबा",
+            "नಿಲ್ಲಿಸಿ",
+            "ಇಲ್ಲಿಗೆ ನಿಲ್ಲಿಸಿ",
+        }
+        return normalized in stop_phrases
+
+    def _detect_stop_request(self, *, message_text: str, language: str, answers: list[dict]) -> dict:
+        """Best-effort stop detection using LLM first and keyword fallback."""
+        try:
+            result = self.openai.detect_patient_opt_out(
+                message_text=message_text,
+                language=language,
+                recent_answers=answers[-5:],
+            )
+        except Exception:
+            result = None
+
+        if isinstance(result, dict) and bool(result.get("is_opt_out", False)):
+            return {
+                "detected": True,
+                "source": "llm",
+                "confidence": result.get("confidence", ""),
+                "reason": result.get("reason", ""),
+            }
+
+        keyword_detected = self._is_stop_request(message_text)
+        if keyword_detected:
+            return {
+                "detected": True,
+                "source": "keyword_fallback",
+                "confidence": "",
+                "reason": "",
+            }
+        return {"detected": False, "source": "", "confidence": "", "reason": ""}
+
+    @staticmethod
+    def _closing_message(language: str, patient_name: str | None) -> str:
+        name = str(patient_name or "").strip()
+        template_key = "closing_named" if name else "closing_unnamed"
+        template = IntakeChatService._language_text(INTAKE_STATIC_TEXT[template_key], language)
+        return template.format(patient_name=name)
```

## `clinic_ai_backend/src/adapters/external/ai/prompt_templates/opt_out_prompt.txt`
```diff
+You are classifying whether the patient wants to stop the intake chat.
+
+Input:
+- language: {{language}}
+- latest_patient_message: {{message_text}}
+- recent_answers_json: {{recent_answers_json}}
+
+Task:
+Classify if latest_patient_message means the patient does not want to continue answering intake questions.
+
+Rules:
+1) Mark is_opt_out=true if intent is to stop, pause, skip remaining questions, or end chat.
+2) Mark is_opt_out=false if "stop" is about symptoms, pain, bleeding, cough, fever, or any medical condition.
+3) Mark is_opt_out=false for normal medical responses and clarifications.
+4) Be language-agnostic and handle Hindi, Hinglish, Tamil, Telugu, Bengali, Marathi, Kannada, English.
+5) If ambiguous, choose false unless the stop intent is reasonably clear.
+6) confidence must be between 0 and 1.
+
+Positive examples:
+- "stop"
+- "bas karo"
+- "i don't want to answer more"
+- "enough questions"
+- "ruk jaiye"
+- "வேண்டாம், இப்போ நிறுத்துங்க"
+
+Negative examples:
+- "my fever stopped yesterday"
+- "pain stopped after medicine"
+- "when will this bleeding stop?"
+- "can we stop this medicine?"
+
+Return strict JSON only:
+{
+  "is_opt_out": true,
+  "confidence": 0.0,
+  "reason": "short explanation"
+}
```

## Unit tests
```diff
+def test_detect_patient_opt_out_returns_structured_response(monkeypatch: pytest.MonkeyPatch) -> None:
+    client = OpenAIQuestionClient()
+    monkeypatch.setattr(
+        client,
+        "_chat_completion",
+        lambda **_: json.dumps({"is_opt_out": True, "confidence": 0.91, "reason": "patient asked to stop"}),
+    )
+
+    result = client.detect_patient_opt_out(message_text="please stop now", language="en")
+
+    assert result["is_opt_out"] is True
+    assert result["confidence"] == pytest.approx(0.91)
+    assert result["reason"] == "patient asked to stop"
+
+def test_detect_patient_opt_out_raises_for_invalid_schema(monkeypatch: pytest.MonkeyPatch) -> None:
+    client = OpenAIQuestionClient()
+    monkeypatch.setattr(
+        client,
+        "_chat_completion",
+        lambda **_: json.dumps({"is_opt_out": "yes", "confidence": 0.5, "reason": "bad"}),
+    )
+
+    with pytest.raises(RuntimeError, match="opt_out_detection_schema_invalid"):
+        client.detect_patient_opt_out(message_text="stop", language="en")
```

```diff
+def test_stop_request_detects_english_and_hindi_variants() -> None:
+    service = _build_service()
+
+    assert service._is_stop_request("stop") is True
+    assert service._is_stop_request("please stop") is True
+    assert service._is_stop_request("रुकना") is True
+    assert service._is_stop_request("நிறுத்து") is True
+    assert service._is_stop_request("बंद करो") is True
+    assert service._is_stop_request("नிறுத்துங்கள்") is True
+    assert service._is_stop_request("ఆపు") is True
+    assert service._is_stop_request("ఆపండి") is True
+    assert service._is_stop_request("বন্ধ") is True
+    assert service._is_stop_request("বন্ধ করুন") is True
+    assert service._is_stop_request("थांब") is True
+    assert service._is_stop_request("थांबा") is True
+    assert service._is_stop_request("ನಿಲ್ಲಿಸು") is True
+    assert service._is_stop_request("ನಿಲ್ಲಿಸಿ") is True
+    assert service._is_stop_request("continue") is False
+
+def test_stop_confirmation_message_respects_language() -> None:
+    service = _build_service()
+
+    assert service._stop_confirmation_message("en") == "Thank you. We will continue with your submitted answers."
+    assert service._stop_confirmation_message("hi-eng") == "Dhanyavaad. Hum aapke diye gaye jawaabon ke saath aage badhenge."
+    assert service._stop_confirmation_message("hi") == "धन्यवाद। हम आपके दिए गए जवाबों के साथ आगे बढ़ेंगे।"
+
+def test_detect_stop_request_prefers_llm_when_model_flags_opt_out() -> None:
+    service = IntakeChatService.__new__(IntakeChatService)
+
+    class _FakeOpenAI:
+        @staticmethod
+        def detect_patient_opt_out(*, message_text: str, language: str, recent_answers: list[dict]) -> dict:
+            assert message_text == "i want to stop now"
+            assert language == "en"
+            assert isinstance(recent_answers, list)
+            return {"is_opt_out": True, "confidence": 0.9, "reason": "patient asked to stop"}
+
+    service.openai = _FakeOpenAI()
+    result = service._detect_stop_request(
+        message_text="i want to stop now",
+        language="en",
+        answers=[{"question": "illness", "answer": "fever"}],
+    )
+    assert result["detected"] is True
+    assert result["source"] == "llm"
+    assert result["confidence"] == 0.9
+
+def test_detect_stop_request_uses_keyword_fallback_when_llm_errors() -> None:
+    service = IntakeChatService.__new__(IntakeChatService)
+
+    class _FailingOpenAI:
+        @staticmethod
+        def detect_patient_opt_out(*, message_text: str, language: str, recent_answers: list[dict]) -> dict:
+            raise RuntimeError("network issue")
+
+    service.openai = _FailingOpenAI()
+    result = service._detect_stop_request(message_text="stop", language="en", answers=[])
+    assert result["detected"] is True
+    assert result["source"] == "keyword_fallback"
```

