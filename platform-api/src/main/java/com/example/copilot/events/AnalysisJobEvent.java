package com.example.copilot.events;

import com.example.copilot.analysis.domain.AnalysisJobStatus;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;

public record AnalysisJobEvent(
        String eventVersion,
        UUID eventId,
        long sequence,
        UUID jobId,
        UUID tenantId,
        String traceId,
        String type,
        AnalysisJobStatus status,
        Instant occurredAt,
        Map<String, Object> payload) {}
