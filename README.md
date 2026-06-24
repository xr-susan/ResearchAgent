# 🔬 ResearchAgent - AI Research Assistant

An intelligent AI agent that can conduct web research, analyze documents, process data, and generate comprehensive research reports. Built with LangChain, FastAPI, and modern Python.

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)

## ✨ Features

### Core Capabilities
- **🔍 Web Search** - Search the web using DuckDuckGo or SerpAPI
- **📄 Document Analysis** - Parse PDF, CSV, Excel, TXT, JSON, Markdown files
- **📊 Data Analysis** - Statistical analysis, trend detection, visualizations
- **🌐 Web Scraping** - Extract content from web pages
- **📝 Report Generation** - Create structured Markdown/PDF reports
- **🧠 Memory Management** - Short-term context and long-term memory

### Agent Intelligence
- **ReAct Framework** - Think → Act → Observe reasoning loop
- **Goal Decomposition** - Break complex tasks into manageable steps
- **Adaptive Tool Selection** - Automatically choose the right tool
- **Error Recovery** - Graceful handling of tool failures
- **Multi-Source Synthesis** - Combine information from multiple sources

### Interaction Modes
- **CLI** - Interactive command-line interface with rich formatting
- **REST API** - FastAPI backend with full OpenAPI documentation
- **Streaming** - Server-Sent Events for real-time responses

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- OpenAI API key (or Anthropic Claude key)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/ResearchAgent.git
cd ResearchAgent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your API keys
# OPENAI_API_KEY=sk-your-key-here
```

### Run the CLI

```bash
# Interactive mode
python -m cli.main

# Single query mode
python -m cli.main -q "What are the latest AI trends in 2024?"

# Start API server
python -m cli.main --server
```

### Run the API Server

```bash
# Direct uvicorn
uvicorn backend.api.main:app --reload --port 8000

# Access API docs
# http://localhost:8000/docs
```

## 📖 Usage Examples

### CLI Interactive Mode

```
🔬 ResearchAgent - AI Research Assistant

You: Analyze the current state of AI agents in 2024

🤖 ResearchAgent:
# AI Agents in 2024: A Comprehensive Analysis

## Executive Summary
The AI agent ecosystem has evolved significantly in 2024...

## Key Findings
1. **Market Growth**: The AI agent market reached $X billion...
2. **Technical Advances**: Multi-modal agents became mainstream...
3. **Enterprise Adoption**: 60% of Fortune 500 companies...

