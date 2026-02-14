"""
Seed Schema Knowledge - Loads table metadata into pgvector schema_knowledge table.

This script reads JSON files from recall/knowledge/tables/ and inserts them
into the schema_knowledge table with vector embeddings for semantic search.

Usage:
    python -m recall.scripts.seed_schema_knowledge
    python -m recall.scripts.seed_schema_knowledge --recreate
"""

import argparse
import json
import logging
import os
from pathlib import Path

from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"


def get_embedder():
    """Create an OpenAI embedding function."""
    client = OpenAI()
    
    def embed(text: str) -> list[float]:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    
    return embed


def load_table_schemas() -> list[dict]:
    """Load all table schema JSON files."""
    tables_dir = KNOWLEDGE_DIR / "tables"
    schemas = []
    
    if not tables_dir.exists():
        logger.warning(f"Tables directory not found: {tables_dir}")
        return schemas
    
    for file_path in tables_dir.glob("*.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                schema = json.load(f)
                schemas.append(schema)
                logger.info(f"Loaded schema: {schema.get('table_name', file_path.name)}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
    
    return schemas


def seed_schema_knowledge(recreate: bool = False):
    """
    Seed the schema_knowledge table with table metadata.
    
    Args:
        recreate: If True, truncate existing data before seeding
    """
    from db import db_url
    from db.learning_store import SchemaInfo, SchemaStore
    
    embedder = get_embedder()
    store = SchemaStore(db_url=db_url, embedder=embedder)
    
    if recreate:
        logger.info("Recreating schema_knowledge table...")
        with store.engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("TRUNCATE TABLE schema_knowledge RESTART IDENTITY"))
            conn.commit()
    
    schemas = load_table_schemas()
    
    if not schemas:
        logger.warning("No schemas found to seed")
        return
    
    success_count = 0
    for schema in schemas:
        schema_info = SchemaInfo(
            id=None,
            table_name=schema.get("table_name", ""),
            table_description=schema.get("table_description", ""),
            columns=schema.get("table_columns", []),
            use_cases=schema.get("use_cases", []),
            data_quality_notes=schema.get("data_quality_notes", []),
        )
        
        success, message = store.save_schema(schema_info)
        if success:
            success_count += 1
            logger.info(f"  [OK] {schema_info.table_name}")
        else:
            logger.error(f"  [FAIL] {schema_info.table_name}: {message}")
    
    logger.info(f"\nSeeded {success_count}/{len(schemas)} schemas")


def verify_search():
    """Verify vector search is working."""
    from db import db_url
    from db.learning_store import SchemaStore
    
    embedder = get_embedder()
    store = SchemaStore(db_url=db_url, embedder=embedder)
    
    test_queries = [
        "race results with driver positions",
        "championship points by year",
        "fastest lap times",
    ]
    
    logger.info("\nVerifying vector search...")
    for query in test_queries:
        results = store.search_schemas(query, limit=2)
        logger.info(f"\nQuery: '{query}'")
        for r in results:
            logger.info(f"  -> {r.table_name}: {r.table_description[:50]}...")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed schema knowledge into pgvector")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Truncate existing data before seeding",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run verification queries after seeding",
    )
    args = parser.parse_args()
    
    seed_schema_knowledge(recreate=args.recreate)
    
    if args.verify:
        verify_search()
