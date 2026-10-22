package com.example.copilot.dto.response;

import java.time.Instant;
import java.util.UUID;

public record AnalysisJobSearchItem (
        UUID id,
        String question,
        String status,
        Instant createdAt,
        UUID dataSourceId,
        String dataSourceName,
        UUID createdBy,
        String createdByName) {}
