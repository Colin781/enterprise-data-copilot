package com.example.copilot.analysis.repository;

import com.example.copilot.analysis.domain.AnalysisJob;
import com.example.copilot.analysis.domain.AnalysisJobStatus;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AnalysisJobRepository extends JpaRepository<AnalysisJob, UUID> {
    Optional<AnalysisJob> findByIdAndTenantId(UUID id, UUID tenantId);

    Optional<AnalysisJob> findByIdAndTenantIdAndCreatedBy(UUID id, UUID tenantId, UUID createdBy);

    Optional<AnalysisJob> findByTenantIdAndCreatedByAndIdempotencyKey(
            UUID tenantId, UUID createdBy, String idempotencyKey);

    List<AnalysisJob> findAllByStatusIn(Collection<AnalysisJobStatus> statuses);

    List<AnalysisJob> findTop50ByTenantIdOrderByCreatedAtDesc(UUID tenantId);

    List<AnalysisJob> findTop50ByTenantIdAndCreatedByOrderByCreatedAtDesc(UUID tenantId, UUID createdBy);
}
