"""Unit tests for GetTaskStatusTool inbox fallback wiring."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.domain.tasks.models import StepStatus, TaskStatus
from src.infrastructure.flux_runtime.tools.get_task_status import GetTaskStatusTool


def _task(task_id: str, user_id: str, status: TaskStatus, steps: list[StepStatus]) -> SimpleNamespace:
    return SimpleNamespace(
        id=task_id,
        user_id=user_id,
        goal=f"Goal for {task_id}",
        status=status,
        steps=[SimpleNamespace(status=s) for s in steps],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        get_progress_percentage=lambda: 50.0,
    )


def _checkpoint(task_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        plan_id=task_id,
        step_id="step-1",
        checkpoint_name="approval",
        description="Review required",
        preview_data={"risk": "high"},
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    )


@pytest.fixture
def tool() -> GetTaskStatusTool:
    return GetTaskStatusTool()


@pytest.mark.asyncio
async def test_specific_task_uses_inbox_fallback_context(tool: GetTaskStatusTool) -> None:
    task_use_cases = AsyncMock()
    checkpoint_use_cases = AsyncMock()
    task_use_cases.get_task = AsyncMock(
        return_value=_task("task-1", "user-1", TaskStatus.PLANNING, [StepStatus.PENDING])
    )
    checkpoint_use_cases.list_pending_for_task = AsyncMock(return_value=[_checkpoint("task-1")])

    result = await tool.execute(
        {"plan_id": "task-1", "include_checkpoints": True},
        {
            "user_id": "user-1",
            "task_use_cases": task_use_cases,
            "checkpoint_use_cases": checkpoint_use_cases,
        },
    )

    assert result.success is True
    assert result.data["plan_id"] == "task-1"
    assert result.data["status"] == "planning"
    assert result.data["pending_checkpoints"][0]["step_id"] == "step-1"


@pytest.mark.asyncio
async def test_list_tasks_uses_inbox_fallback_context(tool: GetTaskStatusTool) -> None:
    task_use_cases = AsyncMock()
    checkpoint_use_cases = AsyncMock()
    task_use_cases.list_tasks = AsyncMock(
        return_value=[
            _task("task-active", "user-1", TaskStatus.PLANNING, [StepStatus.PENDING]),
            _task("task-done", "user-1", TaskStatus.COMPLETED, [StepStatus.DONE]),
        ]
    )
    checkpoint_use_cases.list_pending = AsyncMock(return_value=[_checkpoint("task-active")])

    result = await tool.execute(
        {
            "include_completed": True,
            "include_checkpoints": True,
            "limit": 10,
        },
        {
            "user_id": "user-1",
            "task_use_cases": task_use_cases,
            "checkpoint_use_cases": checkpoint_use_cases,
        },
    )

    assert result.success is True
    assert result.data["active_count"] == 1
    assert result.data["completed_count"] == 1
    assert result.data["checkpoint_count"] == 1
