# ResearchAgent Architecture

## Overview

ResearchAgent is built on a modular architecture that separates concerns into distinct layers:

```
┌─────────────────────────────────────────────────┐
│                 User Interfaces                  │
│         (CLI / Web UI / API Clients)             │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│              API Layer (FastAPI)                  │
│    Routes: Chat, Tasks, Files, Health            │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│             Agent Layer                          │
│  ┌─────────────┐  ┌──────────────┐              │
│  │ BaseAgent   │  │ ResearchAgent│              │
│  │ (ReAct)     │──│ (Specialized)│              │
│  └─────────────┘  └──────────────┘              │
│  ┌──────────────┐                               │
│  │ TaskExecutor │ (Async task management)        │
│  └──────────────┘                               │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│              Tool Layer                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │ Search   │ │ Scraper  │ │ Analyzer │        │
│  └──────────┘ └──────────┘ └──────────┘        │
│  ┌──────────┐ ┌──────────┐                      │
│  │ Data     │ │ Report   │                      │
│  │ Analysis │ │ Generator│                      │
│  └──────────┘ └──────────┘                      │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│            Memory Layer                          │
│  ┌──────────────────┐ ┌──────────────┐          │
│  │ConversationMemory│ │ StorageManager│          │
│  │ (Short/Long term)│ │   (SQLite)   │          │
│  └──────────────────┘ └──────────────┘          │
└─────────────────────────────────────────────────┘
```

## Core Components

### 1. Base Agent (`backend/agents/base_agent.py`)

Implements the **ReAct (Reasoning + Acting)** framework:

```python
while iterations < max_iterations:
    # THINK: LLM analyzes the situation
    response = await llm.ainvoke(messages)

    if response.has_tool_calls:
        # ACT: Execute tools
        results = await process_tool_calls(response.tool_calls)

        # OBSERVE: Feed results back to LLM
        messages.extend(results)
    else:
        # FINALIZE: Return response
        return response.content
```

**Key features:**
- Tool binding via LangChain function calling
- Automatic retry on tool failures
- Context window management
- Error recovery with LLM-guided fallback

### 2. Research Agent (`backend/agents/research_agent.py`)

Extends BaseAgent with research-specific capabilities:

- **Goal Decomposition**: Breaks complex research into subtasks
- **Research Methodology**: Structured approach (Gather → Analyze → Synthesize)
- **Multi-Source Synthesis**: Combines information from multiple tools
- **Report Generation**: Creates structured findings

### 3. Task Executor (`backend/agents/task_executor.py`)

Manages asynchronous task execution:

```python
class TaskExecutor:
    - Semaphore-controlled concurrency (max_concurrent_tasks)
    - Task lifecycle: pending → running → completed/failed
    - Progress callbacks for real-time updates
    - Graceful cancellation support
```

## Tool System

Each tool implements the LangChain `BaseTool` interface:

```python
class MyTool(BaseTool):
    name = "tool_name"
    description = "What this tool does"
    args_schema = MyInputSchema  # Pydantic model

    def _run(self, **kwargs) -> str:
        # Synchronous implementation

    async def _arun(self, **kwargs) -> str:
        # Async implementation (preferred)
```

### Tool Details

| Tool | Input | Output | Features |
|------|-------|--------|----------|
| SearchTool | query, num_results | Formatted results | Caching, DuckDuckGo/SerpAPI |
| WebScraperTool | url, extract_mode | Page content | Text/links/tables extraction |
| FileAnalyzerTool | file_path, analysis_type | File analysis | PDF/CSV/Excel/JSON/MD |
| DataAnalysisTool | file_path, query, chart | Analysis + charts | EDA, statistics, visualization |
| ReportGeneratorTool | title, content, format | Report file | Markdown/PDF, TOC, sections |

## Memory Architecture

### Short-term Memory (Conversation Context)
- Current conversation messages
- Sliding window (configurable max_context_messages)
- Formatted for LLM consumption

### Long-term Memory (SQLite)
- Important facts extracted from conversations
- Key-value storage with categories
- Importance scoring and access tracking
- Full-text search capability

### Search Cache
- Hash-based cache for search results
- Configurable TTL
- Automatic expiration cleanup

## Data Flow

### Chat Request Flow

```
User Message
    │
    ▼
API Route (chat.py)
    │
    ▼
ConversationMemory.add_user_message()
    │
    ▼
BaseAgent.run(message)
    │
    ├──▶ Build messages (system + history + user)
    │
    ├──▶ LLM Invocation (with tool binding)
    │
    ├──▶ [If tool calls] Process tools
    │       ├── Execute each tool
    │       ├── Save results to memory
    │       └── Continue ReAct loop
    │
    └──▶ [If no tools] Final response
            ├── Save to memory
            ├── Extract key facts
            └── Return to user
```

### Task Execution Flow

```
Task Creation Request
    │
    ▼
TaskExecutor.submit_task()
    │
    ├── Save to SQLite (status: pending)
    │
    └── asyncio.create_task(_execute_task)
            │
            ├── Semaphore acquire
            │
            ├── Update status: running
            │
            ├── Create agent + memory
            │
            ├── Execute task type:
            │   ├── research → conduct_research()
            │   ├── analyze_file → analyze_uploaded_file()
            │   └── generate_report → generate_report()
            │
            ├── Update status: completed/failed
            │
            └── Semaphore release
```

## Configuration

Settings managed via `pydantic-settings`:

```python
class Settings(BaseSettings):
    # LLM
    llm_provider: str = "openai"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o"

    # Search
    search_engine: str = "duckduckgo"

    # Application
    database_url: str = "sqlite:///./data/research_agent.db"
    max_concurrent_tasks: int = 5
    cache_ttl: int = 3600

    # Files
    max_upload_size_mb: int = 50
    upload_dir: str = "./data/uploads"
    reports_dir: str = "./data/reports"
```

## Security Considerations

1. **File Upload**: Size limits, extension validation
2. **Input Sanitization**: Pydantic validation on all inputs
3. **Rate Limiting**: Semaphore on concurrent tasks
4. **Error Handling**: No internal details exposed to users
5. **CORS**: Configurable origins (default: allow all for dev)

## Performance Optimizations

1. **Search Caching**: Avoid redundant API calls
2. **Connection Pooling**: SQLite WAL mode
3. **Async Operations**: Non-blocking I/O throughout
4. **Context Window**: Sliding window for LLM context
5. **Lazy Loading**: Tools initialized on demand
