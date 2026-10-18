package com.example.copilot.client.agent;

import tools.jackson.databind.JsonNode;

public record AgentResumeResult(String runId, String status, JsonNode state) {

    public AgentResumeResult(String runId, String status) {
        this(runId, status, null);
    }
}
