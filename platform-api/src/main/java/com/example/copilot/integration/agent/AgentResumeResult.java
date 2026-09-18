package com.example.copilot.integration.agent;

import tools.jackson.databind.JsonNode;

public record AgentResumeResult(String runId, String status, JsonNode state) {

    public AgentResumeResult(String runId, String status) {
        this(runId, status, null);
    }
}
