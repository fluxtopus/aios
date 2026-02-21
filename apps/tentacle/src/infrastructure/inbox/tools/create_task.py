# REVIEW: The tool still builds metadata and linking logic inline. Consider
# REVIEW: promoting this into a dedicated application use case to keep inbox
# REVIEW: tools thin and to centralize task creation + conversation linkage.
"""Inbox tool: Create a background task within the current conversation."""

import asyncio
from time import monotonic
from typing import Any, Dict, Optional

import structlog

from src.core.config import settings
from src.application.checkpoints import CheckpointUseCases
from src.infrastructure.flux_runtime.tools.base import BaseTool, ToolDefinition, ToolResult
from src.application.tasks import TaskUseCases
from src.application.tasks.providers import (
    get_checkpoint_use_cases as provider_get_checkpoint_use_cases,
    get_task_use_cases as provider_get_task_use_cases,
)

logger = structlog.get_logger(__name__)

_task_use_cases: Optional[TaskUseCases] = None
_checkpoint_use_cases: Optional[CheckpointUseCases] = None


async def _get_task_use_cases() -> TaskUseCases:
    global _task_use_cases
    if _task_use_cases is None:
        _task_use_cases = await provider_get_task_use_cases()
    return _task_use_cases


async def _get_checkpoint_use_cases() -> CheckpointUseCases:
    global _checkpoint_use_cases
    if _checkpoint_use_cases is None:
        _checkpoint_use_cases = await provider_get_checkpoint_use_cases()
    return _checkpoint_use_cases


def _status_value(status: Any) -> str:
    raw = getattr(status, "value", status)
    return str(raw).lower() if raw is not None else "unknown"


def _safe_progress(task: Any, completed_steps: int, total_steps: int) -> float:
    try:
        return float(task.get_progress_percentage())
    except Exception:
        if total_steps <= 0:
            return 0.0
        return round((completed_steps / total_steps) * 100, 2)


def _summarize_task(task: Any) -> Dict[str, Any]:
    steps = getattr(task, "steps", None) or []
    total_steps = len(steps)
    completed_steps = 0
    failed_steps = 0

    for step in steps:
        step_status = _status_value(getattr(step, "status", None))
        if step_status in {"done", "completed"}:
            completed_steps += 1
        elif step_status == "failed":
            failed_steps += 1

    return {
        "steps_total": total_steps,
        "steps_completed": completed_steps,
        "steps_failed": failed_steps,
        "progress_percentage": _safe_progress(task, completed_steps, total_steps),
    }


def _serialize_checkpoint(checkpoint: Any) -> Dict[str, Any]:
    checkpoint_type = getattr(checkpoint, "checkpoint_type", None)
    checkpoint_type_value = getattr(checkpoint_type, "value", checkpoint_type) or "approval"
    return {
        "task_id": checkpoint.plan_id,
        "step_id": checkpoint.step_id,
        "checkpoint_name": checkpoint.checkpoint_name,
        "description": checkpoint.description,
        "checkpoint_type": checkpoint_type_value,
        "preview_data": checkpoint.preview_data,
        "questions": checkpoint.questions,
        "alternatives": checkpoint.alternatives,
        "created_at": checkpoint.created_at.isoformat() if checkpoint.created_at else None,
        "expires_at": checkpoint.expires_at.isoformat() if checkpoint.expires_at else None,
    }


def _resolve_wait_timeout(arguments: Dict[str, Any]) -> int:
    requested = arguments.get("wait_timeout_seconds")
    default_timeout = settings.INBOX_CREATE_TASK_WAIT_TIMEOUT_SECONDS
    max_timeout = settings.INBOX_CREATE_TASK_WAIT_MAX_TIMEOUT_SECONDS

    if requested is None:
        return max(0, min(default_timeout, max_timeout))

    try:
        timeout_int = int(requested)
    except (TypeError, ValueError):
        return max(0, min(default_timeout, max_timeout))

    return max(0, min(timeout_int, max_timeout))


async def _wait_for_terminal_status(
    task_use_cases: TaskUseCases,
    task_id: str,
    timeout_seconds: int,
) -> tuple[Optional[Any], str, bool]:
    terminal_statuses = {"completed", "failed", "cancelled", "checkpoint"}
    poll_interval = max(0.2, float(settings.INBOX_CREATE_TASK_WAIT_POLL_INTERVAL_SECONDS))
    deadline = monotonic() + max(0, timeout_seconds)

    last_task: Optional[Any] = None
    last_status = "planning"

    while True:
        try:
            task = await task_use_cases.get_task(task_id)
        except Exception as exc:
            logger.warning(
                "Failed to fetch task status while waiting",
                task_id=task_id,
                error=str(exc),
            )
            task = None
        if task is not None:
            last_task = task
            last_status = _status_value(getattr(task, "status", None))
            if last_status in terminal_statuses:
                return task, last_status, False

        if monotonic() >= deadline:
            return last_task, last_status, True

        remaining = deadline - monotonic()
        await asyncio.sleep(min(poll_interval, max(0.01, remaining)))


