package com.example.copilot.event;

import com.example.copilot.enums.AnalysisJobStatus;
import java.util.Map;
import java.util.UUID;

public record JobProgressSignal(
        UUID jobId,
        UUID tenantId,
        String traceId,
        String type,
        AnalysisJobStatus status,
        Map<String, Object> payload) {}
