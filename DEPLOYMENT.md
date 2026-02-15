# Recall MCP Server - Deployment Guide

## Quick Start (Docker Compose)

### Prerequisites
- Docker Desktop installed and running
- OpenAI API key

### Setup Steps

1. **Clone and configure environment**
   ```bash
   git clone https://github.com/Keerthivasan-Venkitajalam/Recall.git
   cd Recall
   cp example.env .env
   # Edit .env and add your OPENAI_API_KEY
   ```

2. **Start services**
   ```bash
   docker-compose up -d
   ```

3. **Verify containers are running**
   ```bash
   docker-compose ps
   # Should show recall-api and recall-db with "Up" status
   ```

4. **Load sample data**
   ```bash
   docker exec recall-api python -m recall.scripts.load_data
   # Loads 27,458 F1 racing dataset rows
   ```

5. **Load knowledge base**
   ```bash
   docker exec recall-api python -m recall.scripts.load_knowledge
   # Loads table schemas, business rules, and query patterns
   ```

6. **Test the API**
   ```bash
   curl http://localhost:8000/health
   # Should return: {"status": "healthy", ...}
   ```

### API Endpoints

#### Core Endpoints
- `GET /` - Service information and endpoint list
- `GET /health` - Basic health check
- `GET /health/dependencies` - Detailed subsystem health (DB, vector stores, knowledge)
- `GET /auth/status` - Authentication configuration status

#### MCP Protocol Endpoints
- `GET /mcp/tools` - List available tools
- `POST /mcp/tools/ask_data_agent` - Ask natural language questions
- `POST /mcp/tools/save_verified_query` - Save validated SQL queries
- `GET /mcp/resources/schema` - Get database schema
- `GET /mcp/resources/learnings` - Get error patterns and fixes

### Example Requests

**Ask a question:**
```bash
curl -X POST http://localhost:8000/mcp/tools/ask_data_agent \
  -H "Content-Type: application/json" \
  -d '{"question": "Who won the most races in 2023?"}'
```

**Save a verified query:**
```bash
curl -X POST http://localhost:8000/mcp/tools/save_verified_query \
  -H "Content-Type: application/json" \
  -d '{
    "name": "top_race_winners",
    "question": "Who won the most races?",
    "query": "SELECT driver, COUNT(*) as wins FROM race_wins GROUP BY driver ORDER BY wins DESC LIMIT 10"
  }'
```

## Archestra Deployment

### Prerequisites
- Kubernetes cluster (Minikube, Docker Desktop K8s, or cloud provider)
- Archestra MCP Orchestra installed
- `kubectl` configured

### Deployment Steps

1. **Build and push Docker image**
   ```bash
   docker build -t your-registry/recall:v1.0.0 .
   docker push your-registry/recall:v1.0.0
   ```

2. **Create Kubernetes manifests**
   ```bash
   kubectl create namespace recall
   kubectl create secret generic recall-secrets \
     --from-literal=openai-api-key=$OPENAI_API_KEY \
     --namespace recall
   ```

3. **Deploy PostgreSQL (with persistence)**
   ```yaml
   # k8s/postgres.yaml
   apiVersion: v1
   kind: PersistentVolumeClaim
   metadata:
     name: recall-db-pvc
     namespace: recall
   spec:
     accessModes: [ReadWriteOnce]
     resources:
       requests:
         storage: 10Gi
   ---
   apiVersion: apps/v1
   kind: StatefulSet
   metadata:
     name: recall-db
     namespace: recall
   spec:
     serviceName: recall-db
     replicas: 1
     selector:
       matchLabels:
         app: recall-db
     template:
       metadata:
         labels:
           app: recall-db
       spec:
         containers:
         - name: postgres
           image: agnohq/pgvector:18
           env:
           - name: POSTGRES_USER
             value: ai
           - name: POSTGRES_PASSWORD
             value: ai
           - name: POSTGRES_DB
             value: ai
           ports:
           - containerPort: 5432
           volumeMounts:
           - name: data
             mountPath: /var/lib/postgresql
         volumes:
         - name: data
           persistentVolumeClaim:
             claimName: recall-db-pvc
   ---
   apiVersion: v1
   kind: Service
   metadata:
     name: recall-db
     namespace: recall
   spec:
     selector:
       app: recall-db
     ports:
     - port: 5432
   ```

