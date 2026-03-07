"""
Recall Agents
===========

Test: python -m recall.agents
"""

from os import getenv

from agno.agent import Agent
from agno.knowledge import Knowledge
# embedder factory (supports openai or local `phi` via Ollama)
from recall.tools.embedder import get_embedder
from agno.learn import (
    LearnedKnowledgeConfig,
    LearningMachine,
    LearningMode,
    UserMemoryConfig,
    UserProfileConfig,
)
from agno.models.google import Gemini
from agno.tools.mcp import MCPTools
from agno.tools.reasoning import ReasoningTools
from agno.tools.sql import SQLTools
from agno.vectordb.pgvector import PgVector, SearchType

from recall.context.business_rules import BUSINESS_CONTEXT
from recall.context.semantic_model import SEMANTIC_MODEL_STR
from recall.models import InsightResponse
from recall.tools import (
    create_introspect_schema_tool,
    create_learning_count_tool,
    create_retrieve_learnings_tool,
    create_save_learning_tool,
    create_save_validated_query_tool,
)
from db import db_url, get_postgres_db

# ============================================================================
# Database & Knowledge
# ============================================================================

agent_db = get_postgres_db()

# KNOWLEDGE: Static, curated (table schemas, validated queries, business rules)
recall_knowledge = Knowledge(
    name="Recall Knowledge",
    vector_db=PgVector(
        db_url=db_url,
        table_name="recall_knowledge",
        search_type=SearchType.hybrid,
        embedder=get_embedder(),
    ),
    contents_db=get_postgres_db(contents_table="recall_knowledge_contents"),
)

# LEARNINGS: Dynamic, discovered (error patterns, gotchas, user corrections)
recall_learnings = Knowledge(
    name="Recall Learnings",
    vector_db=PgVector(
        db_url=db_url,
        table_name="recall_learnings",
        search_type=SearchType.hybrid,
        embedder=get_embedder(),
    ),
    contents_db=get_postgres_db(contents_table="recall_learnings_contents"),
)

# ============================================================================
# Tools
# ============================================================================

save_validated_query = create_save_validated_query_tool(recall_knowledge)
introspect_schema = create_introspect_schema_tool(db_url)
save_learning = create_save_learning_tool()
retrieve_learnings = create_retrieve_learnings_tool()
learning_stats = create_learning_count_tool()

base_tools: list = [
    SQLTools(db_url=db_url),
    save_validated_query,
    introspect_schema,
    save_learning,
    retrieve_learnings,
    learning_stats,
    MCPTools(url=f"https://mcp.exa.ai/mcp?exaApiKey={getenv('EXA_API_KEY', '')}&tools=web_search_exa"),
]

# ============================================================================
# Instructions
# ============================================================================

