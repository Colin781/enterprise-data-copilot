package com.example.copilot.audit.service;

import com.example.copilot.audit.domain.AuditEvent;
import com.example.copilot.audit.repository.AuditEventRepository;
import java.time.Instant;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class AuditService {

    private final AuditEventRepository auditEventRepository;

    public AuditService(AuditEventRepository auditEventRepository) {
        this.auditEventRepository = auditEventRepository;
    }

    public void recordSuccess(
            UUID tenantId, UUID actorUserId, String action, String resourceType, UUID resourceId, String traceId) {
        auditEventRepository.save(new AuditEvent(
                UUID.randomUUID(),
                tenantId,
                actorUserId,
                action,
                resourceType,
                resourceId,
                "SUCCESS",
                traceId,
                "{}",
                Instant.now()));
    }
}
