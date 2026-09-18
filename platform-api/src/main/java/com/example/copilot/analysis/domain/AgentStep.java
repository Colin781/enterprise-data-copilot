package com.example.copilot.analysis.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "agent_steps", schema = "copilot")
public class AgentStep {

    @Id
    private UUID id;

    @Column(nullable = false)
    private UUID tenantId;

    @Column(nullable = false)
    private UUID analysisJobId;

    @Column(nullable = false, length = 80)
    private String stepName;

    @Column(nullable = false, length = 32)
    private String status;

    @Column(nullable = false)
    private int attempt;

    @Column(nullable = false, columnDefinition = "text")
    private String inputSummaryJson;

    @Column(nullable = false, columnDefinition = "text")
    private String outputSummaryJson;

    @Column(nullable = false)
    private long durationMs;

    @Column(length = 80)
    private String errorCode;

    @Column(nullable = false, updatable = false)
    private Instant createdAt;

    protected AgentStep() {}

    public AgentStep(
            UUID id,
            UUID tenantId,
            UUID analysisJobId,
            String stepName,
            String status,
            int attempt,
            String inputSummaryJson,
            String outputSummaryJson,
            long durationMs,
            String errorCode) {
        this.id = id;
        this.tenantId = tenantId;
        this.analysisJobId = analysisJobId;
        this.stepName = stepName;
        this.status = status;
        this.attempt = attempt;
        this.inputSummaryJson = inputSummaryJson;
        this.outputSummaryJson = outputSummaryJson;
        this.durationMs = durationMs;
        this.errorCode = errorCode;
    }

    @PrePersist
    void onCreate() {
        createdAt = Instant.now();
    }

    public UUID getId() {
        return id;
    }

    public String getStepName() {
        return stepName;
    }

    public String getStatus() {
        return status;
    }

    public int getAttempt() {
        return attempt;
    }

    public String getInputSummaryJson() {
        return inputSummaryJson;
    }

    public String getOutputSummaryJson() {
        return outputSummaryJson;
    }

    public long getDurationMs() {
        return durationMs;
    }

    public String getErrorCode() {
        return errorCode;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
