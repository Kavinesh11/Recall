"""
Test script for Recall MCP Server
Validates request models and error handling without starting the server
"""

from pydantic import ValidationError
from recall.server import QueryRequest, SaveQueryRequest

def test_query_request_validation():
    """Test QueryRequest validation"""
    print("Testing QueryRequest validation...")
    
    # Valid request
    try:
        req = QueryRequest(question="Who won the most races?")
        print(f"✓ Valid request: {req.question}")
    except ValidationError as e:
        print(f"✗ Unexpected error: {e}")
        return False
    
    # Empty question
    try:
        req = QueryRequest(question="")
        print("✗ Empty question should have failed")
        return False
    except ValidationError as e:
        print(f"✓ Empty question rejected: {e.errors()[0]['msg']}")
    
    # Whitespace only
    try:
        req = QueryRequest(question="   ")
        print("✗ Whitespace question should have failed")
        return False
    except ValidationError as e:
        print(f"✓ Whitespace question rejected: {e.errors()[0]['msg']}")
    
    # Too long question
    try:
        req = QueryRequest(question="x" * 5001)
        print("✗ Too long question should have failed")
        return False
    except ValidationError as e:
        print(f"✓ Too long question rejected")
    
    print("✓ QueryRequest validation tests passed\n")
    return True

def test_save_query_request_validation():
    """Test SaveQueryRequest validation"""
    print("Testing SaveQueryRequest validation...")
    
    # Valid request
    try:
        req = SaveQueryRequest(
            name="test_query",
            question="Who won?",
            query="SELECT driver FROM race_wins LIMIT 1"
        )
        print(f"✓ Valid request: {req.name}")
    except ValidationError as e:
        print(f"✗ Unexpected error: {e}")
        return False
    
    # Empty name
    try:
        req = SaveQueryRequest(name="", question="test", query="SELECT 1")
        print("✗ Empty name should have failed")
        return False
    except ValidationError as e:
        print(f"✓ Empty name rejected")
    
    # Invalid query (not SELECT)
    try:
        req = SaveQueryRequest(
            name="bad_query",
            question="Delete data",
            query="DELETE FROM table"
        )
        print("✗ DELETE query should have failed")
        return False
    except ValidationError as e:
        print(f"✓ DELETE query rejected: {e.errors()[0]['msg']}")
    
    # Valid WITH query
    try:
        req = SaveQueryRequest(
            name="with_query",
            question="Complex query",
            query="WITH cte AS (SELECT * FROM table) SELECT * FROM cte"
        )
        print(f"✓ WITH query accepted")
    except ValidationError as e:
        print(f"✗ WITH query should be valid: {e}")
        return False
    
    print("✓ SaveQueryRequest validation tests passed\n")
    return True

def test_field_constraints():
    """Test field length constraints"""
    print("Testing field constraints...")
    
    # Max length tests
    try:
        req = QueryRequest(question="x" * 4999)  # Within limit
        print(f"✓ Long question within limit accepted (length: {len(req.question)})")
    except ValidationError as e:
        print(f"✗ Should accept 4999 chars: {e}")
        return False
    
    # run_id max length
    try:
        req = QueryRequest(question="test", run_id="x" * 101)
        print("✗ run_id too long should fail")
        return False
    except ValidationError as e:
        print(f"✓ Long run_id rejected")
    
    print("✓ Field constraint tests passed\n")
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("Recall MCP Server - Validation Tests")
    print("=" * 60)
    print()
    
    results = []
    results.append(("QueryRequest validation", test_query_request_validation()))
    results.append(("SaveQueryRequest validation", test_save_query_request_validation()))
    results.append(("Field constraints", test_field_constraints()))
    
    print("=" * 60)
    print("Test Results:")
    print("=" * 60)
    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: {name}")
    
    all_passed = all(result[1] for result in results)
    print()
    if all_passed:
        print("✓ All validation tests passed!")
        exit(0)
    else:
        print("✗ Some tests failed")
        exit(1)