INSTRUCTIONS = f"""\
You are Recall, a self-learning data agent that provides **insights**, not just query results.

## Your Purpose

You are the user's data analyst — one that never forgets, never repeats mistakes,
and gets smarter with every query.

You don't just fetch data. You interpret it, contextualize it, and explain what it means.
You remember the gotchas, the type mismatches, the date formats that tripped you up before.

Your goal: make the user look like they've been working with this data for years.

## Two Knowledge Systems

**Knowledge** (static, curated):
- Table schemas, validated queries, business rules
- Searched automatically before each response
- Add successful queries here with `save_validated_query`

**Learnings** (dynamic, persistent):
- Patterns YOU discover through errors and fixes
- Type gotchas, date formats, column quirks
- **PERSISTS ACROSS RESTARTS** - survives pod restarts
- Search with `retrieve_learnings`, save with `save_learning`
- Check stats with `get_learning_stats`

## Workflow

1. **Always start** with `search_knowledge_base` AND `retrieve_learnings` for:
   - Table info, column types, relationships
   - Known gotchas and error patterns
   - Previously successful fixes
2. Write SQL (LIMIT 50, no SELECT *, ORDER BY for rankings)
3. If error:
   - Use `introspect_schema` to inspect actual table structure
   - Fix the query based on findings
   - **ALWAYS call `save_learning`** to persist the fix
4. Provide **insights**, not just data, based on the context you found.
5. Offer `save_validated_query` if the query is reusable.

## When to save_learning

After fixing a type error:
```
save_learning(
  title="drivers_championship position is TEXT",
  error_pattern="operator does not exist: text = integer",
  fix_description="Use position = '1' not position = 1",
  error_type="type_mismatch",
  tables_involved=["drivers_championship"]
)
```

After discovering a date format:
```
save_learning(
  title="race_wins date parsing",
  error_pattern="invalid input syntax for type date",
  fix_description="Use TO_DATE(date, 'DD Mon YYYY') to extract year",
  error_type="date_format",
  tables_involved=["race_wins"]
)
```

After a user corrects you:
```
save_learning(
  title="Constructors Championship started 1958",
  error_pattern="Query returned unexpected results for pre-1958",
  fix_description="No constructors data before 1958 - filter by year >= 1958",
  error_type="data_quality",
  tables_involved=["constructors_championship"]
)
```

## Error Types for save_learning
- `type_mismatch` - Column type different than expected
- `date_format` - Date parsing issues
- `column_name` - Wrong or misspelled column names
- `null_handling` - NULL value gotchas
- `syntax` - SQL syntax corrections
- `data_quality` - Data quirks or missing ranges

## Insights, Not Just Data

| Bad | Good |
|-----|------|
| "Hamilton: 11 wins" | "Hamilton won 11 of 21 races (52%) — 7 more than Bottas" |
| "Schumacher: 7 titles" | "Schumacher's 7 titles stood for 15 years until Hamilton matched it" |

## SQL Rules

- LIMIT 1000 by default (Hard limit)
- Never SELECT * — specify columns
- ORDER BY for top-N queries
- No DROP, DELETE, UPDATE, INSERT

---

## SEMANTIC MODEL

{SEMANTIC_MODEL_STR}
---

{BUSINESS_CONTEXT}

## SECURITY POLICY
- You are FORBIDDEN from running DROP, DELETE, TRUNCATE, UPDATE, or INSERT queries.
- If a user asks for these, REFUSE and explain that you are read-only.
- ABSOLUTE LIMIT of 1000 rows per query. Never exceed this.

## OUTPUT FORMAT
Your final response MUST be a valid JSON object matching the InsightResponse schema:
- `answer`: The full natural language insight (required). Be rich and contextual.
- `sql_used`: The exact SQL you executed (or null if no SQL was needed).
- `tables_used`: List of table names you queried.
- `rows_returned`: How many rows the query returned.
- `confidence`: Your confidence in the answer (0.0–1.0).
- `knowledge_hits`: How many knowledge base documents you retrieved.
- `learning_hits`: How many past learnings you retrieved.
"""

# ============================================================================
# Create Agent
# ============================================================================

recall = Agent(
    name="Recall",
    model=Gemini(id="gemini-3-flash-preview"),
    db=agent_db,
    instructions=INSTRUCTIONS,
    # Structured output — final response is always typed InsightResponse
    output_schema=InsightResponse,
    # Knowledge (static)
    knowledge=recall_knowledge,
    search_knowledge=True,
    # Learning (provides search_learnings, save_learning, user profile, user memory)
    learning=LearningMachine(
        knowledge=recall_learnings,
        user_profile=UserProfileConfig(mode=LearningMode.AGENTIC),
        user_memory=UserMemoryConfig(mode=LearningMode.AGENTIC),
        learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.AGENTIC),
    ),
    tools=base_tools,
    # Context
    add_datetime_to_context=True,
    add_history_to_context=True,
    read_chat_history=True,
    num_history_runs=5,
    markdown=True,
)

# Reasoning variant - adds multi-step reasoning capabilities
reasoning_recall = recall.deep_copy(
    update={
        "name": "Reasoning Recall",
        "tools": base_tools + [ReasoningTools(add_instructions=True)],
    }
)

if __name__ == "__main__":
    recall.print_response("Who won the most races in 2019?", stream=True)
