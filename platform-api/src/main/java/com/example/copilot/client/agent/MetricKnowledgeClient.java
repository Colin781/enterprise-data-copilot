package com.example.copilot.client.agent;

import com.example.copilot.dto.request.MetricDocumentUploadRequest;
import com.example.copilot.dto.response.MetricDocumentResource;
import java.util.UUID;

public interface MetricKnowledgeClient {
    MetricDocumentResource ingest(UUID tenantId, UUID userId, MetricDocumentUploadRequest request, String traceId);
}
