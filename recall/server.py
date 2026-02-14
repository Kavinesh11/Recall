"""
Recall MCP Server
===============

FastAPI-based MCP server for Archestra integration.
Exposes Recall agent capabilities via Model Context Protocol.

Run: uvicorn recall.server:app --host 0.0.0.0 --port 8000
Test: curl http://localhost:8000/mcp/tools
"""

import json
import logging
import time
from os import getenv
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from recall.agents import dash, dash_knowledge, dash_learnings
from recall.observability import (
    get_metrics,
    get_metrics_content_type,
    record_query_error,
    record_query_failure,
    record_query_success,
    refresh_learning_count,
    track_query_latency,
)
from recall.tools import create_save_validated_query_tool

# ============================================================================
# Logging Configuration
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

ENABLE_AUTH = getenv("ENABLE_AUTH", "false").lower() == "true"
ARCHESTRA_TOKEN_ENDPOINT = getenv("ARCHESTRA_TOKEN_ENDPOINT", "")
DEBUG_MODE = getenv("DEBUG_MODE", "false").lower() == "true"
VALID_TOKEN_PREFIX = "Bearer "
ARCHESTRA_AGENT_ID_HEADER = "X-Archestra-Agent-Id"
AUTH_WHITELIST = ["/health", "/health/dependencies", "/docs", "/openapi.json", "/redoc", "/metrics", "/"]

# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Recall MCP Server",
    description="Self-learning SQL agent for Archestra orchestration",
    version="1.0.0"
)

