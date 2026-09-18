package com.example.copilot.integration.agent;

import com.example.copilot.knowledge.api.MetricDocumentResource;
import com.example.copilot.knowledge.api.MetricDocumentUploadRequest;
import java.util.UUID;

public interface MetricKnowledgeClient {
    MetricDocumentResource ingest(UUID tenantId, UUID userId, MetricDocumentUploadRequest request, String traceId);
}
