"""
SQLite storage manager for ResearchAgent.

Handles persistence of conversations, messages, tasks, and long-term memory.
Uses aiosqlite for async database operations.
"""

import json
import uuid
from datetime import datetime
from typing import Any, Optional

import aiosqlite

from backend.utils.config import settings
from backend.utils.logger import get_logger

logger = get_logger("storage")


class StorageManager:
    """Async SQLite storage manager for persisting agent data."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize storage manager.

        Args:
            db_path: Path to SQLite database file. Defaults to settings.db_path.
        """
        self.db_path = str(db_path or settings.db_path)
        self._db: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Establish database connection and initialize schema."""
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._init_schema()
        logger.info(f"Connected to database: {self.db_path}")

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None
            logger.info("Database connection closed")

    async def _init_schema(self) -> None:
        """Create database tables if they don't exist."""
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT 'New Conversation',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system', 'tool')),
                content TEXT NOT NULL,
                tool_call_id TEXT,
                tool_name TEXT,
                created_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
                result TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS long_term_memory (
                id TEXT PRIMARY KEY,
                key TEXT NOT NULL UNIQUE,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                importance REAL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                access_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS search_cache (
                query_hash TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                results TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conversation
                ON messages(conversation_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_tasks_status
                ON tasks(status);
            CREATE INDEX IF NOT EXISTS idx_memory_category
                ON long_term_memory(category);
            CREATE INDEX IF NOT EXISTS idx_cache_expires
                ON search_cache(expires_at);
        """)
        await self._db.commit()
        logger.debug("Database schema initialized")

    # ---- Conversation CRUD ----

    async def create_conversation(self, title: str = "New Conversation", metadata: dict | None = None) -> dict:
        """Create a new conversation.

        Args:
            title: Conversation title.
            metadata: Optional metadata dictionary.

        Returns:
            Created conversation record.
        """
        conv_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        await self._db.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at, metadata) VALUES (?, ?, ?, ?, ?)",
            (conv_id, title, now, now, json.dumps(metadata or {}))
        )
        await self._db.commit()
        logger.info(f"Created conversation: {conv_id}")
        return {"id": conv_id, "title": title, "created_at": now, "updated_at": now, "metadata": metadata or {}}

    async def get_conversation(self, conv_id: str) -> Optional[dict]:
        """Get a conversation by ID.

        Args:
            conv_id: Conversation ID.

        Returns:
            Conversation record or None if not found.
        """
        async with self._db.execute(
            "SELECT * FROM conversations WHERE id = ?", (conv_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
        return None

    async def list_conversations(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """List conversations ordered by most recent.

        Args:
            limit: Maximum number of results.
            offset: Pagination offset.

        Returns:
            List of conversation records.
        """
        async with self._db.execute(
            "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def update_conversation(self, conv_id: str, **kwargs) -> bool:
        """Update conversation fields.

        Args:
            conv_id: Conversation ID.
            **kwargs: Fields to update (title, metadata).

        Returns:
            True if updated, False if not found.
        """
        allowed = {"title", "metadata"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False

        updates["updated_at"] = datetime.utcnow().isoformat()
        if "metadata" in updates:
            updates["metadata"] = json.dumps(updates["metadata"])

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [conv_id]
        await self._db.execute(
            f"UPDATE conversations SET {set_clause} WHERE id = ?", values
        )
        await self._db.commit()
        return True

    async def delete_conversation(self, conv_id: str) -> bool:
        """Delete a conversation and its messages.

        Args:
            conv_id: Conversation ID.

        Returns:
            True if deleted, False if not found.
        """
        await self._db.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        await self._db.commit()
        return True

    # ---- Message CRUD ----

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tool_call_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        metadata: dict | None = None,
    ) -> dict:
        """Add a message to a conversation.

        Args:
            conversation_id: Parent conversation ID.
            role: Message role (user/assistant/system/tool).
            content: Message content.
            tool_call_id: Optional tool call identifier.
            tool_name: Optional tool name.
            metadata: Optional metadata dictionary.

        Returns:
            Created message record.
        """
        msg_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        await self._db.execute(
            """INSERT INTO messages (id, conversation_id, role, content, tool_call_id, tool_name, created_at, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (msg_id, conversation_id, role, content, tool_call_id, tool_name, now, json.dumps(metadata or {}))
        )
        # Update conversation timestamp
        await self._db.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id)
        )
        await self._db.commit()
        return {
            "id": msg_id, "conversation_id": conversation_id, "role": role,
            "content": content, "tool_call_id": tool_call_id, "tool_name": tool_name,
            "created_at": now, "metadata": metadata or {},
        }

    async def get_messages(self, conversation_id: str, limit: int = 100) -> list[dict]:
        """Get messages for a conversation.

        Args:
            conversation_id: Conversation ID.
            limit: Maximum messages to return.

        Returns:
            List of message records ordered by creation time.
        """
        async with self._db.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC LIMIT ?",
            (conversation_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # ---- Task CRUD ----

    async def create_task(
        self,
        title: str,
        description: str = "",
        conversation_id: Optional[str] = None,
        metadata: dict | None = None,
    ) -> dict:
        """Create a new task.

        Args:
            title: Task title.
            description: Task description.
            conversation_id: Optional linked conversation.
            metadata: Optional metadata.

        Returns:
            Created task record.
        """
        task_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        await self._db.execute(
            """INSERT INTO tasks (id, conversation_id, title, description, status, created_at, metadata)
               VALUES (?, ?, ?, ?, 'pending', ?, ?)""",
            (task_id, conversation_id, title, description, now, json.dumps(metadata or {}))
        )
        await self._db.commit()
        logger.info(f"Created task: {task_id} - {title}")
        return {
            "id": task_id, "title": title, "description": description,
            "status": "pending", "created_at": now, "metadata": metadata or {},
        }

    async def update_task(self, task_id: str, **kwargs) -> bool:
        """Update task fields.

        Args:
            task_id: Task ID.
            **kwargs: Fields to update.

        Returns:
            True if updated.
        """
        allowed = {"status", "result", "error", "started_at", "completed_at", "metadata"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        if "metadata" in updates:
            updates["metadata"] = json.dumps(updates["metadata"])
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [task_id]
        await self._db.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)
        await self._db.commit()
        return True

    async def get_task(self, task_id: str) -> Optional[dict]:
        """Get a task by ID."""
        async with self._db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def list_tasks(self, status: Optional[str] = None, limit: int = 50) -> list[dict]:
        """List tasks, optionally filtered by status."""
        if status:
            query = "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC LIMIT ?"
            params = (status, limit)
        else:
            query = "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?"
            params = (limit,)
        async with self._db.execute(query, params) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

    # ---- Long-term Memory ----

    async def save_memory(self, key: str, value: str, category: str = "general", importance: float = 0.5) -> dict:
        """Save or update a long-term memory entry."""
        now = datetime.utcnow().isoformat()
        await self._db.execute(
            """INSERT INTO long_term_memory (id, key, value, category, importance, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value=?, updated_at=?, importance=?""",
            (str(uuid.uuid4()), key, value, category, importance, now, now, value, now, importance)
        )
        await self._db.commit()
        return {"key": key, "value": value, "category": category}

    async def get_memory(self, key: str) -> Optional[str]:
        """Get a memory value by key."""
        async with self._db.execute(
            "SELECT value FROM long_term_memory WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                await self._db.execute(
                    "UPDATE long_term_memory SET access_count = access_count + 1 WHERE key = ?", (key,)
                )
                await self._db.commit()
                return row["value"]
        return None

    async def search_memory(self, query: str, category: Optional[str] = None, limit: int = 10) -> list[dict]:
        """Search memories by content."""
        if category:
            sql = "SELECT * FROM long_term_memory WHERE (key LIKE ? OR value LIKE ?) AND category = ? ORDER BY importance DESC, updated_at DESC LIMIT ?"
            params = (f"%{query}%", f"%{query}%", category, limit)
        else:
            sql = "SELECT * FROM long_term_memory WHERE key LIKE ? OR value LIKE ? ORDER BY importance DESC, updated_at DESC LIMIT ?"
            params = (f"%{query}%", f"%{query}%", limit)
        async with self._db.execute(sql, params) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

    # ---- Search Cache ----

    async def get_cached_search(self, query_hash: str) -> Optional[list[dict]]:
        """Get cached search results if not expired."""
        now = datetime.utcnow().isoformat()
        async with self._db.execute(
            "SELECT results FROM search_cache WHERE query_hash = ? AND expires_at > ?",
            (query_hash, now)
        ) as cursor:
            row = await cursor.fetchone()
            return json.loads(row["results"]) if row else None

    async def cache_search(self, query_hash: str, query: str, results: list[dict], ttl: int = 3600) -> None:
        """Cache search results."""
        now = datetime.utcnow().isoformat()
        from datetime import timedelta
        expires = (datetime.utcnow() + timedelta(seconds=ttl)).isoformat()
        await self._db.execute(
            """INSERT OR REPLACE INTO search_cache (query_hash, query, results, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?)""",
            (query_hash, query, json.dumps(results), now, expires)
        )
        await self._db.commit()

    async def cleanup_expired_cache(self) -> int:
        """Remove expired cache entries. Returns count of deleted rows."""
        now = datetime.utcnow().isoformat()
        cursor = await self._db.execute("DELETE FROM search_cache WHERE expires_at < ?", (now,))
        await self._db.commit()
        return cursor.rowcount
