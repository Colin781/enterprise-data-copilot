package com.example.copilot.events;

import com.example.copilot.analysis.domain.AnalysisJobStatus;
import java.util.Map;
import java.util.UUID;

public record JobProgressSignal(
        UUID jobId,
        UUID tenantId,
        String traceId,
        String type,
        AnalysisJobStatus status,
        Map<String, Object> payload) {}
