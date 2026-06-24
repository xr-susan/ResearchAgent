"""
Pydantic models for the ResearchAgent API.

Defines request/response schemas for all API endpoints.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---- Enums ----

class MessageRole(str, Enum):
    """Message role enum."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class TaskStatus(str, Enum):
    """Task status enum."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---- Chat Models ----

class ChatRequest(BaseModel):
    """Request model for sending a chat message."""
    message: str = Field(..., min_length=1, max_length=10000, description="User message")
    conversation_id: Optional[str] = Field(None, description="Existing conversation ID")
    stream: bool = Field(False, description="Enable streaming response")


class ChatResponse(BaseModel):
    """Response model for chat messages."""
    conversation_id: str
    message: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list, description="Tools used in response")
    metadata: dict[str, Any] = Field(default_factory=dict)


class StreamChunk(BaseModel):
    """Streaming response chunk."""
    type: str = Field(..., description="Chunk type: token, tool_call, tool_result, done")
    content: str = ""
    tool_name: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---- Conversation Models ----

class ConversationCreate(BaseModel):
    """Request model for creating a conversation."""
    title: str = Field("New Conversation", max_length=200)


class ConversationResponse(BaseModel):
    """Response model for conversation data."""
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MessageResponse(BaseModel):
    """Response model for message data."""
    id: str
    conversation_id: str
    role: MessageRole
    content: str
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    created_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationDetail(ConversationResponse):
    """Detailed conversation with messages."""
    messages: list[MessageResponse] = Field(default_factory=list)


# ---- Task Models ----

class TaskCreate(BaseModel):
    """Request model for creating a research task."""
    title: str = Field(..., min_length=1, max_length=200, description="Task title")
    task_type: str = Field(
        ...,
        description="Task type: research, analyze_file, generate_report"
    )
    params: dict[str, Any] = Field(default_factory=dict, description="Task parameters")
    conversation_id: Optional[str] = None


class TaskResponse(BaseModel):
    """Response model for task data."""
    id: str
    title: str
    description: Optional[str] = None
    status: TaskStatus
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---- File Models ----

class FileUploadResponse(BaseModel):
    """Response model for file upload."""
    file_id: str
    filename: str
    file_path: str
    size_bytes: int
    content_type: Optional[str] = None
    message: str = "File uploaded successfully"


# ---- Memory Models ----

class MemorySaveRequest(BaseModel):
    """Request model for saving to long-term memory."""
    key: str = Field(..., min_length=1, max_length=200)
    value: str = Field(..., min_length=1)
    category: str = Field("general", max_length=100)
    importance: float = Field(0.5, ge=0.0, le=1.0)


class MemorySearchRequest(BaseModel):
    """Request model for searching memory."""
    query: str = Field(..., min_length=1)
    category: Optional[str] = None
    limit: int = Field(10, ge=1, le=100)


class MemoryEntry(BaseModel):
    """Response model for memory entries."""
    id: str
    key: str
    value: str
    category: str
    importance: float
    created_at: str
    updated_at: str
    access_count: int


# ---- Health & Status ----

class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    version: str = "1.0.0"
    uptime_seconds: float
    active_conversations: int = 0
    active_tasks: int = 0


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
    status_code: int
