# ResearchAgent API Documentation

## Base URL
```
http://localhost:8000
```

## Authentication
Currently, the API does not require authentication. In production, add API key authentication.

## Endpoints

### Health Check

#### `GET /health`

Check the API health status.

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "uptime_seconds": 123.45,
  "active_conversations": 5,
  "active_tasks": 2
}
```

---

### Chat

#### `POST /api/chat`

Send a message to the research agent and receive a response.

**Request Body:**
```json
{
  "message": "What are the latest AI trends?",
  "conversation_id": null,
  "stream": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| message | string | Yes | User message (1-10000 chars) |
| conversation_id | string | No | Existing conversation ID for context |
| stream | bool | No | Enable streaming (default: false) |

**Response:**
```json
{
  "conversation_id": "uuid-string",
  "message": "Here are the latest AI trends...",
  "tool_calls": [],
  "metadata": {
    "model": "gpt-4o"
  }
}
```

#### `POST /api/chat/stream`

Stream a response using Server-Sent Events (SSE).

**Request:** Same as `/api/chat`

**Response:** SSE stream
```
data: {"type": "token", "content": "Here are...", "tool_name": null, "metadata": {}}

data: {"type": "done", "content": "", "tool_name": null, "metadata": {"conversation_id": "..."}}
```

---

### Conversations

#### `GET /api/conversations`

List all conversations.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| limit | int | 50 | Max results |
| offset | int | 0 | Pagination offset |

**Response:**
```json
[
  {
    "id": "uuid",
    "title": "AI Trends Research",
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T01:00:00",
    "metadata": {}
  }
]
```

#### `POST /api/conversations`

Create a new conversation.

**Request Body:**
```json
{
  "title": "My Research Session"
}
```

#### `GET /api/conversations/{id}`

Get conversation with full message history.

**Response:**
```json
{
  "id": "uuid",
  "title": "AI Trends Research",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T01:00:00",
  "message_count": 10,
  "messages": [
    {
      "id": "msg-uuid",
      "conversation_id": "uuid",
      "role": "user",
      "content": "What are AI trends?",
      "created_at": "2024-01-01T00:00:00",
      "metadata": {}
    }
  ]
}
```

#### `DELETE /api/conversations/{id}`

Delete a conversation and all its messages.

---

### Tasks

#### `POST /api/tasks`

Create an asynchronous research task.

**Request Body:**
```json
{
  "title": "AI Industry Analysis",
  "task_type": "research",
  "params": {
    "topic": "AI industry trends 2024",
    "depth": "deep"
  },
  "conversation_id": null
}
```

| task_type | Description | Required params |
|-----------|-------------|-----------------|
| research | Web research task | topic, depth (quick/standard/deep) |
| analyze_file | File analysis | file_path, question |
| generate_report | Report generation | topic, findings, format |

#### `GET /api/tasks`

List tasks with optional status filter.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| status | string | Filter: pending/running/completed/failed/cancelled |
| limit | int | Max results (default: 50) |

#### `GET /api/tasks/{id}`

Get task status and result.

**Response:**
```json
{
  "id": "uuid",
  "title": "AI Industry Analysis",
  "status": "completed",
  "result": "Comprehensive analysis...",
  "created_at": "2024-01-01T00:00:00",
  "started_at": "2024-01-01T00:00:01",
  "completed_at": "2024-01-01T00:02:30"
}
```

#### `POST /api/tasks/{id}/cancel`

Cancel a running task.

---

### Files

#### `POST /api/upload`

Upload a file for analysis.

**Request:** `multipart/form-data`

| Field | Type | Description |
|-------|------|-------------|
| file | file | File to upload (PDF/CSV/Excel/TXT/JSON/MD) |

**Response:**
```json
{
  "file_id": "uuid",
  "filename": "data.csv",
  "file_path": "/uploads/uuid.csv",
  "size_bytes": 1024,
  "content_type": "text/csv"
}
```

#### `GET /api/files`

List all uploaded files.

#### `POST /api/files/{file_id}/analyze`

Analyze an uploaded file.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| question | string | Question about the file |

#### `GET /api/reports`

List generated reports.

#### `GET /api/reports/{filename}`

Get a specific report.

---

## Error Responses

All endpoints return standard error format:

```json
{
  "error": "Error message",
  "detail": "Detailed error information",
  "status_code": 400
}
```

Common status codes:
- `400` - Bad request
- `404` - Resource not found
- `413` - File too large
- `500` - Internal server error
