package com.example.copilot.approval.repository;

import com.example.copilot.approval.domain.Approval;
import jakarta.persistence.LockModeType;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface ApprovalRepository extends JpaRepository<Approval, UUID> {
    Optional<Approval> findByAnalysisJobIdAndTenantId(UUID analysisJobId, UUID tenantId);

    List<Approval> findTop50ByTenantIdOrderByCreatedAtDesc(UUID tenantId);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select approval from Approval approval where approval.id = :id and approval.tenantId = :tenantId")
    Optional<Approval> findForDecision(@Param("id") UUID id, @Param("tenantId") UUID tenantId);
}
