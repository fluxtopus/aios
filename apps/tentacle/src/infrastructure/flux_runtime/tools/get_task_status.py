"""Tool for checking the status of tasks.

Allows users to query the status of active and completed tasks
from Arrow chat.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import structlog

from src.application.checkpoints import CheckpointUseCases
from src.application.tasks import TaskUseCases
from src.application.tasks.providers import (
    get_checkpoint_use_cases as provider_get_checkpoint_use_cases,
    get_task_use_cases as provider_get_task_use_cases,
)
from .base import BaseTool, ToolDefinition, ToolResult

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


class GetTaskStatusTool(BaseTool):
    """Get the current status of tasks.

    This tool allows users to check on the progress of their
    background tasks and see pending checkpoints.
    """

    @property
    def name(self) -> str:
        return "get_task_status"

    @property
    def description(self) -> str:
        return """Get the current status of one or more tasks.

Use this to:
- Check the progress of a specific task
- List all active tasks
- See pending checkpoints that need approval
- View recently completed tasks

If no task_id is provided, shows all active tasks and pending checkpoints."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters={
                "type": "object",
                "properties": {
                    "plan_id": {
                        "type": "string",
                        "description": "Specific plan/task ID to check. If omitted, returns all active tasks.",
                    },
                    "include_completed": {
                        "type": "boolean",
                        "description": "Include recently completed tasks (default: false)",
                        "default": False,
                    },
                    "include_checkpoints": {
                        "type": "boolean",
                        "description": "Include pending checkpoint details (default: true)",
                        "default": True,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of tasks to return (default: 10)",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50,
                    },
                },
                "required": [],
            },
        )

    async def execute(
        self, arguments: Dict[str, Any], context: Dict[str, Any]
    ) -> ToolResult:
        """Get task status.

        Args:
            arguments: {
                "plan_id": str,  # Optional specific task ID
                "include_completed": bool,  # Include completed tasks
                "include_checkpoints": bool,  # Include checkpoint details
                "limit": int,  # Max tasks to return
            }
            context: {
                "user_id": str,  # User making the request
                "delegation_service": DelegationService,  # Injected service
            }

        Returns:
            ToolResult with task status information
        """
        plan_id = arguments.get("plan_id")
        include_completed = arguments.get("include_completed", False)
        include_checkpoints = arguments.get("include_checkpoints", True)
        limit = arguments.get("limit", 10)

        # Get required context
        user_id = context.get("user_id")
        delegation_service = context.get("delegation_service")
        task_use_cases = context.get("task_use_cases")
        checkpoint_use_cases = context.get("checkpoint_use_cases")

        if not user_id:
            return ToolResult(
                success=False,
                error="User context not available",
            )

        if not delegation_service and not task_use_cases:
            try:
                task_use_cases = await _get_task_use_cases()
            except Exception as exc:
                logger.warning("Failed to resolve task use cases", error=str(exc))

        if include_checkpoints and not delegation_service and not checkpoint_use_cases:
            try:
                checkpoint_use_cases = await _get_checkpoint_use_cases()
            except Exception as exc:
                logger.warning("Failed to resolve checkpoint use cases", error=str(exc))

        if not delegation_service and not task_use_cases:
            return ToolResult(
                success=False,
                error="Delegation service not available",
            )

        try:
            # If specific plan requested
            if plan_id:
                if delegation_service:
                    plan = await delegation_service.get_plan(plan_id)
                else:
                    plan = await task_use_cases.get_task(plan_id)

                if not plan:
                    return ToolResult(
                        success=False,
                        error=f"Task not found: {plan_id}",
                    )

                if plan.user_id != user_id:
                    return ToolResult(
                        success=False,
                        error="Access denied to this task",
                    )

                result_data = self._format_plan(plan)

                # Add checkpoint info if pending
                if include_checkpoints:
                    if delegation_service:
                        checkpoints = await delegation_service.get_pending_checkpoints(user_id)
                    elif checkpoint_use_cases:
                        checkpoints = await checkpoint_use_cases.list_pending_for_task(plan_id)
                    else:
                        checkpoints = []
                    plan_checkpoints = [
                        c
                        for c in checkpoints
                        if getattr(c, "plan_id", getattr(c, "task_id", None)) == plan_id
                    ]
                    if plan_checkpoints:
                        result_data["pending_checkpoints"] = [
                            self._format_checkpoint(c) for c in plan_checkpoints
                        ]

                status_value = self._status_value(getattr(plan, "status", None))
                return ToolResult(
                    success=True,
                    data=result_data,
                    message=f"Task '{plan.goal[:50]}...' is {status_value}",
                )

            # List all tasks
            from src.domain.tasks.models import TaskStatus

            # Get active tasks
            if delegation_service:
                active_plans = await delegation_service.get_user_plans(
                    user_id=user_id,
                    status=None,  # All statuses initially
                    limit=limit,
                )
            else:
                active_plans = await task_use_cases.list_tasks(
                    user_id=user_id,
                    status=None,
                    limit=limit,
                )

            # Filter to active statuses
            active_statuses = {
                TaskStatus.PLANNING,
                TaskStatus.READY,
                TaskStatus.EXECUTING,
                TaskStatus.CHECKPOINT,
            }
            active_status_values = {self._status_value(s) for s in active_statuses}
            terminal_status_values = {
                self._status_value(TaskStatus.COMPLETED),
                self._status_value(TaskStatus.FAILED),
                self._status_value(TaskStatus.CANCELLED),
            }

            active_tasks = [
                p
                for p in active_plans
                if self._status_value(getattr(p, "status", None)) in active_status_values
            ]
            completed_tasks = []

            if include_completed:
                completed_tasks = [
                    p for p in active_plans
                    if self._status_value(getattr(p, "status", None)) in terminal_status_values
                ][:5]  # Limit completed to 5

            # Get pending checkpoints
            pending_checkpoints = []
            if include_checkpoints:
                if delegation_service:
                    checkpoints = await delegation_service.get_pending_checkpoints(user_id)
                elif checkpoint_use_cases:
                    checkpoints = await checkpoint_use_cases.list_pending(user_id)
                else:
                    checkpoints = []
                pending_checkpoints = [self._format_checkpoint(c) for c in checkpoints]

            result_data = {
                "active_tasks": [self._format_plan(p) for p in active_tasks],
                "active_count": len(active_tasks),
            }

            if include_completed:
                result_data["completed_tasks"] = [
                    self._format_plan(p) for p in completed_tasks
                ]
                result_data["completed_count"] = len(completed_tasks)

            if include_checkpoints:
                result_data["pending_checkpoints"] = pending_checkpoints
                result_data["checkpoint_count"] = len(pending_checkpoints)

            # Build summary message
            summary_parts = []
            if active_tasks:
                summary_parts.append(f"{len(active_tasks)} active task(s)")
            if pending_checkpoints:
                summary_parts.append(f"{len(pending_checkpoints)} checkpoint(s) pending approval")
            if completed_tasks:
                summary_parts.append(f"{len(completed_tasks)} recently completed")

            if not summary_parts:
                message = "No active tasks"
            else:
                message = ", ".join(summary_parts)

            return ToolResult(
                success=True,
                data=result_data,
                message=message,
            )

        except Exception as e:
            logger.error(
                "Failed to get task status",
                error=str(e),
                plan_id=plan_id,
            )
            return ToolResult(
                success=False,
                error=f"Failed to get task status: {str(e)}",
            )

    def _format_plan(self, plan) -> Dict[str, Any]:
        """Format a plan for display."""
        steps = getattr(plan, "steps", []) or []
        completed_steps = sum(
            1 for s in steps if self._status_value(getattr(s, "status", None)) in {"done", "completed"}
        )
        failed_steps = sum(
            1 for s in steps if self._status_value(getattr(s, "status", None)) == "failed"
        )
        status_value = self._status_value(getattr(plan, "status", None))

        progress = 0.0
        try:
            progress = float(plan.get_progress_percentage())
        except Exception:
            if steps:
                progress = round((completed_steps / len(steps)) * 100, 2)

        return {
            "plan_id": plan.id,
            "goal": plan.goal,
            "status": status_value,
            "progress": progress,
            "steps_total": len(steps),
            "steps_completed": completed_steps,
            "steps_failed": failed_steps,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
        }

    def _format_checkpoint(self, checkpoint) -> Dict[str, Any]:
        """Format a checkpoint for display."""
        return {
            "plan_id": getattr(checkpoint, "plan_id", getattr(checkpoint, "task_id", None)),
            "step_id": checkpoint.step_id,
            "name": checkpoint.checkpoint_name,
            "description": checkpoint.description,
            "preview": checkpoint.preview_data,
            "created_at": checkpoint.created_at.isoformat() if checkpoint.created_at else None,
            "expires_at": checkpoint.expires_at.isoformat() if checkpoint.expires_at else None,
        }

    @staticmethod
    def _status_value(status: Any) -> str:
        raw = getattr(status, "value", status)
        return str(raw).lower() if raw is not None else "unknown"
