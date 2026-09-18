package com.example.copilot.approval.api;

import com.example.copilot.approval.domain.Approval;
import java.time.Instant;
import java.util.UUID;

public record ApprovalResource(
        UUID id,
        UUID analysisJobId,
        String status,
        String reason,
        UUID decidedBy,
        String decisionComment,
        Instant createdAt,
        Instant decidedAt,
        long version) {
    public static ApprovalResource from(Approval approval) {
        return new ApprovalResource(
                approval.getId(),
                approval.getAnalysisJobId(),
                approval.getStatus().name(),
                approval.getReason(),
                approval.getDecidedBy(),
                approval.getDecisionComment(),
                approval.getCreatedAt(),
                approval.getDecidedAt(),
                approval.getVersion());
    }
}