## Sources
- [Source 1](https://...)
- [Source 2](https://...)
```

### API Usage

```python
import requests

# Send a chat message
response = requests.post("http://localhost:8000/api/chat", json={
    "message": "What are the top programming languages in 2024?",
    "conversation_id": None  # or existing conversation ID
})
print(response.json()["message"])

# Create a research task
task = requests.post("http://localhost:8000/api/tasks", json={
    "title": "AI Industry Analysis",
    "task_type": "research",
    "params": {
        "topic": "AI industry trends and market analysis 2024",
        "depth": "deep"
    }
})
print(task.json()["id"])

# Upload a file for analysis
with open("data.csv", "rb") as f:
    upload = requests.post("http://localhost:8000/api/upload", files={"file": f})
    file_id = upload.json()["file_id"]

# Analyze uploaded file
analysis = requests.post(f"http://localhost:8000/api/files/{file_id}/analyze",
    params={"question": "What are the key trends in this data?"})
print(analysis.json()["analysis"])
```

## 🏗️ Architecture

### Project Structure

```
ResearchAgent/
├── backend/
│   ├── agents/              # Agent implementations
│   │   ├── base_agent.py    # ReAct framework base class
│   │   ├── research_agent.py # Research-specialized agent
│   │   └── task_executor.py  # Async task management
│   ├── tools/               # Agent tools
│   │   ├── search_tool.py   # Web search (DuckDuckGo/SerpAPI)
│   │   ├── file_analyzer.py # File parsing (PDF/CSV/Excel)
│   │   ├── data_analysis.py # Data analysis & visualization
│   │   ├── web_scraper.py   # Web content extraction
│   │   └── report_generator.py # Report generation
│   ├── memory/              # Memory management
│   │   ├── conversation_memory.py # Context & long-term memory
│   │   └── storage.py       # SQLite persistence
│   ├── api/                 # FastAPI application
│   │   ├── routes/          # API endpoints
│   │   ├── models.py        # Pydantic schemas
│   │   └── main.py          # App configuration
│   ├── utils/               # Utilities
│   │   ├── config.py        # Settings management
│   │   └── logger.py        # Logging configuration
│   └── tests/               # Test suite
├── cli/                     # CLI interface
├── data/                    # Runtime data (gitignored)
├── docker-compose.yml       # Docker configuration
├── Dockerfile               # Container build
└── README.md                # This file
```

### ReAct Loop

The agent follows the **Think → Act → Observe** pattern:

```
┌─────────────────────────────────────────┐
│              User Input                  │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│    🧠 THINK: Analyze & Plan             │
│    - Understand the task                 │
│    - Decompose into subtasks             │
│    - Select appropriate tools            │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│    ⚡ ACT: Execute Tool                  │
│    - Call selected tool                  │
│    - Handle parameters                   │
│    - Process results                     │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│    👁️ OBSERVE: Evaluate Results          │
│    - Check if task complete              │
│    - Identify next steps                 │
│    - Continue or finalize                │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│    📝 RESPONSE: Final Answer             │
│    - Synthesize findings                 │
│    - Cite sources                        │
│    - Present structured output           │
└─────────────────────────────────────────┘
```

## 🔌 API Reference

### Chat Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Send a message to the agent |
| POST | `/api/chat/stream` | Stream a response (SSE) |
| GET | `/api/conversations` | List all conversations |
| POST | `/api/conversations` | Create a new conversation |
| GET | `/api/conversations/{id}` | Get conversation with messages |
| DELETE | `/api/conversations/{id}` | Delete a conversation |

### Task Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/tasks` | Create a research task |
| GET | `/api/tasks` | List tasks (optional status filter) |
| GET | `/api/tasks/{id}` | Get task status and result |
| POST | `/api/tasks/{id}/cancel` | Cancel a running task |

### File Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/upload` | Upload a file |
| GET | `/api/files` | List uploaded files |
| POST | `/api/files/{id}/analyze` | Analyze an uploaded file |
| GET | `/api/reports` | List generated reports |
| GET | `/api/reports/{filename}` | Get a report |

### System Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/` | API welcome message |

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=backend --cov-report=html

# Run specific test file
pytest backend/tests/test_tools.py

# Run with verbose output
pytest -v
```

## 🐳 Docker Deployment

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f backend

# Stop
docker-compose down
```

## ⚙️ Configuration

Key environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM provider (openai/anthropic) | openai |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `OPENAI_MODEL` | Model name | gpt-4o |
| `SEARCH_ENGINE` | Search backend | duckduckgo |
| `PORT` | Server port | 8000 |
| `LOG_LEVEL` | Logging level | INFO |
| `MAX_CONCURRENT_TASKS` | Max parallel tasks | 5 |
| `CACHE_TTL` | Search cache TTL (seconds) | 3600 |

## 🛠️ Extending ResearchAgent

### Adding Custom Tools

```python
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

class MyToolInput(BaseModel):
    query: str = Field(description="Input for my tool")

class MyCustomTool(BaseTool):
    name = "my_custom_tool"
    description = "Description of what this tool does"
    args_schema = MyToolInput

    def _run(self, query: str) -> str:
        # Your tool logic here
        return f"Result for: {query}"

    async def _arun(self, query: str) -> str:
        # Async version
        return self._run(query)

# Use with agent
from backend.agents.research_agent import ResearchAgent
agent = ResearchAgent(memory=memory, tools=[MyCustomTool()])
```

## 📊 Sample Research Workflow

```
User: "Analyze 2024 AI industry trends with market data"

Agent Execution:
1. 🔍 Search: "2024 AI industry market size trends"
   → Found 5 relevant results

2. 🌐 Scrape: https://statista.com/ai-market-2024
   → Extracted market data and statistics

3. 🔍 Search: "2024 AI funding investment data"
   → Found 5 relevant results

4. 🌐 Scrape: https://cbinsights.com/ai-funding-2024
   → Extracted funding data

5. 📊 Analysis: Compile and cross-reference data
   → Identified key trends and statistics

6. 📝 Report: Generate structured findings
   → Created comprehensive analysis report

Response:
# 2024 AI Industry Analysis

## Market Overview
- Global AI market: $XXX billion (XX% YoY growth)
- Enterprise AI adoption: XX%
...

## Key Trends
1. Large Language Models dominate investment
2. AI Agents emerge as next frontier
...

## Sources
- [Statista AI Market Report](...)
- [CB Insights AI Funding Analysis](...)
```

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- [LangChain](https://github.com/langchain-ai/langchain) - Agent framework
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [OpenAI](https://openai.com/) / [Anthropic](https://www.anthropic.com/) - LLM providers
