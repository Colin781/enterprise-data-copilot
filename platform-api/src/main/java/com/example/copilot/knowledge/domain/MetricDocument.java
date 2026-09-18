package com.example.copilot.knowledge.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "metric_documents", schema = "copilot")
public class MetricDocument {

    @Id
    private UUID id;

    @Column(nullable = false)
    private UUID tenantId;

    @Column(nullable = false, length = 240)
    private String title;

    @Column(nullable = false)
    private int version;

    @Column(nullable = false, length = 32)
    private String status;

    @Column(nullable = false, length = 16)
    private String sourceType;

    @Column(nullable = false, length = 255)
    private String sourceName;

    @Column(nullable = false, length = 64)
    private String contentSha256;

    private UUID createdBy;

    @Column(nullable = false)
    private Instant createdAt;

    @Column(nullable = false)
    private Instant updatedAt;

    protected MetricDocument() {}

    public UUID getId() {
        return id;
    }

    public UUID getTenantId() {
        return tenantId;
    }

    public String getTitle() {
        return title;
    }

    public int getVersion() {
        return version;
    }

    public String getStatus() {
        return status;
    }

    public String getSourceType() {
        return sourceType;
    }

    public String getSourceName() {
        return sourceName;
    }

    public String getContentSha256() {
        return contentSha256;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
