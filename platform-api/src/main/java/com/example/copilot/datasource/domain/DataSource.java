package com.example.copilot.datasource.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import jakarta.persistence.Version;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "data_sources", schema = "copilot")
public class DataSource {

    @Id
    private UUID id;

    @Column(nullable = false)
    private UUID tenantId;

    @Column(nullable = false, length = 160)
    private String name;

    @Column(nullable = false, length = 32)
    private String sourceType;

    @Column(nullable = false, length = 255)
    private String host;

    @Column(nullable = false)
    private int port;

    @Column(nullable = false, length = 128)
    private String databaseName;

    @Column(nullable = false, length = 63)
    private String allowedSchema;

    @Column(nullable = false, length = 255)
    private String secretRef;

    @Column(nullable = false)
    private boolean enabled;

    @Version
    private long version;

    @Column(nullable = false, updatable = false)
    private Instant createdAt;

    @Column(nullable = false)
    private Instant updatedAt;

    protected DataSource() {}

    public DataSource(
            UUID id,
            UUID tenantId,
            String name,
            String host,
            int port,
            String databaseName,
            String allowedSchema,
            String secretRef) {
        this.id = id;
        this.tenantId = tenantId;
        this.name = name;
        this.sourceType = "POSTGRESQL";
        this.host = host;
        this.port = port;
        this.databaseName = databaseName;
        this.allowedSchema = allowedSchema;
        this.secretRef = secretRef;
        this.enabled = true;
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

    public String getName() {
        return name;
    }

    public String getSourceType() {
        return sourceType;
    }

    public String getAllowedSchema() {
        return allowedSchema;
    }

    public boolean isEnabled() {
        return enabled;
    }

    public long getVersion() {
        return version;
    }

    public void rename(String newName) {
        this.name = newName;
    }
}
