package com.example.copilot.analysis.api;

import com.example.copilot.analysis.domain.AnalysisJob;
import com.example.copilot.analysis.domain.AnalysisJobStatus;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.ObjectMapper;

public record AnalysisJobResource(
        UUID id,
        UUID dataSourceId,
        String question,
        AnalysisJobStatus status,
        String traceId,
        Instant createdAt,
        Instant updatedAt,
        Instant finishedAt,
        long version,
        String workflowThreadId,
        String generatedSql,
        String answer,
        String errorCode,
        List<String> columns,
        List<Map<String, Object>> rows,
        Map<String, Object> chart,
        List<Map<String, Object>> citations) {

    public static AnalysisJobResource from(AnalysisJob job, ObjectMapper objectMapper) {
        return new AnalysisJobResource(
                job.getId(),
                job.getDataSourceId(),
                job.getQuestion(),
                job.getStatus(),
                job.getTraceId(),
                job.getCreatedAt(),
                job.getUpdatedAt(),
                job.getFinishedAt(),
                job.getVersion(),
                job.getWorkflowThreadId(),
                job.getGeneratedSql(),
                job.getAnswer(),
                job.getErrorCode(),
                parse(job.getResultColumnsJson(), new TypeReference<>() {}, List.of(), objectMapper),
                parse(job.getResultRowsJson(), new TypeReference<>() {}, List.of(), objectMapper),
                parse(
                        job.getChartSpecJson(),
                        new TypeReference<>() {},
                        Map.of("type", "table", "title", "查询结果", "series", List.of()),
                        objectMapper),
                parse(job.getCitationsJson(), new TypeReference<>() {}, List.of(), objectMapper));
    }

    private static <T> T parse(String json, TypeReference<T> type, T fallback, ObjectMapper objectMapper) {
        return json == null || json.isBlank() ? fallback : objectMapper.readValue(json, type);
    }
}
