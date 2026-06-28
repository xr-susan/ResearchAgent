"""
FastAPI application for ResearchAgent.

Main entry point for the web API server.
Configures routes, middleware, and application lifecycle.
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.agents.research_agent import ResearchAgent
from backend.agents.task_executor import TaskExecutor
from backend.api.models import HealthResponse
from backend.api.routes import chat, files, tasks
from backend.memory.conversation_memory import ConversationMemory
from backend.memory.storage import StorageManager
from backend.utils.config import settings
from backend.utils.logger import get_logger

logger = get_logger("api")

# Global instances
_storage: StorageManager = None
_agent: ResearchAgent = None
_executor: TaskExecutor = None
_start_time: float = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Initializes resources on startup and cleans up on shutdown.
    """
    global _storage, _agent, _executor, _start_time

    _start_time = time.time()
    logger.info("Starting ResearchAgent API...")

    # Initialize storage
    _storage = StorageManager()
    await _storage.connect()
    logger.info("Storage connected")

    # Initialize agent
    memory = ConversationMemory(_storage)
    _agent = ResearchAgent(memory=memory)
    logger.info("Research agent initialized")

    # Initialize task executor
    _executor = TaskExecutor(_storage, max_concurrent=settings.max_concurrent_tasks)
    logger.info("Task executor initialized")

    # Initialize routes with dependencies
    chat.init_chat_routes(_storage, _agent)
    tasks.init_task_routes(_storage, _executor)
    files.init_file_routes(_storage, _agent)

    logger.info(f"ResearchAgent API ready on {settings.host}:{settings.port}")

    yield

    # Shutdown
    logger.info("Shutting down ResearchAgent API...")
    await _executor.cleanup()
    await _storage.close()
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="ResearchAgent API",
    description=(
        "A research assistant API for web search, document analysis, data checks, "
        "and report generation."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    """Add response time header to all responses."""
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    response.headers["X-Response-Time"] = f"{duration:.3f}s"
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


# Include routers
app.include_router(chat.router)
app.include_router(tasks.router)
app.include_router(files.router)


# Health endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API health status.

    Returns:
        Health status with uptime and active counts.
    """
    uptime = time.time() - _start_time

    conversations = await _storage.list_conversations(limit=1000)
    running_tasks = await _storage.list_tasks(status="running")

    return HealthResponse(
        status="ok",
        version="1.0.0",
        uptime_seconds=round(uptime, 2),
        active_conversations=len(conversations),
        active_tasks=len(running_tasks),
    )


@app.get("/")
async def root():
    """API root endpoint with welcome message."""
    return {
        "name": "ResearchAgent API",
        "version": "1.0.0",
        "description": "Research assistant API",
        "docs": "/docs",
        "health": "/health",
    }


def run_server():
    """Run the API server (for CLI use)."""
    import uvicorn
    uvicorn.run(
        "backend.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run_server()
