"""
Learning Tools - Agno tools for saving and retrieving learnings.

Provides tools for the Dash agent to:
- Save new learnings (error patterns and fixes)
- Retrieve relevant learnings for context
- Check for duplicates before saving
"""

import json
import logging
from functools import lru_cache
from typing import Callable

from agno.tools import tool
from openai import OpenAI

from db import db_url
from db.learning_store import LearningStore

logger = logging.getLogger(__name__)

try:
    from recall.observability import record_learning_saved
except ImportError:
    def record_learning_saved(error_type: str = "unknown"):
        pass


from recall.tools.embedder import get_embedder


@lru_cache(maxsize=1)
def get_learning_store() -> LearningStore:
    """Get cached learning store instance."""
    embedder = get_embedder()
    return LearningStore(db_url=db_url, embedder=embedder)


def create_save_learning_tool():
    """Create the save_learning tool for persisting error patterns."""
    
    @tool
    def save_learning(
        title: str,
        error_pattern: str,
        fix_description: str,
        error_type: str | None = None,
        tables_involved: list[str] | None = None,
    ) -> str:
        """
        Save a discovered error pattern and its fix to the learning database.
        
        Call this AFTER you fix an error during SQL generation/execution.
        The learning will be available for future similar queries.
        
        Args:
            title: Short descriptive title (e.g., "position column is TEXT not INT")
            error_pattern: The error message or pattern that was encountered
            fix_description: How to fix/avoid this error in the future
            error_type: Category: 'type_mismatch', 'date_format', 'column_name', 
                       'null_handling', 'syntax', 'data_quality'
            tables_involved: List of table names related to this learning
        
        Returns:
            Success or failure message
        
        Examples:
            save_learning(
                title="drivers_championship position is TEXT",
                error_pattern="operator does not exist: text = integer",
                fix_description="Use position = '1' not position = 1 when filtering for champions",
                error_type="type_mismatch",
                tables_involved=["drivers_championship"]
            )
            
            save_learning(
                title="race_wins date parsing",
                error_pattern="invalid input syntax for type date",
                fix_description="Use TO_DATE(date, 'DD Mon YYYY') to parse the date column",
                error_type="date_format",
                tables_involved=["race_wins"]
            )
        """
        if not title or not title.strip():
            return "Error: title is required"
        if not error_pattern or not error_pattern.strip():
            return "Error: error_pattern is required"
        if not fix_description or not fix_description.strip():
            return "Error: fix_description is required"
        
        valid_error_types = [
            "type_mismatch", "date_format", "column_name", 
            "null_handling", "syntax", "data_quality", "other"
        ]
        if error_type and error_type not in valid_error_types:
            error_type = "other"
        
        try:
            store = get_learning_store()
            success, message = store.save_learning(
                title=title.strip(),
                error_pattern=error_pattern.strip(),
                fix_description=fix_description.strip(),
                error_type=error_type,
                tables_involved=tables_involved,
                skip_if_duplicate=True,
            )
            
            if success:
                record_learning_saved(error_type or "unknown")
                logger.info(f"[save_learning] Saved: {title}")
                return f"Learning saved: {title}"
            else:
                logger.info(f"[save_learning] Skipped (duplicate): {title}")
                return f"Learning not saved: {message}"
                
        except Exception as e:
            logger.error(f"[save_learning] Error: {e}", exc_info=True)
            return f"Error saving learning: {e}"
    
    return save_learning


def create_retrieve_learnings_tool():
    """Create the retrieve_learnings tool for getting relevant past learnings."""
    
    @tool
    def retrieve_learnings(
        query: str,
        limit: int = 5,
        error_type: str | None = None,
    ) -> str:
        """
        Retrieve relevant learnings from the database based on similarity.
        
        Call this BEFORE generating SQL to check for known gotchas.
        Especially useful when you encounter an error and want to see
        if similar issues have been solved before.
        
        Args:
            query: The question, error message, or context to find learnings for
            limit: Maximum number of learnings to return (default: 5)
            error_type: Filter by error type: 'type_mismatch', 'date_format', 
                       'column_name', 'null_handling', 'syntax', 'data_quality'
        
        Returns:
            Formatted list of relevant learnings with their fixes
        
        Examples:
            retrieve_learnings("position column comparison error")
            retrieve_learnings("date parsing issue", error_type="date_format")
            retrieve_learnings("race results query", limit=3)
        """
        if not query or not query.strip():
            return "Error: query is required"
        
        try:
            store = get_learning_store()
            
            if error_type:
                learnings = store.get_learnings_by_error_type(error_type)[:limit]
            else:
                learnings = store.retrieve_learnings(
                    query=query.strip(),
                    limit=limit,
                    min_similarity=0.6,
                )
            
            if not learnings:
                return "No relevant learnings found."
            
            results = []
            for i, learning in enumerate(learnings, 1):
                similarity_str = (
                    f" (similarity: {learning.similarity:.2%})"
                    if learning.similarity else ""
                )
                results.append(
                    f"**{i}. {learning.title}**{similarity_str}\n"
                    f"   Error: {learning.error_pattern}\n"
                    f"   Fix: {learning.fix_description}"
                )
            
            header = f"Found {len(learnings)} relevant learning(s):\n"
            return header + "\n\n".join(results)
            
        except Exception as e:
            logger.error(f"[retrieve_learnings] Error: {e}", exc_info=True)
            return f"Error retrieving learnings: {e}"
    
    return retrieve_learnings


def create_learning_count_tool():
    """Create tool to get the current learning count."""
    
    @tool
    def get_learning_stats() -> str:
        """
        Get statistics about stored learnings.
        
        Returns count of learnings and breakdown by error type.
        Useful for monitoring the agent's learning progress.
        """
        try:
            store = get_learning_store()
            total = store.get_learning_count()
            
            from sqlalchemy import text
            with store.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT error_type, COUNT(*) as count
                    FROM recall_learnings
                    GROUP BY error_type
                    ORDER BY count DESC
                """))
                by_type = {row.error_type or "unknown": row.count for row in result}
            
            lines = [f"**Total Learnings:** {total}"]
            if by_type:
                lines.append("\n**By Error Type:**")
                for error_type, count in by_type.items():
                    lines.append(f"  - {error_type}: {count}")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"[get_learning_stats] Error: {e}", exc_info=True)
            return f"Error getting stats: {e}"
    
    return get_learning_stats
