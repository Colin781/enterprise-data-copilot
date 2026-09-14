package com.example.copilot.analysis.api;

import com.example.copilot.analysis.domain.AnalysisJob;
import com.example.copilot.analysis.domain.AnalysisJobStatus;
import java.time.Instant;
import java.util.UUID;

public record AnalysisJobResource(
        UUID id,
        UUID dataSourceId,
        String question,
        AnalysisJobStatus status,
        String traceId,
        Instant createdAt,
        Instant updatedAt,
        Instant finishedAt,
        long version) {

    public static AnalysisJobResource from(AnalysisJob job) {
        return new AnalysisJobResource(
                job.getId(),
                job.getDataSourceId(),
                job.getQuestion(),
                job.getStatus(),
                job.getTraceId(),
                job.getCreatedAt(),
                job.getUpdatedAt(),
                job.getFinishedAt(),
                job.getVersion());
    }
}
