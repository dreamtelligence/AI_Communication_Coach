from __future__ import annotations

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    scenario_id: str = Field(default="salary", min_length=1, max_length=64)
    practice_side: str | None = Field(default=None, max_length=64)
    sandbox: bool = False


class AnalyzeSessionRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=128)
    scenario_id: str = Field(default="salary", min_length=1, max_length=64)
    practice_side: str | None = Field(default=None, max_length=64)


class AnalysisResult(BaseModel):
    empathy_score: int = Field(ge=0, le=10)
    empathy_feedback: str
    clarity_score: int = Field(ge=0, le=10)
    clarity_feedback: str
    result_score: int = Field(ge=0, le=10)
    result_feedback: str
    summary: str
    transcript: str | None = None
    note: str | None = None
