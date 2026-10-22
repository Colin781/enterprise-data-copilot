package com.example.copilot.service;

import com.example.copilot.entity.AuditEvent;
import com.example.copilot.repository.AuditEventRepository;
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

    public void recordOutcome(UUID tenantId, UUID actorUserId, String action, String outcome, String traceId) {
        auditEventRepository.save(new AuditEvent(UUID.randomUUID(), tenantId, actorUserId, action,
                "INTELLIGENCE", null, outcome, traceId, "{}", Instant.now()));
    }
}
