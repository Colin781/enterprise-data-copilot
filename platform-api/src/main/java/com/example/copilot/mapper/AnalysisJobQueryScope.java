package com.example.copilot.mapper;

import java.util.Objects;
import java.util.UUID;

public record AnalysisJobQueryScope(
        UUID tenantId,
        UUID ownerId,
        UUID dataSourceId) {

    public AnalysisJobQueryScope {
        Objects.requireNonNull(tenantId, "tenantId is required");
    }
}
