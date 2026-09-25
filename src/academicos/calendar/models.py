from __future__ import annotations

from datetime import date, datetime, time
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceType(StrEnum):
    BRIGHTSPACE = "brightspace"
    EMAIL = "email"
    MANUAL = "manual"
    ZOOM = "zoom"
    LOCAL_FILE = "local_file"


class SessionType(StrEnum):
    LECTURE = "lecture"
    LAB = "lab"
    TUTORIAL = "tutorial"
    DGD = "dgd"
    OFFICE_HOUR = "office_hour"
    OTHER = "other"


class OverrideKind(StrEnum):
    CANCELLED = "cancelled"
    MOVED = "moved"
    LOCATION_CHANGED = "location_changed"
    MODE_CHANGED = "mode_changed"


class EventKind(StrEnum):
    CLASS_CANCELLED = "class_cancelled"
    CLASS_MOVED = "class_moved"
    CLASS_MODE_CHANGED = "class_mode_changed"
    DEADLINE_CREATED = "deadline_created"
    DEADLINE_CHANGED = "deadline_changed"
    EXAM_ANNOUNCED = "exam_announced"
    QUIZ_ANNOUNCED = "quiz_announced"
    NEW_MATERIAL = "new_material"
    SUGGESTED_TASK = "suggested_task"


class CandidateStatus(StrEnum):
    PENDING = "pending"
    AUTO_ACCEPTED = "auto_accepted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class PlanBlockState(StrEnum):
    PLANNED = "planned"
    STARTED = "started"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Course(FrozenModel):
    id: str
    code: str
    name: str
    term: str
    section: str | None = None


class SourceItem(FrozenModel):
    id: str
    source_type: SourceType
    source_id: str
    course_id: str | None = None
    source_url: str | None = None
    source_timestamp: datetime | None = None
    fetched_at: datetime
    content_hash: str
    raw_text: str | None = None
    raw_json: dict[str, Any] | None = None


class Evidence(FrozenModel):
    id: str
    source_item_id: str
    excerpt: str
    field_path: str | None = None


class RecurringSession(FrozenModel):
    id: str
    course_id: str
    session_type: SessionType
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    start_date: date
    end_date: date
    location: str | None = None
    delivery_mode: str | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "RecurringSession":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class EventOverride(FrozenModel):
    id: str
    session_id: str
    effective_date: date
    kind: OverrideKind
    new_start_at: datetime | None = None
    new_end_at: datetime | None = None
    new_location: str | None = None
    new_delivery_mode: str | None = None
    candidate_event_id: str | None = None


class CandidateEvent(FrozenModel):
    id: str
    kind: EventKind
    course_id: str | None = None
    target_ref: str | None = None
    effective_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    status: CandidateStatus = CandidateStatus.PENDING


class Task(FrozenModel):
    id: str
    course_id: str | None = None
    title: str
    task_type: str
    due_at: datetime | None = None
    initial_estimate_minutes: int = Field(default=0, ge=0)
    remaining_minutes: int = Field(default=0, ge=0)
    actual_spent_minutes: int = Field(default=0, ge=0)
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    status: TaskStatus = TaskStatus.PENDING
    origin_candidate_event_id: str | None = None


class PlanBlock(FrozenModel):
    id: str
    task_id: str
    start_at: datetime
    end_at: datetime
    state: PlanBlockState = PlanBlockState.PLANNED
    pinned: bool = False
    planner_run_id: str | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "PlanBlock":
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self
