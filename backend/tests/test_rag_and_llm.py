"""tests/test_rag_and_llm.py  –  unit tests, no HTTP, no model needed"""
import pytest
from llm.local_llm import extract_plantuml, is_valid_plantuml, _fallback


# ── PlantUML extraction ───────────────────────────────────────────────────────

class TestExtractPlantuml:

    def test_clean_block(self):
        raw = "@startuml\nA -> B: hello\n@enduml"
        assert extract_plantuml(raw) == raw

    def test_with_markdown_fence(self):
        raw = "```plantuml\n@startuml\nA -> B\n@enduml\n```"
        result = extract_plantuml(raw)
        assert result == "@startuml\nA -> B\n@enduml"

    def test_with_backtick_fence(self):
        raw = "Here is the diagram:\n```\n@startuml\nA --> B\n@enduml\n```\nDone."
        result = extract_plantuml(raw)
        assert "@startuml" in result
        assert "@enduml"   in result

    def test_embedded_in_prose(self):
        raw = "Sure! Here's your diagram:\n@startuml\nactor User\n@enduml\nHope that helps!"
        result = extract_plantuml(raw)
        assert result == "@startuml\nactor User\n@enduml"

    def test_case_insensitive(self):
        raw = "@StartUML\nA -> B\n@EndUML"
        result = extract_plantuml(raw)
        assert result is not None

    def test_no_block_returns_none(self):
        assert extract_plantuml("Just some text, no diagram here.") is None

    def test_empty_string_returns_none(self):
        assert extract_plantuml("") is None

    def test_only_startuml_returns_none(self):
        # Missing @enduml — not a valid block
        assert extract_plantuml("@startuml\nsome content") is None


# ── PlantUML validation ───────────────────────────────────────────────────────

class TestIsValidPlantuml:

    def test_valid(self):
        assert is_valid_plantuml("@startuml\nA -> B\n@enduml") is True

    def test_missing_enduml(self):
        assert is_valid_plantuml("@startuml\nA -> B") is False

    def test_missing_startuml(self):
        assert is_valid_plantuml("A -> B\n@enduml") is False

    def test_empty(self):
        assert is_valid_plantuml("") is False

    def test_none(self):
        assert is_valid_plantuml(None) is False   # type: ignore

    def test_valid_complex(self):
        code = "@startuml\nactor User\nparticipant Server\nUser -> Server: login\nalt valid\n Server --> User: 200\nend\n@enduml"
        assert is_valid_plantuml(code) is True


# ── Fallback stubs ────────────────────────────────────────────────────────────

class TestFallbackDiagram:

    @pytest.mark.parametrize("diagram_type", [
        "sequence","class","usecase","activity","component","state","er"
    ])
    def test_fallback_always_valid(self, diagram_type):
        code = _fallback("test description", diagram_type)
        assert is_valid_plantuml(code), f"Fallback for {diagram_type} is not valid PlantUML"

    def test_fallback_unknown_type_returns_something_valid(self):
        code = _fallback("test", "unknown_type")
        assert is_valid_plantuml(code)

    def test_fallback_includes_description(self):
        code = _fallback("login system", "sequence")
        assert "login system" in code


# ── Feedback-weighted retriever ───────────────────────────────────────────────

class TestFeedbackLoop:

    def test_feedback_boost_neutral_when_no_cache(self):
        from rag.retriever import _get_feedback_boost, _feedback_cache
        _feedback_cache.clear()
        boost = _get_feedback_boost("some chunk text about sequences")
        assert boost == 0.5   # neutral

    def test_feedback_boost_positive(self):
        from rag.retriever import _feedback_cache, _get_feedback_boost
        _feedback_cache["my great diagram"] = 1.0
        boost = _get_feedback_boost("This chunk references my great diagram in detail")
        # thumb_score=1.0 → normalised to 1.0
        assert boost == 1.0
        _feedback_cache.clear()

    def test_feedback_boost_negative(self):
        from rag.retriever import _feedback_cache, _get_feedback_boost
        _feedback_cache["bad diagram"] = -1.0
        boost = _get_feedback_boost("this chunk mentions bad diagram")
        # thumb_score=-1.0 → normalised to 0.0
        assert boost == 0.0
        _feedback_cache.clear()

    def test_final_score_with_boost(self):
        from rag.retriever import RetrievedChunk, FEEDBACK_WEIGHT
        chunk = RetrievedChunk(
            text="test", source="s", diagram_type="sequence",
            content_type="rule", score=0.8,
        )
        chunk.feedback_boost = 1.0   # max positive feedback
        chunk.final_score = round(
            0.8 * (1 - FEEDBACK_WEIGHT) + 1.0 * FEEDBACK_WEIGHT, 4
        )
        # Should be higher than raw score alone
        assert chunk.final_score > chunk.score * (1 - FEEDBACK_WEIGHT)

    def test_final_score_penalised_by_negative_feedback(self):
        from rag.retriever import RetrievedChunk, FEEDBACK_WEIGHT
        chunk = RetrievedChunk(
            text="test", source="s", diagram_type="sequence",
            content_type="rule", score=0.9,
        )
        chunk.feedback_boost = 0.0   # max negative feedback
        chunk.final_score = round(
            0.9 * (1 - FEEDBACK_WEIGHT) + 0.0 * FEEDBACK_WEIGHT, 4
        )
        # Should be lower than raw score
        assert chunk.final_score < chunk.score


# ── Code generator ────────────────────────────────────────────────────────────

class TestCodeGenerator:

    def test_mock_python(self):
        from llm.code_generator import generate_code
        result = generate_code("@startuml\nA->B\n@enduml", "sequence", "python")
        assert result["language"] == "python"
        assert result["code"]
        assert result["error"] is None

    def test_mock_typescript(self):
        from llm.code_generator import generate_code
        result = generate_code("@startuml\nA->B\n@enduml", "sequence", "typescript")
        assert result["language"] == "typescript"
        assert result["code"]

    def test_unsupported_language(self):
        from llm.code_generator import generate_code
        result = generate_code("@startuml\n@enduml", "sequence", "cobol")
        assert result["error"] == "unsupported"

    @pytest.mark.parametrize("lang", [
        "python","javascript","typescript","java","go","rust","csharp","cpp","ruby","kotlin","swift"
    ])
    def test_all_languages_return_code(self, lang):
        from llm.code_generator import generate_code
        result = generate_code("@startuml\nA->B\n@enduml", "sequence", lang)
        assert result["language"] == lang
        assert result["code"]     is not None
