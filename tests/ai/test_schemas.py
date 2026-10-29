import pytest
from pydantic import ValidationError

from fitbit_app.ai.client import describe_errors, extract_json
from fitbit_app.ai.schemas import AnomalyNote, DailyBrief, WeeklyReview

# Real shape returned by qwen3.5:9b with thinking off (dummy beach prompt, 2026-10-29):
# fenced in markdown and with categories outside the allowed list.
FENCED_REPLY = """```json
{
  "headline": "Golden Waves: A Perfect Sunny Day at the Beach",
  "summary": "Under a brilliant blue sky, golden sunlight dances on gentle waves.",
  "tips": [
    {"title": "Sun Protection", "detail": "Apply sunscreen every two hours.", "category": "Safety"},
    {"title": "Hydration Station", "detail": "Carry a water bottle.", "category": "Health"},
    {"title": "Gear Up Early", "detail": "Arrive before the crowds.", "category": "Planning"}
  ]
}
```"""


def test_fenced_reply_with_unknown_categories_is_accepted() -> None:
    brief = DailyBrief.model_validate_json(extract_json(FENCED_REPLY))
    assert brief.headline.startswith("Golden Waves")
    assert [t.category for t in brief.tips] == ["health", "health", "health"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"a": 1}', '{"a": 1}'),
        ('```json\n{"a": 1}\n```', '{"a": 1}'),
        ('```\n{"a": 1}\n```', '{"a": 1}'),
        ('Sure! Here it is: {"a": {"b": 2}} Hope that helps.', '{"a": {"b": 2}}'),
        ("no json here", "no json here"),
    ],
)
def test_extract_json(text: str, expected: str) -> None:
    assert extract_json(text) == expected


def test_known_categories_are_normalized() -> None:
    tip = {"title": "t", "detail": "d", "category": "  Training "}
    brief = DailyBrief.model_validate({"headline": "h", "summary": "s", "tips": [tip]})
    assert brief.tips[0].category == "training"


def test_over_long_text_is_shortened_not_rejected() -> None:
    long_summary = "word " * 600
    brief = DailyBrief.model_validate(
        {
            "headline": "h",
            "summary": long_summary,
            "tips": [{"title": "t", "detail": "d", "category": "sleep"}],
        }
    )
    assert len(brief.summary) <= 1500
    assert brief.summary.endswith("…")


def test_extra_list_items_are_dropped() -> None:
    tips = [{"title": f"t{i}", "detail": "d", "category": "sleep"} for i in range(5)]
    brief = DailyBrief.model_validate({"headline": "h", "summary": "s", "tips": tips})
    assert [t.title for t in brief.tips] == ["t0", "t1", "t2"]
    review = WeeklyReview.model_validate(
        {"headline": "h", "summary": "s", "wins": list("abcde"), "watch": [], "focus": "f"}
    )
    assert review.wins == ["a", "b", "c"]


def test_missing_fields_still_fail() -> None:
    with pytest.raises(ValidationError) as info:
        DailyBrief.model_validate_json('{"brief": {"headline": "h"}}')
    described = describe_errors(info.value)
    assert "headline:missing" in described
    assert "tips:missing" in described


def test_anomaly_needs_a_suggestion() -> None:
    with pytest.raises(ValidationError):
        AnomalyNote.model_validate(
            {"headline": "h", "explanation": "e", "suggestions": [], "see_doctor_if": "x"}
        )


def test_schema_still_advertises_limits_to_ollama() -> None:
    schema = DailyBrief.model_json_schema()
    assert schema["properties"]["summary"]["maxLength"] == 1500
    assert set(schema["$defs"]["Tip"]["properties"]["category"]["enum"]) == {
        "sleep",
        "training",
        "recovery",
        "stress",
        "activity",
        "health",
    }
