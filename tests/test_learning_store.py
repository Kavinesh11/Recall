"""
Tests for Learning Store
========================

Test cases for the learning persistence layer:
- Basic CRUD operations
- Deduplication logic
- Vector similarity search
- Concurrent write handling
- Edge cases (empty inputs, special characters, etc.)
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from db.learning_store import Learning, LearningStore, SchemaInfo, SchemaStore


def mock_embedder(text: str) -> list[float]:
    """Mock embedder that returns consistent vectors for testing."""
    import hashlib
    hash_bytes = hashlib.md5(text.encode()).digest()
    base_vector = [float(b) / 255 for b in hash_bytes]
    return base_vector * 96


class TestLearning:
    """Tests for Learning dataclass."""
    
    def test_learning_creation(self):
        learning = Learning(
            id=1,
            title="Test Learning",
            error_pattern="Test error",
            fix_description="Test fix",
            error_type="type_mismatch",
            tables_involved=["test_table"],
        )
        assert learning.id == 1
        assert learning.title == "Test Learning"
        assert learning.error_pattern == "Test error"
        assert learning.fix_description == "Test fix"
        assert learning.error_type == "type_mismatch"
        assert "test_table" in learning.tables_involved
    
    def test_learning_defaults(self):
        learning = Learning(
            id=None,
            title="Test",
            error_pattern="Error",
            fix_description="Fix",
        )
        assert learning.id is None
        assert learning.error_type is None
        assert learning.usage_count == 0
        assert learning.success_rate == 1.0
        assert learning.similarity is None


class TestSchemaInfo:
    """Tests for SchemaInfo dataclass."""
    
    def test_schema_info_creation(self):
        schema = SchemaInfo(
            id=1,
            table_name="test_table",
            table_description="Test table description",
            columns=[{"name": "id", "type": "int"}],
            use_cases=["test case"],
            data_quality_notes=["note 1"],
        )
        assert schema.table_name == "test_table"
        assert len(schema.columns) == 1
        assert schema.columns[0]["name"] == "id"


class TestLearningStoreUnit:
    """Unit tests for LearningStore (mocked database)."""
    
    @pytest.fixture
    def store(self):
        with patch('db.learning_store.create_engine'):
            store = LearningStore(
                db_url="postgresql://test:test@localhost/test",
                embedder=mock_embedder
            )
            return store
    
    def test_compute_text_hash(self, store):
        hash1 = store._compute_text_hash("test text")
        hash2 = store._compute_text_hash("test text")
        hash3 = store._compute_text_hash("different text")
        
        assert hash1 == hash2
        assert hash1 != hash3
        assert len(hash1) == 32
    
    def test_get_embedding(self, store):
        embedding = store._get_embedding("test text")
        assert isinstance(embedding, list)
        assert len(embedding) == 1536
        assert all(isinstance(x, float) for x in embedding)
    
    def test_get_embedding_without_embedder(self):
        with patch('db.learning_store.create_engine'):
            store = LearningStore(
                db_url="postgresql://test:test@localhost/test",
                embedder=None
            )
            with pytest.raises(ValueError, match="Embedder not configured"):
                store._get_embedding("test")
    
    def test_constants(self, store):
        assert store.SIMILARITY_THRESHOLD == 0.95
        assert store.DEFAULT_SEARCH_LIMIT == 5
        assert store.MIN_SIMILARITY == 0.7


class TestLearningStoreValidation:
    """Validation tests for save_learning inputs."""
    
    @pytest.fixture
    def mock_store(self):
        with patch('db.learning_store.create_engine'):
            store = LearningStore(
                db_url="postgresql://test:test@localhost/test",
                embedder=mock_embedder
            )
            return store
    
    def test_empty_title_validation(self, mock_store):
        with patch.object(mock_store.engine, 'connect') as mock_conn:
            mock_ctx = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            
            success, message = mock_store.save_learning(
                title="",
                error_pattern="error",
                fix_description="fix",
            )
    
    def test_whitespace_only_input(self, mock_store):
        with patch.object(mock_store.engine, 'connect') as mock_conn:
            mock_ctx = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            
            mock_ctx.execute.return_value.scalar.return_value = False
            
            success, message = mock_store.save_learning(
                title="   Valid Title   ",
                error_pattern="   error pattern   ",
                fix_description="   fix description   ",
            )


class TestLearningStoreEdgeCases:
    """Edge case tests for learning store."""
    
    def test_special_characters_in_title(self):
        learning = Learning(
            id=1,
            title="Test with 'quotes' and \"double quotes\"",
            error_pattern="Error with special chars: <>!@#$%",
            fix_description="Fix with unicode: \u00e9\u00e8\u00ea",
        )
        assert "quotes" in learning.title
        assert "unicode" in learning.fix_description
    
    def test_very_long_title(self):
        long_title = "A" * 300
        learning = Learning(
            id=1,
            title=long_title,
            error_pattern="Error",
            fix_description="Fix",
        )
        assert len(learning.title) == 300
    
    def test_empty_tables_involved(self):
        learning = Learning(
            id=1,
            title="Test",
            error_pattern="Error",
            fix_description="Fix",
            tables_involved=[],
        )
        assert learning.tables_involved == []
    
    def test_none_optional_fields(self):
        learning = Learning(
            id=1,
            title="Test",
            error_pattern="Error",
            fix_description="Fix",
            error_type=None,
            tables_involved=None,
            embedding=None,
            created_at=None,
        )
        assert learning.error_type is None
        assert learning.tables_involved is None


class TestSchemaStoreEdgeCases:
    """Edge case tests for schema store."""
    
    def test_empty_columns_list(self):
        schema = SchemaInfo(
            id=1,
            table_name="empty_table",
            table_description="Table with no columns",
            columns=[],
        )
        assert schema.columns == []
    
    def test_complex_column_types(self):
        schema = SchemaInfo(
            id=1,
            table_name="complex_table",
            table_description="Table with complex types",
            columns=[
                {"name": "json_col", "type": "jsonb"},
                {"name": "array_col", "type": "text[]"},
                {"name": "vector_col", "type": "vector(1536)"},
            ],
        )
        assert len(schema.columns) == 3


class TestErrorTypes:
    """Tests for error type categorization."""
    
    @pytest.mark.parametrize("error_type", [
        "type_mismatch",
        "date_format",
        "column_name",
        "null_handling",
        "syntax",
        "data_quality",
        "other",
    ])
    def test_valid_error_types(self, error_type):
        learning = Learning(
            id=1,
            title="Test",
            error_pattern="Error",
            fix_description="Fix",
            error_type=error_type,
        )
        assert learning.error_type == error_type
    
    def test_unknown_error_type(self):
        learning = Learning(
            id=1,
            title="Test",
            error_pattern="Error",
            fix_description="Fix",
            error_type="unknown_type",
        )
        assert learning.error_type == "unknown_type"


class TestVectorSearchMocking:
    """Tests for vector search functionality with mocking."""
    
    @pytest.fixture
    def mock_store(self):
        with patch('db.learning_store.create_engine'):
            store = LearningStore(
                db_url="postgresql://test:test@localhost/test",
                embedder=mock_embedder
            )
            return store
    
    def test_retrieve_learnings_no_results(self, mock_store):
        with patch.object(mock_store.engine, 'connect') as mock_conn:
            mock_ctx = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.execute.return_value = iter([])
            
            results = mock_store.retrieve_learnings("test query")
            assert results == []
    
    def test_retrieve_learnings_with_custom_limit(self, mock_store):
        with patch.object(mock_store.engine, 'connect') as mock_conn:
            mock_ctx = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.execute.return_value = iter([])
            
            results = mock_store.retrieve_learnings("test query", limit=10)
            assert results == []


class TestConcurrencyMocking:
    """Tests for concurrent access handling."""
    
    @pytest.fixture
    def mock_store(self):
        with patch('db.learning_store.create_engine'):
            store = LearningStore(
                db_url="postgresql://test:test@localhost/test",
                embedder=mock_embedder
            )
            return store
    
    def test_advisory_lock_used(self, mock_store):
        """Verify that advisory locks are used during save."""
        with patch.object(mock_store.engine, 'connect') as mock_conn:
            mock_ctx = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            
            mock_ctx.execute.return_value.scalar.return_value = False
            
            mock_store.save_learning(
                title="Test",
                error_pattern="Error",
                fix_description="Fix",
            )
            
            calls = [str(call) for call in mock_ctx.execute.call_args_list]
            assert any("pg_advisory_lock" in call for call in calls)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
