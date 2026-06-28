# ResearchAgent

ResearchAgent is a small research assistant project with a FastAPI backend, a React chat UI, and a CLI. It can search the web, read local files, inspect tabular data, and turn findings into Markdown or PDF reports.

The project is meant to be easy to run locally and easy to extend. It does not hide setup behind a hosted service: you bring an OpenAI or Anthropic API key, choose the search backend, and keep the generated data on your machine.

## What It Includes

- Chat API backed by a tool-using research agent
- Web search with DuckDuckGo by default, or SerpAPI when configured
- Web page extraction for text, links, and tables
- File analysis for TXT, Markdown, JSON, PDF, CSV, and Excel files
- Basic data summaries and optional charts for tabular files
- Markdown/PDF report generation
- SQLite storage for conversations, tasks, memory, and search cache
- CLI for quick terminal use
- React frontend for a simple browser chat experience

## Project Layout

```text
ResearchAgent/
  backend/
    agents/      Agent and task execution logic
    api/         FastAPI app and routes
    memory/      SQLite-backed storage and conversation memory
    tools/       Search, scraping, file, data, and report tools
    tests/       Backend tests
  cli/           Command-line interface
  docs/          API and architecture notes
  frontend/      React + Vite UI
```

## Requirements

- Python 3.10+
- Node.js 18+ if you want to run the frontend
- An OpenAI API key or Anthropic API key for model-backed answers

## Backend Setup

```bash
git clone https://github.com/xr-susan/ResearchAgent.git
cd ResearchAgent

python -m venv venv
venv\Scripts\activate

pip install -r backend/requirements.txt
copy .env.example .env
```

Edit `.env` and set one provider:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your-key
OPENAI_MODEL=gpt-4o
```

or:

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-key
ANTHROPIC_MODEL=claude-sonnet-4-20250514
```

Start the API:

```bash
uvicorn backend.api.main:app --reload --port 8000
```

Open the API docs at `http://localhost:8000/docs`.

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

By default, the UI talks to `http://localhost:8000/api`. To point it somewhere else, create `frontend/.env`:

```env
VITE_API_BASE=http://localhost:8000/api
```

## CLI Usage

```bash
python -m cli.main
python -m cli.main -q "Summarize recent research on small language models"
python -m cli.main --server --port 8000
```

Useful interactive commands:

```text
/new      Start a new conversation
/history  Show current conversation stats
/clear    Clear in-memory context
/tools    List available tools
/quit     Exit
```

## API Examples

Send a chat message:

```python
import requests

response = requests.post(
    "http://localhost:8000/api/chat",
    json={"message": "Find three reliable sources about battery recycling."},
)

print(response.json()["message"])
```

Create a background research task:

```python
import requests

task = requests.post(
    "http://localhost:8000/api/tasks",
    json={
        "title": "Battery recycling overview",
        "task_type": "research",
        "params": {"topic": "battery recycling policy and market trends", "depth": "standard"},
    },
)

print(task.json()["id"])
```

Upload and analyze a file:

```python
import requests

with open("data.csv", "rb") as f:
    upload = requests.post("http://localhost:8000/api/upload", files={"file": f})

file_id = upload.json()["file_id"]
analysis = requests.post(
    f"http://localhost:8000/api/files/{file_id}/analyze",
    params={"question": "What are the main patterns in this file?"},
)

print(analysis.json()["analysis"])
```

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `LLM_PROVIDER` | `openai` or `anthropic` | `openai` |
| `OPENAI_API_KEY` | OpenAI key | unset |
| `OPENAI_MODEL` | OpenAI model | `gpt-4o` |
| `ANTHROPIC_API_KEY` | Anthropic key | unset |
| `ANTHROPIC_MODEL` | Anthropic model | `claude-sonnet-4-20250514` |
| `SEARCH_ENGINE` | `duckduckgo` or `serpapi` | `duckduckgo` |
| `SERPAPI_KEY` | Optional SerpAPI key | unset |
| `PORT` | API server port | `8000` |
| `MAX_CONCURRENT_TASKS` | Background task limit | `5` |
| `CACHE_TTL` | Search cache TTL in seconds | `3600` |
| `UPLOAD_DIR` | Uploaded file directory | `./data/uploads` |
| `REPORTS_DIR` | Report output directory | `./data/reports` |

## Testing

```bash
pytest
```

The tests use temporary SQLite databases and do not require a model API key for schema and storage checks.

## Notes

- Without an LLM API key, the API still starts and returns a setup message for agent calls.
- Generated files and the SQLite database live under `data/`, which is ignored by Git.
- Web search and scraping depend on external services and network access, so results can vary.

## License

MIT