# ============================================================================
# CORS Middleware for MCP Clients
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Request/Response Models
# ============================================================================

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=5000, description="Natural language question")
    use_learning: bool = Field(default=True, description="Enable learning retrieval")
    run_id: Optional[str] = Field(default=None, max_length=100, description="Correlation ID for tracing")
    
    @field_validator('question')
    @classmethod
    def validate_question(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Question cannot be empty or whitespace")
        return v.strip()

class QueryResponse(BaseModel):
    result: str
    status: str = "success"

class SaveQueryRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Query identifier")
    question: str = Field(..., min_length=1, max_length=1000, description="Original question")
    query: str = Field(..., min_length=1, max_length=10000, description="SQL query")
    summary: Optional[str] = Field(default=None, max_length=500, description="Query description")
    tables_used: Optional[list[str]] = Field(default=None, description="Tables referenced")
    data_quality_notes: Optional[str] = Field(default=None, max_length=1000, description="Data quality issues")
    
    @field_validator('name', 'question', 'query')
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace")
        return v.strip()
    
    @field_validator('query')
    @classmethod
    def validate_query_safe(cls, v: str) -> str:
        query_lower = v.lower()
        if not (query_lower.strip().startswith('select') or query_lower.strip().startswith('with')):
            raise ValueError("Only SELECT or WITH queries are allowed")
        return v

# ============================================================================
# MCP Error Response Format
# ============================================================================

class MCPErrorResponse(BaseModel):
    error: str
    code: str
    details: Optional[dict] = None

# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Format HTTP exceptions as MCP error responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "code": f"HTTP_{exc.status_code}",
            "path": str(request.url.path)
        }
    )

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Format validation errors as MCP error responses."""
    return JSONResponse(
        status_code=400,
        content={
            "error": str(exc),
            "code": "VALIDATION_ERROR",
            "path": str(request.url.path)
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Format general exceptions as MCP error responses."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "code": "INTERNAL_ERROR",
            "path": str(request.url.path),
            "details": {"type": type(exc).__name__}
        }
    )

# ============================================================================
# Authentication Middleware
# ============================================================================

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """
    Enhanced authentication middleware with bearer token validation.
    
    Features:
    - Bearer token validation (when ENABLE_AUTH=true)
    - Request timing and performance tracking
    - Agent identity logging and propagation
    - Audit trail with client IP
    """
    # Skip auth for health/docs/metrics endpoints
    if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc", "/metrics"]:
        return await call_next(request)
    start_time = time.time()
    
    # Skip auth for whitelisted paths
    if request.url.path in AUTH_WHITELIST:
        response = await call_next(request)
        return response
    
    # Extract headers and client info
    agent_id = request.headers.get(ARCHESTRA_AGENT_ID_HEADER, "unknown")
    authorization = request.headers.get("Authorization", "")
    client_ip = request.client.host if request.client else "unknown"
    
    # Log incoming request with full context
    logger.info(
        f"→ {request.method} {request.url.path} | "
        f"Agent: {agent_id} | "
        f"IP: {client_ip} | "
        f"Auth: {'present' if authorization else 'missing'}"
    )
    
    # Validate authentication if enabled
    if ENABLE_AUTH:
        # Check bearer token format
        if not authorization:
            logger.warning(f"✗ Missing Authorization header | Agent: {agent_id} | Path: {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Missing Authorization header",
                    "code": "UNAUTHORIZED",
                    "path": str(request.url.path)
                },
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        if not authorization.startswith(VALID_TOKEN_PREFIX):
            logger.warning(f"✗ Invalid token format | Agent: {agent_id} | Path: {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": f"Invalid token format. Expected '{VALID_TOKEN_PREFIX}...'",
                    "code": "INVALID_TOKEN_FORMAT",
                    "path": str(request.url.path)
                },
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        token = authorization[len(VALID_TOKEN_PREFIX):]
        if not token or len(token) < 10:
            logger.warning(f"✗ Token too short | Agent: {agent_id} | Path: {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Token too short or empty",
                    "code": "INVALID_TOKEN",
                    "path": str(request.url.path)
                },
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # In production: validate token against Archestra's auth service
        if ARCHESTRA_TOKEN_ENDPOINT:
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        ARCHESTRA_TOKEN_ENDPOINT,
                        json={"token": token},
                        timeout=2.0
                    )
                    if response.status_code != 200:
                        logger.warning(f"✗ Token validation rejected by Archestra | Agent: {agent_id}")
                        return JSONResponse(status_code=401, content={"error": "Invalid token"})
            except Exception as e:
                logger.error(f"Token validation failed: {e}")
                # Fallback: if auth service is down, decide whether to fail open or closed.
                # For high security, fail closed:
                return JSONResponse(status_code=503, content={"error": "Auth service unavailable"})
        else:
             logger.info(f"Archestra token endpoint not configured, skipping remote validation for token ending in ...{token[-4:]}")
    
    # Warn if agent ID is missing in production
    if agent_id == "unknown" and ENABLE_AUTH:
        logger.warning(
            f"Missing {ARCHESTRA_AGENT_ID_HEADER} header | "
            f"Path: {request.url.path} | "
            f"IP: {client_ip}"
        )
    
    # Process request
    try:
        response = await call_next(request)
        
        # Calculate request duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log response with timing
        logger.info(
            f"← {response.status_code} | "
            f"Duration: {duration_ms:.2f}ms | "
            f"Agent: {agent_id}"
        )
        
        # Add custom headers for debugging and audit trail
        response.headers["X-Request-Duration-Ms"] = f"{duration_ms:.2f}"
        response.headers["X-Agent-Id"] = agent_id
        response.headers["X-Request-Id"] = f"{int(start_time * 1000)}"
        
        return response
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"✗ Request failed: {str(e)} | "
            f"Duration: {duration_ms:.2f}ms | "
            f"Agent: {agent_id} | "
            f"Path: {request.url.path}",
            exc_info=True
        )
        raise

# ============================================================================
# API Endpoints (MCP Tools)
# ============================================================================

@app.post("/mcp/tools/ask_data_agent", response_model=QueryResponse)
async def ask_data_agent(request: QueryRequest) -> QueryResponse:
    """
    Answers natural language questions about your database using SQL.
    
    The agent generates SQL queries, executes them, and provides insights.
    When errors occur, it self-corrects and persists the fix for future queries.
    """
    logger.info(f"[ask_data_agent] Question: {request.question[:100]}... | run_id={request.run_id}")
    
    with track_query_latency():
        try:
            response = await dash.arun(request.question)
            
            if hasattr(response, 'content'):
                result = response.content
            elif isinstance(response, str):
                result = response
            else:
                result = str(response)
            
            record_query_success()
            logger.info(f"[ask_data_agent] Success | run_id={request.run_id}")
            return QueryResponse(result=result, status="success")
            
        except Exception as e:
            record_query_failure()
            record_query_error(type(e).__name__)
            error_msg = f"Error processing question: {str(e)}"
            logger.error(f"[ask_data_agent] {error_msg} | run_id={request.run_id}", exc_info=True)
            raise HTTPException(status_code=500, detail=error_msg)
    try:
        # Run the agent with the question
        response = await dash.arun(request.question)
        
        # Extract content from response
        if hasattr(response, 'content'):
            result = response.content
        elif isinstance(response, str):
            result = response
        else:
            result = str(response)
        
        logger.info(f"[ask_data_agent] Success | run_id={request.run_id} | length={len(result)}")
        return QueryResponse(result=result, status="success")
        
    except Exception as e:
        error_msg = f"Agent execution failed: {str(e)}"
        logger.error(f"[ask_data_agent] {error_msg} | run_id={request.run_id}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=error_msg
        )


@app.post("/mcp/tools/save_verified_query")
async def save_verified_query(request: SaveQueryRequest) -> dict:
    """
    Saves a successful SQL query to the permanent knowledge base.
    
    Call this after a query executes successfully and produces useful results.
    The query becomes part of the agent's memory and can be retrieved for similar questions.
    """
    logger.info(f"[save_verified_query] Saving: {request.name}")
    
    try:
        # Use the existing tool from Recall
        save_tool = create_save_validated_query_tool(dash_knowledge)
        result = save_tool(
            name=request.name,
            question=request.question,
            query=request.query,
            summary=request.summary,
            tables_used=request.tables_used or [],
            data_quality_notes=request.data_quality_notes
        )
        logger.info(f"[save_verified_query] Result: {result}")
        return {
            "status": "success",
            "message": result,
            "query_name": request.name
        }
    except Exception as e:
        error_msg = f"Failed to save query: {str(e)}"
        logger.error(f"[save_verified_query] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=error_msg
        )


# ============================================================================
# MCP Resources
# ============================================================================

@app.get("/mcp/resources/schema")
async def get_schema() -> dict[str, Any]:
    """
    Returns the current database schema tracked by Recall.
    
    This includes table names, column definitions, foreign keys,
    and any human annotations about the semantic meaning of tables.
    """
    try:
        # Query the knowledge base for schema information
        schema_docs = dash_knowledge.search(
            query="table schema columns structure",
            limit=50
        )
        
        schema_info = {
            "type": "schema",
            "description": "Database schema tracked by Recall",
            "tables": []
        }
        
        if schema_docs:
            for doc in schema_docs:
                if hasattr(doc, 'content') and doc.content:
                    try:
                        content = json.loads(doc.content) if isinstance(doc.content, str) else doc.content
                        if isinstance(content, dict) and content.get('type') == 'table':
                            schema_info['tables'].append(content)
                    except (json.JSONDecodeError, TypeError):
                        continue
        
        return schema_info
        
    except Exception as e:
        logger.error(f"Error retrieving schema: {e}", exc_info=True)
        return {
            "type": "error",
            "message": f"Error retrieving schema: {str(e)}"
        }


@app.get("/mcp/resources/learnings")
async def get_learnings() -> dict[str, Any]:
    """
    Returns error patterns and fixes discovered by the Learning Machine.
    
    This shows how Recall has evolved through self-correction:
    - Type mismatches discovered
    - Data quality gotchas found
    - Date format patterns learned
    """
    try:
        # Query the learnings knowledge base
        learning_docs = dash_learnings.search(
            query="error pattern fix learning",
            limit=100
        )
        
        learnings_info = {
            "type": "learnings",
            "description": "Error patterns and fixes discovered by Recall",
            "count": len(learning_docs) if learning_docs else 0,
            "recent_learnings": []
        }
        
        if learning_docs:
            for doc in learning_docs[:20]:  # Show most recent 20
                if hasattr(doc, 'content'):
                    try:
                        content = json.loads(doc.content) if isinstance(doc.content, str) else doc.content
                        learnings_info['recent_learnings'].append(content)
                    except (json.JSONDecodeError, TypeError):
                        learnings_info['recent_learnings'].append({"raw": str(doc.content)})
        
        return learnings_info
        
    except Exception as e:
        logger.error(f"Error retrieving learnings: {e}", exc_info=True)
        return {
            "type": "error",
            "message": f"Error retrieving learnings: {str(e)}"
        }

# ============================================================================
# Additional Endpoints
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint for Kubernetes liveness/readiness probes."""
    return {
        "status": "healthy",
        "service": "recall-mcp-server",
        "version": "1.0.0",
        "timestamp": time.time()
    }

