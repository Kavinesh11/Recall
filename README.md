<div align="center">

# Recall

### The Self-Learning MCP Data Agent

**From natural language queries to SQL insights with 6 layers of context and automatic learning.**

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg?style=for-the-badge)](https://github.com/Keerthivasan-Venkitajalam/Recall)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-yellow?style=for-the-badge&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![MCP-Enabled](https://img.shields.io/badge/MCP-Enabled-purple?style=for-the-badge)](https://modelcontextprotocol.io)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker)](https://docker.com)

[About](#about-the-project) • [Architecture](#system-architecture) • [6 Layers](#the-6-layers-of-context) • [Getting Started](#getting-started) • [Tech Stack](#tech-stack) • [Demo](#live-demo)

</div>

---

## About the Project

**Recall** is a production-ready **Self-Learning MCP Data Agent** that delivers insights, not just SQL results. Inspired by OpenAI's internal data agent, Recall grounds every query in **6 layers of context** and improves automatically with every interaction.

Traditional SQL agents fail repeatedly on the same errors. They return raw SQL output that users still need to interpret. They lack observability into their reasoning process.

**Recall is different.** It treats errors as learning opportunities, synthesizes natural language insights from query results, and exposes every step of its pipeline for full transparency.

### Key Transformations

- **SQL to Insights**: No more raw query results. Get natural language answers with confidence scores.
- **Static to Self-Learning**: Dual learning system with curated knowledge + discovered patterns.
- **Opaque to Observable**: Real-time visualization of all 7 pipeline steps with expandable data views.
- **Error-Prone to Self-Correcting**: Automatic capture and prevention of errors through Learning Machine.

### Built for Hackathons, Ready for Production

Recall was built for the **"2 Fast 2 MCP"** hackathon with production-grade features:
- **OpenTelemetry traces** for observability
- **Prometheus metrics** for monitoring
- **Docker deployment** with health checks
- **Kubernetes configs** for scaling
- **ChatGPT-style UI** with process visualization

---

## System Architecture

Recall follows a **context-grounded agent architecture** where every SQL query is enriched with 6 layers of contextual knowledge before execution.

![Recall Architecture](Recall%20Architecture.png)

### Detailed Component Flow

```mermaid
graph TB
    subgraph "Frontend Layer"
        User[User] -->|Natural Language Query| UI[React UI]
        UI -->|Real-time Updates| ProcessMonitor[Process Monitor]
    end
    
    subgraph "API Layer"
        UI -->|POST /ask_data_agent| API[FastAPI Server]
        API -->|Health Checks| Health[/health/dependencies]
        API -->|OpenTelemetry| Traces[OTEL Collector]
    end
    
    subgraph "Agent Orchestration Core"
        API -->|MCP Protocol| Agent[Recall Agent]
        
        Agent -->|1. Parse| Parser[Query Parser]
        Parser -->|Intent & Entities| Context[Context Aggregator]
        
        subgraph "6 Layers of Context"
            Context -->|Layer 1| TableUsage[Table Usage Patterns]
            Context -->|Layer 2| BusinessRules[Business Rules]
            Context -->|Layer 3| QueryPatterns[Validated Queries]
            Context -->|Layer 4| InstKnowledge[Institutional Knowledge]
            Context -->|Layer 5| Learnings[Dynamic Learnings]
            Context -->|Layer 6| Runtime[Runtime Schema]
        end
        
        Context -->|Enriched Context| SQLGen[SQL Generator]
        SQLGen -->|Validated SQL| Executor[Query Executor]
        Executor -->|Results| Formatter[Insight Formatter]
    end
    
    subgraph "Data Layer"
        Executor -->|Execute| DB[(PostgreSQL)]
        
        subgraph "Dual Knowledge System"
            TableUsage -.->|Read| KnowledgeDB[Static Knowledge]
            BusinessRules -.->|Read| KnowledgeDB
            QueryPatterns -.->|Read| KnowledgeDB
            
            Learnings -.->|Read/Write| LearningsDB[Learning Machine]
        end
        
        KnowledgeDB -->|pgvector| VectorSearch[Semantic Search]
        LearningsDB -->|pgvector| VectorSearch
        VectorSearch -->|768-dim embeddings| Ollama[nomic-embed-text]
    end
    
    subgraph "LLM Infrastructure"
        SQLGen -->|Prompt| LLM[Mistral via Ollama]
        Formatter -->|Synthesize| LLM
        InstKnowledge -->|Web Research| Exa[Exa MCP]
        
        subgraph "Ollama Proxy"
            LLM -.->|HTTP API| Proxy[Host Proxy :5001]
            Ollama -.->|Embed| Proxy
        end
    end
    
    subgraph "Observability"
        Traces -->|Metrics| Prometheus[Prometheus]
        Prometheus -->|Visualize| Grafana[Grafana]
    end
    
    Formatter -->|Natural Language Answer| ProcessMonitor
    ProcessMonitor -->|7 Steps + Data| User
    
    classDef frontend fill:#3b82f6,stroke:#1e40af,stroke-width:2px,color:#fff;
    classDef api fill:#8b5cf6,stroke:#6d28d9,stroke-width:2px,color:#fff;
    classDef agent fill:#10b981,stroke:#059669,stroke-width:2px,color:#fff;
    classDef data fill:#f59e0b,stroke:#d97706,stroke-width:2px,color:#fff;
    classDef llm fill:#ec4899,stroke:#db2777,stroke-width:2px,color:#fff;
    
    class User,UI,ProcessMonitor frontend;
    class API,Health,Traces api;
    class Agent,Parser,Context,SQLGen,Executor,Formatter agent;
    class DB,KnowledgeDB,LearningsDB,VectorSearch data;
    class LLM,Ollama,Proxy,Exa llm;
```

---

## The 6 Layers of Context

**What makes Recall different:** Most SQL agents use 1-2 layers of context. Recall uses **6 distinct layers** that are semantically retrieved and combined at query time.

### Layer 1: Table Usage Patterns
**Source:** `recall/knowledge/tables/*.json`  
**What it contains:** Column definitions, data types, common join patterns, query frequency  
**Example:**
```json
{
  "table": "race_wins",
  "columns": ["driver_name", "race_name", "date"],
  "common_joins": ["drivers_championship"],
  "date_format": "DD Mon YYYY"
}
```

### Layer 2: Business Rules & Metrics
**Source:** `recall/knowledge/business/*.json`  
**What it contains:** Domain-specific logic, calculation formulas, aggregation rules  
**Example:**
```json
{
  "metric": "win_rate",
  "formula": "COUNT(wins) / COUNT(total_races)",
  "filters": ["WHERE position = 1"]
}
```

### Layer 3: Query Patterns
**Source:** `recall/knowledge/queries/*.sql`  
**What it contains:** Validated SQL queries that have worked in production  
**Why it matters:** Provides templates for similar queries, reducing errors

### Layer 4: Institutional Knowledge
**Source:** Exa MCP (web research)  
**What it contains:** Real-time web context, documentation, domain expertise  
**Use case:** Understanding context like "F1 2019 season" or "Lewis Hamilton"

### Layer 5: Dynamic Learnings
**Source:** Learning Machine (auto-discovered)  
**What it contains:** Error fixes, user preferences, discovered patterns  
**How it evolves:** Automatically captured and indexed after every query

### Layer 6: Runtime Context
**Source:** `introspect_schema` tool  
**What it contains:** Live database metadata, current schema state  
**Why it matters:** Handles schema changes without retraining

---

## Live Demo

### ChatGPT-Style Interface with Process Visualization

The frontend provides real-time visibility into every step of the agent's reasoning process:

**Features:**
- **ChatGPT-style UI** with dark theme and Inter font
- **7-Step Pipeline Visualization** with animated status indicators
- **Expandable Data Views** - click any step to see the actual data processed
- **Natural Language Responses** with SQL code blocks
- **Copy-to-Clipboard** for SQL queries
- **Chat History** with transcript download
- **Streaming Typing Effect** for realistic interaction

**The 7 Steps:**
1. **Parsing question** → Extracts intent and entities
2. **Searching knowledge base** → Retrieves 3-8 relevant documents
3. **Retrieving learnings** → Finds similar query patterns
4. **Introspecting schema** → Queries database metadata
5. **Generating SQL** → Creates validated query with all 6 context layers
6. **Executing query** → Runs SQL and returns results
7. **Formatting insights** → Synthesizes natural language answer

**Click any completed step to see:**
- Parsed entities and intent classification
- Knowledge documents retrieved with relevance scores
- Actual SQL generated with syntax highlighting
- Query execution results in JSON format
- Final insight with confidence score

---

## Tech Stack

**Recall is built on a modern, production-ready stack:**

### Core Intelligence
- **Agent Framework**: Agno MCP Framework
- **Integration Protocol**: Model Context Protocol (MCP)
- **LLM**: Mistral:latest via Ollama (self-hosted)
- **Embeddings**: nomic-embed-text (768-dimensional)

### Backend & API
- **Framework**: FastAPI with async/await
- **Language**: Python 3.12 with type hints
- **Data Validation**: Pydantic v2
- **Database**: PostgreSQL 18 + pgvector

### Knowledge Management
- **Vector Search**: pgvector with semantic similarity
- **Static Knowledge**: JSON files (tables, queries, business rules)
- **Dynamic Learnings**: Learning Machine with auto-indexing
- **Embedding Provider**: Ollama HTTP API with host proxy fallback

### Frontend
- **Framework**: React 18 with Vite 4
- **Styling**: Tailwind CSS 3.4 with custom dark theme
- **Fonts**: Inter (300-900 weights) with OpenType features
- **State Management**: React Hooks (useState, useEffect, useRef)

### Infrastructure
- **Deployment**: Docker Compose + Kubernetes
- **Observability**: OpenTelemetry + Prometheus + Grafana
- **Health Checks**: `/health/dependencies` with status monitoring
- **Proxy**: Custom Ollama proxy for Docker and host LLM communication

---

## Getting Started

### Prerequisites

- **Docker & Docker Compose** (for simplest setup)
- **Ollama** installed on host machine with these models:
  - `mistral:latest` (text generation)
  - `nomic-embed-text:latest` (embeddings)
- **Node.js 18+** (for frontend development)
- **Python 3.12+** (for backend development)

### Quick Start (Docker)

```bash
# 1. Clone the repository
git clone https://github.com/Keerthivasan-Venkitajalam/Recall.git
cd Recall

# 2. Configure environment
cp example.env .env
# Edit .env if needed (defaults work for local development)

# 3. Start Ollama models on host
ollama pull mistral:latest
ollama pull nomic-embed-text:latest

# 4. Start Ollama proxy (in separate terminal)
python scripts/ollama_proxy.py

# 5. Start backend services (PostgreSQL + API)
docker compose up -d --build

# 6. Load sample data (F1 racing dataset)
docker exec recall-api python -m recall.scripts.load_data

# 7. Load knowledge base
docker exec recall-api python -m recall.scripts.load_knowledge

# 8. Start frontend (in separate terminal)
cd web
npm install
npm run dev

# 9. Open browser
# http://localhost:5174/ (frontend)
# http://localhost:8000/docs (API docs)
```

### Verify Health

```bash
curl http://localhost:8000/health/dependencies | jq
```

Expected response:
```json
{
  "status": "healthy",
  "checks": {
    "database": { "status": "healthy" },
    "vector_db_knowledge": { "status": "healthy", "sample_count": 8 },
    "vector_db_learnings": { "status": "healthy" }
  }
}
```

---

## Configuration

Recall is configured via **environment variables** in `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `MODEL_PROVIDER` | LLM provider (mistral, openai) | `mistral` |
| `EMBEDDER_PROVIDER` | Embedding provider (nomic, openai) | `nomic` |
| `OLLAMA_BASE_URL` | Ollama API endpoint | `http://host.docker.internal:11434` |
| `OLLAMA_PROXY_URL` | Ollama proxy for Mistral | `http://host.docker.internal:5001` |
| `DB_HOST` | PostgreSQL host | `recall-db` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_NAME` | Database name | `ai` |
| `DB_USER` | Database user | `keerthi` |
| `DB_PASSWORD` | Database password | `*****` |
| `LOG_LEVEL` | Logging level | `INFO` |

### Docker Compose Configuration

The `compose.yaml` includes:
- **recall-api**: FastAPI backend with Agno MCP framework
- **recall-db**: PostgreSQL 18 with pgvector extension
- **Health checks** on both services
- **Persistent volumes** for database
- **Host network access** via `extra_hosts` for Ollama communication

---

## How the Dual Learning System Works

### Static Knowledge (Curated)
**Location:** `recall/knowledge/` directory  
**Managed by:** You (manual curation)  
**Contents:**
- Table schemas (5 F1 racing tables)
- Validated SQL queries  
- Business rules and metrics

**When to update:**
- Schema changes
- New common queries discovered
- Domain knowledge updates

### Dynamic Learnings (Discovered)
**Location:** `recall_learnings` database table  
**Managed by:** Learning Machine (automatic)  
**Contents:**
- Error patterns and fixes
- User preferences
- Type gotchas (e.g., "position is TEXT in some tables")
- Query performance insights

**How it works:**
1. User submits query
2. Agent processes with current knowledge
3. If error occurs → captured automatically
4. If query succeeds → patterns extracted
5. Learning saved to vector DB
6. Future similar queries use this learning

**Example Learning:**
```json
{
  "pattern": "date_parsing_f1",
  "context": "F1 race_wins table has dates as 'DD Mon YYYY' text format",
  "solution": "Use TO_DATE(date, 'DD Mon YYYY') for year extraction",
  "created_at": "2026-02-15T12:00:00Z"
}
```

---

## Development

### Project Structure

```text
recall/
├── agents.py                  # Recall and Reasoning agents
├── paths.py                   # Path constants
├── context/                   # Context layer implementations
│   ├── semantic_model.py     # Layer 1: Table usage
│   └── business_rules.py     # Layer 2: Business rules
├── tools/                     # Agent tools
│   ├── introspect.py         # Layer 6: Runtime context
│   └── save_query.py         # Save validated queries
├── scripts/
│   ├── load_data.py          # Load F1 sample data
│   ├── load_knowledge.py     # Load knowledge files
│   └── ollama_proxy.py       # Ollama HTTP proxy
├── knowledge/                 # Static knowledge files
│   ├── tables/               # Layer 1 schemas
│   ├── queries/              # Layer 3 patterns
│   └── business/             # Layer 2 rules
├── evals/
│   ├── test_cases.py         # Test cases with golden SQL
│   ├── grader.py             # LLM-based response grader
│   └── run_evals.py          # Run evaluations

web/
├── src/
│   ├── App.jsx               # Main React component
│   ├── main.jsx              # React entry point
│   └── styles.css            # Tailwind + custom styles
├── index.html                # HTML template
├── vite.config.js            # Vite configuration
├── tailwind.config.cjs       # Tailwind configuration
└── package.json              # Frontend dependencies

db/
├── session.py                # PostgreSQL session factory
└── url.py                    # Database URL builder

k8s/
└── base/                     # Kubernetes manifests
```

### Running Tests

```bash
# Backend tests
python -m recall.evals.run_evals              # All evals (string matching)
python -m recall.evals.run_evals -c basic     # Specific category
python -m recall.evals.run_evals -v           # Verbose mode
python -m recall.evals.run_evals -g           # Use LLM grader
python -m recall.evals.run_evals -r           # Compare against golden SQL results
python -m recall.evals.run_evals -g -r -v     # All modes combined

# Frontend (in web/ directory)
npm test                                     # Run tests
npm run build                                # Production build
```

### Code Quality

```bash
# Backend
./scripts/format.sh      # Format code (black, isort)
./scripts/validate.sh    # Lint + type check (ruff, mypy)

# Frontend
cd web
npm run lint             # ESLint
```

---

## Deployment

### Docker (Production)

```bash
# Build and deploy
docker compose -f compose.yaml up -d --build

# View logs
docker logs -f recall-api
docker logs -f recall-db

# Health check
curl http://localhost:8000/health/dependencies
```

### Kubernetes

```bash
# Apply configurations
kubectl apply -k k8s/base/

# Check status
kubectl get pods -n recall
kubectl logs -n recall deployment/recall-api

# Port forward for local access
kubectl port-forward -n recall svc/recall-api 8000:8000
```

---

## Advanced Use Cases

### 1. Complex Data Analysis

**Query:** *"Who won the most races in 2019?"*

**The Agentic Loop:**
1. **Parse**: Identifies intent (data_query), entities (race, winner, 2019)
2. **Knowledge Search**: Retrieves `race_wins.json`, `drivers_championship.json`
3. **Learnings**: Finds pattern about date parsing in F1 dataset
4. **Schema**: Confirms `race_wins` table structure
5. **SQL Gen**: Creates query with `TO_DATE(date, 'DD Mon YYYY')`
6. **Execute**: Returns `{ driver_name: 'Lewis Hamilton', wins: 11 }`
7. **Format**: "Lewis Hamilton won the most races in 2019 with 11 victories"

### 2. Self-Correction on Error

**Query:** *"Show me constructor standings for 2020"*

**Initial Attempt:**
- Generates SQL with `year = 2020`
- Executes → Error: "column 'year' does not exist"
- **Learning captures**: "Use `season` column, not `year`"

**Retry:**
- Updates SQL to use `season = 2020`
- Executes → Success
- **Learning saved**: Future queries automatically use correct column

### 3. Cross-Table Insights

**Query:** *"Which team had the fastest lap times in Monaco 2019?"*

**Context Aggregation:**
- Layer 1: Identifies need for `fastest_laps` + `race_results` join
- Layer 2: Business rule: "Monaco" = race_name filter
- Layer 3: Similar query pattern found
- Layer 4: Web context confirms Monaco Grand Prix details
- Result: Complex join executed correctly on first try

---

## Observability & Monitoring

### OpenTelemetry Traces

Every request generates a trace with spans:
- `recall.parse_query`
- `recall.search_knowledge`
- `recall.search_learnings`
- `recall.introspect_schema`  
- `recall.generate_sql`
- `recall.execute_query`
- `recall.format_insight`

### Prometheus Metrics

Available at `/metrics`:
```
# Query metrics
recall_queries_total{status="success",model="mistral"} 127
recall_query_duration_seconds_bucket{le="5.0"} 120
recall_query_errors_total{error_type="sql_syntax"} 3

# Knowledge metrics
recall_knowledge_searches_total{layer="table_usage"} 127
recall_knowledge_hits{layer="learnings"} 45

# LLM metrics
recall_llm_tokens_total{model="mistral",type="completion"} 52341
recall_llm_latency_seconds{model="mistral"} 2.5
```

### Grafana Dashboard

Import the pre-built dashboard for:
- Query throughput and success rate
- Latency percentiles (p50, p95, p99)
- Token usage and cost estimation
- Learning rate (how fast is it improving?)
- Knowledge layer hit rates

---

## Troubleshooting

| Issue | Solution |
| :--- | :--- |
| **"Ollama proxy unavailable"** | Start the proxy: `python scripts/ollama_proxy.py`. Ensure Ollama daemon is running on host. |
| **"Knowledge base empty"** | Run `docker exec recall-api python -m recall.scripts.load_knowledge` to index documents. |
| **"Frontend can't connect to API"** | Check `VITE_API_URL` in `web/.env`. Ensure backend is running on port 8000. |
| **"502 Mistral error"** | Verify Mistral model is pulled: `ollama list`. Check proxy logs for HTTP API errors. |
| **"Database connection failed"** | Check `DB_*` environment variables. Ensure recall-db container is healthy: `docker ps`. |
| **"Process monitor not expanding"** | Click on completed steps (green checkmark). Only completed steps have data. |

---

## Contributing

Contributions are welcome! Whether you're fixing bugs, adding new context layers, improving the UI, or enhancing documentation, your help is appreciated.

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add some amazing feature'`)
4. **Add tests** for new functionality
5. **Run** the eval suite (`python -m recall.evals.run_evals`)
6. **Push** to the branch (`git push origin feature/amazing-feature`)
7. **Open** a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines
- Write type hints for all functions
- Add docstrings for public APIs
- Update knowledge files when schema changes
- Keep commits atomic and well-described
- Test both backend and frontend changes

---

<div align="center">

## Developers

[Keerthivasan S V](https://github.com/Keerthivasan-Venkitajalam)
[Kavinesh](https://github.com/Kavinesh11)
[Sri Krishna Vundavalli](https://github.com/Sri-Krishna-V/)
[Sai Nivedh](https://github.com/SaiNivedh26)

**Recall** is a production-ready self-learning data agent built for the 2 Fast 2 MCP hackathon.

[Report Bug](https://github.com/Keerthivasan-Venkitajalam/Recall/issues) • [Request Feature](https://github.com/Keerthivasan-Venkitajalam/Recall/issues)

## License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with Agno MCP Framework
- Inspired by OpenAI's in-house data agent
- MCP integration follows the Model Context Protocol specification
- Learning Machine powered by pgvector semantic search
- Special thanks to the open-source community

---

Built for the 2 Fast 2 MCP Hackathon

</div>
