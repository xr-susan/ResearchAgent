"""
Task executor for ResearchAgent.

Manages asynchronous research tasks with status tracking,
progress reporting, and concurrent execution support.
"""

import asyncio
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from backend.agents.research_agent import ResearchAgent
from backend.memory.storage import StorageManager
from backend.utils.config import settings
from backend.utils.logger import get_logger

logger = get_logger("task_executor")


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskExecutor:
    """Manages and executes research tasks asynchronously.

    Supports:
    - Concurrent task execution with configurable limits
    - Task status tracking and progress reporting
    - Error handling and retry logic
    - Task cancellation
    """

    def __init__(self, storage: StorageManager, max_concurrent: int = 3):
        """Initialize task executor.

        Args:
            storage: Storage manager for task persistence.
            max_concurrent: Maximum concurrent task executions.
        """
        self.storage = storage
        self.max_concurrent = max_concurrent
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._progress_callbacks: dict[str, list[Callable]] = {}

    async def submit_task(
        self,
        title: str,
        task_type: str,
        params: dict[str, Any],
        conversation_id: Optional[str] = None,
    ) -> dict:
        """Submit a new research task for execution.

        Args:
            title: Task title.
            task_type: Type of task (research, analyze_file, generate_report).
            params: Task parameters.
            conversation_id: Optional conversation context.

        Returns:
            Created task record.
        """
        # Create task in storage
        task = await self.storage.create_task(
            title=title,
            description=f"Type: {task_type}",
            conversation_id=conversation_id,
            metadata={"type": task_type, "params": params},
        )

        # Start async execution
        asyncio.create_task(self._execute_task(task["id"], task_type, params))

        logger.info(f"Task submitted: {task['id']} - {title}")
        return task

    async def _execute_task(self, task_id: str, task_type: str, params: dict) -> None:
        """Execute a task with semaphore-controlled concurrency.

        Args:
            task_id: Task ID.
            task_type: Task type.
            params: Task parameters.
        """
        async with self._semaphore:
            await self._run_task(task_id, task_type, params)

    async def _run_task(self, task_id: str, task_type: str, params: dict) -> None:
        """Run the actual task logic.

        Args:
            task_id: Task ID.
            task_type: Task type.
            params: Task parameters.
        """
        # Update status to running
        await self.storage.update_task(
            task_id,
            status=TaskStatus.RUNNING,
            started_at=datetime.utcnow().isoformat(),
        )
        self._notify_progress(task_id, TaskStatus.RUNNING, 0)

        try:
            # Create a research agent for this task
            from backend.memory.conversation_memory import ConversationMemory
            memory = ConversationMemory(self.storage)

            if task_type == "research":
                agent = ResearchAgent(memory=memory)
                result = await agent.conduct_research(
                    topic=params.get("topic", ""),
                    depth=params.get("depth", "standard"),
                )
            elif task_type == "analyze_file":
                agent = ResearchAgent(memory=memory)
                result = await agent.analyze_uploaded_file(
                    file_path=params.get("file_path", ""),
                    question=params.get("question", ""),
                )
            elif task_type == "generate_report":
                agent = ResearchAgent(memory=memory)
                result = await agent.generate_report(
                    topic=params.get("topic", ""),
                    findings=params.get("findings", ""),
                    format=params.get("format", "markdown"),
                )
            else:
                result = f"Unknown task type: {task_type}"

            # Update task as completed
            await self.storage.update_task(
                task_id,
                status=TaskStatus.COMPLETED,
                result=result[:50000],  # Truncate very long results
                completed_at=datetime.utcnow().isoformat(),
            )
            self._notify_progress(task_id, TaskStatus.COMPLETED, 100)
            logger.info(f"Task completed: {task_id}")

        except asyncio.CancelledError:
            await self.storage.update_task(task_id, status=TaskStatus.CANCELLED)
            self._notify_progress(task_id, TaskStatus.CANCELLED, 0)
            logger.info(f"Task cancelled: {task_id}")

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            await self.storage.update_task(
                task_id,
                status=TaskStatus.FAILED,
                error=error_msg,
                completed_at=datetime.utcnow().isoformat(),
            )
            self._notify_progress(task_id, TaskStatus.FAILED, 0)
            logger.error(f"Task failed: {task_id} - {error_msg}")

        finally:
            self._running_tasks.pop(task_id, None)

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task.

        Args:
            task_id: Task ID to cancel.

        Returns:
            True if task was cancelled, False if not found or not running.
        """
        task = await self.storage.get_task(task_id)
        if not task:
            return False

        if task["status"] != TaskStatus.RUNNING:
            return False

        # Cancel the asyncio task if it exists
        async_task = self._running_tasks.get(task_id)
        if async_task and not async_task.done():
            async_task.cancel()

        await self.storage.update_task(task_id, status=TaskStatus.CANCELLED)
        logger.info(f"Task cancelled: {task_id}")
        return True

    async def get_task_status(self, task_id: str) -> Optional[dict]:
        """Get the current status of a task.

        Args:
            task_id: Task ID.

        Returns:
            Task record with status information.
        """
        return await self.storage.get_task(task_id)

    async def list_tasks(self, status: Optional[str] = None) -> list[dict]:
        """List tasks with optional status filter.

        Args:
            status: Optional status filter.

        Returns:
            List of task records.
        """
        return await self.storage.list_tasks(status=status)

    def on_progress(self, task_id: str, callback: Callable) -> None:
        """Register a progress callback for a task.

        Args:
            task_id: Task ID to watch.
            callback: Callback function(task_id, status, progress).
        """
        if task_id not in self._progress_callbacks:
            self._progress_callbacks[task_id] = []
        self._progress_callbacks[task_id].append(callback)

    def _notify_progress(self, task_id: str, status: TaskStatus, progress: int) -> None:
        """Notify registered callbacks of task progress.

        Args:
            task_id: Task ID.
            status: Current status.
            progress: Progress percentage (0-100).
        """
        for callback in self._progress_callbacks.get(task_id, []):
            try:
                callback(task_id, status, progress)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

    async def cleanup(self) -> None:
        """Cancel all running tasks and clean up."""
        for task_id in list(self._running_tasks.keys()):
            await self.cancel_task(task_id)
        self._running_tasks.clear()
        self._progress_callbacks.clear()
        logger.info("Task executor cleaned up")
