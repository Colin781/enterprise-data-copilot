package com.example.copilot.approval.repository;

import com.example.copilot.approval.domain.Approval;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ApprovalRepository extends JpaRepository<Approval, UUID> {
    Optional<Approval> findByAnalysisJobIdAndTenantId(UUID analysisJobId, UUID tenantId);
}
