package com.example.copilot.analysis.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import jakarta.persistence.Version;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(
        name = "analysis_jobs",
        schema = "copilot",
        uniqueConstraints =
                @UniqueConstraint(
                        name = "uq_analysis_jobs_idempotency",
                        columnNames = {"tenant_id", "created_by", "idempotency_key"}))
public class AnalysisJob {

    @Id
    private UUID id;

    @Column(nullable = false)
    private UUID tenantId;

    @Column(nullable = false)
    private UUID dataSourceId;

    @Column(nullable = false)
    private UUID createdBy;

    @Column(nullable = false, length = 4000)
    private String question;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private AnalysisJobStatus status;

    @Column(nullable = false, length = 128)
    private String idempotencyKey;

    @Column(nullable = false, length = 64)
    private String requestHash;

    @Column(nullable = false, length = 64)
    private String traceId;

    @Version
    private long version;

    @Column(nullable = false, updatable = false)
    private Instant createdAt;

    @Column(nullable = false)
    private Instant updatedAt;

    private Instant finishedAt;

    protected AnalysisJob() {}

    public AnalysisJob(
            UUID id,
            UUID tenantId,
            UUID dataSourceId,
            UUID createdBy,
            String question,
            String idempotencyKey,
            String requestHash,
            String traceId) {
        this.id = id;
        this.tenantId = tenantId;
        this.dataSourceId = dataSourceId;
        this.createdBy = createdBy;
        this.question = question;
        this.status = AnalysisJobStatus.CREATED;
        this.idempotencyKey = idempotencyKey;
        this.requestHash = requestHash;
        this.traceId = traceId;
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

    public UUID getTenantId() {
        return tenantId;
    }

    public UUID getDataSourceId() {
        return dataSourceId;
    }

    public UUID getCreatedBy() {
        return createdBy;
    }

    public String getQuestion() {
        return question;
    }

    public AnalysisJobStatus getStatus() {
        return status;
    }

    public String getRequestHash() {
        return requestHash;
    }

    public String getTraceId() {
        return traceId;
    }

    public long getVersion() {
        return version;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public Instant getFinishedAt() {
        return finishedAt;
    }
}