4. **Deploy Recall MCP Server**
   ```yaml
   # k8s/recall-api.yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: recall-api
     namespace: recall
   spec:
     replicas: 2
     selector:
       matchLabels:
         app: recall-api
     template:
       metadata:
         labels:
           app: recall-api
       spec:
         containers:
         - name: recall
           image: your-registry/recall:v1.0.0
           env:
           - name: DB_HOST
             value: recall-db
           - name: DB_PORT
             value: "5432"
           - name: DB_USER
             value: ai
           - name: DB_PASS
             value: ai
           - name: DB_DATABASE
             value: ai
           - name: OPENAI_API_KEY
             valueFrom:
               secretKeyRef:
                 name: recall-secrets
                 key: openai-api-key
           - name: RUNTIME_ENV
             value: production
           - name: ENABLE_AUTH
             value: "true"
           - name: ARCHESTRA_OTEL_ENDPOINT
             value: "http://otel-collector:4318"
           ports:
           - containerPort: 8000
           livenessProbe:
             httpGet:
               path: /health
               port: 8000
             initialDelaySeconds: 30
             periodSeconds: 10
           readinessProbe:
             httpGet:
               path: /health/dependencies
               port: 8000
             initialDelaySeconds: 10
             periodSeconds: 5
   ---
   apiVersion: v1
   kind: Service
   metadata:
     name: recall-api
     namespace: recall
   spec:
     selector:
       app: recall-api
     ports:
     - port: 8000
   ```

5. **Apply manifests**
   ```bash
   kubectl apply -f k8s/postgres.yaml
   kubectl apply -f k8s/recall-api.yaml
   ```

6. **Initialize data (one-time)**
   ```bash
   kubectl exec -n recall deployment/recall-api -- python -m recall.scripts.load_data
   # If you want to use local Ollama `nomic-embed-text` for embeddings, set EMBEDDER_PROVIDER=nomic
   kubectl exec -n recall deployment/recall-api -- env EMBEDDER_PROVIDER=nomic python -m recall.scripts.load_knowledge
   # Or use local Ollama `phi` for text-only models (not embeddings):
   kubectl exec -n recall deployment/recall-api -- env EMBEDDER_PROVIDER=phi python -m recall.scripts.load_knowledge
   # Otherwise (default) the OpenAI embedder will be used
   kubectl exec -n recall deployment/recall-api -- python -m recall.scripts.load_knowledge
   ```

7. **Register with Archestra**
   ```bash
   # Create MCP service manifest
   cat > recall-mcp.json <<EOF
   {
     "name": "recall",
     "version": "1.0.0",
     "description": "Self-learning SQL agent",
     "transport": "streamable-http",
     "endpoint": "http://recall-api.recall:8000",
     "tools": [
       {
         "name": "ask_data_agent",
         "description": "Answers natural language questions about databases using SQL"
       },
       {
         "name": "save_verified_query",
         "description": "Saves validated SQL queries to knowledge base"
       }
     ],
     "resources": ["schema", "learnings"]
   }
   EOF
   
   # Register with Archestra
   kubectl apply -f - <<EOF
   apiVersion: mcp.archestra.ai/v1
   kind: MCPServer
   metadata:
     name: recall
     namespace: archestra-system
   spec:
     serviceRef:
       name: recall-api
       namespace: recall
       port: 8000
     manifestFile: recall-mcp.json
   EOF
   ```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | OpenAI API key for embeddings and LLM |
| `EMBEDDER_PROVIDER` | No | `openai` | Embedding provider: `openai` or `phi` (use `phi` for local Ollama) |
| `DB_HOST` | No | `localhost` | PostgreSQL host |
| `DB_PORT` | No | `5432` | PostgreSQL port |
| `DB_USER` | No | `ai` | Database user |
| `DB_PASS` | No | `ai` | Database password |
| `DB_DATABASE` | No | `ai` | Database name |
| `ENABLE_AUTH` | No | `false` | Enable bearer token validation |
| `ARCHESTRA_TOKEN_ENDPOINT` | No | - | Token validation endpoint URL |
| `ARCHESTRA_OTEL_ENDPOINT` | No | - | OpenTelemetry collector endpoint |
| `RUNTIME_ENV` | No | `dev` | Runtime environment (dev/production) |

### Authentication

**Development Mode (ENABLE_AUTH=false):**
- All requests accepted without authentication
- Suitable for local testing only

**Production Mode (ENABLE_AUTH=true):**
- Requires `Authorization: Bearer <token>` header
- Token validated against Archestra Gateway
- Whitelisted paths: `/health`, `/docs`, `/openapi.json`

### Security Policies

Configure in Archestra Gateway:

1. **Output Validation**
   - Block PII patterns in query results
   - Limit result sets to 1000 rows
   
