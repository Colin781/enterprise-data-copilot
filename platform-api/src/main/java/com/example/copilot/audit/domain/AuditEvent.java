package com.example.copilot.audit.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "audit_events", schema = "copilot")
public class AuditEvent {

    @Id
    private UUID id;

    @Column(nullable = false)
    private UUID tenantId;

    private UUID actorUserId;

    @Column(nullable = false, length = 80)
    private String action;

    @Column(nullable = false, length = 80)
    private String resourceType;

    private UUID resourceId;

    @Column(nullable = false, length = 32)
    private String outcome;

    @Column(nullable = false, length = 64)
    private String traceId;

    @Column(nullable = false)
    private String detailsJson;

    @Column(nullable = false, updatable = false)
    private Instant createdAt;

    protected AuditEvent() {}

    public AuditEvent(
            UUID id,
            UUID tenantId,
            UUID actorUserId,
            String action,
            String resourceType,
            UUID resourceId,
            String outcome,
            String traceId,
            String detailsJson,
            Instant createdAt) {
        this.id = id;
        this.tenantId = tenantId;
        this.actorUserId = actorUserId;
        this.action = action;
        this.resourceType = resourceType;
        this.resourceId = resourceId;
        this.outcome = outcome;
        this.traceId = traceId;
        this.detailsJson = detailsJson;
        this.createdAt = createdAt;
    }

    public UUID getId() {
        return id;
    }

    public UUID getTenantId() {
        return tenantId;
    }

    public String getAction() {
        return action;
    }

    public UUID getResourceId() {
        return resourceId;
    }

    public String getTraceId() {
        return traceId;
    }
}
