"""Unit tests for InboxCreateTaskTool waiting behavior."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.domain.checkpoints import CheckpointDecision, CheckpointState, CheckpointType
from src.domain.tasks.models import StepStatus, TaskStatus
from src.infrastructure.inbox.tools.create_task import InboxCreateTaskTool


@pytest.fixture
def tool() -> InboxCreateTaskTool:
    return InboxCreateTaskTool()


@pytest.fixture
def valid_context() -> dict:
    return {
        "user_id": "user-123",
        "organization_id": "org-123",
        "conversation_id": "conv-123",
    }


def _task_snapshot(status: TaskStatus, steps: list[StepStatus] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id="task-123",
        status=status,
        steps=[SimpleNamespace(status=s) for s in (steps or [])],
        user_id="user-123",
    )


class TestToolDefinition:
    def test_definition_includes_wait_parameters(self, tool: InboxCreateTaskTool) -> None:
        definition = tool.get_definition()
        props = definition.parameters["properties"]

        assert "wait_for_completion" in props
        assert "wait_timeout_seconds" in props
        assert props["wait_for_completion"]["default"] is True


class TestExecute:
    @pytest.mark.asyncio
    async def test_requires_user_and_conversation(self, tool: InboxCreateTaskTool) -> None:
        result = await tool.execute({"goal": "Research agent patterns"}, {"organization_id": "org"})
        assert result.success is False
        assert "user_id or conversation_id" in (result.error or "")

    @pytest.mark.asyncio
    async def test_wait_returns_terminal_completion(
        self, tool: InboxCreateTaskTool, valid_context: dict,
    ) -> None:
        mock_task_use_cases = AsyncMock()
        mock_task_use_cases.create_task = AsyncMock(return_value=SimpleNamespace(id="task-123"))
        mock_task_use_cases.link_conversation = AsyncMock()
        mock_task_use_cases.get_task = AsyncMock(
            return_value=_task_snapshot(
                status=TaskStatus.COMPLETED,
                steps=[StepStatus.DONE, StepStatus.DONE],
            )
        )

        with patch(
            "src.infrastructure.inbox.tools.create_task._get_task_use_cases",
            new=AsyncMock(return_value=mock_task_use_cases),
        ):
            result = await tool.execute(
                {
                    "goal": "Research agent patterns",
                    "wait_for_completion": True,
                    "wait_timeout_seconds": 5,
                },
                valid_context,
            )

        assert result.success is True
        assert result.data["status"] == "completed"
        assert result.data["steps_total"] == 2
        assert result.data["steps_completed"] == 2
        assert result.data["timed_out"] is False
        mock_task_use_cases.link_conversation.assert_awaited_once_with(
            task_id="task-123",
            conversation_id="conv-123",
        )

    @pytest.mark.asyncio
    async def test_wait_timeout_returns_running(
        self, tool: InboxCreateTaskTool, valid_context: dict,
    ) -> None:
        mock_task_use_cases = AsyncMock()
        mock_task_use_cases.create_task = AsyncMock(return_value=SimpleNamespace(id="task-123"))
        mock_task_use_cases.link_conversation = AsyncMock()
        mock_task_use_cases.get_task = AsyncMock(
            return_value=_task_snapshot(
                status=TaskStatus.PLANNING,
                steps=[StepStatus.PENDING],
            )
        )

        with patch(
            "src.infrastructure.inbox.tools.create_task._get_task_use_cases",
            new=AsyncMock(return_value=mock_task_use_cases),
        ):
            result = await tool.execute(
                {
                    "goal": "Research agent patterns",
                    "wait_for_completion": True,
                    "wait_timeout_seconds": 0,
                },
                valid_context,
            )

        assert result.success is True
        assert result.data["status"] == "running"
        assert result.data["current_status"] == "planning"
        assert result.data["timed_out"] is True

    @pytest.mark.asyncio
    async def test_checkpoint_status_includes_pending_checkpoint_data(
        self, tool: InboxCreateTaskTool, valid_context: dict,
    ) -> None:
        mock_task_use_cases = AsyncMock()
        mock_task_use_cases.create_task = AsyncMock(return_value=SimpleNamespace(id="task-123"))
        mock_task_use_cases.link_conversation = AsyncMock()
        mock_task_use_cases.get_task = AsyncMock(
            return_value=_task_snapshot(
                status=TaskStatus.CHECKPOINT,
                steps=[StepStatus.CHECKPOINT],
            )
        )

        checkpoint = CheckpointState(
            plan_id="task-123",
            step_id="step-approval",
            checkpoint_name="approval",
            description="Need approval",
            decision=CheckpointDecision.PENDING,
            preview_data={"risk": "high"},
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=30),
            checkpoint_type=CheckpointType.APPROVAL,
        )
        mock_checkpoint_use_cases = AsyncMock()
        mock_checkpoint_use_cases.list_pending_for_task = AsyncMock(return_value=[checkpoint])

        with patch(
            "src.infrastructure.inbox.tools.create_task._get_task_use_cases",
            new=AsyncMock(return_value=mock_task_use_cases),
        ), patch(
            "src.infrastructure.inbox.tools.create_task._get_checkpoint_use_cases",
            new=AsyncMock(return_value=mock_checkpoint_use_cases),
        ):
            result = await tool.execute(
                {
                    "goal": "Research agent patterns",
                    "wait_for_completion": True,
                    "wait_timeout_seconds": 5,
                },
                valid_context,
            )

        assert result.success is True
        assert result.data["status"] == "checkpoint"
        assert result.data["checkpoint"]["step_id"] == "step-approval"
        assert result.data["checkpoint"]["checkpoint_type"] == "approval"

    @pytest.mark.asyncio
    async def test_wait_disabled_returns_planning_without_polling(
        self, tool: InboxCreateTaskTool, valid_context: dict,
    ) -> None:
        mock_task_use_cases = AsyncMock()
        mock_task_use_cases.create_task = AsyncMock(return_value=SimpleNamespace(id="task-123"))
        mock_task_use_cases.link_conversation = AsyncMock()
        mock_task_use_cases.get_task = AsyncMock()

        with patch(
            "src.infrastructure.inbox.tools.create_task._get_task_use_cases",
            new=AsyncMock(return_value=mock_task_use_cases),
        ):
            result = await tool.execute(
                {
                    "goal": "Research agent patterns",
                    "wait_for_completion": False,
                },
                valid_context,
            )

        assert result.success is True
        assert result.data["status"] == "planning"
        mock_task_use_cases.get_task.assert_not_called()
