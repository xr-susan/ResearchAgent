"""
Tests for ResearchAgent agent classes.
"""

import pytest

from backend.agents.research_agent import ResearchAgent
from backend.agents.task_executor import TaskExecutor, TaskStatus
from backend.memory.conversation_memory import ConversationMemory
from backend.tools import (
    DataAnalysisTool,
    FileAnalyzerTool,
    ReportGeneratorTool,
    SearchTool,
    WebScraperTool,
)


class TestConversationMemory:
    """Tests for ConversationMemory."""

    @pytest.mark.asyncio
    async def test_start_conversation(self, memory):
        """Test starting a new conversation."""
        conv_id = await memory.start_conversation("Test Conversation")
        assert conv_id is not None
        assert len(conv_id) > 0
        assert memory.conversation_id == conv_id

    @pytest.mark.asyncio
    async def test_add_messages(self, memory):
        """Test adding messages to conversation."""
        await memory.start_conversation()

        msg1 = await memory.add_user_message("Hello")
        assert msg1["role"] == "user"
        assert msg1["content"] == "Hello"

        msg2 = await memory.add_assistant_message("Hi there!")
        assert msg2["role"] == "assistant"

        context = memory.get_context_messages()
        assert len(context) == 2

    @pytest.mark.asyncio
    async def test_tool_message(self, memory):
        """Test adding tool messages."""
        await memory.start_conversation()
        await memory.add_user_message("Search for AI news")

        msg = await memory.add_tool_message("web_search", "Found 5 results", "call_123")
        assert msg["role"] == "tool"
        assert msg["tool_name"] == "web_search"

    @pytest.mark.asyncio
    async def test_conversation_summary(self, memory):
        """Test conversation summary statistics."""
        await memory.start_conversation()
        await memory.add_user_message("Question 1")
        await memory.add_assistant_message("Answer 1")
        await memory.add_tool_message("search", "results", "t1")

        summary = memory.get_conversation_summary()
        assert summary["total_messages"] == 3
        assert summary["user_messages"] == 1
        assert summary["assistant_messages"] == 1
        assert summary["tool_calls"] == 1

    @pytest.mark.asyncio
    async def test_context_limit(self, memory):
        """Test context window limiting."""
        memory.max_context_messages = 5
        await memory.start_conversation()

        for i in range(10):
            await memory.add_user_message(f"Message {i}")
            await memory.add_assistant_message(f"Response {i}")

        context = memory.get_context_messages()
        assert len(context) <= 5

    @pytest.mark.asyncio
    async def test_save_and_recall_memory(self, memory):
        """Test long-term memory save and recall."""
        await memory.start_conversation()

        await memory.save_important_info(
            key="user_preference",
            value="Prefers detailed analysis",
            category="preferences",
            importance=0.8,
        )

        results = await memory.recall("preference")
        assert len(results) > 0
        assert any("detailed" in r["value"] for r in results)

    @pytest.mark.asyncio
    async def test_load_conversation(self, memory, storage):
        """Test loading an existing conversation."""
        conv_id = await memory.start_conversation("Loadable Conv")
        await memory.add_user_message("Test message")

        # Create new memory instance and load
        memory2 = ConversationMemory(storage)
        loaded = await memory2.load_conversation(conv_id)
        assert loaded is True

        context = memory2.get_context_messages()
        assert len(context) == 1

    @pytest.mark.asyncio
    async def test_clear_context(self, memory):
        """Test clearing context cache."""
        await memory.start_conversation()
        await memory.add_user_message("Hello")
        await memory.add_assistant_message("Hi")

        await memory.clear_context()
        context = memory.get_context_messages()
        assert len(context) == 0


class TestTaskExecutor:
    """Tests for TaskExecutor."""

    @pytest.mark.asyncio
    async def test_list_tasks_empty(self, storage):
        """Test listing tasks when none exist."""
        executor = TaskExecutor(storage)
        tasks = await executor.list_tasks()
        assert len(tasks) == 0

    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self, storage):
        """Test getting a task that doesn't exist."""
        executor = TaskExecutor(storage)
        task = await executor.get_task_status("nonexistent-id")
        assert task is None


class TestResearchAgent:
    """Tests for ResearchAgent."""

    def test_default_tools(self, memory):
        """Test that default tools are loaded."""
        agent = ResearchAgent(memory=memory)
        tool_names = set(agent.tools.keys())

        expected = {"web_search", "web_scraper", "file_analyzer", "data_analysis", "report_generator"}
        assert expected == tool_names

    def test_custom_tools(self, memory):
        """Test initialization with custom tools."""
        custom_tools = [SearchTool()]
        agent = ResearchAgent(memory=memory, tools=custom_tools)
        assert len(agent.tools) == 1
        assert "web_search" in agent.tools

    def test_tool_descriptions(self, memory):
        """Test getting tool descriptions."""
        agent = ResearchAgent(memory=memory)
        descriptions = agent.get_tool_descriptions()

        assert "web_search" in descriptions
        assert "file_analyzer" in descriptions
        assert "data_analysis" in descriptions
