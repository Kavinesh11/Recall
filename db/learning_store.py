"""
Learning Persistence Module
===========================

Handles storage and retrieval of learnings with vector embeddings.
Uses PostgreSQL + pgvector for persistence across restarts.
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError, IntegrityError, OperationalError
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

try:
    from recall.observability.metrics import track_vector_search_latency
except ImportError:
    from contextlib import contextmanager

    @contextmanager  # type: ignore[misc]
    def track_vector_search_latency(search_type: str = "hybrid"):  # type: ignore[misc]
        yield


@dataclass
class Learning:
    """Represents a discovered error pattern and its fix."""
    id: int | None
    title: str
    error_pattern: str
    fix_description: str
    error_type: str | None = None
    tables_involved: list[str] | None = None
    embedding: list[float] | None = None
    created_at: datetime | None = None
    usage_count: int = 0
    success_rate: float = 1.0
    similarity: float | None = None


@dataclass
class SchemaInfo:
    """Represents table schema information."""
    id: int | None
    table_name: str
    table_description: str | None
    columns: list[dict]
    use_cases: list[str] | None = None
    data_quality_notes: list[str] | None = None
    embedding: list[float] | None = None


class LearningStore:
    """
    Persistent storage for agent learnings using PostgreSQL + pgvector.
    
    Features:
    - Vector similarity search for finding relevant learnings
    - Deduplication using cosine similarity threshold
    - Advisory locks for concurrent write safety
    - HNSW indexing for fast retrieval
    """
    
    SIMILARITY_THRESHOLD = 0.95
    DEFAULT_SEARCH_LIMIT = 5
    MIN_SIMILARITY = 0.7
    
    def __init__(self, db_url: str, embedder=None):
        """
        Initialize learning store.
        
        Args:
            db_url: PostgreSQL connection URL
            embedder: Embedding function (query -> vector)
        """
        self.db_url = db_url
        self.embedder = embedder
        self.engine = create_engine(
            db_url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
    
    def _get_embedding(self, text: str) -> list[float]:
        """Get embedding vector for text."""
        if self.embedder is None:
            raise ValueError("Embedder not configured")
        return self.embedder(text)
    
    def _compute_text_hash(self, text: str) -> str:
        """Compute hash for deduplication."""
        return hashlib.sha256(text.encode()).hexdigest()[:32]
    
    def save_learning(
        self,
        title: str,
        error_pattern: str,
        fix_description: str,
        error_type: str | None = None,
        tables_involved: list[str] | None = None,
        skip_if_duplicate: bool = True,
    ) -> tuple[bool, str]:
        """
        Save a learning to the database.
        
        Args:
            title: Short title describing the learning
            error_pattern: The error pattern that was encountered
            fix_description: How the error was fixed
            error_type: Category of error (e.g., 'type_mismatch', 'date_format')
            tables_involved: Database tables related to this learning
            skip_if_duplicate: Skip if similar learning exists (cosine > 0.95)
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            combined_text = f"{title}\n{error_pattern}\n{fix_description}"
            embedding = self._get_embedding(combined_text)
            
            with self.engine.connect() as conn:
                conn.execute(text("SELECT pg_advisory_lock(hashtext('recall_learning_write'))"))
                
                try:
                    if skip_if_duplicate:
                        result = conn.execute(
                            text("""
                                SELECT check_learning_duplicate(:embedding::vector, :threshold)
                            """),
                            {
                                "embedding": str(embedding),
                                "threshold": self.SIMILARITY_THRESHOLD,
                            }
                        )
                        is_duplicate = result.scalar()
                        
                        if is_duplicate:
                            logger.info(f"Skipping duplicate learning: {title}")
                            return False, "Similar learning already exists"
                    
                    tables_array = (
                        "{" + ",".join(f'"{t}"' for t in tables_involved) + "}"
                        if tables_involved else None
                    )
                    
                    conn.execute(
                        text("""
                            INSERT INTO recall_learnings 
                                (title, error_pattern, fix_description, error_type, 
                                 tables_involved, embedding)
                            VALUES 
                                (:title, :error_pattern, :fix_description, :error_type,
                                 :tables_involved, :embedding::vector)
                        """),
                        {
                            "title": title,
                            "error_pattern": error_pattern,
                            "fix_description": fix_description,
                            "error_type": error_type,
                            "tables_involved": tables_array,
                            "embedding": str(embedding),
                        }
                    )
                    conn.commit()
                    logger.info(f"Saved learning: {title}")
                    return True, f"Learning saved: {title}"
                    
                finally:
                    conn.execute(text("SELECT pg_advisory_unlock(hashtext('recall_learning_write'))"))
                    
        except IntegrityError as e:
            logger.error(f"Integrity error saving learning: {e}")
            return False, f"Database constraint error: {e}"
        except OperationalError as e:
            logger.error(f"Database connection error: {e}")
            return False, f"Database connection error: {e}"
        except Exception as e:
            logger.error(f"Unexpected error saving learning: {e}")
            return False, f"Error: {e}"
    
    def retrieve_learnings(
        self,
        query: str,
        limit: int | None = None,
        min_similarity: float | None = None,
    ) -> list[Learning]:
        """
        Retrieve relevant learnings using vector similarity search.
        
        Args:
            query: The query or error message to find learnings for
            limit: Maximum number of results
            min_similarity: Minimum similarity threshold (0-1)
        
        Returns:
            List of Learning objects sorted by relevance
        """
        limit = limit or self.DEFAULT_SEARCH_LIMIT
        min_similarity = min_similarity or self.MIN_SIMILARITY
        
        try:
            embedding = self._get_embedding(query)
            
            with track_vector_search_latency("hybrid"):
                with self.engine.connect() as conn:
                    result = conn.execute(
                        text("""
                            SELECT * FROM search_similar_learnings(
                                :embedding::vector,
                                :limit,
                                :min_similarity
                            )
                        """),
                        {
                            "embedding": str(embedding),
                            "limit": limit,
                            "min_similarity": min_similarity,
                        }
                    )
                    
                    learnings = []
                    for row in result:
                        learnings.append(Learning(
                            id=row.id,
                            title=row.title,
                            error_pattern=row.error_pattern,
                            fix_description=row.fix_description,
                            similarity=row.similarity,
                        ))
                    
                    return learnings
                
        except OperationalError as e:
            logger.error(f"Database connection error: {e}")
            return []
        except Exception as e:
            logger.error(f"Error retrieving learnings: {e}")
            return []
    
    def increment_usage(self, learning_id: int, success: bool = True) -> None:
        """
        Increment usage count and update success rate for a learning.
        
        Args:
            learning_id: ID of the learning
            success: Whether the learning led to successful query
        """
        try:
            with self.engine.connect() as conn:
                if success:
                    conn.execute(
                        text("""
                            UPDATE recall_learnings
                            SET usage_count = usage_count + 1,
                                success_rate = (success_rate * usage_count + 1) / (usage_count + 1)
                            WHERE id = :id
                        """),
                        {"id": learning_id}
                    )
                else:
                    conn.execute(
                        text("""
                            UPDATE recall_learnings
                            SET usage_count = usage_count + 1,
                                success_rate = (success_rate * usage_count) / (usage_count + 1)
                            WHERE id = :id
                        """),
                        {"id": learning_id}
                    )
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating usage count: {e}")
    
    def get_learning_count(self) -> int:
        """Get total number of learnings in the database."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM recall_learnings"))
                return result.scalar() or 0
        except Exception as e:
            logger.error(f"Error getting learning count: {e}")
            return 0
    
    def get_learnings_by_error_type(self, error_type: str) -> list[Learning]:
        """Get all learnings of a specific error type."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT id, title, error_pattern, fix_description, 
                               error_type, tables_involved, usage_count, success_rate
                        FROM recall_learnings
                        WHERE error_type = :error_type
                        ORDER BY usage_count DESC, success_rate DESC
                    """),
                    {"error_type": error_type}
                )
                
                return [
                    Learning(
                        id=row.id,
                        title=row.title,
                        error_pattern=row.error_pattern,
                        fix_description=row.fix_description,
                        error_type=row.error_type,
                        tables_involved=row.tables_involved,
                        usage_count=row.usage_count,
                        success_rate=row.success_rate,
                    )
                    for row in result
                ]
        except Exception as e:
            logger.error(f"Error getting learnings by type: {e}")
            return []


class SchemaStore:
    """
    Persistent storage for database schema information.
    """
    
    def __init__(self, db_url: str, embedder=None):
        self.db_url = db_url
        self.embedder = embedder
        self.engine = create_engine(db_url, pool_pre_ping=True)
    
    def _get_embedding(self, text: str) -> list[float]:
        """Get embedding vector for text."""
        if self.embedder is None:
            raise ValueError("Embedder not configured")
        return self.embedder(text)
    
    def save_schema(self, schema_info: SchemaInfo) -> tuple[bool, str]:
        """
        Save or update schema information.
        
        Args:
            schema_info: SchemaInfo object with table details
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            combined_text = f"{schema_info.table_name}\n{schema_info.table_description or ''}"
            if schema_info.use_cases:
                combined_text += "\n" + "\n".join(schema_info.use_cases)
            if schema_info.data_quality_notes:
                combined_text += "\n" + "\n".join(schema_info.data_quality_notes)
            
            embedding = self._get_embedding(combined_text)
            
            use_cases_array = (
                "{" + ",".join(f'"{u}"' for u in schema_info.use_cases) + "}"
                if schema_info.use_cases else None
            )
            quality_notes_array = (
                "{" + ",".join(f'"{n}"' for n in schema_info.data_quality_notes) + "}"
                if schema_info.data_quality_notes else None
            )
            
            with self.engine.connect() as conn:
                conn.execute(
                    text("""
                        INSERT INTO schema_knowledge 
                            (table_name, table_description, columns, use_cases, 
                             data_quality_notes, embedding)
                        VALUES 
                            (:table_name, :table_description, :columns, :use_cases,
                             :data_quality_notes, :embedding::vector)
                        ON CONFLICT (table_name) DO UPDATE SET
                            table_description = EXCLUDED.table_description,
                            columns = EXCLUDED.columns,
                            use_cases = EXCLUDED.use_cases,
                            data_quality_notes = EXCLUDED.data_quality_notes,
                            embedding = EXCLUDED.embedding,
                            updated_at = CURRENT_TIMESTAMP
                    """),
                    {
                        "table_name": schema_info.table_name,
                        "table_description": schema_info.table_description,
                        "columns": json.dumps(schema_info.columns),
                        "use_cases": use_cases_array,
                        "data_quality_notes": quality_notes_array,
                        "embedding": str(embedding),
                    }
                )
                conn.commit()
                logger.info(f"Saved schema: {schema_info.table_name}")
                return True, f"Schema saved: {schema_info.table_name}"
                
        except Exception as e:
            logger.error(f"Error saving schema: {e}")
            return False, f"Error: {e}"
    
    def search_schemas(
        self,
        query: str,
        limit: int = 5,
    ) -> list[SchemaInfo]:
        """
        Search for relevant schemas using vector similarity.
        
        Args:
            query: Natural language query
            limit: Maximum number of results
        
        Returns:
            List of SchemaInfo objects
        """
        try:
            embedding = self._get_embedding(query)
            
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT id, table_name, table_description, columns,
                               use_cases, data_quality_notes,
                               1 - (embedding <=> :embedding::vector) as similarity
                        FROM schema_knowledge
                        ORDER BY embedding <=> :embedding::vector
                        LIMIT :limit
                    """),
                    {"embedding": str(embedding), "limit": limit}
                )
                
                return [
                    SchemaInfo(
                        id=row.id,
                        table_name=row.table_name,
                        table_description=row.table_description,
                        columns=json.loads(row.columns) if isinstance(row.columns, str) else row.columns,
                        use_cases=row.use_cases,
                        data_quality_notes=row.data_quality_notes,
                    )
                    for row in result
                ]
        except Exception as e:
            logger.error(f"Error searching schemas: {e}")
            return []