@app.get("/health/dependencies")
async def health_dependencies():
    """
    Comprehensive dependency health check for monitoring.
    
    Checks:
    - PostgreSQL connection
    - Vector database availability
    - Knowledge base loaded status
    - Learning machine initialized
    """
    checks = {}
    overall_status = "healthy"
    
    # Check database connection
    try:
        from db import db_url
        from sqlalchemy import create_engine, text
        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            checks["database"] = {"status": "healthy", "url": db_url.split("@")[-1]}  # Hide credentials
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        overall_status = "degraded"
    
    # Check vector database (pgvector)
    try:
        if dash_knowledge.vector_db:
            # Try to check if table exists
            checks["vector_db_knowledge"] = {"status": "healthy", "table": "recall_knowledge"}
        else:
            checks["vector_db_knowledge"] = {"status": "not_configured"}
            overall_status = "degraded"
    except Exception as e:
        checks["vector_db_knowledge"] = {"status": "unhealthy", "error": str(e)}
        overall_status = "degraded"
    
    # Check learnings vector database
    try:
        if dash_learnings.vector_db:
            checks["vector_db_learnings"] = {"status": "healthy", "table": "recall_learnings"}
        else:
            checks["vector_db_learnings"] = {"status": "not_configured"}
    except Exception as e:
        checks["vector_db_learnings"] = {"status": "unhealthy", "error": str(e)}
        overall_status = "degraded"
    
    # Check if knowledge base has content
    try:
        # Simple check - try to search
        results = dash_knowledge.search(query="test", limit=1)
        knowledge_count = len(results) if results else 0
        checks["knowledge_loaded"] = {
            "status": "healthy" if knowledge_count > 0 else "empty",
            "sample_count": knowledge_count
        }
        if knowledge_count == 0:
            overall_status = "degraded"
    except Exception as e:
        checks["knowledge_loaded"] = {"status": "error", "error": str(e)}
        overall_status = "degraded"
    
    # Check agent initialization
    try:
        checks["agent"] = {
            "status": "healthy",
            "name": dash.name if hasattr(dash, 'name') else "unknown",
            "model": str(dash.model.id) if hasattr(dash, 'model') else "unknown"
        }
    except Exception as e:
        checks["agent"] = {"status": "unhealthy", "error": str(e)}
        overall_status = "degraded"
    
    return {
        "status": overall_status,
        "checks": checks,
        "timestamp": time.time()
    }

