package com.example.copilot.integration.agent;

import java.util.UUID;

public interface AgentRunClient {
    AgentRunResult start(
            UUID jobId,
            UUID tenantId,
            UUID userId,
            String role,
            UUID dataSourceId,
            String question,
            String traceId,
            String idempotencyKey);

    AgentResumeResult resume(
            UUID jobId,
            UUID tenantId,
            UUID approvalId,
            UUID decidedBy,
            String decision,
            String comment,
            String traceId);
}