async def _get_pending_checkpoint(task_id: str) -> Optional[Dict[str, Any]]:
    checkpoint_use_cases = await _get_checkpoint_use_cases()
    pending = await checkpoint_use_cases.list_pending_for_task(task_id)
    if not pending:
        return None
    return _serialize_checkpoint(pending[0])


class InboxCreateTaskTool(BaseTool):
    """Create a background task and optionally wait for early completion."""

    @property
    def name(self) -> str:
        return "create_task"

    @property
    def description(self) -> str:
        return (
            "Start a background task. The task plans and executes autonomously, "
            "and can optionally wait briefly for a terminal result before returning."
        )

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters={
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": "Clear description of what the task should accomplish.",
                    },
                    "constraints": {
                        "type": "object",
                        "description": "Optional constraints (budget, time, etc.).",
                    },
                    "wait_for_completion": {
                        "type": "boolean",
                        "description": (
                            "If true, wait briefly for task terminal status "
                            "(completed/failed/checkpoint) before returning."
                        ),
                        "default": True,
                    },
                    "wait_timeout_seconds": {
                        "type": "integer",
                        "description": (
                            "Maximum wait time for terminal status. "
                            "If omitted, uses system default."
                        ),
                        "minimum": 0,
                        "maximum": settings.INBOX_CREATE_TASK_WAIT_MAX_TIMEOUT_SECONDS,
                    },
                },
                "required": ["goal"],
            },
        )

    async def execute(
        self, arguments: Dict[str, Any], context: Dict[str, Any]
    ) -> ToolResult:
        goal = arguments["goal"]
        constraints = arguments.get("constraints") or {}
        wait_for_completion = bool(arguments.get("wait_for_completion", True))
        wait_timeout_seconds = _resolve_wait_timeout(arguments)
        user_id = context.get("user_id")
        organization_id = context.get("organization_id", "")
        conversation_id = context.get("conversation_id")

        # Forward file references from chat context so the planner knows about attached files
        file_references = context.get("file_references")
        if file_references:
            constraints["file_references"] = file_references

        if not user_id or not conversation_id:
            return ToolResult(
                success=False,
                error="Missing user_id or conversation_id in context",
            )

        try:
            task_use_cases = await _get_task_use_cases()
            task = await task_use_cases.create_task(
                user_id=user_id,
                organization_id=organization_id,
                goal=goal,
                constraints=constraints or None,
                metadata={
                    "source": "inbox_chat",
                    "conversation_id": conversation_id,
                },
                auto_start=True,
            )

            await task_use_cases.link_conversation(
                task_id=task.id,
                conversation_id=conversation_id,
            )

            base_data: Dict[str, Any] = {
                "task_id": task.id,
                "goal": goal,
                "timed_out": False,
            }

            if not wait_for_completion:
                return ToolResult(
                    success=True,
                    data={
                        **base_data,
                        "status": "planning",
                    },
                    message=f"Task created and planning started: {goal}",
                )

            observed_task, observed_status, timed_out = await _wait_for_terminal_status(
                task_use_cases=task_use_cases,
                task_id=task.id,
                timeout_seconds=wait_timeout_seconds,
            )

            if observed_task is not None:
                base_data.update(_summarize_task(observed_task))

            if timed_out:
                return ToolResult(
                    success=True,
                    data={
                        **base_data,
                        "status": "running",
                        "current_status": observed_status,
                        "timed_out": True,
                        "wait_timeout_seconds": wait_timeout_seconds,
                    },
                    message=(
                        "Task started and is still running. "
                        "Use get_task_status for updates."
                    ),
                )

            if observed_status == "checkpoint":
                checkpoint_data = await _get_pending_checkpoint(task.id)
                return ToolResult(
                    success=True,
                    data={
                        **base_data,
                        "status": "checkpoint",
                        "checkpoint": checkpoint_data,
                    },
                    message="Task is waiting for your checkpoint approval.",
                )

            if observed_status in {"completed", "failed", "cancelled"}:
                return ToolResult(
                    success=True,
                    data={
                        **base_data,
                        "status": observed_status,
                    },
                    message=f"Task reached terminal status: {observed_status}.",
                )

            logger.info(
                "Inbox task created",
                task_id=task.id,
                conversation_id=conversation_id,
                goal=goal[:100],
            )

            return ToolResult(
                success=True,
                data={
                    **base_data,
                    "status": observed_status,
                },
                message="Task created and started.",
            )

        except Exception as e:
            logger.error("Failed to create inbox task", error=str(e))
            return ToolResult(
                success=False,
                error=f"Failed to create task: {str(e)}",
            )
