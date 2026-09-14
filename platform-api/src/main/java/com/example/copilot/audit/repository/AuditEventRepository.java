package com.example.copilot.audit.repository;

import com.example.copilot.audit.domain.AuditEvent;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AuditEventRepository extends JpaRepository<AuditEvent, UUID> {
    List<AuditEvent> findAllByTenantIdOrderByCreatedAtDesc(UUID tenantId);

    long countByTenantIdAndAction(UUID tenantId, String action);
}
