package com.example.copilot.client.agent;

import tools.jackson.databind.JsonNode;

public record AgentRunResult(String runId, String status, JsonNode state) {}
