"""
Pytest configuration and fixtures for ResearchAgent tests.
"""

import asyncio
import tempfile
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from backend.memory.conversation_memory import ConversationMemory
from backend.memory.storage import StorageManager


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def storage() -> AsyncGenerator[StorageManager, None]:
    """Create a temporary storage manager for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        mgr = StorageManager(db_path=str(db_path))
        await mgr.connect()
        yield mgr
        await mgr.close()


@pytest_asyncio.fixture
async def memory(storage: StorageManager) -> ConversationMemory:
    """Create a conversation memory instance for tests."""
    return ConversationMemory(storage)


@pytest.fixture
def sample_csv(tmp_path) -> Path:
    """Create a sample CSV file for testing."""
    csv_content = """name,age,salary,department,join_date
Alice,30,75000,Engineering,2022-01-15
Bob,25,55000,Marketing,2023-03-20
Charlie,35,90000,Engineering,2021-06-10
Diana,28,62000,Sales,2023-01-05
Eve,32,85000,Engineering,2022-08-22
Frank,45,120000,Management,2020-02-14
Grace,29,68000,Marketing,2023-05-30
Hank,38,95000,Sales,2021-11-11
Ivy,27,58000,Marketing,2023-07-19
Jack,41,110000,Management,2020-09-01"""
    csv_file = tmp_path / "test_data.csv"
    csv_file.write_text(csv_content)
    return csv_file


@pytest.fixture
def sample_text(tmp_path) -> Path:
    """Create a sample text file for testing."""
    text_content = """This is a sample research document.

Key Findings:
1. AI adoption increased by 35% in 2024
2. Machine learning leads in enterprise applications
3. Natural language processing shows fastest growth

The global AI market is expected to reach $500 billion by 2025.
Major players include OpenAI, Google, Microsoft, and Anthropic.

Conclusion: AI continues to transform industries at an accelerating pace.
"""
    text_file = tmp_path / "sample_research.txt"
    text_file.write_text(text_content)
    return text_file


@pytest.fixture
def sample_markdown(tmp_path) -> Path:
    """Create a sample markdown file for testing."""
    md_content = """# Research Report: AI Industry Analysis

## Executive Summary
The AI industry experienced significant growth in 2024.

## Key Metrics
- Market size: $200B
- Growth rate: 35%
- Investment: $50B

## Trends
### Large Language Models
LLMs continue to dominate the AI landscape.

### AI Agents
Autonomous agents represent the next frontier.

## Conclusion
The AI industry shows no signs of slowing down.
"""
    md_file = tmp_path / "report.md"
    md_file.write_text(md_content)
    return md_file
