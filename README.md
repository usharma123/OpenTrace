# OpenTrace - Live App Flow Investigator

A full-stack application that visualizes application execution flows as interactive graphs using OpenTelemetry tracing. Point at a GitHub repo, and the system will clone it, auto-instrument it, run it, and visualize the traces.

![OpenTrace Architecture](https://via.placeholder.com/800x400?text=OpenTrace+Architecture)

## Features

- **Runtime Trace Visualization**: Convert OpenTelemetry traces into interactive ReactFlow graphs
- **GitHub Repo Analysis**: Clone any Python/Node.js repo, auto-instrument it with OTel, and run it
- **AI-Powered Agent**: Ask questions about traces, find bottlenecks, identify errors
- **Demo Endpoints**: Generate interesting traces with various patterns (slow, parallel, errors)
- **Docker-First**: One command boots everything

## Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/opentrace.git
cd opentrace

# Copy environment file
cp .env.example .env

# Start all services
docker compose up --build
```

### Access Points

| Service | URL | Description |
|---------|-----|-------------|
| Web UI | http://localhost:5173 | Main application |
| API | http://localhost:8000 | Backend API |
| Agent | http://localhost:8081 | AI agent service |
| Jaeger UI | http://localhost:16686 | Trace explorer |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Frontend (React + ReactFlow)                   │
│                           Port: 5173                                │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│      API Service         │    │     Agent Service        │
│       (FastAPI)          │    │      (FastAPI)           │
│       Port: 8000         │    │      Port: 8081          │
└──────────────────────────┘    └──────────────────────────┘
            │
            ▼
┌──────────────────────────┐
│      Jaeger All-in-One   │
│   OTLP: 4317 | UI: 16686 │
└──────────────────────────┘
```

## Usage Guide

### 1. Generate a Demo Trace

Click the **"Record Trace"** button in the top-right corner and select a demo endpoint:

- **Fast**: Instant response
- **Slow**: 300-800ms delay
- **External**: HTTP call to external API
- **Database**: Simulated DB query
- **Chain**: Nested operations (great for visualizing depth)
- **Parallel**: Fan-out pattern with multiple workers
- **Error**: Intentional 500 error

### 2. View the Trace

1. The new trace will appear in the left sidebar
2. Click on it to load the visualization
3. Spans are displayed as nodes with duration and status
4. Edges show parent-child relationships

### 3. Ask the AI Agent

Open the chat panel (bottom-right) and ask questions:

- **"What's slow?"** - Identifies bottlenecks and highlights slow spans
- **"Any errors?"** - Finds error spans and explains what failed
- **"Explain this trace"** - Provides a summary of the request flow
- **"Record /demo/slow"** - Triggers a new trace (requires approval)

### 4. Analyze External Repos

Enter a GitHub URL in the header input and click "Analyze":

```
https://github.com/tiangolo/fastapi
```

The system will:
1. Clone the repository
2. Detect the language (Python/Node.js)
3. Find the entry point
4. Generate an instrumented Dockerfile
5. Build and run the container with OTel tracing

## Environment Variables

```bash
# .env file

# OpenRouter API Key (optional - enables LLM-powered agent)
# Get your key at https://openrouter.ai/keys
OPENROUTER_API_KEY=sk-or-...

# Model to use with OpenRouter
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet

# Require UI approval before recording new traces
APPROVAL_REQUIRED=true
```

### Without an LLM Key

The agent works without an API key using rule-based analysis:
- Identifies slowest spans by duration
- Finds error spans by tags
- Calculates critical path
- Generates human-readable summaries

## API Reference

### Flows

```bash
# Get runtime flow for a trace
GET /flows/runtime/{trace_id}

# Get static architecture graph
GET /flows/static
```

### Traces

```bash
# Search recent traces
GET /traces/search?service=...&lookback=1h&limit=20

# Get trace details
GET /traces/{trace_id}

# Get trace analysis
GET /traces/{trace_id}/analysis
```

### Recording

```bash
# Record a new trace
POST /record
{
  "method": "GET",
  "path": "/demo/slow"
}
```

### Repos

```bash
# Analyze a GitHub repo
POST /repos/analyze
{
  "githubUrl": "https://github.com/user/repo"
}

# Get repo status
GET /repos/{repo_id}

# Start repo container
POST /repos/{repo_id}/start

# Stop repo container
POST /repos/{repo_id}/stop
```

### Agent

```bash
# Chat with the agent
POST /chat
{
  "message": "what's slow?",
  "selectedTraceId": "abc123..."
}
```

## Project Structure

```
/
├── docker-compose.yml      # Docker orchestration
├── .env.example            # Environment template
│
├── api/                    # Backend API service
│   ├── app/
│   │   ├── main.py         # FastAPI application
│   │   ├── jaeger_client.py
│   │   ├── trace_to_graph.py
│   │   ├── demo/routes.py
│   │   └── repo_analyzer/
│   └── Dockerfile
│
├── agent/                  # AI agent service
│   ├── app/
│   │   ├── main.py
│   │   ├── openrouter.py
│   │   ├── tools.py
│   │   ├── planner.py
│   │   └── fallback.py
│   └── Dockerfile
│
└── web/                    # React frontend
    ├── src/
    │   ├── App.tsx
    │   ├── api.ts
    │   ├── components/
    │   │   ├── FlowCanvas.tsx
    │   │   ├── ChatPanel.tsx
    │   │   └── ...
    │   └── graph/
    │       ├── layout.ts   # Dagre layout
    │       └── nodes/
    └── Dockerfile
```

## Development

### Running Locally

```bash
# Start infrastructure only
docker compose up jaeger -d

# Run API locally
cd api
pip install -r requirements.txt
uvicorn app.main:app --reload

# Run Agent locally
cd agent
pip install -r requirements.txt
uvicorn app.main:app --port 8081 --reload

# Run Frontend locally
cd web
npm install
npm run dev
```

### Running Tests

```bash
# API tests
cd api
pytest app/tests/

# Type check frontend
cd web
npm run build
```

## Tech Stack

- **Backend**: FastAPI (Python 3.11)
- **Frontend**: Vite + React + ReactFlow
- **Observability**: OpenTelemetry + Jaeger
- **AI**: OpenRouter (Claude, GPT, etc.)
- **Layout**: Dagre.js
- **Container**: Docker + Docker Compose

## Troubleshooting

### Traces not appearing

1. Check Jaeger is running: http://localhost:16686
2. Verify the API service has `jaegerConnected: true` at `/health`
3. Wait a few seconds - traces take time to index

### Agent not responding

1. Check agent health: http://localhost:8081/health
2. If `llm_available: false`, the system uses fallback analysis
3. Add an `OPENROUTER_API_KEY` for AI-powered responses

### Repo analysis failing

1. Ensure Docker socket is mounted (check docker-compose.yml)
2. Check the repo has `requirements.txt` (Python) or `package.json` (Node.js)
3. View container logs: `docker compose logs api`

## License

MIT

## Contributing

Contributions welcome! Please read the contributing guidelines first.
