package com.example.copilot.approval.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import jakarta.persistence.Version;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "approvals", schema = "copilot")
public class Approval {

    @Id
    private UUID id;

    @Column(nullable = false)
    private UUID tenantId;

    @Column(nullable = false)
    private UUID analysisJobId;

    @Column(nullable = false)
    private UUID requestedBy;

    private UUID decidedBy;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private ApprovalStatus status;

    @Column(nullable = false, length = 500)
    private String reason;

    @Column(length = 500)
    private String decisionComment;

    @Version
    private long version;

    @Column(nullable = false, updatable = false)
    private Instant createdAt;

    @Column(nullable = false)
    private Instant updatedAt;

    private Instant decidedAt;

    protected Approval() {}

    public Approval(UUID id, UUID tenantId, UUID analysisJobId, UUID requestedBy, String reason) {
        this.id = id;
        this.tenantId = tenantId;
        this.analysisJobId = analysisJobId;
        this.requestedBy = requestedBy;
        this.status = ApprovalStatus.PENDING;
        this.reason = reason;
    }

    @PrePersist
    void onCreate() {
        var now = Instant.now();
        createdAt = now;
        updatedAt = now;
    }

    @PreUpdate
    void onUpdate() {
        updatedAt = Instant.now();
    }

    public UUID getId() {
        return id;
    }

    public ApprovalStatus getStatus() {
        return status;
    }

    public long getVersion() {
        return version;
    }
}
