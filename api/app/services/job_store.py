from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import uuid

from app.models import AgentSearchResponse


@dataclass
class JobRecord:
    id: str
    status: str = "running"
    progress: int = 0
    message: str = "Starting job"
    result: AgentSearchResponse | None = None
    error: str | None = None
    task: asyncio.Task | None = field(default=None, repr=False)


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}

    def create(self, message: str) -> JobRecord:
        record = JobRecord(id=uuid.uuid4().hex, message=message)
        self._jobs[record.id] = record
        return record

    def get(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    def set_task(self, job_id: str, task: asyncio.Task) -> None:
        self._jobs[job_id].task = task

    def update(self, job_id: str, *, progress: int | None = None, message: str | None = None) -> None:
        record = self._jobs[job_id]
        if progress is not None:
            record.progress = max(0, min(100, progress))
        if message is not None:
            record.message = message

    def complete(self, job_id: str, result: AgentSearchResponse) -> None:
        record = self._jobs[job_id]
        record.status = "completed"
        record.progress = 100
        record.message = "Completed"
        record.result = result

    def fail(self, job_id: str, error: str) -> None:
        record = self._jobs[job_id]
        record.status = "failed"
        record.error = error
        record.message = error
