"""
Task management API routes for ResearchAgent.

Handles creation, monitoring, and retrieval of research tasks.
"""

from fastapi import APIRouter, HTTPException

from backend.api.models import TaskCreate, TaskResponse, TaskStatus
from backend.agents.task_executor import TaskExecutor
from backend.memory.storage import StorageManager
from backend.utils.logger import get_logger

logger = get_logger("api.tasks")

router = APIRouter(prefix="/api", tags=["tasks"])

_storage: StorageManager = None
_executor: TaskExecutor = None


def init_task_routes(storage: StorageManager, executor: TaskExecutor):
    """Initialize task routes with dependencies.

    Args:
        storage: Storage manager instance.
        executor: Task executor instance.
    """
    global _storage, _executor
    _storage = storage
    _executor = executor


@router.post("/tasks", response_model=TaskResponse)
async def create_task(request: TaskCreate):
    """Create and submit a new research task.

    The task will be executed asynchronously. Use GET /api/tasks/{id}
    to check the task status and retrieve results.

    Args:
        request: Task creation request.

    Returns:
        Created task with pending status.
    """
    try:
        task = await _executor.submit_task(
            title=request.title,
            task_type=request.task_type,
            params=request.params,
            conversation_id=request.conversation_id,
        )
        return TaskResponse(**task)
    except Exception as e:
        logger.error(f"Task creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks", response_model=list[TaskResponse])
async def list_tasks(status: str = None, limit: int = 50):
    """List tasks with optional status filter.

    Args:
        status: Filter by task status (pending/running/completed/failed/cancelled).
        limit: Maximum results.

    Returns:
        List of task records.
    """
    tasks = await _executor.list_tasks(status=status)
    return [TaskResponse(**t) for t in tasks[:limit]]


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """Get a task by ID with its current status and result.

    Args:
        task_id: Task ID.

    Returns:
        Task record with status and result.
    """
    task = await _executor.get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse(**task)


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running task.

    Args:
        task_id: Task ID to cancel.

    Returns:
        Cancellation confirmation.
    """
    task = await _executor.get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task["status"] not in (TaskStatus.PENDING, TaskStatus.RUNNING):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel task with status: {task['status']}"
        )

    cancelled = await _executor.cancel_task(task_id)
    if cancelled:
        return {"message": "Task cancelled", "id": task_id}
    else:
        raise HTTPException(status_code=400, detail="Failed to cancel task")
