package com.example.copilot.analysis.api;

import com.example.copilot.analysis.domain.AgentStep;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.ObjectMapper;

public record AgentStepResource(
        UUID id,
        String stepName,
        String status,
        int attempt,
        Map<String, Object> inputSummary,
        Map<String, Object> outputSummary,
        long durationMs,
        String errorCode,
        Instant createdAt) {

    public static AgentStepResource from(AgentStep step, ObjectMapper objectMapper) {
        return new AgentStepResource(
                step.getId(),
                step.getStepName(),
                step.getStatus(),
                step.getAttempt(),
                parse(step.getInputSummaryJson(), objectMapper),
                parse(step.getOutputSummaryJson(), objectMapper),
                step.getDurationMs(),
                step.getErrorCode(),
                step.getCreatedAt());
    }

    private static Map<String, Object> parse(String json, ObjectMapper objectMapper) {
        return objectMapper.readValue(json, new TypeReference<>() {});
    }
}
