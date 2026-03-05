"""
Recall Response Models
======================

Pydantic models for structured agent outputs.
"""

from typing import Optional
from pydantic import BaseModel, Field


class InsightResponse(BaseModel):
    """Structured response from the Recall data agent.
    
    Used as output_schema on the Recall Agent so every response is
    typed and machine-readable rather than raw markdown text.
    """

    answer: str = Field(
        ...,
        description=(
            "Natural language insight answering the user's question. "
            "Include context, comparisons, and what the numbers mean — not just raw values."
        ),
    )
    sql_used: Optional[str] = Field(
        default=None,
        description="The final SQL query that was executed to produce the answer.",
    )
    tables_used: list[str] = Field(
        default_factory=list,
        description="List of database table names referenced in the query.",
    )
    rows_returned: int = Field(
        default=0,
        description="Number of rows returned by the SQL query.",
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description=(
            "Confidence score for this answer (0=low, 1=high). "
            "Use lower values when data is incomplete or the question is ambiguous."
        ),
    )
    knowledge_hits: int = Field(
        default=0,
        description="Number of knowledge base documents retrieved to answer this question.",
    )
    learning_hits: int = Field(
        default=0,
        description="Number of past learnings (error patterns/fixes) retrieved for this query.",
    )
