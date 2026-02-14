#!/bin/bash
# Recall MCP Server - API Testing Script
# Run this after starting the server with: docker-compose up -d

BASE_URL="http://localhost:8000"

echo "================================"
echo "Recall MCP Server - API Tests"
echo "================================"
echo ""

# Test 1: Health Check
echo "Test 1: Health Check"
echo "--------------------"
curl -s "${BASE_URL}/health" | jq '.'
echo ""

# Test 2: List Tools
echo "Test 2: List Available Tools"
echo "-----------------------------"
curl -s "${BASE_URL}/mcp/tools" | jq '.'
echo ""

# Test 3: Get Root Info
echo "Test 3: Server Info"
echo "-------------------"
curl -s "${BASE_URL}/" | jq '.'
echo ""

# Test 4: Valid Query Request
echo "Test 4: Valid Query Request"
echo "---------------------------"
curl -s -X POST "${BASE_URL}/mcp/tools/ask_data_agent" \
  -H "Content-Type: application/json" \
  -H "X-Archestra-Agent-Id: test-agent" \
  -d '{"question": "Who won the most F1 World Championships?", "run_id": "test-001"}' \
  | jq '.'
echo ""

# Test 5: Empty Question (Should Fail)
echo "Test 5: Empty Question (Validation Error)"
echo "-----------------------------------------"
curl -s -X POST "${BASE_URL}/mcp/tools/ask_data_agent" \
  -H "Content-Type: application/json" \
  -d '{"question": ""}' \
  | jq '.'
echo ""

# Test 6: Missing Question (Should Fail)
echo "Test 6: Missing Question Field (Validation Error)"
echo "--------------------------------------------------"
curl -s -X POST "${BASE_URL}/mcp/tools/ask_data_agent" \
  -H "Content-Type: application/json" \
  -d '{}' \
  | jq '.'
echo ""

# Test 7: Save Valid Query
echo "Test 7: Save Valid Query"
echo "------------------------"
curl -s -X POST "${BASE_URL}/mcp/tools/save_verified_query" \
  -H "Content-Type: application/json" \
  -H "X-Archestra-Agent-Id: test-agent" \
  -d '{
    "name": "test_query_championship_wins",
    "question": "Who won the most championships?",
    "query": "SELECT driver, COUNT(*) as titles FROM drivers_championship WHERE position = '\''1'\'' GROUP BY driver ORDER BY titles DESC LIMIT 10",
    "summary": "Count championship wins by driver",
    "tables_used": ["drivers_championship"],
    "data_quality_notes": "position field is TEXT type, use string comparison"
  }' \
  | jq '.'
echo ""

# Test 8: Invalid Query (DELETE - Should Fail)
echo "Test 8: Invalid Query Type (Should Fail)"
echo "----------------------------------------"
curl -s -X POST "${BASE_URL}/mcp/tools/save_verified_query" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "bad_query",
    "question": "Delete data",
    "query": "DELETE FROM table WHERE id = 1"
  }' \
  | jq '.'
echo ""

# Test 9: Get Schema Resource
echo "Test 9: Get Schema Resource"
echo "---------------------------"
curl -s "${BASE_URL}/mcp/resources/schema" | jq '.'
echo ""

# Test 10: Get Learnings Resource
echo "Test 10: Get Learnings Resource"
echo "-------------------------------"
curl -s "${BASE_URL}/mcp/resources/learnings" | jq '.'
echo ""

echo "================================"
echo "Tests Complete!"
echo "================================"
