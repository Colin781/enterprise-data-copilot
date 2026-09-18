package com.example.copilot.knowledge.service;

import com.example.copilot.audit.service.AuditService;
import com.example.copilot.integration.agent.MetricKnowledgeClient;
import com.example.copilot.knowledge.api.MetricDocumentResource;
import com.example.copilot.knowledge.api.MetricDocumentUploadRequest;
import com.example.copilot.knowledge.repository.MetricDocumentRepository;
import com.example.copilot.security.CallerIdentity.Caller;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class MetricDocumentService {

    private final MetricDocumentRepository repository;
    private final MetricKnowledgeClient knowledgeClient;
    private final AuditService auditService;

    public MetricDocumentService(
            MetricDocumentRepository repository, MetricKnowledgeClient knowledgeClient, AuditService auditService) {
        this.repository = repository;
        this.knowledgeClient = knowledgeClient;
        this.auditService = auditService;
    }

    @Transactional(readOnly = true)
    public List<MetricDocumentResource> list(Caller caller) {
        return repository.findTop100ByTenantIdOrderByUpdatedAtDesc(caller.tenantId()).stream()
                .map(MetricDocumentResource::from)
                .toList();
    }

    public MetricDocumentResource upload(MetricDocumentUploadRequest request, Caller caller, String traceId) {
        var document = knowledgeClient.ingest(caller.tenantId(), caller.userId(), request, traceId);
        auditService.recordSuccess(
                caller.tenantId(),
                caller.userId(),
                "METRIC_DOCUMENT_UPLOADED",
                "METRIC_DOCUMENT",
                document.id(),
                traceId);
        return document;
    }
}
