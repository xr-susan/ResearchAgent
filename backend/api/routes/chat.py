"""
Chat API routes for ResearchAgent.

Handles conversational interactions with the research agent.
"""

import json
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.agents.research_agent import ResearchAgent
from backend.api.models import (
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationDetail,
    ConversationResponse,
    MessageResponse,
    StreamChunk,
)
from backend.memory.conversation_memory import ConversationMemory
from backend.memory.storage import StorageManager
from backend.utils.logger import get_logger

logger = get_logger("api.chat")

router = APIRouter(prefix="/api", tags=["chat"])

# These will be set by the main app
_storage: StorageManager = None
_agent: ResearchAgent = None


def init_chat_routes(storage: StorageManager, agent: ResearchAgent):
    """Initialize chat routes with dependencies.

    Args:
        storage: Storage manager instance.
        agent: Research agent instance.
    """
    global _storage, _agent
    _storage = storage
    _agent = agent


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message to the research agent.

    The agent will process the message, potentially using tools,
    and return a comprehensive response.

    Args:
        request: Chat request with message and optional conversation ID.

    Returns:
        Chat response with agent's reply.
    """
    try:
        # Load or create conversation
        memory = ConversationMemory(_storage)

        if request.conversation_id:
            loaded = await memory.load_conversation(request.conversation_id)
            if not loaded:
                raise HTTPException(status_code=404, detail="Conversation not found")
        else:
            # Auto-generate title from first message
            title = request.message[:50] + ("..." if len(request.message) > 50 else "")
            await memory.start_conversation(title)

        # Set the agent's memory
        _agent.memory = memory

        # Run the agent
        response = await _agent.run(request.message, stream=request.stream)

        return ChatResponse(
            conversation_id=memory.conversation_id,
            message=response,
            metadata={"model": _agent.model_name},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Send a message and receive a streaming response.

    Uses Server-Sent Events (SSE) for streaming.

    Args:
        request: Chat request.

    Returns:
        Streaming response with SSE events.
    """
    try:
        memory = ConversationMemory(_storage)

        if request.conversation_id:
            loaded = await memory.load_conversation(request.conversation_id)
            if not loaded:
                raise HTTPException(status_code=404, detail="Conversation not found")
        else:
            title = request.message[:50] + ("..." if len(request.message) > 50 else "")
            await memory.start_conversation(title)

        _agent.memory = memory

        async def event_stream() -> AsyncGenerator[str, None]:
            """Generate SSE events for streaming response."""
            try:
                # For now, send the complete response as a single chunk
                # In production, you'd implement true token streaming
                response = await _agent.run(request.message)

                chunk = StreamChunk(type="token", content=response)
                yield f"data: {chunk.model_dump_json()}\n\n"

                done_chunk = StreamChunk(
                    type="done",
                    content="",
                    metadata={"conversation_id": memory.conversation_id}
                )
                yield f"data: {done_chunk.model_dump_json()}\n\n"

            except Exception as e:
                error_chunk = StreamChunk(type="error", content=str(e))
                yield f"data: {error_chunk.model_dump_json()}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stream chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(limit: int = 50, offset: int = 0):
    """List all conversations.

    Args:
        limit: Maximum results to return.
        offset: Pagination offset.

    Returns:
        List of conversation summaries.
    """
    conversations = await _storage.list_conversations(limit=limit, offset=offset)
    return [ConversationResponse(**c) for c in conversations]


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(request: ConversationCreate):
    """Create a new conversation.

    Args:
        request: Conversation creation request.

    Returns:
        Created conversation.
    """
    conv = await _storage.create_conversation(title=request.title)
    return ConversationResponse(**conv)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: str):
    """Get a conversation with its message history.

    Args:
        conversation_id: Conversation ID.

    Returns:
        Conversation detail with messages.
    """
    conv = await _storage.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = await _storage.get_messages(conversation_id)

    return ConversationDetail(
        **conv,
        messages=[MessageResponse(**m) for m in messages],
        message_count=len(messages),
    )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation and its messages.

    Args:
        conversation_id: Conversation ID.

    Returns:
        Deletion confirmation.
    """
    conv = await _storage.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await _storage.delete_conversation(conversation_id)
    return {"message": "Conversation deleted", "id": conversation_id}
