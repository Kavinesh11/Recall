# Archestra Hackathon Demo Script

## 1. Introduction (30s)
- **Problem**: Enterprises need AI agents that can learn from their mistakes and query secure data, but integrating them into orchestration platforms is hard.
- **Solution**: "Dash" - A Self-Learning SQL Agent for Archestra.
- **Key Features**:
  - 🧠 **Self-Correction**: Learns from failed SQL queries.
  - 🔒 **Trusted Data**: Read-only policies & access control.
  - 📊 **Observability**: Built-in OTEL traces & Prometheus metrics.

## 2. Architecture Overview (30s)
- Show `docs/architecture.mermaid`.
- Explain how Dash sits behind an Ingress, authenticates via Archestra, and talks to Postgres/pgvector.

## 3. Live Demo (2m)
### Scenario 1: The "Cold Start" Failure
- **Action**: Ask "How many users signed up last week?"
- **Observation**: Agent tries a generic query. Fails (e.g., wrong column name).
- **Result**: Agent catches error, reflects, and *fixes the query*. It saves this "Learning".

### Scenario 2: The "Learned" Success
- **Action**: Ask a similar question: "Show me daily signups for last month."
- **Observation**: Agent *retrieves* the previous learning. Uses the correct schema immediately.
- **Result**: Fast, correct answer.

### Scenario 3: Security & Governance
- **Action**: Ask "Drop the users table."
- **Result**: Agent refuses (Trusted Data Policy).
- **Action**: Show `server.py` logs confirming the blocked attempt.

### Scenario 4: Observability
- **Action**: Switch to Grafana.
- **Observation**: Show:
  - Spike in "Query Rate".
  - "Token Usage" histogram.
  - "Learning Count" metric increasing.
  - Trace of the "Reasoning" span showing the retry loop.

## 4. Conclusion (30s)
- Dash makes AI agents production-ready for Archestra.
- Secure, Observable, and gets smarter over time.
- Available now on the MCP Registry.
