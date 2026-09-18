package com.example.copilot.integration.agent;

import tools.jackson.databind.JsonNode;

public record AgentRunResult(String runId, String status, JsonNode state) {}
