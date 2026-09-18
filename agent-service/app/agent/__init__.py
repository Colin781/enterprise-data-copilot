"""Durable LangGraph orchestration for analysis runs."""

import os

# Checkpoints contain only JSON-like state; reject arbitrary module revival even if the
# database is compromised. This must be set before LangGraph imports its serializer.
os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

from app.agent.graph import build_agent_graph
from app.agent.service import AgentWorkflowService

__all__ = ["AgentWorkflowService", "build_agent_graph"]
