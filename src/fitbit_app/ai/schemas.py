"""Structured outputs the model must return (sent to Ollama as JSON schema).

Some models (e.g. qwen3.5 with thinking off) ignore Ollama's schema enforcement and return
free-form JSON. The validators below are lenient where that is harmless: over-long text is
shortened, extra list items dropped, and category labels normalized. Missing fields still fail.
"""

from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, BeforeValidator, Field

TipCategory = Literal["sleep", "training", "recovery", "stress", "activity", "health"]
TIP_CATEGORIES: tuple[str, ...] = get_args(TipCategory)


def _clip_text(limit: int) -> BeforeValidator:
    def clip(value: Any) -> Any:
        if not isinstance(value, str) or len(value) <= limit:
            return value
        cut = value[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:")
        return cut + "…"

    return BeforeValidator(clip)


def _clip_list(limit: int) -> BeforeValidator:
    return BeforeValidator(lambda value: value[:limit] if isinstance(value, list) else value)


def _normalize_category(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    label = value.strip().lower()
    return label if label in TIP_CATEGORIES else "health"


Title = Annotated[str, _clip_text(80), Field(max_length=80)]
Headline = Annotated[str, _clip_text(160), Field(max_length=160)]
Sentence = Annotated[str, _clip_text(300), Field(max_length=300)]
Detail = Annotated[str, _clip_text(400), Field(max_length=400)]
Paragraph = Annotated[str, _clip_text(1500), Field(max_length=1500)]
Category = Annotated[TipCategory, BeforeValidator(_normalize_category)]


class Tip(BaseModel):
    title: Title = Field(description="Short imperative, e.g. 'Keep today easy'")
    detail: Detail = Field(description="One or two sentences, citing the data")
    category: Category


class DailyBrief(BaseModel):
    headline: Headline = Field(description="One sentence: how the body looks today")
    summary: Paragraph = Field(description="3-5 sentences using only the given numbers")
    tips: Annotated[list[Tip], _clip_list(3), Field(min_length=1, max_length=3)]


class WeeklyReview(BaseModel):
    headline: Headline
    summary: Paragraph = Field(description="How this week compared with the last")
    wins: Annotated[list[Sentence], _clip_list(3), Field(max_length=3)]
    watch: Annotated[list[Sentence], _clip_list(3), Field(max_length=3)]
    focus: Detail = Field(description="One concrete focus for next week")


class AnomalyNote(BaseModel):
    headline: Headline
    explanation: Paragraph = Field(description="What the unusual signals could mean")
    suggestions: Annotated[list[Sentence], _clip_list(3), Field(min_length=1, max_length=3)]
    see_doctor_if: Detail = Field(description="When it would be sensible to talk to a doctor")


INSIGHT_SCHEMAS: dict[str, type[BaseModel]] = {
    "daily_brief": DailyBrief,
    "weekly_review": WeeklyReview,
    "anomaly": AnomalyNote,
}
