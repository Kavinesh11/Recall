
import os
import sys
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set env vars BEFORE importing server
os.environ["ENABLE_AUTH"] = "true"
os.environ["ARCHESTRA_TOKEN_ENDPOINT"] = ""

# Mock problematic dependencies
sys.modules["agno"] = MagicMock()
sys.modules["agno.agent"] = MagicMock()
sys.modules["agno.knowledge"] = MagicMock()
sys.modules["agno.knowledge.embedder.openai"] = MagicMock()
sys.modules["agno.learn"] = MagicMock()
sys.modules["agno.models.openai"] = MagicMock()
sys.modules["agno.tools.mcp"] = MagicMock()
sys.modules["agno.tools.reasoning"] = MagicMock()
sys.modules["agno.tools.sql"] = MagicMock()
sys.modules["agno.vectordb.pgvector"] = MagicMock()
sys.modules["db"] = MagicMock()
sys.modules["recall.context.business_rules"] = MagicMock()
sys.modules["recall.context.semantic_model"] = MagicMock()

# Mock recall.agents because it imports agno
mock_agents = MagicMock()
sys.modules["recall.agents"] = mock_agents
# Setup recall agent mock
mock_recall = MagicMock()
mock_agents.recall = mock_recall
mock_agents.recall_knowledge = MagicMock()
mock_agents.recall_learnings = MagicMock()

# Mock recall.observability
mock_observability = MagicMock()
sys.modules["recall.observability"] = mock_observability
mock_observability.track_query_latency = MagicMock()
# Make track_query_latency a context manager
mock_observability.track_query_latency.return_value.__enter__.return_value = None
mock_observability.track_query_latency.return_value.__exit__.return_value = None

# Mock recall.tools
mock_tools = MagicMock()
sys.modules["recall.tools"] = mock_tools
# This is used in server.py
mock_tools.create_save_validated_query_tool = MagicMock()

# Now import app from server
from recall.server import app
from fastapi.testclient import TestClient

client = TestClient(app)

class TestAuthSecurity(unittest.TestCase):
    def test_health_no_auth(self):
        """Health endpoints should be accessible without auth"""
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")

    def test_auth_missing_header(self):
        """Should return 401 if Authorization header is missing"""
        response = client.post("/mcp/tools/ask_data_agent", json={"question": "test"})
        self.assertEqual(response.status_code, 401)
        self.assertIn("Missing Authorization header", str(response.json()))

    def test_auth_invalid_format(self):
        """Should return 401 if token format is invalid"""
        response = client.post(
            "/mcp/tools/ask_data_agent", 
            json={"question": "test"},
            headers={"Authorization": "Basic 1234"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("Invalid token format", str(response.json()))

    def test_auth_short_token(self):
        """Should return 401 if token is too short"""
        response = client.post(
            "/mcp/tools/ask_data_agent", 
            json={"question": "test"},
            headers={"Authorization": "Bearer 123"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("Token too short", str(response.json()))

    def test_save_validate_drop(self):
        """Save query endpoint should reject DROP"""
        response = client.post(
            "/mcp/tools/save_verified_query",
            json={
                "name": "malicious",
                "question": "destroy",
                "query": "DROP TABLE users",
                "summary": "evil"
            },
            headers={"Authorization": "Bearer valid_token_12345"}
        )
        # Pydantic validation errors are usually 422, but our ValueError handler makes them 400.
        # However, FastAPI's RequestValidationError (for Pydantic models) might take precedence.
        self.assertIn(response.status_code, [400, 422])
        # The error message format depends on whether it's our handler or FastAPI's default
        if response.status_code == 400:
             self.assertIn("Only SELECT or WITH queries are allowed", response.text)
        else:
             # FastAPI default validation error structure
             pass

    def test_run_agent_valid_token(self):
         """Should call agent if token is valid"""
         # Setup mock result
         # We need to ensure the async run returns a proper object or string
         # The server code checks: hasattr(response, 'content') or isinstance(str)
         mock_recall.arun = AsyncMock(return_value="Success Result")
         
         response = client.post(
            "/mcp/tools/ask_data_agent", 
            json={"question": "test"},
            headers={"Authorization": "Bearer valid_token_12345"}
        )
         # If this fails with 500, print result
         if response.status_code != 200:
             print(f"Agent Run Failed: {response.text}")
             
         self.assertEqual(response.status_code, 200)
         self.assertEqual(response.json()["result"], "Success Result")

if __name__ == "__main__":
    unittest.main()
