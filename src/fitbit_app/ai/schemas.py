"""Structured outputs the model must return (sent to Ollama as JSON schema)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TipCategory = Literal["sleep", "training", "recovery", "stress", "activity", "health"]


class Tip(BaseModel):
    title: str = Field(max_length=80, description="Short imperative, e.g. 'Keep today easy'")
    detail: str = Field(max_length=400, description="One or two sentences, citing the data")
    category: TipCategory


class DailyBrief(BaseModel):
    headline: str = Field(max_length=120, description="One sentence: how the body looks today")
    summary: str = Field(max_length=900, description="3-5 sentences using only the given numbers")
    tips: list[Tip] = Field(min_length=1, max_length=3)


class WeeklyReview(BaseModel):
    headline: str = Field(max_length=120)
    summary: str = Field(max_length=1200, description="How this week compared with the last")
    wins: list[str] = Field(max_length=3, description="Things that went well")
    watch: list[str] = Field(max_length=3, description="Things to keep an eye on")
    focus: str = Field(max_length=300, description="One concrete focus for next week")


class AnomalyNote(BaseModel):
    headline: str = Field(max_length=120)
    explanation: str = Field(max_length=900, description="What the unusual signals could mean")
    suggestions: list[str] = Field(min_length=1, max_length=3)
    see_doctor_if: str = Field(
        max_length=300, description="When it would be sensible to talk to a doctor"
    )


INSIGHT_SCHEMAS: dict[str, type[BaseModel]] = {
    "daily_brief": DailyBrief,
    "weekly_review": WeeklyReview,
    "anomaly": AnomalyNote,
}
