"""
Tests for Learning Tools
========================

Test cases for the save_learning and retrieve_learnings tools.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestSaveLearningTool:
    """Tests for save_learning tool."""
    
    def test_save_learning_requires_title(self):
        from recall.tools.learning import create_save_learning_tool
        
        with patch('recall.tools.learning.get_learning_store') as mock_store:
            save_learning = create_save_learning_tool()
            
            result = save_learning(
                title="",
                error_pattern="test error",
                fix_description="test fix",
            )
            assert "Error: title is required" in result
    
    def test_save_learning_requires_error_pattern(self):
        from recall.tools.learning import create_save_learning_tool
        
        with patch('recall.tools.learning.get_learning_store'):
            save_learning = create_save_learning_tool()
            
            result = save_learning(
                title="Test Title",
                error_pattern="",
                fix_description="test fix",
            )
            assert "Error: error_pattern is required" in result
    
    def test_save_learning_requires_fix_description(self):
        from recall.tools.learning import create_save_learning_tool
        
        with patch('recall.tools.learning.get_learning_store'):
            save_learning = create_save_learning_tool()
            
            result = save_learning(
                title="Test Title",
                error_pattern="test error",
                fix_description="",
            )
            assert "Error: fix_description is required" in result
    
    def test_save_learning_invalid_error_type(self):
        from recall.tools.learning import create_save_learning_tool
        
        with patch('recall.tools.learning.get_learning_store') as mock_store_fn:
            mock_store = MagicMock()
            mock_store.save_learning.return_value = (True, "Success")
            mock_store_fn.return_value = mock_store
            
            save_learning = create_save_learning_tool()
            
            result = save_learning(
                title="Test",
                error_pattern="error",
                fix_description="fix",
                error_type="invalid_type",
            )
            
            call_args = mock_store.save_learning.call_args
            assert call_args.kwargs.get('error_type') == 'other'
    
    def test_save_learning_valid_error_types(self):
        from recall.tools.learning import create_save_learning_tool
        
        valid_types = [
            "type_mismatch", "date_format", "column_name",
            "null_handling", "syntax", "data_quality", "other"
        ]
        
        for error_type in valid_types:
            with patch('recall.tools.learning.get_learning_store') as mock_store_fn:
                mock_store = MagicMock()
                mock_store.save_learning.return_value = (True, "Success")
                mock_store_fn.return_value = mock_store
                
                save_learning = create_save_learning_tool()
                
                result = save_learning(
                    title="Test",
                    error_pattern="error",
                    fix_description="fix",
                    error_type=error_type,
                )
                
                call_args = mock_store.save_learning.call_args
                assert call_args.kwargs.get('error_type') == error_type
    
    def test_save_learning_success_message(self):
        from recall.tools.learning import create_save_learning_tool
        
        with patch('recall.tools.learning.get_learning_store') as mock_store_fn:
            with patch('recall.tools.learning.record_learning_saved'):
                mock_store = MagicMock()
                mock_store.save_learning.return_value = (True, "Saved successfully")
                mock_store_fn.return_value = mock_store
                
                save_learning = create_save_learning_tool()
                
                result = save_learning(
                    title="Test Learning",
                    error_pattern="error pattern",
                    fix_description="fix description",
                )
                
                assert "Learning saved: Test Learning" in result
    
    def test_save_learning_duplicate_message(self):
        from recall.tools.learning import create_save_learning_tool
        
        with patch('recall.tools.learning.get_learning_store') as mock_store_fn:
            mock_store = MagicMock()
            mock_store.save_learning.return_value = (False, "Similar learning already exists")
            mock_store_fn.return_value = mock_store
            
            save_learning = create_save_learning_tool()
            
            result = save_learning(
                title="Duplicate Learning",
                error_pattern="error pattern",
                fix_description="fix description",
            )
            
            assert "Learning not saved" in result
            assert "Similar learning already exists" in result


class TestRetrieveLearningsTool:
    """Tests for retrieve_learnings tool."""
    
    def test_retrieve_learnings_requires_query(self):
        from recall.tools.learning import create_retrieve_learnings_tool
        
        with patch('recall.tools.learning.get_learning_store'):
            retrieve_learnings = create_retrieve_learnings_tool()
            
            result = retrieve_learnings(query="")
            assert "Error: query is required" in result
    
    def test_retrieve_learnings_no_results(self):
        from recall.tools.learning import create_retrieve_learnings_tool
        
        with patch('recall.tools.learning.get_learning_store') as mock_store_fn:
            mock_store = MagicMock()
            mock_store.retrieve_learnings.return_value = []
            mock_store_fn.return_value = mock_store
            
            retrieve_learnings = create_retrieve_learnings_tool()
            
            result = retrieve_learnings(query="test query")
            assert "No relevant learnings found" in result
    
    def test_retrieve_learnings_with_results(self):
        from recall.tools.learning import create_retrieve_learnings_tool
        from db.learning_store import Learning
        
        with patch('recall.tools.learning.get_learning_store') as mock_store_fn:
            mock_store = MagicMock()
            mock_store.retrieve_learnings.return_value = [
                Learning(
                    id=1,
                    title="Test Learning",
                    error_pattern="test error",
                    fix_description="test fix",
                    similarity=0.85,
                )
            ]
            mock_store_fn.return_value = mock_store
            
            retrieve_learnings = create_retrieve_learnings_tool()
            
            result = retrieve_learnings(query="test query")
            assert "Found 1 relevant learning" in result
            assert "Test Learning" in result
            assert "85%" in result
    
    def test_retrieve_learnings_with_error_type_filter(self):
        from recall.tools.learning import create_retrieve_learnings_tool
        from db.learning_store import Learning
        
        with patch('recall.tools.learning.get_learning_store') as mock_store_fn:
            mock_store = MagicMock()
            mock_store.get_learnings_by_error_type.return_value = [
                Learning(
                    id=1,
                    title="Type Mismatch Learning",
                    error_pattern="type error",
                    fix_description="cast fix",
                    error_type="type_mismatch",
                )
            ]
            mock_store_fn.return_value = mock_store
            
            retrieve_learnings = create_retrieve_learnings_tool()
            
            result = retrieve_learnings(
                query="test query",
                error_type="type_mismatch"
            )
            
            mock_store.get_learnings_by_error_type.assert_called_once_with("type_mismatch")


class TestLearningStatsTool:
    """Tests for get_learning_stats tool."""
    
    def test_learning_stats_returns_count(self):
        from recall.tools.learning import create_learning_count_tool
        
        with patch('recall.tools.learning.get_learning_store') as mock_store_fn:
            mock_store = MagicMock()
            mock_store.get_learning_count.return_value = 42
            mock_store.engine.connect.return_value.__enter__.return_value.execute.return_value = iter([])
            mock_store_fn.return_value = mock_store
            
            get_stats = create_learning_count_tool()
            
            result = get_stats()
            assert "42" in result


class TestEdgeCases:
    """Edge case tests for learning tools."""
    
    def test_whitespace_input_stripped(self):
        from recall.tools.learning import create_save_learning_tool
        
        with patch('recall.tools.learning.get_learning_store') as mock_store_fn:
            with patch('recall.tools.learning.record_learning_saved'):
                mock_store = MagicMock()
                mock_store.save_learning.return_value = (True, "Success")
                mock_store_fn.return_value = mock_store
                
                save_learning = create_save_learning_tool()
                
                result = save_learning(
                    title="  Test Title  ",
                    error_pattern="  error  ",
                    fix_description="  fix  ",
                )
                
                call_args = mock_store.save_learning.call_args
                assert call_args.kwargs.get('title') == "Test Title"
                assert call_args.kwargs.get('error_pattern') == "error"
                assert call_args.kwargs.get('fix_description') == "fix"
    
    def test_tables_involved_list_passed(self):
        from recall.tools.learning import create_save_learning_tool
        
        with patch('recall.tools.learning.get_learning_store') as mock_store_fn:
            with patch('recall.tools.learning.record_learning_saved'):
                mock_store = MagicMock()
                mock_store.save_learning.return_value = (True, "Success")
                mock_store_fn.return_value = mock_store
                
                save_learning = create_save_learning_tool()
                
                tables = ["table1", "table2"]
                result = save_learning(
                    title="Test",
                    error_pattern="error",
                    fix_description="fix",
                    tables_involved=tables,
                )
                
                call_args = mock_store.save_learning.call_args
                assert call_args.kwargs.get('tables_involved') == tables


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