@app.get("/auth/status")
async def auth_status():
    """Return current authentication configuration (for debugging)."""
    return {
        "enabled": ENABLE_AUTH,
        "token_prefix": VALID_TOKEN_PREFIX,
        "agent_id_header": ARCHESTRA_AGENT_ID_HEADER,
        "whitelisted_paths": AUTH_WHITELIST,
        "validation_endpoint_configured": bool(ARCHESTRA_TOKEN_ENDPOINT)
    }


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint for observability.
    
    Exposes:
    - dash_queries_total: Total queries processed
    - dash_query_errors: Query errors by type
    - dash_learnings_saved: Learnings saved by type
    - dash_learnings_total: Current total learnings
    - dash_query_latency_seconds: Query latency histogram
    - llm_token_usage: LLM token usage histogram
    """
    await refresh_learning_count()
    return Response(
        content=get_metrics(),
        media_type=get_metrics_content_type()
    )


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Recall MCP Server",
        "version": "1.0.0",
        "description": "Self-learning SQL agent for Archestra",
        "auth_enabled": ENABLE_AUTH,
        "endpoints": {
            "health": "/health",
            "metrics": "/metrics",
            "health_dependencies": "/health/dependencies",
            "auth_status": "/auth/status",
            "ask_data_agent": "/mcp/tools/ask_data_agent",
            "save_verified_query": "/mcp/tools/save_verified_query",
            "schema": "/mcp/resources/schema",
            "learnings": "/mcp/resources/learnings",
            "docs": "/docs"
        }
    }

@app.get("/mcp/tools")
async def list_tools():
    """List available MCP tools."""
    return {
        "tools": [
            {
                "name": "ask_data_agent",
                "description": "Answers natural language questions about your database using SQL",
                "endpoint": "/mcp/tools/ask_data_agent",
                "method": "POST"
            },
            {
                "name": "save_verified_query",
                "description": "Saves a successful SQL query to the permanent knowledge base",
                "endpoint": "/mcp/tools/save_verified_query",
                "method": "POST"
            }
        ]
    }

# ============================================================================
# Development Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(getenv("PORT", "8000"))
    logger.info(f"Starting Recall MCP Server on port {port}")
    
    uvicorn.run(
        "recall.server:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
