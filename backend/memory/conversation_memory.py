"""
Conversation memory management for ResearchAgent.

Implements short-term (conversation context) and long-term (important facts) memory.
Provides context window management for LLM interactions.
"""

from typing import Any, Optional

from backend.memory.storage import StorageManager
from backend.utils.logger import get_logger

logger = get_logger("conversation_memory")


class ConversationMemory:
    """Manages conversation context and long-term memory for the agent.

    Provides two memory tiers:
    - Short-term: Current conversation messages (context window)
    - Long-term: Persisted important facts extracted from conversations
    """

    def __init__(self, storage: StorageManager, max_context_messages: int = 50):
        """Initialize conversation memory.

        Args:
            storage: StorageManager instance for persistence.
            max_context_messages: Maximum messages to keep in context window.
        """
        self.storage = storage
        self.max_context_messages = max_context_messages
        self._current_conversation_id: Optional[str] = None
        self._message_cache: list[dict] = []

    @property
    def conversation_id(self) -> Optional[str]:
        """Current conversation ID."""
        return self._current_conversation_id

    async def start_conversation(self, title: str = "New Conversation") -> str:
        """Start a new conversation.

        Args:
            title: Conversation title.

        Returns:
            New conversation ID.
        """
        conv = await self.storage.create_conversation(title)
        self._current_conversation_id = conv["id"]
        self._message_cache = []
        logger.info(f"Started new conversation: {conv['id']}")
        return conv["id"]

    async def load_conversation(self, conversation_id: str) -> bool:
        """Load an existing conversation.

        Args:
            conversation_id: Conversation ID to load.

        Returns:
            True if conversation was found and loaded.
        """
        conv = await self.storage.get_conversation(conversation_id)
        if not conv:
            logger.warning(f"Conversation not found: {conversation_id}")
            return False

        self._current_conversation_id = conversation_id
        self._message_cache = await self.storage.get_messages(conversation_id, limit=self.max_context_messages)
        logger.info(f"Loaded conversation: {conversation_id} ({len(self._message_cache)} messages)")
        return True

    async def add_user_message(self, content: str, metadata: dict | None = None) -> dict:
        """Add a user message to the current conversation.

        Args:
            content: Message content.
            metadata: Optional metadata.

        Returns:
            Created message record.
        """
        if not self._current_conversation_id:
            await self.start_conversation()

        msg = await self.storage.add_message(
            self._current_conversation_id, "user", content, metadata=metadata
        )
        self._message_cache.append(msg)
        return msg

    async def add_assistant_message(self, content: str, metadata: dict | None = None) -> dict:
        """Add an assistant message to the current conversation."""
        if not self._current_conversation_id:
            await self.start_conversation()

        msg = await self.storage.add_message(
            self._current_conversation_id, "assistant", content, metadata=metadata
        )
        self._message_cache.append(msg)
        return msg

    async def add_tool_message(self, tool_name: str, content: str, tool_call_id: Optional[str] = None) -> dict:
        """Add a tool result message to the current conversation."""
        if not self._current_conversation_id:
            await self.start_conversation()

        msg = await self.storage.add_message(
            self._current_conversation_id, "tool", content,
            tool_call_id=tool_call_id, tool_name=tool_name
        )
        self._message_cache.append(msg)
        return msg

    def get_context_messages(self, limit: Optional[int] = None) -> list[dict[str, Any]]:
        """Get messages for LLM context window.

        Args:
            limit: Maximum messages to return. Defaults to max_context_messages.

        Returns:
            List of messages formatted for LLM consumption.
        """
        max_msgs = limit or self.max_context_messages
        messages = self._message_cache[-max_msgs:]

        return [
            {
                "role": msg["role"],
                "content": msg["content"],
                **({"tool_call_id": msg["tool_call_id"]} if msg.get("tool_call_id") else {}),
                **({"name": msg["tool_name"]} if msg.get("tool_name") else {}),
            }
            for msg in messages
        ]

    async def save_important_info(self, key: str, value: str, category: str = "general", importance: float = 0.7) -> None:
        """Save important information to long-term memory.

        Args:
            key: Memory key (descriptive identifier).
            value: Information to remember.
            category: Memory category.
            importance: Importance score (0-1).
        """
        await self.storage.save_memory(key, value, category, importance)
        logger.info(f"Saved to long-term memory: {key}")

    async def recall(self, query: str, category: Optional[str] = None) -> list[dict]:
        """Recall information from long-term memory.

        Args:
            query: Search query.
            category: Optional category filter.

        Returns:
            List of matching memory entries.
        """
        return await self.storage.search_memory(query, category)

    async def extract_and_save_key_facts(self, llm_callable=None) -> list[str]:
        """Extract key facts from recent conversation and save to long-term memory.

        This method identifies important information worth remembering long-term,
        such as user preferences, key findings, or important conclusions.

        Args:
            llm_callable: Optional LLM function for fact extraction.

        Returns:
            List of extracted fact keys.
        """
        if len(self._message_cache) < 4:
            return []

        recent = self._message_cache[-10:]
        facts = []

        # Simple heuristic: save assistant messages with high information density
        for msg in recent:
            if msg["role"] == "assistant" and len(msg["content"]) > 200:
                # Extract the first meaningful paragraph as a summary
                lines = [l.strip() for l in msg["content"].split("\n") if l.strip() and not l.strip().startswith("#")]
                if lines:
                    summary = lines[0][:500]
                    fact_key = f"conversation_insight_{msg['id'][:8]}"
                    await self.save_important_info(fact_key, summary, "conversation_insights", 0.6)
                    facts.append(fact_key)

        logger.info(f"Extracted {len(facts)} key facts from conversation")
        return facts

    def get_conversation_summary(self) -> dict[str, Any]:
        """Get a summary of the current conversation state.

        Returns:
            Dictionary with conversation statistics.
        """
        user_msgs = [m for m in self._message_cache if m["role"] == "user"]
        assistant_msgs = [m for m in self._message_cache if m["role"] == "assistant"]
        tool_msgs = [m for m in self._message_cache if m["role"] == "tool"]

        return {
            "conversation_id": self._current_conversation_id,
            "total_messages": len(self._message_cache),
            "user_messages": len(user_msgs),
            "assistant_messages": len(assistant_msgs),
            "tool_calls": len(tool_msgs),
            "context_size": len(self.get_context_messages()),
        }

    async def clear_context(self) -> None:
        """Clear the message cache (keeps persisted data)."""
        self._message_cache = []
        logger.info("Context cache cleared")