2. **Input Sanitization**
   - Reject DELETE, DROP, TRUNCATE, ALTER in queries
   - Detect SQL injection attempts

3. **Dynamic Tools**
   - Full access in trusted context
   - Read-only mode in untrusted context

## Observability

### Health Checks

**Basic health:**
```bash
curl http://localhost:8000/health
```

**Detailed health:**
```bash
curl http://localhost:8000/health/dependencies
```

Returns:
```json
{
  "status": "healthy",
  "checks": {
    "postgres": "connected",
    "vector_db_knowledge": "accessible",
    "vector_db_learnings": "accessible",
    "knowledge_loaded": "14 items",
    "agent_initialized": "ready"
  }
}
```

### OpenTelemetry Traces

Configure OTEL endpoint to export traces:
```bash
export ARCHESTRA_OTEL_ENDPOINT=http://otel-collector:4318
```

**Trace Spans:**
- `mcp.request` - Overall request
- `dash.reasoning` - LLM planning
- `dash.sql_generation` - SQL query generation
- `dash.sql_execution` - Database execution
- `dash.learning` - Error correction loop

### Prometheus Metrics

Exposed at `/metrics`:
- `dash_queries_total` - Total queries processed
- `dash_query_errors` - Failed queries
- `dash_learnings_saved` - New error patterns learned
- `llm_token_usage` - Token consumption

### Logging

**Request Logging Format:**
```
→ POST /mcp/tools/ask_data_agent | agent=archestra-123 | ip=10.0.1.45 | duration=1.23s
← 200 OK | agent=archestra-123
✗ 500 Error | agent=archestra-123 | error=DatabaseError
```

**Custom Response Headers:**
- `X-Request-Duration-Ms` - Processing time
- `X-Agent-Id` - Archestra agent identifier
- `X-Request-Id` - Unique request ID

## Troubleshooting

### Container won't start
```bash
# Check logs
docker logs recall-api

# Common issues:
# - Missing OPENAI_API_KEY: Set in .env file
# - Database not ready: Wait 10s and retry
# - Port 8000 in use: Change in compose.yaml
```

### Knowledge loading fails
```bash
# Verify API key is valid
docker exec recall-api env | grep OPENAI_API_KEY

# Check vector tables exist
docker exec recall-db psql -U ai -d ai -c "\dt ai.*"

# Should show: recall_knowledge, recall_learnings
```

### "401 Unauthorized" errors
```bash
# Check auth configuration
curl http://localhost:8000/auth/status

# If ENABLE_AUTH=true, add bearer token:
curl -H "Authorization: Bearer <token>" http://localhost:8000/mcp/tools
```

### Learning not persisting
```bash
# Verify database volume is mounted
docker volume inspect dash_pgdata

# Check learnings table
docker exec recall-db psql -U ai -d ai -c "SELECT COUNT(*) FROM ai.recall_learnings;"
```

### High latency
```bash
# Check database connection
docker exec recall-api python -c "from db.session import SessionLocal; SessionLocal().execute('SELECT 1')"

# Review OTEL traces in Grafana
# Identify bottleneck: LLM call vs DB query vs vector search
```

## Performance Tuning

### Cold Start Optimization
- Pre-build Docker image with dependencies baked in
- Use readiness probe to delay traffic until knowledge loaded
- Consider vector index warming on startup

### Query Performance
- PostgreSQL connection pooling (default: 10 connections)
- Vector search optimization: HNSW index parameters
- Cache frequently accessed schema definitions

### Scaling
- Horizontal: Multiple replicas behind load balancer
- Vertical: Increase container memory for larger knowledge bases
- Database: Separate read replicas for vector searches

## Migration from Dash to Recall

If upgrading from original Dash:

1. **Rename tables**
   ```sql
   ALTER TABLE ai.dash_knowledge RENAME TO recall_knowledge;
   ALTER TABLE ai.dash_learnings RENAME TO recall_learnings;
   ```

2. **Update imports**
   ```bash
   # Already done in this version
   # from dash.agents -> from recall.agents
   ```

3. **Migrate configurations**
   - `.env` file compatible
   - No schema changes required

## Next Steps

- **Dev B**: Implement learning loop stress testing
- **Dev C**: Deploy to production Kubernetes cluster
- **Dev D**: Configure Grafana dashboards for observability
- **Integration**: Connect to Archestra Gateway for production use

## Support

- GitHub Issues: https://github.com/Keerthivasan-Venkitajalam/Recall/issues
- Documentation: See [README.md](README.md) and [CLAUDE.md](CLAUDE.md)
- Hackathon: 2 Fast 2 MCP @ WeMakeDevs
