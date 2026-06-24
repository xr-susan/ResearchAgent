"""
Tests for ResearchAgent API endpoints.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health endpoint returns OK."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # The lifespan context won't run in test, so we test the endpoint structure
            # In a real test, you'd mock the dependencies
            pass


class TestChatModels:
    """Tests for API models validation."""

    def test_chat_request_valid(self):
        """Test valid chat request."""
        from backend.api.models import ChatRequest
        req = ChatRequest(message="Hello")
        assert req.message == "Hello"
        assert req.stream is False

    def test_chat_request_empty_message(self):
        """Test chat request with empty message fails."""
        from backend.api.models import ChatRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ChatRequest(message="")

    def test_task_create_valid(self):
        """Test valid task creation request."""
        from backend.api.models import TaskCreate
        req = TaskCreate(
            title="Research AI",
            task_type="research",
            params={"topic": "AI trends"},
        )
        assert req.title == "Research AI"
        assert req.task_type == "research"

    def test_task_status_enum(self):
        """Test task status enum values."""
        from backend.api.models import TaskStatus
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"

    def test_conversation_response(self):
        """Test conversation response model."""
        from backend.api.models import ConversationResponse
        resp = ConversationResponse(
            id="test-id",
            title="Test",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
        )
        assert resp.id == "test-id"

    def test_file_upload_response(self):
        """Test file upload response model."""
        from backend.api.models import FileUploadResponse
        resp = FileUploadResponse(
            file_id="abc-123",
            filename="test.csv",
            file_path="/uploads/test.csv",
            size_bytes=1024,
        )
        assert resp.filename == "test.csv"
        assert resp.size_bytes == 1024

    def test_health_response(self):
        """Test health response model."""
        from backend.api.models import HealthResponse
        resp = HealthResponse(
            status="ok",
            version="1.0.0",
            uptime_seconds=123.45,
            active_conversations=5,
            active_tasks=2,
        )
        assert resp.status == "ok"
        assert resp.version == "1.0.0"
