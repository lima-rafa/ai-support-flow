from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

Category = Literal['network','hardware','software','access','email','other']
Priority = Literal['low','medium','high','critical']
Impact = Literal['unknown','individual','partial','blocked','multiple','widespread']


class TicketCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=4, max_length=150)
    description: str = Field(min_length=10, max_length=5000)
    affected_service: str | None = Field(default=None, max_length=100)
    reported_impact: str | None = Field(default=None, max_length=1000)
    impact_scope: Impact = 'unknown'


class AnalysisOutput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    category: Category
    suggested_priority: Priority
    summary: str = Field(min_length=4, max_length=600)
    recommendations: list[str] = Field(min_length=1, max_length=5)
    review_reason: str = Field(max_length=300)


class AnalyzeRequest(BaseModel):
    event_id: str


class SyncRequest(BaseModel):
    event_id: str
    status: Literal['succeeded','failed']
    failure_stage: Literal['none','analysis','sync'] = 'none'
    error_code: str | None = Field(default=None, max_length=80)


class StatusChange(BaseModel):
    status: Literal['in_progress','resolved','closed']
    resolution_notes: str | None = Field(default=None, max_length=2000)
    reason: str | None = Field(default=None, max_length=300)


class PriorityReview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    priority: Priority
    reason: str = Field(min_length=8,max_length=300)
