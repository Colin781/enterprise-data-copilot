package com.example.copilot.knowledge.api;

import com.example.copilot.knowledge.domain.MetricDocument;
import java.time.Instant;
import java.util.UUID;

public record MetricDocumentResource(
        UUID id,
        UUID tenantId,
        String title,
        int version,
        String status,
        String sourceType,
        String sourceName,
        String contentSha256,
        int chunkCount,
        Instant createdAt,
        Instant updatedAt) {

    public static MetricDocumentResource from(MetricDocument document) {
        return new MetricDocumentResource(
                document.getId(),
                document.getTenantId(),
                document.getTitle(),
                document.getVersion(),
                document.getStatus(),
                document.getSourceType(),
                document.getSourceName(),
                document.getContentSha256(),
                0,
                document.getCreatedAt(),
                document.getUpdatedAt());
    }
}
